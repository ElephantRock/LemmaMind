from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    PipelineRun,
    RepositoryIdentity,
    RunType,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
)
from lemmamind.github_workflow import (
    GitHubWorkflowCaptureService,
    GitHubWorkflowError,
    GitHubWorkflowEvidenceService,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 15, 10, tzinfo=timezone.utc)
HEAD_SHA = "6" * 40
TREE_SHA = "7" * 40


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"workflow-{self.value}"


class FakeWorkflowReader:
    def __init__(self, *, pre_step_failure: bool = False) -> None:
        self.pre_step_failure = pre_step_failure

    def get_workflow_run(self, owner: str, repo: str, run_id: int):
        assert (owner, repo, run_id) == ("ElephantRock", "Resonance-World", 31895957256)
        return {
            "id": run_id,
            "name": "D2 Confirmatory Campaign",
            "path": ".github/workflows/d2-confirmatory.yml",
            "display_title": "D2: authorize frozen confirmatory campaign",
            "run_number": 1,
            "event": "push",
            "status": "completed",
            "conclusion": "failure" if self.pre_step_failure else "cancelled",
            "workflow_id": 335121764,
            "check_suite_id": 86514229967,
            "head_branch": "experiment/d2-confirmatory",
            "head_sha": HEAD_SHA,
            "run_attempt": 1,
            "created_at": "2026-08-15T16:36:09Z",
            "updated_at": "2026-08-15T21:36:29Z",
            "run_started_at": "2026-08-15T16:36:09Z",
            "pull_requests": [{"number": 177}],
            "repository": {"full_name": "ElephantRock/Resonance-World"},
        }

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int):
        if self.pre_step_failure:
            return {
                "total_count": 2,
                "jobs": [
                    self._job(9001, "test", "failure", steps=None),
                    self._job(9002, "compile", "failure", steps=None),
                ],
            }
        return {
            "total_count": 2,
            "jobs": [
                self._job(
                    95039193643,
                    "provider-confirmatory-campaign",
                    "cancelled",
                    steps=[
                        self._step(1, "Set up job", "success", "16:36:13", "16:36:14"),
                        self._step(
                            6,
                            "Execute frozen provider campaign",
                            "cancelled",
                            "16:36:24",
                            "21:36:25",
                        ),
                        self._step(
                            8,
                            "Run actions/upload-artifact@v4",
                            "skipped",
                            "21:36:25",
                            "21:36:25",
                        ),
                    ],
                ),
                self._job(95039193963, "registry-promotion-disabled", "skipped", steps=[]),
            ],
        }

    def get_workflow_artifacts(self, owner: str, repo: str, run_id: int):
        return {"total_count": 0, "artifacts": []}

    def probe_job_log(self, owner: str, repo: str, job_id: int):
        if self.pre_step_failure:
            return {"availability": "missing", "http_status": 404, "redirected": False}
        if job_id == 95039193643:
            return {"availability": "available", "http_status": 200, "redirected": True}
        return {"availability": "missing", "http_status": 404, "redirected": False}

    @staticmethod
    def _job(job_id: int, name: str, conclusion: str, *, steps):
        return {
            "id": job_id,
            "run_id": 31895957256,
            "run_attempt": 1,
            "head_sha": HEAD_SHA,
            "name": name,
            "status": "completed",
            "conclusion": conclusion,
            "created_at": "2026-08-15T16:36:09Z",
            "started_at": "2026-08-15T16:36:12Z",
            "completed_at": "2026-08-15T21:36:28Z",
            "labels": ["ubuntu-latest"],
            "runner_id": 1 if steps else None,
            "runner_name": "GitHub Actions 1" if steps else None,
            "runner_group_id": 0 if steps else None,
            "runner_group_name": "GitHub Actions" if steps else None,
            "steps": steps,
        }

    @staticmethod
    def _step(number: int, name: str, conclusion: str, start: str, end: str):
        return {
            "number": number,
            "name": name,
            "status": "completed",
            "conclusion": conclusion,
            "started_at": f"2026-08-15T{start}Z",
            "completed_at": f"2026-08-15T{end}Z",
        }


def build_store(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source = Source(
        source_id="github:resonance-world",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/ElephantRock/Resonance-World",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    repository = RepositoryIdentity(
        source_id=source.source_id,
        provider_repository_id="1330427174",
        owner="ElephantRock",
        name="Resonance-World",
        default_branch="main",
        aliases=(),
        archived=False,
    )
    revision = SourceRevision(
        source_revision_id=f"github:1330427174@{HEAD_SHA}",
        source_id=source.source_id,
        commit_sha=HEAD_SHA,
        tree_sha=TREE_SHA,
        observed_at=NOW,
    )
    store.put_many((source, repository, revision))
    return store, objects, revision


def services(tmp_path, reader=None):
    store, objects, revision = build_store(tmp_path)
    ids = DeterministicIds()
    reader = reader or FakeWorkflowReader()
    capture = GitHubWorkflowCaptureService(
        reader,
        store,
        objects,
        clock=lambda: NOW,
        id_factory=ids,
    )
    extraction = GitHubWorkflowEvidenceService(
        store,
        objects,
        clock=lambda: NOW,
        id_factory=ids,
    )
    return store, objects, revision, capture, extraction


def test_captures_cancelled_run_steps_log_availability_and_zero_artifacts(tmp_path) -> None:
    store, _, revision, capture, extraction = services(tmp_path)

    captured = capture.capture_run(revision.source_revision_id, 31895957256)
    extracted = extraction.extract_run(captured.manifest.capture_id)
    facts = {fact.locator: fact.normalized_value for fact in extracted.facts}
    root = "$github/actions/run/31895957256"

    assert facts[f"{root}#/run/conclusion"] == "cancelled"
    assert facts[f"{root}#/run/head_sha"] == HEAD_SHA
    assert facts[f"{root}#/artifact_count"] == 0
    assert facts[f"{root}#/job_count"] == 2
    assert facts[f"{root}#/jobs/95039193643/conclusion"] == "cancelled"
    assert facts[f"{root}#/jobs/95039193643/step_count"] == 3
    assert facts[f"{root}#/jobs/95039193643/log/availability"] == "available"
    assert facts[f"{root}#/jobs/95039193643/steps/6/name"] == "Execute frozen provider campaign"
    assert facts[f"{root}#/jobs/95039193643/steps/6/conclusion"] == "cancelled"
    assert facts[f"{root}#/jobs/95039193643/steps/6/started_at"] == "2026-08-15T16:36:24Z"
    assert facts[f"{root}#/jobs/95039193643/steps/6/completed_at"] == "2026-08-15T21:36:25Z"
    assert facts[f"{root}#/jobs/95039193643/steps/8/conclusion"] == "skipped"
    assert facts[f"{root}#/jobs/95039193963/step_count"] == 0
    assert captured.run.run_type is RunType.CAPTURE
    assert extracted.run.run_type is RunType.EXTRACTION
    assert len(store.list(PipelineRun)) == 2


def test_represents_pre_step_failure_without_calling_it_test_failure(tmp_path) -> None:
    reader = FakeWorkflowReader(pre_step_failure=True)
    _, _, revision, capture, extraction = services(tmp_path, reader=reader)

    captured = capture.capture_run(revision.source_revision_id, 31895957256)
    extracted = extraction.extract_run(captured.manifest.capture_id)
    facts = {fact.locator: fact.normalized_value for fact in extracted.facts}
    root = "$github/actions/run/31895957256"

    assert facts[f"{root}#/run/conclusion"] == "failure"
    assert facts[f"{root}#/jobs/9001/conclusion"] == "failure"
    assert facts[f"{root}#/jobs/9001/step_count"] == 0
    assert facts[f"{root}#/jobs/9001/log/availability"] == "missing"
    assert facts[f"{root}#/jobs/9002/step_count"] == 0
    assert not any("steps/" in locator for locator in facts)


def test_rejects_workflow_run_from_different_source_revision(tmp_path) -> None:
    _, _, revision, capture, _ = services(tmp_path)
    bad = FakeWorkflowReader()
    original = bad.get_workflow_run

    def mismatched(owner: str, repo: str, run_id: int):
        payload = dict(original(owner, repo, run_id))
        payload["head_sha"] = "9" * 40
        return payload

    bad.get_workflow_run = mismatched  # type: ignore[method-assign]
    capture.reader = bad

    with pytest.raises(GitHubWorkflowError, match="head_sha does not match"):
        capture.capture_run(revision.source_revision_id, 31895957256)


def test_fails_closed_on_incomplete_job_pagination(tmp_path) -> None:
    reader = FakeWorkflowReader()
    original = reader.get_workflow_jobs

    def incomplete(owner: str, repo: str, run_id: int):
        payload = dict(original(owner, repo, run_id))
        payload["total_count"] = 101
        return payload

    reader.get_workflow_jobs = incomplete  # type: ignore[method-assign]
    _, _, revision, capture, _ = services(tmp_path, reader=reader)

    with pytest.raises(GitHubWorkflowError, match="pagination"):
        capture.capture_run(revision.source_revision_id, 31895957256)
