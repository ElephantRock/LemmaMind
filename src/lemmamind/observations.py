"""Evidence-supported Observation construction for the M0 epistemic boundary.

This module does not generate claims. Callers supply a candidate statement and
explicit typed support references. The service validates that every support is
present, provenance-complete, and revision-consistent before atomically
persisting the Observation, support edges, and reasoning PipelineRun.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureManifest,
    EvidenceFact,
    Observation,
    ObservationEpistemicType,
    ObservationSupport,
    PipelineRun,
    RunType,
    SourceAssertion,
    SourceRevision,
    SupportType,
    ValidationState,
)
from .storage import SQLiteContractStore


class ObservationConstructionError(RuntimeError):
    """A candidate Observation violates the explicit-support contract."""


@dataclass(frozen=True, order=True)
class SupportRef:
    support_type: SupportType
    support_id: str


@dataclass(frozen=True)
class ObservationConstructionResult:
    observation: Observation
    supports: tuple[ObservationSupport, ...]
    run: PipelineRun
    source_revision_id: str

    def records(self) -> tuple:
        return (self.observation, *self.supports, self.run)


class ObservationConstructionService:
    """Persist one source-revision-bound candidate Observation with support.

    V1 intentionally permits only a single resolved SourceRevision per
    Observation. Cross-source comparison/synthesis belongs to later Pattern and
    Insight objects rather than being smuggled into a source-level Observation.
    """

    def __init__(
        self,
        store: SQLiteContractStore,
        *,
        policy_version: str = "supported-observation.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

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
            revisions = self._resolve_support_revisions(support, seen_observations=frozenset())
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
                "supported-observation.v1 requires all support to resolve to one SourceRevision; "
                f"resolved {sorted(all_revisions)}"
            )
        source_revision_id = next(iter(all_revisions))

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
                previous.observation_id, seen_observations=frozenset()
            )
            if previous_revisions != all_revisions:
                raise ObservationConstructionError(
                    "supersession requires the same resolved SourceRevision in v1"
                )

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

    def _resolve_support_revisions(
        self,
        support: SupportRef,
        *,
        seen_observations: frozenset[str],
    ) -> frozenset[str]:
        if support.support_type is SupportType.EVIDENCE_FACT:
            record = self.store.get(EvidenceFact, support.support_id)
            if record is None:
                raise ObservationConstructionError(
                    f"missing EvidenceFact support: {support.support_id}"
                )
            self._require_pipeline_run(record.run_id, expected=RunType.EXTRACTION)
            return frozenset({self._artifact_revision(record.artifact_id)})

        if support.support_type is SupportType.SOURCE_ASSERTION:
            record = self.store.get(SourceAssertion, support.support_id)
            if record is None:
                raise ObservationConstructionError(
                    f"missing SourceAssertion support: {support.support_id}"
                )
            self._require_pipeline_run(record.run_id, expected=RunType.EXTRACTION)
            return frozenset({self._artifact_revision(record.artifact_id)})

        if support.support_type is SupportType.OBSERVATION:
            record = self.store.get(Observation, support.support_id)
            if record is None:
                raise ObservationConstructionError(
                    f"missing Observation support: {support.support_id}"
                )
            self._require_pipeline_run(record.reasoning_run_id, expected=RunType.REASONING)
            return self._observation_revisions(
                record.observation_id,
                seen_observations=seen_observations,
            )

        raise ObservationConstructionError(f"unsupported support type: {support.support_type}")

    def _observation_revisions(
        self,
        observation_id: str,
        *,
        seen_observations: frozenset[str],
    ) -> frozenset[str]:
        if observation_id in seen_observations:
            raise ObservationConstructionError(
                f"cycle detected in Observation support graph at {observation_id}"
            )
        observation = self.store.get(Observation, observation_id)
        if observation is None:
            raise ObservationConstructionError(f"missing Observation: {observation_id}")

        edges = tuple(
            edge
            for edge in self.store.list(ObservationSupport)
            if edge.observation_id == observation_id
        )
        if not edges:
            raise ObservationConstructionError(
                f"Observation has no support edges: {observation_id}"
            )

        next_seen = seen_observations | {observation_id}
        revisions: set[str] = set()
        for edge in edges:
            revisions.update(
                self._resolve_support_revisions(
                    SupportRef(edge.support_type, edge.support_id),
                    seen_observations=next_seen,
                )
            )
        return frozenset(revisions)

    def _artifact_revision(self, artifact_id: str) -> str:
        artifact = self.store.get(Artifact, artifact_id)
        if artifact is None:
            raise ObservationConstructionError(
                f"support references missing Artifact: {artifact_id}"
            )
        manifest = self.store.get(CaptureManifest, artifact.capture_id)
        if manifest is None:
            raise ObservationConstructionError(
                f"Artifact references missing CaptureManifest: {artifact.capture_id}"
            )
        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise ObservationConstructionError(
                "CaptureManifest references missing SourceRevision: "
                f"{manifest.source_revision_id}"
            )
        if not any(
            ref.artifact_id == artifact.artifact_id
            and ref.content_hash == artifact.content_hash
            for ref in manifest.artifacts
        ):
            raise ObservationConstructionError(
                f"Artifact is not content-bound by its CaptureManifest: {artifact.artifact_id}"
            )
        return revision.source_revision_id

    def _require_pipeline_run(self, run_id: str, *, expected: RunType) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise ObservationConstructionError(f"support references missing PipelineRun: {run_id}")
        if run.run_type is not expected:
            raise ObservationConstructionError(
                f"support run {run_id} has type {run.run_type.value}, expected {expected.value}"
            )
        if run.finished_at is None or run.outputs_hash is None:
            raise ObservationConstructionError(
                f"support run is incomplete: {run_id}"
            )
        return run

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ObservationConstructionError("clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()
