"""Bounded public surface for full-M5 candidate evidence packets."""
from __future__ import annotations

from .candidate_evidence_packet_contracts import (
    AssertionSnapshotSide,
    SourceAssertionPreview,
    StructuralDeltaPreview,
)
from .candidate_evidence_packet_generation_contracts import (
    CandidateEvidencePacketGeneration,
)
from .candidate_evidence_packets_hardened_base import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketResult,
    CandidateEvidencePacketService as _HardenedCandidateEvidencePacketService,
    ContractStore,
)
from .candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
)
from .change_contracts import StructuralDelta
from .contracts import CONTRACT_SCHEMA_VERSION, PipelineRun, RunType, SourceAssertion


class CandidateEvidencePacketService(_HardenedCandidateEvidencePacketService):
    """Keep every interpreter-facing preview inside a fixed context bound."""

    _MAX_STRUCTURAL_PREVIEWS = 256
    _MAX_ASSERTION_PREVIEWS = 128
    _MAX_PREVIEW_CHARS = 512

    def __init__(
        self,
        *args,
        max_structural_previews: int = 256,
        max_assertion_previews: int = 128,
        preview_chars: int = 512,
        **kwargs,
    ) -> None:
        if max_structural_previews > self._MAX_STRUCTURAL_PREVIEWS:
            raise ValueError("max_structural_previews exceeds bounded packet policy")
        if max_assertion_previews > self._MAX_ASSERTION_PREVIEWS:
            raise ValueError("max_assertion_previews exceeds bounded packet policy")
        if preview_chars > self._MAX_PREVIEW_CHARS:
            raise ValueError("preview_chars exceeds bounded packet policy")
        super().__init__(
            *args,
            max_structural_previews=max_structural_previews,
            max_assertion_previews=max_assertion_previews,
            preview_chars=preview_chars,
            **kwargs,
        )

    def build_reduction(self, reduction_run_id: str) -> CandidateEvidencePacketResult:
        """Persist the exact bounded profile needed to authenticate this generation."""

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
        generation = CandidateEvidencePacketGeneration(
            candidate_evidence_packet_generation_id=(
                f"candidate-evidence-packet-generation:{packet_run_id}"
            ),
            packet_run_id=packet_run_id,
            reduction_run_id=reduction_run_id,
            policy_version=self.policy_version,
            max_structural_previews=self.max_structural_previews,
            max_assertion_previews=self.max_assertion_previews,
            preview_chars=self.preview_chars,
            candidate_evidence_packet_ids=tuple(
                sorted(item.candidate_evidence_packet_id for item in packets)
            ),
        )
        result = CandidateEvidencePacketResult(reduction_run_id, packets, run)
        self.store.put_many((*packets, run, generation))
        return result

    def _assertion_snapshots(
        self,
        reduction: CandidateFactualReduction,
    ) -> tuple[tuple[AssertionSnapshotSide, str, SourceAssertion], ...]:
        result = super()._assertion_snapshots(reduction)
        for _, path, assertion in result:
            if not (
                assertion.locator.startswith(path + ":")
                or assertion.locator.startswith(path + "#")
            ):
                raise CandidateEvidencePacketError(
                    "SourceAssertion locator must use an exact artifact-path namespace boundary"
                )
        return result

    def _structural_preview(self, item: StructuralDelta) -> StructuralDeltaPreview:
        previous, previous_truncated = self._preview_json(item.previous_value)
        current, current_truncated = self._preview_json(item.current_value)
        structural_key, key_truncated = self._preview_text(item.structural_key)
        return StructuralDeltaPreview(
            structural_delta_id=item.structural_delta_id,
            source_locator=item.source_locator,
            structural_key=structural_key,
            structural_key_truncated=key_truncated,
            change_type=item.change_type,
            extractor_name=item.extractor_name,
            extractor_version=item.extractor_version,
            previous_value_preview=previous,
            current_value_preview=current,
            value_preview_truncated=(previous_truncated or current_truncated),
        )

    def _assertion_preview(
        self,
        side: AssertionSnapshotSide,
        path: str,
        item: SourceAssertion,
    ) -> SourceAssertionPreview:
        statement, statement_truncated = self._preview_text(item.statement)
        locator, locator_truncated = self._preview_text(item.locator)
        return SourceAssertionPreview(
            assertion_id=item.assertion_id,
            side=side,
            source_locator=path,
            locator=locator,
            locator_truncated=locator_truncated,
            statement_preview=statement,
            statement_truncated=statement_truncated,
            extractor_name=item.extractor_name,
            extractor_version=item.extractor_version,
        )


__all__ = [
    "CandidateEvidencePacketError",
    "CandidateEvidencePacketResult",
    "CandidateEvidencePacketService",
    "ContractStore",
]
