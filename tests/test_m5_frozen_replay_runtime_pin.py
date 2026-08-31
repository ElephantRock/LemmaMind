from pathlib import Path
import runpy

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_semantic_replay.py"


def test_replay_driver_binds_runtime_sha_from_environment(monkeypatch) -> None:
    expected = "a" * 40
    monkeypatch.setenv("M5_PR34_SHA", expected)

    namespace = runpy.run_path(str(SCRIPT), run_name="m5_frozen_replay_runtime_pin_test")

    assert namespace["PR34_SHA"] == expected


def test_replay_driver_rejects_missing_runtime_sha(monkeypatch) -> None:
    monkeypatch.delenv("M5_PR34_SHA", raising=False)

    with pytest.raises(RuntimeError, match="M5_PR34_SHA"):
        runpy.run_path(str(SCRIPT), run_name="m5_frozen_replay_missing_runtime_pin_test")


def test_replay_driver_rejects_malformed_runtime_sha(monkeypatch) -> None:
    monkeypatch.setenv("M5_PR34_SHA", "NOT-A-GIT-SHA")

    with pytest.raises(RuntimeError, match="40-character lowercase Git SHA"):
        runpy.run_path(str(SCRIPT), run_name="m5_frozen_replay_bad_runtime_pin_test")
