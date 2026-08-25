from datetime import datetime, timezone

import pytest

from lemmamind.action_policy import (
    ActionPolicyDecision,
    ActionPolicyEffect,
    ActionPolicyError,
    ActionPolicyRule,
    ActionPolicyService,
    ActionProposal,
    PolicySupportRequirement,
)
from lemmamind.contracts import (
    ActionRecommendation,
    ActionStatus,
    ActionType,
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RelationshipType,
    RepositoryRelationship,
    RetrievalStatus,
    RunType,
    SourceAssertion,
    SourceRevision,
    SupportType,
)
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 15, 30, tzinfo=timezone.utc)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"policy-{self.value}"


def complete_extraction_run(run_id: str = "run:extract") -> PipelineRun:
    return PipelineRun(
        run_id=run_id,
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="test-extraction.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST_A,
        outputs_hash=DIGEST_B,
    )


def build_store(tmp_path, *, source_id: str = "source:resonance"):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    revision = SourceRevision(
        source_revision_id=f"{source_id}@" + "a" * 40,
        source_id=source_id,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        observed_at=NOW,
    )
    request_artifact = Artifact(
        artifact_id="artifact:request-plan",
        capture_id="capture:policy",
        source_locator="research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json",
        content_hash=DIGEST_A,
        media_type="application/json",
    )
    pr_artifact = Artifact(
        artifact_id="artifact:pr177",
        capture_id="capture:policy",
        source_locator="$github/pull/177",
        content_hash=DIGEST_B,
        media_type="application/vnd.lemmamind.github-process+json",
    )
    manifest = CaptureManifest(
        capture_id="capture:policy",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=NOW,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=request_artifact.artifact_id,
                source_locator=request_artifact.source_locator,
                content_hash=request_artifact.content_hash,
                media_type=request_artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
            CaptureArtifactRef(
                artifact_id=pr_artifact.artifact_id,
                source_locator=pr_artifact.source_locator,
                content_hash=pr_artifact.content_hash,
                media_type=pr_artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    rerun_fact = EvidenceFact(
        evidence_id="fact:no-rerun",
        artifact_id=request_artifact.artifact_id,
        locator="research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json#/confirmatory_rerun_allowed",
        raw_value=False,
        normalized_value=False,
        extractor_name="json-pointer",
        extractor_version="1",
        run_id="run:extract",
    )
    governance_assertion = SourceAssertion(
        assertion_id="assertion:governance",
        artifact_id=pr_artifact.artifact_id,
        locator="$github/pull/177#body",
        statement=(
            "frozen provider runner emits no classification; separate frozen-output evaluator "
            "is the only classifier; no registry promotion job; any promotion requires "
            "independent Acceptance-plane authority"
        ),
        extractor_name="github-process-text",
        extractor_version="1",
        run_id="run:extract",
    )
    relationship = RepositoryRelationship(
        relationship_id="relationship:owned",
        source_id=source_id,
        relationship_type=RelationshipType.OWNED,
        can_write=True,
        can_contribute=True,
        observed_at=NOW,
    )
    store.put_many(
        (
            complete_extraction_run(),
            revision,
            request_artifact,
            pr_artifact,
            manifest,
            rerun_fact,
            governance_assertion,
            relationship,
        )
    )
    return store, rerun_fact, governance_assertion, relationship


def service(store: SQLiteContractStore) -> ActionPolicyService:
    return ActionPolicyService(
        store,
        policy_version="resonance-confirmatory.v1",
        code_version="test",
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    )


def rules(rerun_fact: EvidenceFact, assertion: SourceAssertion):
    return (
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
            rationale="classification belongs to the separate frozen-output evaluator",
            supports=(
                PolicySupportRequirement(
                    support_type=SupportType.SOURCE_ASSERTION,
                    support_id=assertion.assertion_id,
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
                    support_id=assertion.assertion_id,
                    statement_fragments=(
                        "any promotion requires independent Acceptance-plane authority",
                    ),
                ),
            ),
        ),
    )


def proposal(action_type: ActionType, *, actor_role: str = "operator") -> ActionProposal:
    return ActionProposal(
        proposal_id=f"proposal:{action_type.value}:{actor_role}",
        subject_id="workflow-run:31895957256",
        source_id="source:resonance",
        action_type=action_type,
        target="workflow-run:31895957256",
        rationale=f"Evaluate {action_type.value} for the cancelled confirmatory campaign.",
        repository_modification_required=False,
        actor_role=actor_role,
    )


def test_owned_write_access_does_not_override_explicit_no_rerun(tmp_path) -> None:
    store, fact, assertion, relationship = build_store(tmp_path)

    result = service(store).evaluate(
        proposal(ActionType.RERUN),
        relationship_id=relationship.relationship_id,
        rules=rules(fact, assertion),
    )

    assert relationship.can_write is True
    assert result.decision is ActionPolicyDecision.BLOCKED
    assert result.recommendation.action_type is ActionType.RERUN
    assert result.recommendation.status is ActionStatus.REJECTED
    assert result.recommendation.authorization_required is False
    assert result.matched_rule_ids == ("no-confirmatory-rerun",)
    assert store.get(ActionRecommendation, result.recommendation.action_id) == result.recommendation


def test_classifier_role_gate_blocks_self_classification_but_allows_evaluator(tmp_path) -> None:
    store, fact, assertion, relationship = build_store(tmp_path)
    policy_rules = rules(fact, assertion)
    builder = service(store)

    blocked = builder.evaluate(
        proposal(ActionType.CLASSIFY, actor_role="provider_runner"),
        relationship_id=relationship.relationship_id,
        rules=policy_rules,
    )
    allowed = builder.evaluate(
        proposal(ActionType.CLASSIFY, actor_role="frozen_output_evaluator"),
        relationship_id=relationship.relationship_id,
        rules=policy_rules,
    )

    assert blocked.decision is ActionPolicyDecision.BLOCKED
    assert blocked.recommendation.status is ActionStatus.REJECTED
    assert allowed.decision is ActionPolicyDecision.RECOMMENDED
    assert allowed.recommendation.status is ActionStatus.RECOMMENDED
    assert allowed.recommendation.authorization_required is False


def test_promotion_stays_recommendation_until_independent_authorization(tmp_path) -> None:
    store, fact, assertion, relationship = build_store(tmp_path)

    result = service(store).evaluate(
        proposal(ActionType.PROMOTE),
        relationship_id=relationship.relationship_id,
        rules=rules(fact, assertion),
    )

    assert result.decision is ActionPolicyDecision.REQUIRES_AUTHORIZATION
    assert result.recommendation.status is ActionStatus.RECOMMENDED
    assert result.recommendation.status is not ActionStatus.AUTHORIZED
    assert result.recommendation.authorization_required is True
    assert "does not grant authorization" in result.recommendation.rationale


def test_unconstrained_preservation_is_recommendable(tmp_path) -> None:
    store, fact, assertion, relationship = build_store(tmp_path)

    result = service(store).evaluate(
        proposal(ActionType.PRESERVE),
        relationship_id=relationship.relationship_id,
        rules=rules(fact, assertion),
    )

    assert result.decision is ActionPolicyDecision.RECOMMENDED
    assert result.recommendation.status is ActionStatus.RECOMMENDED
    assert result.recommendation.authorization_required is False
    assert result.matched_rule_ids == ()


def test_policy_evidence_value_mismatch_fails_closed_without_action_record(tmp_path) -> None:
    store, fact, assertion, relationship = build_store(tmp_path)
    broken = ActionPolicyRule(
        rule_id="incorrect-rerun-rule",
        effect=ActionPolicyEffect.PROHIBIT,
        action_types=(ActionType.RERUN,),
        rationale="synthetic mismatch",
        supports=(
            PolicySupportRequirement(
                support_type=SupportType.EVIDENCE_FACT,
                support_id=fact.evidence_id,
                expected_normalized_value=True,
            ),
        ),
    )

    with pytest.raises(ActionPolicyError, match="policy evidence value mismatch"):
        service(store).evaluate(
            proposal(ActionType.RERUN),
            relationship_id=relationship.relationship_id,
            rules=(broken,),
        )

    assert store.list(ActionRecommendation) == []
    assert [run for run in store.list(PipelineRun) if run.run_type is RunType.EVALUATION] == []


def test_policy_support_from_another_source_is_rejected(tmp_path) -> None:
    store, fact, assertion, relationship = build_store(tmp_path)
    other_revision = SourceRevision(
        source_revision_id="source:other@" + "c" * 40,
        source_id="source:other",
        commit_sha="c" * 40,
        tree_sha="d" * 40,
        observed_at=NOW,
    )
    other_artifact = Artifact(
        artifact_id="artifact:other",
        capture_id="capture:other",
        source_locator="other.json",
        content_hash=DIGEST_A,
        media_type="application/json",
    )
    other_manifest = CaptureManifest(
        capture_id="capture:other",
        source_revision_id=other_revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=NOW,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=other_artifact.artifact_id,
                source_locator=other_artifact.source_locator,
                content_hash=other_artifact.content_hash,
                media_type=other_artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    other_fact = EvidenceFact(
        evidence_id="fact:other",
        artifact_id=other_artifact.artifact_id,
        locator="other.json#/confirmatory_rerun_allowed",
        raw_value=False,
        normalized_value=False,
        extractor_name="json-pointer",
        extractor_version="1",
        run_id="run:extract",
    )
    store.put_many((other_revision, other_artifact, other_manifest, other_fact))
    cross_source = ActionPolicyRule(
        rule_id="cross-source-rule",
        effect=ActionPolicyEffect.PROHIBIT,
        action_types=(ActionType.RERUN,),
        rationale="must not borrow another source's rule",
        supports=(
            PolicySupportRequirement(
                support_type=SupportType.EVIDENCE_FACT,
                support_id=other_fact.evidence_id,
                expected_normalized_value=False,
            ),
        ),
    )

    with pytest.raises(ActionPolicyError, match="resolves to source source:other"):
        service(store).evaluate(
            proposal(ActionType.RERUN),
            relationship_id=relationship.relationship_id,
            rules=(cross_source,),
        )


def test_repository_permission_gate_is_separate_from_policy_rules(tmp_path) -> None:
    store, _, _, _ = build_store(tmp_path)
    read_only = RepositoryRelationship(
        relationship_id="relationship:read-only",
        source_id="source:resonance",
        relationship_type=RelationshipType.READ_ONLY,
        can_write=False,
        can_contribute=False,
        observed_at=NOW,
    )
    store.put(read_only)
    write_proposal = ActionProposal(
        proposal_id="proposal:write",
        subject_id="observation:x",
        source_id="source:resonance",
        action_type=ActionType.MITIGATE,
        target="repository",
        rationale="Apply a local repository change.",
        repository_modification_required=True,
        actor_role="operator",
    )

    result = service(store).evaluate(
        write_proposal,
        relationship_id=read_only.relationship_id,
        rules=(),
    )

    assert result.decision is ActionPolicyDecision.BLOCKED
    assert result.recommendation.status is ActionStatus.REJECTED
    assert "can_write=true" in result.recommendation.rationale
