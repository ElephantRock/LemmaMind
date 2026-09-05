from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v7", SCRIPT_PATH)
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


def test_v7_first_pass_requires_mechanism_and_target_independent_contract_consequence():
    rules = MODULE.SYSTEM_RULES
    lowered = rules.casefold()

    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v7"
    assert "candidate-level change" in lowered
    assert "runtime behavior change" in lowered
    assert "externally observable change" in lowered
    assert "must pass both a mechanism test and a contract-consequence test" in lowered
    assert "stable technical or project-state contract, boundary, invariant, or externally consumed classification" in lowered
    assert "target-independent contract dimension" in lowered
    assert "authority, eligibility, control assignment, or ownership" in lowered
    assert "durable state-transition or persistence semantics" in lowered
    assert "externally consumed interface, protocol, configuration, support, compatibility, release, or ci contract" in lowered
    assert "externally consumed classification, taxonomy, or reason vocabulary" in lowered
    assert "used by policy, routing, automation, integration, or operator workflows" in lowered
    assert "failure-handling or recovery semantics" in lowered
    assert "correctness-critical ordering, concurrency, or isolation constraint" in lowered
    assert "can qualify even when downstream action mapping is unchanged" in lowered

    for leaked_consequence_cue in (
        "session, process, retry, reconnect, restart",
        "unsafe mutation",
        "data loss or duplication",
        "silent loss",
        "stuck or unbounded waits",
        "stale ownership/readiness",
    ):
        assert leaked_consequence_cue not in lowered


def test_v7_declines_local_behavior_without_hard_surface_suppression():
    rules = MODULE.SYSTEM_RULES
    lowered = rules.casefold()

    assert "decline localized behavior" in lowered
    assert "one helper, callback, ui interaction" in lowered
    assert "tuning detail" in lowered
    assert "performance optimization" in lowered
    assert "does not establish or alter one of the contract dimensions" in lowered
    assert "do not treat a consumer-visible classification or taxonomy contract as merely local diagnostics" in lowered

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

    assert "documentation, test, configuration, or workflow change" in lowered
    assert "changes declared support, compatibility, authority, admission, release behavior, externally consumed classification" in lowered


def test_v7_has_no_frozen_target_or_threshold_leakage():
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


def test_v7_requests_shared_contract_labels_and_one_central_contract():
    rules = MODULE.SYSTEM_RULES

    assert "highest contract level directly supported by the packet" in rules
    assert "facets of the same contract" in rules
    assert "shared contract label" in rules
    assert "never merge independent contracts" in rules
    assert "single central qualifying contract" in rules
    assert "Choose the smallest interpretation_types set" in rules
    assert "Use one type whenever one is sufficient" in rules
    assert "Prefer one exact semantic support when one support is sufficient" in rules


def test_v7_keeps_support_copy_failure_separate_from_semantic_decline():
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


def test_v7_preserves_bounded_execution_and_first_pass_is_repair_free():
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
