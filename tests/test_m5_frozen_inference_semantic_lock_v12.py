from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_inference_semantic_lock_v12", SCRIPT_PATH)
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


def proposal(*, support_id="structural-delta:1", mechanism="bounded mechanism", summary="bounded summary"):
    return {
        "decision": "interpret",
        "interpretation_types": ["modification"],
        "mechanism": mechanism,
        "summary": summary,
        "uncertainty_notes": [],
        "supports": [
            {
                "support_type": "StructuralDelta",
                "support_id": support_id,
            }
        ],
    }


def test_support_repair_rejects_interpret_to_decline_drift_then_can_recover(monkeypatch):
    outputs = iter(
        [
            MODULE.json.dumps(proposal(support_id="structural-delta:invented")),
            '{"decision":"decline"}',
            MODULE.json.dumps(proposal()),
        ]
    )
    prompts = []

    def fake_invoke(_binary, prompt_value):
        prompts.append(prompt_value)
        return next(outputs)

    monkeypatch.setattr(MODULE, "invoke_with_timeout_retry", fake_invoke)

    result = MODULE.infer_packet("/tmp/copilot", packet())

    assert result["status"] == "interpret"
    assert len(prompts) == 3
    assert '"semantic_reference"' in prompts[1]
    assert '"semantic_reference"' in prompts[2]
    assert "support repair changed preserved semantic fields" in prompts[2]
    assert '"previous_output"' not in prompts[2]


def test_support_repair_fails_closed_on_non_support_semantic_mutation(monkeypatch):
    outputs = iter(
        [
            MODULE.json.dumps(proposal(support_id="structural-delta:invented")),
            MODULE.json.dumps(proposal(summary="rewritten summary")),
            MODULE.json.dumps(proposal(mechanism="rewritten mechanism")),
        ]
    )

    monkeypatch.setattr(
        MODULE,
        "invoke_with_timeout_retry",
        lambda _binary, _prompt: next(outputs),
    )

    with pytest.raises(
        RuntimeError,
        match="support repair changed preserved semantic fields",
    ):
        MODULE.infer_packet("/tmp/copilot", packet())


def test_semantic_reference_excludes_rejected_supports_and_is_exact():
    raw = MODULE.json.dumps(proposal(support_id="structural-delta:invented"))
    reference = MODULE.support_repair_reference(
        raw,
        ValueError("support lies outside exact packet: StructuralDelta:structural-delta:invented"),
    )

    assert reference == {
        "decision": "interpret",
        "interpretation_types": ["modification"],
        "mechanism": "bounded mechanism",
        "summary": "bounded summary",
        "uncertainty_notes": [],
    }
    assert "supports" not in reference
