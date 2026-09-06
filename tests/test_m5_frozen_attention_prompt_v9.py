from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v9", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def packet():
    return {
        "candidate_evidence_packet_id": "packet:test",
        "artifact_delta_ids": ["artifact-delta:1"],
        "structural_delta_previews": [
            {"structural_delta_id": "structural-delta:1"}
        ],
        "assertion_previews": [{"assertion_id": "assertion:1"}],
        "extraction_gap_signal_ids": [],
    }


def test_v9_requires_mechanism_review_span_and_boundary_effect():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v9"
    assert "must pass all three tests" in lowered
    assert "mechanism, review-span, and boundary-effect" in lowered
    assert "review-span test" in lowered
    assert "review-bearing span" in lowered
    assert "this is not a file-count or path-count test" in lowered
    assert "one file may qualify" in lowered


def test_v9_review_span_is_cross_call_component_or_phase_not_local_admission():
    lowered = MODULE.SYSTEM_RULES.casefold()

    for expected in (
        "later session, process, restart, deployment, migration, or recovery phase",
        "independently progressing actors, components, or trust domains",
        "batch, await boundary, retry cycle, lifecycle phase",
        "cross-component failure, recovery, or terminal-state handoff",
        "externally consumed classification, taxonomy, support/compatibility obligation, or operator decision surface",
    ):
        assert expected in lowered
    assert "authority, admission, eligibility, and ownership wording is not enough by itself" in lowered
    assert "single-operation precondition, capability check, parameter validation, endpoint guard" in lowered
    assert "a changed admitted-versus-denied outcome inside one operation is not automatically a review item" in lowered


def test_v9_allows_state_action_consumer_lifecycle_without_allowing_mere_projection():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "externally consumed state/action lifecycle" in lowered
    assert "both observes governed state and performs a governed state transition" in lowered
    assert "is not automatically a projection-only decline" in lowered
    assert "if it merely mirrors, formats, documents, or verifies a contract established elsewhere" in lowered
    assert "decline it" in lowered


def test_v9_keeps_taxonomy_contracts_eligible_only_with_direct_consumer_dependency():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "for classifications, taxonomies, and reason vocabularies" in lowered
    assert "mere logging, serialization, persistence, display, or enumeration is insufficient" in lowered
    assert "may qualify even when downstream action mapping is unchanged" in lowered
    assert "non-local consumer or operator decision surface depends on stable named distinctions" in lowered


def test_v9_declines_local_representation_failure_ownership_and_state_noise():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "decline additive or representational surface changes" in lowered
    assert "request/response fields, methods, enum members, accepted values" in lowered
    assert "local failure-handling details" in lowered
    assert "internal precedence, source-of-truth selection, routing ownership" in lowered
    assert "persistence of presentation state, cache state, layout state" in lowered
    assert "schema/version bookkeeping" in lowered


def test_v9_preserves_weak_prior_not_hard_suppression_rule():
    lowered = MODULE.SYSTEM_RULES.casefold()

    for expected in (
        "tests, fixtures, harnesses",
        "documentation, examples",
        "configuration, workflows",
        "weak priors about review-worthiness",
        "never as hard suppression categories",
        "remains eligible",
    ):
        assert expected in lowered
    assert "changes declared support, compatibility, authority, admission, migration, release behavior" in lowered


def test_v9_canonicalizes_to_review_bearing_lifecycle_and_minimal_type_set():
    rules = MODULE.SYSTEM_RULES

    assert "highest review-bearing contract level directly supported by the packet" in rules
    assert "label the lifecycle rather than the uniqueness check" in rules
    assert "use the same stable governing-contract wording rather than surface-specific wording" in rules
    assert "If the packet contains only a projection without enough evidence for the governing lifecycle, decline" in rules
    assert "Do not add temporal_correctness merely because a newly introduced lifecycle uses a uniqueness constraint" in rules
    assert "Choose the smallest interpretation_types set" in rules
    assert "Use one type whenever one is sufficient" in rules
    assert "Prefer one exact semantic support when one support is sufficient" in rules


def test_v9_has_no_frozen_target_or_threshold_leakage():
    lowered = MODULE.SYSTEM_RULES.casefold()

    forbidden_target_material = (
        "copilotkit/openbot",
        "openclaw/openclaw",
        "nousresearch/hermes-agent",
        "attention/queries.ts",
        "sticky-model-selection.ts",
        "update_contract.py",
        "attention inbox for refusals",
        "policy dry-run against historical judged actions",
        "configurable model-selection scopes",
        "provenance-aware update admission",
        "8/10",
        "primary anchor",
        "openbot:    5",
        "openclaw:  35",
        "hermes:    10",
        "total 50",
    )
    for forbidden in forbidden_target_material:
        assert forbidden not in lowered


def test_v9_keeps_support_copy_failure_separate_from_semantic_decline():
    rules = MODULE.SYSTEM_RULES

    assert "verify every support_id character-for-character" in rules
    assert "Semantic review-worthiness and support-format validity are separate" in rules
    assert "do not convert that support-copy failure into decline" in rules
    assert "return an empty supports array" in rules
    assert "Mechanism must contain 1..240 characters" in rules
    assert "Summary must contain 1..1600 characters" in rules
    assert "uncertainty note must contain at most 800 characters" in rules


def test_v9_preserves_bounded_execution_and_first_pass_is_repair_free():
    prompt = MODULE.packet_prompt(packet())

    assert MODULE.INVOKE_TIMEOUT_SECONDS == 600
    assert MODULE.MAX_TIMEOUT_RETRIES == 1
    assert MODULE.MAX_SEMANTIC_REPAIRS == 2
    assert MODULE.MAX_INFERENCE_WORKERS == 2
    assert prompt.startswith(MODULE.SYSTEM_RULES + "\nCandidateEvidencePacket:\n")
    assert "Deterministic adapter repair context" not in prompt
    assert "exact_support_allowlist" not in prompt
    assert "exact_semantic_support_choices" not in prompt
    assert "forbidden_support_ids" not in prompt
