"""Deterministic capture and extraction of exact Git root-tree evidence.

Git tree metadata is source evidence, not repository interpretation. This module
captures a canonical non-recursive Git tree object tied to SourceRevision.tree_sha
and emits only source-addressed EvidenceFact records.
"""
from __future__ import annotations

import hashlib
import json
import re
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

GIT_ROOT_TREE_MEDIA_TYPE = "application/vnd.lemmamind.git-tree+json"
GIT_ROOT_TREE_LOCATOR = "$git/tree/root"
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_TYPES = {"blob", "tree", "commit"}


class GitTreeError(RuntimeError):
    """Git tree source data is malformed or inconsistent with the pinned revision."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


class GitHubTreeRESTReader(GitHubRESTReader):
    """Read-only GitHub reader extended with the Git Trees endpoint."""

    def get_tree(self, owner: str, repo: str, tree_sha: str) -> Mapping[str, Any]:
        payload = self._get_json(  # noqa: SLF001 - subclass exposes one stable read-only operation
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/git/trees/{quote(tree_sha, safe='')}"
        )
        if not isinstance(payload, Mapping):
            raise GitTreeError("GitHub tree response must be an object")
        return payload


@dataclass(frozen=True)
class GitTreeCaptureResult:
    manifest: CaptureManifest
    artifact: Artifact
    run: PipelineRun

    def records(self) -> tuple:
        return (self.artifact, self.manifest, self.run)


@dataclass(frozen=True)
class GitTreeExtractionResult:
    capture_id: str
    facts: tuple[EvidenceFact, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.facts, self.run)


class GitHubRootTreeCaptureService:
    """Capture the exact non-recursive root tree for one persisted SourceRevision."""

    def __init__(
        self,
        reader: GitHubTreeRESTReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.root-tree.v1",
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

    def capture_root_tree(self, source_revision_id: str) -> GitTreeCaptureResult:
        started_at = self._aware_now()
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise KeyError(f"unknown source revision: {source_revision_id}")
        repository = self.store.get(RepositoryIdentity, revision.source_id)
        if repository is None:
            raise KeyError(f"unknown repository identity: {revision.source_id}")

        payload = self.reader.get_tree(repository.owner, repository.name, revision.tree_sha)
        canonical = self._canonical_tree(payload, expected_tree_sha=revision.tree_sha)
        data = (json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        content_hash = self.object_store.put(data)
        capture_id = f"capture-tree:{self.id_factory()}"
        artifact_id = self._artifact_id(capture_id, revision.tree_sha)
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=GIT_ROOT_TREE_LOCATOR,
            content_hash=content_hash,
            media_type=GIT_ROOT_TREE_MEDIA_TYPE,
        )
        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision.source_revision_id,
            capture_policy_version=self.capture_policy_version,
            captured_at=self._aware_now(),
            artifacts=(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=GIT_ROOT_TREE_LOCATOR,
                    content_hash=content_hash,
                    media_type=GIT_ROOT_TREE_MEDIA_TYPE,
                    retrieval_status=RetrievalStatus.CAPTURED,
                ),
            ),
        )
        inputs_hash = self._digest_json(
            {
                "source_revision_id": revision.source_revision_id,
                "tree_sha": revision.tree_sha,
                "recursive": False,
                "capture_policy_version": self.capture_policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "artifact": artifact.model_dump(mode="json", by_alias=True),
                "manifest": manifest.model_dump(mode="json", by_alias=True),
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
        result = GitTreeCaptureResult(manifest, artifact, run)
        self.store.put_many(result.records())
        return result

    @classmethod
    def _canonical_tree(
        cls, payload: Mapping[str, Any], *, expected_tree_sha: str
    ) -> dict[str, Any]:
        tree_sha = payload.get("sha")
        if tree_sha != expected_tree_sha:
            raise GitTreeError(
                f"tree SHA mismatch: expected {expected_tree_sha}, received {tree_sha!r}"
            )
        entries_raw = payload.get("tree")
        if not isinstance(entries_raw, list):
            raise GitTreeError("GitHub tree response omitted tree entries")

        entries: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for raw in entries_raw:
            if not isinstance(raw, Mapping):
                raise GitTreeError("Git tree entry must be an object")
            path = raw.get("path")
            mode = raw.get("mode")
            entry_type = raw.get("type")
            sha = raw.get("sha")
            size = raw.get("size")
            if not isinstance(path, str) or not path or "/" in path:
                raise GitTreeError(f"non-recursive root tree contains invalid path: {path!r}")
            if path in seen_paths:
                raise GitTreeError(f"duplicate root tree path: {path}")
            seen_paths.add(path)
            if not isinstance(mode, str) or not mode:
                raise GitTreeError(f"tree entry {path!r} omitted mode")
            if entry_type not in _ALLOWED_TYPES:
                raise GitTreeError(f"tree entry {path!r} has unsupported type {entry_type!r}")
            if not isinstance(sha, str) or _GIT_SHA.fullmatch(sha) is None:
                raise GitTreeError(f"tree entry {path!r} has invalid SHA")
            entry: dict[str, Any] = {
                "path": path,
                "mode": mode,
                "type": entry_type,
                "sha": sha,
            }
            if size is not None:
                if not isinstance(size, int) or size < 0:
                    raise GitTreeError(f"tree entry {path!r} has invalid size")
                entry["size"] = size
            entries.append(entry)

        entries.sort(key=lambda item: item["path"])
        return {
            "tree_sha": expected_tree_sha,
            "recursive": False,
            "truncated": bool(payload.get("truncated", False)),
            "entries": entries,
        }

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("tree capture clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _artifact_id(capture_id: str, tree_sha: str) -> str:
        material = f"{capture_id}\0{tree_sha}\0root-tree".encode("utf-8")
        return f"artifact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


class GitTreeEvidenceService:
    """Emit deterministic EvidenceFact records from a captured canonical root tree."""

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "git-tree-facts.v1",
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

    def extract_root_tree(self, capture_id: str) -> GitTreeExtractionResult:
        started_at = self._aware_now()
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")
        if len(manifest.artifacts) != 1:
            raise GitTreeError("root-tree capture must contain exactly one artifact")
        reference = manifest.artifacts[0]
        if (
            reference.retrieval_status is not RetrievalStatus.CAPTURED
            or reference.media_type != GIT_ROOT_TREE_MEDIA_TYPE
            or reference.source_locator != GIT_ROOT_TREE_LOCATOR
        ):
            raise GitTreeError("capture is not a canonical root-tree capture")
        artifact = self.store.get(Artifact, reference.artifact_id)
        if artifact is None:
            raise GitTreeError("root-tree manifest references a missing Artifact")
        if (
            artifact.capture_id != manifest.capture_id
            or artifact.content_hash != reference.content_hash
            or artifact.media_type != GIT_ROOT_TREE_MEDIA_TYPE
            or artifact.source_locator != GIT_ROOT_TREE_LOCATOR
        ):
            raise GitTreeError("root-tree Artifact disagrees with CaptureManifest")

        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise GitTreeError("root-tree capture references a missing SourceRevision")
        data = self.object_store.get(artifact.content_hash)
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitTreeError("captured root tree is not canonical UTF-8 JSON") from exc
        if not isinstance(document, Mapping):
            raise GitTreeError("captured root tree must be a JSON object")
        if document.get("tree_sha") != revision.tree_sha:
            raise GitTreeError("captured root tree no longer matches SourceRevision.tree_sha")
        entries = document.get("entries")
        if not isinstance(entries, list):
            raise GitTreeError("captured root tree omitted entries")

        run_id = f"run:{self.id_factory()}"
        specs: list[tuple[str, object]] = [
            ("tree_sha", document["tree_sha"]),
            ("recursive", bool(document.get("recursive", False))),
            ("truncated", bool(document.get("truncated", False))),
            ("entry_count", len(entries)),
            ("entry_paths", [entry["path"] for entry in entries]),
        ]
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise GitTreeError("canonical root-tree entry must be an object")
            path = str(entry["path"])
            prefix = f"entries/{self._pointer_escape(path)}"
            specs.extend(
                [
                    (f"{prefix}/type", entry["type"]),
                    (f"{prefix}/mode", entry["mode"]),
                    (f"{prefix}/sha", entry["sha"]),
                ]
            )
            if "size" in entry:
                specs.append((f"{prefix}/size", entry["size"]))

        facts = tuple(
            EvidenceFact(
                evidence_id=self._fact_id(run_id, index, key),
                artifact_id=artifact.artifact_id,
                locator=f"{GIT_ROOT_TREE_LOCATOR}#/{key}",
                raw_value=value,
                normalized_value=value,
                extractor_name="git-root-tree",
                extractor_version="1",
                run_id=run_id,
            )
            for index, (key, value) in enumerate(specs, start=1)
        )
        inputs_hash = self._digest_json(
            {
                "artifact_id": artifact.artifact_id,
                "content_hash": artifact.content_hash,
                "source_revision_id": revision.source_revision_id,
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            [
                {
                    "locator": fact.locator,
                    "normalized_value": fact.normalized_value,
                    "extractor_name": fact.extractor_name,
                    "extractor_version": fact.extractor_version,
                }
                for fact in facts
            ]
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
        result = GitTreeExtractionResult(capture_id, facts, run)
        self.store.put_many(result.records())
        return result

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("tree extraction clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _pointer_escape(value: str) -> str:
        return value.replace("~", "~0").replace("/", "~1")

    @staticmethod
    def _fact_id(run_id: str, index: int, key: str) -> str:
        material = f"tree-fact\0{run_id}\0{index}\0{key}".encode("utf-8")
        return f"fact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
