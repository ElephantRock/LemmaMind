from datetime import datetime, timezone

from lemmamind.contracts import Artifact, EvidenceFact, PipelineRun, RunType
from lemmamind.extraction import FactSpec, ExtractionResult
from lemmamind.pilot_coverage_v2 import _assess_python_ast
from lemmamind.python_ast import PythonAstExtractor

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def extracted(source: bytes, path: str = "local.py") -> ExtractionResult:
    artifact = Artifact(
        artifact_id="artifact:python",
        capture_id="capture:python",
        source_locator=path,
        content_hash=DIGEST,
        media_type="text/x-python",
    )
    specs = [
        item for item in PythonAstExtractor().extract(artifact, source)
        if isinstance(item, FactSpec)
    ]
    run = PipelineRun(
        run_id="run:python",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="deterministic-evidence.python-ast.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST,
        outputs_hash=DIGEST,
    )
    facts = tuple(
        EvidenceFact(
            evidence_id=f"fact:{index}",
            artifact_id=artifact.artifact_id,
            locator=spec.locator,
            raw_value=spec.raw_value,
            normalized_value=spec.normalized_value,
            extractor_name=spec.extractor_name,
            extractor_version=spec.extractor_version,
            run_id=run.run_id,
        )
        for index, spec in enumerate(specs, start=1)
    )
    return ExtractionResult(artifact.capture_id, facts, (), run)


def requirement():
    return {
        "evidence_id": "demo-python",
        "evidence_type": "EvidenceFact",
        "check": {
            "kind": "python_ast_contains",
            "artifact": "local.py",
            "functions": ["Worker.stop", "Worker.stop.sweep"],
            "assignments": [
                {
                    "scope": "Worker.stop",
                    "target": "descendants",
                    "value_call": "psutil.Process().children",
                    "keywords": {"recursive": "True"},
                }
            ],
            "calls": [
                {"scope": "Worker.stop.sweep", "callee": "child.kill"},
                {
                    "scope": "Worker.stop",
                    "callee": "os.killpg",
                    "args_contains": ["signal.SIGTERM"],
                },
            ],
            "assertions": [
                {"scope": "Worker.stop", "expression_contains": "descendants"}
            ],
        },
        "needed_capability_if_missing": "python-ast-structural-facts",
    }


def test_python_ast_requirement_recovers_source_structure() -> None:
    result = _assess_python_ast(
        requirement(),
        extracted(
            b'''class Worker:\n    def stop(self, proc):\n        descendants = psutil.Process(proc.pid).children(recursive=True)\n        def sweep():\n            for child in descendants:\n                child.kill()\n        os.killpg(proc.pid, signal.SIGTERM)\n        assert descendants\n'''
        ),
    )

    assert result.status == "recovered"
    assert result.missing_fragments == ()
    assert len(result.matched_locators) >= 6


def test_python_ast_requirement_reports_precise_missing_structure() -> None:
    result = _assess_python_ast(
        requirement(),
        extracted(b"class Worker:\n    def stop(self, proc):\n        pass\n"),
    )

    assert result.status == "gap"
    assert "function:Worker.stop.sweep" in result.missing_fragments
    assert any(item.startswith("assignment:Worker.stop:descendants") for item in result.missing_fragments)
    assert result.needed_capability == "python-ast-structural-facts"
