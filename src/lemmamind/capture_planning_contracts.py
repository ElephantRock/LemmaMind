"""Durable deterministic contracts for full-M5 affected-file capture planning.

Planning is operational routing over factual ``GitPathDelta`` evidence. It says
which exact Git path/revision sides are eligible for later byte capture under a
versioned deterministic policy. It does not claim semantic importance and does
not execute repository content.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import CONTRACT_TYPES, ContractModel, GitSha, Identifier
from .path_change_contracts import ChangeSurface


class CapturePlanDisposition(StrEnum):
    """Deterministic disposition for one revision side of a changed Git path."""

    CAPTURE = "capture"
    ABSENT = "absent"
    SUPPRESSED = "suppressed"
    NON_FILE = "non_file"


class CapturePlanReason(StrEnum):
    ELIGIBLE_BLOB = "eligible_blob"
    PATH_ABSENT = "path_absent"
    DIRECTORY_ENTRY = "directory_entry"
    SUBMODULE_POINTER = "submodule_pointer"
    GENERATED_SURFACE = "generated_surface"
    VENDORED_SURFACE = "vendored_surface"
    LARGE_BLOB = "large_blob"


class CapturePlanSide(BaseModel):
    """One exact revision-side routing decision for a changed path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_revision_id: Identifier
    disposition: CapturePlanDisposition
    reason: CapturePlanReason
    entry_type: Identifier | None = None
    object_sha: GitSha | None = None
    size: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_disposition(self) -> "CapturePlanSide":
        if self.disposition is CapturePlanDisposition.ABSENT:
            if self.reason is not CapturePlanReason.PATH_ABSENT:
                raise ValueError("absent side requires path_absent reason")
            if self.entry_type is not None or self.object_sha is not None or self.size is not None:
                raise ValueError("absent side cannot carry Git entry metadata")
            return self

        if self.entry_type is None or self.object_sha is None:
            raise ValueError("present capture-plan side requires Git entry type and object SHA")

        if self.disposition is CapturePlanDisposition.NON_FILE:
            expected = {
                "tree": CapturePlanReason.DIRECTORY_ENTRY,
                "commit": CapturePlanReason.SUBMODULE_POINTER,
            }.get(self.entry_type)
            if expected is None or self.reason is not expected:
                raise ValueError("non_file side requires matching tree/submodule reason")
            return self

        if self.entry_type != "blob":
            raise ValueError("capture/suppressed sides must reference blob entries")

        if self.disposition is CapturePlanDisposition.CAPTURE:
            if self.reason is not CapturePlanReason.ELIGIBLE_BLOB:
                raise ValueError("capture side requires eligible_blob reason")
        elif self.disposition is CapturePlanDisposition.SUPPRESSED:
            if self.reason not in {
                CapturePlanReason.GENERATED_SURFACE,
                CapturePlanReason.VENDORED_SURFACE,
                CapturePlanReason.LARGE_BLOB,
            }:
                raise ValueError("suppressed side requires deterministic suppression reason")
        return self


class AffectedFileCapturePlan(ContractModel):
    """Capture routing for one factual ``GitPathDelta`` across both revisions."""

    record_id_field = "affected_file_plan_id"

    affected_file_plan_id: Identifier
    git_path_delta_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    # Git paths are exact source identity and may contain leading/trailing whitespace.
    path: str = Field(min_length=1)
    surface: ChangeSurface
    previous: CapturePlanSide
    current: CapturePlanSide
    tracking_assignment_id: Identifier
    tracking_level: Identifier
    diff_run_id: Identifier
    planner_run_id: Identifier

    @model_validator(mode="after")
    def validate_revision_sides(self) -> "AffectedFileCapturePlan":
        if self.previous.source_revision_id != self.previous_source_revision_id:
            raise ValueError("previous plan side must match previous_source_revision_id")
        if self.current.source_revision_id != self.current_source_revision_id:
            raise ValueError("current plan side must match current_source_revision_id")
        if (
            self.previous.disposition is CapturePlanDisposition.ABSENT
            and self.current.disposition is CapturePlanDisposition.ABSENT
        ):
            raise ValueError("affected path cannot be absent from both revisions")
        return self


CONTRACT_TYPES[AffectedFileCapturePlan.__name__] = AffectedFileCapturePlan

CAPTURE_PLANNING_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    AffectedFileCapturePlan.__name__: AffectedFileCapturePlan,
}
