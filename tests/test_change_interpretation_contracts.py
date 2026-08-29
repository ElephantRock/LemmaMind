import pytest
from pydantic import ValidationError

from lemmamind.change_interpretation_contracts import (
    ChangeInterpretation,
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
    ChangeInterpretationType,
)
from lemmamind.contracts import CONTRACT_TYPES, ValidationState


def support(kind, support_id):
    return ChangeInterpretationSupportRef(
        support_type=kind,
        support_id=support_id,
    )


def base_kwargs():
    return {
        "change_interpretation_id": "interpretation:test",
        "source_id": "github:test",
        "previous_source_revision_id": "github:test@" + "a" * 40,
        "current_source_revision_id": "github:test@" + "b" * 40,
        "interval_candidate_segment_ids": ("candidate:1",),
        "candidate_factual_reduction_ids": ("reduction:1",),
        "candidate_evidence_packet_ids": ("packet:1",),
        "interpretation_types": (ChangeInterpretationType.MODIFICATION,),
        "mechanism": "Preserve worker timeout deadlines across clock changes",
        "summary": "Timeout accounting now uses a stable elapsed-time basis.",
        "supports": (
            support(
                ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION,
                "reduction:1",
            ),
            support(
                ChangeInterpretationSupportType.STRUCTURAL_DELTA,
                "structural:1",
            ),
        ),
        "interpretation_run_id": "run:change-interpretation:test",
    }


def test_change_interpretation_registers_as_candidate_inferred_contract() -> None:
    item = ChangeInterpretation(**base_kwargs())

    assert CONTRACT_TYPES["ChangeInterpretation"] is ChangeInterpretation
    assert item.validation_state is ValidationState.CANDIDATE
    assert item.interpretation_types == (ChangeInterpretationType.MODIFICATION,)
    assert item.candidate_evidence_packet_ids == ("packet:1",)


def test_change_interpretation_requires_support_for_each_reduction() -> None:
    kwargs = base_kwargs()
    kwargs["supports"] = (
        support(ChangeInterpretationSupportType.STRUCTURAL_DELTA, "structural:1"),
    )

    with pytest.raises(ValidationError, match="explicit support edge"):
        ChangeInterpretation(**kwargs)


def test_change_interpretation_requires_uncertainty_for_gap_support() -> None:
    kwargs = base_kwargs()
    kwargs["supports"] = (
        support(
            ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL,
            "gap:1",
        ),
        support(
            ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION,
            "reduction:1",
        ),
    )

    with pytest.raises(ValidationError, match="require uncertainty"):
        ChangeInterpretation(**kwargs)

    kwargs["uncertainty_notes"] = (
        "One candidate path has incomplete deterministic extraction coverage.",
    )
    item = ChangeInterpretation(**kwargs)
    assert item.uncertainty_notes


def test_change_interpretation_cannot_claim_reviewed_state() -> None:
    kwargs = base_kwargs()
    kwargs["validation_state"] = ValidationState.REVIEWED

    with pytest.raises(ValidationError):
        ChangeInterpretation(**kwargs)


def test_change_interpretation_requires_sorted_unique_membership() -> None:
    kwargs = base_kwargs()
    kwargs["interval_candidate_segment_ids"] = ("candidate:2", "candidate:1")
    kwargs["candidate_factual_reduction_ids"] = ("reduction:1", "reduction:2")
    kwargs["candidate_evidence_packet_ids"] = ("packet:1", "packet:2")

    with pytest.raises(ValidationError, match="sorted and unique"):
        ChangeInterpretation(**kwargs)


def test_change_interpretation_requires_one_packet_per_candidate() -> None:
    kwargs = base_kwargs()
    kwargs["candidate_evidence_packet_ids"] = ("packet:1", "packet:2")

    with pytest.raises(ValidationError, match="one deterministic evidence packet"):
        ChangeInterpretation(**kwargs)
