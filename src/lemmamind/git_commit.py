"""Deterministic capture and extraction of exact Git commit metadata evidence."""
from __future__ import annotations

import hashlib
import json
import re
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
    SourceAssertion,
    SourceRevision,
)
from .github import GitHubRESTReader
from .objects import ContentAddressedFileStore

GIT_COMMIT_MEDIA_TYPE = "application/vnd.lemmamind.git-commit+json"
GIT_COMMIT_LOCATOR = "$git/commit"
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class GitCommitError(RuntimeError):
    """Commit source data is malformed or inconsistent with the pinned revision."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class GitCommitCaptureResult:
    manifest: CaptureManifest
    artifact: Artifact
    run: PipelineRun

    def records(self) -> tuple:
        return (self.artifact, self.manifest, self.run)


@dataclass(frozen=True)
class GitCommitExtractionResult:
    capture_id: str
    facts: tuple[EvidenceFact, ...]
    assertions: tuple[SourceAssertion, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.facts, *self.assertions, self.run)


class GitHubCommitCaptureService:
    """Capture a canonical immutable subset of one persisted SourceRevision commit."""

    def __init__(
        self,
        reader: GitHubRESTReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.commit-metadata.v1",
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

    def capture_commit(self, source_revision_id: str) -> GitCommitCaptureResult:
        started_at = self._aware_now()
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise KeyError(f"unknown source revision: {source_revision_id}")
        repository = self.store.get(RepositoryIdentity, revision.source_id)
        if repository is None:
            raise KeyError(f"unknown repository identity: {revision.source_id}")

        payload = self.reader.get_commit(repository.owner, repository.name, revision.commit_sha)
        canonical = self._canonical_commit(payload, revision=revision)
        data = (json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        content_hash = self.object_store.put(data)
        capture_id = f"capture-commit:{self.id_factory()}"
        artifact_id = self._artifact_id(capture_id, revision.commit_sha)
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=GIT_COMMIT_LOCATOR,
            content_hash=content_hash,
            media_type=GIT_COMMIT_MEDIA_TYPE,
        )
        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision.source_revision_id,
            capture_policy_version=self.capture_policy_version,
            captured_at=self._aware_now(),
            artifacts=(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=GIT_COMMIT_LOCATOR,
                    content_hash=content_hash,
                    media_type=GIT_COMMIT_MEDIA_TYPE,
                    retrieval_status=RetrievalStatus.CAPTURED,
                ),
            ),
        )
        inputs_hash = self._digest_json(
            {
                "source_revision_id": revision.source_revision_id,
                "commit_sha": revision.commit_sha,
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
        result = GitCommitCaptureResult(manifest, artifact, run)
        self.store.put_many(result.records())
        return result

    @classmethod
    def _canonical_commit(
        cls, payload: Mapping[str, Any], *, revision: SourceRevision
    ) -> dict[str, Any]:
        commit_sha = payload.get("sha")
        if commit_sha != revision.commit_sha:
            raise GitCommitError(
                f"commit SHA mismatch: expected {revision.commit_sha}, received {commit_sha!r}"
            )
        commit = payload.get("commit")
        if not isinstance(commit, Mapping):
            raise GitCommitError("GitHub commit response omitted commit metadata")
        tree = commit.get("tree")
        tree_sha = tree.get("sha") if isinstance(tree, Mapping) else None
        if tree_sha != revision.tree_sha:
            raise GitCommitError(
                f"commit tree mismatch: expected {revision.tree_sha}, received {tree_sha!r}"
            )
        message = commit.get("message")
        if not isinstance(message, str) or not message.strip():
            raise GitCommitError("GitHub commit response omitted commit message")

        parents_raw = payload.get("parents")
        if not isinstance(parents_raw, list):
            raise GitCommitError("GitHub commit response omitted parent list")
        parents: list[str] = []
        for parent in parents_raw:
            sha = parent.get("sha") if isinstance(parent, Mapping) else None
            if not isinstance(sha, str) or _GIT_SHA.fullmatch(sha) is None:
                raise GitCommitError("GitHub commit response contains invalid parent SHA")
            parents.append(sha)

        author = commit.get("author")
        committer = commit.get("committer")
        author_date = author.get("date") if isinstance(author, Mapping) else None
        committer_date = committer.get("date") if isinstance(committer, Mapping) else None
        if not isinstance(author_date, str) or not author_date:
            raise GitCommitError("GitHub commit response omitted author timestamp")
        if not isinstance(committer_date, str) or not committer_date:
            raise GitCommitError("GitHub commit response omitted committer timestamp")

        verification_raw = commit.get("verification")
        verification: dict[str, Any] | None = None
        if isinstance(verification_raw, Mapping):
            verified = verification_raw.get("verified")
            reason = verification_raw.get("reason")
            verified_at = verification_raw.get("verified_at")
            if isinstance(verified, bool):
                verification = {"verified": verified}
                if isinstance(reason, str) and reason:
                    verification["reason"] = reason
                if isinstance(verified_at, str) and verified_at:
                    verification["verified_at"] = verified_at

        canonical: dict[str, Any] = {
            "commit_sha": revision.commit_sha,
            "tree_sha": revision.tree_sha,
            "parents": parents,
            "author_timestamp": author_date,
            "committer_timestamp": committer_date,
            "message": message,
        }
        if verification is not None:
            canonical["verification"] = verification
        return canonical

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("commit capture clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _artifact_id(capture_id: str, commit_sha: str) -> str:
        material = f"{capture_id}\0{commit_sha}\0commit-metadata".encode("utf-8")
        return f"artifact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


class GitCommitEvidenceService:
    """Emit deterministic commit facts and preserve the commit message as a source assertion."""

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "git-commit-evidence.v1",
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

    def extract_commit(self, capture_id: str) -> GitCommitExtractionResult:
        started_at = self._aware_now()
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")
        if len(manifest.artifacts) != 1:
            raise GitCommitError("commit capture must contain exactly one artifact")
        reference = manifest.artifacts[0]
        if (
            reference.retrieval_status is not RetrievalStatus.CAPTURED
            or reference.media_type != GIT_COMMIT_MEDIA_TYPE
            or reference.source_locator != GIT_COMMIT_LOCATOR
        ):
            raise GitCommitError("capture is not a canonical commit-metadata capture")
        artifact = self.store.get(Artifact, reference.artifact_id)
        if artifact is None:
            raise GitCommitError("commit manifest references a missing Artifact")
        if (
            artifact.capture_id != manifest.capture_id
            or artifact.content_hash != reference.content_hash
            or artifact.media_type != GIT_COMMIT_MEDIA_TYPE
            or artifact.source_locator != GIT_COMMIT_LOCATOR
        ):
            raise GitCommitError("commit Artifact disagrees with CaptureManifest")
        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise GitCommitError("commit capture references a missing SourceRevision")

        data = self.object_store.get(artifact.content_hash)
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitCommitError("captured commit metadata is not canonical UTF-8 JSON") from exc
        if not isinstance(document, Mapping):
            raise GitCommitError("captured commit metadata must be a JSON object")
        if document.get("commit_sha") != revision.commit_sha:
            raise GitCommitError("captured commit no longer matches SourceRevision.commit_sha")
        if document.get("tree_sha") != revision.tree_sha:
            raise GitCommitError("captured commit no longer matches SourceRevision.tree_sha")

        run_id = f"run:{self.id_factory()}"
        facts_spec: list[tuple[str, Any]] = [
            ("commit_sha", document["commit_sha"]),
            ("tree_sha", document["tree_sha"]),
            ("parents", document.get("parents", [])),
            ("parent_count", len(document.get("parents", []))),
            ("author_timestamp", document["author_timestamp"]),
            ("committer_timestamp", document["committer_timestamp"]),
        ]
        verification = document.get("verification")
        if isinstance(verification, Mapping):
            if "verified" in verification:
                facts_spec.append(("verification/verified", verification["verified"]))
            if "reason" in verification:
                facts_spec.append(("verification/reason", verification["reason"]))
            if "verified_at" in verification:
                facts_spec.append(("verification/verified_at", verification["verified_at"]))

        facts = tuple(
            EvidenceFact(
                evidence_id=self._record_id("fact", run_id, index, key),
                artifact_id=artifact.artifact_id,
                locator=f"{GIT_COMMIT_LOCATOR}#/{key}",
                raw_value=value,
                normalized_value=value,
                extractor_name="git-commit-metadata",
                extractor_version="1",
                run_id=run_id,
            )
            for index, (key, value) in enumerate(facts_spec, start=1)
        )
        message = document.get("message")
        if not isinstance(message, str) or not message.strip():
            raise GitCommitError("captured commit metadata omitted message")
        assertions = (
            SourceAssertion(
                assertion_id=self._record_id("assertion", run_id, 1, "message"),
                artifact_id=artifact.artifact_id,
                locator=f"{GIT_COMMIT_LOCATOR}#message",
                statement=message,
                extractor_name="git-commit-message",
                extractor_version="1",
                run_id=run_id,
            ),
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
            {
                "facts": [
                    {
                        "locator": fact.locator,
                        "normalized_value": fact.normalized_value,
                        "extractor_name": fact.extractor_name,
                        "extractor_version": fact.extractor_version,
                    }
                    for fact in facts
                ],
                "assertions": [
                    {
                        "locator": assertion.locator,
                        "statement": assertion.statement,
                        "extractor_name": assertion.extractor_name,
                        "extractor_version": assertion.extractor_version,
                    }
                    for assertion in assertions
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
        result = GitCommitExtractionResult(capture_id, facts, assertions, run)
        self.store.put_many(result.records())
        return result

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("commit extraction clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _record_id(kind: str, run_id: str, index: int, key: str) -> str:
        material = f"git-commit\0{kind}\0{run_id}\0{index}\0{key}".encode("utf-8")
        return f"{kind}:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
