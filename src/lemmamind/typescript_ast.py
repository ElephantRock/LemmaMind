"""Deterministic TypeScript/TSX syntax evidence for captured source artifacts.

Tree-sitter is used only as a concrete-syntax parser. The extractor does not
execute code, resolve imports, run a type checker, evaluate expressions, or
assign behavioral meaning to syntax. Authored comments remain SourceAssertion;
parser-derived structure remains EvidenceFact.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from tree_sitter import Language, Node, Parser
import tree_sitter_typescript as tsgrammar

from .contracts import Artifact
from .extraction import ArtifactExtractor, AssertionSpec, FactSpec
from .python_ast import python_aware_extractors


_TYPESCRIPT_LANGUAGE = Language(tsgrammar.language_typescript())
_TSX_LANGUAGE = Language(tsgrammar.language_tsx())


class TypeScriptAstExtractionError(RuntimeError):
    """Captured TypeScript source cannot be parsed deterministically."""


class TypeScriptAstExtractor:
    """Emit exact TypeScript syntax facts and authored comment assertions."""

    name = "typescript-ast"
    version = "1"

    _FACT_NODE_TYPES = {
        "function_declaration": "function",
        "method_definition": "function",
        "arrow_function": "function",
        "function_expression": "function",
        "call_expression": "call",
        "if_statement": "if",
        "throw_statement": "throw",
        "variable_declarator": "declaration",
        "type_alias_declaration": "type_alias",
        "interface_declaration": "interface",
    }

    def supports(self, artifact: Artifact) -> bool:
        return PurePosixPath(artifact.source_locator).suffix.lower() in {".ts", ".tsx"}

    def extract(self, artifact: Artifact, data: bytes) -> tuple[FactSpec | AssertionSpec, ...]:
        try:
            source = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TypeScriptAstExtractionError(
                f"TypeScript source is not UTF-8: {artifact.source_locator}"
            ) from exc

        suffix = PurePosixPath(artifact.source_locator).suffix.lower()
        parser = Parser(_TSX_LANGUAGE if suffix == ".tsx" else _TYPESCRIPT_LANGUAGE)
        tree = parser.parse(data)
        if tree.root_node.has_error:
            raise TypeScriptAstExtractionError(
                f"invalid TypeScript syntax: {artifact.source_locator}"
            )

        records: list[FactSpec | AssertionSpec] = []
        self._walk(tree.root_node, artifact.source_locator, data, records)
        return tuple(records)

    def _walk(
        self,
        node: Node,
        source_locator: str,
        data: bytes,
        records: list[FactSpec | AssertionSpec],
    ) -> None:
        if node.type == "comment":
            statement = self._clean_comment(self._text(node, data))
            if statement:
                records.append(
                    AssertionSpec(
                        locator=self._line_locator(source_locator, node),
                        statement=statement,
                        extractor_name="typescript-comment",
                        extractor_version="1",
                    )
                )
        else:
            kind = self._FACT_NODE_TYPES.get(node.type)
            if kind is not None:
                value = self._normalized_node(kind, node, data)
                records.append(
                    FactSpec(
                        locator=f"{self._range_locator(source_locator, node)}#typescript/{kind}",
                        raw_value=value,
                        normalized_value=value,
                        extractor_name=self.name,
                        extractor_version=self.version,
                    )
                )

        for child in node.children:
            self._walk(child, source_locator, data, records)

    def _normalized_node(self, kind: str, node: Node, data: bytes) -> dict[str, object]:
        value: dict[str, object] = {
            "kind": kind,
            "node_type": node.type,
            "text": self._text(node, data),
            "line": node.start_point.row + 1,
            "column": node.start_point.column,
            "end_line": node.end_point.row + 1,
            "end_column": node.end_point.column,
        }

        if kind == "function":
            name = node.child_by_field_name("name")
            value["name"] = None if name is None else self._text(name, data)
        elif kind == "call":
            function = node.child_by_field_name("function")
            arguments = node.child_by_field_name("arguments")
            value["callee"] = None if function is None else self._text(function, data)
            value["arguments"] = (
                []
                if arguments is None
                else [self._text(child, data) for child in arguments.named_children]
            )
        elif kind == "if":
            condition = node.child_by_field_name("condition")
            value["condition"] = None if condition is None else self._text(condition, data)
        elif kind == "throw":
            value["expression"] = (
                self._text(node.named_children[0], data) if node.named_children else None
            )
        elif kind == "declaration":
            name = node.child_by_field_name("name")
            initializer = node.child_by_field_name("value")
            value["name"] = None if name is None else self._text(name, data)
            value["value"] = None if initializer is None else self._text(initializer, data)
        elif kind in {"type_alias", "interface"}:
            name = node.child_by_field_name("name")
            value["name"] = None if name is None else self._text(name, data)

        return value

    @staticmethod
    def _text(node: Node, data: bytes) -> str:
        return data[node.start_byte : node.end_byte].decode("utf-8")

    @staticmethod
    def _range_locator(source_locator: str, node: Node) -> str:
        return (
            f"{source_locator}:L{node.start_point.row + 1}:C{node.start_point.column}"
            f"-L{node.end_point.row + 1}:C{node.end_point.column}"
        )

    @staticmethod
    def _line_locator(source_locator: str, node: Node) -> str:
        return (
            f"{source_locator}:L{node.start_point.row + 1}-L{node.end_point.row + 1}"
        )

    @staticmethod
    def _clean_comment(raw: str) -> str:
        text = raw.strip()
        if text.startswith("//"):
            return text[2:].strip()
        if text.startswith("/*") and text.endswith("*/"):
            body = text[2:-2]
            cleaned: list[str] = []
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("*"):
                    stripped = stripped[1:].strip()
                if stripped:
                    cleaned.append(stripped)
            return " ".join(cleaned)
        return text


def typescript_aware_extractors() -> tuple[ArtifactExtractor, ...]:
    """Current deterministic extractor set plus TypeScript syntax evidence."""

    return (*python_aware_extractors(), TypeScriptAstExtractor())
