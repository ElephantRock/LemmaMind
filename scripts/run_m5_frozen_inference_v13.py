#!/usr/bin/env python3
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import local


BASE_PATH = Path(__file__).with_name("run_m5_frozen_inference.py")
BASE_SPEC = spec_from_file_location("m5_frozen_inference_v12_base", BASE_PATH)
assert BASE_SPEC is not None and BASE_SPEC.loader is not None
BASE = module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE)

RULES_PATH = Path(__file__).with_name("m5_frozen_attention_rules_v18.py")
RULES_SPEC = spec_from_file_location("m5_frozen_attention_rules_v18", RULES_PATH)
assert RULES_SPEC is not None and RULES_SPEC.loader is not None
RULES = module_from_spec(RULES_SPEC)
RULES_SPEC.loader.exec_module(RULES)

BASE_ADAPTER_VERSION = BASE.ADAPTER_VERSION
ADAPTER_VERSION = "zai-glm-5.3.packet-v18r2"
REPAIR_PROTOCOL_VERSION = "support-choice-index-v1"
ATTENTION_V18_RULES = RULES.ATTENTION_V18_RULES
REPAIR_V15_RULES = RULES.REPAIR_V15_RULES

BASE.ADAPTER_VERSION = ADAPTER_VERSION
BASE.SYSTEM_RULES = (
    BASE.SYSTEM_RULES.rstrip()
    + "\n\n"
    + ATTENTION_V18_RULES.strip()
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
_BASE_NORMALIZE = BASE.normalize
semantic_reference_fields = BASE.semantic_reference_fields
support_repair_reference = BASE.support_repair_reference

_MALFORMED_OUTPUT_PLACEHOLDER = (
    "<malformed provider output omitted; reconstruct a fresh JSON response from the packet>"
)
_REPAIR_SEQUENCE = local()


def _packet_key(packet: dict) -> str:
    packet_key = packet.get("candidate_evidence_packet_id")
    if isinstance(packet_key, str) and packet_key:
        return packet_key
    return BASE.json.dumps(
        packet,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sequence_forbidden_support_ids(
    packet: dict,
    *,
    previous_output: str,
    repair_attempt: int,
) -> dict[str, list[str]]:
    packet_key = _packet_key(packet)
    if repair_attempt == 1 or getattr(_REPAIR_SEQUENCE, "packet_key", None) != packet_key:
        _REPAIR_SEQUENCE.packet_key = packet_key
        _REPAIR_SEQUENCE.forbidden = {}

    support_allowlist = {
        support_type: sorted(values)
        for support_type, values in sorted(BASE.allowed_ids(packet).items())
    }
    current = BASE.forbidden_support_ids(previous_output, support_allowlist)
    merged: dict[str, set[str]] = {
        support_type: set(values)
        for support_type, values in getattr(_REPAIR_SEQUENCE, "forbidden", {}).items()
    }
    for support_type, values in current.items():
        merged.setdefault(support_type, set()).update(values)

    normalized = {
        support_type: sorted(values)
        for support_type, values in sorted(merged.items())
        if values
    }
    _REPAIR_SEQUENCE.forbidden = normalized
    return normalized


def _indexed_semantic_support_choices(packet: dict) -> list[dict]:
    return [
        {"choice_index": index, **choice}
        for index, choice in enumerate(BASE.semantic_support_choices(packet), start=1)
    ]


def _indexed_repair_validator_contract() -> dict:
    contract = dict(BASE.repair_validator_contract())
    contract["interpret_required_fields"] = [
        "decision",
        "interpretation_types",
        "mechanism",
        "summary",
        "support_choice_indices",
    ]
    contract["interpret_optional_fields"] = ["uncertainty_notes"]
    contract["support_choice_indices_non_empty_integer_list"] = True
    contract["supports_field_forbidden_in_index_mode"] = True
    return contract


def normalize(packet: dict, response: dict) -> dict:
    if "support_choice_indices" not in response:
        return _BASE_NORMALIZE(packet, response)

    packet_key = _packet_key(packet)
    if getattr(_REPAIR_SEQUENCE, "choice_packet_key", None) != packet_key:
        raise ValueError("support_choice_indices are allowed only during semantic-lock repair")
    if "supports" in response:
        raise ValueError("semantic-lock support-choice repair must not include supports")

    indices = response.get("support_choice_indices")
    if (
        not isinstance(indices, list)
        or not indices
        or any(isinstance(index, bool) or not isinstance(index, int) for index in indices)
    ):
        raise ValueError("support_choice_indices must be a non-empty integer list")

    choices = BASE.semantic_support_choices(packet)
    selected: list[dict[str, str]] = []
    seen: set[int] = set()
    for index in indices:
        if index < 1 or index > len(choices):
            raise ValueError(f"support choice index lies outside exact choices: {index}")
        if index in seen:
            continue
        seen.add(index)
        selected.append(choices[index - 1])

    translated = dict(response)
    translated.pop("support_choice_indices")
    translated["supports"] = selected
    result = _BASE_NORMALIZE(packet, translated)
    _REPAIR_SEQUENCE.choice_packet_key = None
    return result


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
    sequence_forbidden = _sequence_forbidden_support_ids(
        packet,
        previous_output=previous_output,
        repair_attempt=repair_attempt,
    )

    if semantic_reference is not None:
        _REPAIR_SEQUENCE.choice_packet_key = _packet_key(packet)
        repair_context = {
            "adapter_error": str(error),
            "exact_semantic_support_choices_by_index": _indexed_semantic_support_choices(packet),
            "forbidden_support_ids": sequence_forbidden,
            "repair_attempt": repair_attempt,
            "repair_protocol_version": REPAIR_PROTOCOL_VERSION,
            "semantic_reference": semantic_reference,
            "validator_contract": _indexed_repair_validator_contract(),
        }
        return (
            packet_prompt(packet)
            + "\n\nDeterministic adapter repair context:\n"
            + BASE.json.dumps(
                repair_context,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
            + REPAIR_V15_RULES.strip()
            + "\nSemantic-lock mode is active: reproduce semantic_reference fields exactly and do not re-evaluate, broaden, narrow, or rewrite them."
            + "\nSupport-choice index mode is active only for this bounded repair. Do not output support IDs and do not output a supports field."
            + "\nReturn exactly the semantic_reference fields plus support_choice_indices, where support_choice_indices is a non-empty JSON array of integer choice_index values copied from exact_semantic_support_choices_by_index."
            + "\nChoose only entries that directly support the preserved bounded mechanism. Prefer exactly one choice when one is sufficient. The deterministic adapter will copy the selected exact support objects after parsing the indices."
            + "\nNever derive, regenerate, shorten, complete, or invent a support ID. If no listed semantic choice directly supports the preserved interpretation, return an empty support_choice_indices array so deterministic validation rejects the repair instead of silently reclassifying it."
            + "\nCumulative forbidden support IDs across this bounded repair sequence are listed in forbidden_support_ids; a support ID rejected on an earlier attempt remains forbidden on every later attempt in this sequence. In index mode these IDs are diagnostic only and must never be reproduced."
            + "\nReturn exactly one complete compact single-line JSON object."
        )

    repair_previous_output = (
        _MALFORMED_OUTPUT_PLACEHOLDER if malformed_json else previous_output
    )
    prompt = _BASE_REPAIR_PROMPT(
        packet,
        previous_output=repair_previous_output,
        error=error,
        repair_attempt=repair_attempt,
        semantic_reference=None,
    )
    mode_note = (
        "The rejected raw response was malformed JSON and has been deliberately omitted; reconstruct from the packet instead of copying broken text."
        if malformed_json
        else "The rejected response remains available only under the base deterministic repair contract."
    )
    sequence_note = (
        "Cumulative forbidden support IDs across this bounded repair sequence: "
        + BASE.json.dumps(
            sequence_forbidden,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + ". a support ID rejected on an earlier attempt remains forbidden on every later attempt in this sequence; never regenerate it from memory."
        if sequence_forbidden
        else "No invalid support ID has been observed earlier in this bounded repair sequence."
    )
    exact_choices = BASE.semantic_support_choices(packet)
    return (
        prompt.rstrip()
        + "\n\n"
        + REPAIR_V15_RULES.strip()
        + "\n"
        + mode_note
        + "\nNo semantic lock is available because no complete validated semantic reference has been established."
        + "\n"
        + sequence_note
        + "\nExact semantic support choices repeated at the final output boundary: "
        + BASE.json.dumps(
            exact_choices,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\nReturn exactly one complete compact single-line JSON object."
    )


BASE.normalize = normalize
BASE.repair_prompt = repair_prompt
infer_packet = BASE.infer_packet
infer_packets = BASE.infer_packets
main = BASE.main


if __name__ == "__main__":
    raise SystemExit(main())
