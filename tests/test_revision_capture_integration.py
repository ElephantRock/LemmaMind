from datetime import datetime, timedelta, timezone

from lemmamind.contracts import SourceRole
from lemmamind.github import GitHubCaptureService, GitHubNotFound
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.revision_capture import CaptureReconstructionService
from lemmamind.storage import SQLiteContractStore

COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40


class FakeGitHubReader:
    def __init__(self) -> None:
        self.files = {
            "README.md": b"# reconstruct me\n",
            "pyproject.toml": b"[project]\nname='demo'\n",
        }
        self.provider_reads = 0

    def get_repository(self, owner: str, repo: str):
        self.provider_reads += 1
        return {
            "id": 42,
            "owner": {"login": "Acme"},
            "name": "Repo",
            "default_branch": "main",
            "archived": False,
        }

    def get_commit(self, owner: str, repo: str, ref: str):
        self.provider_reads += 1
        return {"sha": COMMIT_SHA, "commit": {"tree": {"sha": TREE_SHA}}}

    def get_file(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        self.provider_reads += 1
        try:
            return self.files[path]
        except KeyError as exc:
            raise GitHubNotFound("missing", status_code=404) from exc


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 26, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"id-{self.value}"


def test_existing_github_capture_reconstructs_locally_without_new_provider_reads(tmp_path) -> None:
    reader = FakeGitHubReader()
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    capture = GitHubCaptureService(
        reader,
        store,
        objects,
        clock=Clock(),
        id_factory=Ids(),
    )

    captured = capture.capture_repository(
        "Acme/Repo",
        ["README.md", "pyproject.toml", "missing.md"],
        source_role=SourceRole.IMPLEMENTATION,
    )
    reads_after_capture = reader.provider_reads

    reconstructed = CaptureReconstructionService(store, objects).reconstruct(
        captured.manifest.capture_id
    )

    assert reader.provider_reads == reads_after_capture
    assert reconstructed.revision == captured.revision
    assert reconstructed.manifest == captured.manifest
    assert reconstructed.captured_bytes_by_locator() == {
        "README.md": b"# reconstruct me\n",
        "pyproject.toml": b"[project]\nname='demo'\n",
    }
    missing = [item for item in reconstructed.artifacts if item.source_locator == "missing.md"]
    assert len(missing) == 1
    assert missing[0].data is None
