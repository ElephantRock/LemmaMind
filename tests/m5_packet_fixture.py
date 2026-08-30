"""Shared authentic deterministic lineage for M5 packet-boundary tests."""
from __future__ import annotations

from datetime import timedelta

from lemmamind.affected_file_planning import (
    MAX_CAPTURE_BLOB_BYTES_V1,
    _SUPPRESSED_SURFACES_V1,
    AffectedFileCapturePlanner,
)
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    PipelineRun,
    RepositoryIdentity,
    RunType,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
)
from lemmamind.interval_segmentation import IntervalCandidateSegmentationService
from lemmamind.interval_segmentation_contracts import (
    CommitPathSnapshot,
    CommitRangeStatus,
    CommitRangeSummary,
)
from lemmamind.path_change_contracts import (
    GitPathDelta,
    GitPathDeltaType,
    GitPathDiffSummary,
)
from lemmamind.recursive_tree import RecursiveGitTreeDiffService, classify_change_surface
from lemmamind.tracking_contracts import RepositoryTrackingAssignment, TrackingLevel


class SeededPathPipeline:
    def __init__(self, *, summary, deltas, candidates, plans, tracking_assignment):
        self.summary = summary
        self.deltas = deltas
        self.candidates = candidates
        self.plans = plans
        self.tracking_assignment = tracking_assignment


def _digest(value):
    return RecursiveGitTreeDiffService._digest_json(value)


def seed_path_pipeline(
    store,
    *,
    source_id: str,
    previous_revision_id: str,
    current_revision_id: str,
    diff_run_id: str,
    segmentation_run_id: str,
    planner_run_id: str,
    tracking_assignment_id: str,
    now,
    path_specs: tuple[dict, ...],
    max_paths_per_candidate: int = 50,
) -> SeededPathPipeline:
    """Persist an authenticated one-commit path-diff/segmentation/planner chain."""

    previous_commit_sha = "a" * 40
    current_commit_sha = "b" * 40
    source = Source(
        source_id=source_id,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator=f"https://github.com/fixture/{source_id.split(':')[-1]}",
        first_seen_at=now - timedelta(minutes=2),
        last_seen_at=now,
    )
    repository = RepositoryIdentity(
        source_id=source_id,
        provider_repository_id=f"fixture:{source_id}",
        owner="fixture",
        name=source_id.split(":")[-1],
        default_branch="main",
    )
    previous_revision = SourceRevision(
        source_revision_id=previous_revision_id,
        source_id=source_id,
        commit_sha=previous_commit_sha,
        tree_sha="c" * 40,
        observed_at=now - timedelta(seconds=20),
    )
    current_revision = SourceRevision(
        source_revision_id=current_revision_id,
        source_id=source_id,
        commit_sha=current_commit_sha,
        tree_sha="d" * 40,
        observed_at=now - timedelta(seconds=10),
    )
    tracking = RepositoryTrackingAssignment(
        tracking_assignment_id=tracking_assignment_id,
        source_id=source_id,
        level=TrackingLevel.STRUCTURAL,
        effective_at=now - timedelta(minutes=1),
        recorded_at=now - timedelta(minutes=1),
        assigned_by="test:fixture",
        reason="Authenticate deterministic M5 packet lineage",
        policy_version="repository-tracking.v1",
    )

    deltas = []
    for index, spec in enumerate(path_specs, start=1):
        path = spec["path"]
        previous_type = spec.get("previous_entry_type", "blob")
        current_type = spec.get("current_entry_type", previous_type)
        previous_size = spec.get("previous_size", 3 if previous_type == "blob" else None)
        current_size = spec.get("current_size", 4 if current_type == "blob" else None)
        previous_mode = spec.get(
            "previous_mode", "100644" if previous_type == "blob" else "160000"
        )
        current_mode = spec.get(
            "current_mode", "100644" if current_type == "blob" else "160000"
        )
        previous_object_sha = spec.get("previous_object_sha", f"{index + 1:040x}")
        current_object_sha = spec.get("current_object_sha", f"{index + 20:040x}")
        change_type = spec.get("change_type", GitPathDeltaType.MODIFIED)
        delta = GitPathDelta(
            git_path_delta_id=RecursiveGitTreeDiffService._delta_id(
                diff_run_id,
                previous_revision_id,
                current_revision_id,
                path,
                change_type,
            ),
            source_id=source_id,
            previous_source_revision_id=previous_revision_id,
            current_source_revision_id=current_revision_id,
            previous_capture_id=spec.get("path_diff_previous_capture_id", f"tree:{source_id}:previous"),
            current_capture_id=spec.get("path_diff_current_capture_id", f"tree:{source_id}:current"),
            path=path,
            change_type=change_type,
            surface=classify_change_surface(path),
            previous_entry_type=previous_type,
            current_entry_type=current_type,
            previous_mode=previous_mode,
            current_mode=current_mode,
            previous_object_sha=previous_object_sha,
            current_object_sha=current_object_sha,
            previous_size=previous_size,
            current_size=current_size,
            diff_run_id=diff_run_id,
        )
        deltas.append(delta)
    deltas = tuple(sorted(deltas, key=lambda item: item.path))
    previous_tree_capture = deltas[0].previous_capture_id
    current_tree_capture = deltas[0].current_capture_id
    if any(
        item.previous_capture_id != previous_tree_capture
        or item.current_capture_id != current_tree_capture
        for item in deltas
    ):
        raise ValueError("path_specs must share one recursive-tree capture pair")

    summary = GitPathDiffSummary(
        git_path_diff_summary_id=RecursiveGitTreeDiffService._summary_id(diff_run_id),
        source_id=source_id,
        previous_source_revision_id=previous_revision_id,
        current_source_revision_id=current_revision_id,
        previous_capture_id=previous_tree_capture,
        current_capture_id=current_tree_capture,
        delta_count=len(deltas),
        diff_run_id=diff_run_id,
    )
    diff_run = PipelineRun(
        run_id=diff_run_id,
        run_type=RunType.DIFF,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="recursive-git-path-diff.v1",
        started_at=now,
        finished_at=now,
        inputs_hash=_digest(
            {
                "previous_capture_id": previous_tree_capture,
                "current_capture_id": current_tree_capture,
                "previous_source_revision_id": previous_revision_id,
                "current_source_revision_id": current_revision_id,
                "policy_version": "recursive-git-path-diff.v1",
            }
        ),
        outputs_hash=_digest(
            {
                "summary": summary.model_dump(mode="json", by_alias=True),
                "deltas": [
                    {
                        "path": item.path,
                        "change_type": item.change_type.value,
                        "surface": item.surface.value,
                        "previous_entry_type": item.previous_entry_type,
                        "current_entry_type": item.current_entry_type,
                        "previous_mode": item.previous_mode,
                        "current_mode": item.current_mode,
                        "previous_object_sha": item.previous_object_sha,
                        "current_object_sha": item.current_object_sha,
                        "previous_size": item.previous_size,
                        "current_size": item.current_size,
                    }
                    for item in deltas
                ],
            }
        ),
    )

    segmentation_service = IntervalCandidateSegmentationService(
        None,
        store,
        None,
        max_paths_per_candidate=max_paths_per_candidate,
        policy_version="interval-candidate-segmentation.v1",
    )
    commit_range = CommitRangeSummary(
        commit_range_summary_id=segmentation_service._stable_id(
            "commit-range-summary",
            segmentation_run_id,
            previous_revision_id,
            current_revision_id,
        ),
        source_id=source_id,
        previous_source_revision_id=previous_revision_id,
        current_source_revision_id=current_revision_id,
        provider_status=CommitRangeStatus.AHEAD,
        total_commits=1,
        commit_shas=(current_commit_sha,),
        segmentation_run_id=segmentation_run_id,
    )
    snapshot = CommitPathSnapshot(
        commit_path_snapshot_id=segmentation_service._stable_id(
            "commit-path-snapshot", segmentation_run_id, current_commit_sha
        ),
        source_id=source_id,
        previous_source_revision_id=previous_revision_id,
        current_source_revision_id=current_revision_id,
        commit_sha=current_commit_sha,
        ordinal=1,
        parent_shas=(previous_commit_sha,),
        touched_paths=tuple(sorted(item.path for item in deltas)),
        segmentation_run_id=segmentation_run_id,
    )
    integration = (snapshot,)
    latest_touch = segmentation_service._assign_latest_touch(deltas, integration)
    candidates = segmentation_service._build_candidates(
        deltas,
        latest_touch,
        run_id=segmentation_run_id,
        source_id=source_id,
        previous_source_revision_id=previous_revision_id,
        current_source_revision_id=current_revision_id,
    )
    segmentation_run = PipelineRun(
        run_id=segmentation_run_id,
        run_type=RunType.DIFF,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="interval-candidate-segmentation.v1",
        started_at=now,
        finished_at=now,
        inputs_hash=_digest(
            {
                "diff_run_id": diff_run_id,
                "diff_summary": summary.model_dump(mode="json", by_alias=True),
                "path_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in deltas
                ],
                "tracking_assignment_id": tracking_assignment_id,
                "tracking_level": TrackingLevel.STRUCTURAL.value,
                "max_paths_per_candidate": max_paths_per_candidate,
                "policy_version": "interval-candidate-segmentation.v1",
            }
        ),
        outputs_hash=_digest(
            {
                "commit_range": commit_range.model_dump(mode="json", by_alias=True),
                "commit_snapshots": [snapshot.model_dump(mode="json", by_alias=True)],
                "integration_commit_shas": [current_commit_sha],
                "candidates": [
                    item.model_dump(mode="json", by_alias=True) for item in candidates
                ],
            }
        ),
    )

    planner = AffectedFileCapturePlanner(
        store,
        None,
        policy_version="affected-file-plan.v1",
    )
    plans = tuple(
        planner._plan_delta(
            item,
            run_id=planner_run_id,
            tracking_assignment_id=tracking_assignment_id,
            tracking_level=TrackingLevel.STRUCTURAL.value,
        )
        for item in deltas
    )
    planner_run = PipelineRun(
        run_id=planner_run_id,
        run_type=RunType.OTHER,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="affected-file-plan.v1",
        started_at=now,
        finished_at=now,
        inputs_hash=_digest(
            {
                "diff_run_id": diff_run_id,
                "diff_summary": summary.model_dump(mode="json", by_alias=True),
                "path_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in deltas
                ],
                "tracking_assignment_id": tracking_assignment_id,
                "tracking_level": TrackingLevel.STRUCTURAL.value,
                "max_capture_blob_bytes": MAX_CAPTURE_BLOB_BYTES_V1,
                "suppressed_surfaces": sorted(
                    surface.value for surface in _SUPPRESSED_SURFACES_V1
                ),
                "policy_version": "affected-file-plan.v1",
            }
        ),
        outputs_hash=_digest(
            [item.model_dump(mode="json", by_alias=True) for item in plans]
        ),
    )

    store.put_many(
        (
            source,
            repository,
            previous_revision,
            current_revision,
            tracking,
            summary,
            *deltas,
            diff_run,
            commit_range,
            snapshot,
            *candidates,
            segmentation_run,
            *plans,
            planner_run,
        )
    )
    return SeededPathPipeline(
        summary=summary,
        deltas=deltas,
        candidates=candidates,
        plans=plans,
        tracking_assignment=tracking,
    )
