"""Durable deterministic contracts for full-M5 Git path localization.

These records localize exact Git object changes between two SourceRevision
records. They remain factual: no architectural importance, causality, adoption,
reversal, or other ChangeInterpretation belongs in this layer.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .contracts import CONTRACT_TYPES, ContractModel, GitSha, Identifier


class GitPathDeltaType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    TYPE_CHANGED = "type_changed"


class ChangeSurface(StrEnum):
    SOURCE = "SOURCE"
    TEST = "TEST"
    DOCS = "DOCS"
    CONFIG = "CONFIG"
    WORKFLOW = "WORKFLOW"
    MANIFEST = "MANIFEST"
    LOCKFILE = "LOCKFILE"
    GENERATED = "GENERATED"
    VENDORED = "VENDORED"
    UNKNOWN = "UNKNOWN"


class GitPathDelta(ContractModel):
    """One exact non-directory Git path change between two pinned revisions."""

    record_id_field = "git_path_delta_id"

    git_path_delta_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    previous_capture_id: Identifier
    current_capture_id: Identifier
    # Git permits leading/trailing whitespace in path components. Do not use
    # Identifier here because Identifier strips whitespace and would corrupt
    # exact source identity.
    path: str = Field(min_length=1)
    change_type: GitPathDeltaType
    surface: ChangeSurface

    previous_entry_type: Identifier | None = None
    current_entry_type: Identifier | None = None
    previous_mode: Identifier | None = None
    current_mode: Identifier | None = None
    previous_object_sha: GitSha | None = None
    current_object_sha: GitSha | None = None
    previous_size: int | None = Field(default=None, ge=0)
    current_size: int | None = Field(default=None, ge=0)
    diff_run_id: Identifier

    @model_validator(mode="after")
    def validate_transition(self) -> "GitPathDelta":
        previous_fields = (
            self.previous_entry_type,
            self.previous_mode,
            self.previous_object_sha,
        )
        current_fields = (
            self.current_entry_type,
            self.current_mode,
            self.current_object_sha,
        )
        previous_any = any(value is not None for value in previous_fields)
        previous_all = all(value is not None for value in previous_fields)
        current_any = any(value is not None for value in current_fields)
        current_all = all(value is not None for value in current_fields)
        if previous_any != previous_all:
            raise ValueError("previous Git entry fields must be present together")
        if current_any != current_all:
            raise ValueError("current Git entry fields must be present together")
        previous_present = previous_all
        current_present = current_all

        if not previous_present and self.previous_size is not None:
            raise ValueError("previous_size requires a previous Git entry")
        if not current_present and self.current_size is not None:
            raise ValueError("current_size requires a current Git entry")

        if self.change_type is GitPathDeltaType.ADDED:
            if previous_present or not current_present:
                raise ValueError("added path delta requires only current Git entry")
        elif self.change_type is GitPathDeltaType.REMOVED:
            if not previous_present or current_present:
                raise ValueError("removed path delta requires only previous Git entry")
        elif self.change_type is GitPathDeltaType.TYPE_CHANGED:
            if not previous_present or not current_present:
                raise ValueError("type_changed requires Git entries on both sides")
            if self.previous_entry_type == self.current_entry_type:
                raise ValueError("type_changed requires unequal Git entry types")
        elif self.change_type is GitPathDeltaType.MODIFIED:
            if not previous_present or not current_present:
                raise ValueError("modified requires Git entries on both sides")
            if self.previous_entry_type != self.current_entry_type:
                raise ValueError("modified cannot change Git entry type")
            if (
                self.previous_object_sha == self.current_object_sha
                and self.previous_mode == self.current_mode
                and self.previous_size == self.current_size
            ):
                raise ValueError("modified requires object, mode, or size change")

        return self


CONTRACT_TYPES[GitPathDelta.__name__] = GitPathDelta

PATH_CHANGE_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    GitPathDelta.__name__: GitPathDelta,
}
