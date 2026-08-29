"""Deterministic bounded evidence packets for full-M5 interpretation input."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .candidate_reduction_contracts import CandidateSignalKind
from .change_contracts import StructuralDeltaType
from .contracts import CONTRACT_TYPES, ContractModel, Identifier, SourceLocator


class AssertionSnapshotSide(StrEnum):
    PREVIOUS = "previous"
    CURRENT = "current"


class StructuralDeltaPreview(BaseModel):
    """Bounded deterministic projection of one exact StructuralDelta."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    structural_delta_id: Identifier
    source_locator: SourceLocator
    structural_key: Identifier
    change_type: StructuralDeltaType
    extractor_name: Identifier
    extractor_version: Identifier
    previous_value_preview: str | None = None
    current_value_preview: str | None = None
    value_preview_truncated: bool = False


class SourceAssertionPreview(BaseModel):
    """Bounded preview of one exact authored SourceAssertion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assertion_id: Identifier
    side: AssertionSnapshotSide
    source_locator: SourceLocator
    locator: SourceLocator
    statement_preview: str
    statement_truncated: bool
    extractor_name: Identifier
    extractor_version: Identifier


class CandidateEvidencePacket(ContractModel):
    """Hashable bounded input envelope for one retained machine candidate."""

    record_id_field = "candidate_evidence_packet_id"

    candidate_evidence_packet_id: Identifier
    interval_candidate_segment_id: Identifier
    candidate_factual_reduction_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier

    paths: tuple[SourceLocator, ...]
    signal_kinds: tuple[CandidateSignalKind, ...]
    policy_suppressed_paths: tuple[SourceLocator, ...] = ()
    artifact_only_paths: tuple[SourceLocator, ...] = ()
    git_only_paths: tuple[SourceLocator, ...] = ()

    artifact_delta_ids: tuple[Identifier, ...] = ()

    structural_delta_total: int = Field(ge=0)
    structural_delta_previews: tuple[StructuralDeltaPreview, ...] = ()
    structural_delta_omitted_count: int = Field(ge=0)

    assertion_snapshot_total: int = Field(ge=0)
    assertion_previews: tuple[SourceAssertionPreview, ...] = ()
    assertion_snapshot_omitted_count: int = Field(ge=0)

    extraction_gap_signal_ids: tuple[Identifier, ...] = ()
    extraction_gap_paths: tuple[SourceLocator, ...] = ()

    segmentation_run_id: Identifier
    reduction_run_id: Identifier
    previous_extraction_run_id: Identifier
    current_extraction_run_id: Identifier
    change_run_id: Identifier
    packet_run_id: Identifier

    @model_validator(mode="after")
    def validate_packet(self) -> "CandidateEvidencePacket":
        if not self.paths:
            raise ValueError("CandidateEvidencePacket requires candidate paths")

        for field_name in (
            "paths",
            "policy_suppressed_paths",
            "artifact_only_paths",
            "git_only_paths",
            "artifact_delta_ids",
            "extraction_gap_signal_ids",
            "extraction_gap_paths",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")

        if self.signal_kinds != tuple(
            sorted(set(self.signal_kinds), key=lambda item: item.value)
        ):
            raise ValueError("signal_kinds must be sorted and unique")
        if not self.signal_kinds:
            raise ValueError("CandidateEvidencePacket requires factual signal kinds")

        path_set = set(self.paths)
        for field_name in (
            "policy_suppressed_paths",
            "artifact_only_paths",
            "git_only_paths",
            "extraction_gap_paths",
        ):
            if not set(getattr(self, field_name)).issubset(path_set):
                raise ValueError(f"{field_name} must be a subset of candidate paths")

        structural_ids = [
            item.structural_delta_id for item in self.structural_delta_previews
        ]
        if len(structural_ids) != len(set(structural_ids)):
            raise ValueError("structural_delta_previews cannot repeat a delta")
        if any(
            item.source_locator not in path_set
            for item in self.structural_delta_previews
        ):
            raise ValueError("structural previews must stay inside candidate paths")
        if self.structural_delta_total != (
            len(self.structural_delta_previews)
            + self.structural_delta_omitted_count
        ):
            raise ValueError(
                "structural_delta_total must equal included plus omitted previews"
            )

        assertion_keys = [
            (item.side.value, item.assertion_id) for item in self.assertion_previews
        ]
        if len(assertion_keys) != len(set(assertion_keys)):
            raise ValueError("assertion_previews cannot repeat an assertion side/id")
        if any(
            item.source_locator not in path_set for item in self.assertion_previews
        ):
            raise ValueError("assertion previews must stay inside candidate paths")
        if self.assertion_snapshot_total != (
            len(self.assertion_previews)
            + self.assertion_snapshot_omitted_count
        ):
            raise ValueError(
                "assertion_snapshot_total must equal included plus omitted previews"
            )

        if bool(self.extraction_gap_signal_ids) != bool(self.extraction_gap_paths):
            raise ValueError(
                "extraction gap signal IDs and paths must either both be present or both empty"
            )

        return self


CONTRACT_TYPES[CandidateEvidencePacket.__name__] = CandidateEvidencePacket

CANDIDATE_EVIDENCE_PACKET_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    CandidateEvidencePacket.__name__: CandidateEvidencePacket,
}
