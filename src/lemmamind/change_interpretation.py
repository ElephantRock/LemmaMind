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
from .change_interpretation_generation_contracts import (
    ChangeInterpretationGeneration,
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

    def produce_packet_run(
        self,
        packet_run_id: str,
        interpreter: CandidateChangeInterpreter,
    ) -> ChangeInterpretationResult:
        """Persist explicit reasoning lineage even when every packet is declined."""

        interpreter_name = str(getattr(interpreter, "name", "")).strip()
        interpreter_version = str(getattr(interpreter, "version", "")).strip()
        result = super().produce_packet_run(packet_run_id, interpreter)
        generation = ChangeInterpretationGeneration(
            change_interpretation_generation_id=(
                f"change-interpretation-generation:{result.run.run_id}"
            ),
            interpretation_run_id=result.run.run_id,
            packet_run_id=packet_run_id,
            interpreter_name=interpreter_name,
            interpreter_version=interpreter_version,
            policy_version=result.run.policy_version,
            change_interpretation_ids=tuple(
                sorted(item.change_interpretation_id for item in result.interpretations)
            ),
        )
        self.store.put_many((generation,))
        return result


__all__ = [
    "CandidateChangeInterpreter",
    "ChangeInterpretationError",
    "ChangeInterpretationResult",
    "ChangeInterpretationService",
    "ContractStore",
    "InterpretationProposal",
]
