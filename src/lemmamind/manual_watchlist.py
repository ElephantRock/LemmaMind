"""Manual-watchlist adapter for M1 curated discovery."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

from .contracts import DiscoveryChannel, DiscoveryChannelType
from .discovery import DiscoveryCandidate, DiscoveryError, DiscoveryResult, DiscoveryService


@dataclass(frozen=True)
class ManualWatchlistEntry:
    repository: str
    revision: str | None


@dataclass(frozen=True)
class ManualWatchlist:
    path: str
    content_sha256: str
    version: object
    pilot_id: str | None
    entries: tuple[ManualWatchlistEntry, ...]


class ManualWatchlistError(DiscoveryError):
    """The configured watchlist cannot produce trustworthy discovery lineage."""


def load_manual_watchlist(path: str | Path) -> ManualWatchlist:
    source_path = Path(path)
    raw = source_path.read_bytes()
    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ManualWatchlistError(f"invalid watchlist YAML: {source_path}") from exc
    if not isinstance(document, Mapping):
        raise ManualWatchlistError("watchlist root must be a mapping")
    repositories = document.get("repositories")
    if not isinstance(repositories, list):
        raise ManualWatchlistError("watchlist repositories must be a list")

    entries: list[ManualWatchlistEntry] = []
    seen: set[str] = set()
    for index, item in enumerate(repositories, start=1):
        if not isinstance(item, Mapping):
            raise ManualWatchlistError(f"watchlist repository #{index} must be a mapping")
        repository = item.get("repository")
        if not isinstance(repository, str) or not repository.strip():
            raise ManualWatchlistError(f"watchlist repository #{index} omitted repository")
        repository = repository.strip()
        parts = repository.split("/")
        if len(parts) != 2 or not all(parts):
            raise ManualWatchlistError(
                f"watchlist repository must be owner/name: {repository!r}"
            )
        if repository in seen:
            raise ManualWatchlistError(f"duplicate repository in watchlist: {repository}")
        seen.add(repository)
        revision = item.get("revision")
        if revision is not None and (not isinstance(revision, str) or not revision.strip()):
            raise ManualWatchlistError(
                f"watchlist revision for {repository} must be a non-empty string or null"
            )
        entries.append(
            ManualWatchlistEntry(
                repository=repository,
                revision=revision.strip() if isinstance(revision, str) else None,
            )
        )

    pilot_id = document.get("pilot_id")
    if pilot_id is not None and not isinstance(pilot_id, str):
        raise ManualWatchlistError("watchlist pilot_id must be a string when present")
    return ManualWatchlist(
        path=source_path.as_posix(),
        content_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
        version=document.get("version"),
        pilot_id=pilot_id.strip() if isinstance(pilot_id, str) else None,
        entries=tuple(entries),
    )


class ManualWatchlistDiscoveryAdapter:
    """Record one manual watchlist generation with optional M2 Source links."""

    def __init__(self, service: DiscoveryService) -> None:
        self.service = service

    def record(
        self,
        *,
        path: str | Path,
        channel: DiscoveryChannel,
        source_id_by_repository: Mapping[str, str] | None = None,
    ) -> DiscoveryResult:
        if channel.channel_type is not DiscoveryChannelType.MANUAL_WATCHLIST:
            raise ManualWatchlistError(
                "manual watchlist adapter requires channel_type=manual_watchlist"
            )
        watchlist = load_manual_watchlist(path)
        if channel.canonical_locator != watchlist.path:
            raise ManualWatchlistError(
                "DiscoveryChannel canonical_locator must match the watchlist path: "
                f"{channel.canonical_locator!r} != {watchlist.path!r}"
            )

        mapping = source_id_by_repository or {}
        candidates: list[DiscoveryCandidate] = []
        for entry in watchlist.entries:
            source_id = mapping.get(entry.repository)
            if source_id is not None:
                if not isinstance(source_id, str) or not source_id.strip():
                    raise ManualWatchlistError(
                        f"invalid Source mapping for watchlist repository: {entry.repository}"
                    )
                source_id = source_id.strip()
            candidates.append(
                DiscoveryCandidate(
                    discovered_locator=entry.repository,
                    source_id=source_id,
                )
            )

        return self.service.record_run(
            channel=channel,
            candidates=tuple(candidates),
            input_snapshot={
                "adapter": "manual-watchlist.v1",
                "path": watchlist.path,
                "content_sha256": watchlist.content_sha256,
                "watchlist_version": watchlist.version,
                "pilot_id": watchlist.pilot_id,
                "repository_count": len(watchlist.entries),
            },
        )
