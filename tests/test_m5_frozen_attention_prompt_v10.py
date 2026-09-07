from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v10", SCRIPT_PATH)
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


def test_v10_requires_mechanism_span_leverage_and_boundary_effect():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v10"
    assert "must pass all four tests" in lowered
    assert "mechanism, review-span, review-leverage, and boundary-effect" in lowered
    assert "review-span test" in lowered
    assert "review-leverage test" in lowered
    assert "boundary-effect test" in lowered


def test_v10_review_worthiness_provenance_is_non_audit_product_contract():
    assert MODULE.REVIEW_WORTHINESS_PROVENANCE == (
        "roadmap:I5-security-trust-isolation",
        "roadmap:I7-mechanism-level-knowledge",
        "roadmap:I8-human-attention",
        "docs:M5-CHANGE-SIGNAL-NEXT-SLICE",
    )


def test_v10_review_span_uses_narrow_generic_contract_dimensions():
    lowered = MODULE.SYSTEM_RULES.casefold()

    for expected in (
        "principal/authority or security trust-boundary rule",
        "durable state, provenance, schema, or ownership lifecycle",
        "cross-boundary failure/recovery handoff or multi-step/multi-participant correctness invariant",
        "externally consumed control, support, compatibility, classification/taxonomy, or operator decision contract",
        "externally consumed state/action lifecycle",
    ):
        assert expected in lowered
    assert "shared rule directly consumed by independently progressing actors, components, or trust domains" not in lowered


def test_v10_review_leverage_declines_internal_contract_preserving_repairs():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "governing review-bearing contract is itself new or materially changed" in lowered
    assert "changed enforcement mechanism materially changes the fail-closed, recovery, terminal, migration, re-admission, trust-boundary, or cross-boundary/multi-step correctness semantics" in lowered
    assert "correctness leverage requires directly evidenced impact on externally or durably consumed state" in lowered
    assert "refactor, implementation repair, shared helper, internal ownership transfer" in lowered
    assert "not review-bearing merely because it is stable, persistent, cross-file, or consumed by multiple components" in lowered
    assert "do not manufacture review leverage" in lowered


def test_v10_request_local_trust_boundary_contract_remains_eligible():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "may qualify even when enforced within one request when the trust boundary itself is the stable contract" in lowered
    assert "do not decline a rule merely because it is request-local" in lowered
    assert "stable principal/authority contract across distinct trust domains" in lowered
    assert "single-operation parameter validation, request-shape check, helper-local capability test" in lowered
    assert "a changed admitted-versus-denied outcome inside one operation is not automatically a review item" in lowered


def test_v10_consumer_state_action_lifecycle_is_eligible_without_persistence_restatement():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "both observation of governed state and an action that performs the governed transition" in lowered
    assert "do not require that consumer packet to restate the persistence implementation" in lowered
    assert "read-only mirror, write-only wrapper" in lowered
    assert "does not qualify on that basis alone" in lowered


def test_v10_persistence_and_multiple_components_are_not_sufficient():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "persistence by itself is not enough" in lowered
    assert "multiple components by itself is not enough" in lowered
    assert "internal registry contents, local counters, size limits" in lowered
    assert "shared helper, common validation routine, internal precedence rule" in lowered


def test_v10_keeps_taxonomy_contracts_eligible_only_with_direct_consumer_dependency():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "for classifications, taxonomies, and reason vocabularies" in lowered
    assert "mere logging, serialization, persistence, display, or enumeration is insufficient" in lowered
    assert "may qualify even when downstream action mapping is unchanged" in lowered
    assert "non-local consumer or operator decision surface depends on stable named distinctions" in lowered


def test_v10_preserves_weak_prior_not_hard_suppression_rule():
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


def test_v10_canonicalizes_to_governing_contract_and_minimal_type_set():
    rules = MODULE.SYSTEM_RULES

    assert "highest review-bearing contract level directly supported by the packet" in rules
    assert "Prefer stable subject + governing operation/contract-kind wording" in rules
    assert "Omit surface, phase, implementation, and enforcement-detail qualifiers" in rules
    assert "label the governing lifecycle rather than the subordinate check" in rules
    assert "use the same governing-contract wording rather than surface-specific wording" in rules
    assert "Choose the smallest interpretation_types set" in rules
    assert "Use one type whenever one is sufficient" in rules
    assert "Prefer one exact semantic support when one support is sufficient" in rules


def test_v10_has_no_frozen_identifier_or_threshold_leakage():
    lowered = MODULE.SYSTEM_RULES.casefold()

    forbidden_frozen_material = (
        "copilotkit/openbot",
        "openclaw/openclaw",
        "nousresearch/hermes-agent",
        "attention/queries.ts",
        "sticky-model-selection.ts",
        "update_contract.py",
        "8/10",
        "primary anchor",
        "openbot:    5",
        "openclaw:  35",
        "hermes:    10",
        "total 50",
    )
    for forbidden in forbidden_frozen_material:
        assert forbidden not in lowered


def test_v10_keeps_support_copy_failure_separate_from_semantic_decline():
    rules = MODULE.SYSTEM_RULES

    assert "verify every support_id character-for-character" in rules
    assert "Semantic review-worthiness and support-format validity are separate" in rules
    assert "do not convert that support-copy failure into decline" in rules
    assert "return an empty supports array" in rules
    assert "Mechanism must contain 1..240 characters" in rules
    assert "Summary must contain 1..1600 characters" in rules
    assert "uncertainty note must contain at most 800 characters" in rules


def test_v10_preserves_bounded_execution_and_first_pass_is_repair_free():
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
