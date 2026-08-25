from datetime import datetime, timezone
from pathlib import Path

import pytest

from lemmamind.contracts import (
    DiscoveryChannel,
    DiscoveryChannelType,
    DiscoveryHit,
    DiscoveryRun,
    Source,
    SourceKind,
    SourceRole,
)
from lemmamind.discovery import DiscoveryService
from lemmamind.manual_watchlist import (
    ManualWatchlistDiscoveryAdapter,
    ManualWatchlistError,
    load_manual_watchlist,
)
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 17, 45, tzinfo=timezone.utc)
WATCHLIST = Path("pilot/watchlist.yaml")


def test_frozen_watchlist_contains_thirteen_ordered_repositories() -> None:
    watchlist = load_manual_watchlist(WATCHLIST)

    assert len(watchlist.entries) == 13
    assert watchlist.entries[0].repository == "ElephantRock/ExpertOS"
    assert watchlist.entries[-1].repository == "NousResearch/hermes-agent"
    assert watchlist.pilot_id == "m-1-technical-intelligence"
    assert watchlist.content_sha256.startswith("sha256:")


def test_watchlist_adapter_records_all_resolved_sources_in_order(tmp_path) -> None:
    watchlist = load_manual_watchlist(WATCHLIST)
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    mapping = {}
    for index, entry in enumerate(watchlist.entries, start=1):
        source_id = f"source:{index:02d}"
        mapping[entry.repository] = source_id
        store.put(
            Source(
                source_id=source_id,
                source_kind=SourceKind.GITHUB_REPOSITORY,
                source_role=SourceRole.UNKNOWN,
                canonical_locator=f"https://github.com/{entry.repository}",
                first_seen_at=NOW,
                last_seen_at=NOW,
            )
        )

    ids = iter(("watchlist-run", "pipeline-run"))
    service = DiscoveryService(
        store,
        clock=lambda: NOW,
        id_factory=lambda: next(ids),
    )
    channel = DiscoveryChannel(
        discovery_channel_id="discovery-channel:manual-watchlist:pilot",
        channel_type=DiscoveryChannelType.MANUAL_WATCHLIST,
        name="M-1 curated watchlist",
        canonical_locator="pilot/watchlist.yaml",
        created_at=NOW,
    )
    result = ManualWatchlistDiscoveryAdapter(service).record(
        path=WATCHLIST,
        channel=channel,
        source_id_by_repository=mapping,
    )

    assert result.discovery_run.hit_count == 13
    assert [hit.discovered_locator for hit in result.hits] == [
        entry.repository for entry in watchlist.entries
    ]
    assert [hit.ordinal for hit in result.hits] == list(range(1, 14))
    assert all(store.get(Source, hit.source_id) is not None for hit in result.hits)
    assert store.get(DiscoveryRun, result.discovery_run.discovery_run_id) == result.discovery_run
    assert len(store.list(DiscoveryHit)) == 13


def test_watchlist_adapter_fails_if_any_repository_lacks_source_mapping(tmp_path) -> None:
    watchlist = load_manual_watchlist(WATCHLIST)
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    mapping = {}
    for index, entry in enumerate(watchlist.entries[:-1], start=1):
        source_id = f"source:{index:02d}"
        mapping[entry.repository] = source_id
        store.put(
            Source(
                source_id=source_id,
                source_kind=SourceKind.GITHUB_REPOSITORY,
                source_role=SourceRole.UNKNOWN,
                canonical_locator=f"https://github.com/{entry.repository}",
                first_seen_at=NOW,
                last_seen_at=NOW,
            )
        )
    channel = DiscoveryChannel(
        discovery_channel_id="discovery-channel:manual-watchlist:pilot",
        channel_type=DiscoveryChannelType.MANUAL_WATCHLIST,
        name="M-1 curated watchlist",
        canonical_locator="pilot/watchlist.yaml",
        created_at=NOW,
    )

    with pytest.raises(ManualWatchlistError, match="no resolved Source mapping"):
        ManualWatchlistDiscoveryAdapter(
            DiscoveryService(store, clock=lambda: NOW)
        ).record(
            path=WATCHLIST,
            channel=channel,
            source_id_by_repository=mapping,
        )


def test_watchlist_rejects_duplicate_repository_entries(tmp_path) -> None:
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """version: 1
repositories:
  - repository: example/one
  - repository: example/one
""",
        encoding="utf-8",
    )

    with pytest.raises(ManualWatchlistError, match="duplicate repository"):
        load_manual_watchlist(path)
