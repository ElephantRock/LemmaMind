from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RepositoryIdentity,
    SourceRevision,
)
from lemmamind.git_tree import (
    GIT_ROOT_TREE_LOCATOR,
    GitHubRootTreeCaptureService,
    GitTreeError,
    GitTreeEvidenceService,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
TREE_SHA = "b" * 40
COMMIT_SHA = "a" * 40


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


class FakeTreeReader:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_tree(self, owner, repo, tree_sha):
        self.calls.append((owner, repo, tree_sha))
        return self.payload


def prepare_store(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put_many(
        (
            RepositoryIdentity(
                source_id="github:42",
                provider_repository_id="42",
                owner="example",
                name="repo",
                default_branch="main",
            ),
            SourceRevision(
                source_revision_id=f"github:42@{COMMIT_SHA}",
                source_id="github:42",
                commit_sha=COMMIT_SHA,
                tree_sha=TREE_SHA,
                observed_at=NOW,
            ),
        )
    )
    return store


def payload(*, sha=TREE_SHA, truncated=False):
    return {
        "sha": sha,
        "truncated": truncated,
        "tree": [
            {
                "path": "README.md",
                "mode": "100644",
                "type": "blob",
                "sha": "d" * 40,
                "size": 12,
            },
            {
                "path": ".github",
                "mode": "040000",
                "type": "tree",
                "sha": "c" * 40,
            },
        ],
    }


def test_root_tree_capture_is_pinned_content_addressed_and_extractable(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    reader = FakeTreeReader(payload())
    capture = GitHubRootTreeCaptureService(
        reader,
        store,
        objects,
        clock=Clock(),
        id_factory=Ids(),
    )

    captured = capture.capture_root_tree(f"github:42@{COMMIT_SHA}")

    assert reader.calls == [("example", "repo", TREE_SHA)]
    assert captured.manifest.source_revision_id == f"github:42@{COMMIT_SHA}"
    assert captured.artifact.source_locator == GIT_ROOT_TREE_LOCATOR
    canonical = objects.get(captured.artifact.content_hash).decode("utf-8")
    assert canonical.index('"path":".github"') < canonical.index('"path":"README.md"')

    extracted = GitTreeEvidenceService(
        store,
        objects,
        clock=Clock(),
        id_factory=Ids(),
    ).extract_root_tree(captured.manifest.capture_id)
    facts = {fact.locator: fact.normalized_value for fact in extracted.facts}

    assert facts[f"{GIT_ROOT_TREE_LOCATOR}#/tree_sha"] == TREE_SHA
    assert facts[f"{GIT_ROOT_TREE_LOCATOR}#/truncated"] is False
    assert facts[f"{GIT_ROOT_TREE_LOCATOR}#/entry_count"] == 2
    assert facts[f"{GIT_ROOT_TREE_LOCATOR}#/entry_paths"] == [".github", "README.md"]
    assert facts[f"{GIT_ROOT_TREE_LOCATOR}#/entries/.github/type"] == "tree"
    assert facts[f"{GIT_ROOT_TREE_LOCATOR}#/entries/README.md/type"] == "blob"
    assert len(store.list(Artifact)) == 1
    assert len(store.list(CaptureManifest)) == 1
    assert len(store.list(EvidenceFact)) == len(extracted.facts)
    assert len(store.list(PipelineRun)) == 2


def test_tree_sha_mismatch_fails_before_tree_capture_persistence(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    capture = GitHubRootTreeCaptureService(
        FakeTreeReader(payload(sha="e" * 40)),
        store,
        objects,
    )

    with pytest.raises(GitTreeError, match="tree SHA mismatch"):
        capture.capture_root_tree(f"github:42@{COMMIT_SHA}")

    assert store.list(Artifact) == []
    assert store.list(CaptureManifest) == []
    assert store.list(EvidenceFact) == []


def test_non_recursive_root_tree_rejects_nested_paths(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    nested = payload()
    nested["tree"][0]["path"] = "src/module.py"
    capture = GitHubRootTreeCaptureService(FakeTreeReader(nested), store, objects)

    with pytest.raises(GitTreeError, match="invalid path"):
        capture.capture_root_tree(f"github:42@{COMMIT_SHA}")
