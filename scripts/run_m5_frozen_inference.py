#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCHEMA_VERSION = "m5-frozen-semantic-replay.v1"
ADAPTER_VERSION = "zai-glm-5.3.packet-v12"
INVOKE_TIMEOUT_SECONDS = 600
MAX_TIMEOUT_RETRIES = 1
MAX_SEMANTIC_REPAIRS = 2
MAX_INFERENCE_WORKERS = 2
ALLOWED_TYPES = {
    "introduction",
    "modification",
    "removal",
    "reversal",
    "deprecation",
    "failure",
    "repair",
    "authority_governance",
    "project_state",
    "temporal_correctness",
    "unknown",
}
ALLOWED_SUPPORT_TYPES = {
    "ArtifactDelta",
    "StructuralDelta",
    "SourceAssertion",
    "CandidateExtractionGapSignal",
}
SEMANTIC_SUPPORT_TYPES = {"StructuralDelta", "SourceAssertion"}
SUPPORT_REPAIR_ERROR_PREFIXES = (
    "supports must be a non-empty list",
    "each support must contain only support_type and support_id",
    "unsupported support_type:",
    "support lies outside exact packet:",
    "mechanism interpretation requires StructuralDelta or SourceAssertion support",
    "model cited extraction-gap support absent from the packet",
)

# Product-rule provenance for the generic review-worthiness rubric. These are deliberately
# non-audit sources: roadmap I5 (security/trust isolation), I7 (mechanism-level
# knowledge), I8 (human-attention budget), and the authorized M5 ChangeInterpretation
# slice. The post-inference human-audit target inventory is not used here.
REVIEW_WORTHINESS_PROVENANCE = (
    "roadmap:I5-security-trust-isolation",
    "roadmap:I7-mechanism-level-knowledge",
    "roadmap:I8-human-attention",
    "docs:M5-CHANGE-SIGNAL-NEXT-SLICE",
)

SYSTEM_RULES = """You are a bounded technical change interpreter.
You receive exactly one deterministic CandidateEvidencePacket. Use only evidence contained in that packet.
Your task is attention reduction into durable mechanism-level knowledge, not prose generation. A candidate-level change, runtime behavior change, externally observable change, additive interface change, persistent state change, cross-file change, operation-local admission decision, implementation repair, documentation assertion, or test expectation is not automatically a human review item.
A valid interpretation must pass all five tests below: mechanism, review-span, review-leverage, durable-knowledge, and boundary-effect.
Mechanism test: the packet must directly support a stable technical or project-state contract, boundary, invariant, lifecycle, or externally consumed classification rather than a file-local implementation symptom, renamed surface, one-call implementation detail, ordinary bug-fix description, or evidence-source restatement.
Review-span test: the packet must directly establish at least one generic review-bearing span: (a) a stable principal/authority or security trust-boundary rule across distinct principals, components, or trust domains; this may qualify even when enforced within one request when the trust boundary itself is the stable contract; (b) a durable state, provenance, schema, or ownership lifecycle whose semantics survive or re-enter across a later independent lifecycle state such as restart, recovery, migration, deletion/re-admission, or another independently executed phase; (c) a cross-boundary failure/recovery handoff or multi-step/multi-participant correctness invariant whose violation can leave externally or durably consumed state lost, duplicated, exposed, corrupted, stranded, or terminally misclassified; (d) an externally consumed control, support, compatibility, classification/taxonomy, or operator decision contract whose stable meaning is relied on outside the producing implementation; or (e) an externally consumed operator decision/control or terminal/recovery state/action lifecycle in which the packet directly shows a consumer or operator surface both observes governed state and performs a governed state transition, and the observed state directly governs subsequent eligibility, required action, terminal/recovery status, or another non-local decision outcome. This is not a file-count or path-count test: one file may qualify when it directly evidences such a span, and many files do not qualify merely because they changed together.
Review-leverage test: the packet must directly show that the governing review-bearing contract is itself new or materially changed, or that a changed enforcement mechanism introduces or materially changes a reusable fail-closed, recovery, terminal, migration, re-admission, trust-boundary, or cross-boundary/multi-step correctness rule by which that contract is upheld. Correctness leverage requires directly evidenced impact on externally or durably consumed state across the qualifying span. A repair that merely restores already-declared behavior is not review leverage just because the defect crossed a boundary; it qualifies only when the packet directly establishes the changed enforcement rule as durable governing knowledge future implementations must preserve. A refactor, implementation repair, shared helper, internal ownership transfer, precedence change, cache/keying change, local cleanup, diagnostic improvement, limit adjustment, or source-of-truth move is not review-bearing merely because it is stable, persistent, cross-file, or consumed by multiple components when the governing cross-boundary contract remains the same. This is a product review-leverage test, not an importance score: do not infer priority, significance, intent, architectural breadth, or user impact from churn, filenames, counts, labels, or absence of extracted structure.
Durable-knowledge test: after removing commit-specific verbs, file/function names, transport/storage carriers, and implementation technique, the mechanism must still state reusable governing knowledge that a future reviewer, operator, or implementer must preserve or act on across an independent execution or lifecycle. Qualifying durable knowledge answers at least one stable question: who may exercise authority; what durable state is admitted, preserved, removed, migrated, or re-admitted; what externally consumed support/compatibility/classification or operator decision contract applies; what cross-boundary failure/terminal rule applies; or what multi-step/multi-participant correctness invariant must hold. Decline when the remaining statement is only that a component now uses a different helper, source, cache, route, key, limit, retry, cleanup, ownership arrangement, or implementation technique, or that a defect was fixed under an unchanged governing obligation.
Boundary-effect test: the packet must directly show that the qualifying span changes a consequential contract outcome: who or what may exercise authority across a trust boundary; which durable state may be created, preserved, removed, migrated, recovered, re-admitted, or made visible to a later lifecycle phase; which compatibility, support, or operator control a consumer may rely on; which stable classification or reason distinction a directly evidenced non-local consumer or operator decision surface may rely on; which cross-boundary failure or terminal outcome is delivered; which governed state/action transition an external consumer or operator may observe and perform; or which multi-step or multi-participant correctness invariant preserves coherent externally or durably consumed state across the evidenced span.
Interpret only when all five tests are directly evidenced. Do not manufacture review leverage or durable knowledge by restating an internal implementation detail in contract language.
Facet rule: storage, service, client/UI, adapter, documentation, test, migration, and generated-schema facets of one governing lifecycle are not automatically separate review items. Interpret a facet only when the packet directly changes an independently governing decision, obligation, lifecycle rule, or externally consumed decision/control semantics. If a facet merely implements, exposes, verifies, documents, migrates, or mirrors a governing rule without independently changing that rule, decline it rather than creating a separate mechanism item.
Authority, admission, eligibility, and ownership wording is not enough by itself. Decline a single-operation parameter validation, request-shape check, helper-local capability test, local owner lookup, local routing choice, surface-only endpoint guard, internal dispatch choice, or ordinary permission check when the packet does not establish a stable trust-boundary contract or another review-bearing span above. Do not decline a rule merely because it is request-local when the packet directly evidences a stable principal/authority contract across distinct trust domains. A changed admitted-versus-denied outcome inside one operation is not automatically a review item.
Persistence by itself is not enough. Decline presentation state, cache state, convenience preferences, internal registry contents, local counters, size limits, internal bookkeeping, or a durable value whose meaning does not cross a later lifecycle, migration/re-admission, operator-control, trust, failure, or compatibility boundary.
Multiple components by itself is not enough. Decline a shared helper, common validation routine, internal precedence rule, source-of-truth selection, routing ownership, callback ownership, cache ownership, or local capability dispatch when the packet does not directly establish a qualifying trust, durable-lifecycle, cross-boundary failure/correctness, or externally consumed contract.
Decline additive or representational surface changes that merely add or rename request/response fields, methods, enum members, accepted values, metadata, type projections, output formatting, status labels, themes, command aliases, navigation affordances, or capability flags unless the packet directly establishes both a review-bearing span and qualifying review leverage/durable knowledge/boundary effect.
A UI, CLI, client, documentation page, generated type, test fixture, or adapter is not automatically a projection-only decline. A consumer surface qualifies on the state/action basis only when the packet directly shows both observation of governed state and an action that performs the governed transition on the same operator decision/control or terminal/recovery lifecycle, the observed state directly governs subsequent eligibility, required action, terminal/recovery status, or another non-local decision outcome, and the surface change itself materially changes those decision/control semantics rather than merely exposing an already-established transition. Do not require that consumer packet to restate the persistence implementation when that governed relationship is directly evidenced. A read-only mirror, write-only wrapper, ordinary CRUD/editor surface, formatting surface, documentation mirror, or verification-only surface does not qualify on that basis alone.
Documentation, plans, examples, tests, fixtures, and harnesses are evidence surfaces, not automatic declines and not automatic mechanisms. They may establish a review item without implementation files when their content directly evidences all five tests, including either an authoritative changed project-state contract or a behavioral contract assertion that directly proves the governing rule and changed boundary effect. Decline them only when they merely mirror, restate, exercise, or verify an otherwise unchanged rule without directly evidencing independent review leverage and durable knowledge. Do not require runtime implementation bytes solely because the evidence surface is a test or document.
Decline local failure-handling details such as error wording, status presentation, exit-code mapping, instrumentation, tuning, local fallback selection, shutdown logging, or diagnostics when the packet does not directly show a changed cross-boundary failure/recovery handoff, durable terminal state, or multi-step/multi-participant correctness contract affecting externally or durably consumed state.
Decline schema/version bookkeeping, generated alignment guards, QA accounting, build metadata, migration scaffolding, local schema reshaping, or implementation-only compatibility tests unless the packet directly establishes changed migration, downgrade, re-admission, externally consumed compatibility, or durable-state semantics that a consumer or operator must rely on across a lifecycle boundary.
For classifications, taxonomies, and reason vocabularies, mere logging, serialization, persistence, display, or enumeration is insufficient. They may qualify even when downstream action mapping is unchanged only when the packet directly shows a non-local consumer or operator decision surface depends on stable named distinctions as a contract.
Treat tests, fixtures, harnesses, documentation, examples, configuration, workflows, localization or copy, styling/layout/visual polish, generated metadata, barrel/export/module organization, and type-only API cleanup as weak priors about review-worthiness, never as hard suppression categories. Evidence on one of those surfaces remains eligible when its content directly establishes all five tests above.
Decline when such evidence merely verifies, documents, exercises, renames, restyles, reorganizes, localizes, tunes, covers, or projects existing behavior without directly changing a review-bearing contract and its boundary effect. A documentation, test, configuration, or workflow change that itself changes declared support, compatibility, authority, migration/re-admission, operator control, release behavior, externally consumed classification, or another qualifying project-state contract remains eligible when all five tests are directly evidenced.
Do not restate a diff as the mechanism. A valid mechanism describes the stable governing contract that changed, not the file, helper, test, UI surface, endpoint, schema field, capability flag, implementation symptom, or repair technique that exposed it. If the best supported label is substantially a method/field/config/status/theme/command/capability name plus a generic word such as contract or support, decline unless the packet directly supports the higher-level lifecycle, trust boundary, externally consumed obligation, or cross-boundary invariant that name participates in.
Canonicalize aggressively to the governing rule so independently evidenced facets converge. Use a short subject + contract-kind label and omit actor-role adjectives, transport/storage carriers, evidence source, triggering subtype, phase, enforcement technique, failure symptom, and surface names unless one is essential to distinguish an independent contract. Prefer these generic normal forms when supported: '<subject> <operation> admission contract' for authority/admission rules; '<subject> <transition> lifecycle' for durable/operator state transitions; '<subject> classification contract' for externally consumed taxonomy; '<subject> recovery contract' for cross-boundary failure/terminal semantics; and '<subject> correctness invariant' for multi-step/multi-participant temporal rules. When storage, service, UI, documentation, and test facets describe the same governing rule, use the same rule-level wording rather than facet-specific wording. If the packet contains only a projection without enough evidence for the governing lifecycle, decline rather than inventing it. Never merge independent contracts or broaden beyond the evidence. Do not put repository names, paths, commit SHAs, test names, generic words such as update/refactor/change, or priority language in the mechanism label.
If a packet contains several unrelated changes, interpret only the single central qualifying contract that is directly supported; do not bundle independent minor mechanisms to manufacture a broader review item. If no single qualifying contract passes all five tests, decline.
Choose a canonical interpretation type. Use exactly one type whenever any specific type is sufficient. Never combine introduction or modification with a more specific type; when authority_governance, failure, temporal_correctness, project_state, removal, deprecation, reversal, or repair describes the governing contract, omit generic introduction/modification. Use authority_governance only when principal/authority/trust-boundary semantics are central; use project_state for authoritative declared support/config/schema/project-state contracts; use failure for cross-boundary recovery or terminal disposition; use temporal_correctness only when a multi-step or multi-participant correctness invariant itself is central. Use repair only when the durable governing rule is specifically a restoration/recovery rule not better described by another specific type. Do not add temporal_correctness merely because an implementation uses synchronization, timeout, deadline, retry, uniqueness, or ordering details.
Every interpreted item must cite at least one StructuralDelta or SourceAssertion ID supplied in the packet. Use the smallest sufficient support set. Prefer one exact semantic support when one support is sufficient. You may additionally cite ArtifactDelta or CandidateExtractionGapSignal IDs from the packet.
Before returning interpret, verify every support_id character-for-character against the matching packet field: structural_delta_previews[].structural_delta_id, assertion_previews[].assertion_id, artifact_delta_ids, or extraction_gap_signal_ids. Never derive a support ID from hashes or IDs mentioned inside preview prose.
Semantic review-worthiness and support-format validity are separate. Decline only when the packet evidence does not support a qualifying contract. If the semantic decision is interpret but you cannot reproduce an exact required semantic support ID, do not convert that support-copy failure into decline and do not guess an ID; preserve decision=interpret and return an empty supports array so the deterministic adapter rejects the output and invokes bounded repair.
Mechanism must contain 1..240 characters. Summary must contain 1..1600 characters. Each uncertainty note must contain at most 800 characters.
If extraction gaps are present, do not treat them as evidence of irrelevance or absence. The adapter will ensure exact gap support and explicit uncertainty are retained.
If the packet is semantically insufficient or does not pass all five tests above, return decline. Never invent support IDs or facts.
Return one JSON object only, with no markdown and no commentary.

Allowed decline shape:
{"decision":"decline"}

Allowed interpretation shape:
{
  "decision":"interpret",
  "interpretation_types":["one or more allowed type strings"],
  "mechanism":"concise mechanism label",
  "summary":"bounded evidence-grounded mechanism explanation",
  "uncertainty_notes":["optional bounded uncertainty"],
  "supports":[{"support_type":"StructuralDelta|SourceAssertion|ArtifactDelta|CandidateExtractionGapSignal","support_id":"exact packet ID"}]
}

Allowed interpretation types, sorted alphabetically when multiple:
authority_governance, deprecation, failure, introduction, modification, project_state, removal, repair, reversal, temporal_correctness, unknown.
Use unknown alone, never combined with another type.
"""


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def packet_prompt(packet: dict) -> str:
    payload = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return SYSTEM_RULES + "\nCandidateEvidencePacket:\n" + payload


def allowed_ids(packet: dict) -> dict[str, set[str]]:
    return {
        "ArtifactDelta": set(packet.get("artifact_delta_ids", [])),
        "StructuralDelta": {
            item["structural_delta_id"] for item in packet.get("structural_delta_previews", [])
        },
        "SourceAssertion": {
            item["assertion_id"] for item in packet.get("assertion_previews", [])
        },
        "CandidateExtractionGapSignal": set(packet.get("extraction_gap_signal_ids", [])),
    }


def semantic_support_choices(packet: dict) -> list[dict[str, str]]:
    ids = allowed_ids(packet)
    return [
        {"support_type": support_type, "support_id": support_id}
        for support_type in sorted(SEMANTIC_SUPPORT_TYPES)
        for support_id in sorted(ids[support_type])
    ]


def repair_validator_contract() -> dict:
    return {
        "json_object_only": True,
        "decline_exact_fields": ["decision"],
        "interpret_required_fields": [
            "decision",
            "interpretation_types",
            "mechanism",
            "summary",
            "supports",
        ],
        "interpret_optional_fields": ["uncertainty_notes"],
        "mechanism_max_characters": 240,
        "summary_max_characters": 1600,
        "uncertainty_note_max_characters": 800,
        "allowed_interpretation_types": sorted(ALLOWED_TYPES),
        "unknown_must_be_alone": True,
        "generic_types_cannot_mix_with_specific": True,
        "semantic_support_required_from": sorted(SEMANTIC_SUPPORT_TYPES),
    }


def forbidden_support_ids(previous_output: str, support_allowlist: dict[str, list[str]]) -> dict[str, list[str]]:
    forbidden: dict[str, set[str]] = {support_type: set() for support_type in ALLOWED_SUPPORT_TYPES}
    try:
        value = json.loads(previous_output)
    except Exception:
        value = None
    if isinstance(value, dict):
        supports = value.get("supports", [])
        if isinstance(supports, list):
            for item in supports:
                if not isinstance(item, dict):
                    continue
                support_type = item.get("support_type")
                support_id = item.get("support_id")
                if (
                    support_type in forbidden
                    and isinstance(support_id, str)
                    and support_id not in support_allowlist[support_type]
                ):
                    forbidden[support_type].add(support_id)
    return {
        support_type: sorted(values)
        for support_type, values in sorted(forbidden.items())
        if values
    }


def semantic_reference_fields(value: dict) -> dict | None:
    if not isinstance(value, dict) or value.get("decision") != "interpret":
        return None
    required_semantic_fields = ("decision", "interpretation_types", "mechanism", "summary")
    if any(field not in value for field in required_semantic_fields):
        return None
    reference = {field: value[field] for field in required_semantic_fields}
    if "uncertainty_notes" in value:
        reference["uncertainty_notes"] = value["uncertainty_notes"]
    return reference


def support_repair_reference(previous_output: str, error: Exception) -> dict | None:
    if not str(error).startswith(SUPPORT_REPAIR_ERROR_PREFIXES):
        return None
    try:
        value = json.loads(previous_output)
    except Exception:
        return None
    return semantic_reference_fields(value)


def repair_prompt(
    packet: dict,
    *,
    previous_output: str,
    error: Exception,
    repair_attempt: int = 1,
    semantic_reference: dict | None = None,
) -> str:
    if repair_attempt < 1 or repair_attempt > MAX_SEMANTIC_REPAIRS:
        raise ValueError(
            f"repair_attempt must be between 1 and {MAX_SEMANTIC_REPAIRS}"
        )
    support_allowlist = {
        support_type: sorted(values)
        for support_type, values in sorted(allowed_ids(packet).items())
    }
    exact_semantic_support_choices = semantic_support_choices(packet)
    repair_context = {
        "adapter_error": str(error),
        "exact_semantic_support_choices": exact_semantic_support_choices,
        "exact_support_allowlist": support_allowlist,
        "forbidden_support_ids": forbidden_support_ids(previous_output, support_allowlist),
        "repair_attempt": repair_attempt,
        "validator_contract": repair_validator_contract(),
    }
    if semantic_reference is None:
        repair_context["previous_output"] = previous_output
        repair_mode_rules = (
            "Repair the previous output only. Treat previous_output as rejected data, not as a source of valid support IDs. "
        )
    else:
        repair_context["semantic_reference"] = semantic_reference
        repair_mode_rules = (
            "This is support-copy/JSON-serialization repair for a semantic interpretation whose non-support fields already passed deterministic validation. "
            "Preserve decision, interpretation_types, mechanism, summary, and uncertainty_notes exactly from semantic_reference; do not re-evaluate, broaden, narrow, or rewrite them. "
            "The rejected raw output is intentionally omitted so invalid IDs or malformed JSON cannot become repair source material. Rebuild supports only from the exact choices supplied below. "
        )
    return (
        packet_prompt(packet)
        + "\n\nDeterministic adapter repair context:\n"
        + json.dumps(repair_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
        + repair_mode_rules
        + "Every support_id must be copied exactly from the exact_support_allowlist for its matching support_type, character-for-character. "
        + "Any value listed in forbidden_support_ids is invalid and must not appear in supports. Never guess, synthesize, shorten, or rewrite an ID. "
        + "For decision=interpret, the first supports entry must be copied as a literal support_type/support_id object from exact_semantic_support_choices. Prefer exactly one semantic support when one support is sufficient; add more only by copying exact objects from the allowlist. "
        + "Do not use a StructuralDelta or SourceAssertion support that is absent from exact_semantic_support_choices. The selected semantic support must directly support the preserved bounded mechanism; do not choose an unrelated allowed ID merely to satisfy validation. "
        + "Satisfy validator_contract exactly, including field and character limits, and emit valid JSON syntax. "
        + "Do not add evidence or broaden the mechanism. Decline only if the packet evidence is semantically insufficient for the same bounded interpretation; do not change an otherwise supported interpret decision to decline solely because a rejected output had an invalid or missing support ID. "
        + "If the same bounded interpretation remains supported, preserve decision=interpret and copy exact support IDs from the supplied choices. If you still cannot produce a valid exact semantic support after using those choices, keep decision=interpret and return an empty supports array so the adapter rejects the repair instead of silently reclassifying it as decline. "
        + "Return one corrected JSON object only."
    )


def invoke(binary: str, prompt: str) -> str:
    env = os.environ.copy()
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    env.pop("COPILOT_GITHUB_TOKEN", None)
    runner_temp = env.get("RUNNER_TEMP") or None
    with tempfile.TemporaryDirectory(
        prefix="lemmamind-frozen-inference-",
        dir=runner_temp,
    ) as directory:
        completed = subprocess.run(
            [
                binary,
                "-s",
                "--no-ask-user",
                "--deny-tool=read,write,shell,url,memory",
            ],
            input=prompt,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=directory,
            timeout=INVOKE_TIMEOUT_SECONDS,
        )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        raise RuntimeError(
            f"Copilot CLI exited {completed.returncode}; stderr={stderr[:2000]!r}; stdout={stdout[:2000]!r}"
        )
    return completed.stdout.strip()


def invoke_with_timeout_retry(binary: str, prompt: str) -> str:
    timeout_errors: list[subprocess.TimeoutExpired] = []
    for attempt in range(MAX_TIMEOUT_RETRIES + 1):
        try:
            return invoke(binary, prompt)
        except subprocess.TimeoutExpired as exc:
            timeout_errors.append(exc)
            if attempt >= MAX_TIMEOUT_RETRIES:
                break
    raise RuntimeError(
        f"provider invocation timed out {len(timeout_errors)} times at {INVOKE_TIMEOUT_SECONDS}s each"
    ) from timeout_errors[-1]


def parse_json_object(raw: str) -> dict:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("model output must be one JSON object")
    return value


def normalize(packet: dict, response: dict) -> dict:
    decision = response.get("decision")
    if decision == "decline":
        if set(response) != {"decision"}:
            raise ValueError("decline response may contain only the decision field")
        return {"status": "decline"}
    if decision != "interpret":
        raise ValueError("decision must be decline or interpret")

    required = {"decision", "interpretation_types", "mechanism", "summary", "supports"}
    allowed_fields = required | {"uncertainty_notes"}
    missing = required - set(response)
    extra = set(response) - allowed_fields
    if missing:
        raise ValueError(f"interpret response missing fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"interpret response has unexpected fields: {sorted(extra)}")

    types = response["interpretation_types"]
    if not isinstance(types, list) or not types or any(not isinstance(item, str) for item in types):
        raise ValueError("interpretation_types must be a non-empty string list")
    types = sorted(set(types))
    if not set(types).issubset(ALLOWED_TYPES):
        raise ValueError("interpretation_types contains an unknown type")
    if "unknown" in types and len(types) != 1:
        raise ValueError("unknown cannot be combined with another interpretation type")
    generic_types = {"introduction", "modification"}
    if len(types) > 1 and set(types) & generic_types and not set(types).issubset(generic_types):
        raise ValueError(
            "introduction or modification cannot be combined with a more specific interpretation type"
        )

    mechanism = response["mechanism"]
    summary = response["summary"]
    if not isinstance(mechanism, str) or not mechanism.strip() or len(mechanism.strip()) > 240:
        raise ValueError("mechanism must contain 1..240 characters")
    if not isinstance(summary, str) or not summary.strip() or len(summary.strip()) > 1600:
        raise ValueError("summary must contain 1..1600 characters")

    uncertainty = response.get("uncertainty_notes", [])
    if not isinstance(uncertainty, list) or any(not isinstance(item, str) for item in uncertainty):
        raise ValueError("uncertainty_notes must be a string list")
    uncertainty = [item.strip() for item in uncertainty if item.strip()]
    if any(len(item) > 800 for item in uncertainty):
        raise ValueError("uncertainty note exceeds 800 characters")

    supports = response["supports"]
    if not isinstance(supports, list) or not supports:
        raise ValueError("supports must be a non-empty list")
    ids = allowed_ids(packet)
    normalized_supports: dict[tuple[str, str], dict] = {}
    for item in supports:
        if not isinstance(item, dict) or set(item) != {"support_type", "support_id"}:
            raise ValueError("each support must contain only support_type and support_id")
        support_type = item["support_type"]
        support_id = item["support_id"]
        if support_type not in ALLOWED_SUPPORT_TYPES:
            raise ValueError(f"unsupported support_type: {support_type!r}")
        if not isinstance(support_id, str) or support_id not in ids[support_type]:
            raise ValueError(f"support lies outside exact packet: {support_type}:{support_id}")
        normalized_supports[(support_type, support_id)] = {
            "support_type": support_type,
            "support_id": support_id,
        }

    if not any(key[0] in SEMANTIC_SUPPORT_TYPES for key in normalized_supports):
        raise ValueError("mechanism interpretation requires StructuralDelta or SourceAssertion support")

    gap_ids = sorted(ids["CandidateExtractionGapSignal"])
    if gap_ids:
        for support_id in gap_ids:
            normalized_supports[("CandidateExtractionGapSignal", support_id)] = {
                "support_type": "CandidateExtractionGapSignal",
                "support_id": support_id,
            }
        uncertainty.append(
            "Deterministic extraction coverage is incomplete for one or more paths in this candidate; the mechanism statement is limited to the cited extracted evidence."
        )
    elif any(key[0] == "CandidateExtractionGapSignal" for key in normalized_supports):
        raise ValueError("model cited extraction-gap support absent from the packet")

    proposal = {
        "interpretation_types": types,
        "mechanism": mechanism.strip(),
        "summary": summary.strip(),
        "uncertainty_notes": sorted(set(uncertainty)),
        "supports": [normalized_supports[key] for key in sorted(normalized_supports)],
    }
    return {"status": "interpret", "proposal": proposal}


def infer_packet(binary: str, packet: dict) -> dict:
    raw = invoke_with_timeout_retry(binary, packet_prompt(packet))
    rejected_outputs: list[str] = []
    errors: list[Exception] = []
    semantic_reference: dict | None = None

    for repair_count in range(MAX_SEMANTIC_REPAIRS + 1):
        try:
            response = parse_json_object(raw)
            if semantic_reference is not None:
                repaired_reference = semantic_reference_fields(response)
                if repaired_reference != semantic_reference:
                    raise ValueError("support repair changed preserved semantic fields")
            return normalize(packet, response)
        except Exception as error:
            rejected_outputs.append(raw)
            errors.append(error)
            if semantic_reference is None:
                semantic_reference = support_repair_reference(raw, error)
            if repair_count >= MAX_SEMANTIC_REPAIRS:
                break
            raw = invoke_with_timeout_retry(
                binary,
                repair_prompt(
                    packet,
                    previous_output=raw,
                    error=error,
                    repair_attempt=repair_count + 1,
                    semantic_reference=semantic_reference,
                ),
            )

    error_summary = "; ".join(
        f"attempt_{index}_error={error}"
        for index, error in enumerate(errors, start=1)
    )
    output_summary = "; ".join(
        f"attempt_{index}_output={output[:1500]!r}"
        for index, output in enumerate(rejected_outputs, start=1)
    )
    raise RuntimeError(
        f"provider output remained invalid after {MAX_SEMANTIC_REPAIRS} bounded repairs: "
        f"{error_summary}; {output_summary}"
    ) from errors[-1]


def infer_packets(
    binary: str,
    packets: list[dict],
    *,
    repo_key: str,
    workers: int,
) -> dict:
    if workers < 1 or workers > MAX_INFERENCE_WORKERS:
        raise ValueError(
            f"workers must be between 1 and {MAX_INFERENCE_WORKERS}"
        )

    entries: list[tuple[int, str, dict]] = []
    packet_ids: set[str] = set()
    for index, packet in enumerate(packets, start=1):
        packet_id = packet.get("candidate_evidence_packet_id")
        if not isinstance(packet_id, str) or not packet_id:
            raise RuntimeError("serialized packet is missing candidate_evidence_packet_id")
        if packet_id in packet_ids:
            raise RuntimeError(f"serialized packet ID is duplicated: {packet_id}")
        packet_ids.add(packet_id)
        entries.append((index, packet_id, packet))

    def run_entry(entry: tuple[int, str, dict]):
        index, packet_id, packet = entry
        print(
            f"M5_INFERENCE_PACKET_START {repo_key} {index}/{len(packets)} {packet_id}",
            flush=True,
        )
        try:
            result = infer_packet(binary, packet)
            print(
                f"M5_INFERENCE_PACKET_DONE {repo_key} {index}/{len(packets)} {result['status']}",
                flush=True,
            )
            return index, packet_id, result, None
        except Exception as exc:
            print(
                f"M5_INFERENCE_PACKET_ERROR {repo_key} {index}/{len(packets)}",
                flush=True,
            )
            return index, packet_id, None, str(exc)[:5000]

    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix=f"m5-{repo_key}",
    ) as executor:
        records = list(executor.map(run_entry, entries))

    results: dict[str, dict] = {}
    errors: list[dict] = []
    interpreted_count = 0
    declined_count = 0
    for _index, packet_id, result, error in records:
        if error is not None:
            errors.append({
                "candidate_evidence_packet_id": packet_id,
                "error": error,
            })
            continue
        if result is None:
            raise RuntimeError("inference worker returned neither result nor error")
        results[packet_id] = result
        if result["status"] == "interpret":
            interpreted_count += 1
        elif result["status"] == "decline":
            declined_count += 1
        else:
            raise RuntimeError(f"unexpected normalized inference status: {result['status']!r}")

    if len(results) + len(errors) != len(packets):
        raise RuntimeError("inference output does not cover every exact input packet")

    return {
        "packet_count": len(packets),
        "worker_count": workers,
        "invoke_timeout_seconds": INVOKE_TIMEOUT_SECONDS,
        "timeout_retry_limit": MAX_TIMEOUT_RETRIES,
        "semantic_repair_limit": MAX_SEMANTIC_REPAIRS,
        "interpreted_count": interpreted_count,
        "declined_count": declined_count,
        "error_count": len(errors),
        "errors": errors,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-key", choices=("openbot", "openclaw", "hermes"), required=True)
    parser.add_argument("--packets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    binary = os.environ.get("M5_COPILOT_BINARY", "").strip()
    api_key = os.environ.get("COPILOT_PROVIDER_API_KEY", "").strip()
    provider_type = os.environ.get("COPILOT_PROVIDER_TYPE", "").strip()
    provider_base_url = os.environ.get("COPILOT_PROVIDER_BASE_URL", "").strip()
    model = os.environ.get("COPILOT_MODEL", "").strip()
    if not binary or not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        raise RuntimeError("M5_COPILOT_BINARY must name the verified executable")
    if not api_key:
        raise RuntimeError("COPILOT_PROVIDER_API_KEY is required")
    if provider_type != "openai":
        raise RuntimeError("frozen Z.ai replay requires COPILOT_PROVIDER_TYPE=openai")
    if provider_base_url != "https://api.z.ai/api/coding/paas/v4":
        raise RuntimeError("frozen Z.ai replay base URL changed")
    if model != "GLM-5.3":
        raise RuntimeError("frozen Z.ai replay model changed")
    if os.environ.get("COPILOT_OFFLINE", "").lower() != "true":
        raise RuntimeError("COPILOT_OFFLINE=true is required")

    packets = read_json(args.packets)
    if not isinstance(packets, list) or not packets:
        raise RuntimeError("packets artifact must contain a non-empty JSON list")

    inference = infer_packets(
        binary,
        packets,
        repo_key=args.repo_key,
        workers=args.workers,
    )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "repo_key": args.repo_key,
        "provider_type": provider_type,
        "provider_base_url": provider_base_url,
        "model": model,
        "adapter_version": ADAPTER_VERSION,
        **inference,
    }
    write_json(args.output, artifact)
    print(
        "M5_FROZEN_INFERENCE="
        + json.dumps(
            {key: value for key, value in artifact.items() if key not in {"results", "errors"}},
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())