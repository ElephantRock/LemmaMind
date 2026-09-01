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
ADAPTER_VERSION = "zai-glm-5.3.packet-v3"
INVOKE_TIMEOUT_SECONDS = 600
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
Your task is attention reduction, not prose generation. Decline when the packet does not support a specific mechanism-level change.
Do not infer importance, priority, causality, intent, or broad architectural significance merely from churn, filenames, counts, test/docs/config labels, or absence of extracted structure.
Do not restate a diff as the mechanism. A valid mechanism describes what technical behavior, authority boundary, failure mode, state transition, temporal property, or project-state contract changed.
Use a concise canonical mechanism label that could be identical across candidate packets only when they truly describe the same mechanism. Do not put repository names, paths, commit SHAs, generic words such as update/refactor/change, or priority language in the mechanism label.
Every interpreted item must cite at least one StructuralDelta or SourceAssertion ID supplied in the packet. You may additionally cite ArtifactDelta or CandidateExtractionGapSignal IDs from the packet.
If extraction gaps are present, do not treat them as evidence of irrelevance or absence. The adapter will ensure exact gap support and explicit uncertainty are retained.
If the packet is insufficient, return decline. Never invent support IDs or facts.
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


def packet_prompt(packet: dict, *, repair: str | None = None) -> str:
    payload = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    prompt = SYSTEM_RULES + "\nCandidateEvidencePacket:\n" + payload
    if repair:
        prompt += (
            "\n\nYour previous response was rejected by the deterministic adapter for this reason:\n"
            + repair
            + "\nReturn a corrected JSON object only. Do not add new evidence."
        )
    return prompt


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


def parse_json_object(raw: str) -> dict:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("model output must be one JSON object")
    return value


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
    first_raw = invoke(binary, packet_prompt(packet))
    try:
        return normalize(packet, parse_json_object(first_raw))
    except Exception as first_error:
        repair_reason = str(first_error)[:1200]
        second_raw = invoke(binary, packet_prompt(packet, repair=repair_reason))
        try:
            return normalize(packet, parse_json_object(second_raw))
        except Exception as second_error:
            raise RuntimeError(
                "provider output remained invalid after one bounded repair: "
                f"first_error={first_error}; second_error={second_error}; "
                f"first_output={first_raw[:1500]!r}; second_output={second_raw[:1500]!r}"
            ) from second_error


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
