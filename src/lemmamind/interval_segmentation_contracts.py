"""Deterministic contracts for full-M5 interval and candidate segmentation.

These records preserve temporal/path grouping provenance without claiming that a
commit, path group, or candidate is architecturally important. Every net
``GitPathDelta`` remains factual evidence and is assigned exactly once by the
segmentation service.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .contracts import CONTRACT_TYPES, ContractModel, GitSha, Identifier, SourceLocator


class CommitRangeStatus(StrEnum):
    AHEAD = "ahead"
    IDENTICAL = "identical"


class CommitRangeSummary(ContractModel):
    """Complete ordered commit frontier between two pinned SourceRevision records."""

    record_id_field = "commit_range_summary_id"

    commit_range_summary_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    provider_status: CommitRangeStatus
    total_commits: int = Field(ge=0)
    commit_shas: tuple[GitSha, ...] = ()
    segmentation_run_id: Identifier

    @model_validator(mode="after")
    def validate_commit_frontier(self) -> "CommitRangeSummary":
        if self.total_commits != len(self.commit_shas):
            raise ValueError("total_commits must equal commit_shas length")
        if len(self.commit_shas) != len(set(self.commit_shas)):
            raise ValueError("commit_shas must be unique")
        if self.provider_status is CommitRangeStatus.IDENTICAL and self.total_commits != 0:
            raise ValueError("identical commit range cannot contain commits")
        return self


class CommitPathSnapshot(ContractModel):
    """Complete changed-path projection for one commit inside a pinned interval."""

    record_id_field = "commit_path_snapshot_id"

    commit_path_snapshot_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    commit_sha: GitSha
    ordinal: int = Field(ge=1)
    parent_shas: tuple[GitSha, ...] = ()
    touched_paths: tuple[SourceLocator, ...] = ()
    segmentation_run_id: Identifier

    @model_validator(mode="after")
    def validate_paths(self) -> "CommitPathSnapshot":
        if self.touched_paths != tuple(sorted(set(self.touched_paths))):
            raise ValueError("touched_paths must be sorted and unique")
        if len(self.parent_shas) != len(set(self.parent_shas)):
            raise ValueError("parent_shas must be unique")
        return self


class IntervalSegmentationGeneration(ContractModel):
    """Durable deterministic profile for one interval-segmentation generation."""

    record_id_field = "interval_segmentation_generation_id"

    interval_segmentation_generation_id: Identifier
    segmentation_run_id: Identifier
    diff_run_id: Identifier
    policy_version: Identifier
    max_paths_per_candidate: int = Field(ge=1)


class IntervalCandidateSegment(ContractModel):
    """Attention-bounded deterministic group of net path deltas.

    A candidate segment means only that these net deltas share the same latest
    touching commit, top-level path group, and deterministic chunk. It is not a
    semantic ranking or ChangeInterpretation.
    """

    record_id_field = "interval_candidate_segment_id"

    interval_candidate_segment_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    commit_path_snapshot_id: Identifier
    commit_sha: GitSha
    commit_ordinal: int = Field(ge=1)
    path_group: SourceLocator
    chunk_ordinal: int = Field(ge=1)
    git_path_delta_ids: tuple[Identifier, ...]
    paths: tuple[SourceLocator, ...]
    segmentation_run_id: Identifier

    @model_validator(mode="after")
    def validate_candidate_membership(self) -> "IntervalCandidateSegment":
        if not self.git_path_delta_ids or not self.paths:
            raise ValueError("candidate segments cannot be empty")
        if len(self.git_path_delta_ids) != len(self.paths):
            raise ValueError("candidate segment requires one delta id per path")
        if len(self.git_path_delta_ids) != len(set(self.git_path_delta_ids)):
            raise ValueError("candidate segment delta ids must be unique")
        if self.paths != tuple(sorted(set(self.paths))):
            raise ValueError("candidate segment paths must be sorted and unique")
        return self


for _model in (
    CommitRangeSummary,
    CommitPathSnapshot,
    IntervalSegmentationGeneration,
    IntervalCandidateSegment,
):
    CONTRACT_TYPES[_model.__name__] = _model


INTERVAL_SEGMENTATION_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    model.__name__: model
    for model in (
        CommitRangeSummary,
        CommitPathSnapshot,
        IntervalSegmentationGeneration,
        IntervalCandidateSegment,
    )
}
