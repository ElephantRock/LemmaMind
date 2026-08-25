#!/usr/bin/env python3
"""Live CSD-Foundry frontier reconciliation against current process + event evidence."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lemmamind.contracts import (
    ObservationEpistemicType,
    RepositoryIdentity,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
    SupportType,
)
from lemmamind.github_process import (
    GitHubProcessCaptureService,
    GitHubProcessEvidenceService,
    GitHubProcessRESTReader,
    ProcessKind,
    ProcessRef,
)
from lemmamind.github_process_events import (
    GitHubProcessEventCaptureService,
    GitHubProcessEventEvidenceService,
    GitHubProcessEventRESTReader,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.observations import SupportRef
from lemmamind.observations_v2 import ObservationConstructionServiceV2
from lemmamind.storage import SQLiteContractStore
from lemmamind.temporal_reconciliation import (
    FactExpectation,
    OrderedEventTransition,
    TemporalFrontierReconciliationService,
)

SOURCE_ID = "github:1318635781"
REPOSITORY = "ElephantRock/CSD-Foundry"
ANCHOR_SHA = "aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7"
ANCHOR_TREE_SHA = "843b049ed77b3d4393f944e252651c0c7deb8c31"
QUALIFICATION_SHA = "2d910f3ff83f061409ca9d8f2e3709fde7c13f6e"
SOURCE_REVISION_ID = f"{SOURCE_ID}@{ANCHOR_SHA}"
LOGICAL_CLAIM_ID = "csd:issue-37-closure-frontier"


def by_locator(records, locator):
    return next(record for record in records if record.locator == locator)


def run_probe() -> dict[str, object]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    now = datetime.now(timezone.utc)

    with tempfile.TemporaryDirectory(prefix="lemmamind-temporal-") as temp:
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

        process_capture = GitHubProcessCaptureService(
            GitHubProcessRESTReader(token=token), store, objects
        ).capture_process(
            SOURCE_REVISION_ID,
            (
                ProcessRef(ProcessKind.ISSUE, 37),
                ProcessRef(ProcessKind.PULL_REQUEST, 115),
                ProcessRef(ProcessKind.PULL_REQUEST, 117),
            ),
        )
        process = GitHubProcessEvidenceService(store, objects).extract_process(
            process_capture.manifest.capture_id
        )
        event_capture = GitHubProcessEventCaptureService(
            GitHubProcessEventRESTReader(token=token), store, objects
        ).capture_issue_events(SOURCE_REVISION_ID, (37,))
        events = GitHubProcessEventEvidenceService(store, objects).extract_issue_events(
            event_capture.manifest.capture_id
        )

        merged = by_locator(process.facts, "$github/pull/115#/merged")
        issue_open = by_locator(process.facts, "$github/issue/37#/state")
        qualification_open = by_locator(process.facts, "$github/pull/117#/state")
        qualification_draft = by_locator(process.facts, "$github/pull/117#/draft")
        qualification_head = by_locator(process.facts, "$github/pull/117#/head/sha")
        qualification_base = by_locator(process.facts, "$github/pull/117#/base/sha")
        qualification_body = by_locator(process.assertions, "$github/pull/117#body")

        state_event_facts = [
            fact for fact in events.facts
            if fact.locator.endswith("/event") and fact.normalized_value in {"closed", "reopened"}
        ]
        closed_event = next(fact for fact in state_event_facts if fact.normalized_value == "closed")
        reopened_event = next(fact for fact in state_event_facts if fact.normalized_value == "reopened")
        closed_at = by_locator(events.facts, closed_event.locator.rsplit("/", 1)[0] + "/created_at")
        reopened_at = by_locator(events.facts, reopened_event.locator.rsplit("/", 1)[0] + "/created_at")

        if qualification_head.normalized_value != QUALIFICATION_SHA:
            raise RuntimeError("PR #117 head revision changed from the frozen qualification revision")
        if qualification_base.normalized_value != ANCHOR_SHA:
            raise RuntimeError("PR #117 no longer bases directly on the frozen D5 merge revision")

        observations = ObservationConstructionServiceV2(store)
        prior = observations.create_candidate(
            logical_claim_id=LOGICAL_CLAIM_ID,
            epistemic_type=ObservationEpistemicType.EVALUATION,
            statement="Issue #37 can close because the D1-D5 implementation frontier is complete.",
            supports=(SupportRef(SupportType.EVIDENCE_FACT, merged.evidence_id),),
        ).observation

        interpretation = observations.create_candidate(
            logical_claim_id="csd:implementation-vs-evidentiary-frontier",
            epistemic_type=ObservationEpistemicType.INTERPRETATION,
            statement=(
                "The implementation frontier and the evidentiary closure frontier are distinct; "
                "D1-D5 production implementation can be complete while independent integrated "
                "qualification remains pending."
            ),
            supports=(
                SupportRef(SupportType.EVIDENCE_FACT, merged.evidence_id),
                SupportRef(SupportType.EVIDENCE_FACT, qualification_open.evidence_id),
                SupportRef(SupportType.EVIDENCE_FACT, qualification_head.evidence_id),
                SupportRef(SupportType.EVIDENCE_FACT, qualification_base.evidence_id),
                SupportRef(SupportType.SOURCE_ASSERTION, qualification_body.assertion_id),
            ),
        ).observation

        current_facts = (
            merged,
            issue_open,
            qualification_open,
            qualification_draft,
            qualification_head,
            qualification_base,
            closed_event,
            closed_at,
            reopened_event,
            reopened_at,
        )
        supports = tuple(
            SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id) for fact in current_facts
        ) + (SupportRef(SupportType.SOURCE_ASSERTION, qualification_body.assertion_id),)
        expectations = (
            FactExpectation(merged.evidence_id, True),
            FactExpectation(issue_open.evidence_id, "open"),
            FactExpectation(qualification_open.evidence_id, "open"),
            FactExpectation(qualification_draft.evidence_id, True),
            FactExpectation(qualification_head.evidence_id, QUALIFICATION_SHA),
            FactExpectation(qualification_base.evidence_id, ANCHOR_SHA),
        )
        transition = OrderedEventTransition(
            from_event_fact_id=closed_event.evidence_id,
            from_event="closed",
            from_timestamp_fact_id=closed_at.evidence_id,
            to_event_fact_id=reopened_event.evidence_id,
            to_event="reopened",
            to_timestamp_fact_id=reopened_at.evidence_id,
        )
        reconciled = TemporalFrontierReconciliationService(
            store, observation_service=observations
        ).reconcile(
            logical_claim_id=LOGICAL_CLAIM_ID,
            prior_observation_id=prior.observation_id,
            epistemic_type=ObservationEpistemicType.EVALUATION,
            statement=(
                "The earlier conclusion that #37 could close was too strong and should be "
                "superseded by the narrower conclusion that implementation is landed but "
                "qualification and closure remain open."
            ),
            supports=supports,
            expectations=expectations,
            transition=transition,
        )

        return {
            "schema_version": "lemmamind.temporal-frontier-probe.v1",
            "case_id": "csd-foundry-frontier",
            "repository": REPOSITORY,
            "analysis_anchor_source_revision_id": SOURCE_REVISION_ID,
            "analysis_anchor_commit_sha": ANCHOR_SHA,
            "qualification_revision": QUALIFICATION_SHA,
            "process_facts": len(process.facts),
            "process_assertions": len(process.assertions),
            "event_facts": len(events.facts),
            "frontier_state": {
                "pr_115_merged": merged.normalized_value,
                "issue_37_state": issue_open.normalized_value,
                "pr_117_state": qualification_open.normalized_value,
                "pr_117_draft": qualification_draft.normalized_value,
                "pr_117_base_sha": qualification_base.normalized_value,
                "pr_117_head_sha": qualification_head.normalized_value,
            },
            "transition": {
                "from": "closed",
                "from_timestamp": reconciled.from_timestamp,
                "to": "reopened",
                "to_timestamp": reconciled.to_timestamp,
            },
            "interpretation": {
                "statement": interpretation.statement,
                "validation_state": interpretation.validation_state.value,
            },
            "belief_revision": {
                "prior_statement": prior.statement,
                "prior_preserved": store.get(type(prior), prior.observation_id) == prior,
                "superseding_statement": reconciled.observation.statement,
                "supersedes_observation_id": reconciled.observation.supersedes_observation_id,
                "validation_state": reconciled.observation.validation_state.value,
            },
            "interpretation_boundary": (
                "The service validates explicit process facts, the PR #117 base/head revision "
                "relationship, and an ordered close→reopen event transition before constructing "
                "a candidate superseding Observation. It does not rewrite the prior Observation "
                "or auto-promote either candidate to reviewed/validated state."
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
