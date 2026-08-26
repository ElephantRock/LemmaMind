"""V1 basic review/feedback provenance.

ReviewDecision remains the durable user-facing decision record introduced in M0.
ReviewFeedback adds the reviewer/subject/run envelope needed to make basic review
capture executable without changing historical ReviewDecision payloads in place.
"""
from __future__ import annotations

from .contracts import CONTRACT_TYPES, AwareDatetime, ContractModel, Identifier


class ReviewFeedback(ContractModel):
    """Immutable provenance envelope for one ReviewDecision."""

    record_id_field = "review_feedback_id"

    review_feedback_id: Identifier
    review_id: Identifier
    subject_type: Identifier
    subject_id: Identifier
    reviewer_id: Identifier
    review_run_id: Identifier
    recorded_at: AwareDatetime


CONTRACT_TYPES[ReviewFeedback.__name__] = ReviewFeedback

REVIEW_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    ReviewFeedback.__name__: ReviewFeedback,
}
