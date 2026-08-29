"""Fail-closed public ChangeInterpretation producer."""
from __future__ import annotations

from .candidate_evidence_packet_auth import (
    CandidateEvidencePacketGenerationAuthenticator,
)
from .candidate_evidence_packets import CandidateEvidencePacketError
from .change_interpretation_base import (
    CandidateChangeInterpreter,
    ChangeInterpretationError,
    ChangeInterpretationResult,
    ChangeInterpretationService as _BaseChangeInterpretationService,
    ContractStore,
    InterpretationProposal,
)


class ChangeInterpretationService(_BaseChangeInterpretationService):
    """Require upstream packet reconstruction before invoking an interpreter."""

    def _authenticated_packet_generation(self, packet_run_id: str):
        try:
            return CandidateEvidencePacketGenerationAuthenticator(
                self.store
            ).authenticate(packet_run_id)
        except CandidateEvidencePacketError as exc:
            raise ChangeInterpretationError(
                "candidate evidence packet generation failed upstream reconstruction"
            ) from exc


__all__ = [
    "CandidateChangeInterpreter",
    "ChangeInterpretationError",
    "ChangeInterpretationResult",
    "ChangeInterpretationService",
    "ContractStore",
    "InterpretationProposal",
]
