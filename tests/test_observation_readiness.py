from pathlib import Path

import pytest
import yaml

from lemmamind.observation_readiness import (
    ObservationReadinessError,
    evaluate_readiness,
)


SPEC = Path("eval/pilot/observation-readiness-v1.yaml")


def test_hard_case_readiness_matches_frozen_boundaries() -> None:
    report = evaluate_readiness(SPEC)

    assert report["summary"] == {
        "case_count": 4,
        "ready": 2,
        "blocked": 1,
        "deferred": 1,
    }
    by_case = {item["case_id"]: item for item in report["cases"]}

    assert by_case["external-opd-source-type"]["outcome"] == "ready"
    assert by_case["external-opd-source-type"]["blockers"] == []

    assert by_case["csd-foundry-frontier"]["outcome"] == "blocked"
    assert {item["capability"] for item in by_case["csd-foundry-frontier"]["blockers"]} == {
        "github_process_event_history",
        "temporal_change_reconciliation",
    }
    assert by_case["csd-foundry-frontier"]["belief_revision_required"] is True

    assert by_case["resonance-world-confirmatory"]["outcome"] == "ready"
    assert by_case["resonance-world-confirmatory"]["blockers"] == []

    assert by_case["private-actions-pattern"]["outcome"] == "deferred"
    assert {item["capability"] for item in by_case["private-actions-pattern"]["blockers"]} == {
        "cross_repository_pattern_layer",
    }
    assert by_case["private-actions-pattern"]["source_count"] == 4


def test_readiness_fails_closed_when_declared_outcome_hides_missing_capability(tmp_path) -> None:
    payload = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    csd = next(item for item in payload["cases"] if item["case_id"] == "csd-foundry-frontier")
    csd["expected_outcome"] = "ready"
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ObservationReadinessError, match="computed outcome"):
        evaluate_readiness(broken)
