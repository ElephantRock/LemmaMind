from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    DiscoveryChannel,
    DiscoveryChannelType,
    DiscoveryHit,
    DiscoveryResolution,
    DiscoveryRun,
    PipelineRun,
    RepositoryIdentity,
    RepositoryLocator,
    RunType,
    Source,
    SourceKind,
    SourceRole,
)
from lemmamind.repository_registry import (
    GitHubRepositoryRegistryService,
    RepositoryRegistryConflict,
    RepositoryRegistryError,
)
from lemmamind.storage import SQLiteContractStore

T0 = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)


class FakeReader:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get_repository(self, owner: str, repo: str):
        self.calls.append((owner, repo))
        return self.payloads[(owner, repo)]


def metadata(
    provider_id: int,
    owner: str,
    name: str,
    *,
    default_branch: str = "main",
    archived: bool = False,
    fork: bool = False,
    parent_id: int | None = None,
):
    payload = {
        "id": provider_id,
        "owner": {"login": owner},
        "name": name,
        "default_branch": default_branch,
        "archived": archived,
        "fork": fork,
    }
    if parent_id is not None:
        payload["parent"] = {"id": parent_id}
    return payload


def source(source_id: str, repository: str) -> Source:
    return Source(
        source_id=source_id,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.UNKNOWN,
        canonical_locator=f"https://github.com/{repository}",
        first_seen_at=T0,
        last_seen_at=T0,
    )


def seed_hit(
    store: SQLiteContractStore,
    hit_id: str,
    locator: str,
    *,
    observed_at: datetime = T0,
    source_id: str | None = None,
    discovery_pipeline_type: RunType = RunType.DISCOVERY,
) -> DiscoveryHit:
    channel_id = "discovery-channel:test"
    channel = store.get(DiscoveryChannel, channel_id)
    if channel is None:
        store.put(
            DiscoveryChannel(
                discovery_channel_id=channel_id,
                channel_type=DiscoveryChannelType.MANUAL_WATCHLIST,
                name="Registry test channel",
                canonical_locator="test://registry",
                created_at=T0,
            )
        )
    token = hit_id.replace(":", "-")
    pipeline = PipelineRun(
        run_id=f"run:discovery:{token}",
        run_type=discovery_pipeline_type,
        code_version="test",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="test.discovery.v1",
        started_at=observed_at,
        finished_at=observed_at,
        inputs_hash="sha256:" + "1" * 64,
        outputs_hash="sha256:" + "2" * 64,
    )
    run = DiscoveryRun(
        discovery_run_id=f"discovery-run:{token}",
        discovery_channel_id=channel_id,
        pipeline_run_id=pipeline.run_id,
        observed_at=observed_at,
        hit_count=1,
    )
    hit = DiscoveryHit(
        discovery_hit_id=hit_id,
        discovery_run_id=run.discovery_run_id,
        source_id=source_id,
        ordinal=1,
        discovered_locator=locator,
    )
    store.put_many((pipeline, run, hit))
    return hit


def test_unresolved_hit_creates_stable_source_identity_and_registry_provenance(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    hit = seed_hit(store, "hit:new", "example/repo")
    reader = FakeReader({("example", "repo"): metadata(42, "example", "repo")})
    resolved_at = T0 + timedelta(minutes=5)
    service = GitHubRepositoryRegistryService(
        reader,
        store,
        clock=lambda: resolved_at,
        id_factory=lambda: "registry-1",
    )

    result = service.resolve_hit(hit.discovery_hit_id)

    assert result.created is True
    assert result.source.source_id == "github:42"
    assert result.source.first_seen_at == T0
    assert result.source.last_seen_at == resolved_at
    assert result.repository_identity.provider_repository_id == "42"
    assert result.repository_identity.owner == "example"
    assert result.locator.canonical_locator == "https://github.com/example/repo"
    assert result.resolution.source_id == "github:42"
    assert result.pipeline_run.run_type is RunType.REGISTRY
    assert result.pipeline_run.outputs_hash is not None
    assert reader.calls == [("example", "repo")]

    assert store.get(DiscoveryHit, hit.discovery_hit_id).source_id is None
    assert store.get_untyped("RepositoryLocator", result.locator.repository_locator_id) == result.locator
    assert store.get_untyped(
        "DiscoveryResolution", result.resolution.discovery_resolution_id
    ) == result.resolution


def test_exact_reresolution_is_idempotent_but_same_hit_cannot_rewrite_state(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    hit = seed_hit(store, "hit:idempotent", "example/repo")
    payload = metadata(42, "example", "repo")
    first = GitHubRepositoryRegistryService(
        FakeReader({("example", "repo"): payload}),
        store,
        clock=lambda: T0 + timedelta(minutes=1),
        id_factory=lambda: "registry-1",
    ).resolve_hit(hit.discovery_hit_id)

    def should_not_allocate():
        raise AssertionError("idempotent resolution allocated a new registry run")

    second = GitHubRepositoryRegistryService(
        FakeReader({("example", "repo"): payload}),
        store,
        clock=lambda: T0 + timedelta(days=1),
        id_factory=should_not_allocate,
    ).resolve_hit(hit.discovery_hit_id)

    assert second.created is False
    assert second.resolution == first.resolution
    assert second.locator == first.locator
    assert second.pipeline_run == first.pipeline_run
    assert len(store.list(DiscoveryResolution)) == 1
    assert len(store.list(RepositoryLocator)) == 1
    assert len([run for run in store.list(PipelineRun) if run.run_type is RunType.REGISTRY]) == 1

    changed = metadata(42, "new-owner", "renamed", default_branch="trunk")
    with pytest.raises(RepositoryRegistryConflict, match="new discovery hit"):
        GitHubRepositoryRegistryService(
            FakeReader({}),
            store,
            clock=lambda: T0 + timedelta(days=2),
        ).resolve_hit_from_metadata(hit.discovery_hit_id, changed)


def test_new_hit_preserves_rename_transfer_branch_and_archive_evolution(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    old_hit = seed_hit(store, "hit:old", "old-owner/repo", observed_at=T0)
    new_hit = seed_hit(
        store,
        "hit:new-locator",
        "new-owner/renamed",
        observed_at=T0 + timedelta(days=1),
    )
    times = iter((T0 + timedelta(minutes=1), T0 + timedelta(days=1, minutes=1)))
    ids = iter(("registry-old", "registry-new"))
    service = GitHubRepositoryRegistryService(
        FakeReader({}),
        store,
        clock=lambda: next(times),
        id_factory=lambda: next(ids),
    )

    old = service.resolve_hit_from_metadata(
        old_hit.discovery_hit_id,
        metadata(42, "old-owner", "repo", default_branch="main", archived=False),
    )
    new = service.resolve_hit_from_metadata(
        new_hit.discovery_hit_id,
        metadata(42, "new-owner", "renamed", default_branch="trunk", archived=True),
    )

    assert old.source.source_id == new.source.source_id == "github:42"
    assert old.repository_identity == new.repository_identity
    assert new.repository_identity.owner == "old-owner"
    assert new.repository_identity.name == "repo"
    assert new.repository_identity.default_branch == "main"
    assert new.repository_identity.archived is False

    assert old.locator.owner == "old-owner"
    assert old.locator.name == "repo"
    assert old.locator.default_branch == "main"
    assert old.locator.archived is False
    assert new.locator.owner == "new-owner"
    assert new.locator.name == "renamed"
    assert new.locator.default_branch == "trunk"
    assert new.locator.archived is True
    assert service.latest_locator("github:42") == new.locator

    assert store.get(DiscoveryHit, old_hit.discovery_hit_id) == old_hit
    assert store.get(DiscoveryResolution, old.resolution.discovery_resolution_id) == old.resolution
    assert len(store.list(RepositoryIdentity)) == 1
    assert len(store.list(RepositoryLocator)) == 2
    assert len(store.list(DiscoveryResolution)) == 2


def test_known_source_is_reused_and_becomes_provider_id_anchor(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    known = source("source:known", "legacy/repo")
    store.put(known)
    linked_hit = seed_hit(
        store,
        "hit:linked",
        "legacy/repo",
        source_id=known.source_id,
    )
    unresolved_hit = seed_hit(
        store,
        "hit:later",
        "current/repo",
        observed_at=T0 + timedelta(hours=1),
    )
    times = iter((T0 + timedelta(minutes=1), T0 + timedelta(hours=1, minutes=1)))
    ids = iter(("registry-1", "registry-2"))
    service = GitHubRepositoryRegistryService(
        FakeReader({}),
        store,
        clock=lambda: next(times),
        id_factory=lambda: next(ids),
    )

    first = service.resolve_hit_from_metadata(
        linked_hit.discovery_hit_id,
        metadata(42, "current", "repo"),
    )
    second = service.resolve_hit_from_metadata(
        unresolved_hit.discovery_hit_id,
        metadata(42, "current", "repo"),
    )

    assert first.source == known
    assert first.repository_identity.source_id == known.source_id
    assert first.repository_identity.provider_repository_id == "42"
    assert first.repository_identity.aliases == ("legacy/repo",)
    assert second.source == known
    assert second.resolution.source_id == known.source_id
    assert store.get(Source, "github:42") is None


def test_provider_id_mapping_conflict_is_rejected(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source_a = source("source:a", "a/repo")
    source_b = source("source:b", "b/repo")
    store.put_many(
        (
            source_a,
            source_b,
            RepositoryIdentity(
                source_id=source_a.source_id,
                provider_repository_id="42",
                owner="a",
                name="repo",
                default_branch="main",
            ),
        )
    )
    hit = seed_hit(store, "hit:conflict", "b/repo", source_id=source_b.source_id)

    with pytest.raises(RepositoryRegistryConflict, match="provider repository ID mapping"):
        GitHubRepositoryRegistryService(
            FakeReader({}),
            store,
            clock=lambda: T0 + timedelta(minutes=1),
        ).resolve_hit_from_metadata(hit.discovery_hit_id, metadata(42, "b", "repo"))

    assert store.list(DiscoveryResolution) == []
    assert store.list(RepositoryLocator) == []


def test_fork_is_distinct_identity_with_parent_provider_relation(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    parent_hit = seed_hit(store, "hit:parent", "upstream/repo")
    fork_hit = seed_hit(
        store,
        "hit:fork",
        "contributor/repo",
        observed_at=T0 + timedelta(minutes=10),
    )
    times = iter((T0 + timedelta(minutes=1), T0 + timedelta(minutes=11)))
    ids = iter(("registry-parent", "registry-fork"))
    service = GitHubRepositoryRegistryService(
        FakeReader({}),
        store,
        clock=lambda: next(times),
        id_factory=lambda: next(ids),
    )

    parent = service.resolve_hit_from_metadata(
        parent_hit.discovery_hit_id,
        metadata(42, "upstream", "repo"),
    )
    fork = service.resolve_hit_from_metadata(
        fork_hit.discovery_hit_id,
        metadata(84, "contributor", "repo", fork=True, parent_id=42),
    )

    assert parent.source.source_id == "github:42"
    assert fork.source.source_id == "github:84"
    assert fork.source != parent.source
    assert fork.locator.fork is True
    assert fork.locator.parent_provider_repository_id == "42"
    assert fork.repository_identity.provider_repository_id == "84"


def test_resolution_requires_complete_m1_lineage(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    orphan = DiscoveryHit(
        discovery_hit_id="hit:orphan",
        discovery_run_id="discovery-run:missing",
        ordinal=1,
        discovered_locator="example/repo",
    )
    store.put(orphan)

    with pytest.raises(RepositoryRegistryError, match="missing DiscoveryRun"):
        GitHubRepositoryRegistryService(
            FakeReader({}), store, clock=lambda: T0
        ).resolve_hit_from_metadata(orphan.discovery_hit_id, metadata(42, "example", "repo"))

    bad_pipeline_hit = seed_hit(
        store,
        "hit:wrong-run-type",
        "example/repo",
        discovery_pipeline_type=RunType.CAPTURE,
    )
    with pytest.raises(RepositoryRegistryError, match="run_type=discovery"):
        GitHubRepositoryRegistryService(
            FakeReader({}), store, clock=lambda: T0
        ).resolve_hit_from_metadata(
            bad_pipeline_hit.discovery_hit_id,
            metadata(42, "example", "repo"),
        )


def test_invalid_locator_or_metadata_fails_without_registry_writes(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    hit = seed_hit(store, "hit:bad", "https://example.com/not/github")
    service = GitHubRepositoryRegistryService(FakeReader({}), store, clock=lambda: T0)

    with pytest.raises(RepositoryRegistryError, match="not a GitHub repository"):
        service.resolve_hit(hit.discovery_hit_id)

    with pytest.raises(RepositoryRegistryError, match="omitted stable identity fields"):
        service.resolve_hit_from_metadata(hit.discovery_hit_id, {"id": 42})

    assert store.list(RepositoryLocator) == []
    assert store.list(DiscoveryResolution) == []
