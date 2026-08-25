from datetime import datetime, timezone

from lemmamind.contracts import EvidenceFact, PipelineRun, RunType
from lemmamind.git_tree import GIT_ROOT_TREE_LOCATOR, GitTreeExtractionResult
from lemmamind.pilot_coverage_v2 import _assess_root_tree

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def tree_result(paths, *, truncated=False):
    run = PipelineRun(
        run_id="run:tree",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="git-tree-facts.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST,
        outputs_hash=DIGEST,
    )
    facts = (
        EvidenceFact(
            evidence_id="fact:paths",
            artifact_id="artifact:tree",
            locator=f"{GIT_ROOT_TREE_LOCATOR}#/entry_paths",
            raw_value=paths,
            normalized_value=paths,
            extractor_name="git-root-tree",
            extractor_version="1",
            run_id=run.run_id,
        ),
        EvidenceFact(
            evidence_id="fact:truncated",
            artifact_id="artifact:tree",
            locator=f"{GIT_ROOT_TREE_LOCATOR}#/truncated",
            raw_value=truncated,
            normalized_value=truncated,
            extractor_name="git-root-tree",
            extractor_version="1",
            run_id=run.run_id,
        ),
    )
    return GitTreeExtractionResult("capture-tree:test", facts, run)


def requirement():
    return {
        "evidence_id": "opd-source-3",
        "evidence_type": "ObservedFact",
        "check": {
            "kind": "git_root_tree_contains",
            "require_complete": True,
            "exact_entries": True,
            "entries": ["CITATION.cff", "CONTRIBUTING.md", "LICENSE", "README.md"],
        },
        "needed_capability_if_missing": "complete-repository-tree-facts",
    }


def test_exact_complete_tree_recovers_requirement() -> None:
    result = _assess_root_tree(
        requirement(),
        tree_result(["CITATION.cff", "CONTRIBUTING.md", "LICENSE", "README.md"]),
    )

    assert result.status == "recovered"
    assert result.matched_locators == (
        f"{GIT_ROOT_TREE_LOCATOR}#/entry_paths",
        f"{GIT_ROOT_TREE_LOCATOR}#/truncated",
    )


def test_exact_tree_rejects_unexpected_root_entry() -> None:
    result = _assess_root_tree(
        requirement(),
        tree_result(["CITATION.cff", "CONTRIBUTING.md", "LICENSE", "README.md", "src"]),
    )

    assert result.status == "gap"
    assert "unexpected root entry: src" in result.missing_fragments


def test_complete_tree_rejects_truncated_response() -> None:
    result = _assess_root_tree(
        requirement(),
        tree_result(["CITATION.cff", "CONTRIBUTING.md", "LICENSE", "README.md"], truncated=True),
    )

    assert result.status == "gap"
    assert "complete non-truncated root tree" in result.missing_fragments
