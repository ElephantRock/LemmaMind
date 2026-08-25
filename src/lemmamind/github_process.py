"""Durable deterministic GitHub issue/pull-request snapshot evidence.

GitHub issue and PR state is mutable process state, not a pure function of a Git
commit. This module therefore uses SourceRevision only as the repository analysis
anchor. The captured process artifact carries its own provider IDs, timestamps,
state, and PR head/base/merge SHAs. Repeated later captures produce new immutable
content-addressed snapshots rather than rewriting prior evidence.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
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
    SourceAssertion,
    SourceRevision,
)
from .github import GitHubRESTReader
from .objects import ContentAddressedFileStore

ISSUE_MEDIA_TYPE = "application/vnd.lemmamind.github-issue+json"
PULL_MEDIA_TYPE = "application/vnd.lemmamind.github-pull+json"


class GitHubProcessError(RuntimeError):
    """GitHub process data is malformed or inconsistent with the capture request."""


class ProcessKind(StrEnum):
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"


@dataclass(frozen=True, order=True)
class ProcessRef:
    kind: ProcessKind
    number: int

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("GitHub issue/PR number must be positive")

    @property
    def locator(self) -> str:
        resource = "issue" if self.kind is ProcessKind.ISSUE else "pull"
        return f"$github/{resource}/{self.number}"


class GitHubProcessReader(Protocol):
    def get_issue(self, owner: str, repo: str, number: int) -> Mapping[str, Any]: ...

    def get_pull(self, owner: str, repo: str, number: int) -> Mapping[str, Any]: ...


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


class GitHubProcessRESTReader(GitHubRESTReader):
    """Read-only REST reader for exact issue and pull-request snapshots."""

    def get_issue(self, owner: str, repo: str, number: int) -> Mapping[str, Any]:
        payload = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/issues/{number}"
        )
        if not isinstance(payload, Mapping):
            raise GitHubProcessError("GitHub issue response must be a JSON object")
        return payload

    def get_pull(self, owner: str, repo: str, number: int) -> Mapping[str, Any]:
        payload = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls/{number}"
        )
        if not isinstance(payload, Mapping):
            raise GitHubProcessError("GitHub pull response must be a JSON object")
        return payload


@dataclass(frozen=True)
class GitHubProcessCaptureResult:
    manifest: CaptureManifest
    artifacts: tuple[Artifact, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.artifacts, self.manifest, self.run)


@dataclass(frozen=True)
class GitHubProcessExtractionResult:
    capture_id: str
    facts: tuple[EvidenceFact, ...]
    assertions: tuple[SourceAssertion, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.facts, *self.assertions, self.run)


class GitHubProcessCaptureService:
    """Capture canonical immutable snapshots of selected GitHub issues/PRs."""

    def __init__(
        self,
        reader: GitHubProcessReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.process-snapshot.v1",
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

    def capture_process(
        self,
        source_revision_id: str,
        refs: tuple[ProcessRef, ...] | list[ProcessRef],
    ) -> GitHubProcessCaptureResult:
        started_at = self._aware_now()
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise KeyError(f"unknown source revision: {source_revision_id}")
        repository = self.store.get(RepositoryIdentity, revision.source_id)
        if repository is None:
            raise KeyError(f"unknown repository identity: {revision.source_id}")

        ordered_refs = tuple(sorted(set(refs)))
        if not ordered_refs:
            raise ValueError("at least one GitHub issue/PR reference is required")
        if len(ordered_refs) != len(tuple(refs)):
            raise ValueError("duplicate GitHub issue/PR references are not allowed")

        capture_id = f"capture-process:{self.id_factory()}"
        artifacts: list[Artifact] = []
        artifact_refs: list[CaptureArtifactRef] = []
        for ref in ordered_refs:
            if ref.kind is ProcessKind.ISSUE:
                payload = self.reader.get_issue(repository.owner, repository.name, ref.number)
                canonical = self._canonical_issue(
                    payload,
                    repository_full_name=f"{repository.owner}/{repository.name}",
                    expected_number=ref.number,
                )
                media_type = ISSUE_MEDIA_TYPE
            elif ref.kind is ProcessKind.PULL_REQUEST:
                payload = self.reader.get_pull(repository.owner, repository.name, ref.number)
                canonical = self._canonical_pull(
                    payload,
                    repository_full_name=f"{repository.owner}/{repository.name}",
                    expected_number=ref.number,
                )
                media_type = PULL_MEDIA_TYPE
            else:  # pragma: no cover - StrEnum constrains construction
                raise GitHubProcessError(f"unsupported process kind: {ref.kind}")

            data = (
                json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
            content_hash = self.object_store.put(data)
            artifact_id = self._artifact_id(capture_id, ref)
            artifact = Artifact(
                artifact_id=artifact_id,
                capture_id=capture_id,
                source_locator=ref.locator,
                content_hash=content_hash,
                media_type=media_type,
            )
            artifacts.append(artifact)
            artifact_refs.append(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=ref.locator,
                    content_hash=content_hash,
                    media_type=media_type,
                    retrieval_status=RetrievalStatus.CAPTURED,
                )
            )

        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision.source_revision_id,
            capture_policy_version=self.capture_policy_version,
            captured_at=self._aware_now(),
            artifacts=tuple(artifact_refs),
        )
        inputs_hash = self._digest_json(
            {
                "source_revision_id": revision.source_revision_id,
                "repository": f"{repository.owner}/{repository.name}",
                "analysis_anchor_commit_sha": revision.commit_sha,
                "resources": [
                    {"kind": ref.kind.value, "number": ref.number, "locator": ref.locator}
                    for ref in ordered_refs
                ],
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
        result = GitHubProcessCaptureResult(manifest, tuple(artifacts), run)
        self.store.put_many(result.records())
        return result

    @classmethod
    def _canonical_issue(
        cls,
        payload: Mapping[str, Any],
        *,
        repository_full_name: str,
        expected_number: int,
    ) -> dict[str, Any]:
        if "pull_request" in payload:
            raise GitHubProcessError("issue endpoint returned a pull request; use ProcessKind.PULL_REQUEST")
        number = cls._required_int(payload, "number")
        if number != expected_number:
            raise GitHubProcessError(
                f"issue number mismatch: expected {expected_number}, received {number}"
            )
        return {
            "resource_type": ProcessKind.ISSUE.value,
            "repository_full_name": repository_full_name,
            "number": number,
            "provider_id": str(cls._required_int(payload, "id")),
            "node_id": cls._required_string(payload, "node_id"),
            "html_url": cls._required_string(payload, "html_url"),
            "state": cls._required_string(payload, "state"),
            "state_reason": cls._optional_string(payload.get("state_reason")),
            "title": cls._required_string(payload, "title"),
            "body": cls._optional_string(payload.get("body")),
            "author_login": cls._nested_login(payload.get("user"), field="user"),
            "author_association": cls._optional_string(payload.get("author_association")),
            "locked": cls._required_bool(payload, "locked"),
            "comments": cls._required_int(payload, "comments"),
            "labels": cls._labels(payload.get("labels")),
            "assignees": cls._logins(payload.get("assignees"), field="assignees"),
            "created_at": cls._required_string(payload, "created_at"),
            "updated_at": cls._required_string(payload, "updated_at"),
            "closed_at": cls._optional_string(payload.get("closed_at")),
        }

    @classmethod
    def _canonical_pull(
        cls,
        payload: Mapping[str, Any],
        *,
        repository_full_name: str,
        expected_number: int,
    ) -> dict[str, Any]:
        number = cls._required_int(payload, "number")
        if number != expected_number:
            raise GitHubProcessError(
                f"pull number mismatch: expected {expected_number}, received {number}"
            )
        return {
            "resource_type": ProcessKind.PULL_REQUEST.value,
            "repository_full_name": repository_full_name,
            "number": number,
            "provider_id": str(cls._required_int(payload, "id")),
            "node_id": cls._required_string(payload, "node_id"),
            "html_url": cls._required_string(payload, "html_url"),
            "state": cls._required_string(payload, "state"),
            "draft": cls._required_bool(payload, "draft"),
            "merged": cls._required_bool(payload, "merged"),
            "merge_commit_sha": cls._optional_string(payload.get("merge_commit_sha")),
            "title": cls._required_string(payload, "title"),
            "body": cls._optional_string(payload.get("body")),
            "author_login": cls._nested_login(payload.get("user"), field="user"),
            "author_association": cls._optional_string(payload.get("author_association")),
            "labels": cls._labels(payload.get("labels")),
            "requested_reviewers": cls._logins(
                payload.get("requested_reviewers"), field="requested_reviewers"
            ),
            "head": cls._canonical_ref(payload.get("head"), field="head"),
            "base": cls._canonical_ref(payload.get("base"), field="base"),
            "commits": cls._required_int(payload, "commits"),
            "changed_files": cls._required_int(payload, "changed_files"),
            "additions": cls._required_int(payload, "additions"),
            "deletions": cls._required_int(payload, "deletions"),
            "created_at": cls._required_string(payload, "created_at"),
            "updated_at": cls._required_string(payload, "updated_at"),
            "closed_at": cls._optional_string(payload.get("closed_at")),
            "merged_at": cls._optional_string(payload.get("merged_at")),
        }

    @classmethod
    def _canonical_ref(cls, value: Any, *, field: str) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise GitHubProcessError(f"pull response omitted {field} ref")
        repo = value.get("repo")
        repo_name = repo.get("full_name") if isinstance(repo, Mapping) else None
        return {
            "ref": cls._required_string(value, "ref"),
            "sha": cls._required_string(value, "sha"),
            "repository_full_name": cls._optional_string(repo_name),
        }

    @staticmethod
    def _required_string(mapping: Mapping[str, Any], key: str) -> str:
        value = mapping.get(key)
        if not isinstance(value, str) or not value.strip():
            raise GitHubProcessError(f"GitHub process response omitted {key}")
        return value.strip()

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise GitHubProcessError("optional GitHub process string has invalid type")
        return value

    @staticmethod
    def _required_int(mapping: Mapping[str, Any], key: str) -> int:
        value = mapping.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise GitHubProcessError(f"GitHub process response omitted integer {key}")
        return value

    @staticmethod
    def _required_bool(mapping: Mapping[str, Any], key: str) -> bool:
        value = mapping.get(key)
        if not isinstance(value, bool):
            raise GitHubProcessError(f"GitHub process response omitted boolean {key}")
        return value

    @classmethod
    def _nested_login(cls, value: Any, *, field: str) -> str:
        if not isinstance(value, Mapping):
            raise GitHubProcessError(f"GitHub process response omitted {field}")
        return cls._required_string(value, "login")

    @classmethod
    def _labels(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise GitHubProcessError("GitHub process response omitted labels")
        labels: list[str] = []
        for item in value:
            if not isinstance(item, Mapping):
                raise GitHubProcessError("GitHub process label must be an object")
            labels.append(cls._required_string(item, "name"))
        return sorted(set(labels))

    @classmethod
    def _logins(cls, value: Any, *, field: str) -> list[str]:
        if not isinstance(value, list):
            raise GitHubProcessError(f"GitHub process response omitted {field}")
        result: list[str] = []
        for item in value:
            result.append(cls._nested_login(item, field=field))
        return sorted(set(result))

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GitHub process capture clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _artifact_id(capture_id: str, ref: ProcessRef) -> str:
        material = f"{capture_id}\0{ref.kind.value}\0{ref.number}".encode("utf-8")
        return f"artifact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


class GitHubProcessEvidenceService:
    """Emit process metadata facts and preserve authored title/body assertions."""

    _FACT_KEYS = (
        "resource_type",
        "repository_full_name",
        "number",
        "provider_id",
        "node_id",
        "html_url",
        "state",
        "state_reason",
        "author_login",
        "author_association",
        "locked",
        "comments",
        "labels",
        "assignees",
        "draft",
        "merged",
        "merge_commit_sha",
        "requested_reviewers",
        "commits",
        "changed_files",
        "additions",
        "deletions",
        "created_at",
        "updated_at",
        "closed_at",
        "merged_at",
    )

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "github-process-evidence.v1",
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

    def extract_process(self, capture_id: str) -> GitHubProcessExtractionResult:
        started_at = self._aware_now()
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")
        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise GitHubProcessError("process capture references a missing SourceRevision")
        if not manifest.artifacts:
            raise GitHubProcessError("process capture must contain at least one artifact")

        run_id = f"run:{self.id_factory()}"
        facts: list[EvidenceFact] = []
        assertions: list[SourceAssertion] = []
        fact_index = 0
        assertion_index = 0

        for reference in manifest.artifacts:
            if reference.retrieval_status is not RetrievalStatus.CAPTURED:
                raise GitHubProcessError("process capture contains a non-captured resource")
            if reference.media_type not in {ISSUE_MEDIA_TYPE, PULL_MEDIA_TYPE}:
                raise GitHubProcessError("capture contains a non-process artifact")
            artifact = self.store.get(Artifact, reference.artifact_id)
            if artifact is None:
                raise GitHubProcessError("process manifest references a missing Artifact")
            if (
                artifact.capture_id != manifest.capture_id
                or artifact.content_hash != reference.content_hash
                or artifact.media_type != reference.media_type
                or artifact.source_locator != reference.source_locator
            ):
                raise GitHubProcessError("process Artifact disagrees with CaptureManifest")

            data = self.object_store.get(artifact.content_hash)
            try:
                document = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GitHubProcessError("captured process snapshot is not canonical UTF-8 JSON") from exc
            if not isinstance(document, Mapping):
                raise GitHubProcessError("captured process snapshot must be a JSON object")
            expected_type = (
                ProcessKind.ISSUE.value
                if artifact.media_type == ISSUE_MEDIA_TYPE
                else ProcessKind.PULL_REQUEST.value
            )
            if document.get("resource_type") != expected_type:
                raise GitHubProcessError("process media type disagrees with resource_type")

            for key in self._FACT_KEYS:
                if key not in document:
                    continue
                fact_index += 1
                value = document[key]
                facts.append(
                    EvidenceFact(
                        evidence_id=self._record_id("fact", run_id, fact_index, artifact.source_locator, key),
                        artifact_id=artifact.artifact_id,
                        locator=f"{artifact.source_locator}#/{key}",
                        raw_value=value,
                        normalized_value=value,
                        extractor_name="github-process-metadata",
                        extractor_version="1",
                        run_id=run_id,
                    )
                )

            for ref_name in ("head", "base"):
                ref_value = document.get(ref_name)
                if not isinstance(ref_value, Mapping):
                    continue
                for key in ("ref", "sha", "repository_full_name"):
                    if key not in ref_value:
                        continue
                    fact_index += 1
                    value = ref_value[key]
                    facts.append(
                        EvidenceFact(
                            evidence_id=self._record_id(
                                "fact", run_id, fact_index, artifact.source_locator, f"{ref_name}/{key}"
                            ),
                            artifact_id=artifact.artifact_id,
                            locator=f"{artifact.source_locator}#/{ref_name}/{key}",
                            raw_value=value,
                            normalized_value=value,
                            extractor_name="github-process-metadata",
                            extractor_version="1",
                            run_id=run_id,
                        )
                    )

            title = document.get("title")
            if not isinstance(title, str) or not title.strip():
                raise GitHubProcessError("captured process snapshot omitted title")
            assertion_index += 1
            assertions.append(
                SourceAssertion(
                    assertion_id=self._record_id(
                        "assertion", run_id, assertion_index, artifact.source_locator, "title"
                    ),
                    artifact_id=artifact.artifact_id,
                    locator=f"{artifact.source_locator}#title",
                    statement=title,
                    extractor_name="github-process-authored-text",
                    extractor_version="1",
                    run_id=run_id,
                )
            )
            body = document.get("body")
            if body is not None:
                if not isinstance(body, str):
                    raise GitHubProcessError("captured process body has invalid type")
                if body.strip():
                    assertion_index += 1
                    assertions.append(
                        SourceAssertion(
                            assertion_id=self._record_id(
                                "assertion", run_id, assertion_index, artifact.source_locator, "body"
                            ),
                            artifact_id=artifact.artifact_id,
                            locator=f"{artifact.source_locator}#body",
                            statement=body,
                            extractor_name="github-process-authored-text",
                            extractor_version="1",
                            run_id=run_id,
                        )
                    )

        inputs_hash = self._digest_json(
            {
                "capture_id": manifest.capture_id,
                "source_revision_id": revision.source_revision_id,
                "artifacts": [
                    {
                        "artifact_id": ref.artifact_id,
                        "content_hash": ref.content_hash,
                        "source_locator": ref.source_locator,
                    }
                    for ref in manifest.artifacts
                ],
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "facts": [
                    {"locator": fact.locator, "normalized_value": fact.normalized_value}
                    for fact in facts
                ],
                "assertions": [
                    {"locator": item.locator, "statement": item.statement}
                    for item in assertions
                ],
            }
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
        result = GitHubProcessExtractionResult(
            manifest.capture_id,
            tuple(facts),
            tuple(assertions),
            run,
        )
        self.store.put_many(result.records())
        return result

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GitHub process extraction clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _record_id(kind: str, run_id: str, index: int, locator: str, key: str) -> str:
        material = f"github-process\0{kind}\0{run_id}\0{index}\0{locator}\0{key}".encode("utf-8")
        return f"{kind}:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
