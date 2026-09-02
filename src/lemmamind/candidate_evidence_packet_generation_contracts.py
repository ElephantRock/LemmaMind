"""Durable profile envelope for one candidate evidence-packet generation."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import CONTRACT_TYPES, ContractModel, Identifier


class PacketExtractorDescriptor(BaseModel):
    """Exact ordered extractor identity authenticated by upstream run hashes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Identifier
    version: Identifier


class CandidateEvidencePacketGeneration(ContractModel):
    """Persist the bounded packet profile needed for deterministic reconstruction."""

    record_id_field = "candidate_evidence_packet_generation_id"

    candidate_evidence_packet_generation_id: Identifier
    packet_run_id: Identifier
    reduction_run_id: Identifier
    policy_version: Identifier
    max_structural_previews: int = Field(ge=1, le=256)
    max_assertion_previews: int = Field(ge=2, le=128)
    preview_chars: int = Field(ge=32, le=512)
    artifact_extractors: tuple[PacketExtractorDescriptor, ...] = Field(min_length=1)
    candidate_evidence_packet_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_generation(self) -> "CandidateEvidencePacketGeneration":
        if self.candidate_evidence_packet_ids != tuple(
            sorted(set(self.candidate_evidence_packet_ids))
        ):
            raise ValueError("candidate_evidence_packet_ids must be sorted and unique")
        return self


CONTRACT_TYPES[CandidateEvidencePacketGeneration.__name__] = CandidateEvidencePacketGeneration

CANDIDATE_EVIDENCE_PACKET_GENERATION_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    CandidateEvidencePacketGeneration.__name__: CandidateEvidencePacketGeneration,
}
