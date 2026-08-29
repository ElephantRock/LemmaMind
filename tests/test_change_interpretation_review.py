from datetime import datetime, timezone

from lemmamind.change_interpretation_contracts import (
    ChangeInterpretation,
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
    ChangeInterpretationType,
)
from lemmamind.contracts import ReviewDecisionType, ValidationState
from lemmamind.review import ReviewFeedbackService
from lemmamind.storage import SQLiteContractStore


NOW = datetime(2026, 8, 29, 16, 20, tzinfo=timezone.utc)


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"interpretation-review-{self.value}"


def interpretation() -> ChangeInterpretation:
    return ChangeInterpretation(
        change_interpretation_id="change-interpretation:reviewable",
        source_id="github:reviewable-interpretation",
        previous_source_revision_id=(
            "github:reviewable-interpretation@" + "a" * 40
        ),
        current_source_revision_id=(
            "github:reviewable-interpretation@" + "b" * 40
        ),
        interval_candidate_segment_ids=("candidate:reviewable",),
        candidate_factual_reduction_ids=("reduction:reviewable",),
        candidate_evidence_packet_ids=("packet:reviewable",),
        interpretation_types=(ChangeInterpretationType.MODIFICATION,),
        mechanism="Runtime authority check changed",
        summary="The candidate changes the mechanism that gates runtime authority.",
        supports=(
            ChangeInterpretationSupportRef(
                support_type=(
                    ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION
                ),
                support_id="reduction:reviewable",
            ),
            ChangeInterpretationSupportRef(
                support_type=ChangeInterpretationSupportType.STRUCTURAL_DELTA,
                support_id="structural:reviewable",
            ),
        ),
        interpreter_name="test-interpreter",
        interpreter_version="1",
        validation_state=ValidationState.CANDIDATE,
        interpretation_run_id="run:change-interpretation:reviewable",
    )


def test_change_interpretation_is_reviewable_without_mutating_candidate_state(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    subject = interpretation()
    store.put(subject)

    result = ReviewFeedbackService(
        store,
        clock=lambda: NOW,
        id_factory=Ids(),
    ).record(
        subject_type="ChangeInterpretation",
        subject_id=subject.change_interpretation_id,
        decision=ReviewDecisionType.ACCEPT,
        reviewer_id="reviewer:human",
        notes="Mechanism is useful and evidence-bound.",
    )

    assert result.feedback.subject_type == "ChangeInterpretation"
    assert result.feedback.subject_id == subject.change_interpretation_id
    assert result.decision.decision is ReviewDecisionType.ACCEPT
    assert store.get(ChangeInterpretation, subject.change_interpretation_id) == subject
    assert subject.validation_state is ValidationState.CANDIDATE
