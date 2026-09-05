from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v6", SCRIPT_PATH)
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


def test_v6_first_pass_encodes_generic_review_worthiness():
    rules = MODULE.SYSTEM_RULES

    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v6"
    assert "candidate-level change is not automatically a human review item" in rules.casefold()
    assert "authority/admission/ownership/persistence boundary" in rules
    assert "durable state lifecycle or invariant" in rules
    assert "failure, recovery, or fail-closed behavior" in rules
    assert "temporal or concurrency ordering" in rules
    assert "externally observable protocol or routing behavior" in rules
    assert "security or resource isolation" in rules
    assert "explicit governance, configuration, compatibility, deprecation, removal, release, or CI contract" in rules


def test_v6_first_pass_treats_non_runtime_surfaces_as_weak_priors_without_target_leakage():
    rules = MODULE.SYSTEM_RULES
    lowered = rules.casefold()

    for expected in (
        "tests, fixtures, harnesses",
        "documentation, examples",
        "configuration, workflows",
        "localization or copy",
        "styling/layout/visual polish",
        "generated metadata",
        "barrel/export/module organization",
        "type-only api cleanup",
        "weak priors about review-worthiness",
        "never as hard suppression categories",
        "remains eligible",
    ):
        assert expected in lowered

    assert "unless the same packet contains direct runtime implementation evidence" not in lowered

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
    )
    for forbidden in forbidden_target_material:
        assert forbidden not in lowered


def test_v6_first_pass_requests_stable_mechanism_names_and_minimal_type_sets():
    rules = MODULE.SYSTEM_RULES

    assert "stable technical or project-state contract" in rules
    assert "facets of one technical or project-state contract, name the shared contract" in rules
    assert "Choose the smallest interpretation_types set" in rules
    assert "Use one type whenever one is sufficient" in rules
    assert "smallest sufficient support set" in rules


def test_v6_first_pass_keeps_support_copy_failure_separate_from_semantic_decline():
    rules = MODULE.SYSTEM_RULES

    assert "verify every support_id character-for-character" in rules
    assert "structural_delta_previews[].structural_delta_id" in rules
    assert "assertion_previews[].assertion_id" in rules
    assert "artifact_delta_ids" in rules
    assert "extraction_gap_signal_ids" in rules
    assert "Semantic review-worthiness and support-format validity are separate" in rules
    assert "do not convert that support-copy failure into decline" in rules
    assert "return an empty supports array" in rules
    assert "Mechanism must contain 1..240 characters" in rules
    assert "Summary must contain 1..1600 characters" in rules
    assert "uncertainty note must contain at most 800 characters" in rules


def test_v6_preserves_bounded_execution_and_first_pass_is_repair_free():
    prompt = MODULE.packet_prompt(packet())

    assert MODULE.INVOKE_TIMEOUT_SECONDS == 600
    assert MODULE.MAX_TIMEOUT_RETRIES == 1
    assert MODULE.MAX_SEMANTIC_REPAIRS == 2
    assert MODULE.MAX_INFERENCE_WORKERS == 2
    assert prompt.startswith(MODULE.SYSTEM_RULES + "\nCandidateEvidencePacket:\n")
    assert "Deterministic adapter repair context" not in prompt
    assert "exact_support_allowlist" not in prompt
    assert "forbidden_support_ids" not in prompt
