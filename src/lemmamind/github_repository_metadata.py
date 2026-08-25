"""Durable GitHub repository-metadata evidence for cross-source comparisons.

Repository metadata such as visibility is mutable provider state. A persisted
SourceRevision anchors the analysis generation, but does not imply that the
captured metadata describes historical state at that Git commit.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol

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
from .objects import ContentAddressedFileStore

REPOSITORY_METADATA_MEDIA_TYPE = "application/vnd.lemmamind.github-repository-metadata+json"


class GitHubRepositoryMetadataError(RuntimeError):
    """Repository metadata is malformed or inconsistent with persisted identity."""


class GitHubRepositoryMetadataReader(Protocol):
    def get_repository(self, owner: str, repo: str) -> Mapping[str, Any]: ...


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...
    def put_many(self, records): ...


@dataclass(frozen=True)
class GitHubRepositoryMetadataCaptureResult:
    manifest: CaptureManifest
    artifact: Artifact
    run: PipelineRun

    def records(self) -> tuple:
        return (self.artifact, self.manifest, self.run)


@dataclass(frozen=True)
class GitHubRepositoryMetadataExtractionResult:
    capture_id: str
    facts: tuple[EvidenceFact, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.facts, self.run)


class GitHubRepositoryMetadataCaptureService:
    """Capture one immutable repository-metadata snapshot under an analysis anchor."""

    def __init__(
        self,
        reader: GitHubRepositoryMetadataReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.repository-metadata-snapshot.v1",
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

    def capture_metadata(self, source_revision_id: str) -> GitHubRepositoryMetadataCaptureResult:
        started_at = self._aware_now()
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise KeyError(f"unknown source revision: {source_revision_id}")
        repository = self.store.get(RepositoryIdentity, revision.source_id)
        if repository is None:
            raise KeyError(f"unknown repository identity: {revision.source_id}")

        payload = self.reader.get_repository(repository.owner, repository.name)
        canonical = self._canonical_metadata(payload, repository)
        snapshot = {
            "resource_type": "repository_metadata",
            "analysis_anchor_source_revision_id": revision.source_revision_id,
            "repository": canonical,
        }
        data = (
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        content_hash = self.object_store.put(data)
        capture_id = f"capture-repository-metadata:{self.id_factory()}"
        artifact_id = self._artifact_id(capture_id)
        locator = "$github/repository"
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=locator,
            content_hash=content_hash,
            media_type=REPOSITORY_METADATA_MEDIA_TYPE,
        )
        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision.source_revision_id,
            capture_policy_version=self.capture_policy_version,
            captured_at=self._aware_now(),
            artifacts=(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=locator,
                    content_hash=content_hash,
                    media_type=REPOSITORY_METADATA_MEDIA_TYPE,
                    retrieval_status=RetrievalStatus.CAPTURED,
                ),
            ),
        )
        inputs_hash = self._digest_json(
            {
                "source_revision_id": source_revision_id,
                "repository": f"{repository.owner}/{repository.name}",
                "capture_policy_version": self.capture_policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "artifact": artifact.model_dump(mode="json"),
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
        result = GitHubRepositoryMetadataCaptureResult(manifest, artifact, run)
        self.store.put_many(result.records())
        return result

    @classmethod
    def _canonical_metadata(
        cls,
        payload: Mapping[str, Any],
        repository: RepositoryIdentity,
    ) -> dict[str, Any]:
        provider_id = payload.get("id")
        if not isinstance(provider_id, int) or isinstance(provider_id, bool):
            raise GitHubRepositoryMetadataError("repository response omitted integer id")
        if str(provider_id) != repository.provider_repository_id:
            raise GitHubRepositoryMetadataError(
                f"provider repository id mismatch: {provider_id} != {repository.provider_repository_id}"
            )
        full_name = cls._required_string(payload, "full_name")
        expected_name = f"{repository.owner}/{repository.name}"
        if full_name != expected_name:
            raise GitHubRepositoryMetadataError(
                f"repository full_name mismatch: {full_name} != {expected_name}"
            )
        visibility = cls._required_string(payload, "visibility")
        if visibility not in {"public", "private", "internal"}:
            raise GitHubRepositoryMetadataError(f"unsupported repository visibility: {visibility}")
        private = payload.get("private")
        if not isinstance(private, bool):
            raise GitHubRepositoryMetadataError("repository response omitted boolean private")
        if private != (visibility == "private"):
            raise GitHubRepositoryMetadataError("repository private flag disagrees with visibility")
        archived = payload.get("archived")
        fork = payload.get("fork")
        if not isinstance(archived, bool) or not isinstance(fork, bool):
            raise GitHubRepositoryMetadataError("repository archived/fork fields must be booleans")
        default_branch = cls._required_string(payload, "default_branch")
        return {
            "id": provider_id,
            "full_name": full_name,
            "visibility": visibility,
            "private": private,
            "archived": archived,
            "fork": fork,
            "default_branch": default_branch,
        }

    @staticmethod
    def _required_string(payload: Mapping[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise GitHubRepositoryMetadataError(f"repository response omitted {key}")
        return value.strip()

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("repository metadata capture clock must be timezone-aware")
        return value

    @staticmethod
    def _artifact_id(capture_id: str) -> str:
        material = f"{capture_id}\0repository-metadata".encode("utf-8")
        return f"artifact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class GitHubRepositoryMetadataEvidenceService:
    """Emit deterministic facts from a captured repository-metadata snapshot."""

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "github-repository-metadata-evidence.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.object_store = object_store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def extract_metadata(self, capture_id: str) -> GitHubRepositoryMetadataExtractionResult:
        started_at = self._aware_now()
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")
        if len(manifest.artifacts) != 1:
            raise GitHubRepositoryMetadataError("repository metadata capture must contain one artifact")
        ref = manifest.artifacts[0]
        if ref.retrieval_status is not RetrievalStatus.CAPTURED or ref.media_type != REPOSITORY_METADATA_MEDIA_TYPE:
            raise GitHubRepositoryMetadataError("capture is not repository metadata")
        artifact = self.store.get(Artifact, ref.artifact_id)
        if artifact is None:
            raise GitHubRepositoryMetadataError("repository metadata Artifact is missing")
        if (
            artifact.capture_id != manifest.capture_id
            or artifact.source_locator != ref.source_locator
            or artifact.content_hash != ref.content_hash
            or artifact.media_type != ref.media_type
        ):
            raise GitHubRepositoryMetadataError("repository metadata Artifact disagrees with manifest")
        data = self.object_store.get(artifact.content_hash)
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubRepositoryMetadataError("repository metadata artifact is not canonical JSON") from exc
        if not isinstance(document, Mapping) or document.get("resource_type") != "repository_metadata":
            raise GitHubRepositoryMetadataError("repository metadata artifact has invalid resource_type")
        repository = document.get("repository")
        if not isinstance(repository, Mapping):
            raise GitHubRepositoryMetadataError("repository metadata artifact omitted repository")

        run_id = f"run:{self.id_factory()}"
        facts = tuple(
            EvidenceFact(
                evidence_id=self._record_id(run_id, index, key),
                artifact_id=artifact.artifact_id,
                locator=f"{artifact.source_locator}#/{key}",
                raw_value=repository[key],
                normalized_value=repository[key],
                extractor_name="github-repository-metadata",
                extractor_version="1",
                run_id=run_id,
            )
            for index, key in enumerate(
                ("id", "full_name", "visibility", "private", "archived", "fork", "default_branch"),
                start=1,
            )
        )
        inputs_hash = GitHubRepositoryMetadataCaptureService._digest_json(
            {
                "capture_id": capture_id,
                "content_hash": artifact.content_hash,
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = GitHubRepositoryMetadataCaptureService._digest_json(
            [fact.model_dump(mode="json") for fact in facts]
        )
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.EXTRACTION,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = GitHubRepositoryMetadataExtractionResult(capture_id, facts, run)
        self.store.put_many(result.records())
        return result

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("repository metadata extraction clock must be timezone-aware")
        return value

    @staticmethod
    def _record_id(run_id: str, index: int, key: str) -> str:
        material = f"{run_id}\0{index}\0{key}".encode("utf-8")
        return f"evidence:{hashlib.sha256(material).hexdigest()}"
