from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_inference_adapter", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SYSTEM_RULES = MODULE.SYSTEM_RULES
normalize = MODULE.normalize
parse_json_object = MODULE.parse_json_object


def packet(*, gaps=()):
    return {
        "candidate_evidence_packet_id": "packet:test",
        "artifact_delta_ids": ["artifact-delta:1"],
        "structural_delta_previews": [
            {"structural_delta_id": "structural-delta:1"}
        ],
        "assertion_previews": [
            {"assertion_id": "assertion:1"}
        ],
        "extraction_gap_signal_ids": list(gaps),
    }


def proposal(**updates):
    value = {
        "decision": "interpret",
        "interpretation_types": ["modification"],
        "mechanism": "session scoped model selection persistence",
        "summary": "The cited structural evidence changes persisted selection behavior.",
        "uncertainty_notes": [],
        "supports": [
            {
                "support_type": "StructuralDelta",
                "support_id": "structural-delta:1",
            }
        ],
    }
    value.update(updates)
    return value


def test_decline_is_exact_and_cannot_carry_hidden_fields():
    assert normalize(packet(), {"decision": "decline"}) == {"status": "decline"}
    with pytest.raises(ValueError, match="only the decision"):
        normalize(packet(), {"decision": "decline", "reason": "low signal"})


def test_interpretation_rejects_support_outside_exact_packet():
    value = proposal(
        supports=[
            {
                "support_type": "StructuralDelta",
                "support_id": "structural-delta:invented",
            }
        ]
    )
    with pytest.raises(ValueError, match="outside exact packet"):
        normalize(packet(), value)


def test_interpretation_requires_structural_or_authored_assertion_support():
    value = proposal(
        supports=[
            {
                "support_type": "ArtifactDelta",
                "support_id": "artifact-delta:1",
            }
        ]
    )
    with pytest.raises(ValueError, match="requires StructuralDelta or SourceAssertion"):
        normalize(packet(), value)


def test_gap_bearing_interpretation_carries_every_gap_and_uncertainty():
    result = normalize(
        packet(gaps=("gap:2", "gap:1")),
        proposal(),
    )
    assert result["status"] == "interpret"
    proposal_value = result["proposal"]
    gap_supports = [
        item["support_id"]
        for item in proposal_value["supports"]
        if item["support_type"] == "CandidateExtractionGapSignal"
    ]
    assert gap_supports == ["gap:1", "gap:2"]
    assert proposal_value["uncertainty_notes"] == [
        "Deterministic extraction coverage is incomplete for one or more paths in this candidate; the mechanism statement is limited to the cited extracted evidence."
    ]


def test_json_parser_rejects_non_object_provider_output():
    with pytest.raises(ValueError, match="one JSON object"):
        parse_json_object("[]")


def test_model_rules_do_not_embed_frozen_target_labels():
    lowered = SYSTEM_RULES.casefold()
    assert "attention/queries" not in lowered
    assert "sticky-model-selection" not in lowered
    assert "update_contract.py" not in lowered
    assert "8/10" not in lowered
    assert "primary anchor" not in lowered
