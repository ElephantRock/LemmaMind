from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v12", SCRIPT_PATH)
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


def test_v12_preserves_v11_mechanism_span_leverage_durable_knowledge_and_boundary_effect():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v12"
    assert "must pass all five tests" in lowered
    assert "mechanism, review-span, review-leverage, durable-knowledge, and boundary-effect" in lowered
    assert "review-span test" in lowered
    assert "review-leverage test" in lowered
    assert "durable-knowledge test" in lowered
    assert "boundary-effect test" in lowered


def test_v11_review_worthiness_provenance_is_non_audit_product_contract():
    assert MODULE.REVIEW_WORTHINESS_PROVENANCE == (
        "roadmap:I5-security-trust-isolation",
        "roadmap:I7-mechanism-level-knowledge",
        "roadmap:I8-human-attention",
        "docs:M5-CHANGE-SIGNAL-NEXT-SLICE",
    )


def test_v11_review_span_retains_generic_contract_dimensions():
    lowered = MODULE.SYSTEM_RULES.casefold()

    for expected in (
        "principal/authority or security trust-boundary rule",
        "durable state, provenance, schema, or ownership lifecycle",
        "cross-boundary failure/recovery handoff or multi-step/multi-participant correctness invariant",
        "externally consumed control, support, compatibility, classification/taxonomy, or operator decision contract",
        "externally consumed operator decision/control or terminal/recovery state/action lifecycle",
    ):
        assert expected in lowered


def test_v11_durable_knowledge_declines_contract_preserving_implementation_churn():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "reusable governing knowledge" in lowered
    assert "future reviewer, operator, or implementer must preserve or act on" in lowered
    assert "a repair that merely restores already-declared behavior is not review leverage" in lowered
    assert "changed enforcement rule as durable governing knowledge" in lowered
    assert "different helper, source, cache, route, key, limit, retry, cleanup, ownership arrangement" in lowered
    assert "defect was fixed under an unchanged governing obligation" in lowered


def test_v11_keeps_cross_boundary_correctness_repairs_eligible_when_rule_itself_is_durable():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "changed enforcement mechanism introduces or materially changes a reusable" in lowered
    assert "cross-boundary/multi-step correctness rule" in lowered
    assert "correctness leverage requires directly evidenced impact on externally or durably consumed state" in lowered
    assert "qualifies only when the packet directly establishes the changed enforcement rule" in lowered


def test_v11_request_local_trust_boundary_contract_remains_eligible():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "may qualify even when enforced within one request when the trust boundary itself is the stable contract" in lowered
    assert "do not decline a rule merely because it is request-local" in lowered
    assert "stable principal/authority contract across distinct trust domains" in lowered
    assert "single-operation parameter validation, request-shape check, helper-local capability test" in lowered
    assert "a changed admitted-versus-denied outcome inside one operation is not automatically a review item" in lowered


def test_v11_facets_need_independent_governing_change():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "facet rule" in lowered
    assert "are not automatically separate review items" in lowered
    assert "independently governing decision, obligation, lifecycle rule" in lowered
    assert "merely implements, exposes, verifies, documents, migrates, or mirrors" in lowered
    assert "decline it rather than creating a separate mechanism item" in lowered


def test_v11_consumer_state_action_lifecycle_stays_decision_bearing():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "both observation of governed state and an action that performs the governed transition" in lowered
    assert "observed state directly governs subsequent eligibility, required action, terminal/recovery status, or another non-local decision outcome" in lowered
    assert "surface change itself materially changes those decision/control semantics" in lowered
    assert "do not require that consumer packet to restate the persistence implementation" in lowered
    assert "read-only mirror, write-only wrapper, ordinary crud/editor surface" in lowered


def test_v11_docs_and_tests_remain_eligible_evidence_surfaces():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "are evidence surfaces, not automatic declines and not automatic mechanisms" in lowered
    assert "may establish a review item without implementation files" in lowered
    assert "authoritative changed project-state contract or a behavioral contract assertion" in lowered
    assert "directly proves the governing rule and changed boundary effect" in lowered
    assert "do not require runtime implementation bytes solely because the evidence surface is a test or document" in lowered
    assert "weak priors about review-worthiness" in lowered
    assert "never as hard suppression categories" in lowered


def test_v11_persistence_and_multiple_components_are_not_sufficient():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "persistence by itself is not enough" in lowered
    assert "multiple components by itself is not enough" in lowered
    assert "internal registry contents, local counters, size limits" in lowered
    assert "shared helper, common validation routine, internal precedence rule" in lowered


def test_v11_keeps_taxonomy_contracts_eligible_only_with_direct_consumer_dependency():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "for classifications, taxonomies, and reason vocabularies" in lowered
    assert "mere logging, serialization, persistence, display, or enumeration is insufficient" in lowered
    assert "may qualify even when downstream action mapping is unchanged" in lowered
    assert "non-local consumer or operator decision surface depends on stable named distinctions" in lowered


def test_v11_canonicalizes_facets_and_normalizes_types():
    rules = MODULE.SYSTEM_RULES
    lowered = rules.casefold()

    assert "Canonicalize aggressively to the governing rule" in rules
    assert "independently evidenced facets converge" in rules
    assert "subject + contract-kind label" in rules
    assert "actor-role adjectives, transport/storage carriers, evidence source" in rules
    assert "<subject> <operation> admission contract" in rules
    assert "<subject> <transition> lifecycle" in rules
    assert "use the same rule-level wording rather than facet-specific wording" in lowered
    assert "Use exactly one type whenever any specific type is sufficient" in rules
    assert "Never combine introduction or modification with a more specific type" in rules
    assert "Prefer one exact semantic support when one semantic support is sufficient" not in rules
    assert "Prefer one exact semantic support when one support is sufficient" in rules


def test_v11_has_no_frozen_identifier_or_threshold_leakage():
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


def test_v11_keeps_support_copy_failure_separate_from_semantic_decline():
    rules = MODULE.SYSTEM_RULES

    assert "verify every support_id character-for-character" in rules
    assert "Semantic review-worthiness and support-format validity are separate" in rules
    assert "do not convert that support-copy failure into decline" in rules
    assert "return an empty supports array" in rules
    assert "Mechanism must contain 1..240 characters" in rules
    assert "Summary must contain 1..1600 characters" in rules
    assert "uncertainty note must contain at most 800 characters" in rules


def test_v12_preserves_bounded_execution_and_first_pass_is_repair_free():
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
