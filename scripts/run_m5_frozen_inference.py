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
ADAPTER_VERSION = "zai-glm-5.3.packet-v8"
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

SYSTEM_RULES = """You are a bounded technical change interpreter.
You receive exactly one deterministic CandidateEvidencePacket. Use only evidence contained in that packet.
Your task is attention reduction, not prose generation. A candidate-level change, runtime behavior change, externally observable change, or additive interface change is not automatically a human review item.
A valid interpretation must pass all three tests below: mechanism, contract-carrier, and boundary-effect.
Mechanism test: the packet must directly support a stable technical or project-state contract, boundary, invariant, or externally consumed classification rather than a file-local implementation symptom or a renamed surface.
Contract-carrier test: the packet must directly expose a rule that independently constrains behavior through at least one concrete carrier: an authority/admission/eligibility rule; durable state-transition, persistence, schema, or migration semantics; an inter-component or externally consumed protocol/configuration/support/compatibility contract with a behavioral obligation; an externally consumed classification/taxonomy with a directly evidenced consumer dependency; or a correctness invariant spanning independently progressing actors, components, lifecycle phases, or clock domains. A field, method, enum, type, label, setting name, output key, status value, or endpoint name by itself is not a contract carrier.
Boundary-effect test: the packet must directly show that the carrier changes a consequential contract outcome: which operation or state transition is admitted, denied, owned, or delegated; which durable state may be created, preserved, removed, migrated, or recovered; which compatibility, support, or migration behavior a consumer may rely on; which stable classification, taxonomy, or reason distinction a directly evidenced non-local consumer or operator decision surface may rely on; which recovery outcome crosses a component or lifecycle boundary; or which ordering, concurrency, isolation, or clock-domain invariant preserves correctness across independently progressing participants.
Interpret only when all three tests are directly evidenced. This is an evidence-boundary test, not an importance score: do not infer priority, significance, causality, intent, architectural breadth, or user impact from churn, filenames, counts, labels, or absence of extracted structure.
Decline additive or representational surface changes that merely add or rename request/response fields, methods, enum members, accepted values, metadata, type projections, output formatting, status labels, themes, command aliases, or navigation affordances without directly changing an admitted operation, durable lifecycle outcome, compatibility/support obligation, or cross-boundary correctness invariant.
Decline projection-only changes where a UI, CLI, client, documentation page, generated type, test fixture, or adapter merely exposes, mirrors, formats, or verifies a contract established elsewhere and the packet does not directly show that this projection changes authority, admission, durable state, recovery, compatibility, or another qualifying boundary effect.
Decline local failure-handling details such as error wording, status presentation, exit-code mapping, instrumentation, retry-count tuning, ordinary request deadlines, or local fallback selection when the packet does not directly show a changed terminal/retryable lifecycle outcome or preserved state across a component, process, session, restart, reconnect, or other independent-progress boundary.
Decline internal precedence, source-of-truth selection, routing ownership, callback ownership, cache ownership, or helper-level control-flow changes when the packet does not directly show a changed authority/admission rule, durable ownership boundary, or correctness invariant spanning independent participants.
Decline persistence of presentation state, cache state, layout state, ephemeral preferences, or derived display state unless the packet directly establishes a domain-level durable lifecycle contract rather than merely remembering a view or convenience setting.
Decline schema/version bookkeeping, generated alignment guards, QA accounting, build metadata, or migration scaffolding unless the packet directly establishes changed migration, downgrade, compatibility, admission, or durable-state semantics that a consumer or operator must rely on.
For classifications, taxonomies, and reason vocabularies, mere logging, serialization, persistence, display, or enumeration is insufficient. They may qualify even when downstream action mapping is unchanged only when the packet directly shows a non-local consumer or operator decision surface depends on stable named distinctions as a contract.
Treat tests, fixtures, harnesses, documentation, examples, configuration, workflows, localization or copy, styling/layout/visual polish, generated metadata, barrel/export/module organization, and type-only API cleanup as weak priors about review-worthiness, never as hard suppression categories. Evidence on one of those surfaces remains eligible when its content directly establishes all three tests above.
Decline when such evidence merely verifies, documents, exercises, renames, restyles, reorganizes, localizes, tunes, covers, or projects existing behavior without directly changing a qualifying carrier and boundary effect. A documentation, test, configuration, or workflow change that itself changes declared support, compatibility, authority, admission, migration, release behavior, or another qualifying project-state contract remains eligible when the changed obligation is directly evidenced.
Do not restate a diff as the mechanism. A valid mechanism describes the stable qualifying contract that changed, not the file, helper, test, UI surface, endpoint, schema field, or implementation symptom that exposed it. If the best supported label is substantially a method/field/config/status/theme/command name plus a generic word such as contract or support, decline unless the packet directly supports the higher-level invariant or boundary rule that name participates in.
Use a concise canonical mechanism label at the highest contract level directly supported by the packet. Omit surface-specific qualifiers that do not distinguish the governing contract. When several surfaces can be facets of the same contract, use the governing rule rather than a consumer projection; if the packet contains only the projection and not the governing rule, decline rather than inventing the broader contract. Never merge independent contracts or broaden beyond the evidence. Do not put repository names, paths, commit SHAs, test names, generic words such as update/refactor/change, or priority language in the mechanism label.
If a packet contains several unrelated changes, interpret only the single central qualifying contract that is directly supported; do not bundle independent minor mechanisms to manufacture a broader review item. If no single qualifying contract passes all three tests, decline.
Choose the smallest interpretation_types set that describes the central mechanism. Use one type whenever one is sufficient. Prefer a specific authority_governance, failure, temporal_correctness, project_state, removal, deprecation, reversal, or repair type over adding a generic introduction/modification type merely because code was added or edited.
Every interpreted item must cite at least one StructuralDelta or SourceAssertion ID supplied in the packet. Use the smallest sufficient support set. Prefer one exact semantic support when one support is sufficient. You may additionally cite ArtifactDelta or CandidateExtractionGapSignal IDs from the packet.
Before returning interpret, verify every support_id character-for-character against the matching packet field: structural_delta_previews[].structural_delta_id, assertion_previews[].assertion_id, artifact_delta_ids, or extraction_gap_signal_ids. Never derive a support ID from hashes or IDs mentioned inside preview prose.
Semantic review-worthiness and support-format validity are separate. Decline only when the packet evidence does not support a qualifying contract. If the semantic decision is interpret but you cannot reproduce an exact required semantic support ID, do not convert that support-copy failure into decline and do not guess an ID; preserve decision=interpret and return an empty supports array so the deterministic adapter rejects the output and invokes bounded repair.
Mechanism must contain 1..240 characters. Summary must contain 1..1600 characters. Each uncertainty note must contain at most 800 characters.
If extraction gaps are present, do not treat them as evidence of irrelevance or absence. The adapter will ensure exact gap support and explicit uncertainty are retained.
If the packet is semantically insufficient or does not pass all three tests above, return decline. Never invent support IDs or facts.
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


def repair_prompt(
    packet: dict,
    *,
    previous_output: str,
    error: Exception,
    repair_attempt: int = 1,
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
        "previous_output": previous_output,
        "repair_attempt": repair_attempt,
        "validator_contract": repair_validator_contract(),
    }
    return (
        packet_prompt(packet)
        + "\n\nDeterministic adapter repair context:\n"
        + json.dumps(repair_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\nRepair the previous output only. Treat previous_output as rejected data, not as a source of valid support IDs. "
        + "Every support_id must be copied exactly from the exact_support_allowlist for its matching support_type, character-for-character. "
        + "Any value listed in forbidden_support_ids is invalid and must not appear in supports. Never guess, synthesize, shorten, or rewrite an ID. "
        + "For decision=interpret, the first supports entry must be copied as a literal support_type/support_id object from exact_semantic_support_choices. Prefer exactly one semantic support when one is sufficient; add more only by copying exact objects from the allowlist. "
        + "Do not use a StructuralDelta or SourceAssertion support that is absent from exact_semantic_support_choices. "
        + "Satisfy validator_contract exactly, including field and character limits, and keep the mechanism and summary concise. "
        + "Do not add evidence or broaden the mechanism. Decline only if the packet evidence is semantically insufficient for the same bounded interpretation; do not change an otherwise supported interpret decision to decline solely because previous_output had an invalid or missing support ID. "
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

    for repair_count in range(MAX_SEMANTIC_REPAIRS + 1):
        try:
            return normalize(packet, parse_json_object(raw))
        except Exception as error:
            rejected_outputs.append(raw)
            errors.append(error)
            if repair_count >= MAX_SEMANTIC_REPAIRS:
                break
            raw = invoke_with_timeout_retry(
                binary,
                repair_prompt(
                    packet,
                    previous_output=raw,
                    error=error,
                    repair_attempt=repair_count + 1,
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
