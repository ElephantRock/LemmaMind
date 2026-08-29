"""M5-lite deterministic change intelligence over reconstructable captures.

This module implements only the factual layers of the roadmap:

    ArtifactDelta -> StructuralDelta

ArtifactDelta compares exact CaptureManifest state. StructuralDelta compares
normalized EvidenceFact generations produced by explicitly compatible extraction
runs. ChangeInterpretation, importance, causality, and action recommendations are
out of scope.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Protocol

from .change_contracts import (
    ArtifactDelta,
    ArtifactDeltaType,
    StructuralDelta,
    StructuralDeltaType,
)
from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
)
from .extraction import (
    ArtifactExtractor,
    AssertionSpec,
    DeterministicExtractionService,
    FactSpec,
)
from .extraction_diagnostic_contracts import ExtractionDiagnostic
from .objects import ContentAddressedFileStore
from .revision_capture import (
    CaptureReconstructionService,
    ReconstructedArtifact,
    ReconstructedCapture,
)


class ChangeIntelligenceError(RuntimeError):
    """Two persisted generations cannot be compared under the M5-lite contract."""


class DeterminismViolation(ChangeIntelligenceError):
    """Equivalent source bytes produced incompatible deterministic evidence."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class DeterministicChangeResult:
    previous_capture_id: str
    current_capture_id: str
    artifact_deltas: tuple[ArtifactDelta, ...]
    structural_deltas: tuple[StructuralDelta, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.artifact_deltas, *self.structural_deltas, self.run)


class DeterministicChangeService:
    """Compare two exact local capture generations without semantic interpretation."""

    STRICT_EXTRACTION_POLICY_VERSION = "deterministic-evidence.v1"

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "deterministic-change.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.object_store = object_store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self.reconstruction = CaptureReconstructionService(store, object_store)

    def compare_captures(
        self,
        previous_capture_id: str,
        current_capture_id: str,
        *,
        previous_extraction_run_id: str | None = None,
        current_extraction_run_id: str | None = None,
        artifact_extractors: Iterable[ArtifactExtractor] | None = None,
    ) -> DeterministicChangeResult:
        if (previous_extraction_run_id is None) != (current_extraction_run_id is None):
            raise ValueError(
                "previous_extraction_run_id and current_extraction_run_id must be supplied together"
            )
        if previous_extraction_run_id is not None and artifact_extractors is None:
            raise ValueError(
                "artifact_extractors is required for structural comparison so extraction "
                "run inputs can be verified exactly"
            )

        extractor_profile = (
            () if artifact_extractors is None else tuple(artifact_extractors)
        )
        if artifact_extractors is not None and not extractor_profile:
            raise ValueError("artifact_extractors must not be empty for structural comparison")
        extractor_descriptors = self._extractor_descriptors(extractor_profile)

        started_at = self._aware_now()
        previous = self.reconstruction.reconstruct(previous_capture_id)
        current = self.reconstruction.reconstruct(current_capture_id)
        self._validate_capture_pair(previous, current)

        run_id = f"run:{self.id_factory()}"
        artifact_deltas = self._artifact_deltas(previous, current, run_id)
        structural_deltas: tuple[StructuralDelta, ...] = ()

        if previous_extraction_run_id is not None and current_extraction_run_id is not None:
            structural_deltas = self._structural_deltas(
                previous,
                current,
                artifact_deltas,
                previous_extraction_run_id,
                current_extraction_run_id,
                extractor_descriptors,
                run_id,
            )

        inputs_hash = self._digest_json(
            {
                "previous_capture_id": previous.manifest.capture_id,
                "current_capture_id": current.manifest.capture_id,
                "previous_source_revision_id": previous.revision.source_revision_id,
                "current_source_revision_id": current.revision.source_revision_id,
                "previous_extraction_run_id": previous_extraction_run_id,
                "current_extraction_run_id": current_extraction_run_id,
                "artifact_extractors": extractor_descriptors,
                "policy_version": self.policy_version,
                "artifact_inputs": {
                    "previous": [self._artifact_state(item) for item in previous.artifacts],
                    "current": [self._artifact_state(item) for item in current.artifacts],
                },
            }
        )
        outputs_hash = self._digest_json(
            {
                "artifact_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in artifact_deltas
                ],
                "structural_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in structural_deltas
                ],
            }
        )
        pipeline_run = PipelineRun(
            run_id=run_id,
            run_type=RunType.DIFF,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = DeterministicChangeResult(
            previous.manifest.capture_id,
            current.manifest.capture_id,
            artifact_deltas,
            structural_deltas,
            pipeline_run,
        )
        self.store.put_many(result.records())
        return result

    def _validate_capture_pair(
        self,
        previous: ReconstructedCapture,
        current: ReconstructedCapture,
    ) -> None:
        if previous.revision.source_id != current.revision.source_id:
            raise ChangeIntelligenceError(
                "M5-lite comparison requires captures from the same Source"
            )
        if previous.revision.observed_at > current.revision.observed_at:
            raise ChangeIntelligenceError(
                "previous SourceRevision must not be newer than current SourceRevision"
            )
        if previous.manifest.captured_at > current.manifest.captured_at:
            raise ChangeIntelligenceError(
                "previous CaptureManifest must not be newer than current CaptureManifest"
            )

    def _artifact_deltas(
        self,
        previous: ReconstructedCapture,
        current: ReconstructedCapture,
        run_id: str,
    ) -> tuple[ArtifactDelta, ...]:
        previous_by_locator = {item.source_locator: item for item in previous.artifacts}
        current_by_locator = {item.source_locator: item for item in current.artifacts}
        deltas: list[ArtifactDelta] = []

        for source_locator in sorted(set(previous_by_locator) | set(current_by_locator)):
            old = previous_by_locator.get(source_locator)
            new = current_by_locator.get(source_locator)
            change_type = self._artifact_change_type(old, new)
            if change_type is None:
                continue
            deltas.append(
                ArtifactDelta(
                    artifact_delta_id=self._artifact_delta_id(run_id, source_locator),
                    source_id=current.revision.source_id,
                    previous_source_revision_id=previous.revision.source_revision_id,
                    current_source_revision_id=current.revision.source_revision_id,
                    previous_capture_id=previous.manifest.capture_id,
                    current_capture_id=current.manifest.capture_id,
                    source_locator=source_locator,
                    change_type=change_type,
                    previous_artifact_id=None if old is None else old.artifact_id,
                    current_artifact_id=None if new is None else new.artifact_id,
                    previous_retrieval_status=None if old is None else old.retrieval_status,
                    current_retrieval_status=None if new is None else new.retrieval_status,
                    previous_content_hash=None if old is None else old.content_hash,
                    current_content_hash=None if new is None else new.content_hash,
                    previous_media_type=None if old is None else old.media_type,
                    current_media_type=None if new is None else new.media_type,
                    diff_run_id=run_id,
                )
            )
        return tuple(deltas)

    @staticmethod
    def _artifact_change_type(
        previous: ReconstructedArtifact | None,
        current: ReconstructedArtifact | None,
    ) -> ArtifactDeltaType | None:
        if previous is None:
            return ArtifactDeltaType.CAPTURE_SCOPE_ADDED
        if current is None:
            return ArtifactDeltaType.CAPTURE_SCOPE_REMOVED

        if (
            previous.retrieval_status is RetrievalStatus.MISSING
            and current.retrieval_status is RetrievalStatus.MISSING
        ):
            return None
        if (
            previous.retrieval_status is RetrievalStatus.MISSING
            and current.retrieval_status is RetrievalStatus.CAPTURED
        ):
            return ArtifactDeltaType.BECAME_CAPTURED
        if (
            previous.retrieval_status is RetrievalStatus.CAPTURED
            and current.retrieval_status is RetrievalStatus.MISSING
        ):
            return ArtifactDeltaType.BECAME_MISSING
        if (
            previous.retrieval_status is RetrievalStatus.CAPTURED
            and current.retrieval_status is RetrievalStatus.CAPTURED
        ):
            if previous.content_hash != current.content_hash:
                return ArtifactDeltaType.CONTENT_CHANGED
            if previous.media_type != current.media_type:
                return ArtifactDeltaType.METADATA_CHANGED
            return None

        raise ChangeIntelligenceError(
            "M5-lite encountered non-reconstructable retrieval-state transition"
        )

    def _structural_deltas(
        self,
        previous: ReconstructedCapture,
        current: ReconstructedCapture,
        artifact_deltas: tuple[ArtifactDelta, ...],
        previous_extraction_run_id: str,
        current_extraction_run_id: str,
        extractor_descriptors: tuple[dict[str, str], ...],
        run_id: str,
    ) -> tuple[StructuralDelta, ...]:
        previous_run, previous_facts = self._extraction_generation(
            previous, previous_extraction_run_id, extractor_descriptors
        )
        current_run, current_facts = self._extraction_generation(
            current, current_extraction_run_id, extractor_descriptors
        )
        self._require_strict_extraction_run(previous_run)
        self._require_strict_extraction_run(current_run)
        self._require_compatible_extraction_runs(previous_run, current_run)

        previous_map = self._fact_map(previous, previous_facts)
        current_map = self._fact_map(current, current_facts)
        comparable_locators = {item.source_locator for item in previous.artifacts} & {
            item.source_locator for item in current.artifacts
        }
        artifact_delta_by_locator = {
            item.source_locator: item
            for item in artifact_deltas
            if item.change_type
            not in {
                ArtifactDeltaType.CAPTURE_SCOPE_ADDED,
                ArtifactDeltaType.CAPTURE_SCOPE_REMOVED,
            }
        }

        structural: list[StructuralDelta] = []
        for key in sorted(set(previous_map) | set(current_map)):
            source_locator, extractor_name, extractor_version, relative_locator = key
            if source_locator not in comparable_locators:
                continue

            old = previous_map.get(key)
            new = current_map.get(key)
            if old is not None and new is not None:
                if old.normalized_value == new.normalized_value:
                    continue
                change_type = StructuralDeltaType.MODIFIED
            elif old is None:
                change_type = StructuralDeltaType.ADDED
            else:
                change_type = StructuralDeltaType.REMOVED

            artifact_delta = artifact_delta_by_locator.get(source_locator)
            if artifact_delta is None:
                raise DeterminismViolation(
                    "deterministic evidence changed without an ArtifactDelta for "
                    f"{source_locator}; identical capture state cannot yield a structural delta"
                )

            structural_key = (
                f"{extractor_name}@{extractor_version}:{relative_locator or '#root'}"
            )
            structural.append(
                StructuralDelta(
                    structural_delta_id=self._structural_delta_id(
                        run_id,
                        artifact_delta.artifact_delta_id,
                        structural_key,
                        change_type,
                    ),
                    artifact_delta_id=artifact_delta.artifact_delta_id,
                    source_id=current.revision.source_id,
                    previous_source_revision_id=previous.revision.source_revision_id,
                    current_source_revision_id=current.revision.source_revision_id,
                    source_locator=source_locator,
                    structural_key=structural_key,
                    change_type=change_type,
                    extractor_name=extractor_name,
                    extractor_version=extractor_version,
                    previous_evidence_id=None if old is None else old.evidence_id,
                    current_evidence_id=None if new is None else new.evidence_id,
                    previous_locator=None if old is None else old.locator,
                    current_locator=None if new is None else new.locator,
                    previous_value=None if old is None else old.normalized_value,
                    current_value=None if new is None else new.normalized_value,
                    diff_run_id=run_id,
                )
            )
        return tuple(structural)

    def _extraction_generation(
        self,
        capture: ReconstructedCapture,
        run_id: str,
        extractor_descriptors: tuple[dict[str, str], ...],
    ) -> tuple[PipelineRun, tuple[EvidenceFact, ...]]:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise ChangeIntelligenceError(f"unknown extraction PipelineRun: {run_id}")
        if run.run_type is not RunType.EXTRACTION:
            raise ChangeIntelligenceError(
                f"structural comparison requires extraction runs: {run_id}"
            )
        if run.finished_at is None:
            raise ChangeIntelligenceError(
                f"structural comparison requires completed extraction runs: {run_id}"
            )

        expected_inputs_hash = self._digest_json(
            {
                "capture_manifest": capture.manifest.model_dump(mode="json", by_alias=True),
                "artifact_extractors": list(extractor_descriptors),
                "policy_version": run.policy_version,
            }
        )
        if run.inputs_hash != expected_inputs_hash:
            raise ChangeIntelligenceError(
                f"extraction run {run_id} does not match the supplied capture/extractor profile"
            )

        facts = tuple(fact for fact in self.store.list(EvidenceFact) if fact.run_id == run_id)
        assertions = tuple(
            item for item in self.store.list(SourceAssertion) if item.run_id == run_id
        )
        evidence_records: tuple[Any, ...] = (*facts, *assertions)

        allowed_artifact_ids = {
            item.artifact_id for item in capture.artifacts if item.is_captured
        }
        foreign = sorted(
            {
                item.artifact_id
                for item in evidence_records
                if item.artifact_id not in allowed_artifact_ids
            }
        )
        if foreign:
            raise ChangeIntelligenceError(
                f"extraction run {run_id} contains evidence outside "
                f"{capture.manifest.capture_id}: {foreign}"
            )
        return run, facts

    def _require_strict_extraction_run(self, run: PipelineRun) -> None:
        diagnostics = tuple(
            item
            for item in self.store.list(ExtractionDiagnostic)
            if item.run_id == run.run_id
        )
        if diagnostics:
            raise ChangeIntelligenceError(
                "strict deterministic change comparison rejects extraction runs containing diagnostics"
            )
        if run.policy_version != self.STRICT_EXTRACTION_POLICY_VERSION:
            raise ChangeIntelligenceError(
                "strict deterministic change comparison rejects gap-tolerant extraction runs or unrecognized extraction policies"
            )

    def _authenticate_gap_tolerant_extraction_run(self, run: PipelineRun) -> None:
        facts = tuple(
            item for item in self.store.list(EvidenceFact) if item.run_id == run.run_id
        )
        assertions = tuple(
            item for item in self.store.list(SourceAssertion) if item.run_id == run.run_id
        )
        diagnostics = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(ExtractionDiagnostic)
                    if item.run_id == run.run_id
                ),
                key=lambda item: (
                    item.source_locator,
                    item.extractor_name,
                    item.extractor_version,
                    item.error_type,
                    item.error_message,
                ),
            )
        )
        payload = self._extraction_output_payload(facts, assertions)
        payload["diagnostics"] = [
            self._diagnostic_payload(item) for item in diagnostics
        ]
        if run.outputs_hash != self._digest_json(payload):
            raise ChangeIntelligenceError(
                f"gap-tolerant extraction run {run.run_id} output envelope does not authenticate against outputs_hash"
            )

    @staticmethod
    def _require_compatible_extraction_runs(
        previous: PipelineRun,
        current: PipelineRun,
    ) -> None:
        previous_generation = (
            previous.code_version,
            previous.schema_version_used,
            previous.policy_version,
        )
        current_generation = (
            current.code_version,
            current.schema_version_used,
            current.policy_version,
        )
        if previous_generation != current_generation:
            raise ChangeIntelligenceError(
                "structural comparison requires matching deterministic extraction "
                "code/schema/policy generations"
            )

    @staticmethod
    def _fact_map(
        capture: ReconstructedCapture,
        facts: tuple[EvidenceFact, ...],
    ) -> dict[tuple[str, str, str, str], EvidenceFact]:
        artifact_by_id = {
            item.artifact_id: item for item in capture.artifacts if item.is_captured
        }
        result: dict[tuple[str, str, str, str], EvidenceFact] = {}

        for fact in facts:
            artifact = artifact_by_id.get(fact.artifact_id)
            if artifact is None:
                raise ChangeIntelligenceError(
                    f"EvidenceFact references non-captured artifact: {fact.artifact_id}"
                )
            if not fact.locator.startswith(artifact.source_locator):
                raise ChangeIntelligenceError(
                    "EvidenceFact locator is not anchored to Artifact.source_locator: "
                    f"{fact.locator}"
                )
            relative_locator = fact.locator[len(artifact.source_locator) :]
            key = (
                artifact.source_locator,
                fact.extractor_name,
                fact.extractor_version,
                relative_locator,
            )
            if key in result:
                raise ChangeIntelligenceError(
                    f"duplicate deterministic structural key in extraction run: {key}"
                )
            result[key] = fact
        return result

    @classmethod
    def _extraction_output_payload(
        cls,
        facts: tuple[EvidenceFact, ...],
        assertions: tuple[SourceAssertion, ...],
    ) -> dict[str, list[dict[str, object]]]:
        fact_specs = [
            FactSpec(
                locator=item.locator,
                raw_value=item.raw_value,
                normalized_value=item.normalized_value,
                extractor_name=item.extractor_name,
                extractor_version=item.extractor_version,
            )
            for item in facts
        ]
        fact_specs.sort(
            key=lambda spec: (
                spec.extractor_name,
                spec.locator,
                DeterministicExtractionService._stable_value(spec.normalized_value),
            )
        )
        assertion_specs = [
            AssertionSpec(
                locator=item.locator,
                statement=item.statement,
                extractor_name=item.extractor_name,
                extractor_version=item.extractor_version,
            )
            for item in assertions
        ]
        assertion_specs.sort(key=DeterministicExtractionService._assertion_sort_key)
        return {
            "facts": [
                DeterministicExtractionService._spec_payload(spec) for spec in fact_specs
            ],
            "assertions": [
                DeterministicExtractionService._spec_payload(spec)
                for spec in assertion_specs
            ],
        }

    @staticmethod
    def _diagnostic_payload(item: ExtractionDiagnostic) -> dict[str, str]:
        return {
            "capture_id": item.capture_id,
            "source_revision_id": item.source_revision_id,
            "artifact_id": item.artifact_id,
            "source_locator": item.source_locator,
            "extractor_name": item.extractor_name,
            "extractor_version": item.extractor_version,
            "error_type": item.error_type,
            "error_message": item.error_message,
        }

    @staticmethod
    def _extractor_descriptors(
        extractors: tuple[ArtifactExtractor, ...],
    ) -> tuple[dict[str, str], ...]:
        descriptors: list[dict[str, str]] = []
        for extractor in extractors:
            name = getattr(extractor, "name", None)
            version = getattr(extractor, "version", None)
            if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
                raise ValueError("artifact_extractors must expose non-empty name/version strings")
            descriptors.append({"name": name, "version": version})
        return tuple(descriptors)

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("change-intelligence clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _artifact_state(item: ReconstructedArtifact) -> dict[str, Any]:
        return {
            "artifact_id": item.artifact_id,
            "source_locator": item.source_locator,
            "retrieval_status": item.retrieval_status.value,
            "content_hash": item.content_hash,
            "media_type": item.media_type,
        }

    @staticmethod
    def _artifact_delta_id(run_id: str, source_locator: str) -> str:
        material = f"artifact-delta\0{run_id}\0{source_locator}".encode("utf-8")
        return f"artifact-delta:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _structural_delta_id(
        run_id: str,
        artifact_delta_id: str,
        structural_key: str,
        change_type: StructuralDeltaType,
    ) -> str:
        material = (
            f"structural-delta\0{run_id}\0{artifact_delta_id}\0"
            f"{structural_key}\0{change_type.value}"
        ).encode("utf-8")
        return f"structural-delta:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
