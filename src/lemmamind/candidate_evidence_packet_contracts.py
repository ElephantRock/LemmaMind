"""Deterministic bounded evidence packets for full-M5 interpretation input."""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .candidate_reduction_contracts import CandidateSignalKind
from .change_contracts import StructuralDeltaType
from .contracts import CONTRACT_TYPES, ContractModel

PacketIdentifier = Annotated[
    str, StringConstraints(min_length=1, max_length=256, strip_whitespace=True)
]
PacketPath = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
PacketPreviewText = Annotated[str, StringConstraints(max_length=512)]
PacketPreviewLocator = Annotated[
    str, StringConstraints(min_length=1, max_length=512)
]

MAX_PACKET_PATHS = 50
MAX_STRUCTURAL_PREVIEWS = 256
MAX_ASSERTION_PREVIEWS = 128


class AssertionSnapshotSide(StrEnum):
    PREVIOUS = "previous"
    CURRENT = "current"


class StructuralDeltaPreview(BaseModel):
    """Bounded deterministic projection of one exact StructuralDelta."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    structural_delta_id: PacketIdentifier
    source_locator: PacketPath
    structural_key: PacketPreviewLocator
    structural_key_truncated: bool = False
    change_type: StructuralDeltaType
    extractor_name: PacketIdentifier
    extractor_version: PacketIdentifier
    previous_value_preview: PacketPreviewText | None = None
    current_value_preview: PacketPreviewText | None = None
    value_preview_truncated: bool = False


class SourceAssertionPreview(BaseModel):
    """Bounded preview of one exact authored SourceAssertion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assertion_id: PacketIdentifier
    side: AssertionSnapshotSide
    source_locator: PacketPath
    locator: PacketPreviewLocator
    locator_truncated: bool = False
    statement_preview: PacketPreviewText
    statement_truncated: bool
    extractor_name: PacketIdentifier
    extractor_version: PacketIdentifier


class CandidateEvidencePacket(ContractModel):
    """Hashable bounded input envelope for one retained machine candidate."""

    record_id_field = "candidate_evidence_packet_id"

    candidate_evidence_packet_id: PacketIdentifier
    interval_candidate_segment_id: PacketIdentifier
    candidate_factual_reduction_id: PacketIdentifier
    source_id: PacketIdentifier
    previous_source_revision_id: PacketIdentifier
    current_source_revision_id: PacketIdentifier

    paths: tuple[PacketPath, ...] = Field(min_length=1, max_length=MAX_PACKET_PATHS)
    signal_kinds: tuple[CandidateSignalKind, ...] = Field(min_length=1, max_length=8)
    policy_suppressed_paths: tuple[PacketPath, ...] = Field(
        default=(), max_length=MAX_PACKET_PATHS
    )
    artifact_only_paths: tuple[PacketPath, ...] = Field(
        default=(), max_length=MAX_PACKET_PATHS
    )
    git_only_paths: tuple[PacketPath, ...] = Field(
        default=(), max_length=MAX_PACKET_PATHS
    )

    artifact_delta_ids: tuple[PacketIdentifier, ...] = Field(
        default=(), max_length=MAX_PACKET_PATHS
    )

    structural_delta_total: int = Field(ge=0)
    structural_delta_previews: tuple[StructuralDeltaPreview, ...] = Field(
        default=(), max_length=MAX_STRUCTURAL_PREVIEWS
    )
    structural_delta_omitted_count: int = Field(ge=0)

    assertion_snapshot_total: int = Field(ge=0)
    assertion_previews: tuple[SourceAssertionPreview, ...] = Field(
        default=(), max_length=MAX_ASSERTION_PREVIEWS
    )
    assertion_snapshot_omitted_count: int = Field(ge=0)

    extraction_gap_signal_ids: tuple[PacketIdentifier, ...] = Field(
        default=(), max_length=MAX_PACKET_PATHS
    )
    extraction_gap_paths: tuple[PacketPath, ...] = Field(
        default=(), max_length=MAX_PACKET_PATHS
    )

    segmentation_run_id: PacketIdentifier
    reduction_run_id: PacketIdentifier
    previous_extraction_run_id: PacketIdentifier
    current_extraction_run_id: PacketIdentifier
    change_run_id: PacketIdentifier
    packet_run_id: PacketIdentifier

    @model_validator(mode="after")
    def validate_packet(self) -> "CandidateEvidencePacket":
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
