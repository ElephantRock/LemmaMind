from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference_v13.py"
SPEC = spec_from_file_location("m5_decision_proof_v19", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def packet():
    return {
        "candidate_evidence_packet_id": "packet:test",
        "artifact_delta_ids": ["artifact-delta:1"],
        "structural_delta_previews": [{"structural_delta_id": "structural-delta:1"}],
        "assertion_previews": [{"assertion_id": "assertion:1"}],
        "extraction_gap_signal_ids": [],
    }


def witness(support_type="SourceAssertion", support_id="assertion:1"):
    return {"support_type": support_type, "support_id": support_id}


def proof(entry=None):
    entry = entry or {"status": "proven", "supports": [witness()]}
    return {test_name: entry for test_name in MODULE.DECISION_PROOF_TESTS}


def response(decision_proof=None):
    return {
        "decision": "interpret",
        "interpretation_types": ["project_state"],
        "mechanism": "bounded mechanism",
        "summary": "bounded summary",
        "uncertainty_notes": ["non-required detail remains unknown"],
        "decision_proof": decision_proof if decision_proof is not None else proof(),
        "supports": [witness()],
    }


def test_v19_requires_decision_proof_for_every_interpretation():
    value = response()
    value.pop("decision_proof")
    with pytest.raises(ValueError, match="decision_proof must be an object"):
        MODULE.normalize(packet(), value)


def test_v19_requires_exact_five_proven_entries():
    missing = proof()
    missing.pop("boundary_effect")
    with pytest.raises(ValueError, match="exactly the five review-worthiness tests"):
        MODULE.normalize(packet(), response(missing))

    not_proven = proof()
    not_proven["review_span"] = {"status": "unresolved", "supports": [witness()]}
    with pytest.raises(ValueError, match="review_span.status must equal proven"):
        MODULE.normalize(packet(), response(not_proven))


def test_v19_requires_non_empty_exact_semantic_packet_witnesses():
    empty = proof()
    empty["review_leverage"] = {"status": "proven", "supports": []}
    with pytest.raises(ValueError, match="review_leverage.supports must be a non-empty list"):
        MODULE.normalize(packet(), response(empty))

    artifact = proof()
    artifact["durable_knowledge"] = {
        "status": "proven",
        "supports": [witness("ArtifactDelta", "artifact-delta:1")],
    }
    with pytest.raises(ValueError, match="outside exact semantic packet support"):
        MODULE.normalize(packet(), response(artifact))

    invented = proof()
    invented["boundary_effect"] = {
        "status": "proven",
        "supports": [witness("SourceAssertion", "assertion:invented")],
    }
    with pytest.raises(ValueError, match="outside exact semantic packet support"):
        MODULE.normalize(packet(), response(invented))


def test_v19_allows_one_exact_witness_to_close_multiple_tests_without_changing_proposal_schema():
    result = MODULE.normalize(packet(), response())

    assert result["status"] == "interpret"
    assert result["decision_proof"] == proof()
    assert "decision_proof" not in result["proposal"]
    assert result["proposal"]["supports"] == [witness()]
    assert result["proposal"]["uncertainty_notes"] == ["non-required detail remains unknown"]


def test_v19_decline_shape_is_unchanged():
    assert MODULE.normalize(packet(), {"decision": "decline"}) == {"status": "decline"}
    with pytest.raises(ValueError, match="decline response may contain only the decision field"):
        MODULE.normalize(packet(), {"decision": "decline", "decision_proof": proof()})


def test_v19_semantic_reference_locks_decision_proof_for_support_repair():
    value = response()
    value["supports"] = []
    reference = MODULE.semantic_reference_fields(value)

    assert reference is not None
    assert reference["decision_proof"] == proof()
    assert "supports" not in reference


def test_v19_repair_validator_contract_exposes_only_existing_five_tests():
    contract = MODULE.repair_validator_contract()

    assert contract["decision_proof_protocol_version"] == "five-test-exact-witness-v1"
    assert contract["decision_proof_exact_tests"] == list(MODULE.DECISION_PROOF_TESTS)
    assert contract["decision_proof_status"] == "proven"
    assert contract["decision_proof_support_types"] == ["SourceAssertion", "StructuralDelta"]
    assert contract["decision_proof_non_empty_exact_packet_supports"] is True
    assert contract["interpret_required_fields"] == [
        "decision",
        "interpretation_types",
        "mechanism",
        "summary",
        "decision_proof",
        "supports",
    ]
