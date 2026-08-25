from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    EvidenceFact,
    PipelineRun,
    RepositoryIdentity,
    RunType,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
    SourceAssertion,
)
from lemmamind.github_process import (
    GitHubProcessCaptureService,
    GitHubProcessError,
    GitHubProcessEvidenceService,
    ProcessKind,
    ProcessRef,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"process-{self.value}"


class FakeProcessReader:
    def __init__(self) -> None:
        self.issue_state = "open"

    def get_issue(self, owner: str, repo: str, number: int):
        assert (owner, repo, number) == ("ElephantRock", "CSD-Foundry", 37)
        return {
            "id": 3700,
            "node_id": "I_37",
            "number": 37,
            "html_url": "https://github.com/ElephantRock/CSD-Foundry/issues/37",
            "state": self.issue_state,
            "state_reason": None,
            "title": "Implement v0.5-D governed registries",
            "body": "Umbrella tracking issue for the governed registry work.",
            "user": {"login": "maintainer"},
            "author_association": "OWNER",
            "locked": False,
            "comments": 12,
            "labels": [{"name": "roadmap"}, {"name": "governance"}],
            "assignees": [{"login": "maintainer"}],
            "created_at": "2026-07-01T00:00:00Z",
            "updated_at": "2026-08-25T10:00:00Z",
            "closed_at": None if self.issue_state == "open" else "2026-08-24T10:00:00Z",
        }

    def get_pull(self, owner: str, repo: str, number: int):
        assert (owner, repo, number) == ("ElephantRock", "CSD-Foundry", 117)
        return {
            "id": 11700,
            "node_id": "PR_117",
            "number": 117,
            "html_url": "https://github.com/ElephantRock/CSD-Foundry/pull/117",
            "state": "open",
            "draft": True,
            "merged": False,
            "merge_commit_sha": None,
            "title": "P3.7: Phase-3 integrated qualification and closure",
            "body": "Independent validator, canary, mutation campaign, and determinism checks.",
            "user": {"login": "maintainer"},
            "author_association": "OWNER",
            "labels": [{"name": "qualification"}],
            "requested_reviewers": [{"login": "reviewer"}],
            "head": {
                "ref": "p3.7-qualification",
                "sha": "2" * 40,
                "repo": {"full_name": "ElephantRock/CSD-Foundry"},
            },
            "base": {
                "ref": "main",
                "sha": "a" * 40,
                "repo": {"full_name": "ElephantRock/CSD-Foundry"},
            },
            "commits": 4,
            "changed_files": 11,
            "additions": 900,
            "deletions": 40,
            "created_at": "2026-08-20T00:00:00Z",
            "updated_at": "2026-08-25T10:05:00Z",
            "closed_at": None,
            "merged_at": None,
        }


def build_store(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source = Source(
        source_id="github:csd",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/ElephantRock/CSD-Foundry",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    repository = RepositoryIdentity(
        source_id=source.source_id,
        provider_repository_id="12345",
        owner="ElephantRock",
        name="CSD-Foundry",
        default_branch="main",
        aliases=(),
        archived=False,
    )
    revision = SourceRevision(
        source_revision_id="github:csd@" + "a" * 40,
        source_id=source.source_id,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        observed_at=NOW,
    )
    store.put_many((source, repository, revision))
    return store, objects, revision


def services(tmp_path, reader=None):
    store, objects, revision = build_store(tmp_path)
    ids = DeterministicIds()
    reader = reader or FakeProcessReader()
    capture = GitHubProcessCaptureService(
        reader,
        store,
        objects,
        clock=lambda: NOW,
        id_factory=ids,
    )
    extraction = GitHubProcessEvidenceService(
        store,
        objects,
        clock=lambda: NOW,
        id_factory=ids,
    )
    return store, objects, revision, reader, capture, extraction


def test_captures_issue_and_pull_as_immutable_process_snapshots(tmp_path) -> None:
    store, objects, revision, _, capture, extraction = services(tmp_path)

    captured = capture.capture_process(
        revision.source_revision_id,
        (
            ProcessRef(ProcessKind.ISSUE, 37),
            ProcessRef(ProcessKind.PULL_REQUEST, 117),
        ),
    )

    assert captured.manifest.source_revision_id == revision.source_revision_id
    assert captured.manifest.capture_policy_version == "github.process-snapshot.v1"
    assert [artifact.source_locator for artifact in captured.artifacts] == [
        "$github/issue/37",
        "$github/pull/117",
    ]
    assert captured.run.run_type is RunType.CAPTURE
    assert captured.run.outputs_hash is not None
    assert all(objects.get(item.content_hash) for item in captured.artifacts)
    assert len(store.list(Artifact)) == 2

    extracted = extraction.extract_process(captured.manifest.capture_id)
    assert extracted.run.run_type is RunType.EXTRACTION
    assert extracted.run.outputs_hash is not None

    facts_by_locator = {fact.locator: fact.normalized_value for fact in extracted.facts}
    assert facts_by_locator["$github/issue/37#/state"] == "open"
    assert facts_by_locator["$github/issue/37#/comments"] == 12
    assert facts_by_locator["$github/pull/117#/draft"] is True
    assert facts_by_locator["$github/pull/117#/merged"] is False
    assert facts_by_locator["$github/pull/117#/head/sha"] == "2" * 40
    assert facts_by_locator["$github/pull/117#/base/sha"] == "a" * 40

    assertions = {(item.locator, item.statement) for item in extracted.assertions}
    assert (
        "$github/issue/37#title",
        "Implement v0.5-D governed registries",
    ) in assertions
    assert (
        "$github/pull/117#body",
        "Independent validator, canary, mutation campaign, and determinism checks.",
    ) in assertions

    assert all(not fact.locator.endswith("#title") for fact in extracted.facts)
    assert all(not fact.locator.endswith("#body") for fact in extracted.facts)
    assert all(isinstance(fact, EvidenceFact) for fact in extracted.facts)
    assert all(isinstance(item, SourceAssertion) for item in extracted.assertions)


def test_repeated_capture_preserves_old_snapshot_when_mutable_issue_state_changes(tmp_path) -> None:
    reader = FakeProcessReader()
    store, objects, revision, _, capture, _ = services(tmp_path, reader=reader)

    first = capture.capture_process(
        revision.source_revision_id,
        (ProcessRef(ProcessKind.ISSUE, 37),),
    )
    first_hash = first.artifacts[0].content_hash
    first_bytes = objects.get(first_hash)

    reader.issue_state = "closed"
    second = capture.capture_process(
        revision.source_revision_id,
        (ProcessRef(ProcessKind.ISSUE, 37),),
    )
    second_hash = second.artifacts[0].content_hash

    assert first.manifest.capture_id != second.manifest.capture_id
    assert first_hash != second_hash
    assert objects.get(first_hash) == first_bytes
    assert b'"state":"open"' in objects.get(first_hash)
    assert b'"state":"closed"' in objects.get(second_hash)


def test_issue_endpoint_pull_marker_is_rejected(tmp_path) -> None:
    class BadReader(FakeProcessReader):
        def get_issue(self, owner: str, repo: str, number: int):
            payload = super().get_issue(owner, repo, number)
            payload["pull_request"] = {"url": "https://api.github.com/pulls/37"}
            return payload

    _, _, revision, _, capture, _ = services(tmp_path, reader=BadReader())

    with pytest.raises(GitHubProcessError, match="use ProcessKind.PULL_REQUEST"):
        capture.capture_process(
            revision.source_revision_id,
            (ProcessRef(ProcessKind.ISSUE, 37),),
        )


def test_duplicate_process_refs_are_rejected_before_capture(tmp_path) -> None:
    store, _, revision, _, capture, _ = services(tmp_path)

    with pytest.raises(ValueError, match="duplicate"):
        capture.capture_process(
            revision.source_revision_id,
            (
                ProcessRef(ProcessKind.PULL_REQUEST, 117),
                ProcessRef(ProcessKind.PULL_REQUEST, 117),
            ),
        )

    assert store.list(PipelineRun) == []
