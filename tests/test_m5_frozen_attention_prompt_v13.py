from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference_v13.py"
SPEC = spec_from_file_location("m5_frozen_attention_prompt_v18", SCRIPT_PATH)
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


def test_v18_layers_one_consolidated_closure_on_exact_v12_controls():
    prompt = MODULE.packet_prompt(packet())

    assert MODULE.BASE_ADAPTER_VERSION == "zai-glm-5.3.packet-v12"
    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v18"
    assert MODULE.BASE.ADAPTER_VERSION == MODULE.ADAPTER_VERSION
    assert MODULE.INVOKE_TIMEOUT_SECONDS == 600
    assert MODULE.MAX_TIMEOUT_RETRIES == 1
    assert MODULE.MAX_SEMANTIC_REPAIRS == 2
    assert MODULE.MAX_INFERENCE_WORKERS == 2
    assert prompt.startswith(MODULE.SYSTEM_RULES + "\nCandidateEvidencePacket:\n")

    lowered = prompt.casefold()
    assert "v18 five-test decision-closure contract" in lowered
    assert "v13 attention-calibration clarification" not in lowered
    assert "v14 independent-boundary clarification" not in lowered
    assert "v16 evidence-role and conjunct-proof clarification" not in lowered
    assert "v17 evidence-bridge and direct-consumer clarification" not in lowered
    assert "v15 provider-output repair reliability clarification" not in lowered
    assert "deterministic adapter repair context" not in lowered
    assert "exact_support_allowlist" not in lowered
    assert "exact_semantic_support_choices" not in lowered


def test_v18_orders_five_test_proof_before_type_selection_and_fails_closed():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "ordered closure rule" in lowered
    assert "mechanism, review-span, review-leverage, durable-knowledge, boundary-effect" in lowered
    assert "each test needs its own direct witness in the current packet" in lowered
    assert "if any required witness is absent, outside the packet, inferred" in lowered
    assert "decline" in lowered
    assert "choose interpretation type only after all five tests pass" in lowered
    assert "cannot rescue a missing conjunct" in lowered


def test_v18_preserves_rule_level_mechanism_and_human_attention_semantics():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "mechanism closure rule" in lowered
    assert "remove repository-specific nouns" in lowered
    assert "reusable governing knowledge" in lowered
    assert "single-execution implementation technique" in lowered
    assert "facet and canonicalization closure rule" in lowered
    assert "same short rule-level label and canonical type" in lowered
    assert "subordinate facet" in lowered
    assert "human-attention closure rule" in lowered
    assert "silence is valid" in lowered


def test_v18_preserves_review_span_and_direct_consumer_read_action_exception():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "review-span closure rule" in lowered
    assert "distinct principals or trust domains" in lowered
    assert "independent invocation, restart, migration, recovery, deletion/re-admission" in lowered
    assert "cross-boundary failure/recovery handoff" in lowered
    assert "externally consumed support, compatibility, classification, taxonomy, or operator-control contract" in lowered
    assert "direct consumer/operator read-action lifecycle" in lowered
    assert "same consumer surface observing governed state and performing the governed transition" in lowered
    assert "observed state governing subsequent eligibility, required action, terminal/recovery status" in lowered
    assert "do not require separate producer, storage, or persistence implementation bytes" in lowered
    assert "read-only mirrors, write-only wrappers, ordinary crud/editor surfaces" in lowered


def test_v18_preserves_review_leverage_without_verification_substitution():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "review-leverage closure rule" in lowered
    assert "governing contract itself is new or materially changed" in lowered
    assert "newly added verification" in lowered
    assert "do not prove changed governing behavior" in lowered
    assert "authoritative changed project-state declaration may itself be the changed contract" in lowered
    assert "end-to-end behavioral test may establish leverage" in lowered
    assert "repair that merely restores an already-declared obligation is not leverage" in lowered


def test_v18_preserves_durable_knowledge_boundary_effect_and_uncertainty_closure():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "durable-knowledge closure rule" in lowered
    assert "persistence, a schema field, function, callback, command, internal api" in lowered
    assert "interface with an unseen caller is not durable knowledge by itself" in lowered
    assert "boundary-effect closure rule" in lowered
    assert "consequential contract outcome" in lowered
    assert "unseen actor, caller, consumer, executor, operator, or later phase" in lowered
    assert "does not prove that participant or its consequential outcome" in lowered
    assert "uncertainty may describe non-required details but cannot fill" in lowered


def test_v18_preserves_evidence_surface_eligibility_without_execution_only_narrowing():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "evidence-role closure rule" in lowered
    assert "all evidence surfaces remain eligible" in lowered
    assert "sourceassertion may itself be authoritative" in lowered
    assert "weak priors rather than hard suppression categories" in lowered
    assert "direct structural or behavioral packet evidence does not need to be exercised by a test or live execution" in lowered
    assert "do not require runtime implementation bytes" in lowered


def test_v18_closes_specific_types_without_using_type_as_eligibility():
    lowered = MODULE.ATTENTION_V18_RULES.casefold()

    assert "type-closure rule" in lowered
    assert "do not use a type to manufacture eligibility" in lowered
    assert "authority_governance requires directly evidenced distinct principals or trust domains" in lowered
    assert "failure requires a changed durable terminal disposition or a changed cross-boundary recovery handoff" in lowered
    assert "separate phase, participant, consumer, or operator" in lowered
    assert "temporal_correctness requires independently progressing actors, tasks, processes, devices, or lifecycle epochs" in lowered
    assert "timing/conflict relation capable of changing a durable or external outcome" in lowered
    assert "project_state requires an authoritative changed support, compatibility, governance, schema-consumer, or declared project-state contract" in lowered
    assert "use generic introduction or modification only when no more specific qualifying type" in lowered


def test_v18_preserves_v15_repair_as_repair_only():
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


def test_v18_preserves_v15_malformed_json_repair_behavior():
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


def test_v18_preserves_v15_support_copy_semantic_lock():
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


def test_v18_preserves_non_audit_provenance_and_has_no_frozen_target_leakage():
    assert MODULE.REVIEW_WORTHINESS_PROVENANCE == (
        "roadmap:I5-security-trust-isolation",
        "roadmap:I7-mechanism-level-knowledge",
        "roadmap:I8-human-attention",
        "docs:M5-CHANGE-SIGNAL-NEXT-SLICE",
    )

    lowered = (MODULE.ATTENTION_V18_RULES + "\n" + MODULE.REPAIR_V15_RULES).casefold()
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
