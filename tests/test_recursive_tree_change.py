from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureManifest,
    PipelineRun,
    RepositoryIdentity,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.path_change_contracts import ChangeSurface, GitPathDelta, GitPathDeltaType
from lemmamind.recursive_tree import (
    GIT_RECURSIVE_TREE_LOCATOR,
    GitHubRecursiveTreeCaptureService,
    RecursiveGitTreeDiffService,
    RecursiveGitTreeError,
    TrackingAwareGitHubRecursiveTreeCaptureService,
    classify_change_surface,
)
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking import RepositoryTrackingService, TrackingNotAllowed
from lemmamind.tracking_contracts import TrackingLevel

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
TREE_A = "c" * 40
TREE_B = "d" * 40
SOURCE_ID = "github:42"


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self):
        value = self.value
        self.value += timedelta(seconds=1)
        return value


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"id-{self.value}"


class FakeRecursiveReader:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get_recursive_tree(self, owner, repo, tree_sha):
        self.calls.append((owner, repo, tree_sha))
        return self.payloads[tree_sha]


def prepare_store(tmp_path, *, include_source=True):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    records = []
    if include_source:
        records.append(
            Source(
                source_id=SOURCE_ID,
                source_kind=SourceKind.GITHUB_REPOSITORY,
                source_role=SourceRole.IMPLEMENTATION,
                canonical_locator="https://github.com/example/repo",
                first_seen_at=NOW,
                last_seen_at=NOW,
            )
        )
    records.extend(
        (
            RepositoryIdentity(
                source_id=SOURCE_ID,
                provider_repository_id="42",
                owner="example",
                name="repo",
                default_branch="main",
            ),
            SourceRevision(
                source_revision_id=f"{SOURCE_ID}@{COMMIT_A}",
                source_id=SOURCE_ID,
                commit_sha=COMMIT_A,
                tree_sha=TREE_A,
                observed_at=NOW,
            ),
            SourceRevision(
                source_revision_id=f"{SOURCE_ID}@{COMMIT_B}",
                source_id=SOURCE_ID,
                commit_sha=COMMIT_B,
                tree_sha=TREE_B,
                observed_at=NOW + timedelta(minutes=1),
            ),
        )
    )
    store.put_many(records)
    return store


def recursive_payload(tree_sha, entries, *, truncated=False):
    return {
        "sha": tree_sha,
        "truncated": truncated,
        "tree": entries,
    }


def entry(path, sha, *, entry_type="blob", mode="100644", size=10):
    result = {
        "path": path,
        "mode": mode,
        "type": entry_type,
        "sha": sha,
    }
    if size is not None:
        result["size"] = size
    return result


def test_recursive_capture_accepts_nested_paths_and_canonicalizes(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    reader = FakeRecursiveReader(
        {
            TREE_A: recursive_payload(
                TREE_A,
                [
                    entry("src/app.py", "2" * 40),
                    entry("src", "1" * 40, entry_type="tree", mode="040000", size=None),
                    entry("README.md", "3" * 40),
                ],
            )
        }
    )
    service = GitHubRecursiveTreeCaptureService(
        reader,
        store,
        objects,
        clock=Clock(),
        id_factory=Ids(),
    )

    captured = service.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_A}")

    assert reader.calls == [("example", "repo", TREE_A)]
    assert captured.artifact.source_locator == GIT_RECURSIVE_TREE_LOCATOR
    canonical = objects.get(captured.artifact.content_hash).decode("utf-8")
    assert canonical.index('"path":"README.md"') < canonical.index('"path":"src"')
    assert canonical.index('"path":"src"') < canonical.index('"path":"src/app.py"')
    assert '"recursive":true' in canonical
    assert '"truncated":false' in canonical
    assert len(store.list(Artifact)) == 1
    assert len(store.list(CaptureManifest)) == 1
    assert len(store.list(PipelineRun)) == 1


def test_recursive_capture_rejects_truncated_response_before_persistence(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    reader = FakeRecursiveReader(
        {
            TREE_A: recursive_payload(
                TREE_A,
                [entry("src/app.py", "1" * 40)],
                truncated=True,
            )
        }
    )

    with pytest.raises(RecursiveGitTreeError, match="truncated"):
        GitHubRecursiveTreeCaptureService(reader, store, objects).capture_recursive_tree(
            f"{SOURCE_ID}@{COMMIT_A}"
        )

    assert store.list(Artifact) == []
    assert store.list(CaptureManifest) == []


def test_recursive_capture_rejects_sha_mismatch_and_unsafe_paths(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    mismatch = FakeRecursiveReader(
        {TREE_A: recursive_payload(TREE_B, [entry("src/app.py", "1" * 40)])}
    )
    with pytest.raises(RecursiveGitTreeError, match="tree SHA mismatch"):
        GitHubRecursiveTreeCaptureService(mismatch, store, objects).capture_recursive_tree(
            f"{SOURCE_ID}@{COMMIT_A}"
        )

    unsafe = FakeRecursiveReader(
        {TREE_A: recursive_payload(TREE_A, [entry("src/../secret", "1" * 40)])}
    )
    with pytest.raises(RecursiveGitTreeError, match="unsafe path"):
        GitHubRecursiveTreeCaptureService(unsafe, store, objects).capture_recursive_tree(
            f"{SOURCE_ID}@{COMMIT_A}"
        )


def test_recursive_capture_rejects_duplicate_paths(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    reader = FakeRecursiveReader(
        {
            TREE_A: recursive_payload(
                TREE_A,
                [entry("src/app.py", "1" * 40), entry("src/app.py", "2" * 40)],
            )
        }
    )
    with pytest.raises(RecursiveGitTreeError, match="duplicate recursive tree path"):
        GitHubRecursiveTreeCaptureService(reader, store, objects).capture_recursive_tree(
            f"{SOURCE_ID}@{COMMIT_A}"
        )


def test_recursive_diff_emits_leaf_changes_not_parent_tree_hash_churn(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_entries = [
        entry("src", "1" * 40, entry_type="tree", mode="040000", size=None),
        entry("src/app.py", "2" * 40),
        entry("src/old.py", "3" * 40),
        entry("tests", "4" * 40, entry_type="tree", mode="040000", size=None),
        entry("tests/test_app.py", "5" * 40),
        entry("vendor", "6" * 40, entry_type="tree", mode="040000", size=None),
        entry("vendor/lib.js", "7" * 40),
        entry("README.md", "8" * 40),
    ]
    current_entries = [
        entry("src", "9" * 40, entry_type="tree", mode="040000", size=None),
        entry("src/app.py", "a" * 40),
        entry("src/new.py", "b" * 40),
        entry("tests", "c" * 40, entry_type="tree", mode="040000", size=None),
        entry("tests/test_app.py", "5" * 40, mode="100755"),
        entry("vendor", "d" * 40, entry_type="tree", mode="040000", size=None),
        entry("vendor/lib.js", "e" * 40),
        entry("README.md", "8" * 40),
        entry(".github", "f" * 40, entry_type="tree", mode="040000", size=None),
        entry(".github/workflows", "1" * 40, entry_type="tree", mode="040000", size=None),
        entry(".github/workflows/test.yml", "2" * 40),
    ]
    reader = FakeRecursiveReader(
        {
            TREE_A: recursive_payload(TREE_A, previous_entries),
            TREE_B: recursive_payload(TREE_B, current_entries),
        }
    )
    capture = GitHubRecursiveTreeCaptureService(reader, store, objects, id_factory=Ids())
    previous = capture.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_A}")
    current = capture.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_B}")

    result = RecursiveGitTreeDiffService(
        store,
        objects,
        clock=Clock(),
        id_factory=Ids(),
    ).compare_captures(previous.manifest.capture_id, current.manifest.capture_id)
    by_path = {delta.path: delta for delta in result.deltas}

    assert set(by_path) == {
        ".github/workflows/test.yml",
        "src/app.py",
        "src/new.py",
        "src/old.py",
        "tests/test_app.py",
        "vendor/lib.js",
    }
    assert "src" not in by_path
    assert "tests" not in by_path
    assert by_path["src/app.py"].change_type is GitPathDeltaType.MODIFIED
    assert by_path["src/new.py"].change_type is GitPathDeltaType.ADDED
    assert by_path["src/old.py"].change_type is GitPathDeltaType.REMOVED
    assert by_path["tests/test_app.py"].change_type is GitPathDeltaType.MODIFIED
    assert by_path[".github/workflows/test.yml"].surface is ChangeSurface.WORKFLOW
    assert by_path["src/app.py"].surface is ChangeSurface.SOURCE
    assert by_path["tests/test_app.py"].surface is ChangeSurface.TEST
    assert by_path["vendor/lib.js"].surface is ChangeSurface.VENDORED
    assert len(store.list(GitPathDelta)) == 6
    assert result.run.run_type.value == "diff"


def test_recursive_diff_records_tree_to_blob_type_change(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    reader = FakeRecursiveReader(
        {
            TREE_A: recursive_payload(
                TREE_A,
                [entry("config", "1" * 40, entry_type="tree", mode="040000", size=None)],
            ),
            TREE_B: recursive_payload(TREE_B, [entry("config", "2" * 40)]),
        }
    )
    capture = GitHubRecursiveTreeCaptureService(reader, store, objects, id_factory=Ids())
    previous = capture.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_A}")
    current = capture.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_B}")

    result = RecursiveGitTreeDiffService(store, objects, id_factory=Ids()).compare_captures(
        previous.manifest.capture_id,
        current.manifest.capture_id,
    )

    assert len(result.deltas) == 1
    assert result.deltas[0].path == "config"
    assert result.deltas[0].change_type is GitPathDeltaType.TYPE_CHANGED
    assert result.deltas[0].previous_entry_type == "tree"
    assert result.deltas[0].current_entry_type == "blob"


def test_recursive_diff_rejects_cross_source_comparison(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    other_source_id = "github:99"
    store.put_many(
        (
            RepositoryIdentity(
                source_id=other_source_id,
                provider_repository_id="99",
                owner="other",
                name="repo",
                default_branch="main",
            ),
            SourceRevision(
                source_revision_id=f"{other_source_id}@{'e' * 40}",
                source_id=other_source_id,
                commit_sha="e" * 40,
                tree_sha="f" * 40,
                observed_at=NOW,
            ),
        )
    )
    reader = FakeRecursiveReader(
        {
            TREE_A: recursive_payload(TREE_A, [entry("README.md", "1" * 40)]),
            "f" * 40: recursive_payload("f" * 40, [entry("README.md", "2" * 40)]),
        }
    )
    capture = GitHubRecursiveTreeCaptureService(reader, store, objects, id_factory=Ids())
    previous = capture.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_A}")
    current = capture.capture_recursive_tree(f"{other_source_id}@{'e' * 40}")

    with pytest.raises(RecursiveGitTreeError, match="requires one Source"):
        RecursiveGitTreeDiffService(store, objects).compare_captures(
            previous.manifest.capture_id,
            current.manifest.capture_id,
        )


def test_tracking_aware_recursive_capture_requires_structural_level(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    reader = FakeRecursiveReader(
        {TREE_A: recursive_payload(TREE_A, [entry("README.md", "1" * 40)])}
    )
    tracking = RepositoryTrackingService(store, clock=Clock())
    tracking.assign_level(
        SOURCE_ID,
        TrackingLevel.SHALLOW,
        assigned_by="test",
        reason="shallow first",
    )
    service = TrackingAwareGitHubRecursiveTreeCaptureService(
        reader,
        store,
        objects,
        tracking=tracking,
    )

    with pytest.raises(TrackingNotAllowed):
        service.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_A}")

    tracking.assign_level(
        SOURCE_ID,
        TrackingLevel.STRUCTURAL,
        assigned_by="test",
        reason="allow structural tree evidence",
    )
    captured = service.capture_recursive_tree(f"{SOURCE_ID}@{COMMIT_A}")
    assert captured.manifest.source_revision_id == f"{SOURCE_ID}@{COMMIT_A}"


@pytest.mark.parametrize(
    ("path", "surface"),
    [
        (".github/workflows/test.yml", ChangeSurface.WORKFLOW),
        ("pnpm-lock.yaml", ChangeSurface.LOCKFILE),
        ("package.json", ChangeSurface.MANIFEST),
        ("vendor/lib.js", ChangeSurface.VENDORED),
        ("generated/client.ts", ChangeSurface.GENERATED),
        ("tests/test_api.py", ChangeSurface.TEST),
        ("docs/design.md", ChangeSurface.DOCS),
        ("config/settings.yaml", ChangeSurface.CONFIG),
        ("src/app.py", ChangeSurface.SOURCE),
        ("assets/logo.png", ChangeSurface.UNKNOWN),
    ],
)
def test_change_surface_classifier_is_deterministic(path, surface) -> None:
    assert classify_change_surface(path) is surface
