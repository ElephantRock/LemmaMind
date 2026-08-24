from pathlib import Path

import yaml

from lemmamind.contracts import ObservationEpistemicType, RelationshipType, ValidationState

CASE_DIR = Path(__file__).resolve().parents[1] / "eval" / "pilot" / "cases"
EXPECTED_EXTERNAL_CASE_FILES = {
    "external-hermes-process-containment.yaml",
    "external-opd-source-type.yaml",
    "external-openbot-capability-authority.yaml",
    "external-openclaw-sandbox-posture.yaml",
    "external-runtime-authority-pattern.yaml",
}
EVIDENCE_CLASSES = {"ObservedFact", "SourceAssertion"}


def load_cases() -> list[dict]:
    paths = sorted(CASE_DIR.glob("*.yaml"))
    assert paths, "M-1 golden corpus must not be empty"

    cases = []
    for path in paths:
        try:
            cases.append(yaml.safe_load(path.read_text(encoding="utf-8")))
        except yaml.YAMLError as exc:
            raise AssertionError(f"invalid golden YAML: {path}") from exc
    return cases


def test_m1_external_regression_cases_remain_present() -> None:
    present = {path.name for path in CASE_DIR.glob("*.yaml")}
    assert EXPECTED_EXTERNAL_CASE_FILES <= present


def test_golden_corpus_epistemic_and_relationship_values_fit_m0_contracts() -> None:
    for case in load_cases():
        relationship = case["repository_relationship"]
        RelationshipType(relationship["type"])

        for evidence in case["evidence"]:
            assert evidence["epistemic_type"] in EVIDENCE_CLASSES

        for observation in case["expected_observations"]:
            ObservationEpistemicType(observation["epistemic_type"])
            ValidationState(observation["validation_state"])


def test_golden_sources_preserve_exact_revision_identities() -> None:
    for case in load_cases():
        for source in case["sources"]:
            revision = str(source["revision"])
            assert len(revision) >= 7
            assert source["repository"].count("/") == 1
