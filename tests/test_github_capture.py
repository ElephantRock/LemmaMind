from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import CaptureManifest, RetrievalStatus, SourceRevision, SourceRole
from lemmamind.github import (
    GitHubCaptureService,
    GitHubNotFound,
    RepositoryIdentityDrift,
    SourceMetadataDrift,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40


class FakeGitHubReader:
    def __init__(self) -> None:
        self.metadata = {
            "id": 42,
            "owner": {"login": "Acme"},
            "name": "Repo",
            "default_branch": "main",
            "archived": False,
        }
        self.files = {
            "README.md": b"# example\n",
            "pyproject.toml": b"[project]\n",
        }
        self.file_calls: list[tuple[str, str, str, str]] = []
        self.commit_refs: list[str] = []

    def get_repository(self, owner: str, repo: str):
        return self.metadata

    def get_commit(self, owner: str, repo: str, ref: str):
        self.commit_refs.append(ref)
        return {"sha": COMMIT_SHA, "commit": {"tree": {"sha": TREE_SHA}}}

    def get_file(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        self.file_calls.append((owner, repo, path, ref))
        try:
            return self.files[path]
        except KeyError as exc:
            raise GitHubNotFound("missing", status_code=404) from exc


class IncrementingClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 25, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"id-{self.value}"


def make_service(tmp_path):
    reader = FakeGitHubReader()
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    object_store = ContentAddressedFileStore(tmp_path / "objects")
    service = GitHubCaptureService(
        reader,
        store,
        object_store,
        clock=IncrementingClock(),
        id_factory=DeterministicIds(),
    )
    return reader, store, object_store, service


def test_capture_pins_every_artifact_to_resolved_commit(tmp_path) -> None:
    reader, store, object_store, service = make_service(tmp_path)

    result = service.capture_repository(
        "Acme/Repo",
        ["pyproject.toml", "README.md", "README.md"],
        source_role=SourceRole.IMPLEMENTATION,
    )

    assert result.source.source_id == "github:42"
    assert result.repository.provider_repository_id == "42"
    assert result.revision.commit_sha == COMMIT_SHA
    assert result.revision.tree_sha == TREE_SHA
    assert reader.commit_refs == ["main"]
    assert [ref.source_locator for ref in result.manifest.artifacts] == [
        "README.md",
        "pyproject.toml",
    ]
    assert all(call[-1] == COMMIT_SHA for call in reader.file_calls)
    assert object_store.get(result.artifacts[0].content_hash) == b"# example\n"
    assert result.run.inputs_hash.startswith("sha256:")
    assert result.run.outputs_hash is not None


def test_repeat_capture_reuses_stable_source_and_revision(tmp_path) -> None:
    _, store, _, service = make_service(tmp_path)

    first = service.capture_repository("Acme/Repo", ["README.md"])
    second = service.capture_repository("Acme/Repo", ["README.md"])

    assert first.source == second.source
    assert first.repository == second.repository
    assert first.revision == second.revision
    assert first.manifest.capture_id != second.manifest.capture_id
    assert len(store.list(SourceRevision)) == 1
    assert len(store.list(CaptureManifest)) == 2


def test_missing_file_is_recorded_without_artifact_bytes(tmp_path) -> None:
    _, _, _, service = make_service(tmp_path)

    result = service.capture_repository("Acme/Repo", ["missing.txt"])

    assert result.artifacts == ()
    assert len(result.manifest.artifacts) == 1
    assert result.manifest.artifacts[0].retrieval_status is RetrievalStatus.MISSING
    assert result.manifest.artifacts[0].content_hash is None


def test_repository_metadata_drift_is_not_silently_overwritten(tmp_path) -> None:
    reader, _, _, service = make_service(tmp_path)

    service.capture_repository("Acme/Repo", ["README.md"])
    reader.metadata = {**reader.metadata, "default_branch": "trunk"}

    with pytest.raises(RepositoryIdentityDrift):
        service.capture_repository("Acme/Repo", ["README.md"])


def test_source_role_drift_requires_explicit_migration(tmp_path) -> None:
    _, _, _, service = make_service(tmp_path)

    service.capture_repository("Acme/Repo", ["README.md"])

    with pytest.raises(SourceMetadataDrift):
        service.capture_repository(
            "Acme/Repo",
            ["README.md"],
            source_role=SourceRole.IMPLEMENTATION,
        )


def test_capture_rejects_parent_traversal_paths(tmp_path) -> None:
    _, _, _, service = make_service(tmp_path)

    with pytest.raises(ValueError):
        service.capture_repository("Acme/Repo", ["../secret"])
