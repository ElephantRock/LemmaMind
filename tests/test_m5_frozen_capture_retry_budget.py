from pathlib import Path
import runpy
import sys
from types import ModuleType


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_semantic_replay.py"


class FakeGitHubIntervalRESTReader:
    def __init__(self, *, token: str, max_retries: int) -> None:
        self.token = token
        self.max_retries = max_retries


def test_frozen_replay_uses_explicit_extended_capture_retry_budget(monkeypatch) -> None:
    monkeypatch.setenv("M5_PR34_SHA", "a" * 40)
    interval_module = ModuleType("lemmamind.interval_segmentation")
    interval_module.GitHubIntervalRESTReader = FakeGitHubIntervalRESTReader
    monkeypatch.setitem(sys.modules, "lemmamind.interval_segmentation", interval_module)
    namespace = runpy.run_path(str(SCRIPT), run_name="m5_frozen_capture_retry_budget_test")

    reader = namespace["make_capture_reader"]("test-token")

    assert namespace["CAPTURE_MAX_RETRIES"] == 5
    assert reader.max_retries == 5
    assert reader.token == "test-token"


def test_capture_retry_budget_is_finite(monkeypatch) -> None:
    monkeypatch.setenv("M5_PR34_SHA", "a" * 40)
    namespace = runpy.run_path(str(SCRIPT), run_name="m5_frozen_capture_retry_bound_test")

    assert 0 < namespace["CAPTURE_MAX_RETRIES"] <= 5
