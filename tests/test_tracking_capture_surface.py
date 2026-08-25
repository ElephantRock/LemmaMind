from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    RepositoryIdentity,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking import RepositoryTrackingService, TrackingNotAllowed
from lemmamind.tracking_adapters import (
    TrackingAwareGitHubCommitCaptureService,
    TrackingAwareGitHubRepositoryMetadataCaptureService,
    TrackingAwareGitHubRootTreeCaptureService,
    TrackingAwareGitHubWorkflowCaptureService,
)
from lemmamind.tracking_contracts import TrackingLevel

T0 = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40


class Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class MarkerReader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_repository(self, owner: str, repo: str):
        self.calls.append("repository")
        raise AssertionError("eligible metadata capture reached provider reader")

    def get_commit(self, owner: str, repo: str, ref: str):
        self.calls.append("commit")
        raise AssertionError("eligible commit capture reached provider reader")

    def get_tree(self, owner: str, repo: str, tree_sha: str):
        self.calls.append("tree")
        raise AssertionError("eligible tree capture reached provider reader")

    def get_workflow_run(self, owner: str, repo: str, run_id: int):
        self.calls.append("workflow")
        raise AssertionError("eligible workflow capture reached provider reader")

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int):  # pragma: no cover
        raise AssertionError("workflow run marker should fail first")

    def get_workflow_artifacts(self, owner: str, repo: str, run_id: int):  # pragma: no cover
        raise AssertionError("workflow run marker should fail first")

    def probe_job_log(self, owner: str, repo: str, job_id: int):  # pragma: no cover
        raise AssertionError("workflow run marker should fail first")


def seed_repository(store: SQLiteContractStore) -> tuple[Source, SourceRevision]:
    source = Source(
        source_id="github:42",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.UNKNOWN,
        canonical_locator="https://github.com/Acme/Repo",
        first_seen_at=T0,
        last_seen_at=T0,
    )
    repository = RepositoryIdentity(
        source_id=source.source_id,
        provider_repository_id="42",
        owner="Acme",
        name="Repo",
        default_branch="main",
        archived=False,
    )
    revision = SourceRevision(
        source_revision_id=f"{source.source_id}@{COMMIT_SHA}",
        source_id=source.source_id,
        commit_sha=COMMIT_SHA,
        tree_sha=TREE_SHA,
        observed_at=T0 + timedelta(minutes=5),
    )
    store.put_many((source, repository, revision))
    return source, revision


def make_context(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source, revision = seed_repository(store)
    reader = MarkerReader()
    clock = Clock(T0 + timedelta(hours=1))
    tracking = RepositoryTrackingService(store, clock=clock)
    return store, objects, source, revision, reader, clock, tracking


def test_repository_metadata_requires_level_one(tmp_path) -> None:
    store, objects, source, revision, reader, _, tracking = make_context(tmp_path)
    service = TrackingAwareGitHubRepositoryMetadataCaptureService(
        reader,
        store,
        objects,
        tracking=tracking,
    )

    with pytest.raises(TrackingNotAllowed):
        service.capture_metadata(revision.source_revision_id)
    assert reader.calls == []

    tracking.assign_level(
        source.source_id,
        TrackingLevel.METADATA_ONLY,
        assigned_by="operator:test",
        reason="metadata watch",
    )
    with pytest.raises(AssertionError, match="eligible metadata capture"):
        service.capture_metadata(revision.source_revision_id)
    assert reader.calls == ["repository"]


def test_commit_metadata_requires_level_two(tmp_path) -> None:
    store, objects, source, revision, reader, clock, tracking = make_context(tmp_path)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.METADATA_ONLY,
        assigned_by="operator:test",
        reason="metadata only",
    )
    service = TrackingAwareGitHubCommitCaptureService(
        reader,
        store,
        objects,
        tracking=tracking,
    )

    with pytest.raises(TrackingNotAllowed):
        service.capture_commit(revision.source_revision_id)
    assert reader.calls == []

    clock.value = T0 + timedelta(hours=2)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.SHALLOW,
        assigned_by="operator:test",
        reason="capture commit metadata",
    )
    with pytest.raises(AssertionError, match="eligible commit capture"):
        service.capture_commit(revision.source_revision_id)
    assert reader.calls == ["commit"]


def test_root_tree_requires_level_three(tmp_path) -> None:
    store, objects, source, revision, reader, clock, tracking = make_context(tmp_path)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.SHALLOW,
        assigned_by="operator:test",
        reason="shallow only",
    )
    service = TrackingAwareGitHubRootTreeCaptureService(
        reader,
        store,
        objects,
        tracking=tracking,
    )

    with pytest.raises(TrackingNotAllowed):
        service.capture_root_tree(revision.source_revision_id)
    assert reader.calls == []

    clock.value = T0 + timedelta(hours=2)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="operator:test",
        reason="capture structure",
    )
    with pytest.raises(AssertionError, match="eligible tree capture"):
        service.capture_root_tree(revision.source_revision_id)
    assert reader.calls == ["tree"]


def test_workflow_runs_require_level_four(tmp_path) -> None:
    store, objects, source, revision, reader, clock, tracking = make_context(tmp_path)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="operator:test",
        reason="structural only",
    )
    service = TrackingAwareGitHubWorkflowCaptureService(
        reader,
        store,
        objects,
        tracking=tracking,
    )

    with pytest.raises(TrackingNotAllowed):
        service.capture_run(revision.source_revision_id, 123)
    assert reader.calls == []

    clock.value = T0 + timedelta(hours=2)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.DEEP,
        assigned_by="operator:test",
        reason="capture workflow evidence",
    )
    with pytest.raises(AssertionError, match="eligible workflow capture"):
        service.capture_run(revision.source_revision_id, 123)
    assert reader.calls == ["workflow"]
