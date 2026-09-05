from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_inference_adapter_v6", SCRIPT_PATH)
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


def proposal(*, support_id="structural-delta:1", summary="bounded summary"):
    return {
        "decision": "interpret",
        "interpretation_types": ["modification"],
        "mechanism": "bounded mechanism",
        "summary": summary,
        "uncertainty_notes": [],
        "supports": [
            {
                "support_type": "StructuralDelta",
                "support_id": support_id,
            }
        ],
    }


def test_repair_context_exposes_validator_limits_and_forbids_rejected_support_ids():
    rejected = MODULE.json.dumps(proposal(support_id="structural-delta:invented"))
    prompt = MODULE.repair_prompt(
        packet(),
        previous_output=rejected,
        error=ValueError("support lies outside exact packet"),
    )

    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v6"
    assert MODULE.MAX_SEMANTIC_REPAIRS == 2
    assert '"summary_max_characters":1600' in prompt
    assert '"mechanism_max_characters":240' in prompt
    assert '"uncertainty_note_max_characters":800' in prompt
    assert '"forbidden_support_ids":{"StructuralDelta":["structural-delta:invented"]}' in prompt
    assert "Treat previous_output as rejected data" in prompt
    assert "Never guess, synthesize, shorten, or rewrite an ID" in prompt
    assert "do not change an otherwise supported interpret decision to decline solely because" in prompt
    assert "keep decision=interpret and return an empty supports array" in prompt


def test_second_bounded_repair_can_recover_without_changing_first_pass(monkeypatch):
    first = MODULE.json.dumps(proposal(support_id="structural-delta:first-invalid"))
    second = MODULE.json.dumps(proposal(support_id="structural-delta:second-invalid"))
    third = MODULE.json.dumps(proposal())
    outputs = iter([first, second, third])
    prompts = []

    def fake_invoke(_binary, prompt_value):
        prompts.append(prompt_value)
        return next(outputs)

    monkeypatch.setattr(MODULE, "invoke_with_timeout_retry", fake_invoke)

    result = MODULE.infer_packet("/tmp/copilot", packet())

    assert result["status"] == "interpret"
    assert len(prompts) == 3
    assert prompts[0] == MODULE.packet_prompt(packet())
    assert "Deterministic adapter repair context" not in prompts[0]
    assert '"repair_attempt":1' in prompts[1]
    assert "structural-delta:first-invalid" in prompts[1]
    assert '"repair_attempt":2' in prompts[2]
    assert "structural-delta:second-invalid" in prompts[2]


def test_persistent_invalid_output_fails_closed_after_two_repairs(monkeypatch):
    outputs = iter(
        [
            MODULE.json.dumps(proposal(support_id="structural-delta:bad-1")),
            MODULE.json.dumps(proposal(support_id="structural-delta:bad-2")),
            MODULE.json.dumps(proposal(support_id="structural-delta:bad-3")),
        ]
    )
    prompts = []

    def fake_invoke(_binary, prompt_value):
        prompts.append(prompt_value)
        return next(outputs)

    monkeypatch.setattr(MODULE, "invoke_with_timeout_retry", fake_invoke)

    with pytest.raises(RuntimeError, match="remained invalid after 2 bounded repairs"):
        MODULE.infer_packet("/tmp/copilot", packet())

    assert len(prompts) == 3


def test_repair_contract_makes_length_failure_actionable():
    rejected = MODULE.json.dumps(proposal(summary="x" * 1601))
    prompt = MODULE.repair_prompt(
        packet(),
        previous_output=rejected,
        error=ValueError("summary must contain 1..1600 characters"),
        repair_attempt=2,
    )

    assert "summary must contain 1..1600 characters" in prompt
    assert '"summary_max_characters":1600' in prompt
    assert '"repair_attempt":2' in prompt


def test_inference_metadata_records_semantic_repair_limit(monkeypatch):
    monkeypatch.setattr(MODULE, "infer_packet", lambda *_args: {"status": "decline"})
    result = MODULE.infer_packets(
        "/tmp/copilot",
        [packet()],
        repo_key="openbot",
        workers=1,
    )

    assert result["semantic_repair_limit"] == 2
    assert result["packet_count"] == 1
    assert result["declined_count"] == 1
    assert result["error_count"] == 0
