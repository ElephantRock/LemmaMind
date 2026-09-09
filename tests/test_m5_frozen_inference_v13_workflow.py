from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "m5-frozen-semantic-replay.yml"


def _inference_section() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return text.split("\n  inference:\n", 1)[1].split("\n  validate:\n", 1)[0]


def test_frozen_replay_invokes_v13_attention_wrapper_only_for_provider_inference():
    section = _inference_section()

    assert "python control/scripts/run_m5_frozen_inference_v13.py \\\n" in section
    assert "python control/scripts/run_m5_frozen_inference.py \\\n" not in section


def test_v13_workflow_preserves_frozen_provider_serialization_and_worker_limits():
    section = _inference_section()

    assert "strategy:\n      fail-fast: false\n      max-parallel: 1\n      matrix:" in section
    assert "- repo_key: openbot\n            workers: 1" in section
    assert "- repo_key: openclaw\n            workers: 2" in section
    assert "- repo_key: hermes\n            workers: 2" in section
    assert "COPILOT_PROVIDER_API_KEY: ${{ secrets.M5_BYOK_API_KEY }}" in section
    assert "unset GITHUB_TOKEN GH_TOKEN COPILOT_GITHUB_TOKEN" in section
