from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference_v13.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v17", SCRIPT_PATH)
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


def test_v17_layers_on_exact_v12_adapter_controls_through_stable_entrypoint():
    prompt = MODULE.packet_prompt(packet())

    assert MODULE.BASE_ADAPTER_VERSION == "zai-glm-5.3.packet-v12"
    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v17"
    assert MODULE.BASE.ADAPTER_VERSION == MODULE.ADAPTER_VERSION
    assert MODULE.INVOKE_TIMEOUT_SECONDS == 600
    assert MODULE.MAX_TIMEOUT_RETRIES == 1
    assert MODULE.MAX_SEMANTIC_REPAIRS == 2
    assert MODULE.MAX_INFERENCE_WORKERS == 2
    assert prompt.startswith(MODULE.SYSTEM_RULES + "\nCandidateEvidencePacket:\n")
    assert "Deterministic adapter repair context" not in prompt
    assert "exact_support_allowlist" not in prompt
    assert "exact_semantic_support_choices" not in prompt
    assert "V15 provider-output repair reliability clarification" not in prompt


def test_v17_retains_v13_proof_burden_and_type_guards():
    lowered = MODULE.SYSTEM_RULES.casefold()

    assert "evidence-burden rule" in lowered
    assert "scope-collapse rule" in lowered
    assert "authority-governance guard" in lowered
    assert "failure guard" in lowered
    assert "temporal-correctness guard" in lowered
    assert "project-state guard" in lowered
    assert "facet convergence rule" in lowered
    assert "canonical-type rule" in lowered
    assert "human-attention rule" in lowered


def test_v17_retains_v14_independent_cross_boundary_evidence_rules():
    lowered = MODULE.ATTENTION_V14_RULES.casefold()

    assert "independent-boundary proof rule" in lowered
    assert "genuinely independent boundary" in lowered
    assert "distinct security principals or trust domains" in lowered
    assert "separately executing lifecycle phases" in lowered
    assert "authoritative producer and a separate durable/external consumer" in lowered
    assert "merely touching several files" in lowered
    assert "self-contained evidence rule" in lowered


def test_v17_retains_v14_authority_from_local_ownership_and_routing_guard():
    lowered = MODULE.ATTENTION_V14_RULES.casefold()

    assert "authority-versus-ownership rule" in lowered
    assert "do not by themselves identify a security principal or trust domain" in lowered
    assert "local object ownership" in lowered
    assert "routing ownership" in lowered
    assert "same-principal allow/deny validation" in lowered
    assert "gains, loses, delegates, or is prevented from exercising a capability" in lowered


def test_v17_retains_v14_authoritative_surface_rules():
    lowered = MODULE.ATTENTION_V14_RULES.casefold()

    assert "authoritative-surface rule" in lowered
    assert "tests, generated files, migration scaffolding, release notes, plans, translations, and documentation" in lowered
    assert "normally evidence about a governing mechanism rather than separate review mechanisms" in lowered
    assert "consumer/ui surface may qualify only when the packet itself directly establishes" in lowered
    assert "externally consumed read/action contract over durable or cross-phase state" in lowered
    assert "presentation alone is insufficient" in lowered


def test_v17_retains_v14_persistence_recovery_and_temporal_independence():
    lowered = MODULE.ATTENTION_V14_RULES.casefold()

    assert "persistence qualification rule" in lowered
    assert "not durable-knowledge evidence by itself" in lowered
    assert "recovery novelty rule" in lowered
    assert "restoring an already-declared behavior" in lowered
    assert "temporal independence rule" in lowered
    assert "independently progressing actors, tasks, processes, devices, or lifecycle epochs" in lowered
    assert "ui rerender order" in lowered


def test_v17_retains_v14_rule_level_knowledge_guard():
    lowered = MODULE.ATTENTION_V14_RULES.casefold()

    assert "rule-versus-facet test" in lowered
    assert "one short imperative that an independent future implementer would need to preserve" in lowered
    assert "without knowing the current file names" in lowered
    assert "subordinate facet of a broader rule" in lowered
    assert "decline rather than creating another mechanism item" in lowered


def test_v17_retains_v16_direct_evidence_and_weak_prior_eligibility():
    lowered = MODULE.ATTENTION_V16_RULES.casefold()

    assert "proof-source rule" in lowered
    assert "source itself is evidence of that contract under the existing five tests" in lowered
    assert "sourceassertion remains fully eligible" in lowered
    assert "do not require runtime implementation bytes solely because" in lowered
    assert "may not substitute for a missing producer, consumer, authority boundary" in lowered
    assert "facet-evidence rule" in lowered
    assert "remain eligible under the existing weak-prior rules" in lowered
    assert "are not hard suppression categories" in lowered
    assert "end-to-end behavioral test that directly exercises the qualifying sides" in lowered
    assert "documentation may qualify when the document itself is the authoritative changed project-state contract" in lowered
    assert "uncertainty-conjunct rule" in lowered
    assert "authoritative implementation or consumer is outside the packet" in lowered
    assert "changed behavior cannot be distinguished from newly added verification" in lowered


def test_v17_retains_v16_boundary_authority_failure_and_temporal_scope():
    lowered = MODULE.ATTENTION_V16_RULES.casefold()

    assert "two-sided boundary rule" in lowered
    assert "direct packet evidence for both sides of the qualifying boundary" in lowered
    assert "a write plus a claim that something later reads it is insufficient" in lowered
    assert "authority-identity rule" in lowered
    assert "directly distinguishes the principals or trust domains on both sides" in lowered
    assert "same-principal policy gate" in lowered
    assert "authenticated request scope remains implementation policy" in lowered
    assert "terminal-disposition proof rule" in lowered
    assert "changed durable terminal disposition or a changed cross-boundary recovery handoff" in lowered
    assert "separate phase, participant, consumer, or operator" in lowered
    assert "temporal-conflict proof rule" in lowered
    assert "independently progressing actors, tasks, processes, devices, or lifecycle epochs" in lowered
    assert "do not narrow this inherited scope" in lowered
    assert "mechanism-language neutrality rule" in lowered
    assert "carry no evidentiary weight by themselves" in lowered


def test_v17_requires_direct_runtime_bridge_and_uncertainty_veto():
    lowered = MODULE.ATTENTION_V17_RULES.casefold()

    assert "declared-runtime bridge rule" in lowered
    assert "does not by itself prove participation by a separate runtime actor" in lowered
    assert "outside the packet, absent, inferred, unexercised, or explicitly not directly shown" in lowered
    assert "required conjunct is unresolved and the decision must be decline" in lowered
    assert "authoritative changed project-state declaration may itself be the governing contract" in lowered
    assert "end-to-end behavioral test may qualify when it actually exercises" in lowered
    assert "uncertainty-veto rule" in lowered
    assert "cannot rescue an interpretation" in lowered
    assert "directly evidenced authoritative project-state declarations" in lowered


def test_v17_distinguishes_changed_behavior_from_new_verification_and_interfaces_from_consumers():
    lowered = MODULE.ATTENTION_V17_RULES.casefold()

    assert "change-versus-verification rule" in lowered
    assert "does not establish review leverage merely because" in lowered
    assert "governing behavior or enforcement rule itself is new or materially changed" in lowered
    assert "newly added or reversed verification" in lowered
    assert "authoritative changed project-state declaration remains eligible" in lowered
    assert "interface-versus-consumer rule" in lowered
    assert "is not a separate consumer merely because another unseen caller could invoke or rely on it" in lowered
    assert "do not infer a cross-boundary handoff from an interface plus prose about an absent caller" in lowered


def test_v17_preserves_direct_consumer_read_action_exception_without_projection_overreach():
    lowered = MODULE.ATTENTION_V17_RULES.casefold()

    assert "direct consumer read/action rule" in lowered
    assert "preserve the existing consumer-surface exception" in lowered
    assert "both observing governed state and performing the governed transition" in lowered
    assert "observed state directly governs subsequent eligibility, required action, terminal/recovery status" in lowered
    assert "may itself establish the qualifying consumer span" in lowered
    assert "do not require separate producer, storage, or persistence implementation bytes" in lowered
    assert "read-only mirror, write-only wrapper, ordinary crud/editor surface" in lowered
    assert "unrelated read and write do not qualify" in lowered


def test_v17_first_pass_includes_v17_and_keeps_v15_repair_guidance_separate():
    prompt = MODULE.packet_prompt(packet())
    lowered = prompt.casefold()

    assert "v16 evidence-role and conjunct-proof clarification" in lowered
    assert "v17 evidence-bridge and direct-consumer clarification" in lowered
    assert "v15 provider-output repair reliability clarification" not in lowered
    assert "exact semantic support choices repeated at the final output boundary" not in lowered
    assert "v17 evidence-bridge and direct-consumer clarification" not in MODULE.REPAIR_V15_RULES.casefold()


def test_v17_preserves_v15_repair_rules_as_repair_only_and_generic():
    lowered = MODULE.REPAIR_V15_RULES.casefold()

    assert "apply only after a provider response has already failed" in lowered
    assert "do not change the five review-worthiness tests" in lowered
    assert "serialization rule" in lowered
    assert "malformed-output reconstruction rule" in lowered
    assert "support-copy rule" in lowered
    assert "semantic-lock serialization rule" in lowered
    assert "repair-economy rule" in lowered
    assert "fail-closed rule" in lowered

    first_pass = MODULE.packet_prompt(packet()).casefold()
    assert "v15 provider-output repair reliability clarification" not in first_pass


def test_v17_preserves_v15_malformed_json_repair_behavior():
    broken = '{"decision":"interpret","summary":"unterminated'
    try:
        MODULE.BASE.json.loads(broken)
    except MODULE.BASE.json.JSONDecodeError as error:
        prompt = MODULE.repair_prompt(
            packet(),
            previous_output=broken,
            error=error,
            repair_attempt=1,
        )
    else:
        raise AssertionError("test fixture must be malformed JSON")

    assert broken not in prompt
    assert MODULE._MALFORMED_OUTPUT_PLACEHOLDER in prompt
    assert "reconstruct from the packet instead of copying broken text" in prompt
    assert "Return exactly one complete compact single-line JSON object" in prompt
    assert '"support_id":"assertion:1","support_type":"SourceAssertion"' in prompt
    assert '"support_id":"structural-delta:1","support_type":"StructuralDelta"' in prompt


def test_v17_preserves_v15_support_copy_semantic_lock():
    semantic_reference = {
        "decision": "interpret",
        "interpretation_types": ["modification"],
        "mechanism": "bounded mechanism",
        "summary": "bounded summary",
        "uncertainty_notes": [],
    }
    rejected = MODULE.BASE.json.dumps(
        {
            **semantic_reference,
            "supports": [
                {
                    "support_type": "StructuralDelta",
                    "support_id": "structural-delta:invented",
                }
            ],
        }
    )
    prompt = MODULE.repair_prompt(
        packet(),
        previous_output=rejected,
        error=ValueError(
            "support lies outside exact packet: StructuralDelta:structural-delta:invented"
        ),
        repair_attempt=2,
        semantic_reference=semantic_reference,
    )

    assert '"semantic_reference"' in prompt
    assert rejected not in prompt
    assert "Semantic-lock mode is active" in prompt
    assert "preserve every supplied non-support semantic field exactly" in prompt
    assert "exactly one compact single-line JSON object" in prompt
    assert "Never convert a supported interpretation to decline" in prompt


def test_v17_preserves_non_audit_provenance_and_has_no_frozen_target_leakage():
    assert MODULE.REVIEW_WORTHINESS_PROVENANCE == (
        "roadmap:I5-security-trust-isolation",
        "roadmap:I7-mechanism-level-knowledge",
        "roadmap:I8-human-attention",
        "docs:M5-CHANGE-SIGNAL-NEXT-SLICE",
    )

    lowered = (
        MODULE.ATTENTION_V14_RULES
        + "\n"
        + MODULE.ATTENTION_V16_RULES
        + "\n"
        + MODULE.ATTENTION_V17_RULES
        + "\n"
        + MODULE.REPAIR_V15_RULES
    ).casefold()
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
