"""Fail-closed authentication of persisted candidate evidence packet generations."""
from __future__ import annotations

from .candidate_evidence_packet_contracts import CandidateEvidencePacket
from .candidate_evidence_packet_generation_contracts import (
    CandidateEvidencePacketGeneration,
)
from .candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
)
from .candidate_reduction_contracts import CandidateReductionDisposition
from .contracts import PipelineRun, RunType


class CandidateEvidencePacketGenerationAuthenticator:
    """Reconstruct packets from upstream facts before semantic consumption."""

    _PACKET_POLICY = "candidate-evidence-packet.v1"

    def __init__(self, store) -> None:
        self.store = store

    def authenticate(
        self,
        packet_run_id: str,
    ) -> tuple[PipelineRun, tuple[CandidateEvidencePacket, ...]]:
        generations = tuple(
            item
            for item in self.store.list(CandidateEvidencePacketGeneration)
            if item.packet_run_id == packet_run_id
        )
        if len(generations) != 1:
            raise CandidateEvidencePacketError(
                "packet generation requires exactly one durable bounded-profile envelope"
            )
        generation = generations[0]
        if generation.policy_version != self._PACKET_POLICY:
            raise CandidateEvidencePacketError(
                "packet generation rejects unrecognized packet policies"
            )

        service = CandidateEvidencePacketService(
            self.store,
            artifact_extractors=generation.artifact_extractors,
            policy_version=generation.policy_version,
            max_structural_previews=generation.max_structural_previews,
            max_assertion_previews=generation.max_assertion_previews,
            preview_chars=generation.preview_chars,
        )
        run = service._completed_run(packet_run_id, RunType.OTHER, "evidence packet")
        if run.policy_version != self._PACKET_POLICY:
            raise CandidateEvidencePacketError(
                "packet PipelineRun uses an unrecognized packet policy"
            )
        if run.policy_version != service.policy_version:
            raise CandidateEvidencePacketError(
                "packet generation policy disagrees with bounded packet policy"
            )
        if generation.packet_run_id != run.run_id:
            raise CandidateEvidencePacketError(
                "bounded packet profile disagrees with packet PipelineRun"
            )

        reduction_run, pairs = service._authenticated_reduction_generation(
            generation.reduction_run_id
        )
        expected_inputs_hash = service._digest_json(
            {
                "reduction_run": reduction_run.model_dump(
                    mode="json", by_alias=True
                ),
                "artifact_extractors": list(service._profile_payload()),
                "policy_version": service.policy_version,
                "max_structural_previews": service.max_structural_previews,
                "max_assertion_previews": service.max_assertion_previews,
                "preview_chars": service.preview_chars,
            }
        )
        if run.inputs_hash != expected_inputs_hash:
            raise CandidateEvidencePacketError(
                "packet input envelope does not authenticate against the bounded policy profile"
            )

        reconstructed = tuple(
            service._build_packet(reduction, candidate, packet_run_id)
            for candidate, reduction in pairs
            if reduction.disposition is CandidateReductionDisposition.RETAIN
        )
        persisted = tuple(
            item
            for item in self.store.list(CandidateEvidencePacket)
            if item.packet_run_id == packet_run_id
        )
        persisted_by_candidate: dict[str, CandidateEvidencePacket] = {}
        for packet in persisted:
            candidate_id = packet.interval_candidate_segment_id
            if candidate_id in persisted_by_candidate:
                raise CandidateEvidencePacketError(
                    "packet generation contains duplicate candidate identities"
                )
            persisted_by_candidate[candidate_id] = packet
        if set(persisted_by_candidate) != {
            item.interval_candidate_segment_id for item in reconstructed
        }:
            raise CandidateEvidencePacketError(
                "packet generation does not exactly cover retained factual candidates"
            )
        ordered = tuple(
            persisted_by_candidate[item.interval_candidate_segment_id]
            for item in reconstructed
        )
        for actual, expected in zip(ordered, reconstructed, strict=True):
            if actual != expected:
                raise CandidateEvidencePacketError(
                    "persisted packet disagrees with reconstruction from upstream factual evidence"
                )

        reconstructed_ids = tuple(
            sorted(item.candidate_evidence_packet_id for item in reconstructed)
        )
        if generation.candidate_evidence_packet_ids != reconstructed_ids:
            raise CandidateEvidencePacketError(
                "bounded packet profile does not exactly name reconstructed packet outputs"
            )

        expected_outputs_hash = service._digest_json(
            [service._stable_packet_payload(item) for item in reconstructed]
        )
        if run.outputs_hash != expected_outputs_hash:
            raise CandidateEvidencePacketError(
                "packet output envelope does not authenticate"
            )
        return run, ordered
