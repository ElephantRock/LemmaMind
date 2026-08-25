from datetime import datetime, timezone
from pathlib import Path

import yaml

from lemmamind.contracts import PipelineRun, RunType, SourceAssertion
from lemmamind.extraction import ExtractionResult
from lemmamind.pilot_coverage import (
    assess_requirements,
    load_coverage_spec,
    report_markdown,
)

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def extraction_with(*assertions: SourceAssertion) -> ExtractionResult:
    return ExtractionResult(
        capture_id="capture:test",
        facts=(),
        assertions=assertions,
        run=PipelineRun(
            run_id="run:test",
            run_type=RunType.EXTRACTION,
            code_version="test",
            contract_schema_version="lemmamind.m0.v1",
            policy_version="test",
            started_at=NOW,
            finished_at=NOW,
            inputs_hash=DIGEST,
            outputs_hash=DIGEST,
        ),
    )


def assertion(locator: str, statement: str) -> SourceAssertion:
    return SourceAssertion(
        assertion_id=f"assertion:{locator}",
        artifact_id="artifact:test",
        locator=locator,
        statement=statement,
        extractor_name="markdown-prose",
        extractor_version="1",
        run_id="run:test",
    )


def test_source_assertion_contains_requires_one_matching_assertion() -> None:
    extraction = extraction_with(
        assertion("README.md:L2-L2", "Sandboxing is off by default."),
        assertion("README.md:L4-L4", "It is controlled by the agent configuration."),
    )
    requirements = [
        {
            "evidence_id": "e1",
            "evidence_type": "SourceAssertion",
            "check": {
                "kind": "source_assertion_contains",
                "artifact": "README.md",
                "fragments": ["off by default", "controlled by"],
            },
            "needed_capability_if_missing": "paragraph-preservation",
        }
    ]

    result = assess_requirements(requirements, extraction)[0]

    assert result.status == "gap"
    assert result.needed_capability == "paragraph-preservation"


def test_source_assertions_cover_can_span_multiple_assertions() -> None:
    extraction = extraction_with(
        assertion("README.md:L2-L2", "A curated collection of papers and tools."),
        assertion("README.md:L8-L8", "See Frameworks and Implementations."),
    )
    requirements = [
        {
            "evidence_id": "e2",
            "evidence_type": "SourceAssertion",
            "check": {
                "kind": "source_assertions_cover",
                "artifact": "README.md",
                "fragments": ["curated collection", "Frameworks and Implementations"],
            },
        }
    ]

    result = assess_requirements(requirements, extraction)[0]

    assert result.status == "recovered"
    assert result.matched_locators == ("README.md:L2-L2", "README.md:L8-L8")


def test_assertion_checks_are_artifact_scoped() -> None:
    extraction = extraction_with(
        assertion("docs/other.md:L1-L1", "The Gateway process always stays on the host."),
    )
    requirements = [
        {
            "evidence_id": "e3",
            "evidence_type": "SourceAssertion",
            "check": {
                "kind": "source_assertion_contains",
                "artifact": "docs/gateway/sandboxing.md",
                "fragments": ["Gateway process always stays on the host"],
            },
        }
    ]

    result = assess_requirements(requirements, extraction)[0]

    assert result.status == "gap"
    assert result.matched_locators == ()


def test_unsupported_requirement_reports_named_capability() -> None:
    result = assess_requirements(
        [
            {
                "evidence_id": "e4",
                "evidence_type": "ObservedFact",
                "check": {"kind": "unsupported"},
                "needed_capability_if_missing": "source-code-semantic-facts",
            }
        ],
        extraction_with(),
    )[0]

    assert result.status == "gap"
    assert result.needed_capability == "source-code-semantic-facts"


def test_external_coverage_spec_revisions_match_watchlist() -> None:
    spec = load_coverage_spec("eval/pilot/coverage/external-v1.yaml")
    watchlist = yaml.safe_load(Path("pilot/watchlist.yaml").read_text(encoding="utf-8"))
    pins = {
        item["repository"]: item["revision"]
        for item in watchlist["repositories"]
    }

    for case in spec["cases"]:
        assert pins[case["repository"]] == case["revision"]


def test_markdown_report_names_coverage_boundary_and_gaps() -> None:
    report = {
        "coverage_id": "example",
        "summary": {
            "case_count": 1,
            "evidence_requirement_count": 2,
            "recovered_count": 1,
            "gap_count": 1,
            "coverage_fraction": 0.5,
            "gaps_by_needed_capability": {"source-code-semantic-facts": 1},
        },
        "cases": [
            {
                "case_id": "case-one",
                "summary": {"total": 2, "recovered": 1, "coverage_fraction": 0.5},
                "requirements": [
                    {
                        "evidence_id": "e1",
                        "status": "recovered",
                        "matched_locators": ["README.md:L1-L1"],
                        "missing_fragments": [],
                    },
                    {
                        "evidence_id": "e2",
                        "status": "gap",
                        "needed_capability": "source-code-semantic-facts",
                        "matched_locators": [],
                        "missing_fragments": [],
                    },
                ],
            }
        ],
    }

    text = report_markdown(report)

    assert "deterministic evidence recovery only" in text
    assert "`source-code-semantic-facts`: 1" in text
    assert "`e1`: **recovered**" in text
