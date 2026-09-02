from pathlib import Path
import runpy


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_semantic_replay.py"


def test_frozen_replay_uses_explicit_extended_capture_retry_budget(monkeypatch) -> None:
    monkeypatch.setenv("M5_PR34_SHA", "a" * 40)
    namespace = runpy.run_path(str(SCRIPT), run_name="m5_frozen_capture_retry_budget_test")

    reader = namespace["make_capture_reader"]("test-token")

    assert namespace["CAPTURE_MAX_RETRIES"] == 5
    assert reader.max_retries == 5
    assert reader.token == "test-token"


def test_runtime_reader_default_retry_budget_is_not_changed(monkeypatch) -> None:
    monkeypatch.setenv("M5_PR34_SHA", "a" * 40)
    runpy.run_path(str(SCRIPT), run_name="m5_frozen_capture_retry_default_test")

    from lemmamind.interval_segmentation import GitHubIntervalRESTReader

    assert GitHubIntervalRESTReader(token="test-token").max_retries == 3
