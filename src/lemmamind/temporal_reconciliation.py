"""Evidence-bound temporal reconciliation for source-local belief revision.

This layer does not discover claims. It validates explicit current-state facts and an
ordered provider event transition, then delegates candidate construction to the
revision-aware Observation service. Prior observations remain immutable; belief
revision is represented by ``supersedes_observation_id``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .contracts import EvidenceFact, Observation, ObservationEpistemicType, SupportType
from .observations import ObservationConstructionResult, SupportRef
from .observations_v2 import ObservationConstructionServiceV2


class TemporalReconciliationError(RuntimeError):
    """Temporal evidence is missing, contradictory, or not ordered as declared."""


@dataclass(frozen=True)
class FactExpectation:
    evidence_id: str
    expected_normalized_value: Any


@dataclass(frozen=True)
class OrderedEventTransition:
    from_event_fact_id: str
    from_event: str
    from_timestamp_fact_id: str
    to_event_fact_id: str
    to_event: str
    to_timestamp_fact_id: str


@dataclass(frozen=True)
class TemporalReconciliationResult:
    observation_result: ObservationConstructionResult
    from_timestamp: str
    to_timestamp: str

    @property
    def observation(self) -> Observation:
        return self.observation_result.observation


class TemporalFrontierReconciliationService:
    """Create one superseding candidate after validating temporal evidence.

    The service intentionally remains source-local. ``ObservationConstructionServiceV2``
    still enforces that all current supports resolve to one SourceRevision and that
    the superseded observation belongs to the same Source.
    """

    def __init__(self, store, *, observation_service: ObservationConstructionServiceV2 | None = None) -> None:
        self.store = store
        self.observation_service = observation_service or ObservationConstructionServiceV2(store)

    def reconcile(
        self,
        *,
        logical_claim_id: str,
        prior_observation_id: str,
        epistemic_type: ObservationEpistemicType,
        statement: str,
        supports: tuple[SupportRef, ...],
        expectations: tuple[FactExpectation, ...],
        transition: OrderedEventTransition,
    ) -> TemporalReconciliationResult:
        prior = self.store.get(Observation, prior_observation_id)
        if prior is None:
            raise TemporalReconciliationError(f"prior Observation does not exist: {prior_observation_id}")
        if prior.logical_claim_id != logical_claim_id:
            raise TemporalReconciliationError("temporal reconciliation requires the same logical_claim_id")

        already_superseded = [
            observation.observation_id
            for observation in self.store.list(Observation)
            if observation.supersedes_observation_id == prior_observation_id
        ]
        if already_superseded:
            raise TemporalReconciliationError(
                "prior Observation already has a superseding candidate: " + ", ".join(sorted(already_superseded))
            )

        support_set = set(supports)
        required_fact_ids = {item.evidence_id for item in expectations} | {
            transition.from_event_fact_id,
            transition.from_timestamp_fact_id,
            transition.to_event_fact_id,
            transition.to_timestamp_fact_id,
        }
        for evidence_id in sorted(required_fact_ids):
            if SupportRef(SupportType.EVIDENCE_FACT, evidence_id) not in support_set:
                raise TemporalReconciliationError(
                    f"validated temporal EvidenceFact is not an explicit Observation support: {evidence_id}"
                )

        for expectation in expectations:
            fact = self._fact(expectation.evidence_id)
            if fact.normalized_value != expectation.expected_normalized_value:
                raise TemporalReconciliationError(
                    f"EvidenceFact {expectation.evidence_id} expected "
                    f"{expectation.expected_normalized_value!r}, observed {fact.normalized_value!r}"
                )

        from_event = self._fact(transition.from_event_fact_id)
        from_time = self._fact(transition.from_timestamp_fact_id)
        to_event = self._fact(transition.to_event_fact_id)
        to_time = self._fact(transition.to_timestamp_fact_id)

        if from_event.normalized_value != transition.from_event:
            raise TemporalReconciliationError(
                f"from-event expected {transition.from_event!r}, observed {from_event.normalized_value!r}"
            )
        if to_event.normalized_value != transition.to_event:
            raise TemporalReconciliationError(
                f"to-event expected {transition.to_event!r}, observed {to_event.normalized_value!r}"
            )
        self._require_same_event_record(from_event, from_time)
        self._require_same_event_record(to_event, to_time)
        if from_event.artifact_id != to_event.artifact_id:
            raise TemporalReconciliationError("ordered event transition must come from one event-history artifact")

        from_timestamp = self._timestamp(from_time)
        to_timestamp = self._timestamp(to_time)
        if not from_timestamp < to_timestamp:
            raise TemporalReconciliationError("ordered event transition timestamps are not strictly increasing")

        result = self.observation_service.create_candidate(
            logical_claim_id=logical_claim_id,
            epistemic_type=epistemic_type,
            statement=statement,
            supports=supports,
            supersedes_observation_id=prior_observation_id,
        )
        return TemporalReconciliationResult(
            observation_result=result,
            from_timestamp=from_timestamp.isoformat().replace("+00:00", "Z"),
            to_timestamp=to_timestamp.isoformat().replace("+00:00", "Z"),
        )

    def _fact(self, evidence_id: str) -> EvidenceFact:
        fact = self.store.get(EvidenceFact, evidence_id)
        if fact is None:
            raise TemporalReconciliationError(f"missing EvidenceFact: {evidence_id}")
        return fact

    @staticmethod
    def _require_same_event_record(event_fact: EvidenceFact, timestamp_fact: EvidenceFact) -> None:
        if event_fact.artifact_id != timestamp_fact.artifact_id:
            raise TemporalReconciliationError("event and timestamp facts come from different artifacts")
        event_prefix = event_fact.locator.rsplit("/", 1)[0]
        timestamp_prefix = timestamp_fact.locator.rsplit("/", 1)[0]
        if event_prefix != timestamp_prefix:
            raise TemporalReconciliationError("event and timestamp facts do not describe the same provider event")
        if not event_fact.locator.endswith("/event") or not timestamp_fact.locator.endswith("/created_at"):
            raise TemporalReconciliationError("ordered event transition requires event and created_at locators")

    @staticmethod
    def _timestamp(fact: EvidenceFact) -> datetime:
        value = fact.normalized_value
        if not isinstance(value, str):
            raise TemporalReconciliationError(f"timestamp EvidenceFact is not a string: {fact.evidence_id}")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TemporalReconciliationError(
                f"timestamp EvidenceFact is not ISO-8601: {fact.evidence_id}"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise TemporalReconciliationError(
                f"timestamp EvidenceFact is not timezone-aware: {fact.evidence_id}"
            )
        return parsed
