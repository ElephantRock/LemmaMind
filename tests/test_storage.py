from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import RepositoryIdentity, Source, SourceKind, SourceRole
from lemmamind.storage import RecordConflict, SQLiteContractStore

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def make_source(*, last_seen_at=NOW) -> Source:
    return Source(
        source_id="source:github:example/repo",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/example/repo",
        first_seen_at=NOW,
        last_seen_at=last_seen_at,
    )


def test_store_round_trip_is_typed_and_idempotent(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = make_source()

    assert store.put(source) is True
    assert store.put(source) is False
    assert store.get(Source, source.source_id) == source
    assert store.list(Source) == [source]


def test_store_rejects_identity_reuse_with_different_payload(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = make_source()
    changed = make_source(last_seen_at=NOW + timedelta(days=1))

    store.put(source)
    with pytest.raises(RecordConflict):
        store.put(changed)


def test_put_many_rolls_back_the_whole_batch_on_conflict(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = make_source()
    changed = make_source(last_seen_at=NOW + timedelta(days=1))
    repository = RepositoryIdentity(
        source_id=source.source_id,
        provider_repository_id="42",
        owner="example",
        name="repo",
        default_branch="main",
    )

    store.put(source)
    with pytest.raises(RecordConflict):
        store.put_many([repository, changed])

    assert store.get(RepositoryIdentity, repository.source_id) is None
