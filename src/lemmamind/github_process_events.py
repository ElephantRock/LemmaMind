"""Durable deterministic GitHub issue-event history evidence.

Issue/PR current snapshots and issue event history are distinct evidence classes.
This module captures the provider's immutable event records for selected issues so
historical transitions such as closed -> reopened are observed rather than inferred
from a current ``state=open`` snapshot.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RepositoryIdentity,
    RetrievalStatus,
    RunType,
    SourceRevision,
)
from .github import GitHubRESTReader
from .objects import ContentAddressedFileStore

ISSUE_EVENT_HISTORY_MEDIA_TYPE = "application/vnd.lemmamind.github-issue-events+json"


class GitHubProcessEventError(RuntimeError):
    """GitHub issue-event data is malformed or incomplete."""


class GitHubProcessEventReader(Protocol):
    def get_issue_events(self, owner: str, repo: str, number: int) -> tuple[Mapping[str, Any], ...]: ...


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


class GitHubProcessEventRESTReader(GitHubRESTReader):
    """Read-only REST reader for complete issue event history.

    Pagination fails closed if the configured page ceiling is exhausted. We do not
    silently truncate historical evidence.
    """

    def __init__(self, *args, max_pages: int = 100, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        self.max_pages = max_pages

    def get_issue_events(self, owner: str, repo: str, number: int) -> tuple[Mapping[str, Any], ...]:
        if number < 1:
            raise ValueError("GitHub issue number must be positive")
        path = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/issues/{number}/events"
        collected: list[Mapping[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            payload = self._get_json(path, {"per_page": "100", "page": str(page)})
            if not isinstance(payload, list):
                raise GitHubProcessEventError("GitHub issue-events response must be a JSON array")
            for item in payload:
                if not isinstance(item, Mapping):
                    raise GitHubProcessEventError("GitHub issue event must be a JSON object")
                collected.append(item)
            if len(payload) < 100:
                return tuple(collected)
        raise GitHubProcessEventError(
            f"issue-event pagination exceeded max_pages={self.max_pages}; refusing truncated history"
        )


@dataclass(frozen=True)
class GitHubProcessEventCaptureResult:
    manifest: CaptureManifest
    artifacts: tuple[Artifact, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.artifacts, self.manifest, self.run)


@dataclass(frozen=True)
class GitHubProcessEventExtractionResult:
    capture_id: str
    facts: tuple[EvidenceFact, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.facts, self.run)


class GitHubProcessEventCaptureService:
    """Capture immutable canonical event-history snapshots for selected issues."""

    def __init__(
        self,
        reader: GitHubProcessEventReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.issue-events.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.reader = reader
        self.store = store
        self.object_store = object_store
        self.capture_policy_version = capture_policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def capture_issue_events(
        self,
        source_revision_id: str,
        issue_numbers: tuple[int, ...] | list[int],
    ) -> GitHubProcessEventCaptureResult:
        started_at = self._aware_now()
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise KeyError(f"unknown source revision: {source_revision_id}")
        repository = self.store.get(RepositoryIdentity, revision.source_id)
        if repository is None:
            raise KeyError(f"unknown repository identity: {revision.source_id}")

        requested = tuple(issue_numbers)
        if not requested:
            raise ValueError("at least one GitHub issue number is required")
        if any(number < 1 for number in requested):
            raise ValueError("GitHub issue numbers must be positive")
        ordered = tuple(sorted(set(requested)))
        if len(ordered) != len(requested):
            raise ValueError("duplicate GitHub issue numbers are not allowed")

        capture_id = f"capture-process-events:{self.id_factory()}"
        artifacts: list[Artifact] = []
        refs: list[CaptureArtifactRef] = []
        repository_full_name = f"{repository.owner}/{repository.name}"

        for number in ordered:
            raw_events = self.reader.get_issue_events(repository.owner, repository.name, number)
            canonical_events = self._canonical_events(raw_events)
            canonical = {
                "resource_type": "issue_event_history",
                "repository_full_name": repository_full_name,
                "issue_number": number,
                "events": canonical_events,
            }
            data = (
                json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
            content_hash = self.object_store.put(data)
            locator = f"$github/issue/{number}/events"
            artifact_id = self._artifact_id(capture_id, number)
            artifact = Artifact(
                artifact_id=artifact_id,
                capture_id=capture_id,
                source_locator=locator,
                content_hash=content_hash,
                media_type=ISSUE_EVENT_HISTORY_MEDIA_TYPE,
            )
            artifacts.append(artifact)
            refs.append(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=locator,
                    content_hash=content_hash,
                    media_type=ISSUE_EVENT_HISTORY_MEDIA_TYPE,
                    retrieval_status=RetrievalStatus.CAPTURED,
                )
            )

        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision.source_revision_id,
            capture_policy_version=self.capture_policy_version,
            captured_at=self._aware_now(),
            artifacts=tuple(refs),
        )
        inputs_hash = self._digest_json(
            {
                "source_revision_id": revision.source_revision_id,
                "repository": repository_full_name,
                "analysis_anchor_commit_sha": revision.commit_sha,
                "issue_numbers": ordered,
                "capture_policy_version": self.capture_policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
                "manifest": manifest.model_dump(mode="json"),
            }
        )
        run = PipelineRun(
            run_id=f"run:{self.id_factory()}",
            run_type=RunType.CAPTURE,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.capture_policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = GitHubProcessEventCaptureResult(manifest, tuple(artifacts), run)
        self.store.put_many(result.records())
        return result

    @classmethod
    def _canonical_events(cls, events: tuple[Mapping[str, Any], ...]) -> list[dict[str, Any]]:
        canonical: list[tuple[datetime, int, dict[str, Any]]] = []
        seen_ids: set[int] = set()
        for payload in events:
            provider_id = cls._required_int(payload, "id")
            if provider_id in seen_ids:
                raise GitHubProcessEventError(f"duplicate GitHub issue event id: {provider_id}")
            seen_ids.add(provider_id)
            created_at = cls._required_timestamp(payload, "created_at")
            actor = payload.get("actor")
            actor_login: str | None
            if actor is None:
                actor_login = None
            elif isinstance(actor, Mapping):
                actor_login = cls._required_string(actor, "login")
            else:
                raise GitHubProcessEventError("GitHub issue event actor has invalid type")
            item = {
                "provider_id": str(provider_id),
                "node_id": cls._required_string(payload, "node_id"),
                "event": cls._required_string(payload, "event"),
                "created_at": created_at.isoformat().replace("+00:00", "Z"),
                "actor_login": actor_login,
                "commit_id": cls._optional_string(payload.get("commit_id")),
                "commit_url": cls._optional_string(payload.get("commit_url")),
            }
            canonical.append((created_at, provider_id, item))
        canonical.sort(key=lambda row: (row[0], row[1]))
        return [row[2] for row in canonical]

    @staticmethod
    def _required_string(mapping: Mapping[str, Any], key: str) -> str:
        value = mapping.get(key)
        if not isinstance(value, str) or not value.strip():
            raise GitHubProcessEventError(f"GitHub issue event omitted {key}")
        return value.strip()

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise GitHubProcessEventError("optional GitHub issue-event string has invalid type")
        return value

    @staticmethod
    def _required_int(mapping: Mapping[str, Any], key: str) -> int:
        value = mapping.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise GitHubProcessEventError(f"GitHub issue event omitted integer {key}")
        return value

    @classmethod
    def _required_timestamp(cls, mapping: Mapping[str, Any], key: str) -> datetime:
        value = cls._required_string(mapping, key)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GitHubProcessEventError(f"GitHub issue event has invalid timestamp {key}") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise GitHubProcessEventError(f"GitHub issue event timestamp {key} is not timezone-aware")
        return parsed.astimezone(timezone.utc)

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GitHub process-event capture clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _artifact_id(capture_id: str, issue_number: int) -> str:
        material = f"{capture_id}\0issue\0{issue_number}\0events".encode("utf-8")
        return f"artifact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


class GitHubProcessEventEvidenceService:
    """Emit deterministic EvidenceFacts from captured issue-event history."""

    name = "github-issue-events"
    version = "1"

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        extraction_policy_version: str = "github.issue-events-evidence.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.object_store = object_store
        self.extraction_policy_version = extraction_policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def extract_issue_events(self, capture_id: str) -> GitHubProcessEventExtractionResult:
        started_at = self._aware_now()
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")
        run_id = f"run:{self.id_factory()}"
        specs: list[tuple[str, str, object]] = []

        for ref in manifest.artifacts:
            if ref.retrieval_status is not RetrievalStatus.CAPTURED:
                continue
            artifact = self.store.get(Artifact, ref.artifact_id)
            if artifact is None:
                raise GitHubProcessEventError(f"manifest references missing Artifact: {ref.artifact_id}")
            if artifact.capture_id != manifest.capture_id:
                raise GitHubProcessEventError("event-history Artifact capture_id disagrees with manifest")
            if artifact.media_type != ISSUE_EVENT_HISTORY_MEDIA_TYPE:
                raise GitHubProcessEventError(f"unsupported event-history media type: {artifact.media_type}")
            if artifact.content_hash != ref.content_hash or artifact.source_locator != ref.source_locator:
                raise GitHubProcessEventError("event-history Artifact disagrees with manifest reference")
            payload = self._load_payload(artifact)
            base = artifact.source_locator
            specs.extend(
                [
                    (artifact.artifact_id, f"{base}#/repository_full_name", payload["repository_full_name"]),
                    (artifact.artifact_id, f"{base}#/issue_number", payload["issue_number"]),
                    (artifact.artifact_id, f"{base}#/event_count", len(payload["events"])),
                ]
            )
            for index, event in enumerate(payload["events"]):
                prefix = f"{base}#/events/{index}"
                for key in (
                    "provider_id",
                    "node_id",
                    "event",
                    "created_at",
                    "actor_login",
                    "commit_id",
                    "commit_url",
                ):
                    value = event[key]
                    if value is not None:
                        specs.append((artifact.artifact_id, f"{prefix}/{key}", value))

        facts = tuple(
            EvidenceFact(
                evidence_id=self._fact_id(run_id, artifact_id, locator),
                artifact_id=artifact_id,
                locator=locator,
                raw_value=value,
                normalized_value=value,
                extractor_name=self.name,
                extractor_version=self.version,
                run_id=run_id,
            )
            for artifact_id, locator, value in specs
        )
        inputs_hash = self._digest_json(
            {
                "capture_id": manifest.capture_id,
                "artifact_hashes": [ref.content_hash for ref in manifest.artifacts],
                "policy_version": self.extraction_policy_version,
            }
        )
        outputs_hash = self._digest_json([fact.model_dump(mode="json") for fact in facts])
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.EXTRACTION,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.extraction_policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = GitHubProcessEventExtractionResult(manifest.capture_id, facts, run)
        self.store.put_many(result.records())
        return result

    def _load_payload(self, artifact: Artifact) -> dict[str, Any]:
        try:
            payload = json.loads(self.object_store.get(artifact.content_hash).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubProcessEventError("captured issue-event history is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise GitHubProcessEventError("captured issue-event history must be a JSON object")
        required = {"resource_type", "repository_full_name", "issue_number", "events"}
        if not required.issubset(payload):
            raise GitHubProcessEventError("captured issue-event history omitted required fields")
        if payload["resource_type"] != "issue_event_history":
            raise GitHubProcessEventError("captured artifact is not issue-event history")
        if not isinstance(payload["repository_full_name"], str):
            raise GitHubProcessEventError("event-history repository_full_name has invalid type")
        if not isinstance(payload["issue_number"], int) or isinstance(payload["issue_number"], bool):
            raise GitHubProcessEventError("event-history issue_number has invalid type")
        if not isinstance(payload["events"], list):
            raise GitHubProcessEventError("event-history events has invalid type")
        for event in payload["events"]:
            if not isinstance(event, dict):
                raise GitHubProcessEventError("event-history event has invalid type")
            for key in ("provider_id", "node_id", "event", "created_at", "actor_login", "commit_id", "commit_url"):
                if key not in event:
                    raise GitHubProcessEventError(f"event-history event omitted {key}")
        return payload

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GitHub process-event extraction clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _fact_id(run_id: str, artifact_id: str, locator: str) -> str:
        material = f"{run_id}\0{artifact_id}\0{locator}".encode("utf-8")
        return f"evidence:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
