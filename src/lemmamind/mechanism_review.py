"""Fail-closed public mechanism-review grouping surface."""
from __future__ import annotations

from .candidate_evidence_packet_auth import (
    CandidateEvidencePacketGenerationAuthenticator,
)
from .candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
)
from .change_interpretation import ChangeInterpretationService
from .change_interpretation_contracts import ChangeInterpretation
from .change_interpretation_generation_contracts import (
    ChangeInterpretationGeneration,
)
from .contracts import PipelineRun, RunType
from .mechanism_review_base import (
    ContractStore,
    MechanismReviewGroupingError,
    MechanismReviewGroupingResult,
    MechanismReviewGroupingService as _BaseMechanismReviewGroupingService,
)


class MechanismReviewGroupingService(_BaseMechanismReviewGroupingService):
    """Authenticate complete reasoning and packet lineage before human projection."""

    def _authenticated_interpretations(
        self,
        interpretation_run_id: str,
    ) -> tuple[PipelineRun, tuple[ChangeInterpretation, ...]]:
        run = self._completed_run(
            interpretation_run_id,
            RunType.REASONING,
            "ChangeInterpretation",
        )
        if run.policy_version != self.INTERPRETATION_POLICY:
            raise MechanismReviewGroupingError(
                "mechanism grouping requires the known ChangeInterpretation policy"
            )

        generations = tuple(
            item
            for item in self.store.list(ChangeInterpretationGeneration)
            if item.interpretation_run_id == interpretation_run_id
        )
        if len(generations) != 1:
            raise MechanismReviewGroupingError(
                "ChangeInterpretation run requires exactly one durable lineage envelope"
            )
        generation = generations[0]
        if (
            generation.interpretation_run_id != run.run_id
            or generation.policy_version != run.policy_version
        ):
            raise MechanismReviewGroupingError(
                "ChangeInterpretation lineage envelope disagrees with PipelineRun"
            )

        try:
            packet_run, packets = CandidateEvidencePacketGenerationAuthenticator(
                self.store
            ).authenticate(generation.packet_run_id)
        except CandidateEvidencePacketError as exc:
            raise MechanismReviewGroupingError(
                "candidate evidence packet generation failed upstream reconstruction"
            ) from exc

        expected_inputs = self._digest_json(
            {
                "packet_run": packet_run.model_dump(mode="json", by_alias=True),
                "packets": [
                    CandidateEvidencePacketService._stable_packet_payload(item)
                    for item in packets
                ],
                "interpreter": {
                    "name": generation.interpreter_name,
                    "version": generation.interpreter_version,
                },
                "policy_version": run.policy_version,
            }
        )
        if run.inputs_hash != expected_inputs:
            raise MechanismReviewGroupingError(
                "ChangeInterpretation input envelope does not authenticate"
            )

        interpretations = tuple(
            item
            for item in self.store.list(ChangeInterpretation)
            if item.interpretation_run_id == interpretation_run_id
        )
        observed_ids = tuple(
            sorted(item.change_interpretation_id for item in interpretations)
        )
        if observed_ids != generation.change_interpretation_ids:
            raise MechanismReviewGroupingError(
                "ChangeInterpretation lineage envelope does not exactly name semantic outputs"
            )

        packet_by_id = {item.candidate_evidence_packet_id: item for item in packets}
        if len(packet_by_id) != len(packets):
            raise MechanismReviewGroupingError(
                "authenticated packet generation contains duplicate packet identities"
            )
        interpretation_by_packet: dict[str, ChangeInterpretation] = {}
        for item in interpretations:
            if (
                item.interpreter_name != generation.interpreter_name
                or item.interpreter_version != generation.interpreter_version
            ):
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation interpreter identity disagrees with lineage envelope"
                )
            if (
                len(item.interval_candidate_segment_ids) != 1
                or len(item.candidate_factual_reduction_ids) != 1
                or len(item.candidate_evidence_packet_ids) != 1
            ):
                raise MechanismReviewGroupingError(
                    "exact grouping v1 requires candidate-local interpretations"
                )
            packet_id = item.candidate_evidence_packet_ids[0]
            if packet_id in interpretation_by_packet:
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation run contains duplicate packet interpretations"
                )
            packet = packet_by_id.get(packet_id)
            if packet is None:
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation references a packet outside the authenticated generation"
                )
            expected = (
                packet.source_id,
                packet.previous_source_revision_id,
                packet.current_source_revision_id,
                packet.interval_candidate_segment_id,
                packet.candidate_factual_reduction_id,
                packet.candidate_evidence_packet_id,
            )
            observed = (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                item.interval_candidate_segment_ids[0],
                item.candidate_factual_reduction_ids[0],
                item.candidate_evidence_packet_ids[0],
            )
            if observed != expected:
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation lineage disagrees with authenticated evidence packet"
                )
            self._validate_supports(item, packet)
            interpretation_by_packet[packet_id] = item

        ordered_interpretations = tuple(
            interpretation_by_packet[item.candidate_evidence_packet_id]
            for item in packets
            if item.candidate_evidence_packet_id in interpretation_by_packet
        )
        expected_outputs = self._digest_json(
            [
                ChangeInterpretationService._stable_interpretation_payload(item)
                for item in ordered_interpretations
            ]
        )
        if run.outputs_hash != expected_outputs:
            raise MechanismReviewGroupingError(
                "ChangeInterpretation output envelope does not authenticate"
            )
        return run, ordered_interpretations


__all__ = [
    "ContractStore",
    "MechanismReviewGroupingError",
    "MechanismReviewGroupingResult",
    "MechanismReviewGroupingService",
]
