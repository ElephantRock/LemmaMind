import pytest

from lemmamind.contracts import Artifact
from lemmamind.extraction import AssertionSpec, FactSpec
from lemmamind.python_ast import PythonAstExtractionError, PythonAstExtractor

DIGEST = "sha256:" + "a" * 64


def artifact(path: str = "demo.py") -> Artifact:
    return Artifact(
        artifact_id="artifact:python",
        capture_id="capture:python",
        source_locator=path,
        content_hash=DIGEST,
        media_type="text/x-python",
    )


def fact_values(records):
    return [
        record.normalized_value
        for record in records
        if isinstance(record, FactSpec)
    ]


def test_extracts_scoped_functions_calls_assignments_and_asserts() -> None:
    source = b'''class Worker:
    """Runs work without claiming that it succeeds."""

    def stop(self, proc):
        descendants = psutil.Process(proc.pid).children(recursive=True)

        def sweep():
            for child in descendants:
                child.kill()

        os.killpg(proc.pid, signal.SIGTERM)
        sweep()
        assert descendants
'''
    records = PythonAstExtractor().extract(artifact(), source)
    facts = fact_values(records)

    functions = [item for item in facts if item["kind"] == "function"]
    calls = [item for item in facts if item["kind"] == "call"]
    assignments = [item for item in facts if item["kind"] == "assignment"]
    asserts = [item for item in facts if item["kind"] == "assert"]

    assert {item["qualified_name"] for item in functions} == {
        "Worker.stop",
        "Worker.stop.sweep",
    }
    descendant_assignment = next(
        item for item in assignments if "descendants" in item["targets"]
    )
    assert descendant_assignment["scope"] == "Worker.stop"
    assert descendant_assignment["value_call"] == "psutil.Process().children"
    assert descendant_assignment["value_call_keywords"] == {"recursive": "True"}

    assert any(
        item["callee"] == "child.kill" and item["scope"] == "Worker.stop.sweep"
        for item in calls
    )
    assert any(
        item["callee"] == "os.killpg"
        and item["scope"] == "Worker.stop"
        and "signal.SIGTERM" in item["args"]
        for item in calls
    )
    assert asserts[0]["scope"] == "Worker.stop"
    assert asserts[0]["expression"] == "descendants"

    docstrings = [item for item in records if isinstance(item, AssertionSpec)]
    assert len(docstrings) == 1
    assert docstrings[0].extractor_name == "python-docstring"
    assert "without claiming" in docstrings[0].statement


def test_source_ranges_are_exact_and_stable() -> None:
    records = PythonAstExtractor().extract(
        artifact("pkg/sample.py"),
        b"def f():\n    return g(x=1)\n",
    )
    facts = [item for item in records if isinstance(item, FactSpec)]

    function = next(item for item in facts if item.normalized_value["kind"] == "function")
    call = next(item for item in facts if item.normalized_value["kind"] == "call")
    assert function.locator.startswith("pkg/sample.py:L1:C0-L2:")
    assert call.locator.startswith("pkg/sample.py:L2:C11-L2:")
    assert call.normalized_value["keywords"] == {"x": "1"}


def test_invalid_python_fails_closed() -> None:
    with pytest.raises(PythonAstExtractionError, match="invalid Python syntax"):
        PythonAstExtractor().extract(artifact(), b"def broken(:\n    pass\n")


def test_non_python_artifact_is_not_supported() -> None:
    assert PythonAstExtractor().supports(artifact("README.md")) is False
