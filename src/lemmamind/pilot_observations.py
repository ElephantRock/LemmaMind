"""Golden-driven live probe for the first Evidence -> Observation transition.

This probe intentionally does not generate observations. It reuses the frozen
OpenBot golden statements, resolves their named golden evidence groups to exact
runtime EvidenceFact/SourceAssertion records, and asks the M0 Observation
construction service to persist candidate observations with explicit support.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Mapping

import yaml

from .contracts import (
    ObservationEpistemicType,
    SourceRole,
    SupportType,
)
from .extraction import DeterministicExtractionService, ExtractionResult
from .git_tree import GitHubTreeRESTReader
from .github import GitHubCaptureService
from .objects import ContentAddressedFileStore
from .observations import ObservationConstructionService, SupportRef
from .pilot_coverage import CoverageSpecError, assess_requirements, load_coverage_spec
from .pilot_coverage_v3 import _assess_typescript_bundle, _check_kind
from .storage import SQLiteContractStore
from .typescript_ast import typescript_aware_extractors


class PilotObservationError(RuntimeError):
    """Frozen golden observation probe cannot be executed safely."""


def run_openbot_observation_probe(
    *,
    coverage_spec_path: str | Path = "eval/pilot/coverage/external-v1.yaml",
    golden_case_path: str | Path = "eval/pilot/cases/external-openbot-capability-authority.yaml",
    token: str | None = None,
    workspace: str | Path | None = None,
) -> dict[str, Any]:
    if workspace is None:
        with tempfile.TemporaryDirectory(prefix="lemmamind-observation-probe-") as directory:
            return _run_probe(
                Path(directory),
                coverage_spec_path=coverage_spec_path,
                golden_case_path=golden_case_path,
                token=token,
            )
    return _run_probe(
        Path(workspace),
        coverage_spec_path=coverage_spec_path,
        golden_case_path=golden_case_path,
        token=token,
    )


def _run_probe(
    workspace: Path,
    *,
    coverage_spec_path: str | Path,
    golden_case_path: str | Path,
    token: str | None,
) -> dict[str, Any]:
    coverage = load_coverage_spec(coverage_spec_path)
    golden = _load_yaml_mapping(golden_case_path)
    case_id = _required_string(golden, "case_id")
    if case_id != "external-openbot-capability-authority":
        raise PilotObservationError(
            f"v1 probe is pinned to external-openbot-capability-authority, got {case_id}"
        )

    coverage_case = _coverage_case(coverage, case_id)
    repository = _required_string(coverage_case, "repository")
    revision = _required_string(coverage_case, "revision")
    paths = coverage_case.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(item, str) for item in paths):
        raise PilotObservationError("OpenBot coverage paths are invalid")

    workspace.mkdir(parents=True, exist_ok=True)
    store = SQLiteContractStore(workspace / "observations.db")
    objects = ContentAddressedFileStore(workspace / "objects")
    reader = GitHubTreeRESTReader(token=token)
    capture = GitHubCaptureService(reader, store, objects)
    extraction = DeterministicExtractionService(
        store,
        objects,
        artifact_extractors=typescript_aware_extractors(),
        extraction_policy_version="deterministic-evidence.typescript-ast.v1",
    )
    observations = ObservationConstructionService(
        store,
        policy_version="golden-supported-observation.v1",
    )

    captured = capture.capture_repository(
        repository,
        paths,
        source_role=SourceRole.IMPLEMENTATION,
        ref=revision,
    )
    extracted = extraction.extract_capture(captured.manifest.capture_id)

    requirement_results = _requirement_results(coverage_case, extracted)
    support_groups = {
        evidence_id: _support_refs_for_result(result, extracted)
        for evidence_id, result in requirement_results.items()
    }

    expected_observations = golden.get("expected_observations")
    if not isinstance(expected_observations, list) or not expected_observations:
        raise PilotObservationError("golden case has no expected_observations")

    built: list[dict[str, Any]] = []
    for index, expected in enumerate(expected_observations, start=1):
        if not isinstance(expected, Mapping):
            raise PilotObservationError("expected_observations entries must be mappings")
        statement = _required_string(expected, "statement")
        epistemic_value = _required_string(expected, "epistemic_type")
        try:
            epistemic_type = ObservationEpistemicType(epistemic_value)
        except ValueError as exc:
            raise PilotObservationError(
                f"unsupported golden Observation epistemic_type: {epistemic_value}"
            ) from exc

        named_support = expected.get("support")
        if not isinstance(named_support, list) or not named_support or not all(
            isinstance(item, str) and item.strip() for item in named_support
        ):
            raise PilotObservationError("golden Observation support must be non-empty evidence IDs")

        flattened: list[SupportRef] = []
        support_summary: list[dict[str, Any]] = []
        for evidence_id in named_support:
            refs = support_groups.get(evidence_id)
            if refs is None:
                raise PilotObservationError(
                    f"golden Observation references unknown evidence group: {evidence_id}"
                )
            flattened.extend(refs)
            support_summary.append(
                {
                    "golden_evidence_id": evidence_id,
                    "runtime_support_count": len(refs),
                    "runtime_support_types": sorted({ref.support_type.value for ref in refs}),
                    "runtime_locators": _locators_for_refs(refs, extracted),
                }
            )

        unique_refs = tuple(sorted(set(flattened)))
        result = observations.create_candidate(
            logical_claim_id=f"golden:{case_id}:{index}",
            epistemic_type=epistemic_type,
            statement=statement,
            supports=unique_refs,
        )
        built.append(
            {
                "golden_index": index,
                "statement_matches_golden": result.observation.statement == statement,
                "epistemic_type_matches_golden": result.observation.epistemic_type is epistemic_type,
                "runtime_validation_state": result.observation.validation_state.value,
                "golden_validation_target": expected.get("validation_state"),
                "source_revision_id": result.source_revision_id,
                "support_edge_count": len(result.supports),
                "golden_support_groups": support_summary,
            }
        )

    return {
        "schema_version": "lemmamind.pilot-observation-probe.v1",
        "case_id": case_id,
        "repository": repository,
        "revision": revision,
        "source_revision_id": captured.revision.source_revision_id,
        "observation_count": len(built),
        "observations": built,
        "summary": {
            "all_statements_match_golden": all(item["statement_matches_golden"] for item in built),
            "all_epistemic_types_match_golden": all(
                item["epistemic_type_matches_golden"] for item in built
            ),
            "all_runtime_states_candidate": all(
                item["runtime_validation_state"] == "candidate" for item in built
            ),
            "all_support_revision_bound": all(
                item["source_revision_id"] == captured.revision.source_revision_id
                for item in built
            ),
        },
        "interpretation_boundary": (
            "The probe replays frozen golden Observation statements with exact runtime support. "
            "It does not generate or independently validate the statements, and it does not copy "
            "the golden reviewed/validated state into newly constructed candidates."
        ),
    }


def _requirement_results(
    coverage_case: Mapping[str, Any], extracted: ExtractionResult
) -> dict[str, Any]:
    requirements = coverage_case.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise PilotObservationError("coverage case has no requirements")
    results: dict[str, Any] = {}
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            raise PilotObservationError("coverage requirement must be a mapping")
        evidence_id = _required_string(requirement, "evidence_id")
        kind = _check_kind(requirement)
        if kind == "typescript_evidence_bundle":
            result = _assess_typescript_bundle(requirement, extracted)
        else:
            assessed = assess_requirements([requirement], extracted)
            if len(assessed) != 1:
                raise PilotObservationError(f"unexpected coverage assessment cardinality: {evidence_id}")
            result = assessed[0]
        if result.status != "recovered":
            raise PilotObservationError(
                f"golden evidence group is not recovered at runtime: {evidence_id}"
            )
        if not result.matched_locators:
            raise PilotObservationError(
                f"recovered evidence group has no runtime locators: {evidence_id}"
            )
        results[evidence_id] = result
    return results


def _support_refs_for_result(result: Any, extracted: ExtractionResult) -> tuple[SupportRef, ...]:
    refs: list[SupportRef] = []
    for locator in result.matched_locators:
        assertion_matches = [
            item for item in extracted.assertions if item.locator == locator
        ]
        fact_matches = [item for item in extracted.facts if item.locator == locator]
        if len(assertion_matches) + len(fact_matches) != 1:
            raise PilotObservationError(
                f"runtime support locator is missing or ambiguous: {locator}"
            )
        if assertion_matches:
            refs.append(
                SupportRef(
                    SupportType.SOURCE_ASSERTION,
                    assertion_matches[0].assertion_id,
                )
            )
        else:
            refs.append(
                SupportRef(
                    SupportType.EVIDENCE_FACT,
                    fact_matches[0].evidence_id,
                )
            )
    return tuple(sorted(set(refs)))


def _locators_for_refs(
    refs: tuple[SupportRef, ...], extracted: ExtractionResult
) -> list[str]:
    assertion_by_id = {item.assertion_id: item.locator for item in extracted.assertions}
    fact_by_id = {item.evidence_id: item.locator for item in extracted.facts}
    locators = []
    for ref in refs:
        if ref.support_type is SupportType.SOURCE_ASSERTION:
            locators.append(assertion_by_id[ref.support_id])
        elif ref.support_type is SupportType.EVIDENCE_FACT:
            locators.append(fact_by_id[ref.support_id])
        else:
            raise PilotObservationError("golden evidence groups must resolve to leaf evidence")
    return sorted(locators)


def _coverage_case(spec: Mapping[str, Any], case_id: str) -> Mapping[str, Any]:
    cases = spec.get("cases")
    if not isinstance(cases, list):
        raise PilotObservationError("coverage spec has no cases")
    for case in cases:
        if isinstance(case, Mapping) and case.get("case_id") == case_id:
            return case
    raise PilotObservationError(f"coverage spec missing case: {case_id}")


def _load_yaml_mapping(path: str | Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise PilotObservationError(f"YAML root must be a mapping: {path}")
    return payload


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PilotObservationError(f"{key} must be a non-empty string")
    return value.strip()
