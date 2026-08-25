#!/usr/bin/env python3
"""One-time live validation for durable GitHub issue-event history evidence."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lemmamind.contracts import RepositoryIdentity, Source, SourceKind, SourceRevision, SourceRole
from lemmamind.github_process_events import (
    GitHubProcessEventCaptureService,
    GitHubProcessEventEvidenceService,
    GitHubProcessEventRESTReader,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

REPOSITORY = "ElephantRock/CSD-Foundry"
SOURCE_ID = "github:1318635781"
ANCHOR_SHA = "aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7"
ANCHOR_TREE_SHA = "843b049ed77b3d4393f944e252651c0c7deb8c31"
SOURCE_REVISION_ID = f"{SOURCE_ID}@{ANCHOR_SHA}"
ISSUE_NUMBER = 37


def run_probe() -> dict[str, object]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    now = datetime.now(timezone.utc)

    with tempfile.TemporaryDirectory(prefix="lemmamind-process-events-") as temp:
        root = Path(temp)
        store = SQLiteContractStore(root / "lemmamind.db")
        objects = ContentAddressedFileStore(root / "objects")
        source = Source(
            source_id=SOURCE_ID,
            source_kind=SourceKind.GITHUB_REPOSITORY,
            source_role=SourceRole.IMPLEMENTATION,
            canonical_locator=f"https://github.com/{REPOSITORY}",
            first_seen_at=now,
            last_seen_at=now,
        )
        repository = RepositoryIdentity(
            source_id=SOURCE_ID,
            provider_repository_id="1318635781",
            owner="ElephantRock",
            name="CSD-Foundry",
            default_branch="main",
            aliases=(),
            archived=False,
        )
        revision = SourceRevision(
            source_revision_id=SOURCE_REVISION_ID,
            source_id=SOURCE_ID,
            commit_sha=ANCHOR_SHA,
            tree_sha=ANCHOR_TREE_SHA,
            observed_at=now,
        )
        store.put_many((source, repository, revision))

        capture = GitHubProcessEventCaptureService(
            GitHubProcessEventRESTReader(token=token), store, objects
        ).capture_issue_events(SOURCE_REVISION_ID, (ISSUE_NUMBER,))
        extraction = GitHubProcessEventEvidenceService(store, objects).extract_issue_events(
            capture.manifest.capture_id
        )

        artifact = capture.artifacts[0]
        payload = json.loads(objects.get(artifact.content_hash).decode("utf-8"))
        events = payload["events"]
        state_events = [
            {
                "provider_id": event["provider_id"],
                "event": event["event"],
                "created_at": event["created_at"],
                "actor_login": event["actor_login"],
            }
            for event in events
            if event["event"] in {"closed", "reopened"}
        ]
        closed = [event for event in state_events if event["event"] == "closed"]
        reopened = [event for event in state_events if event["event"] == "reopened"]
        if not closed or not reopened:
            raise RuntimeError("CSD #37 close/reopen event history was not recovered")
        last_close = closed[-1]
        first_reopen_after_close = next(
            (event for event in reopened if event["created_at"] > last_close["created_at"]),
            None,
        )
        if first_reopen_after_close is None:
            raise RuntimeError("CSD #37 does not contain a reopen event after the recovered close")

        return {
            "schema_version": "lemmamind.github-process-event-probe.v1",
            "repository": REPOSITORY,
            "analysis_anchor_source_revision_id": SOURCE_REVISION_ID,
            "analysis_anchor_commit_sha": ANCHOR_SHA,
            "issue_number": ISSUE_NUMBER,
            "capture_id_omitted_from_stable_report": True,
            "event_count": len(events),
            "fact_count": len(extraction.facts),
            "state_events": state_events,
            "close_reopen_transition": {
                "closed_at": last_close["created_at"],
                "closed_event_id": last_close["provider_id"],
                "reopened_at": first_reopen_after_close["created_at"],
                "reopened_event_id": first_reopen_after_close["provider_id"],
                "observed": True,
            },
            "interpretation_boundary": (
                "The durable evidence records provider issue events and timestamps. "
                "It proves that issue #37 was closed and later reopened; it does not by itself "
                "decide whether implementation or evidentiary closure is complete."
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run_probe()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
