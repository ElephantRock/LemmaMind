"""Fail-closed authentication of persisted candidate evidence packet generations."""
from __future__ import annotations

from .candidate_evidence_packet_contracts import CandidateEvidencePacket
from .candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
)
from .candidate_reduction_contracts import CandidateReductionDisposition
from .contracts import PipelineRun, RunType


class CandidateEvidencePacketGenerationAuthenticator:
    """Reconstruct packets from upstream facts before semantic consumption."""

    def __init__(self, store) -> None:
        self.store = store

    def authenticate(
        self,
        packet_run_id: str,
    ) -> tuple[PipelineRun, tuple[CandidateEvidencePacket, ...]]:
        service = CandidateEvidencePacketService(self.store)
        run = service._completed_run(packet_run_id, RunType.OTHER, "evidence packet")
        if run.policy_version != service.policy_version:
            raise CandidateEvidencePacketError(
                "packet generation policy disagrees with bounded packet policy"
            )
        persisted = tuple(
            item
            for item in self.store.list(CandidateEvidencePacket)
            if item.packet_run_id == packet_run_id
        )
        if not persisted:
            if run.outputs_hash != service._digest_json([]):
                raise CandidateEvidencePacketError(
                    "empty packet generation does not authenticate against outputs_hash"
                )
            return run, ()

        reduction_run_ids = {item.reduction_run_id for item in persisted}
        if len(reduction_run_ids) != 1:
            raise CandidateEvidencePacketError(
                "packet generation spans multiple factual-reduction runs"
            )
        reduction_run_id = next(iter(reduction_run_ids))
        reduction_run, pairs = service._authenticated_reduction_generation(
            reduction_run_id
        )
        expected_inputs_hash = service._digest_json(
            {
                "reduction_run": reduction_run.model_dump(mode="json", by_alias=True),
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
        persisted_by_candidate = {}
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
        expected_outputs_hash = service._digest_json(
            [service._stable_packet_payload(item) for item in reconstructed]
        )
        if run.outputs_hash != expected_outputs_hash:
            raise CandidateEvidencePacketError(
                "packet output envelope does not authenticate"
            )
        return run, ordered
