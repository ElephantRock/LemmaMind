"""Durable generation envelope for full-M5 candidate factual reduction."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import CONTRACT_TYPES, ContractModel, Identifier


class ExtractorDescriptor(BaseModel):
    """Exact ordered extractor identity used by one extraction/reduction generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Identifier
    version: Identifier


class CandidateFactualReductionGeneration(ContractModel):
    """Authenticate reducer lineage and the exact ordered extractor profile."""

    record_id_field = "candidate_factual_reduction_generation_id"

    candidate_factual_reduction_generation_id: Identifier
    reduction_run_id: Identifier
    diff_run_id: Identifier
    segmentation_run_id: Identifier
    planner_run_id: Identifier
    previous_capture_id: Identifier
    current_capture_id: Identifier
    previous_extraction_run_id: Identifier
    current_extraction_run_id: Identifier
    change_run_id: Identifier
    policy_version: Identifier
    artifact_extractors: tuple[ExtractorDescriptor, ...] = Field(min_length=1)
    candidate_factual_reduction_ids: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_generation(self) -> "CandidateFactualReductionGeneration":
        if self.candidate_factual_reduction_ids != tuple(
            sorted(set(self.candidate_factual_reduction_ids))
        ):
            raise ValueError(
                "candidate_factual_reduction_ids must be sorted and unique"
            )
        return self


CONTRACT_TYPES[CandidateFactualReductionGeneration.__name__] = (
    CandidateFactualReductionGeneration
)

CANDIDATE_REDUCTION_GENERATION_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    CandidateFactualReductionGeneration.__name__: CandidateFactualReductionGeneration,
}
