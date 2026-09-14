from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference_v13.py"
SPEC = spec_from_file_location("m5_support_choice_index", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def packet(packet_id="packet:test"):
    return {
        "candidate_evidence_packet_id": packet_id,
        "artifact_delta_ids": [],
        "structural_delta_previews": [{"structural_delta_id": "structural-delta:1"}],
        "assertion_previews": [{"assertion_id": "assertion:1"}],
        "extraction_gap_signal_ids": [],
    }


def reference():
    return {
        "decision": "interpret",
        "interpretation_types": ["project_state"],
        "mechanism": "bounded mechanism",
        "summary": "bounded summary",
        "uncertainty_notes": [],
    }


def activate_choice_mode():
    MODULE.repair_prompt(
        packet(),
        previous_output=MODULE.BASE.json.dumps({**reference(), "supports": []}),
        error=ValueError("supports must be a non-empty list"),
        repair_attempt=1,
        semantic_reference=reference(),
    )


def test_repair_prompt_uses_indexed_support_choices():
    prompt = MODULE.repair_prompt(
        packet(),
        previous_output=MODULE.BASE.json.dumps({**reference(), "supports": []}),
        error=ValueError("supports must be a non-empty list"),
        repair_attempt=1,
        semantic_reference=reference(),
    )
    assert MODULE.REPAIR_PROTOCOL_VERSION == "support-choice-index-v1"
    assert "support_choice_indices" in prompt
    assert '"choice_index":1' in prompt
    assert '"choice_index":2' in prompt
    assert '"supports_field_forbidden_in_index_mode":true' in prompt
    assert '"interpret_required_fields":["decision","interpretation_types","mechanism","summary","support_choice_indices"]' in prompt


def test_index_maps_to_exact_support_object():
    activate_choice_mode()
    result = MODULE.normalize(packet(), {**reference(), "support_choice_indices": [2]})
    assert result["proposal"]["supports"] == [
        {"support_type": "StructuralDelta", "support_id": "structural-delta:1"}
    ]


def test_index_mode_is_repair_only_and_bounds_checked():
    with pytest.raises(ValueError, match="allowed only during semantic-lock repair"):
        MODULE.normalize(packet("packet:fresh"), {**reference(), "support_choice_indices": [1]})

    activate_choice_mode()
    with pytest.raises(ValueError, match="outside exact choices"):
        MODULE.normalize(packet(), {**reference(), "support_choice_indices": [3]})


def test_frozen_controls_and_first_pass_are_unchanged():
    first_pass = MODULE.packet_prompt(packet()).casefold()
    assert MODULE.ADAPTER_VERSION == "zai-glm-5.3.packet-v18r1"
    assert MODULE.BASE_ADAPTER_VERSION == "zai-glm-5.3.packet-v12"
    assert MODULE.INVOKE_TIMEOUT_SECONDS == 600
    assert MODULE.MAX_TIMEOUT_RETRIES == 1
    assert MODULE.MAX_SEMANTIC_REPAIRS == 2
    assert MODULE.MAX_INFERENCE_WORKERS == 2
    assert "support_choice_indices" not in first_pass
