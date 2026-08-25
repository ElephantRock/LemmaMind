"""Deterministic Python syntax evidence for captured ``.py`` artifacts.

The extractor records source structure only. It does not evaluate code, resolve
imports, execute expressions, or infer behavioral meaning from syntax.
"""
from __future__ import annotations

import ast
from pathlib import PurePosixPath

from .contracts import Artifact
from .extraction import (
    ArtifactExtractor,
    ArtifactPathExtractor,
    AssertionSpec,
    FactSpec,
    MarkdownAssertionExtractor,
    MarkdownListAssertionExtractor,
    PackageJsonExtractor,
    PyProjectExtractor,
)


class PythonAstExtractionError(RuntimeError):
    """Captured Python source cannot be parsed deterministically."""


class PythonAstExtractor:
    """Emit source-addressed Python AST facts and authored docstrings."""

    name = "python-ast"
    version = "1"

    def supports(self, artifact: Artifact) -> bool:
        return PurePosixPath(artifact.source_locator).suffix.lower() == ".py"

    def extract(self, artifact: Artifact, data: bytes) -> tuple[FactSpec | AssertionSpec, ...]:
        try:
            source = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PythonAstExtractionError(
                f"Python source is not UTF-8: {artifact.source_locator}"
            ) from exc
        try:
            tree = ast.parse(source, filename=artifact.source_locator, type_comments=True)
        except SyntaxError as exc:
            raise PythonAstExtractionError(
                f"invalid Python syntax: {artifact.source_locator}:{exc.lineno}:{exc.offset}"
            ) from exc

        visitor = _PythonFactVisitor(artifact.source_locator)
        visitor.visit(tree)
        return tuple(visitor.records)


class _PythonFactVisitor(ast.NodeVisitor):
    def __init__(self, source_locator: str) -> None:
        self.source_locator = source_locator
        self.scope: list[str] = []
        self.records: list[FactSpec | AssertionSpec] = []

    def visit_Module(self, node: ast.Module) -> None:  # noqa: N802
        self._emit_docstring(node, scope="<module>")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        parent_scope = self._scope_name()
        qualified_name = self._qualify(node.name)
        self._fact(
            node,
            "class",
            {
                "kind": "class",
                "name": node.name,
                "qualified_name": qualified_name,
                "scope": parent_scope,
                "bases": [self._unparse(item) for item in node.bases],
                "decorators": [self._unparse(item) for item in node.decorator_list],
            },
        )
        self.scope.append(node.name)
        self._emit_docstring(node, scope=qualified_name)
        for item in node.body:
            self.visit(item)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node, is_async=True)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool
    ) -> None:
        parent_scope = self._scope_name()
        qualified_name = self._qualify(node.name)
        self._fact(
            node,
            "function",
            {
                "kind": "function",
                "name": node.name,
                "qualified_name": qualified_name,
                "scope": parent_scope,
                "async": is_async,
                "decorators": [self._unparse(item) for item in node.decorator_list],
                "parameters": [arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)],
            },
        )
        self.scope.append(node.name)
        self._emit_docstring(node, scope=qualified_name)
        for item in node.body:
            self.visit(item)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        keywords: dict[str, str] = {}
        starred_keywords: list[str] = []
        for keyword in node.keywords:
            if keyword.arg is None:
                starred_keywords.append(self._unparse(keyword.value))
            else:
                keywords[keyword.arg] = self._unparse(keyword.value)
        value = {
            "kind": "call",
            "scope": self._scope_name(),
            "callee": self._call_name(node.func),
            "args": [self._unparse(item) for item in node.args],
            "keywords": dict(sorted(keywords.items())),
        }
        if starred_keywords:
            value["starred_keywords"] = starred_keywords
        self._fact(node, "call", value)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        value = {
            "kind": "assignment",
            "scope": self._scope_name(),
            "targets": [self._unparse(item) for item in node.targets],
            "value": self._unparse(node.value),
        }
        if isinstance(node.value, ast.Call):
            value["value_call"] = self._call_name(node.value.func)
            value["value_call_keywords"] = {
                keyword.arg: self._unparse(keyword.value)
                for keyword in node.value.keywords
                if keyword.arg is not None
            }
        self._fact(node, "assignment", value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        value = {
            "kind": "assignment",
            "scope": self._scope_name(),
            "targets": [self._unparse(node.target)],
            "annotation": self._unparse(node.annotation),
            "value": None if node.value is None else self._unparse(node.value),
        }
        if isinstance(node.value, ast.Call):
            value["value_call"] = self._call_name(node.value.func)
            value["value_call_keywords"] = {
                keyword.arg: self._unparse(keyword.value)
                for keyword in node.value.keywords
                if keyword.arg is not None
            }
        self._fact(node, "assignment", value)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
        self._fact(
            node,
            "assert",
            {
                "kind": "assert",
                "scope": self._scope_name(),
                "expression": self._unparse(node.test),
                "message": None if node.msg is None else self._unparse(node.msg),
            },
        )
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        self._fact(
            node,
            "try",
            {
                "kind": "try",
                "scope": self._scope_name(),
                "handlers": [
                    None if handler.type is None else self._unparse(handler.type)
                    for handler in node.handlers
                ],
                "has_else": bool(node.orelse),
                "has_finally": bool(node.finalbody),
            },
        )
        self.generic_visit(node)

    def _emit_docstring(self, node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, *, scope: str) -> None:
        body = getattr(node, "body", ())
        if not body:
            return
        first = body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            return
        self.records.append(
            AssertionSpec(
                locator=self._line_locator(first),
                statement=first.value.value,
                extractor_name="python-docstring",
                extractor_version="1",
            )
        )

    def _fact(self, node: ast.AST, kind: str, normalized: dict[str, object]) -> None:
        value = {
            **normalized,
            "line": getattr(node, "lineno", None),
            "column": getattr(node, "col_offset", None),
            "end_line": getattr(node, "end_lineno", None),
            "end_column": getattr(node, "end_col_offset", None),
        }
        self.records.append(
            FactSpec(
                locator=f"{self._range_locator(node)}#python/{kind}",
                raw_value=value,
                normalized_value=value,
                extractor_name="python-ast",
                extractor_version="1",
            )
        )

    def _scope_name(self) -> str:
        return ".".join(self.scope) if self.scope else "<module>"

    def _qualify(self, name: str) -> str:
        return ".".join((*self.scope, name)) if self.scope else name

    def _range_locator(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", 1)
        column = getattr(node, "col_offset", 0)
        end_line = getattr(node, "end_lineno", line)
        end_column = getattr(node, "end_col_offset", column)
        return (
            f"{self.source_locator}:L{line}:C{column}-L{end_line}:C{end_column}"
        )

    def _line_locator(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", line)
        return f"{self.source_locator}:L{line}-L{end_line}"

    @staticmethod
    def _unparse(node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return ast.dump(node, annotate_fields=True, include_attributes=False)

    @classmethod
    def _call_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = cls._call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        if isinstance(node, ast.Call):
            base = cls._call_name(node.func)
            return f"{base}()" if base else "<call>()"
        if isinstance(node, ast.Subscript):
            base = cls._call_name(node.value)
            return f"{base}[]" if base else "<subscript>"
        return cls._unparse(node)


def python_aware_extractors() -> tuple[ArtifactExtractor, ...]:
    """Current deterministic extractor set plus Python syntax evidence."""

    return (
        ArtifactPathExtractor(),
        PyProjectExtractor(),
        PackageJsonExtractor(),
        MarkdownAssertionExtractor(),
        MarkdownListAssertionExtractor(),
        PythonAstExtractor(),
    )
