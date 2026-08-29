"""Durable contracts for candidate-local deterministic extraction gaps."""
from __future__ import annotations

from pydantic import model_validator

from .contracts import (
    CONTRACT_TYPES,
    ContractModel,
    Identifier,
    SourceLocator,
)


class CandidateExtractionGapSignal(ContractModel):
    """Explicit candidate-level signal that deterministic extraction was incomplete."""

    record_id_field = "candidate_extraction_gap_signal_id"

    candidate_extraction_gap_signal_id: Identifier
    interval_candidate_segment_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    previous_capture_id: Identifier
    current_capture_id: Identifier
    paths: tuple[SourceLocator, ...]
    previous_diagnostic_ids: tuple[Identifier, ...] = ()
    current_diagnostic_ids: tuple[Identifier, ...] = ()
    segmentation_run_id: Identifier
    previous_extraction_run_id: Identifier
    current_extraction_run_id: Identifier
    reduction_run_id: Identifier

    @model_validator(mode="after")
    def validate_signal(self) -> "CandidateExtractionGapSignal":
        if not self.paths:
            raise ValueError("candidate extraction-gap signal cannot be empty")
        if self.paths != tuple(sorted(set(self.paths))):
            raise ValueError("paths must be sorted and unique")
        for field_name in ("previous_diagnostic_ids", "current_diagnostic_ids"):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        if not self.previous_diagnostic_ids and not self.current_diagnostic_ids:
            raise ValueError("candidate extraction-gap signal requires a diagnostic")
        return self


CONTRACT_TYPES[CandidateExtractionGapSignal.__name__] = CandidateExtractionGapSignal

CANDIDATE_EXTRACTION_GAP_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    CandidateExtractionGapSignal.__name__: CandidateExtractionGapSignal,
}
