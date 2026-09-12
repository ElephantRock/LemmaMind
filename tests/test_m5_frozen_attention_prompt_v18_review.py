from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference_v13.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v18_review", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_v18_shared_packet_fact_can_directly_witness_multiple_tests():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "the same packet fact may witness more than one test" in lowered
    assert "independently and directly proves each of those tests" in lowered
    assert "no distinct-support count is required" in lowered


def test_v18_review_span_preserves_distinct_component_and_operator_forms():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "distinct principals, components, or trust domains" in lowered
    assert "same consumer or operator surface observing governed state and performing the governed transition" in lowered


def test_v18_durable_lifecycle_span_stays_within_inherited_phase_boundary():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "independent invocation, restart, migration, recovery, deletion/re-admission, or another independently executed phase" in lowered
    assert "deletion/re-admission, participant, or later phase" not in lowered


def test_v18_human_attention_preserves_request_local_trust_boundary_eligibility():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "across a qualifying review-bearing span" in lowered
    assert "stable trust-boundary contracts that may be enforced within one request" in lowered
    assert "when the trust boundary itself is the durable rule" in lowered


def test_v18_preserves_behavioral_sourceassertion_eligibility():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "sourceassertion may itself be authoritative when its source is the changed project-state contract" in lowered
    assert "behavioral contract assertion remains eligible when it itself directly proves the governing rule and changed boundary effect" in lowered
