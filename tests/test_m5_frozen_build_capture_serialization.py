from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "m5-frozen-semantic-replay.yml"
CONTROL = ROOT / "scripts" / "run_m5_frozen_semantic_replay.py"


def _build_section() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return text.split("\n  build:\n", 1)[1].split("\n  inference:\n", 1)[0]


def test_frozen_source_capture_builds_are_serialized() -> None:
    section = _build_section()

    assert "strategy:\n      fail-fast: false\n      max-parallel: 1\n      matrix:" in section
    assert "repo_key: [openbot, openclaw, hermes]" in section


def test_capture_retry_budget_is_not_escalated_by_serialization_repair() -> None:
    control = CONTROL.read_text(encoding="utf-8")

    assert "CAPTURE_MAX_RETRIES = 5" in control
    assert "GitHubIntervalRESTReader(token=token, max_retries=CAPTURE_MAX_RETRIES)" in control
