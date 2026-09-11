import sqlite3
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


def test_transaction_holds_writer_lock_and_uses_one_connection(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = make_source()
    competing = sqlite3.connect(store.path, timeout=0)
    try:
        competing.execute("PRAGMA journal_mode=WAL")
        with store.transaction() as transaction:
            assert transaction.put_many([source]) == 1
            assert transaction.get(Source, source.source_id) == source
            assert transaction.list(Source) == [source]
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                competing.execute("BEGIN IMMEDIATE")
    finally:
        competing.close()

    assert store.get(Source, source.source_id) == source


def test_transaction_rolls_back_when_validation_or_persistence_fails(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = make_source()

    with pytest.raises(RuntimeError, match="validation failed"):
        with store.transaction() as transaction:
            transaction.put_many([source])
            raise RuntimeError("validation failed")

    assert store.get(Source, source.source_id) is None
