"""Public candidate-evidence packet surface with authenticated projection caching.

The complete reviewed provenance implementation is preserved byte-for-byte in
``candidate_evidence_packets_impl``. This thin subclass only reuses immutable
projection inputs after that implementation has authenticated the full factual
lineage successfully.
"""
from __future__ import annotations

from .candidate_evidence_packet_contracts import AssertionSnapshotSide
from .candidate_evidence_packets_impl import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketResult,
    CandidateEvidencePacketService as _AuthenticatedCandidateEvidencePacketService,
    ContractStore,
)
from .candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
)
from .change_contracts import StructuralDelta
from .contracts import EvidenceFact, RetrievalStatus, SourceAssertion


class CandidateEvidencePacketService(_AuthenticatedCandidateEvidencePacketService):
    """Reuse authenticated projection state without weakening provenance checks."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._reset_projection_cache()

    def _reset_projection_cache(self) -> None:
        self._projection_ready = False
        self._projection_reduction_run_id: str | None = None
        self._projection_packets_remaining = 0
        self._projection_extraction_run_ids: frozenset[str] = frozenset()
        self._projection_final_reauth_run_ids: tuple[str, ...] = ()
        self._projection_artifact_paths: dict[
            tuple[str, str], dict[str, str]
        ] = {}
        self._projection_assertions_by_run: dict[
            str, tuple[SourceAssertion, ...]
        ] = {}

    def _authenticated_reduction_generation(self, reduction_run_id: str):
        """Authenticate first, then snapshot immutable packet-projection indexes."""

        self._reset_projection_cache()
        run, pairs = super()._authenticated_reduction_generation(reduction_run_id)
        if not pairs:
            return run, pairs

        first = pairs[0][1]
        previous_manifest = self._manifest(
            first.previous_capture_id,
            first.previous_source_revision_id,
        )
        current_manifest = self._manifest(
            first.current_capture_id,
            first.current_source_revision_id,
        )
        self._projection_artifact_paths = {
            (
                first.previous_capture_id,
                first.previous_source_revision_id,
            ): {
                reference.artifact_id: reference.source_locator
                for reference in previous_manifest.artifacts
                if reference.retrieval_status is RetrievalStatus.CAPTURED
            },
            (
                first.current_capture_id,
                first.current_source_revision_id,
            ): {
                reference.artifact_id: reference.source_locator
                for reference in current_manifest.artifacts
                if reference.retrieval_status is RetrievalStatus.CAPTURED
            },
        }
        final_reauth_run_ids = (
            first.previous_extraction_run_id,
            first.current_extraction_run_id,
        )
        extraction_run_ids = frozenset(final_reauth_run_ids)
        assertions = tuple(
            item
            for item in self.store.list(SourceAssertion)
            if item.run_id in extraction_run_ids
        )
        self._projection_assertions_by_run = {
            run_id: tuple(item for item in assertions if item.run_id == run_id)
            for run_id in extraction_run_ids
        }
        self._projection_reduction_run_id = run.run_id
        self._projection_packets_remaining = sum(
            1
            for _, reduction in pairs
            if reduction.disposition is CandidateReductionDisposition.RETAIN
        )
        self._projection_extraction_run_ids = extraction_run_ids
        self._projection_final_reauth_run_ids = final_reauth_run_ids
        self._projection_ready = True
        return run, pairs

    def _build_packet(self, reduction, candidate, packet_run_id):
        packet = super()._build_packet(reduction, candidate, packet_run_id)
        if (
            self._projection_ready
            and reduction.reduction_run_id == self._projection_reduction_run_id
        ):
            if self._projection_packets_remaining < 1:
                raise CandidateEvidencePacketError(
                    "authenticated packet projection exceeded retained candidate coverage"
                )
            self._projection_packets_remaining -= 1
            if self._projection_packets_remaining == 0:
                for run_id in self._projection_final_reauth_run_ids:
                    _AuthenticatedCandidateEvidencePacketService._authenticate_extraction_run(
                        self, run_id
                    )
        return packet

    def _authenticate_extraction_run(self, run_id: str) -> None:
        if self._projection_ready and run_id in self._projection_extraction_run_ids:
            return
        super()._authenticate_extraction_run(run_id)

    def _validate_structural_evidence(
        self,
        item: StructuralDelta,
        reduction: CandidateFactualReduction,
    ) -> None:
        if not self._projection_ready:
            super()._validate_structural_evidence(item, reduction)
            return

        previous_artifact_to_path = self._projection_artifact_paths.get(
            (
                reduction.previous_capture_id,
                reduction.previous_source_revision_id,
            )
        )
        current_artifact_to_path = self._projection_artifact_paths.get(
            (
                reduction.current_capture_id,
                reduction.current_source_revision_id,
            )
        )
        if previous_artifact_to_path is None or current_artifact_to_path is None:
            super()._validate_structural_evidence(item, reduction)
            return

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
        if not self._projection_ready:
            return super()._assertion_snapshots(reduction)

        snapshots: list[tuple[AssertionSnapshotSide, str, SourceAssertion]] = []
        for side, capture_id, revision_id, run_id in (
            (
                AssertionSnapshotSide.PREVIOUS,
                reduction.previous_capture_id,
                reduction.previous_source_revision_id,
                reduction.previous_extraction_run_id,
            ),
            (
                AssertionSnapshotSide.CURRENT,
                reduction.current_capture_id,
                reduction.current_source_revision_id,
                reduction.current_extraction_run_id,
            ),
        ):
            artifact_to_path = self._projection_artifact_paths.get(
                (capture_id, revision_id)
            )
            assertions = self._projection_assertions_by_run.get(run_id)
            if artifact_to_path is None or assertions is None:
                return super()._assertion_snapshots(reduction)
            for assertion in assertions:
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
                    snapshots.append((side, path, assertion))

        result = tuple(
            sorted(
                snapshots,
                key=lambda entry: (
                    entry[1],
                    entry[0].value,
                    entry[2].locator,
                    entry[2].assertion_id,
                ),
            )
        )
        for _, path, assertion in result:
            if not (
                assertion.locator.startswith(path + ":")
                or assertion.locator.startswith(path + "#")
            ):
                raise CandidateEvidencePacketError(
                    "SourceAssertion locator must use an exact artifact-path namespace boundary"
                )
        return result


__all__ = [
    "CandidateEvidencePacketError",
    "CandidateEvidencePacketResult",
    "CandidateEvidencePacketService",
    "ContractStore",
]
