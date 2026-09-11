"""Deterministic human-review grouping for provenance-bound ChangeInterpretation."""
from __future__ import annotations

from pydantic import model_validator

from .change_interpretation_contracts import (
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
    ChangeInterpretationType,
    InterpretationSummaryText,
    MechanismText,
    UncertaintyText,
)
from .contracts import CONTRACT_TYPES, ContractModel, Identifier


class MechanismReviewItem(ContractModel):
    """Exact-label grouping of inferred interpretations for human review.

    This is a deterministic projection, not a new semantic claim. ``mechanism``
    and ``representative_summary`` are copied from one member interpretation;
    all member identities and support edges remain explicit.
    """

    record_id_field = "mechanism_review_item_id"

    mechanism_review_item_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier

    canonical_mechanism_key: Identifier
    interpretation_types: tuple[ChangeInterpretationType, ...]
    mechanism: MechanismText
    representative_summary: InterpretationSummaryText
    representative_change_interpretation_id: Identifier

    change_interpretation_ids: tuple[Identifier, ...]
    interval_candidate_segment_ids: tuple[Identifier, ...]
    candidate_factual_reduction_ids: tuple[Identifier, ...]
    candidate_evidence_packet_ids: tuple[Identifier, ...]
    supports: tuple[ChangeInterpretationSupportRef, ...]
    extraction_gap_signal_ids: tuple[Identifier, ...] = ()
    uncertainty_notes: tuple[UncertaintyText, ...] = ()

    interpretation_run_id: Identifier
    grouping_run_id: Identifier

    @model_validator(mode="after")
    def validate_review_item(self) -> "MechanismReviewItem":
        for field_name in (
            "change_interpretation_ids",
            "interval_candidate_segment_ids",
            "candidate_factual_reduction_ids",
            "candidate_evidence_packet_ids",
            "extraction_gap_signal_ids",
            "uncertainty_notes",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        if not self.change_interpretation_ids:
            raise ValueError("MechanismReviewItem requires a member interpretation")
        for field_name in (
            "interval_candidate_segment_ids",
            "candidate_factual_reduction_ids",
            "candidate_evidence_packet_ids",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must not be empty")
        if self.representative_change_interpretation_id not in set(
            self.change_interpretation_ids
        ):
            raise ValueError("representative interpretation must be a group member")
        if self.interpretation_types != tuple(
            sorted(set(self.interpretation_types), key=lambda item: item.value)
        ):
            raise ValueError("interpretation_types must be sorted and unique")
        support_keys = tuple(
            (item.support_type.value, item.support_id) for item in self.supports
        )
        if support_keys != tuple(sorted(set(support_keys))):
            raise ValueError("supports must be sorted and unique")
        gap_support_ids = tuple(
            sorted(
                item.support_id
                for item in self.supports
                if item.support_type
                is ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL
            )
        )
        if gap_support_ids != self.extraction_gap_signal_ids:
            raise ValueError(
                "extraction_gap_signal_ids must exactly match grouped gap support edges"
            )
        if self.extraction_gap_signal_ids and not self.uncertainty_notes:
            raise ValueError("gap-bearing review items require explicit uncertainty")
        return self


CONTRACT_TYPES[MechanismReviewItem.__name__] = MechanismReviewItem

MECHANISM_REVIEW_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    MechanismReviewItem.__name__: MechanismReviewItem,
}
