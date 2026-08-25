import pytest

from lemmamind.contracts import Artifact
from lemmamind.extraction import AssertionSpec, FactSpec
from lemmamind.typescript_ast import (
    TypeScriptAstExtractionError,
    TypeScriptAstExtractor,
    typescript_aware_extractors,
)

DIGEST = "sha256:" + "b" * 64


def artifact(path: str = "demo.ts") -> Artifact:
    return Artifact(
        artifact_id="artifact:typescript",
        capture_id="capture:typescript",
        source_locator=path,
        content_hash=DIGEST,
        media_type="text/typescript",
    )


def fact_values(records):
    return [
        record.normalized_value
        for record in records
        if isinstance(record, FactSpec)
    ]


def test_extracts_comments_calls_if_throw_and_declarations() -> None:
    source = b'''/**
 * A skill is an instruction and confers nothing.
 * The run-time offer is always the intersection of the two.
 */
export function validateTenantPackage(skillSlugs: Set<string>, slug: string) {
  const tools = skill.tools.map((ref) => ref);
  transaction.insert(skillTools).values(tools);
  transaction.insert(pluginGrants).values(grants);
  if (!skillSlugs.has(slug)) {
    throw new Error(`skill ${slug} is not shipped`);
  }
}
'''
    records = TypeScriptAstExtractor().extract(artifact(), source)
    facts = fact_values(records)

    functions = [item for item in facts if item["kind"] == "function"]
    calls = [item for item in facts if item["kind"] == "call"]
    ifs = [item for item in facts if item["kind"] == "if"]
    throws = [item for item in facts if item["kind"] == "throw"]
    declarations = [item for item in facts if item["kind"] == "declaration"]

    assert any(item["name"] == "validateTenantPackage" for item in functions)
    assert any("transaction.insert(skillTools).values" in str(item["callee"]) for item in calls)
    assert any("transaction.insert(pluginGrants).values" in str(item["callee"]) for item in calls)
    assert any("!skillSlugs.has(slug)" in str(item["condition"]) for item in ifs)
    assert any("not shipped" in item["text"] for item in throws)
    assert any(item["name"] == "tools" for item in declarations)

    comments = [item for item in records if isinstance(item, AssertionSpec)]
    assert len(comments) == 1
    assert comments[0].extractor_name == "typescript-comment"
    assert "instruction and confers nothing" in comments[0].statement
    assert "run-time offer is always the intersection" in comments[0].statement


def test_source_ranges_are_one_based_lines_and_zero_based_columns() -> None:
    records = TypeScriptAstExtractor().extract(
        artifact("server/example.ts"),
        b"function f() {\n  return g(1);\n}\n",
    )
    facts = [item for item in records if isinstance(item, FactSpec)]
    function = next(item for item in facts if item.normalized_value["kind"] == "function")
    call = next(item for item in facts if item.normalized_value["kind"] == "call")

    assert function.locator.startswith("server/example.ts:L1:C0-L3:C1#typescript/function")
    assert call.locator.startswith("server/example.ts:L2:C9-L2:C13#typescript/call")
    assert call.normalized_value["callee"] == "g"
    assert call.normalized_value["arguments"] == ["1"]


def test_invalid_typescript_fails_closed() -> None:
    with pytest.raises(TypeScriptAstExtractionError, match="invalid TypeScript syntax"):
        TypeScriptAstExtractor().extract(artifact(), b"function broken( {\n")


def test_tsx_and_non_typescript_support() -> None:
    extractor = TypeScriptAstExtractor()
    assert extractor.supports(artifact("component.tsx")) is True
    assert extractor.supports(artifact("module.ts")) is True
    assert extractor.supports(artifact("README.md")) is False


def test_typescript_aware_set_keeps_python_and_adds_typescript() -> None:
    names = [extractor.name for extractor in typescript_aware_extractors()]
    assert "python-ast" in names
    assert names[-1] == "typescript-ast"
