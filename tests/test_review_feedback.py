from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    EvidenceFact,
    Observation,
    ObservationEpistemicType,
    PipelineRun,
    ReviewDecision,
    ReviewDecisionType,
    RunType,
    ValidationState,
)
from lemmamind.review import ReviewCaptureError, ReviewFeedbackService
from lemmamind.review_contracts import ReviewFeedback
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc)


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"review-{self.value}"


def seed_observation(store: SQLiteContractStore) -> Observation:
    observation = Observation(
        observation_id="observation:candidate",
        logical_claim_id="claim:demo",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement="The repository uses an explicit authority boundary.",
        validation_state=ValidationState.CANDIDATE,
        reasoning_run_id="run:reasoning:demo",
        created_at=NOW,
    )
    store.put(observation)
    return observation


def test_records_review_decision_feedback_and_evaluation_run_atomically(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    observation = seed_observation(store)
    result = ReviewFeedbackService(
        store,
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    ).record(
        subject_type="Observation",
        subject_id=observation.observation_id,
        decision=ReviewDecisionType.ACCEPT,
        reviewer_id="reviewer:human",
        notes="Useful and correctly scoped.",
    )

    assert result.run.run_type is RunType.EVALUATION
    assert result.run.run_id == "run:review:review-1"
    assert result.feedback.review_id == result.decision.review_id
    assert result.feedback.subject_type == "Observation"
    assert result.feedback.subject_id == observation.observation_id
    assert result.feedback.reviewer_id == "reviewer:human"
    assert result.feedback.review_run_id == result.run.run_id
    assert result.decision.decision is ReviewDecisionType.ACCEPT
    assert store.get(ReviewDecision, result.decision.review_id) == result.decision
    assert store.get(ReviewFeedback, result.feedback.review_feedback_id) == result.feedback
    assert store.get(PipelineRun, result.run.run_id) == result.run


def test_review_capture_does_not_mutate_candidate_validation_state(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    observation = seed_observation(store)
    ReviewFeedbackService(
        store,
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    ).record(
        subject_type="Observation",
        subject_id=observation.observation_id,
        decision=ReviewDecisionType.ACCEPT,
        reviewer_id="reviewer:human",
    )

    persisted = store.get(Observation, observation.observation_id)
    assert persisted is not None
    assert persisted.validation_state is ValidationState.CANDIDATE


def test_multiple_review_events_append_history_for_same_subject(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    observation = seed_observation(store)
    ids = DeterministicIds()
    service = ReviewFeedbackService(store, clock=lambda: NOW, id_factory=ids)

    first = service.record(
        subject_type="Observation",
        subject_id=observation.observation_id,
        decision=ReviewDecisionType.LOW_SIGNAL,
        reviewer_id="reviewer:human",
        notes="Needs stronger evidence.",
    )
    second = service.record(
        subject_type="Observation",
        subject_id=observation.observation_id,
        decision=ReviewDecisionType.DEEP_DIVE,
        reviewer_id="reviewer:human",
        notes="Revisit with the new capture.",
    )

    assert first.decision.review_id != second.decision.review_id
    assert len(store.list(ReviewDecision)) == 2
    assert len(store.list(ReviewFeedback)) == 2
    assert len(store.list(PipelineRun)) == 2


def test_unknown_subject_fails_before_any_review_record_is_written(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    service = ReviewFeedbackService(store, clock=lambda: NOW)

    with pytest.raises(ReviewCaptureError, match="does not exist"):
        service.record(
            subject_type="Observation",
            subject_id="observation:missing",
            decision=ReviewDecisionType.REJECT,
            reviewer_id="reviewer:human",
        )

    assert store.list(ReviewDecision) == []
    assert store.list(ReviewFeedback) == []
    assert store.list(PipelineRun) == []


def test_low_level_evidence_is_not_reviewable_by_default(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    fact = EvidenceFact(
        evidence_id="fact:1",
        artifact_id="artifact:1",
        locator="README.md#x",
        raw_value="x",
        normalized_value="x",
        extractor_name="test",
        extractor_version="1",
        run_id="run:extract",
    )
    store.put(fact)
    service = ReviewFeedbackService(store, clock=lambda: NOW)

    with pytest.raises(ReviewCaptureError, match="not reviewable"):
        service.record(
            subject_type="EvidenceFact",
            subject_id=fact.evidence_id,
            decision=ReviewDecisionType.ACCEPT,
            reviewer_id="reviewer:human",
        )


def test_reviewer_identity_is_required_but_not_interpreted_as_authority(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    observation = seed_observation(store)
    service = ReviewFeedbackService(store, clock=lambda: NOW)

    with pytest.raises(ReviewCaptureError, match="required"):
        service.record(
            subject_type="Observation",
            subject_id=observation.observation_id,
            decision=ReviewDecisionType.PROMOTE,
            reviewer_id="   ",
        )


def test_review_feedback_roundtrips_through_generic_registry(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    observation = seed_observation(store)
    result = ReviewFeedbackService(
        store,
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    ).record(
        subject_type="Observation",
        subject_id=observation.observation_id,
        decision=ReviewDecisionType.CONTRADICT,
        reviewer_id="reviewer:human",
    )

    assert (
        store.get_untyped("ReviewFeedback", result.feedback.review_feedback_id)
        == result.feedback
    )
