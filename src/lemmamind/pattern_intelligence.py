"""Minimal M8-lite Pattern construction with explicit multi-source provenance.

The service is intentionally proposal-driven: callers provide a candidate Pattern
and source-local occurrence proposals. LemmaMind validates provenance, source
separation, positive-case and negative-control counts, then persists a candidate
Pattern. It does not discover clusters, measure prevalence, or self-promote review
state.
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
    Pattern,
    PatternOccurrence,
    PatternOccurrenceRole,
    PatternOccurrenceSupport,
    PipelineRun,
    RunType,
    SourceAssertion,
    SourceRevision,
    SupportType,
    ValidationState,
)


class PatternConstructionError(RuntimeError):
    """A candidate Pattern violates cross-source provenance or cohort constraints."""


@dataclass(frozen=True)
class OccurrenceProposal:
    source_revision_id: str
    role: PatternOccurrenceRole
    summary: str
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class PatternConstructionResult:
    pattern: Pattern
    occurrences: tuple[PatternOccurrence, ...]
    supports: tuple[PatternOccurrenceSupport, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (self.run, self.pattern, *self.occurrences, *self.supports)


class PatternConstructionService:
    """Persist one cross-source candidate Pattern from source-local Observations."""

    def __init__(
        self,
        store,
        *,
        policy_version: str = "pattern-construction.v1",
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
        occurrences: tuple[OccurrenceProposal, ...],
        minimum_supporting_sources: int = 2,
        minimum_negative_control_sources: int = 0,
    ) -> PatternConstructionResult:
        logical_claim_id = logical_claim_id.strip()
        statement = statement.strip()
        if not logical_claim_id:
            raise PatternConstructionError("logical_claim_id must not be empty")
        if not statement:
            raise PatternConstructionError("statement must not be empty")
        if minimum_supporting_sources < 2:
            raise PatternConstructionError("cross-repository Patterns require at least two supporting Sources")
        if minimum_negative_control_sources < 0:
            raise PatternConstructionError("minimum_negative_control_sources must not be negative")
        if len(occurrences) < 2:
            raise PatternConstructionError("Pattern requires at least two occurrence proposals")

        ordered = tuple(sorted(occurrences, key=self._proposal_sort_key))
        source_ids: set[str] = set()
        source_revisions: set[str] = set()
        observation_ids: set[str] = set()
        supporting_sources: set[str] = set()
        negative_control_sources: set[str] = set()
        resolved: list[tuple[OccurrenceProposal, SourceRevision]] = []

        for proposal in ordered:
            if not proposal.summary.strip():
                raise PatternConstructionError("PatternOccurrence summary must not be empty")
            if not proposal.observation_ids:
                raise PatternConstructionError("PatternOccurrence requires at least one Observation")
            if proposal.source_revision_id in source_revisions:
                raise PatternConstructionError(
                    f"duplicate PatternOccurrence SourceRevision: {proposal.source_revision_id}"
                )
            source_revisions.add(proposal.source_revision_id)

            revision = self.store.get(SourceRevision, proposal.source_revision_id)
            if revision is None:
                raise PatternConstructionError(
                    f"PatternOccurrence references missing SourceRevision: {proposal.source_revision_id}"
                )
            if revision.source_id in source_ids:
                raise PatternConstructionError(
                    "M8-lite counts each Source once per Pattern to avoid pseudo-replication: "
                    f"{revision.source_id}"
                )
            source_ids.add(revision.source_id)

            local_observations = tuple(sorted(set(proposal.observation_ids)))
            if len(local_observations) != len(proposal.observation_ids):
                raise PatternConstructionError("duplicate Observation support in PatternOccurrence")
            for observation_id in local_observations:
                if observation_id in observation_ids:
                    raise PatternConstructionError(
                        f"Observation reused across PatternOccurrences: {observation_id}"
                    )
                observation_ids.add(observation_id)
                observation = self.store.get(Observation, observation_id)
                if observation is None:
                    raise PatternConstructionError(
                        f"PatternOccurrence references missing Observation: {observation_id}"
                    )
                if observation.validation_state is ValidationState.REJECTED:
                    raise PatternConstructionError(
                        f"rejected Observation cannot support PatternOccurrence: {observation_id}"
                    )
                revisions = self._observation_revisions(
                    observation_id,
                    seen_observations=frozenset(),
                )
                if revisions != frozenset({proposal.source_revision_id}):
                    raise PatternConstructionError(
                        "PatternOccurrence Observation support must resolve exactly to its declared "
                        f"SourceRevision; {observation_id} resolved {sorted(revisions)}"
                    )

            if proposal.role is PatternOccurrenceRole.SUPPORTING:
                supporting_sources.add(revision.source_id)
            elif proposal.role is PatternOccurrenceRole.NEGATIVE_CONTROL:
                negative_control_sources.add(revision.source_id)
            resolved.append((proposal, revision))

        if len(source_ids) < 2:
            raise PatternConstructionError("Pattern must span at least two distinct Sources")
        if len(supporting_sources) < minimum_supporting_sources:
            raise PatternConstructionError(
                f"Pattern requires {minimum_supporting_sources} supporting Sources; "
                f"observed {len(supporting_sources)}"
            )
        if len(negative_control_sources) < minimum_negative_control_sources:
            raise PatternConstructionError(
                f"Pattern requires {minimum_negative_control_sources} negative-control Sources; "
                f"observed {len(negative_control_sources)}"
            )

        created_at = self._aware_now()
        run_id = f"run:{self.id_factory()}"
        pattern_id = f"pattern:{self.id_factory()}"
        pattern = Pattern(
            pattern_id=pattern_id,
            logical_claim_id=logical_claim_id,
            epistemic_type=epistemic_type,
            statement=statement,
            validation_state=ValidationState.CANDIDATE,
            synthesis_run_id=run_id,
            created_at=created_at,
        )

        occurrence_records: list[PatternOccurrence] = []
        support_records: list[PatternOccurrenceSupport] = []
        for occurrence_index, (proposal, _) in enumerate(resolved, start=1):
            occurrence_id = f"occurrence:{run_id}:{occurrence_index}"
            occurrence_records.append(
                PatternOccurrence(
                    occurrence_id=occurrence_id,
                    pattern_id=pattern_id,
                    source_revision_id=proposal.source_revision_id,
                    role=proposal.role,
                    summary=proposal.summary.strip(),
                )
            )
            for support_index, observation_id in enumerate(
                sorted(proposal.observation_ids), start=1
            ):
                support_records.append(
                    PatternOccurrenceSupport(
                        support_edge_id=(
                            f"pattern-support:{run_id}:{occurrence_index}:{support_index}"
                        ),
                        occurrence_id=occurrence_id,
                        observation_id=observation_id,
                    )
                )

        inputs_hash = self._digest_json(
            {
                "logical_claim_id": logical_claim_id,
                "epistemic_type": epistemic_type.value,
                "statement": statement,
                "occurrences": [
                    {
                        "source_revision_id": proposal.source_revision_id,
                        "source_id": revision.source_id,
                        "role": proposal.role.value,
                        "summary": proposal.summary.strip(),
                        "observation_ids": sorted(proposal.observation_ids),
                    }
                    for proposal, revision in resolved
                ],
                "minimum_supporting_sources": minimum_supporting_sources,
                "minimum_negative_control_sources": minimum_negative_control_sources,
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "pattern": pattern.model_dump(mode="json"),
                "occurrences": [item.model_dump(mode="json") for item in occurrence_records],
                "supports": [item.model_dump(mode="json") for item in support_records],
            }
        )
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.SYNTHESIS,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=created_at,
            finished_at=created_at,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = PatternConstructionResult(
            pattern=pattern,
            occurrences=tuple(occurrence_records),
            supports=tuple(support_records),
            run=run,
        )
        self.store.put_many(result.records())
        return result

    def _observation_revisions(
        self,
        observation_id: str,
        *,
        seen_observations: frozenset[str],
    ) -> frozenset[str]:
        if observation_id in seen_observations:
            raise PatternConstructionError(
                f"cycle detected in Observation support graph at {observation_id}"
            )
        observation = self.store.get(Observation, observation_id)
        if observation is None:
            raise PatternConstructionError(f"missing Observation: {observation_id}")
        edges = tuple(
            edge
            for edge in self.store.list(ObservationSupport)
            if edge.observation_id == observation_id
        )
        if not edges:
            raise PatternConstructionError(
                f"Observation has no support edges: {observation_id}"
            )
        next_seen = seen_observations | {observation_id}
        revisions: set[str] = set()
        for edge in edges:
            revisions.update(
                self._support_revisions(edge, seen_observations=next_seen)
            )
        return frozenset(revisions)

    def _support_revisions(
        self,
        edge: ObservationSupport,
        *,
        seen_observations: frozenset[str],
    ) -> frozenset[str]:
        if edge.support_type is SupportType.EVIDENCE_FACT:
            fact = self.store.get(EvidenceFact, edge.support_id)
            if fact is None:
                raise PatternConstructionError(f"missing EvidenceFact: {edge.support_id}")
            self._require_complete_run(fact.run_id, RunType.EXTRACTION)
            return frozenset({self._artifact_revision(fact.artifact_id)})
        if edge.support_type is SupportType.SOURCE_ASSERTION:
            assertion = self.store.get(SourceAssertion, edge.support_id)
            if assertion is None:
                raise PatternConstructionError(f"missing SourceAssertion: {edge.support_id}")
            self._require_complete_run(assertion.run_id, RunType.EXTRACTION)
            return frozenset({self._artifact_revision(assertion.artifact_id)})
        if edge.support_type is SupportType.OBSERVATION:
            nested = self.store.get(Observation, edge.support_id)
            if nested is None:
                raise PatternConstructionError(f"missing Observation: {edge.support_id}")
            self._require_complete_run(nested.reasoning_run_id, RunType.REASONING)
            return self._observation_revisions(
                nested.observation_id,
                seen_observations=seen_observations,
            )
        raise PatternConstructionError(f"unsupported Observation support type: {edge.support_type}")

    def _artifact_revision(self, artifact_id: str) -> str:
        artifact = self.store.get(Artifact, artifact_id)
        if artifact is None:
            raise PatternConstructionError(f"missing Artifact: {artifact_id}")
        manifest = self.store.get(CaptureManifest, artifact.capture_id)
        if manifest is None:
            raise PatternConstructionError(
                f"Artifact references missing CaptureManifest: {artifact.capture_id}"
            )
        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise PatternConstructionError(
                f"CaptureManifest references missing SourceRevision: {manifest.source_revision_id}"
            )
        if not any(
            ref.artifact_id == artifact.artifact_id
            and ref.content_hash == artifact.content_hash
            for ref in manifest.artifacts
        ):
            raise PatternConstructionError(
                f"Artifact is not content-bound by CaptureManifest: {artifact.artifact_id}"
            )
        return revision.source_revision_id

    def _require_complete_run(self, run_id: str, expected: RunType) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise PatternConstructionError(f"support references missing PipelineRun: {run_id}")
        if run.run_type is not expected or run.finished_at is None or run.outputs_hash is None:
            raise PatternConstructionError(
                f"support run is not a complete {expected.value} run: {run_id}"
            )
        return run

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise PatternConstructionError("clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _proposal_sort_key(proposal: OccurrenceProposal) -> tuple[str, str, str]:
        return (proposal.source_revision_id, proposal.role.value, proposal.summary)

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()
