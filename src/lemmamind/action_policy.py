"""Evidence-bound action-policy validation for the M0 operational boundary.

The service evaluates an explicitly proposed action against repository
relationship and explicit, evidence-supported governance rules. It never executes
an action and never emits ``AUTHORIZED`` status. A recommendation may be rejected,
recommended, or marked as still requiring independent authorization.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue, model_validator

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    ActionRecommendation,
    ActionStatus,
    ActionType,
    Artifact,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RepositoryRelationship,
    RunType,
    SourceAssertion,
    SourceRevision,
    SupportType,
)


class ActionPolicyError(RuntimeError):
    """A proposed action or governance rule violates the policy contract."""


class ActionPolicyEffect(StrEnum):
    PROHIBIT = "prohibit"
    REQUIRE_ROLE = "require_role"
    REQUIRE_INDEPENDENT_AUTHORIZATION = "require_independent_authorization"


class ActionPolicyDecision(StrEnum):
    BLOCKED = "blocked"
    RECOMMENDED = "recommended"
    REQUIRES_AUTHORIZATION = "requires_authorization"


class ActionProposal(BaseModel):
    """Transient proposed operation evaluated before recommendation/authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str
    subject_id: str
    source_id: str
    action_type: ActionType
    target: str
    rationale: str
    repository_modification_required: bool
    actor_role: str

    @model_validator(mode="after")
    def validate_text(self) -> ActionProposal:
        for field in ("proposal_id", "subject_id", "source_id", "target", "rationale", "actor_role"):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"{field} must not be empty")
        return self


class PolicySupportRequirement(BaseModel):
    """Exact direct-evidence condition that makes one policy rule applicable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    support_type: SupportType
    support_id: str
    expected_normalized_value: JsonValue | None = None
    statement_fragments: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_requirement(self) -> PolicySupportRequirement:
        if not self.support_id.strip():
            raise ValueError("support_id must not be empty")
        if self.support_type is SupportType.EVIDENCE_FACT:
            if self.expected_normalized_value is None:
                raise ValueError("EvidenceFact policy support requires expected_normalized_value")
            if self.statement_fragments:
                raise ValueError("EvidenceFact policy support cannot use statement_fragments")
            return self
        if self.support_type is SupportType.SOURCE_ASSERTION:
            if self.expected_normalized_value is not None:
                raise ValueError("SourceAssertion policy support cannot use expected_normalized_value")
            if not self.statement_fragments or any(not item.strip() for item in self.statement_fragments):
                raise ValueError("SourceAssertion policy support requires non-empty statement_fragments")
            return self
        raise ValueError("action-policy.v1 permits only direct EvidenceFact/SourceAssertion support")


class ActionPolicyRule(BaseModel):
    """One explicit governance rule grounded in captured direct evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    effect: ActionPolicyEffect
    action_types: tuple[ActionType, ...]
    rationale: str
    supports: tuple[PolicySupportRequirement, ...]
    allowed_actor_roles: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_rule(self) -> ActionPolicyRule:
        if not self.rule_id.strip() or not self.rationale.strip():
            raise ValueError("rule_id and rationale must not be empty")
        if not self.action_types:
            raise ValueError("policy rule must apply to at least one action type")
        if len(set(self.action_types)) != len(self.action_types):
            raise ValueError("policy rule action_types must be unique")
        if not self.supports:
            raise ValueError("policy rule requires explicit evidence support")
        if self.effect is ActionPolicyEffect.REQUIRE_ROLE:
            roles = tuple(role.strip() for role in self.allowed_actor_roles)
            if not roles or any(not role for role in roles):
                raise ValueError("require_role policy requires allowed_actor_roles")
        elif self.allowed_actor_roles:
            raise ValueError("allowed_actor_roles is only valid for require_role policies")
        return self


@dataclass(frozen=True)
class ActionPolicyResult:
    recommendation: ActionRecommendation
    run: PipelineRun
    decision: ActionPolicyDecision
    matched_rule_ids: tuple[str, ...]
    source_revision_ids: tuple[str, ...]

    def records(self) -> tuple:
        return (self.run, self.recommendation)


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


class ActionPolicyService:
    """Evaluate one proposed action without granting execution authority.

    Policy v1 treats direct captured evidence as the authority for governance
    constraints. Repository write/contribution capability is a separate gate and
    cannot override a matched prohibition or independent-authorization rule.
    """

    def __init__(
        self,
        store: ContractStore,
        *,
        policy_version: str = "action-policy.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def evaluate(
        self,
        proposal: ActionProposal,
        *,
        relationship_id: str,
        rules: tuple[ActionPolicyRule, ...],
    ) -> ActionPolicyResult:
        if len({rule.rule_id for rule in rules}) != len(rules):
            raise ActionPolicyError("policy rule IDs must be unique")

        relationship = self.store.get(RepositoryRelationship, relationship_id)
        if relationship is None:
            raise ActionPolicyError(f"unknown RepositoryRelationship: {relationship_id}")
        if relationship.source_id != proposal.source_id:
            raise ActionPolicyError(
                "RepositoryRelationship source does not match the proposed action source"
            )

        blocked_reasons: list[str] = []
        requires_independent_authorization = False
        matched_rule_ids: list[str] = []
        resolved_revisions: set[str] = set()

        if proposal.repository_modification_required and not relationship.can_write:
            blocked_reasons.append("repository modification requires can_write=true")
        if proposal.action_type is ActionType.CONTRIBUTE_UPSTREAM and not relationship.can_contribute:
            blocked_reasons.append("contribute_upstream requires can_contribute=true")

        for rule in rules:
            if proposal.action_type not in rule.action_types:
                continue
            rule_revisions = self._validate_rule_support(rule, expected_source_id=proposal.source_id)
            resolved_revisions.update(rule_revisions)
            matched_rule_ids.append(rule.rule_id)

            if rule.effect is ActionPolicyEffect.PROHIBIT:
                blocked_reasons.append(f"{rule.rule_id}: {rule.rationale}")
            elif rule.effect is ActionPolicyEffect.REQUIRE_ROLE:
                if proposal.actor_role not in rule.allowed_actor_roles:
                    blocked_reasons.append(
                        f"{rule.rule_id}: actor role {proposal.actor_role!r} is not one of "
                        f"{sorted(rule.allowed_actor_roles)}"
                    )
            elif rule.effect is ActionPolicyEffect.REQUIRE_INDEPENDENT_AUTHORIZATION:
                requires_independent_authorization = True
            else:  # pragma: no cover - enum exhaustiveness guard
                raise ActionPolicyError(f"unsupported policy effect: {rule.effect}")

        if blocked_reasons:
            decision = ActionPolicyDecision.BLOCKED
            status = ActionStatus.REJECTED
            authorization_required = False
        elif requires_independent_authorization:
            decision = ActionPolicyDecision.REQUIRES_AUTHORIZATION
            status = ActionStatus.RECOMMENDED
            authorization_required = True
        else:
            decision = ActionPolicyDecision.RECOMMENDED
            status = ActionStatus.RECOMMENDED
            authorization_required = False

        created_at = self._aware_now()
        run_id = f"run:{self.id_factory()}"
        action_id = f"action:{self.id_factory()}"
        policy_suffix = self._policy_rationale(
            decision=decision,
            matched_rule_ids=tuple(sorted(matched_rule_ids)),
            blocked_reasons=tuple(blocked_reasons),
        )
        recommendation = ActionRecommendation(
            action_id=action_id,
            subject_id=proposal.subject_id,
            action_type=proposal.action_type,
            target=proposal.target,
            rationale=f"{proposal.rationale.rstrip()} {policy_suffix}".strip(),
            repository_modification_required=proposal.repository_modification_required,
            authorization_required=authorization_required,
            status=status,
            created_at=created_at,
        )

        inputs_hash = self._digest_json(
            {
                "proposal": proposal.model_dump(mode="json"),
                "relationship": relationship.model_dump(mode="json"),
                "rules": [rule.model_dump(mode="json") for rule in rules],
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "recommendation": recommendation.model_dump(mode="json"),
                "decision": decision.value,
                "matched_rule_ids": sorted(matched_rule_ids),
                "source_revision_ids": sorted(resolved_revisions),
            }
        )
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.EVALUATION,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=created_at,
            finished_at=created_at,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = ActionPolicyResult(
            recommendation=recommendation,
            run=run,
            decision=decision,
            matched_rule_ids=tuple(sorted(matched_rule_ids)),
            source_revision_ids=tuple(sorted(resolved_revisions)),
        )
        self.store.put_many(result.records())
        return result

    def _validate_rule_support(
        self,
        rule: ActionPolicyRule,
        *,
        expected_source_id: str,
    ) -> set[str]:
        revisions: set[str] = set()
        for support in rule.supports:
            if support.support_type is SupportType.EVIDENCE_FACT:
                record = self.store.get(EvidenceFact, support.support_id)
                if record is None:
                    raise ActionPolicyError(f"missing EvidenceFact policy support: {support.support_id}")
                self._require_extraction_run(record.run_id)
                if record.normalized_value != support.expected_normalized_value:
                    raise ActionPolicyError(
                        f"policy evidence value mismatch for {support.support_id}: "
                        f"expected {support.expected_normalized_value!r}, "
                        f"received {record.normalized_value!r}"
                    )
                revision = self._artifact_revision(record.artifact_id)
            elif support.support_type is SupportType.SOURCE_ASSERTION:
                record = self.store.get(SourceAssertion, support.support_id)
                if record is None:
                    raise ActionPolicyError(
                        f"missing SourceAssertion policy support: {support.support_id}"
                    )
                self._require_extraction_run(record.run_id)
                missing = [
                    fragment
                    for fragment in support.statement_fragments
                    if fragment not in record.statement
                ]
                if missing:
                    raise ActionPolicyError(
                        f"policy assertion fragments missing for {support.support_id}: {missing}"
                    )
                revision = self._artifact_revision(record.artifact_id)
            else:  # model validation should make this unreachable
                raise ActionPolicyError("policy support must be direct evidence")

            if revision.source_id != expected_source_id:
                raise ActionPolicyError(
                    f"policy support {support.support_id} resolves to source "
                    f"{revision.source_id}, expected {expected_source_id}"
                )
            revisions.add(revision.source_revision_id)
        return revisions

    def _artifact_revision(self, artifact_id: str) -> SourceRevision:
        artifact = self.store.get(Artifact, artifact_id)
        if artifact is None:
            raise ActionPolicyError(f"policy support references missing Artifact: {artifact_id}")
        manifest = self.store.get(CaptureManifest, artifact.capture_id)
        if manifest is None:
            raise ActionPolicyError(
                f"policy support Artifact references missing CaptureManifest: {artifact.capture_id}"
            )
        if not any(
            ref.artifact_id == artifact.artifact_id
            and ref.content_hash == artifact.content_hash
            for ref in manifest.artifacts
        ):
            raise ActionPolicyError(
                f"policy support Artifact is not content-bound by its manifest: {artifact.artifact_id}"
            )
        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise ActionPolicyError(
                f"policy support manifest references missing SourceRevision: {manifest.source_revision_id}"
            )
        return revision

    def _require_extraction_run(self, run_id: str) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise ActionPolicyError(f"policy support references missing PipelineRun: {run_id}")
        if run.run_type is not RunType.EXTRACTION:
            raise ActionPolicyError(
                f"policy support run {run_id} has type {run.run_type.value}, expected extraction"
            )
        if run.finished_at is None or run.outputs_hash is None:
            raise ActionPolicyError(f"policy support run is incomplete: {run_id}")
        return run

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ActionPolicyError("action-policy clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _policy_rationale(
        *,
        decision: ActionPolicyDecision,
        matched_rule_ids: tuple[str, ...],
        blocked_reasons: tuple[str, ...],
    ) -> str:
        if decision is ActionPolicyDecision.BLOCKED:
            return "Policy decision: blocked. " + " ".join(blocked_reasons)
        if decision is ActionPolicyDecision.REQUIRES_AUTHORIZATION:
            rules = ", ".join(matched_rule_ids) or "matched governance rule"
            return (
                "Policy decision: recommendation only; independent authorization remains required "
                f"by {rules}. This evaluator does not grant authorization."
            )
        rules = ", ".join(matched_rule_ids)
        if rules:
            return f"Policy decision: recommendable under matched rules {rules}."
        return "Policy decision: recommendable; no blocking governance rule matched."

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()
