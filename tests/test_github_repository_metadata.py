from datetime import datetime, timezone

import pytest

from lemmamind.contracts import RepositoryIdentity, SourceRevision
from lemmamind.github_repository_metadata import (
    GitHubRepositoryMetadataCaptureService,
    GitHubRepositoryMetadataError,
    GitHubRepositoryMetadataEvidenceService,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 17, 0, tzinfo=timezone.utc)


class FakeReader:
    def __init__(self, payload=None):
        self.payload = payload or {
            "id": 1282740796,
            "full_name": "ElephantRock/ExpertOS",
            "visibility": "private",
            "private": True,
            "archived": False,
            "fork": False,
            "default_branch": "master",
        }

    def get_repository(self, owner, repo):
        assert (owner, repo) == ("ElephantRock", "ExpertOS")
        return self.payload


def build_store(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    identity = RepositoryIdentity(
        source_id="github:1282740796",
        provider_repository_id="1282740796",
        owner="ElephantRock",
        name="ExpertOS",
        default_branch="master",
        aliases=(),
        archived=False,
    )
    revision = SourceRevision(
        source_revision_id="github:1282740796@8fd8250121baf75b3689e2bba7ba2df8fa3608cf",
        source_id=identity.source_id,
        commit_sha="8fd8250121baf75b3689e2bba7ba2df8fa3608cf",
        tree_sha="a" * 40,
        observed_at=NOW,
    )
    store.put_many((identity, revision))
    return store, objects, revision


def test_captures_visibility_as_content_addressed_evidence(tmp_path) -> None:
    store, objects, revision = build_store(tmp_path)
    captured = GitHubRepositoryMetadataCaptureService(
        FakeReader(), store, objects, clock=lambda: NOW
    ).capture_metadata(revision.source_revision_id)
    extracted = GitHubRepositoryMetadataEvidenceService(
        store, objects, clock=lambda: NOW
    ).extract_metadata(captured.manifest.capture_id)

    by_locator = {fact.locator: fact.normalized_value for fact in extracted.facts}
    assert by_locator["$github/repository#/visibility"] == "private"
    assert by_locator["$github/repository#/private"] is True
    assert by_locator["$github/repository#/full_name"] == "ElephantRock/ExpertOS"
    assert objects.get(captured.artifact.content_hash)


def test_rejects_provider_identity_mismatch(tmp_path) -> None:
    store, objects, revision = build_store(tmp_path)
    payload = FakeReader().payload | {"id": 999}
    with pytest.raises(GitHubRepositoryMetadataError, match="provider repository id mismatch"):
        GitHubRepositoryMetadataCaptureService(
            FakeReader(payload), store, objects, clock=lambda: NOW
        ).capture_metadata(revision.source_revision_id)


def test_rejects_inconsistent_visibility_and_private_flag(tmp_path) -> None:
    store, objects, revision = build_store(tmp_path)
    payload = FakeReader().payload | {"visibility": "public", "private": True}
    with pytest.raises(GitHubRepositoryMetadataError, match="disagrees with visibility"):
        GitHubRepositoryMetadataCaptureService(
            FakeReader(payload), store, objects, clock=lambda: NOW
        ).capture_metadata(revision.source_revision_id)
