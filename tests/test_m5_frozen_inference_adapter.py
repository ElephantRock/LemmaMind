from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_m5_frozen_inference.py"
SPEC = spec_from_file_location("m5_frozen_inference_adapter", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SYSTEM_RULES = MODULE.SYSTEM_RULES
infer_packets = MODULE.infer_packets
invoke = MODULE.invoke
normalize = MODULE.normalize
parse_json_object = MODULE.parse_json_object


def packet(*, gaps=(), packet_id="packet:test"):
    return {
        "candidate_evidence_packet_id": packet_id,
        "artifact_delta_ids": ["artifact-delta:1"],
        "structural_delta_previews": [
            {"structural_delta_id": "structural-delta:1"}
        ],
        "assertion_previews": [
            {"assertion_id": "assertion:1"}
        ],
        "extraction_gap_signal_ids": list(gaps),
    }


def proposal(**updates):
    value = {
        "decision": "interpret",
        "interpretation_types": ["modification"],
        "mechanism": "session scoped model selection persistence",
        "summary": "The cited structural evidence changes persisted selection behavior.",
        "uncertainty_notes": [],
        "supports": [
            {
                "support_type": "StructuralDelta",
                "support_id": "structural-delta:1",
            }
        ],
    }
    value.update(updates)
    return value


def test_decline_is_exact_and_cannot_carry_hidden_fields():
    assert normalize(packet(), {"decision": "decline"}) == {"status": "decline"}
    with pytest.raises(ValueError, match="only the decision"):
        normalize(packet(), {"decision": "decline", "reason": "low signal"})


def test_interpretation_rejects_support_outside_exact_packet():
    value = proposal(
        supports=[
            {
                "support_type": "StructuralDelta",
                "support_id": "structural-delta:invented",
            }
        ]
    )
    with pytest.raises(ValueError, match="outside exact packet"):
        normalize(packet(), value)


def test_interpretation_requires_structural_or_authored_assertion_support():
    value = proposal(
        supports=[
            {
                "support_type": "ArtifactDelta",
                "support_id": "artifact-delta:1",
            }
        ]
    )
    with pytest.raises(ValueError, match="requires StructuralDelta or SourceAssertion"):
        normalize(packet(), value)


def test_gap_bearing_interpretation_carries_every_gap_and_uncertainty():
    result = normalize(
        packet(gaps=("gap:2", "gap:1")),
        proposal(),
    )
    assert result["status"] == "interpret"
    proposal_value = result["proposal"]
    gap_supports = [
        item["support_id"]
        for item in proposal_value["supports"]
        if item["support_type"] == "CandidateExtractionGapSignal"
    ]
    assert gap_supports == ["gap:1", "gap:2"]
    assert proposal_value["uncertainty_notes"] == [
        "Deterministic extraction coverage is incomplete for one or more paths in this candidate; the mechanism statement is limited to the cited extracted evidence."
    ]


def test_json_parser_rejects_non_object_provider_output():
    with pytest.raises(ValueError, match="one JSON object"):
        parse_json_object("[]")


def test_model_rules_do_not_embed_frozen_target_labels():
    lowered = SYSTEM_RULES.casefold()
    assert "attention/queries" not in lowered
    assert "sticky-model-selection" not in lowered
    assert "update_contract.py" not in lowered
    assert "8/10" not in lowered
    assert "primary anchor" not in lowered


def test_invoke_streams_large_prompt_over_stdin_without_argv_expansion(monkeypatch, tmp_path):
    prompt = "x" * 3_000_000
    observed = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed.update(kwargs)
        return MODULE.subprocess.CompletedProcess(
            args,
            0,
            stdout='{"decision":"decline"}\n',
            stderr="",
        )

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret")
    monkeypatch.setenv("GH_TOKEN", "gh-secret")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "copilot-secret")

    assert invoke("/tmp/copilot", prompt) == '{"decision":"decline"}'
    assert observed["args"] == [
        "/tmp/copilot",
        "-s",
        "--no-ask-user",
        "--deny-tool=read,write,shell,url,memory",
    ]
    assert prompt not in observed["args"]
    assert sum(len(item) for item in observed["args"]) < 1024
    assert observed["input"] == prompt
    assert observed["check"] is False
    assert observed["capture_output"] is True
    assert observed["text"] is True
    assert observed["timeout"] == MODULE.INVOKE_TIMEOUT_SECONDS == 600
    assert "GITHUB_TOKEN" not in observed["env"]
    assert "GH_TOKEN" not in observed["env"]
    assert "COPILOT_GITHUB_TOKEN" not in observed["env"]


def test_infer_packets_uses_bounded_workers_and_preserves_exact_coverage(monkeypatch):
    observed = {}

    class FakeExecutor:
        def __init__(self, *, max_workers, thread_name_prefix):
            observed["max_workers"] = max_workers
            observed["thread_name_prefix"] = thread_name_prefix

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def map(self, fn, entries):
            return map(fn, entries)

    def fake_infer_packet(_binary, item):
        packet_id = item["candidate_evidence_packet_id"]
        if packet_id == "packet:2":
            raise RuntimeError("provider timeout")
        if packet_id == "packet:3":
            return {
                "status": "interpret",
                "proposal": proposal() | {"decision": "interpret"},
            }
        return {"status": "decline"}

    monkeypatch.setattr(MODULE, "ThreadPoolExecutor", FakeExecutor)
    monkeypatch.setattr(MODULE, "infer_packet", fake_infer_packet)

    result = infer_packets(
        "/tmp/copilot",
        [
            packet(packet_id="packet:1"),
            packet(packet_id="packet:2"),
            packet(packet_id="packet:3"),
        ],
        repo_key="openclaw",
        workers=2,
    )

    assert observed == {
        "max_workers": 2,
        "thread_name_prefix": "m5-openclaw",
    }
    assert result["packet_count"] == 3
    assert result["worker_count"] == 2
    assert result["invoke_timeout_seconds"] == 600
    assert result["interpreted_count"] == 1
    assert result["declined_count"] == 1
    assert result["error_count"] == 1
    assert list(result["results"]) == ["packet:1", "packet:3"]
    assert result["errors"] == [
        {
            "candidate_evidence_packet_id": "packet:2",
            "error": "provider timeout",
        }
    ]


def test_infer_packets_rejects_unbounded_or_duplicate_work(monkeypatch):
    monkeypatch.setattr(MODULE, "infer_packet", lambda *_args: {"status": "decline"})

    with pytest.raises(ValueError, match="workers must be between 1 and 2"):
        infer_packets(
            "/tmp/copilot",
            [packet()],
            repo_key="openbot",
            workers=3,
        )

    with pytest.raises(RuntimeError, match="duplicated"):
        infer_packets(
            "/tmp/copilot",
            [packet(), packet()],
            repo_key="openbot",
            workers=1,
        )
