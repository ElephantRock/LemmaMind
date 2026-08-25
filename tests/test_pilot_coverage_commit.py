from datetime import datetime, timezone

from lemmamind.contracts import PipelineRun, RunType, SourceAssertion
from lemmamind.git_commit import GIT_COMMIT_LOCATOR, GitCommitExtractionResult
from lemmamind.pilot_coverage_v2 import _assess_commit_message

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def commit_result(message: str) -> GitCommitExtractionResult:
    run = PipelineRun(
        run_id="run:commit",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="git-commit-evidence.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST,
        outputs_hash=DIGEST,
    )
    assertion = SourceAssertion(
        assertion_id="assertion:commit",
        artifact_id="artifact:commit",
        locator=f"{GIT_COMMIT_LOCATOR}#message",
        statement=message,
        extractor_name="git-commit-message",
        extractor_version="1",
        run_id=run.run_id,
    )
    return GitCommitExtractionResult("capture-commit:test", (), (assertion,), run)


def requirement():
    return {
        "evidence_id": "hermes-containment-1",
        "evidence_type": "SourceAssertion",
        "check": {
            "kind": "commit_message_contains",
            "fragments": ["sweep setsid descendants", "local timeout group-kill"],
        },
        "needed_capability_if_missing": "commit-metadata-and-change-facts",
    }


def test_commit_message_recovers_requirement() -> None:
    result = _assess_commit_message(
        requirement(),
        commit_result(
            "Merge pull request #1\n\n"
            "fix(terminal): sweep setsid descendants after local timeout group-kill"
        ),
    )

    assert result.status == "recovered"
    assert result.matched_locators == (f"{GIT_COMMIT_LOCATOR}#message",)


def test_commit_message_reports_missing_fragment() -> None:
    result = _assess_commit_message(
        requirement(),
        commit_result("fix(terminal): sweep setsid descendants"),
    )

    assert result.status == "gap"
    assert result.missing_fragments == ("local timeout group-kill",)
    assert result.needed_capability == "commit-metadata-and-change-facts"
