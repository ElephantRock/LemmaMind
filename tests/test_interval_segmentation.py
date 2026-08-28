from datetime import datetime, timedelta, timezone

import pytest

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
from lemmamind.interval_segmentation import (
    IntervalCandidateSegmentationService,
    IntervalSegmentationError,
)
from lemmamind.interval_segmentation_contracts import (
    CommitPathSnapshot,
    CommitRangeSummary,
    IntervalCandidateSegment,
)
from lemmamind.path_change_contracts import (
    ChangeSurface,
    GitPathDelta,
    GitPathDeltaType,
    GitPathDiffSummary,
)
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking import RepositoryTrackingService
from lemmamind.tracking_contracts import TrackingLevel

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)
SOURCE_ID = "github:interval-test"
BASE_SHA = "a" * 40
HEAD_SHA = "d" * 40
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{BASE_SHA}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{HEAD_SHA}"
DIFF_RUN_ID = "run:recursive-path-diff:interval-test"
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


class FakeIntervalReader:
    def __init__(self, compare_pages, commit_pages):
        self.compare_pages = compare_pages
        self.commit_pages = commit_pages
        self.compare_calls = []
        self.commit_calls = []

    def get_compare_page(self, owner, repo, base_sha, head_sha, *, page, per_page=100):
        self.compare_calls.append((owner, repo, base_sha, head_sha, page, per_page))
        return self.compare_pages[page]

    def get_commit_page(self, owner, repo, commit_sha, *, page, per_page=100):
        self.commit_calls.append((owner, repo, commit_sha, page, per_page))
        return self.commit_pages[(commit_sha, page)]


def delta(path: str, *, delta_id: str | None = None) -> GitPathDelta:
    return GitPathDelta(
        git_path_delta_id=delta_id or f"git-path-delta:{path}",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        previous_capture_id="capture-recursive-tree:previous",
        current_capture_id="capture-recursive-tree:current",
        path=path,
        change_type=GitPathDeltaType.MODIFIED,
        surface=ChangeSurface.SOURCE,
        previous_entry_type="blob",
        current_entry_type="blob",
        previous_mode="100644",
        current_mode="100644",
        previous_object_sha="1" * 40,
        current_object_sha="2" * 40,
        previous_size=10,
        current_size=11,
        diff_run_id=DIFF_RUN_ID,
    )


def commit_payload(sha: str, files, *, parents=(BASE_SHA,)):
    return {
        "sha": sha,
        "parents": [{"sha": parent} for parent in parents],
        "files": files,
    }


def compare_payload(commits, *, status="ahead", total=None):
    return {
        "status": status,
        "total_commits": len(commits) if total is None else total,
        "base_commit": {"sha": BASE_SHA},
        "merge_base_commit": {"sha": BASE_SHA},
        "commits": [{"sha": sha} for sha in commits],
    }


def prepare(tmp_path, deltas, reader, *, max_paths_per_candidate=50):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = Source(
        source_id=SOURCE_ID,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/Acme/Repo",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    repository = RepositoryIdentity(
        source_id=SOURCE_ID,
        provider_repository_id="42",
        owner="Acme",
        name="Repo",
        default_branch="main",
        aliases=(),
        archived=False,
    )
    previous = SourceRevision(
        source_revision_id=PREVIOUS_REVISION_ID,
        source_id=SOURCE_ID,
        commit_sha=BASE_SHA,
        tree_sha="3" * 40,
        observed_at=NOW,
    )
    current = SourceRevision(
        source_revision_id=CURRENT_REVISION_ID,
        source_id=SOURCE_ID,
        commit_sha=HEAD_SHA,
        tree_sha="4" * 40,
        observed_at=NOW + timedelta(seconds=1),
    )
    summary = GitPathDiffSummary(
        git_path_diff_summary_id="git-path-diff-summary:interval-test",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        previous_capture_id="capture-recursive-tree:previous",
        current_capture_id="capture-recursive-tree:current",
        delta_count=len(deltas),
        diff_run_id=DIFF_RUN_ID,
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
    store.put_many((source, repository, previous, current, summary, diff_run, *deltas))
    tracking = RepositoryTrackingService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=2)),
    )
    tracking.assign_level(
        SOURCE_ID,
        TrackingLevel.STRUCTURAL,
        assigned_by="test",
        reason="interval segmentation test",
    )
    service = IntervalCandidateSegmentationService(
        reader,
        store,
        tracking,
        max_paths_per_candidate=max_paths_per_candidate,
        clock=FixedClock(NOW + timedelta(seconds=3)),
        id_factory=Ids(),
    )
    return store, service


def test_assigns_each_net_delta_to_latest_touch_then_groups_by_path(tmp_path) -> None:
    commit_one = "b" * 40
    commit_two = "c" * 40
    changes = [
        delta("src/a.py"),
        delta("src/b.py"),
        delta("docs/readme.md"),
        delta("old/name.py"),
        delta("new/name.py"),
    ]
    reader = FakeIntervalReader(
        {1: compare_payload([commit_one, commit_two, HEAD_SHA])},
        {
            (commit_one, 1): commit_payload(
                commit_one,
                [{"filename": "src/a.py"}, {"filename": "old/name.py"}],
            ),
            (commit_two, 1): commit_payload(
                commit_two,
                [{"filename": "src/a.py"}, {"filename": "src/b.py"}],
                parents=(commit_one,),
            ),
            (HEAD_SHA, 1): commit_payload(
                HEAD_SHA,
                [
                    {"filename": "docs/readme.md"},
                    {"filename": "new/name.py", "previous_filename": "old/name.py"},
                ],
                parents=(commit_two,),
            ),
        },
    )
    store, service = prepare(tmp_path, changes, reader)

    result = service.segment_diff(DIFF_RUN_ID)

    assert result.commit_range.commit_shas == (commit_one, commit_two, HEAD_SHA)
    assert len(result.commit_snapshots) == 3
    by_path = {
        path: candidate
        for candidate in result.candidates
        for path in candidate.paths
    }
    assert set(by_path) == {item.path for item in changes}
    assert by_path["src/a.py"].commit_sha == commit_two
    assert by_path["src/b.py"].commit_sha == commit_two
    assert by_path["docs/readme.md"].commit_sha == HEAD_SHA
    assert by_path["old/name.py"].commit_sha == HEAD_SHA
    assert by_path["new/name.py"].commit_sha == HEAD_SHA
    assert by_path["src/a.py"].path_group == 'top-level:"src"'
    assert len(store.list(CommitRangeSummary)) == 1
    assert len(store.list(CommitPathSnapshot)) == 3
    assert len(store.list(IntervalCandidateSegment)) == len(result.candidates)


def test_candidate_chunk_bound_is_deterministic(tmp_path) -> None:
    changes = [delta(f"src/file-{index}.py") for index in range(5)]
    reader = FakeIntervalReader(
        {1: compare_payload([HEAD_SHA])},
        {
            (HEAD_SHA, 1): commit_payload(
                HEAD_SHA,
                [{"filename": item.path} for item in changes],
            )
        },
    )
    _, service = prepare(tmp_path, changes, reader, max_paths_per_candidate=2)

    result = service.segment_diff(DIFF_RUN_ID)

    assert [candidate.chunk_ordinal for candidate in result.candidates] == [1, 2, 3]
    assert [len(candidate.paths) for candidate in result.candidates] == [2, 2, 1]
    assert result.candidate_paths == tuple(sorted(item.path for item in changes))


def test_distinct_commits_with_no_net_paths_produce_no_candidates(tmp_path) -> None:
    reader = FakeIntervalReader(
        {1: compare_payload([HEAD_SHA])},
        {(HEAD_SHA, 1): commit_payload(HEAD_SHA, [])},
    )
    store, service = prepare(tmp_path, [], reader)

    result = service.segment_diff(DIFF_RUN_ID)

    assert result.commit_range.total_commits == 1
    assert len(result.commit_snapshots) == 1
    assert result.commit_snapshots[0].touched_paths == ()
    assert result.candidates == ()
    assert store.list(IntervalCandidateSegment) == []


def test_commit_file_pagination_preserves_exact_whitespace_path(tmp_path) -> None:
    exact_path = " odd.py "
    noise = [{"filename": f"noise/file-{index}.txt"} for index in range(100)]
    reader = FakeIntervalReader(
        {1: compare_payload([HEAD_SHA])},
        {
            (HEAD_SHA, 1): commit_payload(HEAD_SHA, noise),
            (HEAD_SHA, 2): commit_payload(HEAD_SHA, [{"filename": exact_path}]),
        },
    )
    _, service = prepare(tmp_path, [delta(exact_path)], reader)

    result = service.segment_diff(DIFF_RUN_ID)

    assert exact_path in result.commit_snapshots[0].touched_paths
    assert result.candidates[0].paths == (exact_path,)
    assert [call[3] for call in reader.commit_calls] == [1, 2]


def test_unassigned_net_delta_fails_closed_before_persistence(tmp_path) -> None:
    reader = FakeIntervalReader(
        {1: compare_payload([HEAD_SHA])},
        {(HEAD_SHA, 1): commit_payload(HEAD_SHA, [{"filename": "other.py"}])},
    )
    store, service = prepare(tmp_path, [delta("src/missing.py")], reader)

    with pytest.raises(IntervalSegmentationError, match="absent from complete commit touch sets"):
        service.segment_diff(DIFF_RUN_ID)

    assert store.list(CommitRangeSummary) == []
    assert store.list(CommitPathSnapshot) == []
    assert store.list(IntervalCandidateSegment) == []


def test_diverged_compare_frontier_fails_closed(tmp_path) -> None:
    reader = FakeIntervalReader(
        {1: compare_payload([], status="diverged", total=0)},
        {},
    )
    _, service = prepare(tmp_path, [], reader)

    with pytest.raises(IntervalSegmentationError, match="unsupported GitHub compare status"):
        service.segment_diff(DIFF_RUN_ID)


def test_foreign_delta_generation_provenance_fails_closed(tmp_path) -> None:
    contaminated = delta("src/a.py").model_copy(
        update={"current_capture_id": "capture-recursive-tree:foreign"}
    )
    reader = FakeIntervalReader(
        {1: compare_payload([HEAD_SHA])},
        {(HEAD_SHA, 1): commit_payload(HEAD_SHA, [{"filename": "src/a.py"}])},
    )
    store, service = prepare(tmp_path, [contaminated], reader)

    with pytest.raises(
        IntervalSegmentationError,
        match="generation provenance disagrees",
    ):
        service.segment_diff(DIFF_RUN_ID)

    assert store.list(CommitRangeSummary) == []
    assert store.list(CommitPathSnapshot) == []
    assert store.list(IntervalCandidateSegment) == []


def test_merge_commit_history_fails_closed_before_latest_touch_assignment(tmp_path) -> None:
    sibling_parent = "e" * 40
    reader = FakeIntervalReader(
        {1: compare_payload([HEAD_SHA])},
        {
            (HEAD_SHA, 1): commit_payload(
                HEAD_SHA,
                [{"filename": "src/a.py"}],
                parents=(BASE_SHA, sibling_parent),
            )
        },
    )
    store, service = prepare(tmp_path, [delta("src/a.py")], reader)

    with pytest.raises(
        IntervalSegmentationError,
        match="not a single-parent linear chain",
    ):
        service.segment_diff(DIFF_RUN_ID)

    assert store.list(CommitRangeSummary) == []
    assert store.list(CommitPathSnapshot) == []
    assert store.list(IntervalCandidateSegment) == []


def test_root_group_marker_cannot_collide_with_literal_top_level_directory(tmp_path) -> None:
    changes = [delta("README.md"), delta("$root/file.py")]
    reader = FakeIntervalReader(
        {1: compare_payload([HEAD_SHA])},
        {
            (HEAD_SHA, 1): commit_payload(
                HEAD_SHA,
                [{"filename": item.path} for item in changes],
            )
        },
    )
    _, service = prepare(tmp_path, changes, reader)

    result = service.segment_diff(DIFF_RUN_ID)

    groups = {candidate.paths[0]: candidate.path_group for candidate in result.candidates}
    assert groups["README.md"] == "root"
    assert groups["$root/file.py"] == 'top-level:"$root"'
    assert groups["README.md"] != groups["$root/file.py"]
