#!/usr/bin/env python3
"""One-time/live-replay harness for the frozen private-Actions Pattern case."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lemmamind.contracts import (
    EvidenceFact,
    ObservationEpistemicType,
    PatternOccurrenceRole,
    RepositoryIdentity,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
    SupportType,
)
from lemmamind.github import GitHubRESTReader
from lemmamind.github_repository_metadata import (
    GitHubRepositoryMetadataCaptureService,
    GitHubRepositoryMetadataEvidenceService,
)
from lemmamind.github_workflow import (
    GitHubWorkflowCaptureService,
    GitHubWorkflowEvidenceService,
)
from lemmamind.github_workflow_http import SafeGitHubWorkflowRESTReader
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.observations import SupportRef
from lemmamind.observations_v2 import ObservationConstructionServiceV2
from lemmamind.pattern_intelligence import OccurrenceProposal, PatternConstructionService
from lemmamind.storage import SQLiteContractStore

CASES = (
    {
        "repository": "ElephantRock/ExpertOS",
        "revision": "8fd8250121baf75b3689e2bba7ba2df8fa3608cf",
        "run_id": 32779830513,
        "role": PatternOccurrenceRole.SUPPORTING,
        "visibility": "private",
        "local_statement": (
            "ExpertOS workflow run 32779830513 completed as failure, all four jobs had no "
            "recorded steps, and job logs were unavailable."
        ),
        "summary": "Private repository with matched pre-step failure signature.",
    },
    {
        "repository": "ElephantRock/ExpertForge",
        "revision": "5dcde592808d07008c2b5ad953fce78acb02f656",
        "run_id": 32778642199,
        "role": PatternOccurrenceRole.SUPPORTING,
        "visibility": "private",
        "local_statement": (
            "ExpertForge workflow run 32778642199 completed with a failed first job that had no "
            "recorded steps, while downstream jobs were skipped."
        ),
        "summary": "Private repository with matched pre-step failure signature.",
    },
    {
        "repository": "ElephantRock/ERLab",
        "revision": "d0078339601c431ccf2f8a12974dba0dba9724a6",
        "run_id": 32334661409,
        "role": PatternOccurrenceRole.NEGATIVE_CONTROL,
        "visibility": "public",
        "local_statement": (
            "ERLab workflow run 32334661409 executed normal GitHub Actions steps successfully in "
            "a public repository."
        ),
        "summary": "Public portfolio repository with successful Actions step execution.",
    },
    {
        "repository": "ElephantRock/Resonance-ContextGraph",
        "revision": "7caa57fa3650ed29e00ffd482b99ac571d294fc3",
        "run_id": 32780247570,
        "role": PatternOccurrenceRole.NEGATIVE_CONTROL,
        "visibility": "public",
        "local_statement": (
            "Resonance-ContextGraph workflow run 32780247570 executed pytest and other GitHub "
            "Actions steps successfully in a public repository."
        ),
        "summary": "Public portfolio repository with successful Actions step execution.",
    },
)

PATTERN_INFERENCE = (
    "The matched pre-step failure signature across two private repositories, contrasted with "
    "functioning public-repository Actions, supports a shared private-repository Actions "
    "provisioning, entitlement, or billing hypothesis more strongly than two independent "
    "code-test failures."
)
PATTERN_EVALUATION = (
    "The affected PRs should be described as CI not executed rather than code tests failed until "
    "runner/provisioning state is resolved."
)


def one(facts: tuple[EvidenceFact, ...], locator: str) -> EvidenceFact:
    matches = [fact for fact in facts if fact.locator == locator]
    if len(matches) != 1:
        raise RuntimeError(f"expected one fact at {locator}, found {len(matches)}")
    return matches[0]


def suffix(facts: tuple[EvidenceFact, ...], tail: str) -> list[EvidenceFact]:
    return [fact for fact in facts if fact.locator.endswith(tail)]


def job_facts(facts: tuple[EvidenceFact, ...], tail: str) -> list[EvidenceFact]:
    return [
        fact
        for fact in facts
        if "#/jobs/" in fact.locator and "/steps/" not in fact.locator and fact.locator.endswith(tail)
    ]


def create_source_context(store, reader, repository: str, revision_sha: str, now: datetime):
    owner, name = repository.split("/", 1)
    metadata = reader.get_repository(owner, name)
    commit = reader.get_commit(owner, name, revision_sha)
    if str(commit["sha"]) != revision_sha:
        raise RuntimeError(f"commit mismatch for {repository}")
    source_id = f"github:{metadata['id']}"
    source = Source(
        source_id=source_id,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator=f"https://github.com/{repository}",
        first_seen_at=now,
        last_seen_at=now,
    )
    identity = RepositoryIdentity(
        source_id=source_id,
        provider_repository_id=str(metadata["id"]),
        owner=str(metadata["owner"]["login"]),
        name=str(metadata["name"]),
        default_branch=str(metadata["default_branch"]),
        aliases=(),
        archived=bool(metadata.get("archived", False)),
    )
    revision = SourceRevision(
        source_revision_id=f"{source_id}@{revision_sha}",
        source_id=source_id,
        commit_sha=revision_sha,
        tree_sha=str(commit["commit"]["tree"]["sha"]),
        observed_at=now,
    )
    store.put_many((source, identity, revision))
    return metadata, revision


def select_supports(case, metadata_facts, workflow_facts):
    root = f"$github/actions/run/{case['run_id']}"
    selected = [
        one(metadata_facts, "$github/repository#/visibility"),
        one(workflow_facts, f"{root}#/run/conclusion"),
    ]
    step_counts = job_facts(workflow_facts, "/step_count")
    job_conclusions = job_facts(workflow_facts, "/conclusion")
    log_availability = suffix(workflow_facts, "/log/availability")

    if case["role"] is PatternOccurrenceRole.SUPPORTING:
        if case["visibility"] != "private":
            raise RuntimeError("supporting private-Actions case must be private")
        if one(metadata_facts, "$github/repository#/visibility").normalized_value != "private":
            raise RuntimeError(f"{case['repository']} is not private in live metadata")
        if not step_counts or not any(f.normalized_value == 0 for f in step_counts):
            raise RuntimeError(f"{case['repository']} lacks zero-step workflow evidence")
        if case["repository"].endswith("ExpertOS"):
            if len(step_counts) != 4 or not all(f.normalized_value == 0 for f in step_counts):
                raise RuntimeError("ExpertOS expected four workflow jobs with zero steps")
            if len(log_availability) != 4 or not all(
                f.normalized_value == "missing" for f in log_availability
            ):
                raise RuntimeError("ExpertOS expected all four job logs to be unavailable")
            selected.extend(step_counts)
            selected.extend(log_availability)
        else:
            failed = [f for f in job_conclusions if f.normalized_value == "failure"]
            skipped = [f for f in job_conclusions if f.normalized_value == "skipped"]
            if len(step_counts) != 3 or not failed or len(skipped) < 2:
                raise RuntimeError("ExpertForge expected one failed zero-step job and skipped dependents")
            selected.extend(step_counts)
            selected.extend(failed)
            selected.extend(skipped)
    else:
        if one(metadata_facts, "$github/repository#/visibility").normalized_value != "public":
            raise RuntimeError(f"{case['repository']} is not public in live metadata")
        positive_steps = [
            f for f in step_counts if isinstance(f.normalized_value, int) and f.normalized_value > 0
        ]
        success = [f for f in job_conclusions if f.normalized_value == "success"]
        if not positive_steps or not success:
            raise RuntimeError(f"{case['repository']} lacks successful step execution")
        selected.extend(positive_steps)
        selected.extend(success)

    dedup = {fact.evidence_id: fact for fact in selected}
    return tuple(
        SupportRef(SupportType.EVIDENCE_FACT, evidence_id)
        for evidence_id in sorted(dedup)
    )


def run_probe(token: str) -> dict:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="lemmamind-pattern-") as tmp:
        root = Path(tmp)
        store = SQLiteContractStore(root / "lemmamind.db")
        objects = ContentAddressedFileStore(root / "objects")
        github = GitHubRESTReader(token)
        workflow_reader = SafeGitHubWorkflowRESTReader(token)
        observations = ObservationConstructionServiceV2(store, clock=lambda: now)
        proposals = []
        occurrence_report = []

        for index, case in enumerate(CASES, start=1):
            metadata, revision = create_source_context(
                store, github, case["repository"], case["revision"], now
            )
            metadata_capture = GitHubRepositoryMetadataCaptureService(
                github, store, objects, clock=lambda: now
            ).capture_metadata(revision.source_revision_id)
            metadata_evidence = GitHubRepositoryMetadataEvidenceService(
                store, objects, clock=lambda: now
            ).extract_metadata(metadata_capture.manifest.capture_id)
            workflow_capture = GitHubWorkflowCaptureService(
                workflow_reader, store, objects, clock=lambda: now
            ).capture_run(revision.source_revision_id, case["run_id"])
            workflow_evidence = GitHubWorkflowEvidenceService(
                store, objects, clock=lambda: now
            ).extract_run(workflow_capture.manifest.capture_id)

            supports = select_supports(case, metadata_evidence.facts, workflow_evidence.facts)
            observation = observations.create_candidate(
                logical_claim_id=f"private-actions:source:{index}",
                epistemic_type=ObservationEpistemicType.INTERPRETATION,
                statement=case["local_statement"],
                supports=supports,
            ).observation
            proposals.append(
                OccurrenceProposal(
                    revision.source_revision_id,
                    case["role"],
                    case["summary"],
                    (observation.observation_id,),
                )
            )
            occurrence_report.append(
                {
                    "repository": case["repository"],
                    "source_revision_id": revision.source_revision_id,
                    "visibility": metadata["visibility"],
                    "workflow_run_id": case["run_id"],
                    "role": case["role"].value,
                    "observation_id": observation.observation_id,
                    "observation_validation_state": observation.validation_state.value,
                    "support_count": len(supports),
                }
            )

        patterns = PatternConstructionService(store, clock=lambda: now)
        inference = patterns.create_candidate(
            logical_claim_id="pattern:private-actions-pre-step-failure",
            epistemic_type=ObservationEpistemicType.INFERENCE,
            statement=PATTERN_INFERENCE,
            occurrences=tuple(proposals),
            minimum_supporting_sources=2,
            minimum_negative_control_sources=2,
        )
        evaluation = patterns.create_candidate(
            logical_claim_id="pattern:private-actions-ci-not-executed",
            epistemic_type=ObservationEpistemicType.EVALUATION,
            statement=PATTERN_EVALUATION,
            occurrences=tuple(proposals),
            minimum_supporting_sources=2,
            minimum_negative_control_sources=2,
        )

        return {
            "schema_version": "lemmamind.private-actions-pattern-probe.v1",
            "case_id": "private-actions-pattern",
            "occurrences": occurrence_report,
            "supporting_sources": 2,
            "negative_control_sources": 2,
            "patterns": [
                {
                    "logical_claim_id": inference.pattern.logical_claim_id,
                    "epistemic_type": inference.pattern.epistemic_type.value,
                    "statement": inference.pattern.statement,
                    "validation_state": inference.pattern.validation_state.value,
                    "occurrence_count": len(inference.occurrences),
                },
                {
                    "logical_claim_id": evaluation.pattern.logical_claim_id,
                    "epistemic_type": evaluation.pattern.epistemic_type.value,
                    "statement": evaluation.pattern.statement,
                    "validation_state": evaluation.pattern.validation_state.value,
                    "occurrence_count": len(evaluation.occurrences),
                },
            ],
            "boundary": (
                "Each occurrence is supported by a source-local Observation whose leaf evidence "
                "resolves to exactly one SourceRevision. Cross-repository synthesis exists only at "
                "Pattern level; both live Patterns remain candidate and the provisioning/billing "
                "explanation is not promoted to confirmed fact."
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    report = run_probe(token)
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.json:
        args.json.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
