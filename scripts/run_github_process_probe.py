from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from lemmamind.contracts import SourceRole
from lemmamind.github import GitHubCaptureService, GitHubRESTReader
from lemmamind.github_process import (
    GitHubProcessCaptureService,
    GitHubProcessEvidenceService,
    GitHubProcessRESTReader,
    ProcessKind,
    ProcessRef,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore


def run_probe(token: str | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="lemmamind-process-probe-") as directory:
        root = Path(directory)
        store = SQLiteContractStore(root / "lemmamind.db")
        objects = ContentAddressedFileStore(root / "objects")

        repository_reader = GitHubRESTReader(token=token)
        repository_capture = GitHubCaptureService(repository_reader, store, objects)
        anchored = repository_capture.capture_repository(
            "ElephantRock/CSD-Foundry",
            ["README.md"],
            source_role=SourceRole.IMPLEMENTATION,
        )

        process_reader = GitHubProcessRESTReader(token=token)
        process_capture = GitHubProcessCaptureService(process_reader, store, objects)
        process_evidence = GitHubProcessEvidenceService(store, objects)
        captured = process_capture.capture_process(
            anchored.revision.source_revision_id,
            (
                ProcessRef(ProcessKind.ISSUE, 37),
                ProcessRef(ProcessKind.PULL_REQUEST, 115),
                ProcessRef(ProcessKind.PULL_REQUEST, 117),
            ),
        )
        extracted = process_evidence.extract_process(captured.manifest.capture_id)

        facts = {fact.locator: fact.normalized_value for fact in extracted.facts}
        assertions = {item.locator: item.statement for item in extracted.assertions}
        required_facts = (
            "$github/issue/37#/state",
            "$github/issue/37#/updated_at",
            "$github/pull/115#/state",
            "$github/pull/115#/merged",
            "$github/pull/115#/merge_commit_sha",
            "$github/pull/115#/head/sha",
            "$github/pull/117#/state",
            "$github/pull/117#/draft",
            "$github/pull/117#/head/sha",
            "$github/pull/117#/base/sha",
            "$github/pull/117#/updated_at",
        )
        required_assertions = (
            "$github/issue/37#title",
            "$github/pull/115#title",
            "$github/pull/115#body",
            "$github/pull/117#title",
            "$github/pull/117#body",
        )
        missing = [locator for locator in required_facts if locator not in facts]
        missing += [locator for locator in required_assertions if locator not in assertions]
        if missing:
            raise RuntimeError(f"live process probe missing required evidence: {missing}")

        return {
            "schema_version": "lemmamind.github-process-probe.v1",
            "repository": "ElephantRock/CSD-Foundry",
            "analysis_anchor_source_revision_id": anchored.revision.source_revision_id,
            "analysis_anchor_commit_sha": anchored.revision.commit_sha,
            "capture_id": captured.manifest.capture_id,
            "artifact_locators": [artifact.source_locator for artifact in captured.artifacts],
            "fact_count": len(extracted.facts),
            "source_assertion_count": len(extracted.assertions),
            "issue_37": {
                "state": facts["$github/issue/37#/state"],
                "updated_at": facts["$github/issue/37#/updated_at"],
                "title": assertions["$github/issue/37#title"],
            },
            "pull_115": {
                "state": facts["$github/pull/115#/state"],
                "merged": facts["$github/pull/115#/merged"],
                "merge_commit_sha": facts["$github/pull/115#/merge_commit_sha"],
                "head_sha": facts["$github/pull/115#/head/sha"],
                "title": assertions["$github/pull/115#title"],
                "body_mentions_issue_37": "#37" in assertions["$github/pull/115#body"],
            },
            "pull_117": {
                "state": facts["$github/pull/117#/state"],
                "draft": facts["$github/pull/117#/draft"],
                "head_sha": facts["$github/pull/117#/head/sha"],
                "base_sha": facts["$github/pull/117#/base/sha"],
                "updated_at": facts["$github/pull/117#/updated_at"],
                "title": assertions["$github/pull/117#title"],
            },
            "interpretation_boundary": (
                "Issue/PR snapshots are mutable process evidence observed during this capture. "
                "The SourceRevision is the repository analysis anchor, not a claim that the "
                "process state is historically determined by that Git commit."
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live CSD GitHub process evidence probe")
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
