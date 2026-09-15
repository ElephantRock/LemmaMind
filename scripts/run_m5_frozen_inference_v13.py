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
ADAPTER_VERSION = "zai-glm-5.3.packet-v19"
REPAIR_PROTOCOL_VERSION = "support-choice-index-v1"
DECISION_PROOF_PROTOCOL_VERSION = "five-test-exact-witness-v1"
DECISION_PROOF_TESTS = (
    "mechanism",
    "review_span",
    "review_leverage",
    "durable_knowledge",
    "boundary_effect",
)
ATTENTION_V18_RULES = RULES.ATTENTION_V18_RULES
REPAIR_V15_RULES = RULES.REPAIR_V15_RULES
DECISION_PROOF_V19_RULES = """V19 machine-readable decision-proof contract. This adds no product criterion and does not change V18 evidence eligibility, exceptions, canonicalization, or any frozen product gate. It makes the existing five conjunctive tests explicit at the deterministic adapter boundary.
Decision-proof ledger rule: for decision=interpret, output one additional required field named decision_proof. It must contain exactly these five keys: mechanism, review_span, review_leverage, durable_knowledge, boundary_effect. Each key must contain exactly status and supports. status must be the literal string proven. supports must be a non-empty list of exact StructuralDelta or SourceAssertion support objects copied character-for-character from the current packet. The same exact packet support may witness more than one test when it independently and directly proves each test; no distinct-support count is required.
Fail-closed proof rule: do not mark a test proven merely because another test passed, the mechanism wording sounds contractual, a type label suggests eligibility, or a downstream consequence is plausible. If any one of the five tests lacks an exact in-packet witness that directly establishes that test, return decline instead of interpret. The ledger is a witness binding for the existing tests, not a place to invent new facts or broaden the mechanism.
Uncertainty consistency rule: uncertainty_notes may describe only non-required details. If an uncertainty note would admit that a participant, consumer, authority side, lifecycle phase, changedness fact, handoff, consequential effect, or other witness required by one of the five tests is outside the packet, absent, inferred, not directly shown, or otherwise unresolved, that test is not proven and the decision must be decline. Do not return an interpret decision whose uncertainty contradicts a proven ledger entry.
Output-contract override: despite the earlier generic allowed interpretation shape, decision_proof is required for every decision=interpret under this adapter. The deterministic adapter validates the exact five keys, proven status, semantic-only witness types, and exact packet membership. It removes decision_proof before constructing the downstream ChangeInterpretation proposal while retaining the normalized ledger beside the proposal in the inference artifact for provenance. decision=decline remains exactly {\"decision\":\"decline\"}.
"""

BASE.ADAPTER_VERSION = ADAPTER_VERSION
BASE.SYSTEM_RULES = (
    BASE.SYSTEM_RULES.rstrip()
    + "\n\n"
    + ATTENTION_V18_RULES.strip()
    + "\n\n"
    + DECISION_PROOF_V19_RULES.strip()
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
_BASE_REPAIR_VALIDATOR_CONTRACT = BASE.repair_validator_contract
semantic_support_choices = BASE.semantic_support_choices
allowed_ids = BASE.allowed_ids
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


def _normalize_decision_proof(packet: dict, response: dict) -> dict[str, dict]:
    proof = response.get("decision_proof")
    if not isinstance(proof, dict):
        raise ValueError("decision_proof must be an object for decision=interpret")
    if set(proof) != set(DECISION_PROOF_TESTS):
        raise ValueError(
            "decision_proof must contain exactly the five review-worthiness tests"
        )

    exact_semantic = {
        (item["support_type"], item["support_id"])
        for item in BASE.semantic_support_choices(packet)
    }
    normalized: dict[str, dict] = {}
    for test_name in DECISION_PROOF_TESTS:
        entry = proof[test_name]
        if not isinstance(entry, dict) or set(entry) != {"status", "supports"}:
            raise ValueError(
                f"decision_proof.{test_name} must contain only status and supports"
            )
        if entry.get("status") != "proven":
            raise ValueError(f"decision_proof.{test_name}.status must equal proven")
        supports = entry.get("supports")
        if not isinstance(supports, list) or not supports:
            raise ValueError(
                f"decision_proof.{test_name}.supports must be a non-empty list"
            )
        selected: dict[tuple[str, str], dict[str, str]] = {}
        for support in supports:
            if not isinstance(support, dict) or set(support) != {"support_type", "support_id"}:
                raise ValueError(
                    f"decision_proof.{test_name} support must contain only support_type and support_id"
                )
            support_type = support.get("support_type")
            support_id = support.get("support_id")
            if not isinstance(support_type, str) or not isinstance(support_id, str):
                raise ValueError(
                    f"decision_proof.{test_name} support values must be strings"
                )
            key = (support_type, support_id)
            if key not in exact_semantic:
                raise ValueError(
                    f"decision_proof.{test_name} witness lies outside exact semantic packet support: {support_type}:{support_id}"
                )
            selected[key] = {
                "support_type": support_type,
                "support_id": support_id,
            }
        normalized[test_name] = {
            "status": "proven",
            "supports": [selected[key] for key in sorted(selected)],
        }
    return normalized


def repair_validator_contract() -> dict:
    contract = dict(_BASE_REPAIR_VALIDATOR_CONTRACT())
    contract["interpret_required_fields"] = [
        "decision",
        "interpretation_types",
        "mechanism",
        "summary",
        "decision_proof",
        "supports",
    ]
    contract["interpret_optional_fields"] = ["uncertainty_notes"]
    contract["decision_proof_protocol_version"] = DECISION_PROOF_PROTOCOL_VERSION
    contract["decision_proof_exact_tests"] = list(DECISION_PROOF_TESTS)
    contract["decision_proof_status"] = "proven"
    contract["decision_proof_support_types"] = sorted(BASE.SEMANTIC_SUPPORT_TYPES)
    contract["decision_proof_non_empty_exact_packet_supports"] = True
    return contract


def semantic_reference_fields(value: dict) -> dict | None:
    if not isinstance(value, dict) or value.get("decision") != "interpret":
        return None
    required_semantic_fields = (
        "decision",
        "interpretation_types",
        "mechanism",
        "summary",
        "decision_proof",
    )
    if any(field not in value for field in required_semantic_fields):
        return None
    reference = {field: value[field] for field in required_semantic_fields}
    if "uncertainty_notes" in value:
        reference["uncertainty_notes"] = value["uncertainty_notes"]
    return reference


def _indexed_repair_validator_contract() -> dict:
    contract = repair_validator_contract()
    contract["interpret_required_fields"] = [
        "decision",
        "interpretation_types",
        "mechanism",
        "summary",
        "decision_proof",
        "support_choice_indices",
    ]
    contract["interpret_optional_fields"] = ["uncertainty_notes"]
    contract["support_choice_indices_non_empty_integer_list"] = True
    contract["supports_field_forbidden_in_index_mode"] = True
    return contract


def normalize(packet: dict, response: dict) -> dict:
    if response.get("decision") == "decline":
        return _BASE_NORMALIZE(packet, response)

    decision_proof = _normalize_decision_proof(packet, response)
    translated = dict(response)
    translated.pop("decision_proof", None)

    indexed_mode = "support_choice_indices" in translated
    if indexed_mode:
        packet_key = _packet_key(packet)
        if getattr(_REPAIR_SEQUENCE, "choice_packet_key", None) != packet_key:
            raise ValueError("support_choice_indices are allowed only during semantic-lock repair")
        if "supports" in translated:
            raise ValueError("semantic-lock support-choice repair must not include supports")

        indices = translated.get("support_choice_indices")
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

        translated.pop("support_choice_indices")
        translated["supports"] = selected

    result = _BASE_NORMALIZE(packet, translated)
    if result.get("status") == "interpret":
        result["decision_proof"] = decision_proof
    if indexed_mode:
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
            "decision_proof_protocol_version": DECISION_PROOF_PROTOCOL_VERSION,
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
            + "\nSemantic-lock mode is active: reproduce semantic_reference fields exactly, including decision_proof, and do not re-evaluate, broaden, narrow, or rewrite them."
            + "\nSupport-choice index mode is active only for this bounded repair. Do not output support IDs for the proposal supports field and do not output a proposal supports field. Exact support objects inside the preserved decision_proof must remain unchanged."
            + "\nReturn exactly the semantic_reference fields plus support_choice_indices, where support_choice_indices is a non-empty JSON array of integer choice_index values copied from exact_semantic_support_choices_by_index."
            + "\nChoose only entries that directly support the preserved bounded mechanism. Prefer exactly one choice when one is sufficient. The deterministic adapter will copy the selected exact support objects after parsing the indices."
            + "\nNever derive, regenerate, shorten, complete, or invent a support ID. If no listed semantic choice directly supports the preserved interpretation, return an empty support_choice_indices array so deterministic validation rejects the repair instead of silently reclassifying it."
            + "\nCumulative forbidden support IDs across this bounded repair sequence are listed in forbidden_support_ids; a support ID rejected on an earlier attempt remains forbidden on every later attempt in this sequence. In index mode these IDs are diagnostic only and must never be reproduced in the proposal supports field."
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
        + "\nDecision-proof ledger remains required for decision=interpret and must satisfy the deterministic validator contract above."
        + "\nReturn exactly one complete compact single-line JSON object."
    )


BASE.repair_validator_contract = repair_validator_contract
BASE.semantic_reference_fields = semantic_reference_fields
BASE.normalize = normalize
BASE.repair_prompt = repair_prompt
infer_packet = BASE.infer_packet
infer_packets = BASE.infer_packets
main = BASE.main


if __name__ == "__main__":
    raise SystemExit(main())
