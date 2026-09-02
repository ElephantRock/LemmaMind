import pytest

from lemmamind.contracts import ReviewDecisionType
from lemmamind.mechanism_review import MechanismReviewGroupingService
from lemmamind.review import ReviewCaptureError, ReviewFeedbackService
from lemmamind.storage import SQLiteContractStore
from tests.test_mechanism_review import Ids, NOW, seed_authenticated_generation


def test_forged_mechanism_review_item_cannot_receive_feedback(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, interpreted = seed_authenticated_generation(store)
    grouped = MechanismReviewGroupingService(
        store,
        clock=lambda: NOW,
        id_factory=Ids(),
    ).group_interpretation_run(interpreted.run.run_id)
    assert len(grouped.items) == 1

    forged = grouped.items[0].model_copy(
        update={
            "mechanism_review_item_id": "mechanism-review-item:forged-review-subject"
        }
    )
    store.put(forged)

    with pytest.raises(
        ReviewCaptureError,
        match="semantic provenance does not authenticate",
    ):
        ReviewFeedbackService(
            store,
            clock=lambda: NOW,
            id_factory=Ids(),
        ).record(
            subject_type="MechanismReviewItem",
            subject_id=forged.mechanism_review_item_id,
            decision=ReviewDecisionType.ACCEPT,
            reviewer_id="reviewer:human",
        )
