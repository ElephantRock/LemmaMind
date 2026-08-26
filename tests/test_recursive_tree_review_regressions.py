import json
from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    RetrievalStatus,
    SourceRevision,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.path_change_contracts import GitPathDelta
from lemmamind.recursive_tree import (
    GIT_RECURSIVE_TREE_LOCATOR,
    GIT_RECURSIVE_TREE_MEDIA_TYPE,
    RecursiveGitTreeDiffService,
    RecursiveGitTreeError,
)
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)
SOURCE_ID = "github:review-regression"


def _persist_recursive_capture(
    store,
    objects,
    *,
    name: str,
    commit_char: str,
    tree_char: str,
    observed_at: datetime,
    captured_at: datetime,
    entries: list[dict],
) -> CaptureManifest:
    commit_sha = commit_char * 40
    tree_sha = tree_char * 40
    revision = SourceRevision(
        source_revision_id=f"{SOURCE_ID}@{commit_sha}",
        source_id=SOURCE_ID,
        commit_sha=commit_sha,
        tree_sha=tree_sha,
        observed_at=observed_at,
    )
    document = {
        "tree_sha": tree_sha,
        "recursive": True,
        "truncated": False,
        "entries": sorted(entries, key=lambda item: item["path"]),
    }
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    content_hash = objects.put(payload)
    capture_id = f"capture-recursive-tree:{name}"
    artifact_id = f"artifact:recursive-tree:{name}"
    artifact = Artifact(
        artifact_id=artifact_id,
        capture_id=capture_id,
        source_locator=GIT_RECURSIVE_TREE_LOCATOR,
        content_hash=content_hash,
        media_type=GIT_RECURSIVE_TREE_MEDIA_TYPE,
    )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="github.recursive-tree.v1",
        captured_at=captured_at,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact_id,
                source_locator=GIT_RECURSIVE_TREE_LOCATOR,
                content_hash=content_hash,
                media_type=GIT_RECURSIVE_TREE_MEDIA_TYPE,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    store.put_many((revision, artifact, manifest))
    return manifest


def _blob(path: str, sha_char: str) -> dict:
    return {
        "path": path,
        "mode": "100644",
        "type": "blob",
        "sha": sha_char * 40,
        "size": 1,
    }


def test_recursive_diff_preserves_leading_and_trailing_whitespace_in_git_path(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous = _persist_recursive_capture(
        store,
        objects,
        name="previous-whitespace",
        commit_char="a",
        tree_char="b",
        observed_at=NOW,
        captured_at=NOW,
        entries=[],
    )
    current = _persist_recursive_capture(
        store,
        objects,
        name="current-whitespace",
        commit_char="c",
        tree_char="d",
        observed_at=NOW + timedelta(seconds=1),
        captured_at=NOW + timedelta(seconds=1),
        entries=[_blob(" file.py ", "e")],
    )

    result = RecursiveGitTreeDiffService(store, objects).compare_captures(
        previous.capture_id,
        current.capture_id,
    )

    assert [delta.path for delta in result.deltas] == [" file.py "]
    assert store.list(GitPathDelta)[0].path == " file.py "


def test_recursive_diff_rejects_newer_previous_source_revision(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous = _persist_recursive_capture(
        store,
        objects,
        name="previous-revision-time",
        commit_char="a",
        tree_char="b",
        observed_at=NOW + timedelta(seconds=2),
        captured_at=NOW,
        entries=[_blob("old.py", "e")],
    )
    current = _persist_recursive_capture(
        store,
        objects,
        name="current-revision-time",
        commit_char="c",
        tree_char="d",
        observed_at=NOW + timedelta(seconds=1),
        captured_at=NOW + timedelta(seconds=1),
        entries=[_blob("old.py", "f")],
    )

    with pytest.raises(RecursiveGitTreeError, match="previous SourceRevision"):
        RecursiveGitTreeDiffService(store, objects).compare_captures(
            previous.capture_id,
            current.capture_id,
        )

    assert store.list(GitPathDelta) == []


def test_recursive_diff_rejects_newer_previous_capture_manifest(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous = _persist_recursive_capture(
        store,
        objects,
        name="previous-capture-time",
        commit_char="a",
        tree_char="b",
        observed_at=NOW,
        captured_at=NOW + timedelta(seconds=2),
        entries=[_blob("old.py", "e")],
    )
    current = _persist_recursive_capture(
        store,
        objects,
        name="current-capture-time",
        commit_char="c",
        tree_char="d",
        observed_at=NOW + timedelta(seconds=1),
        captured_at=NOW + timedelta(seconds=1),
        entries=[_blob("old.py", "f")],
    )

    with pytest.raises(RecursiveGitTreeError, match="previous CaptureManifest"):
        RecursiveGitTreeDiffService(store, objects).compare_captures(
            previous.capture_id,
            current.capture_id,
        )

    assert store.list(GitPathDelta) == []
