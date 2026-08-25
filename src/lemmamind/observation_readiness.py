"""Deterministic readiness evaluation for hard golden Observation cases.

The evaluator does not infer capability state from prose or repository contents.
It validates a versioned readiness declaration against the frozen golden corpus
and computes each case outcome from explicit capability states.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


class ObservationReadinessError(RuntimeError):
    """The readiness specification is malformed or contradicts the golden corpus."""


_ALLOWED_STATES = {"implemented", "missing", "deferred"}
_ALLOWED_OUTCOMES = {"ready", "blocked", "deferred"}


def load_readiness_spec(path: str | Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ObservationReadinessError("readiness YAML root must be a mapping")
    if payload.get("schema_version") != "lemmamind.observation-readiness.v1":
        raise ObservationReadinessError("unsupported observation readiness schema_version")
    return payload


def evaluate_readiness(
    spec_path: str | Path = "eval/pilot/observation-readiness-v1.yaml",
) -> dict[str, Any]:
    spec = load_readiness_spec(spec_path)
    capabilities = _capabilities(spec)
    cases = spec.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ObservationReadinessError("readiness spec must contain cases")

    results: list[dict[str, Any]] = []
    for item in cases:
        if not isinstance(item, Mapping):
            raise ObservationReadinessError("readiness case entries must be mappings")
        case_id = _required_string(item, "case_id")
        golden_path = Path(_required_string(item, "golden_case"))
        golden = _load_golden(golden_path)
        if golden.get("case_id") != case_id:
            raise ObservationReadinessError(
                f"readiness case_id does not match golden case: {case_id}"
            )
        expected_case_type = _required_string(item, "expected_case_type")
        if golden.get("case_type") != expected_case_type:
            raise ObservationReadinessError(
                f"case_type mismatch for {case_id}: expected {expected_case_type}, "
                f"golden has {golden.get('case_type')}"
            )

        requires = item.get("requires")
        if not isinstance(requires, list) or not requires or not all(
            isinstance(value, str) and value.strip() for value in requires
        ):
            raise ObservationReadinessError(
                f"{case_id} requires must be a non-empty capability list"
            )
        unknown = [name for name in requires if name not in capabilities]
        if unknown:
            raise ObservationReadinessError(
                f"{case_id} references unknown capabilities: {sorted(unknown)}"
            )

        required_states = {name: capabilities[name]["state"] for name in requires}
        outcome = _outcome(required_states.values())
        expected_outcome = _required_string(item, "expected_outcome")
        if expected_outcome not in _ALLOWED_OUTCOMES:
            raise ObservationReadinessError(
                f"invalid expected_outcome for {case_id}: {expected_outcome}"
            )
        if outcome != expected_outcome:
            raise ObservationReadinessError(
                f"computed outcome for {case_id} is {outcome}, expected {expected_outcome}"
            )

        blockers = [
            {
                "capability": name,
                "state": capabilities[name]["state"],
                "reason": capabilities[name]["reason"],
            }
            for name in requires
            if capabilities[name]["state"] != "implemented"
        ]
        belief_revision = golden.get("belief_revision")
        revision_required = (
            bool(belief_revision.get("required"))
            if isinstance(belief_revision, Mapping)
            else False
        )
        sources = golden.get("sources")
        source_count = len(sources) if isinstance(sources, list) else 0
        expected_observations = golden.get("expected_observations")
        observation_count = len(expected_observations) if isinstance(expected_observations, list) else 0

        results.append(
            {
                "case_id": case_id,
                "case_type": expected_case_type,
                "outcome": outcome,
                "required_capabilities": list(requires),
                "blockers": blockers,
                "source_count": source_count,
                "golden_observation_count": observation_count,
                "belief_revision_required": revision_required,
                "boundary": _required_string(item, "boundary"),
            }
        )

    summary = {
        "case_count": len(results),
        "ready": sum(item["outcome"] == "ready" for item in results),
        "blocked": sum(item["outcome"] == "blocked" for item in results),
        "deferred": sum(item["outcome"] == "deferred" for item in results),
    }
    return {
        "schema_version": "lemmamind.observation-readiness-report.v1",
        "readiness_id": _required_string(spec, "readiness_id"),
        "summary": summary,
        "cases": results,
        "interpretation_boundary": (
            "Readiness reports whether the current explicit contracts/capabilities can represent "
            "a frozen golden case without weakening epistemic boundaries. It does not generate "
            "or validate the golden observations themselves."
        ),
    }


def _capabilities(spec: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    raw = spec.get("capabilities")
    if not isinstance(raw, Mapping) or not raw:
        raise ObservationReadinessError("readiness spec must contain capabilities")
    result: dict[str, dict[str, str]] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(value, Mapping):
            raise ObservationReadinessError("capability entries must be named mappings")
        state = _required_string(value, "state")
        if state not in _ALLOWED_STATES:
            raise ObservationReadinessError(f"invalid capability state for {name}: {state}")
        result[name] = {
            "state": state,
            "reason": _required_string(value, "reason"),
        }
    return result


def _outcome(states) -> str:
    values = set(states)
    if "deferred" in values:
        return "deferred"
    if "missing" in values:
        return "blocked"
    return "ready"


def _load_golden(path: Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ObservationReadinessError(f"golden case root must be a mapping: {path}")
    if payload.get("schema_version") != "lemmamind.pilot-case.v1":
        raise ObservationReadinessError(f"unsupported golden case schema: {path}")
    return payload


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ObservationReadinessError(f"{key} must be a non-empty string")
    return value.strip()
