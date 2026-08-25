"""Pilot coverage runner with deterministic Git root-tree evidence support.

This extends the v1 coverage harness only where the measured corpus requires it.
The report schema remains unchanged so historical baselines stay comparable.
"""
from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .contracts import SourceRole
from .extraction import DeterministicExtractionService
from .git_tree import (
    GIT_ROOT_TREE_LOCATOR,
    GitHubRootTreeCaptureService,
    GitHubTreeRESTReader,
    GitTreeEvidenceService,
    GitTreeExtractionResult,
)
from .github import GitHubCaptureService
from .objects import ContentAddressedFileStore
from .pilot_coverage import (
    REPORT_SCHEMA_VERSION,
    CoverageSpecError,
    RequirementResult,
    assess_requirements,
    load_coverage_spec,
)
from .storage import SQLiteContractStore


def run_live_coverage(
    spec_path: str | Path,
    *,
    token: str | None = None,
    workspace: str | Path | None = None,
) -> dict[str, Any]:
    """Run pinned file evidence plus exact root-tree evidence when requested."""

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
    reader = GitHubTreeRESTReader(token=token)
    capture = GitHubCaptureService(reader, store, objects)
    extraction = DeterministicExtractionService(store, objects)
    tree_capture = GitHubRootTreeCaptureService(reader, store, objects)
    tree_extraction = GitTreeEvidenceService(store, objects)

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

        needs_tree = any(_check_kind(requirement) == "git_root_tree_contains" for requirement in requirements)
        tree_result: GitTreeExtractionResult | None = None
        tree_capture_id: str | None = None
        if needs_tree:
            tree_captured = tree_capture.capture_root_tree(captured.revision.source_revision_id)
            tree_capture_id = tree_captured.manifest.capture_id
            tree_result = tree_extraction.extract_root_tree(tree_capture_id)

        requirement_results: list[RequirementResult] = []
        for requirement in requirements:
            if not isinstance(requirement, Mapping):
                raise CoverageSpecError(f"{case_id}: requirement must be a mapping")
            if _check_kind(requirement) == "git_root_tree_contains":
                if tree_result is None:
                    raise CoverageSpecError(f"{case_id}: tree requirement executed without tree capture")
                requirement_results.append(_assess_root_tree(requirement, tree_result))
            else:
                requirement_results.extend(assess_requirements([requirement], extracted))

        case_total = len(requirement_results)
        case_recovered = sum(item.status == "recovered" for item in requirement_results)
        total += case_total
        recovered += case_recovered
        for item in requirement_results:
            if item.status == "gap" and item.needed_capability:
                gap_counter[item.needed_capability] += 1

        capture_payload: dict[str, Any] = {
            "requested_paths": list(paths),
            "artifact_statuses": [
                {
                    "path": item.source_locator,
                    "status": item.retrieval_status.value,
                }
                for item in captured.manifest.artifacts
            ],
        }
        if tree_capture_id is not None:
            capture_payload["root_tree_capture"] = {
                "source_revision_tree_sha": captured.revision.tree_sha,
                "capture_id_omitted_from_stable_report": True,
            }

        case_reports.append(
            {
                "case_id": case_id,
                "repository": repository,
                "revision": revision,
                "source_role": source_role.value,
                "capture": capture_payload,
                "extraction": {
                    "fact_count": len(extracted.facts),
                    "source_assertion_count": len(extracted.assertions),
                    "root_tree_fact_count": 0 if tree_result is None else len(tree_result.facts),
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


def _assess_root_tree(
    requirement: Mapping[str, Any], tree: GitTreeExtractionResult
) -> RequirementResult:
    evidence_id = _required_string(requirement, "evidence_id")
    evidence_type = _required_string(requirement, "evidence_type")
    check = requirement.get("check")
    if not isinstance(check, Mapping):
        raise CoverageSpecError(f"{evidence_id}: check must be a mapping")
    entries_raw = check.get("entries")
    if not isinstance(entries_raw, list) or not entries_raw or not all(
        isinstance(item, str) and item.strip() for item in entries_raw
    ):
        raise CoverageSpecError(f"{evidence_id}: entries must be non-empty strings")
    required_entries = tuple(item.strip() for item in entries_raw)
    require_complete = check.get("require_complete", False)
    if not isinstance(require_complete, bool):
        raise CoverageSpecError(f"{evidence_id}: require_complete must be boolean")
    needed = requirement.get("needed_capability_if_missing")
    if needed is not None and not isinstance(needed, str):
        raise CoverageSpecError(
            f"{evidence_id}: needed_capability_if_missing must be a string"
        )

    facts = {fact.locator: fact for fact in tree.facts}
    paths_fact = facts.get(f"{GIT_ROOT_TREE_LOCATOR}#/entry_paths")
    truncated_fact = facts.get(f"{GIT_ROOT_TREE_LOCATOR}#/truncated")
    if paths_fact is None or not isinstance(paths_fact.normalized_value, list):
        raise CoverageSpecError(f"{evidence_id}: root-tree extraction omitted entry_paths")
    observed_paths = {
        item for item in paths_fact.normalized_value if isinstance(item, str)
    }
    missing = tuple(item for item in required_entries if item not in observed_paths)
    incomplete = bool(
        require_complete
        and (truncated_fact is None or truncated_fact.normalized_value is not False)
    )

    if not missing and not incomplete:
        locators = [paths_fact.locator]
        if require_complete and truncated_fact is not None:
            locators.append(truncated_fact.locator)
        return RequirementResult(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            status="recovered",
            check_kind="git_root_tree_contains",
            matched_locators=tuple(locators),
        )

    missing_fragments = list(missing)
    if incomplete:
        missing_fragments.append("complete non-truncated root tree")
    return RequirementResult(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        status="gap",
        check_kind="git_root_tree_contains",
        missing_fragments=tuple(missing_fragments),
        needed_capability=needed or "complete-repository-tree-facts",
    )


def _check_kind(requirement: Mapping[str, Any]) -> str:
    check = requirement.get("check")
    if not isinstance(check, Mapping):
        return ""
    value = check.get("kind")
    return value if isinstance(value, str) else ""


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CoverageSpecError(f"{key} must be a non-empty string")
    return value.strip()


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator
