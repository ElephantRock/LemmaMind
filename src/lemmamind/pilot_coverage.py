"""Live deterministic-evidence coverage evaluation for pinned pilot cases.

Coverage answers a narrow question: did the current capture + deterministic
extraction spine recover source-addressed material matching an explicit golden
evidence check? It does not generate Observations and it does not treat recovery
as proof that a golden interpretation follows automatically.
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .contracts import SourceAssertion, SourceRole
from .extraction import DeterministicExtractionService, ExtractionResult
from .github import GitHubCaptureService, GitHubRESTReader
from .objects import ContentAddressedFileStore
from .storage import SQLiteContractStore

COVERAGE_SCHEMA_VERSION = "lemmamind.pilot-coverage.v1"
REPORT_SCHEMA_VERSION = "lemmamind.pilot-coverage-report.v1"


class CoverageSpecError(ValueError):
    """Coverage specification is malformed or unsupported."""


@dataclass(frozen=True)
class RequirementResult:
    evidence_id: str
    evidence_type: str
    status: str
    check_kind: str
    matched_locators: tuple[str, ...] = ()
    missing_fragments: tuple[str, ...] = ()
    needed_capability: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "status": self.status,
            "check_kind": self.check_kind,
            "matched_locators": list(self.matched_locators),
            "missing_fragments": list(self.missing_fragments),
        }
        if self.needed_capability is not None:
            payload["needed_capability"] = self.needed_capability
        return payload


def load_coverage_spec(path: str | Path) -> Mapping[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, Mapping):
        raise CoverageSpecError("coverage spec root must be a mapping")
    if document.get("schema_version") != COVERAGE_SCHEMA_VERSION:
        raise CoverageSpecError(
            f"unsupported coverage schema: {document.get('schema_version')!r}"
        )
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CoverageSpecError("coverage spec must contain at least one case")
    return document


def assess_requirements(
    requirements: list[Mapping[str, Any]], extraction: ExtractionResult
) -> list[RequirementResult]:
    """Assess explicit requirements against deterministic extraction outputs."""

    results: list[RequirementResult] = []
    assertions = extraction.assertions
    for requirement in requirements:
        evidence_id = _required_string(requirement, "evidence_id")
        evidence_type = _required_string(requirement, "evidence_type")
        check = requirement.get("check")
        if not isinstance(check, Mapping):
            raise CoverageSpecError(f"{evidence_id}: check must be a mapping")
        kind = _required_string(check, "kind")
        needed = requirement.get("needed_capability_if_missing")
        if needed is not None and not isinstance(needed, str):
            raise CoverageSpecError(
                f"{evidence_id}: needed_capability_if_missing must be a string"
            )

        if kind == "unsupported":
            results.append(
                RequirementResult(
                    evidence_id=evidence_id,
                    evidence_type=evidence_type,
                    status="gap",
                    check_kind=kind,
                    needed_capability=needed or "unspecified-deterministic-capability",
                )
            )
            continue

        artifact = _required_string(check, "artifact")
        fragments_raw = check.get("fragments")
        if not isinstance(fragments_raw, list) or not fragments_raw or not all(
            isinstance(item, str) and item.strip() for item in fragments_raw
        ):
            raise CoverageSpecError(f"{evidence_id}: fragments must be non-empty strings")
        fragments = tuple(item.strip() for item in fragments_raw)
        candidates = tuple(
            assertion
            for assertion in assertions
            if _assertion_belongs_to_artifact(assertion, artifact)
        )

        if kind == "source_assertion_contains":
            matched = tuple(
                assertion
                for assertion in candidates
                if _contains_all(assertion.statement, fragments)
            )
            if matched:
                results.append(
                    RequirementResult(
                        evidence_id=evidence_id,
                        evidence_type=evidence_type,
                        status="recovered",
                        check_kind=kind,
                        matched_locators=tuple(item.locator for item in matched),
                    )
                )
            else:
                combined = "\n".join(item.statement for item in candidates)
                missing = tuple(
                    fragment for fragment in fragments if not _contains(combined, fragment)
                )
                results.append(
                    RequirementResult(
                        evidence_id=evidence_id,
                        evidence_type=evidence_type,
                        status="gap",
                        check_kind=kind,
                        missing_fragments=missing,
                        needed_capability=needed or "deterministic-source-assertion-coverage",
                    )
                )
            continue

        if kind == "source_assertions_cover":
            combined = "\n".join(item.statement for item in candidates)
            missing = tuple(
                fragment for fragment in fragments if not _contains(combined, fragment)
            )
            if not missing:
                matched_locators = tuple(
                    item.locator
                    for item in candidates
                    if any(_contains(item.statement, fragment) for fragment in fragments)
                )
                results.append(
                    RequirementResult(
                        evidence_id=evidence_id,
                        evidence_type=evidence_type,
                        status="recovered",
                        check_kind=kind,
                        matched_locators=matched_locators,
                    )
                )
            else:
                results.append(
                    RequirementResult(
                        evidence_id=evidence_id,
                        evidence_type=evidence_type,
                        status="gap",
                        check_kind=kind,
                        missing_fragments=missing,
                        needed_capability=needed or "deterministic-source-assertion-coverage",
                    )
                )
            continue

        raise CoverageSpecError(f"{evidence_id}: unsupported check kind {kind!r}")

    return results


def run_live_coverage(
    spec_path: str | Path,
    *,
    token: str | None = None,
    workspace: str | Path | None = None,
) -> dict[str, Any]:
    """Run real pinned GitHub capture + extraction for every case in a spec."""

    spec = load_coverage_spec(spec_path)
    if workspace is None:
        with tempfile.TemporaryDirectory(prefix="lemmamind-pilot-coverage-") as directory:
            return _run_live_coverage(spec, Path(directory), token=token)
    return _run_live_coverage(spec, Path(workspace), token=token)


def _run_live_coverage(
    spec: Mapping[str, Any], workspace: Path, *, token: str | None
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    store = SQLiteContractStore(workspace / "coverage.db")
    objects = ContentAddressedFileStore(workspace / "objects")
    reader = GitHubRESTReader(token=token)
    capture = GitHubCaptureService(reader, store, objects)
    extraction = DeterministicExtractionService(store, objects)

    case_reports: list[dict[str, Any]] = []
    total = 0
    recovered = 0
    gap_counter: Counter[str] = Counter()

    for raw_case in spec["cases"]:
        if not isinstance(raw_case, Mapping):
            raise CoverageSpecError("case entries must be mappings")
        case_id = _required_string(raw_case, "case_id")
        repository = _required_string(raw_case, "repository")
        revision = _required_string(raw_case, "revision")
        source_role_value = _required_string(raw_case, "source_role")
        try:
            source_role = SourceRole(source_role_value)
        except ValueError as exc:
            raise CoverageSpecError(
                f"{case_id}: unknown source_role {source_role_value!r}"
            ) from exc
        paths = raw_case.get("paths")
        requirements = raw_case.get("requirements")
        if not isinstance(paths, list) or not paths or not all(
            isinstance(item, str) and item.strip() for item in paths
        ):
            raise CoverageSpecError(f"{case_id}: paths must be non-empty strings")
        if not isinstance(requirements, list) or not requirements:
            raise CoverageSpecError(f"{case_id}: requirements must be a non-empty list")

        captured = capture.capture_repository(
            repository,
            paths,
            source_role=source_role,
            ref=revision,
        )
        extracted = extraction.extract_capture(captured.manifest.capture_id)
        requirement_results = assess_requirements(requirements, extracted)
        case_total = len(requirement_results)
        case_recovered = sum(item.status == "recovered" for item in requirement_results)
        total += case_total
        recovered += case_recovered
        for item in requirement_results:
            if item.status == "gap" and item.needed_capability:
                gap_counter[item.needed_capability] += 1

        case_reports.append(
            {
                "case_id": case_id,
                "repository": repository,
                "revision": revision,
                "source_role": source_role.value,
                "capture": {
                    "requested_paths": list(paths),
                    "artifact_statuses": [
                        {
                            "path": item.source_locator,
                            "status": item.retrieval_status.value,
                        }
                        for item in captured.manifest.artifacts
                    ],
                },
                "extraction": {
                    "fact_count": len(extracted.facts),
                    "source_assertion_count": len(extracted.assertions),
                },
                "requirements": [item.to_dict() for item in requirement_results],
                "summary": {
                    "total": case_total,
                    "recovered": case_recovered,
                    "coverage_fraction": _fraction(case_recovered, case_total),
                },
            }
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "coverage_id": spec.get("coverage_id"),
        "source_spec_schema_version": spec.get("schema_version"),
        "summary": {
            "case_count": len(case_reports),
            "evidence_requirement_count": total,
            "recovered_count": recovered,
            "gap_count": total - recovered,
            "coverage_fraction": _fraction(recovered, total),
            "gaps_by_needed_capability": dict(sorted(gap_counter.items())),
        },
        "cases": case_reports,
        "interpretation_boundary": (
            "Evidence recovery measures deterministic source-addressed coverage only; "
            "it does not generate or validate golden Observations."
        ),
    }


def report_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# External pilot deterministic-evidence coverage",
        "",
        f"Coverage ID: `{report.get('coverage_id')}`",
        "",
        "This report measures deterministic evidence recovery only. It does not claim that "
        "golden observations can be generated without reasoning or review.",
        "",
        "## Summary",
        "",
        f"- Cases: **{summary['case_count']}**",
        f"- Evidence requirements: **{summary['evidence_requirement_count']}**",
        f"- Recovered: **{summary['recovered_count']}**",
        f"- Gaps: **{summary['gap_count']}**",
        f"- Coverage fraction: **{summary['coverage_fraction']:.3f}**",
        "",
        "## Cases",
        "",
        "| Case | Recovered | Total | Fraction |",
        "| --- | ---: | ---: | ---: |",
    ]
    for case in report["cases"]:
        case_summary = case["summary"]
        lines.append(
            f"| `{case['case_id']}` | {case_summary['recovered']} | "
            f"{case_summary['total']} | {case_summary['coverage_fraction']:.3f} |"
        )

    lines.extend(["", "## Missing deterministic capabilities", ""])
    gaps = summary["gaps_by_needed_capability"]
    if gaps:
        for capability, count in gaps.items():
            lines.append(f"- `{capability}`: {count} evidence requirement(s)")
    else:
        lines.append("- None")

    lines.extend(["", "## Requirement detail", ""])
    for case in report["cases"]:
        lines.append(f"### `{case['case_id']}`")
        lines.append("")
        for requirement in case["requirements"]:
            suffix = ""
            if requirement.get("needed_capability"):
                suffix = f" — needs `{requirement['needed_capability']}`"
            lines.append(
                f"- `{requirement['evidence_id']}`: **{requirement['status']}**{suffix}"
            )
            if requirement.get("matched_locators"):
                for locator in requirement["matched_locators"]:
                    lines.append(f"  - matched: `{locator}`")
            if requirement.get("missing_fragments"):
                for fragment in requirement["missing_fragments"]:
                    lines.append(f"  - missing fragment: `{fragment}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def dump_report_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CoverageSpecError(f"{key} must be a non-empty string")
    return value.strip()


def _assertion_belongs_to_artifact(assertion: SourceAssertion, artifact: str) -> bool:
    return assertion.locator.startswith(f"{artifact}:") or assertion.locator.startswith(
        f"{artifact}#"
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains(haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in _normalize_text(haystack)


def _contains_all(haystack: str, fragments: tuple[str, ...]) -> bool:
    return all(_contains(haystack, fragment) for fragment in fragments)


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator
