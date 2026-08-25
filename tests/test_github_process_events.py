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
)
from lemmamind.github_process_events import (
    GitHubProcessEventCaptureService,
    GitHubProcessEventError,
    GitHubProcessEventEvidenceService,
    GitHubProcessEventRESTReader,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"event-{self.value}"


class FakeEventReader:
    def get_issue_events(self, owner: str, repo: str, number: int):
        assert (owner, repo, number) == ("ElephantRock", "CSD-Foundry", 37)
        # Deliberately returned out of order: capture must canonicalize by provider time/id.
        return (
            {
                "id": 29941032785,
                "node_id": "REE_37",
                "event": "reopened",
                "actor": {"login": "Alajmah"},
                "commit_id": None,
                "commit_url": None,
                "created_at": "2026-08-24T21:36:12Z",
            },
            {
                "id": 29940854834,
                "node_id": "CE_37",
                "event": "closed",
                "actor": {"login": "Alajmah"},
                "commit_id": None,
                "commit_url": None,
                "created_at": "2026-08-24T21:31:54Z",
            },
            {
                "id": 28846410979,
                "node_id": "REF_37",
                "event": "referenced",
                "actor": {"login": "Alajmah"},
                "commit_id": "4" * 40,
                "commit_url": "https://api.github.com/repos/ElephantRock/CSD-Foundry/commits/" + "4" * 40,
                "created_at": "2026-08-02T11:55:57Z",
            },
        )


def build_store(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source = Source(
        source_id="github:1318635781",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/ElephantRock/CSD-Foundry",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    repository = RepositoryIdentity(
        source_id=source.source_id,
        provider_repository_id="1318635781",
        owner="ElephantRock",
        name="CSD-Foundry",
        default_branch="main",
        aliases=(),
        archived=False,
    )
    revision = SourceRevision(
        source_revision_id="github:1318635781@aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7",
        source_id=source.source_id,
        commit_sha="aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7",
        tree_sha="b" * 40,
        observed_at=NOW,
    )
    store.put_many((source, repository, revision))
    return store, objects, revision


def services(tmp_path, reader=None):
    store, objects, revision = build_store(tmp_path)
    ids = DeterministicIds()
    capture = GitHubProcessEventCaptureService(
        reader or FakeEventReader(),
        store,
        objects,
        clock=lambda: NOW,
        id_factory=ids,
    )
    extraction = GitHubProcessEventEvidenceService(
        store,
        objects,
        clock=lambda: NOW,
        id_factory=ids,
    )
    return store, objects, revision, capture, extraction


def test_captures_and_extracts_chronological_issue_event_history(tmp_path) -> None:
    store, objects, revision, capture, extraction = services(tmp_path)

    captured = capture.capture_issue_events(revision.source_revision_id, (37,))

    assert captured.manifest.source_revision_id == revision.source_revision_id
    assert captured.manifest.capture_policy_version == "github.issue-events.v1"
    assert len(captured.artifacts) == 1
    artifact = captured.artifacts[0]
    assert artifact.source_locator == "$github/issue/37/events"
    assert objects.get(artifact.content_hash)
    assert captured.run.run_type is RunType.CAPTURE
    assert len(store.list(Artifact)) == 1

    extracted = extraction.extract_issue_events(captured.manifest.capture_id)
    assert extracted.run.run_type is RunType.EXTRACTION
    assert all(isinstance(fact, EvidenceFact) for fact in extracted.facts)

    facts = {fact.locator: fact.normalized_value for fact in extracted.facts}
    assert facts["$github/issue/37/events#/event_count"] == 3
    assert facts["$github/issue/37/events#/events/0/event"] == "referenced"
    assert facts["$github/issue/37/events#/events/1/event"] == "closed"
    assert facts["$github/issue/37/events#/events/1/created_at"] == "2026-08-24T21:31:54Z"
    assert facts["$github/issue/37/events#/events/2/event"] == "reopened"
    assert facts["$github/issue/37/events#/events/2/created_at"] == "2026-08-24T21:36:12Z"
    assert facts["$github/issue/37/events#/events/2/actor_login"] == "Alajmah"


def test_duplicate_provider_event_ids_fail_closed(tmp_path) -> None:
    class DuplicateReader(FakeEventReader):
        def get_issue_events(self, owner: str, repo: str, number: int):
            events = list(super().get_issue_events(owner, repo, number))
            events.append(dict(events[0]))
            return tuple(events)

    _, _, revision, capture, _ = services(tmp_path, reader=DuplicateReader())

    with pytest.raises(GitHubProcessEventError, match="duplicate GitHub issue event id"):
        capture.capture_issue_events(revision.source_revision_id, (37,))


def test_duplicate_issue_numbers_are_rejected_before_capture(tmp_path) -> None:
    store, _, revision, capture, _ = services(tmp_path)

    with pytest.raises(ValueError, match="duplicate"):
        capture.capture_issue_events(revision.source_revision_id, (37, 37))

    assert store.list(PipelineRun) == []


def test_rest_reader_paginates_until_short_page() -> None:
    class StubReader(GitHubProcessEventRESTReader):
        def __init__(self):
            super().__init__(max_pages=3)
            self.pages = []

        def _get_json(self, path, query=None):
            self.pages.append((path, dict(query or {})))
            page = int(query["page"])
            if page == 1:
                return [
                    {
                        "id": index + 1,
                        "node_id": f"E_{index + 1}",
                        "event": "referenced",
                        "actor": None,
                        "commit_id": None,
                        "commit_url": None,
                        "created_at": "2026-08-01T00:00:00Z",
                    }
                    for index in range(100)
                ]
            return []

    reader = StubReader()
    events = reader.get_issue_events("ElephantRock", "CSD-Foundry", 37)

    assert len(events) == 100
    assert [query["page"] for _, query in reader.pages] == ["1", "2"]
    assert all(query["per_page"] == "100" for _, query in reader.pages)


def test_rest_reader_refuses_silent_pagination_truncation() -> None:
    class EndlessReader(GitHubProcessEventRESTReader):
        def __init__(self):
            super().__init__(max_pages=2)

        def _get_json(self, path, query=None):
            return [
                {
                    "id": int(query["page"]) * 1000 + index,
                    "node_id": f"E_{query['page']}_{index}",
                    "event": "referenced",
                    "actor": None,
                    "commit_id": None,
                    "commit_url": None,
                    "created_at": "2026-08-01T00:00:00Z",
                }
                for index in range(100)
            ]

    with pytest.raises(GitHubProcessEventError, match="refusing truncated history"):
        EndlessReader().get_issue_events("ElephantRock", "CSD-Foundry", 37)
