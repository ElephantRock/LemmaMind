"""Minimal append-only SQLite persistence for M0 contract records."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, TypeVar

from .contracts import CONTRACT_TYPES, ContractModel

TContract = TypeVar("TContract", bound=ContractModel)


class RecordConflict(RuntimeError):
    """Raised when an immutable contract identity is reused with different content."""


class _SQLiteContractTransaction:
    """Connection-bound store view used inside one SQLite write transaction."""

    def __init__(self, store: "SQLiteContractStore", connection: sqlite3.Connection):
        self._store = store
        self._connection = connection

    def put_many(self, records: Iterable[ContractModel]) -> int:
        pending = tuple(records)
        inserted = 0
        for record in pending:
            inserted += int(self._store._put_on_connection(self._connection, record))
        return inserted

    def get(self, model: type[TContract], record_id: str) -> TContract | None:
        return self._store._get_on_connection(self._connection, model, record_id)

    def list(self, model: type[TContract]) -> list[TContract]:
        return self._store._list_on_connection(self._connection, model)


class SQLiteContractStore:
    """Typed append-only record store.

    M0 deliberately persists validated contracts as canonical JSON rather than
    committing to one relational table per domain object. Identity, type, schema
    version, and payload digest remain queryable while the ontology is still
    intentionally small and evolving.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS contract_records (
                    contract_type TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    stored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (contract_type, record_id)
                );

                CREATE INDEX IF NOT EXISTS idx_contract_records_type
                ON contract_records(contract_type);
                """
            )

    @staticmethod
    def _canonical_payload(record: ContractModel) -> tuple[str, str]:
        payload = record.model_dump(mode="json", by_alias=True)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return encoded, digest

    def _put_on_connection(self, connection: sqlite3.Connection, record: ContractModel) -> bool:
        payload_json, payload_sha256 = self._canonical_payload(record)
        contract_type = type(record).__name__

        existing = connection.execute(
            """
            SELECT payload_sha256
            FROM contract_records
            WHERE contract_type = ? AND record_id = ?
            """,
            (contract_type, record.record_id),
        ).fetchone()

        if existing is not None:
            if existing["payload_sha256"] == payload_sha256:
                return False
            raise RecordConflict(
                f"{contract_type}:{record.record_id} already exists with different content"
            )

        connection.execute(
            """
            INSERT INTO contract_records (
                contract_type,
                record_id,
                schema_version,
                payload_json,
                payload_sha256
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                contract_type,
                record.record_id,
                record.schema_version,
                payload_json,
                payload_sha256,
            ),
        )
        return True

    @staticmethod
    def _get_on_connection(
        connection: sqlite3.Connection,
        model: type[TContract],
        record_id: str,
    ) -> TContract | None:
        row = connection.execute(
            """
            SELECT payload_json
            FROM contract_records
            WHERE contract_type = ? AND record_id = ?
            """,
            (model.__name__, record_id),
        ).fetchone()
        if row is None:
            return None
        return model.model_validate_json(row["payload_json"])

    @staticmethod
    def _list_on_connection(
        connection: sqlite3.Connection,
        model: type[TContract],
    ) -> list[TContract]:
        rows = connection.execute(
            """
            SELECT payload_json
            FROM contract_records
            WHERE contract_type = ?
            ORDER BY record_id
            """,
            (model.__name__,),
        ).fetchall()
        return [model.model_validate_json(row["payload_json"]) for row in rows]

    def put(self, record: ContractModel) -> bool:
        """Persist one record.

        Returns True for a new insert, False for an idempotent re-insert, and
        raises RecordConflict if the same typed identity has different content.
        """

        with self._connect() as connection:
            return self._put_on_connection(connection, record)

    def put_many(self, records: Iterable[ContractModel]) -> int:
        """Persist a batch atomically.

        Any identity conflict rolls back the whole batch. This matters for capture
        envelopes: Source/Revision/Artifact/Manifest/Run records must not be left
        partially committed when one immutable identity disagrees with storage.
        """

        pending = tuple(records)
        with self._connect() as connection:
            inserted = 0
            for record in pending:
                inserted += int(self._put_on_connection(connection, record))
            return inserted

    @contextmanager
    def transaction(self) -> Iterator[_SQLiteContractTransaction]:
        """Hold one immediate write transaction across validation and persistence.

        The yielded view performs reads and writes on the same connection. An
        immediate transaction prevents another writer from committing after a
        final validation read but before the corresponding append-only records
        are persisted.
        """

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield _SQLiteContractTransaction(self, connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self, model: type[TContract], record_id: str) -> TContract | None:
        with self._connect() as connection:
            return self._get_on_connection(connection, model, record_id)

    def list(self, model: type[TContract]) -> list[TContract]:
        with self._connect() as connection:
            return self._list_on_connection(connection, model)

    def get_untyped(self, contract_type: str, record_id: str) -> ContractModel | None:
        model = CONTRACT_TYPES.get(contract_type)
        if model is None:
            raise KeyError(f"unknown contract type: {contract_type}")
        return self.get(model, record_id)
