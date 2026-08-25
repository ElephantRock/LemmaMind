from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from lemmamind.action_policy import (
    ActionPolicyEffect,
    ActionPolicyRule,
    ActionPolicyService,
    ActionProposal,
    PolicySupportRequirement,
)
from lemmamind.contracts import (
    ActionStatus,
    ActionType,
    RelationshipType,
    RepositoryRelationship,
    SourceRole,
    SupportType,
)
from lemmamind.extraction import DeterministicExtractionService
from lemmamind.github import GitHubCaptureService, GitHubRESTReader
from lemmamind.github_process import (
    GitHubProcessCaptureService,
    GitHubProcessEvidenceService,
    GitHubProcessRESTReader,
    ProcessKind,
    ProcessRef,
)
from lemmamind.github_workflow import (
    GitHubWorkflowCaptureService,
    GitHubWorkflowEvidenceService,
)
from lemmamind.github_workflow_http import SafeGitHubWorkflowRESTReader
from lemmamind.json_evidence import JsonPointerExtractor
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

REPOSITORY = "ElephantRock/Resonance-World"
HEAD_SHA = "65d739736070bbebe7941bebfbee785d33499c46"
REQUEST_PLAN = "research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json"
PR_NUMBER = 177
WORKFLOW_RUN_ID = 31895957256


def run_probe(token: str | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="lemmamind-action-policy-") as directory:
        root = Path(directory)
        store = SQLiteContractStore(root / "lemmamind.db")
        objects = ContentAddressedFileStore(root / "objects")

        repository_reader = GitHubRESTReader(token=token)
        repository_capture = GitHubCaptureService(repository_reader, store, objects)
        anchored = repository_capture.capture_repository(
            REPOSITORY,
            [REQUEST_PLAN],
            source_role=SourceRole.IMPLEMENTATION,
            ref=HEAD_SHA,
        )
        request_extraction = DeterministicExtractionService(
            store,
            objects,
            artifact_extractors=(JsonPointerExtractor(),),
            extraction_policy_version="governance-json.v1",
        ).extract_capture(anchored.manifest.capture_id)
        rerun_fact = next(
            fact
            for fact in request_extraction.facts
            if fact.locator == f"{REQUEST_PLAN}#/confirmatory_rerun_allowed"
        )
        if rerun_fact.normalized_value is not False:
            raise RuntimeError("frozen request plan no longer says confirmatory_rerun_allowed=false")

        process_capture = GitHubProcessCaptureService(
            GitHubProcessRESTReader(token=token), store, objects
        )
        process = process_capture.capture_process(
            anchored.revision.source_revision_id,
            (ProcessRef(ProcessKind.PULL_REQUEST, PR_NUMBER),),
        )
        process_evidence = GitHubProcessEvidenceService(store, objects).extract_process(
            process.manifest.capture_id
        )
        pr_body = next(
            assertion
            for assertion in process_evidence.assertions
            if assertion.locator == f"$github/pull/{PR_NUMBER}#body"
        )
        required_pr_fragments = (
            "separate frozen-output evaluator is the only classifier",
            "any promotion requires independent Acceptance-plane authority",
        )
        missing_pr_fragments = [
            fragment for fragment in required_pr_fragments if fragment not in pr_body.statement
        ]
        if missing_pr_fragments:
            raise RuntimeError(f"PR governance text missing fragments: {missing_pr_fragments}")

        workflow_capture = GitHubWorkflowCaptureService(
            SafeGitHubWorkflowRESTReader(token=token), store, objects
        )
        workflow = workflow_capture.capture_run(
            anchored.revision.source_revision_id, WORKFLOW_RUN_ID
        )
        workflow_evidence = GitHubWorkflowEvidenceService(store, objects).extract_run(
            workflow.manifest.capture_id
        )
        workflow_facts = {fact.locator: fact.normalized_value for fact in workflow_evidence.facts}
        run_base = f"$github/actions/run/{WORKFLOW_RUN_ID}"
        if workflow_facts[f"{run_base}#/run/conclusion"] != "cancelled":
            raise RuntimeError("frozen workflow run no longer resolves as cancelled")
        if workflow_facts[f"{run_base}#/artifact_count"] != 0:
            raise RuntimeError("frozen workflow run unexpectedly contains uploaded artifacts")

        relationship = RepositoryRelationship(
            relationship_id="relationship:resonance-world-owned",
            source_id=anchored.source.source_id,
            relationship_type=RelationshipType.OWNED,
            can_write=True,
            can_contribute=True,
            observed_at=anchored.revision.observed_at,
        )
        store.put(relationship)

        policy_rules = (
            ActionPolicyRule(
                rule_id="no-confirmatory-rerun",
                effect=ActionPolicyEffect.PROHIBIT,
                action_types=(ActionType.RERUN,),
                rationale="the frozen request plan explicitly disallows a confirmatory rerun",
                supports=(
                    PolicySupportRequirement(
                        support_type=SupportType.EVIDENCE_FACT,
                        support_id=rerun_fact.evidence_id,
                        expected_normalized_value=False,
                    ),
                ),
            ),
            ActionPolicyRule(
                rule_id="separate-evaluator-only-classifier",
                effect=ActionPolicyEffect.REQUIRE_ROLE,
                action_types=(ActionType.CLASSIFY,),
                rationale="the frozen provider runner is not the classifier",
                supports=(
                    PolicySupportRequirement(
                        support_type=SupportType.SOURCE_ASSERTION,
                        support_id=pr_body.assertion_id,
                        statement_fragments=(
                            "separate frozen-output evaluator is the only classifier",
                        ),
                    ),
                ),
                allowed_actor_roles=("frozen_output_evaluator",),
            ),
            ActionPolicyRule(
                rule_id="independent-acceptance-for-promotion",
                effect=ActionPolicyEffect.REQUIRE_INDEPENDENT_AUTHORIZATION,
                action_types=(ActionType.PROMOTE,),
                rationale="promotion requires independent Acceptance-plane authority",
                supports=(
                    PolicySupportRequirement(
                        support_type=SupportType.SOURCE_ASSERTION,
                        support_id=pr_body.assertion_id,
                        statement_fragments=(
                            "any promotion requires independent Acceptance-plane authority",
                        ),
                    ),
                ),
            ),
        )
        policy = ActionPolicyService(
            store,
            policy_version="resonance-world-confirmatory-action-policy.v1",
        )

        def evaluate(action_type: ActionType, actor_role: str):
            return policy.evaluate(
                ActionProposal(
                    proposal_id=f"proposal:{action_type.value}:{actor_role}",
                    subject_id=f"workflow-run:{WORKFLOW_RUN_ID}",
                    source_id=anchored.source.source_id,
                    action_type=action_type,
                    target=f"workflow-run:{WORKFLOW_RUN_ID}",
                    rationale=f"Evaluate {action_type.value} for the frozen confirmatory campaign.",
                    repository_modification_required=False,
                    actor_role=actor_role,
                ),
                relationship_id=relationship.relationship_id,
                rules=policy_rules,
            )

        rerun = evaluate(ActionType.RERUN, "operator")
        provider_classify = evaluate(ActionType.CLASSIFY, "provider_runner")
        evaluator_classify = evaluate(ActionType.CLASSIFY, "frozen_output_evaluator")
        promote = evaluate(ActionType.PROMOTE, "operator")
        preserve = evaluate(ActionType.PRESERVE, "operator")

        if rerun.decision.value != "blocked":
            raise RuntimeError("frozen no-rerun policy did not block rerun")
        if provider_classify.decision.value != "blocked":
            raise RuntimeError("provider runner was incorrectly allowed to self-classify")
        if evaluator_classify.decision.value != "recommended":
            raise RuntimeError("separate evaluator role was not recognized")
        if promote.decision.value != "requires_authorization":
            raise RuntimeError("promotion did not retain independent authorization requirement")
        if promote.recommendation.status is ActionStatus.AUTHORIZED:
            raise RuntimeError("policy evaluator self-authorized an independent action")
        if preserve.decision.value != "recommended":
            raise RuntimeError("preservation was unexpectedly blocked")

        return {
            "schema_version": "lemmamind.action-policy-probe.v1",
            "case_id": "resonance-world-confirmatory",
            "repository": REPOSITORY,
            "analysis_anchor_commit_sha": anchored.revision.commit_sha,
            "analysis_anchor_source_revision_id": anchored.revision.source_revision_id,
            "workflow_run": {
                "run_id": WORKFLOW_RUN_ID,
                "conclusion": workflow_facts[f"{run_base}#/run/conclusion"],
                "artifact_count": workflow_facts[f"{run_base}#/artifact_count"],
            },
            "governance_evidence": {
                "confirmatory_rerun_allowed": rerun_fact.normalized_value,
                "separate_evaluator_only_classifier": True,
                "promotion_requires_independent_acceptance": True,
            },
            "repository_relationship": {
                "type": relationship.relationship_type.value,
                "can_write": relationship.can_write,
                "can_contribute": relationship.can_contribute,
            },
            "evaluations": {
                "rerun": {
                    "decision": rerun.decision.value,
                    "status": rerun.recommendation.status.value,
                    "authorization_required": rerun.recommendation.authorization_required,
                },
                "provider_self_classify": {
                    "decision": provider_classify.decision.value,
                    "status": provider_classify.recommendation.status.value,
                },
                "separate_evaluator_classify": {
                    "decision": evaluator_classify.decision.value,
                    "status": evaluator_classify.recommendation.status.value,
                },
                "promote": {
                    "decision": promote.decision.value,
                    "status": promote.recommendation.status.value,
                    "authorization_required": promote.recommendation.authorization_required,
                },
                "preserve": {
                    "decision": preserve.decision.value,
                    "status": preserve.recommendation.status.value,
                },
            },
            "all_policy_outputs_non_authorized": all(
                result.recommendation.status is not ActionStatus.AUTHORIZED
                for result in (
                    rerun,
                    provider_classify,
                    evaluator_classify,
                    promote,
                    preserve,
                )
            ),
            "interpretation_boundary": (
                "This probe validates operational policy against explicit captured governance rules. "
                "It does not execute an action, infer authorization from repository ownership, or "
                "grant independent Acceptance-plane authority."
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live Resonance-World action-policy probe")
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
