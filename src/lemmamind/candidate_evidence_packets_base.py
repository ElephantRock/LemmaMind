"""Deterministic bounded evidence packets for full-M5 ChangeInterpretation."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .candidate_evidence_packet_contracts import (
    AssertionSnapshotSide,
    CandidateEvidencePacket,
    SourceAssertionPreview,
    StructuralDeltaPreview,
)
from .candidate_extraction_gap_contracts import CandidateExtractionGapSignal
from .candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
)
from .change_contracts import ArtifactDelta, StructuralDelta
from .change_intelligence import ChangeIntelligenceError, DeterministicChangeService
from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
)
from .extraction_diagnostic_contracts import ExtractionDiagnostic
from .interval_segmentation_contracts import IntervalCandidateSegment


class CandidateEvidencePacketError(RuntimeError):
    """A factual generation cannot be projected safely into interpretation input."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class CandidateEvidencePacketResult:
    reduction_run_id: str
    packets: tuple[CandidateEvidencePacket, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.packets, self.run)


class CandidateEvidencePacketService:
    """Build one bounded deterministic packet per retained factual candidate."""

    _REDUCTION_POLICIES = {
        "candidate-factual-reduction.v1",
        "candidate-factual-reduction.gap-aware.v1",
    }
    _STRICT_EXTRACTION_POLICY = "deterministic-evidence.v1"

    def __init__(
        self,
        store: ContractStore,
        *,
        policy_version: str = "candidate-evidence-packet.v1",
        code_version: str = "lemmamind-0.1.0",
        max_structural_previews: int = 256,
        max_assertion_previews: int = 128,
        preview_chars: int = 512,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_structural_previews < 1:
            raise ValueError("max_structural_previews must be positive")
        if max_assertion_previews < 1:
            raise ValueError("max_assertion_previews must be positive")
        if preview_chars < 32:
            raise ValueError("preview_chars must be at least 32")
        self.store = store
        self.policy_version = policy_version
        self.code_version = code_version
        self.max_structural_previews = max_structural_previews
        self.max_assertion_previews = max_assertion_previews
        self.preview_chars = preview_chars
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def build_reduction(self, reduction_run_id: str) -> CandidateEvidencePacketResult:
        started_at = self._aware_now()
        reduction_run, pairs = self._authenticated_reduction_generation(
            reduction_run_id
        )

        packet_run_id = f"run:candidate-evidence-packet:{self.id_factory()}"
        packets = tuple(
            self._build_packet(reduction, candidate, packet_run_id)
            for candidate, reduction in pairs
            if reduction.disposition is CandidateReductionDisposition.RETAIN
        )

        inputs_hash = self._digest_json(
            {
                "reduction_run": reduction_run.model_dump(
                    mode="json", by_alias=True
                ),
                "policy_version": self.policy_version,
                "max_structural_previews": self.max_structural_previews,
                "max_assertion_previews": self.max_assertion_previews,
                "preview_chars": self.preview_chars,
            }
        )
        outputs_hash = self._digest_json(
            [self._stable_packet_payload(item) for item in packets]
        )
        run = PipelineRun(
            run_id=packet_run_id,
            run_type=RunType.OTHER,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = CandidateEvidencePacketResult(reduction_run_id, packets, run)
        self.store.put_many(result.records())
        return result

    def _authenticated_reduction_generation(
        self,
        reduction_run_id: str,
    ) -> tuple[
        PipelineRun,
        tuple[tuple[IntervalCandidateSegment, CandidateFactualReduction], ...],
    ]:
        run = self._completed_run(
            reduction_run_id, RunType.OTHER, "candidate factual reduction"
        )
        if run.policy_version not in self._REDUCTION_POLICIES:
            raise CandidateEvidencePacketError(
                "candidate evidence packets require a known factual-reduction policy"
            )

        reductions = tuple(
            item
            for item in self.store.list(CandidateFactualReduction)
            if item.reduction_run_id == reduction_run_id
        )
        if not reductions:
            raise CandidateEvidencePacketError(
                "candidate factual-reduction generation is empty"
            )
        segmentation_ids = {item.segmentation_run_id for item in reductions}
        if len(segmentation_ids) != 1:
            raise CandidateEvidencePacketError(
                "candidate factual reductions span multiple segmentation generations"
            )
        segmentation_run_id = next(iter(segmentation_ids))

        candidates = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(IntervalCandidateSegment)
                    if item.segmentation_run_id == segmentation_run_id
                ),
                key=lambda item: (
                    item.commit_ordinal,
                    item.path_group,
                    item.chunk_ordinal,
                    item.interval_candidate_segment_id,
                ),
            )
        )
        reduction_by_candidate: dict[str, CandidateFactualReduction] = {}
        for reduction in reductions:
            candidate_id = reduction.interval_candidate_segment_id
            if candidate_id in reduction_by_candidate:
                raise CandidateEvidencePacketError(
                    "candidate factual-reduction generation contains duplicate candidates"
                )
            reduction_by_candidate[candidate_id] = reduction

        expected_candidate_ids = {
            item.interval_candidate_segment_id for item in candidates
        }
        if set(reduction_by_candidate) != expected_candidate_ids:
            raise CandidateEvidencePacketError(
                "candidate factual reductions do not cover segmentation exactly"
            )

        pairs: list[tuple[IntervalCandidateSegment, CandidateFactualReduction]] = []
        for candidate in candidates:
            reduction = reduction_by_candidate[candidate.interval_candidate_segment_id]
            self._validate_reduction_lineage(candidate, reduction, reduction_run_id)
            pairs.append((candidate, reduction))

        expected_outputs_hash = self._digest_json(
            [
                reduction.model_dump(mode="json", by_alias=True)
                for _, reduction in pairs
            ]
        )
        if run.outputs_hash != expected_outputs_hash:
            raise CandidateEvidencePacketError(
                "candidate factual-reduction output envelope does not authenticate"
            )
        return run, tuple(pairs)

    @staticmethod
    def _validate_reduction_lineage(
        candidate: IntervalCandidateSegment,
        reduction: CandidateFactualReduction,
        reduction_run_id: str,
    ) -> None:
        expected = (
            candidate.interval_candidate_segment_id,
            candidate.source_id,
            candidate.previous_source_revision_id,
            candidate.current_source_revision_id,
            candidate.paths,
            candidate.segmentation_run_id,
            reduction_run_id,
        )
        observed = (
            reduction.interval_candidate_segment_id,
            reduction.source_id,
            reduction.previous_source_revision_id,
            reduction.current_source_revision_id,
            reduction.paths,
            reduction.segmentation_run_id,
            reduction.reduction_run_id,
        )
        if observed != expected:
            raise CandidateEvidencePacketError(
                "candidate factual-reduction lineage disagrees with interval candidate"
            )

    def _build_packet(
        self,
        reduction: CandidateFactualReduction,
        candidate: IntervalCandidateSegment,
        packet_run_id: str,
    ) -> CandidateEvidencePacket:
        self._authenticate_extraction_run(reduction.previous_extraction_run_id)
        self._authenticate_extraction_run(reduction.current_extraction_run_id)

        artifacts = self._artifact_deltas(reduction)
        structural = self._structural_deltas(reduction, artifacts)
        structural_selected = self._round_robin_by_path(
            structural,
            self.max_structural_previews,
            path_of=lambda item: item.source_locator,
            item_key=lambda item: (
                item.structural_key,
                item.structural_delta_id,
            ),
        )
        structural_previews = tuple(
            self._structural_preview(item) for item in structural_selected
        )

        assertions = self._assertion_snapshots(reduction)
        assertion_selected = self._round_robin_by_path(
            assertions,
            self.max_assertion_previews,
            path_of=lambda item: item[1],
            item_key=lambda item: (
                item[0].value,
                item[2].locator,
                item[2].assertion_id,
            ),
        )
        assertion_previews = tuple(
            self._assertion_preview(side, path, item)
            for side, path, item in assertion_selected
        )

        gap_signals = self._gap_signals(reduction)
        gap_paths = tuple(
            sorted({path for signal in gap_signals for path in signal.paths})
        )

        return CandidateEvidencePacket(
            candidate_evidence_packet_id=self._packet_id(
                packet_run_id,
                candidate.interval_candidate_segment_id,
            ),
            interval_candidate_segment_id=candidate.interval_candidate_segment_id,
            candidate_factual_reduction_id=reduction.candidate_factual_reduction_id,
            source_id=reduction.source_id,
            previous_source_revision_id=reduction.previous_source_revision_id,
            current_source_revision_id=reduction.current_source_revision_id,
            paths=reduction.paths,
            signal_kinds=reduction.signal_kinds,
            policy_suppressed_paths=reduction.policy_suppressed_paths,
            artifact_only_paths=reduction.artifact_only_paths,
            git_only_paths=reduction.git_only_paths,
            artifact_delta_ids=tuple(
                sorted(item.artifact_delta_id for item in artifacts)
            ),
            structural_delta_total=len(structural),
            structural_delta_previews=structural_previews,
            structural_delta_omitted_count=(
                len(structural) - len(structural_previews)
            ),
            assertion_snapshot_total=len(assertions),
            assertion_previews=assertion_previews,
            assertion_snapshot_omitted_count=(
                len(assertions) - len(assertion_previews)
            ),
            extraction_gap_signal_ids=tuple(
                sorted(
                    item.candidate_extraction_gap_signal_id
                    for item in gap_signals
                )
            ),
            extraction_gap_paths=gap_paths,
            segmentation_run_id=reduction.segmentation_run_id,
            reduction_run_id=reduction.reduction_run_id,
            previous_extraction_run_id=reduction.previous_extraction_run_id,
            current_extraction_run_id=reduction.current_extraction_run_id,
            change_run_id=reduction.change_run_id,
            packet_run_id=packet_run_id,
        )

    def _artifact_deltas(
        self,
        reduction: CandidateFactualReduction,
    ) -> tuple[ArtifactDelta, ...]:
        previous_manifest = self._manifest(
            reduction.previous_capture_id,
            reduction.previous_source_revision_id,
        )
        current_manifest = self._manifest(
            reduction.current_capture_id,
            reduction.current_source_revision_id,
        )
        previous_by_path = {
            item.source_locator: item for item in previous_manifest.artifacts
        }
        current_by_path = {
            item.source_locator: item for item in current_manifest.artifacts
        }

        result: list[ArtifactDelta] = []
        for artifact_delta_id in reduction.artifact_delta_ids:
            item = self.store.get(ArtifactDelta, artifact_delta_id)
            if item is None:
                raise CandidateEvidencePacketError(
                    f"missing ArtifactDelta referenced by reduction: {artifact_delta_id}"
                )
            expected = (
                reduction.source_id,
                reduction.previous_source_revision_id,
                reduction.current_source_revision_id,
                reduction.previous_capture_id,
                reduction.current_capture_id,
                reduction.change_run_id,
            )
            observed = (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                item.previous_capture_id,
                item.current_capture_id,
                item.diff_run_id,
            )
            if observed != expected or item.source_locator not in reduction.paths:
                raise CandidateEvidencePacketError(
                    "ArtifactDelta lineage disagrees with candidate factual reduction"
                )
            self._validate_artifact_delta_state(
                item,
                previous_by_path.get(item.source_locator),
                current_by_path.get(item.source_locator),
            )
            result.append(item)
        if tuple(sorted(item.source_locator for item in result)) != tuple(
            reduction.artifact_delta_paths
        ):
            raise CandidateEvidencePacketError(
                "ArtifactDelta path coverage disagrees with candidate factual reduction"
            )
        return tuple(sorted(result, key=lambda item: item.source_locator))

    @staticmethod
    def _validate_artifact_delta_state(
        item: ArtifactDelta,
        previous_reference,
        current_reference,
    ) -> None:
        expected_previous = (
            None
            if previous_reference is None
            else (
                previous_reference.artifact_id,
                previous_reference.retrieval_status,
                previous_reference.content_hash,
                previous_reference.media_type,
            )
        )
        expected_current = (
            None
            if current_reference is None
            else (
                current_reference.artifact_id,
                current_reference.retrieval_status,
                current_reference.content_hash,
                current_reference.media_type,
            )
        )
        observed_previous = (
            None
            if item.previous_retrieval_status is None
            else (
                item.previous_artifact_id,
                item.previous_retrieval_status,
                item.previous_content_hash,
                item.previous_media_type,
            )
        )
        observed_current = (
            None
            if item.current_retrieval_status is None
            else (
                item.current_artifact_id,
                item.current_retrieval_status,
                item.current_content_hash,
                item.current_media_type,
            )
        )
        if observed_previous != expected_previous or observed_current != expected_current:
            raise CandidateEvidencePacketError(
                "ArtifactDelta state disagrees with exact candidate capture manifests"
            )

    def _structural_deltas(
        self,
        reduction: CandidateFactualReduction,
        artifacts: tuple[ArtifactDelta, ...],
    ) -> tuple[StructuralDelta, ...]:
        artifact_ids = {item.artifact_delta_id for item in artifacts}
        result: list[StructuralDelta] = []
        for structural_delta_id in reduction.structural_delta_ids:
            item = self.store.get(StructuralDelta, structural_delta_id)
            if item is None:
                raise CandidateEvidencePacketError(
                    f"missing StructuralDelta referenced by reduction: {structural_delta_id}"
                )
            expected = (
                reduction.source_id,
                reduction.previous_source_revision_id,
                reduction.current_source_revision_id,
                reduction.change_run_id,
            )
            observed = (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                item.diff_run_id,
            )
            if (
                observed != expected
                or item.source_locator not in reduction.paths
                or item.artifact_delta_id not in artifact_ids
            ):
                raise CandidateEvidencePacketError(
                    "StructuralDelta lineage disagrees with candidate factual reduction"
                )
            self._validate_structural_evidence(item, reduction)
            result.append(item)
        if tuple(
            sorted({item.source_locator for item in result})
        ) != reduction.structural_delta_paths:
            raise CandidateEvidencePacketError(
                "StructuralDelta path coverage disagrees with candidate factual reduction"
            )
        return tuple(
            sorted(
                result,
                key=lambda item: (
                    item.source_locator,
                    item.structural_key,
                    item.structural_delta_id,
                ),
            )
        )

    def _validate_structural_evidence(
        self,
        item: StructuralDelta,
        reduction: CandidateFactualReduction,
    ) -> None:
        previous_manifest = self._manifest(
            reduction.previous_capture_id,
            reduction.previous_source_revision_id,
        )
        current_manifest = self._manifest(
            reduction.current_capture_id,
            reduction.current_source_revision_id,
        )
        previous_artifact_to_path = {
            reference.artifact_id: reference.source_locator
            for reference in previous_manifest.artifacts
            if reference.retrieval_status is RetrievalStatus.CAPTURED
        }
        current_artifact_to_path = {
            reference.artifact_id: reference.source_locator
            for reference in current_manifest.artifacts
            if reference.retrieval_status is RetrievalStatus.CAPTURED
        }

        for evidence_id, expected_run_id, expected_locator, expected_value, artifact_paths, label in (
            (
                item.previous_evidence_id,
                reduction.previous_extraction_run_id,
                item.previous_locator,
                item.previous_value,
                previous_artifact_to_path,
                "previous",
            ),
            (
                item.current_evidence_id,
                reduction.current_extraction_run_id,
                item.current_locator,
                item.current_value,
                current_artifact_to_path,
                "current",
            ),
        ):
            if evidence_id is None:
                continue
            fact = self.store.get(EvidenceFact, evidence_id)
            if fact is None:
                raise CandidateEvidencePacketError(
                    f"missing {label} EvidenceFact referenced by StructuralDelta: {evidence_id}"
                )
            if (
                fact.run_id != expected_run_id
                or artifact_paths.get(fact.artifact_id) != item.source_locator
                or fact.locator != expected_locator
                or fact.normalized_value != expected_value
                or fact.extractor_name != item.extractor_name
                or fact.extractor_version != item.extractor_version
            ):
                raise CandidateEvidencePacketError(
                    f"{label} StructuralDelta evidence disagrees with exact extraction generation"
                )

    def _assertion_snapshots(
        self,
        reduction: CandidateFactualReduction,
    ) -> tuple[tuple[AssertionSnapshotSide, str, SourceAssertion], ...]:
        previous_manifest = self._manifest(
            reduction.previous_capture_id,
            reduction.previous_source_revision_id,
        )
        current_manifest = self._manifest(
            reduction.current_capture_id,
            reduction.current_source_revision_id,
        )
        result: list[tuple[AssertionSnapshotSide, str, SourceAssertion]] = []
        for side, manifest, run_id in (
            (
                AssertionSnapshotSide.PREVIOUS,
                previous_manifest,
                reduction.previous_extraction_run_id,
            ),
            (
                AssertionSnapshotSide.CURRENT,
                current_manifest,
                reduction.current_extraction_run_id,
            ),
        ):
            artifact_to_path = {
                item.artifact_id: item.source_locator
                for item in manifest.artifacts
                if item.retrieval_status is RetrievalStatus.CAPTURED
            }
            for assertion in self.store.list(SourceAssertion):
                if assertion.run_id != run_id:
                    continue
                path = artifact_to_path.get(assertion.artifact_id)
                if path is None:
                    raise CandidateEvidencePacketError(
                        "SourceAssertion extraction provenance is outside candidate capture"
                    )
                if not assertion.locator.startswith(path):
                    raise CandidateEvidencePacketError(
                        "SourceAssertion locator is not anchored to candidate artifact path"
                    )
                if path in reduction.assertion_changed_paths:
                    result.append((side, path, assertion))

        return tuple(
            sorted(
                result,
                key=lambda item: (
                    item[1],
                    item[0].value,
                    item[2].locator,
                    item[2].assertion_id,
                ),
            )
        )

    def _gap_signals(
        self,
        reduction: CandidateFactualReduction,
    ) -> tuple[CandidateExtractionGapSignal, ...]:
        result = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(CandidateExtractionGapSignal)
                    if item.interval_candidate_segment_id
                    == reduction.interval_candidate_segment_id
                    and item.reduction_run_id == reduction.reduction_run_id
                ),
                key=lambda item: item.candidate_extraction_gap_signal_id,
            )
        )
        for item in result:
            expected = (
                reduction.source_id,
                reduction.previous_source_revision_id,
                reduction.current_source_revision_id,
                reduction.previous_capture_id,
                reduction.current_capture_id,
                reduction.segmentation_run_id,
                reduction.previous_extraction_run_id,
                reduction.current_extraction_run_id,
                reduction.reduction_run_id,
            )
            observed = (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                item.previous_capture_id,
                item.current_capture_id,
                item.segmentation_run_id,
                item.previous_extraction_run_id,
                item.current_extraction_run_id,
                item.reduction_run_id,
            )
            if observed != expected or not set(item.paths).issubset(
                set(reduction.paths)
            ):
                raise CandidateEvidencePacketError(
                    "CandidateExtractionGapSignal lineage disagrees with factual reduction"
                )
            self._validate_gap_diagnostics(item, reduction)
        return result

    def _validate_gap_diagnostics(
        self,
        signal: CandidateExtractionGapSignal,
        reduction: CandidateFactualReduction,
    ) -> None:
        for diagnostic_id, expected_run_id, expected_capture_id, expected_revision_id, label in (
            *(
                (
                    item,
                    reduction.previous_extraction_run_id,
                    reduction.previous_capture_id,
                    reduction.previous_source_revision_id,
                    "previous",
                )
                for item in signal.previous_diagnostic_ids
            ),
            *(
                (
                    item,
                    reduction.current_extraction_run_id,
                    reduction.current_capture_id,
                    reduction.current_source_revision_id,
                    "current",
                )
                for item in signal.current_diagnostic_ids
            ),
        ):
            diagnostic = self.store.get(ExtractionDiagnostic, diagnostic_id)
            if diagnostic is None:
                raise CandidateEvidencePacketError(
                    f"missing {label} extraction diagnostic referenced by gap signal"
                )
            if (
                diagnostic.run_id != expected_run_id
                or diagnostic.capture_id != expected_capture_id
                or diagnostic.source_revision_id != expected_revision_id
                or diagnostic.source_locator not in signal.paths
            ):
                raise CandidateEvidencePacketError(
                    f"{label} extraction diagnostic disagrees with candidate gap lineage"
                )

    def _authenticate_extraction_run(self, run_id: str) -> None:
        run = self._completed_run(run_id, RunType.EXTRACTION, "extraction")
        authenticator = DeterministicChangeService(self.store, None)
        try:
            if run.policy_version == self._STRICT_EXTRACTION_POLICY:
                facts = tuple(
                    item
                    for item in self.store.list(EvidenceFact)
                    if item.run_id == run_id
                )
                assertions = tuple(
                    item
                    for item in self.store.list(SourceAssertion)
                    if item.run_id == run_id
                )
                diagnostics = authenticator._diagnostics_for_run(run)
                if diagnostics:
                    raise CandidateEvidencePacketError(
                        "strict extraction run unexpectedly contains diagnostics"
                    )
                payload = authenticator._extraction_output_payload(
                    facts, assertions
                )
                if run.outputs_hash != self._digest_json(payload):
                    raise CandidateEvidencePacketError(
                        "strict extraction output envelope does not authenticate"
                    )
            else:
                authenticator._authenticate_gap_tolerant_extraction_run(run)
        except ChangeIntelligenceError as exc:
            raise CandidateEvidencePacketError(
                "extraction output envelope does not authenticate"
            ) from exc

    def _manifest(
        self,
        capture_id: str,
        source_revision_id: str,
    ) -> CaptureManifest:
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise CandidateEvidencePacketError(
                f"missing candidate capture manifest: {capture_id}"
            )
        if manifest.source_revision_id != source_revision_id:
            raise CandidateEvidencePacketError(
                "candidate capture revision disagrees with factual reduction"
            )
        return manifest

    def _structural_preview(
        self,
        item: StructuralDelta,
    ) -> StructuralDeltaPreview:
        previous, previous_truncated = self._preview_json(item.previous_value)
        current, current_truncated = self._preview_json(item.current_value)
        return StructuralDeltaPreview(
            structural_delta_id=item.structural_delta_id,
            source_locator=item.source_locator,
            structural_key=item.structural_key,
            change_type=item.change_type,
            extractor_name=item.extractor_name,
            extractor_version=item.extractor_version,
            previous_value_preview=previous,
            current_value_preview=current,
            value_preview_truncated=(
                previous_truncated or current_truncated
            ),
        )

    def _assertion_preview(
        self,
        side: AssertionSnapshotSide,
        path: str,
        item: SourceAssertion,
    ) -> SourceAssertionPreview:
        statement, truncated = self._preview_text(item.statement)
        return SourceAssertionPreview(
            assertion_id=item.assertion_id,
            side=side,
            source_locator=path,
            locator=item.locator,
            statement_preview=statement,
            statement_truncated=truncated,
            extractor_name=item.extractor_name,
            extractor_version=item.extractor_version,
        )

    def _preview_json(self, value: object) -> tuple[str | None, bool]:
        if value is None:
            return None, False
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return self._preview_text(text)

    def _preview_text(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.preview_chars:
            return text, False
        return text[: self.preview_chars - 1] + "…", True

    @staticmethod
    def _round_robin_by_path(
        items: tuple,
        limit: int,
        *,
        path_of,
        item_key,
    ) -> tuple:
        groups: dict[str, list] = {}
        for item in items:
            groups.setdefault(path_of(item), []).append(item)
        for values in groups.values():
            values.sort(key=item_key)

        selected: list = []
        depth = 0
        paths = sorted(groups)
        while len(selected) < limit:
            added = False
            for path in paths:
                values = groups[path]
                if depth < len(values):
                    selected.append(values[depth])
                    added = True
                    if len(selected) == limit:
                        break
            if not added:
                break
            depth += 1
        return tuple(selected)

    def _completed_run(
        self,
        run_id: str,
        run_type: RunType,
        label: str,
    ) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise CandidateEvidencePacketError(
                f"unknown {label} PipelineRun: {run_id}"
            )
        if run.run_type is not run_type or run.finished_at is None:
            raise CandidateEvidencePacketError(
                f"{label} requires one completed {run_type.value} PipelineRun"
            )
        return run

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "candidate evidence packet clock must return timezone-aware datetimes"
            )
        return value

    @staticmethod
    def _packet_id(run_id: str, candidate_id: str) -> str:
        material = f"candidate-evidence-packet\0{run_id}\0{candidate_id}".encode(
            "utf-8"
        )
        return f"candidate-evidence-packet:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _stable_packet_payload(item: CandidateEvidencePacket) -> dict:
        payload = item.model_dump(mode="json", by_alias=True)
        payload.pop("candidate_evidence_packet_id", None)
        payload.pop("packet_run_id", None)
        return payload

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
