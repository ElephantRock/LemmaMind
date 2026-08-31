import json
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


@pytest.mark.parametrize("value", ["NOT-A-GIT-SHA", " " + "a" * 40, "a" * 40 + "\n"])
def test_replay_driver_rejects_malformed_runtime_sha(monkeypatch, value: str) -> None:
    monkeypatch.setenv("M5_PR34_SHA", value)

    with pytest.raises(RuntimeError, match="40-character lowercase Git SHA"):
        runpy.run_path(str(SCRIPT), run_name="m5_frozen_replay_bad_runtime_pin_test")


def test_aggregate_rejects_mixed_runtime_provenance(monkeypatch, tmp_path) -> None:
    expected = "a" * 40
    monkeypatch.setenv("M5_PR34_SHA", expected)
    namespace = runpy.run_path(str(SCRIPT), run_name="m5_frozen_replay_aggregate_pin_test")

    for repo_key in namespace["SPECS"]:
        root = tmp_path / repo_key
        root.mkdir(parents=True)
        runtime_sha = "b" * 40 if repo_key == "openclaw" else expected
        (root / "validation_meta.json").write_text(
            json.dumps({"runtime_sha": runtime_sha, "status": "INCONCLUSIVE_PROVIDER_OUTPUT"}),
            encoding="utf-8",
        )
        (root / "review_items.json").write_text("[]", encoding="utf-8")

    with pytest.raises(AssertionError, match="openclaw"):
        namespace["aggregate"](tmp_path, tmp_path / "report")
