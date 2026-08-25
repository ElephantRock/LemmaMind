"""Pilot coverage runner with deterministic Git-object, Python, and TypeScript evidence.

V3 preserves the report schema while extending the evidence-producing policy with
pinned Tree-sitter TypeScript/TSX syntax and authored comment extraction.
"""
from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .contracts import SourceRole
from .extraction import DeterministicExtractionService, ExtractionResult
from .git_commit import (
    GitCommitEvidenceService,
    GitCommitExtractionResult,
    GitHubCommitCaptureService,
)
from .git_tree import (
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
from .pilot_coverage_v2 import (
    _assess_commit_message,
    _assess_python_ast,
    _assess_root_tree,
    _check_kind,
    _fraction,
    _required_string,
)
from .storage import SQLiteContractStore
from .typescript_ast import typescript_aware_extractors


def run_live_coverage(
    spec_path: str | Path,
    *,
    token: str | None = None,
    workspace: str | Path | None = None,
) -> dict[str, Any]:
    """Run pinned external coverage with the V3 deterministic evidence policy."""

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
    extraction = DeterministicExtractionService(
        store,
        objects,
        artifact_extractors=typescript_aware_extractors(),
        extraction_policy_version="deterministic-evidence.typescript-ast.v1",
    )
    tree_capture = GitHubRootTreeCaptureService(reader, store, objects)
    tree_extraction = GitTreeEvidenceService(store, objects)
    commit_capture = GitHubCommitCaptureService(reader, store, objects)
    commit_extraction = GitCommitEvidenceService(store, objects)

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

        needs_tree = any(
            _check_kind(requirement) == "git_root_tree_contains"
            for requirement in requirements
            if isinstance(requirement, Mapping)
        )
        tree_result: GitTreeExtractionResult | None = None
        tree_capture_id: str | None = None
        if needs_tree:
            tree_captured = tree_capture.capture_root_tree(captured.revision.source_revision_id)
            tree_capture_id = tree_captured.manifest.capture_id
            tree_result = tree_extraction.extract_root_tree(tree_capture_id)

        needs_commit = any(
            _check_kind(requirement) == "commit_message_contains"
            for requirement in requirements
            if isinstance(requirement, Mapping)
        )
        commit_result: GitCommitExtractionResult | None = None
        commit_capture_id: str | None = None
        if needs_commit:
            commit_captured = commit_capture.capture_commit(captured.revision.source_revision_id)
            commit_capture_id = commit_captured.manifest.capture_id
            commit_result = commit_extraction.extract_commit(commit_capture_id)

        requirement_results: list[RequirementResult] = []
        for requirement in requirements:
            if not isinstance(requirement, Mapping):
                raise CoverageSpecError(f"{case_id}: requirement must be a mapping")
            kind = _check_kind(requirement)
            if kind == "git_root_tree_contains":
                if tree_result is None:
                    raise CoverageSpecError(
                        f"{case_id}: tree requirement executed without tree capture"
                    )
                requirement_results.append(_assess_root_tree(requirement, tree_result))
            elif kind == "commit_message_contains":
                if commit_result is None:
                    raise CoverageSpecError(
                        f"{case_id}: commit requirement executed without commit capture"
                    )
                requirement_results.append(_assess_commit_message(requirement, commit_result))
            elif kind == "python_ast_contains":
                requirement_results.append(_assess_python_ast(requirement, extracted))
            elif kind == "typescript_evidence_bundle":
                requirement_results.append(_assess_typescript_bundle(requirement, extracted))
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
                {"path": item.source_locator, "status": item.retrieval_status.value}
                for item in captured.manifest.artifacts
            ],
        }
        if tree_capture_id is not None:
            capture_payload["root_tree_capture"] = {
                "source_revision_tree_sha": captured.revision.tree_sha,
                "capture_id_omitted_from_stable_report": True,
            }
        if commit_capture_id is not None:
            capture_payload["commit_capture"] = {
                "source_revision_commit_sha": captured.revision.commit_sha,
                "capture_id_omitted_from_stable_report": True,
            }

        python_fact_count = sum(
            fact.extractor_name == "python-ast" for fact in extracted.facts
        )
        python_docstring_count = sum(
            assertion.extractor_name == "python-docstring"
            for assertion in extracted.assertions
        )
        typescript_fact_count = sum(
            fact.extractor_name == "typescript-ast" for fact in extracted.facts
        )
        typescript_comment_count = sum(
            assertion.extractor_name == "typescript-comment"
            for assertion in extracted.assertions
        )

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
                    "python_ast_fact_count": python_fact_count,
                    "python_docstring_assertion_count": python_docstring_count,
                    "typescript_ast_fact_count": typescript_fact_count,
                    "typescript_comment_assertion_count": typescript_comment_count,
                    "root_tree_fact_count": 0 if tree_result is None else len(tree_result.facts),
                    "commit_fact_count": 0 if commit_result is None else len(commit_result.facts),
                    "commit_source_assertion_count": (
                        0 if commit_result is None else len(commit_result.assertions)
                    ),
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


def _assess_typescript_bundle(
    requirement: Mapping[str, Any], extracted: ExtractionResult
) -> RequirementResult:
    evidence_id = _required_string(requirement, "evidence_id")
    evidence_type = _required_string(requirement, "evidence_type")
    check = requirement.get("check")
    if not isinstance(check, Mapping):
        raise CoverageSpecError(f"{evidence_id}: check must be a mapping")
    artifact = _required_string(check, "artifact")
    needed = requirement.get("needed_capability_if_missing")
    if needed is not None and not isinstance(needed, str):
        raise CoverageSpecError(
            f"{evidence_id}: needed_capability_if_missing must be a string"
        )

    comments = [
        assertion
        for assertion in extracted.assertions
        if assertion.extractor_name == "typescript-comment"
        and assertion.locator.startswith(f"{artifact}:")
    ]
    facts = [
        fact
        for fact in extracted.facts
        if fact.extractor_name == "typescript-ast"
        and fact.locator.startswith(f"{artifact}:")
        and isinstance(fact.normalized_value, dict)
    ]

    comment_fragments = check.get("comment_fragments", [])
    if not isinstance(comment_fragments, list) or not all(
        isinstance(item, str) and item.strip() for item in comment_fragments
    ):
        raise CoverageSpecError(f"{evidence_id}: comment_fragments must be strings")

    selectors = check.get("fact_selectors", [])
    if not isinstance(selectors, list) or not all(isinstance(item, Mapping) for item in selectors):
        raise CoverageSpecError(f"{evidence_id}: fact_selectors must be mappings")
    if not comment_fragments and not selectors:
        raise CoverageSpecError(
            f"{evidence_id}: typescript_evidence_bundle requires comments or facts"
        )

    matched_locators: list[str] = []
    missing: list[str] = []

    for fragment in comment_fragments:
        matches = [item for item in comments if _contains(item.statement, fragment)]
        if matches:
            matched_locators.extend(item.locator for item in matches)
        else:
            missing.append(f"comment:{fragment}")

    for selector in selectors:
        kind = _required_string(selector, "kind")
        field = selector.get("field", "text")
        if not isinstance(field, str) or not field.strip():
            raise CoverageSpecError(f"{evidence_id}: selector field must be a string")
        contains = selector.get("contains")
        equals = selector.get("equals")
        if (contains is None) == (equals is None):
            raise CoverageSpecError(
                f"{evidence_id}: selector requires exactly one of contains or equals"
            )
        if contains is not None and not isinstance(contains, str):
            raise CoverageSpecError(f"{evidence_id}: selector contains must be a string")
        if equals is not None and not isinstance(equals, str):
            raise CoverageSpecError(f"{evidence_id}: selector equals must be a string")

        matches = []
        for fact in facts:
            value = fact.normalized_value
            if value.get("kind") != kind:
                continue
            observed = value.get(field)
            if contains is not None and _contains(str(observed or ""), contains):
                matches.append(fact)
            elif equals is not None and str(observed) == equals:
                matches.append(fact)
        if matches:
            matched_locators.extend(item.locator for item in matches)
        else:
            expected = contains if contains is not None else equals
            missing.append(f"fact:{kind}:{field}:{expected}")

    if not missing:
        return RequirementResult(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            status="recovered",
            check_kind="typescript_evidence_bundle",
            matched_locators=tuple(dict.fromkeys(matched_locators)),
        )

    return RequirementResult(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        status="gap",
        check_kind="typescript_evidence_bundle",
        missing_fragments=tuple(missing),
        needed_capability=needed or "typescript-comments-and-structural-facts",
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains(haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in _normalize_text(haystack)
