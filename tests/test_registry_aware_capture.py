from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    DiscoveryChannel,
    DiscoveryChannelType,
    DiscoveryHit,
    DiscoveryRun,
    PipelineRun,
    RunType,
)
from lemmamind.github import (
    GitHubCaptureService,
    RepositoryIdentityDrift,
    SourceMetadataDrift,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.registry_aware_capture import RegistryAwareGitHubCaptureService
from lemmamind.repository_registry import GitHubRepositoryRegistryService
from lemmamind.storage import SQLiteContractStore

COMMIT_SHA = "c" * 40
TREE_SHA = "d" * 40
T0 = datetime(2026, 8, 25, 20, 0, tzinfo=timezone.utc)


class MutableReader:
    def __init__(self):
        self.metadata = {
            "id": 42,
            "owner": {"login": "Acme"},
            "name": "Repo",
            "default_branch": "main",
            "archived": False,
            "fork": False,
        }
        self.commit_refs = []
        self.file_calls = []

    def get_repository(self, owner: str, repo: str):
        return self.metadata

    def get_commit(self, owner: str, repo: str, ref: str):
        self.commit_refs.append((owner, repo, ref))
        return {"sha": COMMIT_SHA, "commit": {"tree": {"sha": TREE_SHA}}}

    def get_file(self, owner: str, repo: str, path: str, ref: str):
        self.file_calls.append((owner, repo, path, ref))
        return b"# registry-aware\n"


class Clock:
    def __init__(self, start):
        self.value = start

    def __call__(self):
        value = self.value
        self.value += timedelta(seconds=1)
        return value


def seed_discovery_hit(store, hit_id: str, locator: str, observed_at: datetime, source_id: str):
    channel_id = "discovery-channel:registry-aware-capture"
    if store.get(DiscoveryChannel, channel_id) is None:
        store.put(
            DiscoveryChannel(
                discovery_channel_id=channel_id,
                channel_type=DiscoveryChannelType.MANUAL_WATCHLIST,
                name="Registry-aware capture test",
                canonical_locator="test://registry-aware-capture",
                created_at=T0,
            )
        )
    token = hit_id.replace(":", "-")
    discovery_pipeline = PipelineRun(
        run_id=f"run:discovery:{token}",
        run_type=RunType.DISCOVERY,
        code_version="test",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="test.discovery.v1",
        started_at=observed_at,
        finished_at=observed_at,
        inputs_hash="sha256:" + "4" * 64,
        outputs_hash="sha256:" + "5" * 64,
    )
    discovery_run = DiscoveryRun(
        discovery_run_id=f"discovery-run:{token}",
        discovery_channel_id=channel_id,
        pipeline_run_id=discovery_pipeline.run_id,
        observed_at=observed_at,
        hit_count=1,
    )
    hit = DiscoveryHit(
        discovery_hit_id=hit_id,
        discovery_run_id=discovery_run.discovery_run_id,
        source_id=source_id,
        ordinal=1,
        discovered_locator=locator,
    )
    store.put_many((discovery_pipeline, discovery_run, hit))
    return hit


def make_services(tmp_path):
    reader = MutableReader()
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    base = GitHubCaptureService(
        reader,
        store,
        objects,
        clock=Clock(T0),
        id_factory=iter(("base-capture", "base-run")).__next__,
    )
    return reader, store, objects, base


def test_registry_history_allows_capture_after_rename_and_branch_archive_drift(tmp_path) -> None:
    reader, store, objects, base = make_services(tmp_path)
    first = base.capture_repository("Acme/Repo", ["README.md"])

    reader.metadata = {
        **reader.metadata,
        "owner": {"login": "NewAcme"},
        "name": "RenamedRepo",
        "default_branch": "trunk",
        "archived": True,
    }

    with pytest.raises((SourceMetadataDrift, RepositoryIdentityDrift)):
        base.capture_repository("NewAcme/RenamedRepo", ["README.md"])

    hit = seed_discovery_hit(
        store,
        "hit:renamed",
        "NewAcme/RenamedRepo",
        T0 + timedelta(hours=1),
        first.source.source_id,
    )
    registry = GitHubRepositoryRegistryService(
        reader,
        store,
        clock=lambda: T0 + timedelta(hours=1, minutes=1),
        id_factory=lambda: "registry-run",
    )
    resolution = registry.resolve_hit(hit.discovery_hit_id)

    capture = RegistryAwareGitHubCaptureService(
        reader,
        store,
        objects,
        clock=Clock(T0 + timedelta(hours=2)),
        id_factory=iter(("capture-2", "run-2")).__next__,
    )
    second = capture.capture_repository("NewAcme/RenamedRepo", ["README.md"])

    assert second.source == first.source
    assert second.repository == first.repository
    assert resolution.locator.owner == "NewAcme"
    assert resolution.locator.name == "RenamedRepo"
    assert resolution.locator.default_branch == "trunk"
    assert resolution.locator.archived is True
    assert reader.commit_refs[-1] == ("NewAcme", "RenamedRepo", "trunk")
    assert reader.file_calls[-1][:3] == ("NewAcme", "RenamedRepo", "README.md")


def test_only_latest_registry_locator_can_authorize_capture_state(tmp_path) -> None:
    reader, store, objects, base = make_services(tmp_path)
    first = base.capture_repository("Acme/Repo", ["README.md"])

    old_hit = seed_discovery_hit(
        store,
        "hit:old-state",
        "Acme/Repo",
        T0 + timedelta(hours=1),
        first.source.source_id,
    )
    GitHubRepositoryRegistryService(
        reader,
        store,
        clock=lambda: T0 + timedelta(hours=1, minutes=1),
        id_factory=lambda: "registry-old",
    ).resolve_hit(old_hit.discovery_hit_id)

    reader.metadata = {
        **reader.metadata,
        "owner": {"login": "NewAcme"},
        "name": "RenamedRepo",
        "default_branch": "trunk",
    }
    new_hit = seed_discovery_hit(
        store,
        "hit:new-state",
        "NewAcme/RenamedRepo",
        T0 + timedelta(hours=2),
        first.source.source_id,
    )
    GitHubRepositoryRegistryService(
        reader,
        store,
        clock=lambda: T0 + timedelta(hours=2, minutes=1),
        id_factory=lambda: "registry-new",
    ).resolve_hit(new_hit.discovery_hit_id)

    reader.metadata = {
        **reader.metadata,
        "owner": {"login": "Acme"},
        "name": "Repo",
        "default_branch": "main",
    }
    capture = RegistryAwareGitHubCaptureService(
        reader,
        store,
        objects,
        clock=Clock(T0 + timedelta(hours=3)),
        id_factory=iter(("capture-3", "run-3")).__next__,
    )

    with pytest.raises((SourceMetadataDrift, RepositoryIdentityDrift)):
        capture.capture_repository("Acme/Repo", ["README.md"])
