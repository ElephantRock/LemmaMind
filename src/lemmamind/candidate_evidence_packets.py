"""Bounded public surface for full-M5 candidate evidence packets."""
from __future__ import annotations

from .candidate_evidence_packet_contracts import (
    AssertionSnapshotSide,
    SourceAssertionPreview,
    StructuralDeltaPreview,
)
from .candidate_evidence_packets_hardened_base import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketResult,
    CandidateEvidencePacketService as _HardenedCandidateEvidencePacketService,
    ContractStore,
)
from .candidate_reduction_contracts import CandidateFactualReduction
from .change_contracts import StructuralDelta
from .contracts import SourceAssertion


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
