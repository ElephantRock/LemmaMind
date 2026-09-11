#!/usr/bin/env python3
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


BASE_PATH = Path(__file__).with_name("run_m5_frozen_inference.py")
BASE_SPEC = spec_from_file_location("m5_frozen_inference_v12_base", BASE_PATH)
assert BASE_SPEC is not None and BASE_SPEC.loader is not None
BASE = module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE)

RULES_PATH = Path(__file__).with_name("m5_frozen_attention_rules_v16.py")
RULES_SPEC = spec_from_file_location("m5_frozen_attention_rules_v16", RULES_PATH)
assert RULES_SPEC is not None and RULES_SPEC.loader is not None
RULES = module_from_spec(RULES_SPEC)
RULES_SPEC.loader.exec_module(RULES)

BASE_ADAPTER_VERSION = BASE.ADAPTER_VERSION
ADAPTER_VERSION = "zai-glm-5.3.packet-v16"
ATTENTION_V13_RULES = RULES.ATTENTION_V13_RULES
ATTENTION_V14_RULES = RULES.ATTENTION_V14_RULES
ATTENTION_V16_RULES = RULES.ATTENTION_V16_RULES
REPAIR_V15_RULES = RULES.REPAIR_V15_RULES

BASE.ADAPTER_VERSION = ADAPTER_VERSION
BASE.SYSTEM_RULES = (
    BASE.SYSTEM_RULES.rstrip()
    + "\n\n"
    + ATTENTION_V13_RULES.strip()
    + "\n\n"
    + ATTENTION_V14_RULES.strip()
    + "\n\n"
    + ATTENTION_V16_RULES.strip()
    + "\n"
)

SYSTEM_RULES = BASE.SYSTEM_RULES
REVIEW_WORTHINESS_PROVENANCE = BASE.REVIEW_WORTHINESS_PROVENANCE
INVOKE_TIMEOUT_SECONDS = BASE.INVOKE_TIMEOUT_SECONDS
MAX_TIMEOUT_RETRIES = BASE.MAX_TIMEOUT_RETRIES
MAX_SEMANTIC_REPAIRS = BASE.MAX_SEMANTIC_REPAIRS
MAX_INFERENCE_WORKERS = BASE.MAX_INFERENCE_WORKERS
packet_prompt = BASE.packet_prompt
_BASE_REPAIR_PROMPT = BASE.repair_prompt
normalize = BASE.normalize
semantic_reference_fields = BASE.semantic_reference_fields
support_repair_reference = BASE.support_repair_reference

_MALFORMED_OUTPUT_PLACEHOLDER = (
    "<malformed provider output omitted; reconstruct a fresh JSON response from the packet>"
)


def repair_prompt(
    packet: dict,
    *,
    previous_output: str,
    error: Exception,
    repair_attempt: int = 1,
    semantic_reference: dict | None = None,
) -> str:
    malformed_json = semantic_reference is None and isinstance(
        error, BASE.json.JSONDecodeError
    )
    repair_previous_output = (
        _MALFORMED_OUTPUT_PLACEHOLDER if malformed_json else previous_output
    )
    prompt = _BASE_REPAIR_PROMPT(
        packet,
        previous_output=repair_previous_output,
        error=error,
        repair_attempt=repair_attempt,
        semantic_reference=semantic_reference,
    )
    exact_choices = BASE.semantic_support_choices(packet)
    mode_note = (
        "The rejected raw response was malformed JSON and has been deliberately omitted; reconstruct from the packet instead of copying broken text."
        if malformed_json
        else "The rejected response remains available only under the base deterministic repair contract."
    )
    lock_note = (
        "Semantic-lock mode is active: reproduce semantic_reference fields exactly and change only supports plus JSON serialization."
        if semantic_reference is not None
        else "No semantic lock is available because no complete validated semantic reference has been established."
    )
    return (
        prompt.rstrip()
        + "\n\n"
        + REPAIR_V15_RULES.strip()
        + "\n"
        + mode_note
        + "\n"
        + lock_note
        + "\nExact semantic support choices repeated at the final output boundary: "
        + BASE.json.dumps(
            exact_choices,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\nReturn exactly one complete compact single-line JSON object."
    )


BASE.repair_prompt = repair_prompt
infer_packet = BASE.infer_packet
infer_packets = BASE.infer_packets
main = BASE.main


if __name__ == "__main__":
    raise SystemExit(main())
