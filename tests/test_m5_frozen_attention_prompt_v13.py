from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference_v13.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v13", SCRIPT_PATH)
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


def test_v13_layers_attention_clarification_on_exact_v12_adapter_controls():
    prompt = MODULE.packet_prompt(packet())

    assert MODULE.BASE_ADAPTER_VERSION == "zai-glm-5.3.packet-v12"
    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v13"
    assert MODULE.BASE.ADAPTER_VERSION == MODULE.ADAPTER_VERSION
    assert MODULE.INVOKE_TIMEOUT_SECONDS == 600
    assert MODULE.MAX_TIMEOUT_RETRIES == 1
    assert MODULE.MAX_SEMANTIC_REPAIRS == 2
    assert MODULE.MAX_INFERENCE_WORKERS == 2
    assert prompt.startswith(MODULE.SYSTEM_RULES + "\nCandidateEvidencePacket:\n")
    assert "Deterministic adapter repair context" not in prompt
    assert "exact_support_allowlist" not in prompt
    assert "exact_semantic_support_choices" not in prompt


def test_v13_requires_direct_proof_instead_of_semantic_rebranding():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "evidence-burden rule" in lowered
    assert "directly establishes each required element" in lowered
    assert "plausible downstream consequence" in lowered
    assert "scope-collapse rule" in lowered
    assert "single-execution implementation rule" in lowered
    assert "human-attention rule" in lowered
    assert "reusable governing knowledge" in lowered


def test_v13_tightens_specific_type_guards_without_new_product_types():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "authority-governance guard" in lowered
    assert "distinct principal, trust domain, or security authority" in lowered
    assert "do not relabel ordinary validation" in lowered
    assert "failure guard" in lowered
    assert "changed durable terminal disposition" in lowered
    assert "temporal-correctness guard" in lowered
    assert "independently progressing participants" in lowered
    assert "project-state guard" in lowered
    assert "authoritative changed support, compatibility, governance, schema-consumer" in lowered


def test_v13_requires_facet_label_and_type_convergence_or_decline():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "facet convergence rule" in lowered
    assert "exactly the same short mechanism label and the same canonical interpretation type" in lowered
    assert "remove facet-specific adjectives" in lowered
    assert "decline that facet instead of emitting a parallel mechanism item" in lowered
    assert "canonical-type rule" in lowered
    assert "do not split one governing mechanism" in lowered


def test_v13_preserves_non_audit_provenance_and_has_no_frozen_target_leakage():
    assert MODULE.REVIEW_WORTHINESS_PROVENANCE == (
        "roadmap:I5-security-trust-isolation",
        "roadmap:I7-mechanism-level-knowledge",
        "roadmap:I8-human-attention",
        "docs:M5-CHANGE-SIGNAL-NEXT-SLICE",
    )

    lowered = MODULE.ATTENTION_V13_RULES.casefold()
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
