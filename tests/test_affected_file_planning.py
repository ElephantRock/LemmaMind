from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.affected_file_planning import (
    MAX_CAPTURE_BLOB_BYTES_V1,
    AffectedFileCapturePlanner,
)
from lemmamind.capture_planning_contracts import (
    AffectedFileCapturePlan,
    CapturePlanDisposition,
    CapturePlanReason,
)
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    PipelineRun,
    RunType,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
)
from lemmamind.path_change_contracts import (
    ChangeSurface,
    GitPathDelta,
    GitPathDeltaType,
)
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking import RepositoryTrackingService, TrackingNotAllowed
from lemmamind.tracking_contracts import TrackingLevel

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)
SOURCE_ID = "github:affected-plan"
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{'a' * 40}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{'b' * 40}"
DIFF_RUN_ID = "run:recursive-path-diff:test"
DIGEST = "sha256:" + "0" * 64


class FixedClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"id-{self.value}"


def delta(
    path: str,
    *,
    change_type: GitPathDeltaType = GitPathDeltaType.MODIFIED,
    surface: ChangeSurface = ChangeSurface.SOURCE,
    previous_type: str | None = "blob",
    current_type: str | None = "blob",
    previous_sha: str | None = "c" * 40,
    current_sha: str | None = "d" * 40,
    previous_size: int | None = 10,
    current_size: int | None = 11,
) -> GitPathDelta:
    return GitPathDelta(
        git_path_delta_id=f"git-path-delta:{path}",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        previous_capture_id="capture-recursive-tree:previous",
        current_capture_id="capture-recursive-tree:current",
        path=path,
        change_type=change_type,
        surface=surface,
        previous_entry_type=previous_type,
        current_entry_type=current_type,
        previous_mode=None if previous_type is None else ("040000" if previous_type == "tree" else "100644"),
        current_mode=None if current_type is None else ("040000" if current_type == "tree" else "100644"),
        previous_object_sha=previous_sha,
        current_object_sha=current_sha,
        previous_size=previous_size,
        current_size=current_size,
        diff_run_id=DIFF_RUN_ID,
    )


def prepare(tmp_path, deltas, *, level=TrackingLevel.STRUCTURAL):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = Source(
        source_id=SOURCE_ID,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/example/repo",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    previous = SourceRevision(
        source_revision_id=PREVIOUS_REVISION_ID,
        source_id=SOURCE_ID,
        commit_sha="a" * 40,
        tree_sha="1" * 40,
        observed_at=NOW,
    )
    current = SourceRevision(
        source_revision_id=CURRENT_REVISION_ID,
        source_id=SOURCE_ID,
        commit_sha="b" * 40,
        tree_sha="2" * 40,
        observed_at=NOW + timedelta(seconds=1),
    )
    diff_run = PipelineRun(
        run_id=DIFF_RUN_ID,
        run_type=RunType.DIFF,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="recursive-git-path-diff.v1",
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=1),
        inputs_hash=DIGEST,
        outputs_hash=DIGEST,
    )
    store.put_many((source, previous, current, diff_run, *deltas))
    tracking = RepositoryTrackingService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=2)),
    )
    assignment = tracking.assign_level(
        SOURCE_ID,
        level,
        assigned_by="test",
        reason="affected-file planning test",
    )
    planner = AffectedFileCapturePlanner(
        store,
        tracking,
        clock=FixedClock(NOW + timedelta(seconds=3)),
        id_factory=Ids(),
    )
    return store, assignment, planner


def test_modified_blob_captures_both_revisions_with_tracking_provenance(tmp_path) -> None:
    store, assignment, planner = prepare(tmp_path, [delta("src/core.py")])

    result = planner.plan_diff(DIFF_RUN_ID)

    assert result.previous_capture_paths == ("src/core.py",)
    assert result.current_capture_paths == ("src/core.py",)
    assert len(result.plans) == 1
    plan = result.plans[0]
    assert plan.previous.disposition is CapturePlanDisposition.CAPTURE
    assert plan.current.disposition is CapturePlanDisposition.CAPTURE
    assert plan.previous.reason is CapturePlanReason.ELIGIBLE_BLOB
    assert plan.tracking_assignment_id == assignment.tracking_assignment_id
    assert plan.tracking_level == TrackingLevel.STRUCTURAL.value
    assert store.list(AffectedFileCapturePlan) == [plan]
    assert result.run.run_type is RunType.OTHER


def test_added_blob_requests_absent_side_to_preserve_missing_state(tmp_path) -> None:
    added = delta(
        "src/new.py",
        change_type=GitPathDeltaType.ADDED,
        previous_type=None,
        previous_sha=None,
        previous_size=None,
    )
    _, _, planner = prepare(tmp_path, [added])

    result = planner.plan_diff(DIFF_RUN_ID)
    plan = result.plans[0]

    assert plan.previous.disposition is CapturePlanDisposition.ABSENT
    assert plan.previous.reason is CapturePlanReason.PATH_ABSENT
    assert plan.current.disposition is CapturePlanDisposition.CAPTURE
    assert result.previous_capture_paths == ("src/new.py",)
    assert result.current_capture_paths == ("src/new.py",)


def test_v1_suppresses_only_explicit_generated_vendored_and_large_blob_cases(tmp_path) -> None:
    changes = [
        delta("generated/client.ts", surface=ChangeSurface.GENERATED),
        delta("vendor/library.py", surface=ChangeSurface.VENDORED),
        delta(
            "assets/large.bin",
            surface=ChangeSurface.UNKNOWN,
            previous_size=MAX_CAPTURE_BLOB_BYTES_V1 + 1,
            current_size=MAX_CAPTURE_BLOB_BYTES_V1 + 2,
        ),
        delta(
            "odd/unknown.format",
            surface=ChangeSurface.UNKNOWN,
            previous_size=None,
            current_size=None,
        ),
    ]
    _, _, planner = prepare(tmp_path, changes)

    result = planner.plan_diff(DIFF_RUN_ID)
    by_path = {plan.path: plan for plan in result.plans}

    assert by_path["generated/client.ts"].current.reason is CapturePlanReason.GENERATED_SURFACE
    assert by_path["vendor/library.py"].current.reason is CapturePlanReason.VENDORED_SURFACE
    assert by_path["assets/large.bin"].current.reason is CapturePlanReason.LARGE_BLOB
    assert by_path["odd/unknown.format"].current.disposition is CapturePlanDisposition.CAPTURE
    assert set(result.suppressed_paths) == {
        "generated/client.ts",
        "vendor/library.py",
        "assets/large.bin",
    }
    assert result.current_capture_paths == ("odd/unknown.format",)


def test_blob_to_directory_type_change_requests_only_blob_revision(tmp_path) -> None:
    changed = delta(
        "src/component",
        change_type=GitPathDeltaType.TYPE_CHANGED,
        previous_type="blob",
        current_type="tree",
        previous_sha="c" * 40,
        current_sha="d" * 40,
        previous_size=10,
        current_size=None,
    )
    _, _, planner = prepare(tmp_path, [changed])

    result = planner.plan_diff(DIFF_RUN_ID)
    plan = result.plans[0]

    assert plan.previous.disposition is CapturePlanDisposition.CAPTURE
    assert plan.current.disposition is CapturePlanDisposition.NON_FILE
    assert plan.current.reason is CapturePlanReason.DIRECTORY_ENTRY
    assert result.previous_capture_paths == ("src/component",)
    assert result.current_capture_paths == ()


def test_exact_git_path_whitespace_survives_planning(tmp_path) -> None:
    _, _, planner = prepare(tmp_path, [delta(" src/core.py ")])

    result = planner.plan_diff(DIFF_RUN_ID)

    assert result.plans[0].path == " src/core.py "
    assert result.current_capture_paths == (" src/core.py ",)


def test_tracking_below_shallow_cannot_plan_explicit_file_capture(tmp_path) -> None:
    _, _, planner = prepare(
        tmp_path,
        [delta("src/core.py")],
        level=TrackingLevel.METADATA_ONLY,
    )

    with pytest.raises(TrackingNotAllowed, match="shallow is required"):
        planner.plan_diff(DIFF_RUN_ID)
