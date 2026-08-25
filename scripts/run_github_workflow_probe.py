from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from lemmamind.contracts import SourceRole
from lemmamind.github import GitHubCaptureService, GitHubRESTReader
from lemmamind.github_workflow import (
    GitHubWorkflowCaptureService,
    GitHubWorkflowEvidenceService,
    GitHubWorkflowRESTReader,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

REPOSITORY = "ElephantRock/Resonance-World"
RUN_ID = 31895957256
HEAD_SHA = "65d739736070bbebe7941bebfbee785d33499c46"
WORKFLOW_PATH = ".github/workflows/d2-confirmatory.yml"
PROVIDER_JOB_ID = 95039193643


def run_probe(token: str | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="lemmamind-workflow-probe-") as directory:
        root = Path(directory)
        store = SQLiteContractStore(root / "lemmamind.db")
        objects = ContentAddressedFileStore(root / "objects")

        repository_reader = GitHubRESTReader(token=token)
        repository_capture = GitHubCaptureService(repository_reader, store, objects)
        anchored = repository_capture.capture_repository(
            REPOSITORY,
            [WORKFLOW_PATH],
            source_role=SourceRole.IMPLEMENTATION,
            ref=HEAD_SHA,
        )

        workflow_reader = GitHubWorkflowRESTReader(token=token)
        workflow_capture = GitHubWorkflowCaptureService(workflow_reader, store, objects)
        workflow_evidence = GitHubWorkflowEvidenceService(store, objects)
        captured = workflow_capture.capture_run(anchored.revision.source_revision_id, RUN_ID)
        extracted = workflow_evidence.extract_run(captured.manifest.capture_id)

        facts = {fact.locator: fact.normalized_value for fact in extracted.facts}
        base = f"$github/actions/run/{RUN_ID}"
        provider = f"{base}#/jobs/{PROVIDER_JOB_ID}"
        required = {
            f"{base}#/run/conclusion": "cancelled",
            f"{base}#/run/head_sha": HEAD_SHA,
            f"{base}#/job_count": 3,
            f"{base}#/artifact_count": 0,
            f"{provider}/conclusion": "cancelled",
            f"{provider}/steps/6/name": "Execute frozen provider campaign",
            f"{provider}/steps/6/conclusion": "cancelled",
            f"{provider}/steps/8/conclusion": "skipped",
            f"{base}#/jobs/95039193963/step_count": 0,
            f"{base}#/jobs/95073283491/step_count": 0,
        }
        mismatches = {
            locator: {"expected": expected, "actual": facts.get(locator)}
            for locator, expected in required.items()
            if facts.get(locator) != expected
        }
        if mismatches:
            raise RuntimeError(f"workflow probe evidence mismatch: {mismatches}")

        started = facts[f"{provider}/steps/6/started_at"]
        completed = facts[f"{provider}/steps/6/completed_at"]
        elapsed = int(
            (
                datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
                - datetime.fromisoformat(str(started).replace("Z", "+00:00"))
            ).total_seconds()
        )

        return {
            "schema_version": "lemmamind.github-workflow-probe.v1",
            "repository": REPOSITORY,
            "workflow_run_id": RUN_ID,
            "analysis_anchor_source_revision_id": anchored.revision.source_revision_id,
            "analysis_anchor_commit_sha": anchored.revision.commit_sha,
            "workflow_path": WORKFLOW_PATH,
            "capture_id_omitted_from_stable_report": True,
            "fact_count": len(extracted.facts),
            "run": {
                "conclusion": facts[f"{base}#/run/conclusion"],
                "created_at": facts[f"{base}#/run/created_at"],
                "updated_at": facts[f"{base}#/run/updated_at"],
                "job_count": facts[f"{base}#/job_count"],
                "artifact_count": facts[f"{base}#/artifact_count"],
            },
            "provider_job": {
                "conclusion": facts[f"{provider}/conclusion"],
                "step_count": facts[f"{provider}/step_count"],
                "log_availability": facts[f"{provider}/log/availability"],
                "execution_step": {
                    "name": facts[f"{provider}/steps/6/name"],
                    "conclusion": facts[f"{provider}/steps/6/conclusion"],
                    "started_at": started,
                    "completed_at": completed,
                    "elapsed_seconds": elapsed,
                },
                "upload_step_conclusion": facts[f"{provider}/steps/8/conclusion"],
            },
            "dependent_jobs": {
                "registry-promotion-disabled": {
                    "conclusion": facts[f"{base}#/jobs/95039193963/conclusion"],
                    "step_count": facts[f"{base}#/jobs/95039193963/step_count"],
                },
                "frozen-output-evaluator": {
                    "conclusion": facts[f"{base}#/jobs/95073283491/conclusion"],
                    "step_count": facts[f"{base}#/jobs/95073283491/step_count"],
                },
            },
            "interpretation_boundary": (
                "The durable evidence records run/job/step outcomes, timestamps, artifact metadata, "
                "and job-log availability only. The elapsed_seconds field in this probe is a "
                "deterministic report projection from the captured step timestamps, not a stored "
                "causal claim. No log contents are captured and no timeout cause or rerun decision "
                "is inferred by the evidence layer."
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live Resonance-World workflow evidence probe")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    report = run_probe(os.environ.get("GITHUB_TOKEN"))
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_path:
        Path(args.json_path).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
