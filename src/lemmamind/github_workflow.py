"""Durable deterministic GitHub Actions workflow-run evidence.

A workflow run is captured as one immutable content-addressed snapshot containing
run metadata, jobs, steps, artifact metadata, and per-job log availability. Log
*contents* are intentionally not captured in v1. The run's explicit ``head_sha``
is required to match the persisted SourceRevision anchor.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

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
from .github import GitHubAPIError, GitHubRESTReader
from .objects import ContentAddressedFileStore

WORKFLOW_RUN_MEDIA_TYPE = "application/vnd.lemmamind.github-workflow-run+json"


class GitHubWorkflowError(RuntimeError):
    """Workflow-run data is malformed or inconsistent with the capture request."""


class GitHubWorkflowReader(Protocol):
    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Mapping[str, Any]: ...

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int) -> Mapping[str, Any]: ...

    def get_workflow_artifacts(self, owner: str, repo: str, run_id: int) -> Mapping[str, Any]: ...

    def probe_job_log(self, owner: str, repo: str, job_id: int) -> Mapping[str, Any]: ...


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


class GitHubWorkflowRESTReader(GitHubRESTReader):
    """Read-only REST reader for workflow runs, jobs, artifacts, and log availability."""

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Mapping[str, Any]:
        payload = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/actions/runs/{run_id}"
        )
        if not isinstance(payload, Mapping):
            raise GitHubWorkflowError("workflow-run response must be a JSON object")
        return payload

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int) -> Mapping[str, Any]:
        payload = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/actions/runs/{run_id}/jobs",
            {"per_page": "100"},
        )
        if not isinstance(payload, Mapping):
            raise GitHubWorkflowError("workflow jobs response must be a JSON object")
        return payload

    def get_workflow_artifacts(self, owner: str, repo: str, run_id: int) -> Mapping[str, Any]:
        payload = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/actions/runs/{run_id}/artifacts",
            {"per_page": "100"},
        )
        if not isinstance(payload, Mapping):
            raise GitHubWorkflowError("workflow artifacts response must be a JSON object")
        return payload

    def probe_job_log(self, owner: str, repo: str, job_id: int) -> Mapping[str, Any]:
        """Probe availability only; never retain or parse log bytes."""

        path = (
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
            f"/actions/jobs/{job_id}/logs"
        )
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        try:
            response = urlopen(request, timeout=self.timeout)  # noqa: S310
            try:
                status = int(getattr(response, "status", 200))
                final_url = str(response.geturl())
            finally:
                response.close()
            return {
                "availability": "available",
                "http_status": status,
                "redirected": final_url != url,
            }
        except HTTPError as exc:
            if exc.code == 404:
                return {
                    "availability": "missing",
                    "http_status": 404,
                    "redirected": False,
                }
            raise GitHubAPIError(
                f"GitHub job-log probe failed with HTTP {exc.code}",
                status_code=exc.code,
            ) from exc


@dataclass(frozen=True)
class GitHubWorkflowCaptureResult:
    manifest: CaptureManifest
    artifact: Artifact
    run: PipelineRun

    def records(self) -> tuple:
        return (self.artifact, self.manifest, self.run)


@dataclass(frozen=True)
class GitHubWorkflowExtractionResult:
    capture_id: str
    facts: tuple[EvidenceFact, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.facts, self.run)


class GitHubWorkflowCaptureService:
    """Capture one exact workflow-run snapshot under an explicit SourceRevision."""

    def __init__(
        self,
        reader: GitHubWorkflowReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.workflow-run-snapshot.v1",
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

    def capture_run(self, source_revision_id: str, run_id: int) -> GitHubWorkflowCaptureResult:
        if run_id < 1:
            raise ValueError("workflow run_id must be positive")
        started_at = self._aware_now()
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise KeyError(f"unknown source revision: {source_revision_id}")
        repository = self.store.get(RepositoryIdentity, revision.source_id)
        if repository is None:
            raise KeyError(f"unknown repository identity: {revision.source_id}")

        run_payload = self.reader.get_workflow_run(repository.owner, repository.name, run_id)
        canonical_run = self._canonical_run(
            run_payload,
            repository_full_name=f"{repository.owner}/{repository.name}",
            expected_run_id=run_id,
        )
        if canonical_run["head_sha"] != revision.commit_sha:
            raise GitHubWorkflowError(
                "workflow run head_sha does not match SourceRevision.commit_sha: "
                f"{canonical_run['head_sha']} != {revision.commit_sha}"
            )

        jobs_payload = self.reader.get_workflow_jobs(repository.owner, repository.name, run_id)
        jobs = self._canonical_jobs(jobs_payload, expected_run_id=run_id)
        log_status_by_job: dict[int, Mapping[str, Any]] = {}
        for job in jobs:
            job_id = int(job["id"])
            log_status_by_job[job_id] = self._canonical_log_probe(
                self.reader.probe_job_log(repository.owner, repository.name, job_id)
            )
        jobs = [
            {**job, "log": dict(log_status_by_job[int(job["id"])])}
            for job in jobs
        ]

        artifacts_payload = self.reader.get_workflow_artifacts(
            repository.owner, repository.name, run_id
        )
        artifacts = self._canonical_artifacts(artifacts_payload)

        snapshot = {
            "resource_type": "workflow_run",
            "repository_full_name": f"{repository.owner}/{repository.name}",
            "analysis_anchor_source_revision_id": revision.source_revision_id,
            "run": canonical_run,
            "jobs": jobs,
            "job_count": len(jobs),
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
        }
        data = (
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        content_hash = self.object_store.put(data)
        capture_id = f"capture-workflow:{self.id_factory()}"
        locator = f"$github/actions/run/{run_id}"
        artifact_id = self._artifact_id(capture_id, run_id)
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=locator,
            content_hash=content_hash,
            media_type=WORKFLOW_RUN_MEDIA_TYPE,
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
                    media_type=WORKFLOW_RUN_MEDIA_TYPE,
                    retrieval_status=RetrievalStatus.CAPTURED,
                ),
            ),
        )
        inputs_hash = self._digest_json(
            {
                "source_revision_id": revision.source_revision_id,
                "run_id": run_id,
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
        pipeline_run = PipelineRun(
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
        result = GitHubWorkflowCaptureResult(manifest, artifact, pipeline_run)
        self.store.put_many(result.records())
        return result

    @classmethod
    def _canonical_run(
        cls,
        payload: Mapping[str, Any],
        *,
        repository_full_name: str,
        expected_run_id: int,
    ) -> dict[str, Any]:
        run_id = cls._required_int(payload, "id")
        if run_id != expected_run_id:
            raise GitHubWorkflowError(
                f"workflow run id mismatch: expected {expected_run_id}, received {run_id}"
            )
        repository = payload.get("repository")
        if isinstance(repository, Mapping):
            actual_name = repository.get("full_name")
            if isinstance(actual_name, str) and actual_name != repository_full_name:
                raise GitHubWorkflowError(
                    f"workflow run repository mismatch: {actual_name} != {repository_full_name}"
                )
        pull_numbers: list[int] = []
        pulls = payload.get("pull_requests", [])
        if pulls is None:
            pulls = []
        if not isinstance(pulls, list):
            raise GitHubWorkflowError("workflow run pull_requests must be a list")
        for pull in pulls:
            if not isinstance(pull, Mapping):
                raise GitHubWorkflowError("workflow pull_requests entries must be objects")
            pull_numbers.append(cls._required_int(pull, "number"))
        return {
            "id": run_id,
            "name": cls._required_string(payload, "name"),
            "path": cls._required_string(payload, "path"),
            "display_title": cls._required_string(payload, "display_title"),
            "run_number": cls._required_int(payload, "run_number"),
            "event": cls._required_string(payload, "event"),
            "status": cls._required_string(payload, "status"),
            "conclusion": cls._optional_string(payload.get("conclusion")),
            "workflow_id": cls._required_int(payload, "workflow_id"),
            "check_suite_id": cls._required_int(payload, "check_suite_id"),
            "head_branch": cls._optional_string(payload.get("head_branch")),
            "head_sha": cls._required_string(payload, "head_sha"),
            "run_attempt": cls._required_int(payload, "run_attempt"),
            "created_at": cls._required_string(payload, "created_at"),
            "updated_at": cls._required_string(payload, "updated_at"),
            "run_started_at": cls._required_string(payload, "run_started_at"),
            "pull_request_numbers": sorted(set(pull_numbers)),
        }

    @classmethod
    def _canonical_jobs(
        cls, payload: Mapping[str, Any], *, expected_run_id: int
    ) -> list[dict[str, Any]]:
        total = cls._required_int(payload, "total_count")
        raw_jobs = payload.get("jobs")
        if not isinstance(raw_jobs, list):
            raise GitHubWorkflowError("workflow jobs payload omitted jobs")
        if total != len(raw_jobs):
            raise GitHubWorkflowError(
                "workflow jobs pagination would make the snapshot incomplete: "
                f"total_count={total}, captured={len(raw_jobs)}"
            )
        jobs: list[dict[str, Any]] = []
        for raw in raw_jobs:
            if not isinstance(raw, Mapping):
                raise GitHubWorkflowError("workflow job entry must be an object")
            if cls._required_int(raw, "run_id") != expected_run_id:
                raise GitHubWorkflowError("workflow job run_id disagrees with requested run")
            raw_steps = raw.get("steps", [])
            if raw_steps is None:
                raw_steps = []
            if not isinstance(raw_steps, list):
                raise GitHubWorkflowError("workflow job steps must be a list or null")
            steps: list[dict[str, Any]] = []
            seen_numbers: set[int] = set()
            for step in raw_steps:
                if not isinstance(step, Mapping):
                    raise GitHubWorkflowError("workflow step must be an object")
                number = cls._required_int(step, "number")
                if number in seen_numbers:
                    raise GitHubWorkflowError("workflow job has duplicate step numbers")
                seen_numbers.add(number)
                steps.append(
                    {
                        "number": number,
                        "name": cls._required_string(step, "name"),
                        "status": cls._required_string(step, "status"),
                        "conclusion": cls._optional_string(step.get("conclusion")),
                        "started_at": cls._optional_string(step.get("started_at")),
                        "completed_at": cls._optional_string(step.get("completed_at")),
                    }
                )
            steps.sort(key=lambda item: int(item["number"]))
            jobs.append(
                {
                    "id": cls._required_int(raw, "id"),
                    "name": cls._required_string(raw, "name"),
                    "status": cls._required_string(raw, "status"),
                    "conclusion": cls._optional_string(raw.get("conclusion")),
                    "run_attempt": cls._required_int(raw, "run_attempt"),
                    "head_sha": cls._required_string(raw, "head_sha"),
                    "created_at": cls._required_string(raw, "created_at"),
                    "started_at": cls._required_string(raw, "started_at"),
                    "completed_at": cls._required_string(raw, "completed_at"),
                    "labels": cls._string_list(raw.get("labels"), field="labels"),
                    "runner_id": cls._optional_int(raw.get("runner_id")),
                    "runner_name": cls._optional_string(raw.get("runner_name")),
                    "runner_group_id": cls._optional_int(raw.get("runner_group_id")),
                    "runner_group_name": cls._optional_string(raw.get("runner_group_name")),
                    "steps": steps,
                    "step_count": len(steps),
                }
            )
        jobs.sort(key=lambda item: int(item["id"]))
        return jobs

    @classmethod
    def _canonical_artifacts(cls, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        raw = payload.get("artifacts")
        if not isinstance(raw, list):
            raise GitHubWorkflowError("workflow artifacts payload omitted artifacts")
        total = payload.get("total_count", len(raw))
        if not isinstance(total, int) or isinstance(total, bool):
            raise GitHubWorkflowError("workflow artifacts total_count must be an integer")
        if total != len(raw):
            raise GitHubWorkflowError(
                "workflow artifacts pagination would make the snapshot incomplete: "
                f"total_count={total}, captured={len(raw)}"
            )
        artifacts: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise GitHubWorkflowError("workflow artifact entry must be an object")
            artifacts.append(
                {
                    "id": cls._required_int(item, "id"),
                    "name": cls._required_string(item, "name"),
                    "size_in_bytes": cls._required_int(item, "size_in_bytes"),
                    "expired": cls._required_bool(item, "expired"),
                    "created_at": cls._required_string(item, "created_at"),
                    "updated_at": cls._required_string(item, "updated_at"),
                    "expires_at": cls._required_string(item, "expires_at"),
                }
            )
        artifacts.sort(key=lambda item: int(item["id"]))
        return artifacts

    @classmethod
    def _canonical_log_probe(cls, value: Mapping[str, Any]) -> dict[str, Any]:
        availability = cls._required_string(value, "availability")
        if availability not in {"available", "missing"}:
            raise GitHubWorkflowError(f"unsupported job-log availability: {availability}")
        return {
            "availability": availability,
            "http_status": cls._required_int(value, "http_status"),
            "redirected": cls._required_bool(value, "redirected"),
        }

    @staticmethod
    def _required_string(mapping: Mapping[str, Any], key: str) -> str:
        value = mapping.get(key)
        if not isinstance(value, str) or not value.strip():
            raise GitHubWorkflowError(f"GitHub workflow response omitted {key}")
        return value.strip()

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise GitHubWorkflowError("optional GitHub workflow string has invalid type")
        return value

    @staticmethod
    def _required_int(mapping: Mapping[str, Any], key: str) -> int:
        value = mapping.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise GitHubWorkflowError(f"GitHub workflow response omitted integer {key}")
        return value

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise GitHubWorkflowError("optional GitHub workflow integer has invalid type")
        return value

    @staticmethod
    def _required_bool(mapping: Mapping[str, Any], key: str) -> bool:
        value = mapping.get(key)
        if not isinstance(value, bool):
            raise GitHubWorkflowError(f"GitHub workflow response omitted boolean {key}")
        return value

    @classmethod
    def _string_list(cls, value: Any, *, field: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise GitHubWorkflowError(f"workflow {field} must be a string list")
        return sorted(set(value))

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GitHub workflow capture clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _artifact_id(capture_id: str, run_id: int) -> str:
        material = f"{capture_id}\0workflow-run\0{run_id}".encode("utf-8")
        return f"artifact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


class GitHubWorkflowEvidenceService:
    """Emit deterministic leaf facts from one captured workflow-run snapshot."""

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "github-workflow-evidence.v1",
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

    def extract_run(self, capture_id: str) -> GitHubWorkflowExtractionResult:
        started_at = self._aware_now()
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")
        if len(manifest.artifacts) != 1:
            raise GitHubWorkflowError("workflow capture must contain exactly one artifact")
        reference = manifest.artifacts[0]
        if (
            reference.retrieval_status is not RetrievalStatus.CAPTURED
            or reference.media_type != WORKFLOW_RUN_MEDIA_TYPE
        ):
            raise GitHubWorkflowError("capture is not a captured workflow-run artifact")
        artifact = self.store.get(Artifact, reference.artifact_id)
        if artifact is None:
            raise GitHubWorkflowError("workflow manifest references a missing Artifact")
        if (
            artifact.capture_id != manifest.capture_id
            or artifact.source_locator != reference.source_locator
            or artifact.content_hash != reference.content_hash
            or artifact.media_type != reference.media_type
        ):
            raise GitHubWorkflowError("workflow Artifact disagrees with CaptureManifest")
        data = self.object_store.get(artifact.content_hash)
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubWorkflowError("workflow snapshot is not canonical UTF-8 JSON") from exc
        if not isinstance(document, Mapping) or document.get("resource_type") != "workflow_run":
            raise GitHubWorkflowError("workflow snapshot has invalid resource_type")

        run_id = f"run:{self.id_factory()}"
        facts: list[EvidenceFact] = []
        index = 0

        def emit(locator: str, value: Any) -> None:
            nonlocal index
            index += 1
            facts.append(
                EvidenceFact(
                    evidence_id=self._record_id(run_id, index, locator),
                    artifact_id=artifact.artifact_id,
                    locator=locator,
                    raw_value=value,
                    normalized_value=value,
                    extractor_name="github-workflow-metadata",
                    extractor_version="1",
                    run_id=run_id,
                )
            )

        root = artifact.source_locator
        run = document.get("run")
        if not isinstance(run, Mapping):
            raise GitHubWorkflowError("workflow snapshot omitted run object")
        for key in (
            "id", "name", "path", "display_title", "run_number", "event", "status",
            "conclusion", "workflow_id", "check_suite_id", "head_branch", "head_sha",
            "run_attempt", "created_at", "updated_at", "run_started_at", "pull_request_numbers",
        ):
            if key in run:
                emit(f"{root}#/run/{key}", run[key])
        emit(f"{root}#/job_count", document.get("job_count"))
        emit(f"{root}#/artifact_count", document.get("artifact_count"))

        jobs = document.get("jobs")
        if not isinstance(jobs, list):
            raise GitHubWorkflowError("workflow snapshot omitted jobs")
        for job in jobs:
            if not isinstance(job, Mapping):
                raise GitHubWorkflowError("workflow snapshot job must be an object")
            job_id = GitHubWorkflowCaptureService._required_int(job, "id")
            job_root = f"{root}#/jobs/{job_id}"
            for key in (
                "id", "name", "status", "conclusion", "run_attempt", "head_sha",
                "created_at", "started_at", "completed_at", "labels", "runner_id",
                "runner_name", "runner_group_id", "runner_group_name", "step_count",
            ):
                if key in job:
                    emit(f"{job_root}/{key}", job[key])
            log = job.get("log")
            if not isinstance(log, Mapping):
                raise GitHubWorkflowError("workflow snapshot job omitted log probe")
            for key in ("availability", "http_status", "redirected"):
                emit(f"{job_root}/log/{key}", log.get(key))
            steps = job.get("steps")
            if not isinstance(steps, list):
                raise GitHubWorkflowError("workflow snapshot job omitted steps")
            for step in steps:
                if not isinstance(step, Mapping):
                    raise GitHubWorkflowError("workflow snapshot step must be an object")
                number = GitHubWorkflowCaptureService._required_int(step, "number")
                step_root = f"{job_root}/steps/{number}"
                for key in ("number", "name", "status", "conclusion", "started_at", "completed_at"):
                    if key in step:
                        emit(f"{step_root}/{key}", step[key])

        artifacts = document.get("artifacts")
        if not isinstance(artifacts, list):
            raise GitHubWorkflowError("workflow snapshot omitted artifacts")
        for item in artifacts:
            if not isinstance(item, Mapping):
                raise GitHubWorkflowError("workflow snapshot artifact must be an object")
            item_id = GitHubWorkflowCaptureService._required_int(item, "id")
            item_root = f"{root}#/artifacts/{item_id}"
            for key in ("id", "name", "size_in_bytes", "expired", "created_at", "updated_at", "expires_at"):
                if key in item:
                    emit(f"{item_root}/{key}", item[key])

        inputs_hash = GitHubWorkflowCaptureService._digest_json(
            {
                "capture_id": manifest.capture_id,
                "source_revision_id": manifest.source_revision_id,
                "artifact_id": artifact.artifact_id,
                "content_hash": artifact.content_hash,
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = GitHubWorkflowCaptureService._digest_json(
            [
                {"locator": fact.locator, "normalized_value": fact.normalized_value}
                for fact in facts
            ]
        )
        pipeline_run = PipelineRun(
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
        result = GitHubWorkflowExtractionResult(manifest.capture_id, tuple(facts), pipeline_run)
        self.store.put_many(result.records())
        return result

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GitHub workflow extraction clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _record_id(run_id: str, index: int, locator: str) -> str:
        material = f"github-workflow\0{run_id}\0{index}\0{locator}".encode("utf-8")
        return f"fact:{hashlib.sha256(material).hexdigest()}"
