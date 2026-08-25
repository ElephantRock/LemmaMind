"""M2 repository registry resolution and immutable locator history.

M1 records raw discovery hits. M2 resolves those hits to stable GitHub repository
Sources using GitHub's provider repository ID while preserving mutable owner/name,
default-branch, archive, and fork state as append-only RepositoryLocator records.
Historical DiscoveryHit records are never rewritten.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    DiscoveryHit,
    DiscoveryResolution,
    DiscoveryRun,
    PipelineRun,
    RepositoryIdentity,
    RepositoryLocator,
    RepositoryResolutionMethod,
    RunType,
    Source,
    SourceKind,
    SourceRole,
)


class RepositoryRegistryError(RuntimeError):
    """Repository identity or resolution state violates the M2 registry boundary."""


class RepositoryRegistryConflict(RepositoryRegistryError):
    """Existing immutable registry history conflicts with an attempted resolution."""


class RepositoryReader(Protocol):
    def get_repository(self, owner: str, repo: str) -> Mapping[str, Any]: ...


class RegistryStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class RepositorySnapshot:
    provider_repository_id: str
    owner: str
    name: str
    canonical_locator: str
    default_branch: str
    archived: bool
    fork: bool
    parent_provider_repository_id: str | None

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class RepositoryResolutionResult:
    source: Source
    repository_identity: RepositoryIdentity
    locator: RepositoryLocator
    resolution: DiscoveryResolution
    pipeline_run: PipelineRun
    created: bool

    def records(self) -> tuple:
        return (
            self.source,
            self.repository_identity,
            self.locator,
            self.resolution,
            self.pipeline_run,
        )


class GitHubRepositoryRegistryService:
    """Resolve DiscoveryHits through stable GitHub provider repository identity."""

    def __init__(
        self,
        reader: RepositoryReader,
        store: RegistryStore,
        *,
        resolver_version: str = "github-repository-registry.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.reader = reader
        self.store = store
        self.resolver_version = resolver_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def resolve_hit(self, discovery_hit_id: str) -> RepositoryResolutionResult:
        hit = self._require_hit(discovery_hit_id)
        owner, repo = self._split_github_locator(hit.discovered_locator)
        metadata = self.reader.get_repository(owner, repo)
        return self.resolve_hit_from_metadata(discovery_hit_id, metadata)

    def resolve_hit_from_metadata(
        self,
        discovery_hit_id: str,
        metadata: Mapping[str, Any],
    ) -> RepositoryResolutionResult:
        hit = self._require_hit(discovery_hit_id)
        snapshot = self._snapshot(metadata)
        existing = self._existing_resolution(hit, snapshot)
        if existing is not None:
            return existing

        discovery_run = self.store.get(DiscoveryRun, hit.discovery_run_id)
        if discovery_run is None:
            raise RepositoryRegistryError(
                f"DiscoveryHit references missing DiscoveryRun: {hit.discovery_run_id}"
            )

        resolved_at = self._aware_now()
        if resolved_at < discovery_run.observed_at:
            raise RepositoryRegistryError(
                "registry resolution time must not precede the discovery run"
            )

        source, identity, new_source, new_identity = self._resolve_identity(
            hit,
            snapshot,
            first_seen_at=discovery_run.observed_at,
            resolved_at=resolved_at,
        )

        pipeline_run_id = f"run:{self.id_factory()}"
        locator = RepositoryLocator(
            repository_locator_id=self._locator_id(hit.discovery_hit_id),
            source_id=source.source_id,
            provider_repository_id=snapshot.provider_repository_id,
            owner=snapshot.owner,
            name=snapshot.name,
            canonical_locator=snapshot.canonical_locator,
            default_branch=snapshot.default_branch,
            archived=snapshot.archived,
            fork=snapshot.fork,
            parent_provider_repository_id=snapshot.parent_provider_repository_id,
            observed_at=resolved_at,
            pipeline_run_id=pipeline_run_id,
        )
        resolution = DiscoveryResolution(
            discovery_resolution_id=self._resolution_id(hit.discovery_hit_id),
            discovery_hit_id=hit.discovery_hit_id,
            source_id=source.source_id,
            repository_locator_id=locator.repository_locator_id,
            resolution_method=RepositoryResolutionMethod.GITHUB_PROVIDER_REPOSITORY_ID,
            resolver_version=self.resolver_version,
            resolved_at=resolved_at,
            pipeline_run_id=pipeline_run_id,
        )
        inputs_hash = self._digest_json(
            {
                "discovery_hit": hit.model_dump(mode="json", by_alias=True),
                "repository_snapshot": snapshot.__dict__,
                "resolver_version": self.resolver_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "source": source.model_dump(mode="json", by_alias=True),
                "repository_identity": identity.model_dump(mode="json", by_alias=True),
                "repository_locator": locator.model_dump(mode="json", by_alias=True),
                "discovery_resolution": resolution.model_dump(mode="json", by_alias=True),
            }
        )
        pipeline_run = PipelineRun(
            run_id=pipeline_run_id,
            run_type=RunType.REGISTRY,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.resolver_version,
            started_at=resolved_at,
            finished_at=resolved_at,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )

        records = []
        if new_source:
            records.append(source)
        if new_identity:
            records.append(identity)
        records.extend((locator, resolution, pipeline_run))
        self.store.put_many(tuple(records))
        return RepositoryResolutionResult(
            source=source,
            repository_identity=identity,
            locator=locator,
            resolution=resolution,
            pipeline_run=pipeline_run,
            created=True,
        )

    def latest_locator(self, source_id: str) -> RepositoryLocator | None:
        locators = [
            locator
            for locator in self.store.list(RepositoryLocator)
            if locator.source_id == source_id
        ]
        if not locators:
            return None
        return max(locators, key=lambda locator: (locator.observed_at, locator.repository_locator_id))

    def _existing_resolution(
        self,
        hit: DiscoveryHit,
        snapshot: RepositorySnapshot,
    ) -> RepositoryResolutionResult | None:
        resolution = self.store.get(
            DiscoveryResolution,
            self._resolution_id(hit.discovery_hit_id),
        )
        if resolution is None:
            return None
        if resolution.discovery_hit_id != hit.discovery_hit_id:
            raise RepositoryRegistryConflict("discovery resolution identity collision")

        locator = self.store.get(RepositoryLocator, resolution.repository_locator_id)
        source = self.store.get(Source, resolution.source_id)
        identity = self.store.get(RepositoryIdentity, resolution.source_id)
        pipeline_run = self.store.get(PipelineRun, resolution.pipeline_run_id)
        if locator is None or source is None or identity is None or pipeline_run is None:
            raise RepositoryRegistryConflict(
                "existing DiscoveryResolution has incomplete registry provenance"
            )
        if pipeline_run.run_type is not RunType.REGISTRY:
            raise RepositoryRegistryConflict(
                "existing DiscoveryResolution references a non-registry PipelineRun"
            )
        if identity.provider_repository_id != snapshot.provider_repository_id:
            raise RepositoryRegistryConflict(
                "historical DiscoveryHit is already resolved to a different provider repository"
            )
        if hit.source_id is not None and hit.source_id != source.source_id:
            raise RepositoryRegistryConflict(
                "historical DiscoveryHit source link disagrees with its stored resolution"
            )

        current_state = self._locator_state(locator)
        incoming_state = self._snapshot_state(snapshot)
        if current_state != incoming_state:
            raise RepositoryRegistryConflict(
                "historical DiscoveryHit is already resolved with different mutable repository "
                "state; record a new discovery hit instead of rewriting registry history"
            )
        return RepositoryResolutionResult(
            source=source,
            repository_identity=identity,
            locator=locator,
            resolution=resolution,
            pipeline_run=pipeline_run,
            created=False,
        )

    def _resolve_identity(
        self,
        hit: DiscoveryHit,
        snapshot: RepositorySnapshot,
        *,
        first_seen_at: datetime,
        resolved_at: datetime,
    ) -> tuple[Source, RepositoryIdentity, bool, bool]:
        identities = [
            identity
            for identity in self.store.list(RepositoryIdentity)
            if identity.provider_repository_id == snapshot.provider_repository_id
        ]
        if len(identities) > 1:
            raise RepositoryRegistryConflict(
                "provider repository ID is mapped to multiple canonical Sources"
            )

        if identities:
            identity = identities[0]
            source = self.store.get(Source, identity.source_id)
            if source is None:
                raise RepositoryRegistryConflict(
                    f"RepositoryIdentity references missing Source: {identity.source_id}"
                )
            if source.source_kind is not SourceKind.GITHUB_REPOSITORY:
                raise RepositoryRegistryConflict(
                    f"provider repository ID maps to non-GitHub Source: {source.source_id}"
                )
            if hit.source_id is not None and hit.source_id != source.source_id:
                raise RepositoryRegistryConflict(
                    "DiscoveryHit source_id conflicts with the provider repository ID mapping"
                )
            return source, identity, False, False

        if hit.source_id is not None:
            source_id = hit.source_id
            source = self.store.get(Source, source_id)
            if source is None:
                raise RepositoryRegistryConflict(
                    f"DiscoveryHit references missing Source: {source_id}"
                )
            if source.source_kind is not SourceKind.GITHUB_REPOSITORY:
                raise RepositoryRegistryConflict(
                    f"DiscoveryHit source is not a GitHub repository: {source_id}"
                )
            new_source = False
        else:
            source_id = f"github:{snapshot.provider_repository_id}"
            source = self.store.get(Source, source_id)
            if source is None:
                source = Source(
                    source_id=source_id,
                    source_kind=SourceKind.GITHUB_REPOSITORY,
                    source_role=SourceRole.UNKNOWN,
                    canonical_locator=snapshot.canonical_locator,
                    first_seen_at=first_seen_at,
                    last_seen_at=resolved_at,
                )
                new_source = True
            else:
                if source.source_kind is not SourceKind.GITHUB_REPOSITORY:
                    raise RepositoryRegistryConflict(
                        f"canonical GitHub source ID collides with non-GitHub Source: {source_id}"
                    )
                new_source = False

        existing_identity = self.store.get(RepositoryIdentity, source_id)
        if existing_identity is not None:
            if existing_identity.provider_repository_id != snapshot.provider_repository_id:
                raise RepositoryRegistryConflict(
                    "Source is already bound to a different provider repository ID"
                )
            return source, existing_identity, new_source, False

        discovered_repository = self._repository_name_from_locator(hit.discovered_locator)
        aliases = ()
        if discovered_repository is not None and discovered_repository != snapshot.repository:
            aliases = (discovered_repository,)
        identity = RepositoryIdentity(
            source_id=source_id,
            provider_repository_id=snapshot.provider_repository_id,
            owner=snapshot.owner,
            name=snapshot.name,
            default_branch=snapshot.default_branch,
            aliases=aliases,
            archived=snapshot.archived,
        )
        return source, identity, new_source, True

    def _require_hit(self, discovery_hit_id: str) -> DiscoveryHit:
        hit = self.store.get(DiscoveryHit, discovery_hit_id)
        if hit is None:
            raise RepositoryRegistryError(f"unknown DiscoveryHit: {discovery_hit_id}")
        return hit

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RepositoryRegistryError(
                "repository registry clock must return a timezone-aware datetime"
            )
        return value

    @staticmethod
    def _snapshot(metadata: Mapping[str, Any]) -> RepositorySnapshot:
        try:
            provider_id = str(metadata["id"]).strip()
            owner_payload = metadata["owner"]
            if not isinstance(owner_payload, Mapping):
                raise TypeError("owner must be a mapping")
            owner = str(owner_payload["login"]).strip()
            name = str(metadata["name"]).strip()
            default_branch = str(metadata["default_branch"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise RepositoryRegistryError(
                "GitHub repository metadata omitted stable identity fields"
            ) from exc
        if not provider_id or not owner or not name or not default_branch:
            raise RepositoryRegistryError(
                "GitHub repository metadata contains an empty stable identity field"
            )
        fork = bool(metadata.get("fork", False))
        parent_id: str | None = None
        parent = metadata.get("parent")
        if isinstance(parent, Mapping) and parent.get("id") is not None:
            parent_id = str(parent["id"]).strip() or None
        return RepositorySnapshot(
            provider_repository_id=provider_id,
            owner=owner,
            name=name,
            canonical_locator=f"https://github.com/{owner}/{name}",
            default_branch=default_branch,
            archived=bool(metadata.get("archived", False)),
            fork=fork,
            parent_provider_repository_id=parent_id,
        )

    @staticmethod
    def _split_github_locator(locator: str) -> tuple[str, str]:
        raw = locator.strip()
        if raw.startswith("https://") or raw.startswith("http://"):
            parsed = urlparse(raw)
            if parsed.hostname not in {"github.com", "www.github.com"}:
                raise RepositoryRegistryError(
                    f"DiscoveryHit locator is not a GitHub repository: {locator!r}"
                )
            path = parsed.path.strip("/")
        else:
            path = raw.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = path.split("/")
        if len(parts) != 2 or not all(parts):
            raise RepositoryRegistryError(
                f"DiscoveryHit locator must identify one GitHub owner/name repository: {locator!r}"
            )
        return parts[0], parts[1]

    @classmethod
    def _repository_name_from_locator(cls, locator: str) -> str | None:
        try:
            owner, repo = cls._split_github_locator(locator)
        except RepositoryRegistryError:
            return None
        return f"{owner}/{repo}"

    @staticmethod
    def _resolution_id(discovery_hit_id: str) -> str:
        digest = hashlib.sha256(discovery_hit_id.encode("utf-8")).hexdigest()
        return f"discovery-resolution:{digest}"

    @staticmethod
    def _locator_id(discovery_hit_id: str) -> str:
        digest = hashlib.sha256(discovery_hit_id.encode("utf-8")).hexdigest()
        return f"repository-locator:{digest}"

    @staticmethod
    def _locator_state(locator: RepositoryLocator) -> tuple:
        return (
            locator.provider_repository_id,
            locator.owner,
            locator.name,
            locator.canonical_locator,
            locator.default_branch,
            locator.archived,
            locator.fork,
            locator.parent_provider_repository_id,
        )

    @staticmethod
    def _snapshot_state(snapshot: RepositorySnapshot) -> tuple:
        return (
            snapshot.provider_repository_id,
            snapshot.owner,
            snapshot.name,
            snapshot.canonical_locator,
            snapshot.default_branch,
            snapshot.archived,
            snapshot.fork,
            snapshot.parent_provider_repository_id,
        )

    @staticmethod
    def _digest_json(value: object) -> str:
        try:
            encoded = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise RepositoryRegistryError(
                "repository registry provenance must be canonical JSON data"
            ) from exc
        return "sha256:" + hashlib.sha256(encoded).hexdigest()
