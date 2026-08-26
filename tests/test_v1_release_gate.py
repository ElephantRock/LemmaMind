from datetime import datetime, timezone

from lemmamind.profile_contracts import (
    TriageAssessment,
    TriageBand,
    TriageReason,
)
from lemmamind.review import ReviewFeedbackService
from lemmamind.contracts import ReviewDecisionType
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking_contracts import TrackingLevel

NOW = datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc)


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"v1-{self.value}"


def test_v1_triage_output_can_receive_append_only_human_feedback(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    triage = TriageAssessment(
        triage_assessment_id="triage:v1",
        architecture_profile_id="architecture-profile:v1",
        source_id="source:v1",
        source_revision_id="revision:v1",
        triage_run_id="run:triage:v1",
        policy_version="deterministic-triage.v1",
        tracking_level=TrackingLevel.STRUCTURAL,
        domain_match=True,
        band=TriageBand.REVIEW,
        reasons=(
            TriageReason.DOMAIN_MATCH,
            TriageReason.EVIDENCE_RICH,
            TriageReason.TRACKING_ACTIVE,
        ),
    )
    store.put(triage)

    result = ReviewFeedbackService(
        store,
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    ).record(
        subject_type="TriageAssessment",
        subject_id=triage.triage_assessment_id,
        decision=ReviewDecisionType.DEEP_DIVE,
        reviewer_id="reviewer:v1-pilot",
        notes="Worth deeper inspection.",
    )

    assert result.feedback.subject_type == "TriageAssessment"
    assert result.feedback.subject_id == triage.triage_assessment_id
    assert result.decision.decision is ReviewDecisionType.DEEP_DIVE
    # Feedback does not rewrite the deterministic triage result.
    assert store.get(TriageAssessment, triage.triage_assessment_id) == triage
