"""Revision-aware Observation construction for belief revision.

V2 preserves the v1 rule that one Observation is supported by one resolved
SourceRevision, but corrects supersession semantics: a later Observation may
supersede an earlier Observation from a different revision when both revisions
belong to the same Source and the logical claim identity is unchanged.

Cross-source support remains rejected. Cross-repository synthesis belongs to
Pattern/Insight layers rather than being encoded as a source-level Observation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    Observation,
    ObservationEpistemicType,
    ObservationSupport,
    PipelineRun,
    RunType,
    SourceRevision,
    ValidationState,
)
from .observations import (
    ObservationConstructionError,
    ObservationConstructionResult,
    ObservationConstructionService,
    SupportRef,
)


class ObservationConstructionServiceV2(ObservationConstructionService):
    """Construct one revision-bound candidate with revision-aware supersession."""

    def __init__(
        self,
        store,
        *,
        policy_version: str = "supported-observation.v2",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        super().__init__(
            store,
            policy_version=policy_version,
            code_version=code_version,
            clock=clock,
            id_factory=id_factory,
        )

    def create_candidate(
        self,
        *,
        logical_claim_id: str,
        epistemic_type: ObservationEpistemicType,
        statement: str,
        supports: tuple[SupportRef, ...],
        supersedes_observation_id: str | None = None,
    ) -> ObservationConstructionResult:
        logical_claim_id = logical_claim_id.strip()
        statement = statement.strip()
        if not logical_claim_id:
            raise ObservationConstructionError("logical_claim_id must not be empty")
        if not statement:
            raise ObservationConstructionError("statement must not be empty")
        if not supports:
            raise ObservationConstructionError("candidate observations require explicit support")

        ordered_supports = tuple(sorted(supports))
        if len(set(ordered_supports)) != len(ordered_supports):
            raise ObservationConstructionError("duplicate support references are not allowed")

        support_revisions: dict[SupportRef, frozenset[str]] = {}
        for support in ordered_supports:
            revisions = self._resolve_support_revisions(
                support,
                seen_observations=frozenset(),
            )
            if not revisions:
                raise ObservationConstructionError(
                    f"support {support.support_type.value}:{support.support_id} has no source revision"
                )
            support_revisions[support] = revisions

        all_revisions = frozenset(
            revision
            for revisions in support_revisions.values()
            for revision in revisions
        )
        if len(all_revisions) != 1:
            raise ObservationConstructionError(
                "supported-observation.v2 requires all support to resolve to one SourceRevision; "
                f"resolved {sorted(all_revisions)}"
            )
        source_revision_id = next(iter(all_revisions))
        current_revision = self.store.get(SourceRevision, source_revision_id)
        if current_revision is None:
            raise ObservationConstructionError(
                f"resolved SourceRevision does not exist: {source_revision_id}"
            )

        previous_revision_ids: tuple[str, ...] = ()
        if supersedes_observation_id is not None:
            previous = self.store.get(Observation, supersedes_observation_id)
            if previous is None:
                raise ObservationConstructionError(
                    f"superseded Observation does not exist: {supersedes_observation_id}"
                )
            if previous.logical_claim_id != logical_claim_id:
                raise ObservationConstructionError(
                    "supersession requires the same logical_claim_id"
                )
            previous_revisions = self._observation_revisions(
                previous.observation_id,
                seen_observations=frozenset(),
            )
            if len(previous_revisions) != 1:
                raise ObservationConstructionError(
                    "superseded source-level Observation must resolve to exactly one SourceRevision"
                )
            previous_revision_id = next(iter(previous_revisions))
            previous_revision = self.store.get(SourceRevision, previous_revision_id)
            if previous_revision is None:
                raise ObservationConstructionError(
                    f"superseded SourceRevision does not exist: {previous_revision_id}"
                )
            if previous_revision.source_id != current_revision.source_id:
                raise ObservationConstructionError(
                    "supersession requires previous and current revisions to belong to the same Source"
                )
            previous_revision_ids = tuple(sorted(previous_revisions))

        created_at = self._aware_now()
        run_id = f"run:{self.id_factory()}"
        observation_id = f"observation:{self.id_factory()}"

        inputs_hash = self._digest_json(
            {
                "logical_claim_id": logical_claim_id,
                "epistemic_type": epistemic_type.value,
                "statement": statement,
                "supports": [
                    {
                        "support_type": support.support_type.value,
                        "support_id": support.support_id,
                        "source_revision_ids": sorted(support_revisions[support]),
                    }
                    for support in ordered_supports
                ],
                "current_source_revision_id": source_revision_id,
                "previous_source_revision_ids": list(previous_revision_ids),
                "supersedes_observation_id": supersedes_observation_id,
                "policy_version": self.policy_version,
            }
        )

        observation = Observation(
            observation_id=observation_id,
            logical_claim_id=logical_claim_id,
            epistemic_type=epistemic_type,
            statement=statement,
            validation_state=ValidationState.CANDIDATE,
            reasoning_run_id=run_id,
            created_at=created_at,
            supersedes_observation_id=supersedes_observation_id,
        )
        edges = tuple(
            ObservationSupport(
                support_edge_id=f"support:{run_id}:{index}",
                observation_id=observation_id,
                support_id=support.support_id,
                support_type=support.support_type,
            )
            for index, support in enumerate(ordered_supports, start=1)
        )
        outputs_hash = self._digest_json(
            {
                "observation": observation.model_dump(mode="json"),
                "supports": [edge.model_dump(mode="json") for edge in edges],
                "source_revision_id": source_revision_id,
                "superseded_source_revision_ids": list(previous_revision_ids),
            }
        )
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.REASONING,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=created_at,
            finished_at=created_at,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )

        self.store.put_many((run, observation, *edges))
        return ObservationConstructionResult(
            observation=observation,
            supports=edges,
            run=run,
            source_revision_id=source_revision_id,
        )
