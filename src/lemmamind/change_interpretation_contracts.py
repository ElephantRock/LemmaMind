"""Durable contracts for provenance-bound full-M5 ChangeInterpretation.

``ChangeInterpretation`` is explicitly inferred. It may summarize or classify
mechanism-level change supported by deterministic evidence, but it is never an
``EvidenceFact`` or ``SourceAssertion`` and never self-authorizes promotion or
action. Human review remains a separate authority boundary.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from .contracts import (
    CONTRACT_TYPES,
    ContractModel,
    Identifier,
    ValidationState,
)

InterpretationText = Annotated[str, StringConstraints(min_length=1)]


class ChangeInterpretationType(StrEnum):
    INTRODUCTION = "introduction"
    MODIFICATION = "modification"
    REMOVAL = "removal"
    REVERSAL = "reversal"
    DEPRECATION = "deprecation"
    FAILURE = "failure"
    REPAIR = "repair"
    AUTHORITY_GOVERNANCE = "authority_governance"
    PROJECT_STATE = "project_state"
    TEMPORAL_CORRECTNESS = "temporal_correctness"
    UNKNOWN = "unknown"


class ChangeInterpretationSupportType(StrEnum):
    CANDIDATE_FACTUAL_REDUCTION = "CandidateFactualReduction"
    ARTIFACT_DELTA = "ArtifactDelta"
    STRUCTURAL_DELTA = "StructuralDelta"
    SOURCE_ASSERTION = "SourceAssertion"
    CANDIDATE_EXTRACTION_GAP_SIGNAL = "CandidateExtractionGapSignal"


class ChangeInterpretationSupportRef(BaseModel):
    """Typed immutable reference to evidence or explicit extraction uncertainty."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    support_type: ChangeInterpretationSupportType
    support_id: Identifier


class ChangeInterpretation(ContractModel):
    """One candidate mechanism-level interpretation with explicit support edges."""

    record_id_field = "change_interpretation_id"

    change_interpretation_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier

    interval_candidate_segment_ids: tuple[Identifier, ...]
    candidate_factual_reduction_ids: tuple[Identifier, ...]
    candidate_evidence_packet_ids: tuple[Identifier, ...]

    interpretation_types: tuple[ChangeInterpretationType, ...]
    mechanism: InterpretationText
    summary: InterpretationText
    uncertainty_notes: tuple[InterpretationText, ...] = ()

    supports: tuple[ChangeInterpretationSupportRef, ...]
    validation_state: Literal[ValidationState.CANDIDATE] = ValidationState.CANDIDATE

    interpretation_run_id: Identifier

    @model_validator(mode="after")
    def validate_interpretation(self) -> "ChangeInterpretation":
        if not self.interval_candidate_segment_ids:
            raise ValueError("ChangeInterpretation requires at least one interval candidate")
        for field_name in (
            "interval_candidate_segment_ids",
            "candidate_factual_reduction_ids",
            "candidate_evidence_packet_ids",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")

        candidate_count = len(self.interval_candidate_segment_ids)
        if len(self.candidate_factual_reduction_ids) != candidate_count:
            raise ValueError(
                "each interpreted interval candidate requires one factual reduction"
            )
        if len(self.candidate_evidence_packet_ids) != candidate_count:
            raise ValueError(
                "each interpreted interval candidate requires one deterministic evidence packet"
            )

        if not self.interpretation_types:
            raise ValueError("ChangeInterpretation requires an interpretation type")
        if self.interpretation_types != tuple(
            sorted(set(self.interpretation_types), key=lambda item: item.value)
        ):
            raise ValueError("interpretation_types must be sorted and unique")

        if not self.supports:
            raise ValueError("ChangeInterpretation requires explicit support")
        support_keys = tuple(
            (item.support_type.value, item.support_id) for item in self.supports
        )
        if support_keys != tuple(sorted(set(support_keys))):
            raise ValueError("supports must be sorted and unique")

        supported_reductions = {
            item.support_id
            for item in self.supports
            if item.support_type
            is ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION
        }
        if supported_reductions != set(self.candidate_factual_reduction_ids):
            raise ValueError(
                "every candidate_factual_reduction_id must have an explicit support edge"
            )

        carries_gap = any(
            item.support_type
            is ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL
            for item in self.supports
        )
        if carries_gap and not self.uncertainty_notes:
            raise ValueError(
                "interpretations supported by extraction-gap signals require uncertainty"
            )

        if self.uncertainty_notes != tuple(sorted(set(self.uncertainty_notes))):
            raise ValueError("uncertainty_notes must be sorted and unique")

        return self


CONTRACT_TYPES[ChangeInterpretation.__name__] = ChangeInterpretation

CHANGE_INTERPRETATION_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    ChangeInterpretation.__name__: ChangeInterpretation,
}
