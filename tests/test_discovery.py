from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    DiscoveryChannel,
    DiscoveryChannelType,
    DiscoveryHit,
    DiscoveryRun,
    PipelineRun,
    RunType,
    Source,
    SourceKind,
    SourceRole,
)
from lemmamind.discovery import DiscoveryCandidate, DiscoveryError, DiscoveryService
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 17, 30, tzinfo=timezone.utc)


def source(source_id: str, repository: str) -> Source:
    return Source(
        source_id=source_id,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.UNKNOWN,
        canonical_locator=f"https://github.com/{repository}",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def channel() -> DiscoveryChannel:
    return DiscoveryChannel(
        discovery_channel_id="discovery-channel:manual:pilot",
        channel_type=DiscoveryChannelType.MANUAL_WATCHLIST,
        name="Pilot watchlist",
        canonical_locator="pilot/watchlist.yaml",
        created_at=NOW,
    )


def service(store):
    ids = iter(("discovery-1", "pipeline-1", "discovery-2", "pipeline-2"))
    return DiscoveryService(store, clock=lambda: NOW, id_factory=lambda: next(ids))


def test_records_typed_discovery_lineage_in_channel_order(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put_many(
        (
            source("source:one", "example/one"),
            source("source:two", "example/two"),
        )
    )
    result = service(store).record_run(
        channel=channel(),
        candidates=(
            DiscoveryCandidate("source:two", "example/two"),
            DiscoveryCandidate("source:one", "example/one"),
        ),
        input_snapshot={"content_sha256": "sha256:" + "a" * 64},
    )

    assert result.discovery_run.hit_count == 2
    assert result.pipeline_run.run_type is RunType.DISCOVERY
    assert result.pipeline_run.finished_at == NOW
    assert result.pipeline_run.outputs_hash is not None
    assert [(hit.ordinal, hit.source_id) for hit in result.hits] == [
        (1, "source:two"),
        (2, "source:one"),
    ]
    assert store.get(DiscoveryChannel, result.channel.discovery_channel_id) == result.channel
    assert store.get(DiscoveryRun, result.discovery_run.discovery_run_id) == result.discovery_run
    assert store.get(PipelineRun, result.pipeline_run.run_id) == result.pipeline_run
    assert store.get_untyped("DiscoveryHit", result.hits[0].discovery_hit_id) == result.hits[0]


def test_zero_hit_discovery_run_is_valid(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    result = service(store).record_run(
        channel=channel(),
        candidates=(),
        input_snapshot={"query": "topic:example", "result_count": 0},
    )

    assert result.discovery_run.hit_count == 0
    assert result.hits == ()
    assert store.list(DiscoveryHit) == []


def test_unknown_source_is_rejected_at_m1_m2_boundary(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    with pytest.raises(DiscoveryError, match="already-resolved Source"):
        service(store).record_run(
            channel=channel(),
            candidates=(DiscoveryCandidate("source:missing", "example/missing"),),
            input_snapshot={},
        )

    assert store.list(DiscoveryRun) == []
    assert store.list(PipelineRun) == []


def test_duplicate_source_cannot_inflate_one_discovery_run(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put(source("source:one", "example/one"))

    with pytest.raises(DiscoveryError, match="duplicate Source"):
        service(store).record_run(
            channel=channel(),
            candidates=(
                DiscoveryCandidate("source:one", "example/one"),
                DiscoveryCandidate("source:one", "renamed/one"),
            ),
            input_snapshot={},
        )


def test_non_json_input_snapshot_fails_before_persistence(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put(source("source:one", "example/one"))

    with pytest.raises(DiscoveryError, match="canonical JSON"):
        service(store).record_run(
            channel=channel(),
            candidates=(DiscoveryCandidate("source:one", "example/one"),),
            input_snapshot={"bad": object()},
        )

    assert store.list(DiscoveryRun) == []
