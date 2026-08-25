from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RepositoryIdentity,
    SourceAssertion,
    SourceRevision,
)
from lemmamind.git_commit import (
    GIT_COMMIT_LOCATOR,
    GitCommitError,
    GitCommitEvidenceService,
    GitHubCommitCaptureService,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40


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


class FakeCommitReader:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_commit(self, owner, repo, ref):
        self.calls.append((owner, repo, ref))
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


def payload(*, commit_sha=COMMIT_SHA, tree_sha=TREE_SHA):
    return {
        "sha": commit_sha,
        "commit": {
            "author": {"date": "2026-08-24T22:07:05Z"},
            "committer": {"date": "2026-08-24T22:07:05Z"},
            "message": (
                "Merge pull request #1\n\n"
                "fix(terminal): sweep setsid descendants after local timeout group-kill"
            ),
            "tree": {"sha": tree_sha},
            "verification": {
                "verified": True,
                "reason": "valid",
                "verified_at": "2026-08-24T22:07:05Z",
            },
        },
        "parents": [{"sha": "c" * 40}, {"sha": "d" * 40}],
    }


def test_commit_capture_is_pinned_content_addressed_and_extractable(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    reader = FakeCommitReader(payload())
    captured = GitHubCommitCaptureService(
        reader,
        store,
        objects,
        clock=Clock(),
        id_factory=Ids(),
    ).capture_commit(f"github:42@{COMMIT_SHA}")

    assert reader.calls == [("example", "repo", COMMIT_SHA)]
    assert captured.manifest.source_revision_id == f"github:42@{COMMIT_SHA}"
    assert captured.artifact.source_locator == GIT_COMMIT_LOCATOR

    extracted = GitCommitEvidenceService(
        store,
        objects,
        clock=Clock(),
        id_factory=Ids(),
    ).extract_commit(captured.manifest.capture_id)
    facts = {fact.locator: fact.normalized_value for fact in extracted.facts}

    assert facts[f"{GIT_COMMIT_LOCATOR}#/commit_sha"] == COMMIT_SHA
    assert facts[f"{GIT_COMMIT_LOCATOR}#/tree_sha"] == TREE_SHA
    assert facts[f"{GIT_COMMIT_LOCATOR}#/parent_count"] == 2
    assert facts[f"{GIT_COMMIT_LOCATOR}#/verification/verified"] is True
    assert extracted.assertions[0].locator == f"{GIT_COMMIT_LOCATOR}#message"
    assert "sweep setsid descendants" in extracted.assertions[0].statement
    assert len(store.list(Artifact)) == 1
    assert len(store.list(CaptureManifest)) == 1
    assert len(store.list(EvidenceFact)) == len(extracted.facts)
    assert len(store.list(SourceAssertion)) == 1
    assert len(store.list(PipelineRun)) == 2


def test_commit_sha_mismatch_fails_before_capture_persistence(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    service = GitHubCommitCaptureService(
        FakeCommitReader(payload(commit_sha="e" * 40)),
        store,
        objects,
    )

    with pytest.raises(GitCommitError, match="commit SHA mismatch"):
        service.capture_commit(f"github:42@{COMMIT_SHA}")

    assert store.list(Artifact) == []
    assert store.list(CaptureManifest) == []


def test_commit_tree_mismatch_fails_before_capture_persistence(tmp_path) -> None:
    store = prepare_store(tmp_path)
    objects = ContentAddressedFileStore(tmp_path / "objects")
    service = GitHubCommitCaptureService(
        FakeCommitReader(payload(tree_sha="e" * 40)),
        store,
        objects,
    )

    with pytest.raises(GitCommitError, match="commit tree mismatch"):
        service.capture_commit(f"github:42@{COMMIT_SHA}")

    assert store.list(Artifact) == []
    assert store.list(CaptureManifest) == []
