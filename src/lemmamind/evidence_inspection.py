"""M4 executable inspection of deterministic evidence at its retained source location.

The deterministic extractors already emit source locators. M4 makes those
locators executable: an EvidenceFact or SourceAssertion can be traced through its
Artifact/CaptureManifest/SourceRevision to locally retained bytes, and its locator
is resolved to an exact text span, structured value, or explicitly identified
derivation substrate.

Inspection never refetches the provider and never upgrades evidence into an
interpretation. Stable semantic locators used by some canonical snapshots (for
example workflow job IDs or Git-tree entry paths) are resolved to the concrete
array index in the retained JSON document before returning the inspection.
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Protocol

from .contracts import Artifact, EvidenceFact, PipelineRun, RunType, SourceAssertion
from .objects import ContentAddressedFileStore
from .revision_capture import CaptureReconstructionService


class EvidenceInspectionError(RuntimeError):
    """A durable evidence locator cannot be resolved against retained source state."""


class InspectionLocationKind(StrEnum):
    ARTIFACT_METADATA = "artifact_metadata"
    TEXT_LINES = "text_lines"
    TEXT_RANGE = "text_range"
    STRUCTURED_VALUE = "structured_value"
    DERIVED_STRUCTURE = "derived_structure"


@dataclass(frozen=True)
class EvidenceInspection:
    record_type: str
    record_id: str
    artifact_id: str
    capture_id: str
    source_revision_id: str
    requested_locator: str
    resolved_locator: str
    location_kind: InspectionLocationKind
    evidence_value: Any
    source_value: Any | None = None
    source_text: str | None = None


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...


_LINE_RANGE = re.compile(r"^:L(?P<start>\d+)-L(?P<end>\d+)(?:#.*)?$")
_COLUMN_RANGE = re.compile(
    r"^:L(?P<start_line>\d+):C(?P<start_col>\d+)"
    r"-L(?P<end_line>\d+):C(?P<end_col>\d+)(?:#.*)?$"
)
_JSON_MEDIA_TYPES = {
    "application/json",
    "application/vnd.lemmamind.git-tree+json",
    "application/vnd.lemmamind.git-commit+json",
    "application/vnd.lemmamind.github-issue+json",
    "application/vnd.lemmamind.github-pull+json",
    "application/vnd.lemmamind.github-issue-events+json",
    "application/vnd.lemmamind.github-workflow-run+json",
    "application/vnd.lemmamind.github-repository-metadata+json",
}


class EvidenceInspectionService:
    """Resolve persisted deterministic evidence to exact retained source material."""

    def __init__(self, store: ContractStore, object_store: ContentAddressedFileStore) -> None:
        self.store = store
        self.object_store = object_store
        self.reconstruction = CaptureReconstructionService(store, object_store)

    def inspect_fact(self, evidence_id: str) -> EvidenceInspection:
        record = self.store.get(EvidenceFact, evidence_id)
        if record is None:
            raise EvidenceInspectionError(f"unknown EvidenceFact: {evidence_id}")
        return self._inspect(record)

    def inspect_assertion(self, assertion_id: str) -> EvidenceInspection:
        record = self.store.get(SourceAssertion, assertion_id)
        if record is None:
            raise EvidenceInspectionError(f"unknown SourceAssertion: {assertion_id}")
        return self._inspect(record)

    def audit_all(self) -> tuple[EvidenceInspection, ...]:
        """Resolve every deterministic evidence record in the store or fail closed."""

        records = [*self.store.list(EvidenceFact), *self.store.list(SourceAssertion)]
        records.sort(key=lambda item: (type(item).__name__, item.record_id))
        return tuple(self._inspect(record) for record in records)

    def _inspect(self, record: EvidenceFact | SourceAssertion) -> EvidenceInspection:
        run = self.store.get(PipelineRun, record.run_id)
        if run is None:
            raise EvidenceInspectionError(
                f"evidence record references missing PipelineRun: {record.run_id}"
            )
        if run.run_type is not RunType.EXTRACTION:
            raise EvidenceInspectionError(
                f"evidence producer must be an extraction run: {record.run_id}"
            )

        artifact = self.store.get(Artifact, record.artifact_id)
        if artifact is None:
            raise EvidenceInspectionError(
                f"evidence record references missing Artifact: {record.artifact_id}"
            )
        try:
            capture = self.reconstruction.reconstruct(artifact.capture_id)
        except Exception as exc:
            raise EvidenceInspectionError(
                f"cannot reconstruct evidence capture {artifact.capture_id}: {exc}"
            ) from exc
        reconstructed = next(
            (item for item in capture.artifacts if item.artifact_id == artifact.artifact_id),
            None,
        )
        if reconstructed is None or reconstructed.data is None:
            raise EvidenceInspectionError(
                f"evidence Artifact is not locally reconstructable: {artifact.artifact_id}"
            )

        evidence_value = record.raw_value if isinstance(record, EvidenceFact) else record.statement
        location = self._resolve_locator(artifact, reconstructed.data, record.locator)
        return EvidenceInspection(
            record_type=type(record).__name__,
            record_id=record.record_id,
            artifact_id=artifact.artifact_id,
            capture_id=artifact.capture_id,
            source_revision_id=capture.revision.source_revision_id,
            requested_locator=record.locator,
            resolved_locator=location[0],
            location_kind=location[1],
            evidence_value=evidence_value,
            source_value=location[2],
            source_text=location[3],
        )

    def _resolve_locator(
        self,
        artifact: Artifact,
        data: bytes,
        locator: str,
    ) -> tuple[str, InspectionLocationKind, Any | None, str | None]:
        root = artifact.source_locator
        if not locator.startswith(root):
            raise EvidenceInspectionError(
                f"locator is not anchored to Artifact.source_locator: {locator!r} vs {root!r}"
            )
        suffix = locator[len(root) :]

        if suffix.startswith("#$path."):
            return self._resolve_path_metadata(artifact, suffix[len("#$path.") :])

        column_match = _COLUMN_RANGE.fullmatch(suffix)
        if column_match is not None:
            text = self._slice_byte_range(
                data,
                int(column_match.group("start_line")),
                int(column_match.group("start_col")),
                int(column_match.group("end_line")),
                int(column_match.group("end_col")),
            )
            resolved = (
                f"{root}:L{column_match.group('start_line')}:C{column_match.group('start_col')}"
                f"-L{column_match.group('end_line')}:C{column_match.group('end_col')}"
            )
            return resolved, InspectionLocationKind.TEXT_RANGE, None, text

        line_match = _LINE_RANGE.fullmatch(suffix)
        if line_match is not None:
            start = int(line_match.group("start"))
            end = int(line_match.group("end"))
            text = self._slice_lines(data, start, end)
            resolved = f"{root}:L{start}-L{end}"
            return resolved, InspectionLocationKind.TEXT_LINES, None, text

        if not suffix.startswith("#"):
            raise EvidenceInspectionError(f"unsupported evidence locator syntax: {locator}")
        fragment = suffix[1:]

        if fragment == "$manifest.kind":
            return (
                f"artifact:{artifact.artifact_id}#source_locator",
                InspectionLocationKind.ARTIFACT_METADATA,
                PurePosixPath(artifact.source_locator).name,
                None,
            )

        if artifact.media_type == "application/toml" or PurePosixPath(root).name.lower() == "pyproject.toml":
            return self._resolve_toml(artifact, data, fragment)

        if artifact.media_type in _JSON_MEDIA_TYPES or artifact.media_type.endswith("+json"):
            return self._resolve_json(artifact, data, fragment)

        raise EvidenceInspectionError(
            f"unsupported locator/media type combination: {locator} ({artifact.media_type})"
        )

    @staticmethod
    def _resolve_path_metadata(
        artifact: Artifact,
        key: str,
    ) -> tuple[str, InspectionLocationKind, Any, None]:
        path = PurePosixPath(artifact.source_locator)
        parts = path.parts
        values: dict[str, Any] = {
            "basename": path.name,
            "suffix": path.suffix.lower(),
            "path_depth": len(parts),
            "top_level_entry": parts[0],
        }
        if key not in values:
            raise EvidenceInspectionError(f"unsupported artifact path locator field: {key}")
        return (
            f"artifact:{artifact.artifact_id}#source_locator",
            InspectionLocationKind.ARTIFACT_METADATA,
            values[key],
            None,
        )

    def _resolve_toml(
        self,
        artifact: Artifact,
        data: bytes,
        fragment: str,
    ) -> tuple[str, InspectionLocationKind, Any, None]:
        try:
            document = tomllib.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise EvidenceInspectionError("retained TOML artifact cannot be parsed") from exc
        if not fragment:
            raise EvidenceInspectionError("empty TOML locator")
        tokens = fragment.split(".")
        current: Any = document
        for token in tokens:
            if not isinstance(current, dict) or token not in current:
                raise EvidenceInspectionError(
                    f"TOML locator does not resolve in retained artifact: {fragment}"
                )
            current = current[token]
        return (
            f"{artifact.source_locator}#{fragment}",
            InspectionLocationKind.STRUCTURED_VALUE,
            current,
            None,
        )

    def _resolve_json(
        self,
        artifact: Artifact,
        data: bytes,
        fragment: str,
    ) -> tuple[str, InspectionLocationKind, Any, None]:
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceInspectionError("retained JSON artifact cannot be parsed") from exc

        pointer = "" if fragment == "" else (fragment if fragment.startswith("/") else f"/{fragment}")
        tokens = self._decode_pointer(pointer)
        kind = InspectionLocationKind.STRUCTURED_VALUE

        # Canonical repository metadata stores provider fields under /repository,
        # while evidence intentionally presents those fields relative to the
        # $github/repository resource root.
        if artifact.media_type == "application/vnd.lemmamind.github-repository-metadata+json":
            if tokens and tokens[0] != "repository":
                tokens.insert(0, "repository")

        # A small set of counts/lists is a deterministic derivation over an exact
        # retained container rather than a literal JSON leaf. Resolve to that
        # substrate and label it honestly.
        if artifact.media_type == "application/vnd.lemmamind.git-tree+json":
            if tokens == ["entry_count"] or tokens == ["entry_paths"]:
                tokens = ["entries"]
                kind = InspectionLocationKind.DERIVED_STRUCTURE
        elif artifact.media_type == "application/vnd.lemmamind.git-commit+json":
            if tokens == ["parent_count"]:
                tokens = ["parents"]
                kind = InspectionLocationKind.DERIVED_STRUCTURE
        elif artifact.media_type == "application/vnd.lemmamind.github-issue-events+json":
            if tokens == ["event_count"]:
                tokens = ["events"]
                kind = InspectionLocationKind.DERIVED_STRUCTURE

        current = document
        resolved_tokens: list[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if isinstance(current, dict):
                if token not in current:
                    raise EvidenceInspectionError(
                        f"JSON locator token {token!r} does not resolve in {artifact.source_locator}"
                    )
                current = current[token]
                resolved_tokens.append(token)
                index += 1
                continue
            if isinstance(current, list):
                selected_index = self._resolve_list_index(
                    artifact.media_type,
                    resolved_tokens,
                    current,
                    token,
                )
                if selected_index < 0 or selected_index >= len(current):
                    raise EvidenceInspectionError(
                        f"JSON array locator index does not resolve: {token!r}"
                    )
                current = current[selected_index]
                resolved_tokens.append(str(selected_index))
                index += 1
                continue
            raise EvidenceInspectionError(
                f"JSON locator traverses through scalar before completion: {fragment}"
            )

        resolved_pointer = "/" + "/".join(self._escape_pointer(token) for token in resolved_tokens)
        if not resolved_tokens:
            resolved_pointer = ""
        return (
            f"{artifact.source_locator}#{resolved_pointer}",
            kind,
            current,
            None,
        )

    @staticmethod
    def _resolve_list_index(
        media_type: str,
        resolved_tokens: list[str],
        values: list[Any],
        token: str,
    ) -> int:
        # Git-tree evidence uses a stable root-entry path rather than array order.
        if media_type == "application/vnd.lemmamind.git-tree+json" and resolved_tokens == ["entries"]:
            for idx, item in enumerate(values):
                if isinstance(item, dict) and str(item.get("path")) == token:
                    return idx
            raise EvidenceInspectionError(f"Git-tree entry path not found: {token}")

        # Workflow locators use provider IDs/step numbers so evidence addresses a
        # stable provider identity even if canonical array order changes.
        if media_type == "application/vnd.lemmamind.github-workflow-run+json":
            parent = resolved_tokens[-1] if resolved_tokens else ""
            key = {"jobs": "id", "artifacts": "id", "steps": "number"}.get(parent)
            if key is not None:
                for idx, item in enumerate(values):
                    if isinstance(item, dict) and str(item.get(key)) == token:
                        return idx
                raise EvidenceInspectionError(
                    f"workflow {parent} semantic key not found: {token}"
                )

        if not token.isdigit():
            raise EvidenceInspectionError(f"JSON array locator requires numeric index: {token}")
        return int(token)

    @staticmethod
    def _decode_pointer(pointer: str) -> list[str]:
        if pointer == "":
            return []
        if not pointer.startswith("/"):
            raise EvidenceInspectionError(f"invalid JSON pointer: {pointer}")
        return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]

    @staticmethod
    def _escape_pointer(token: str) -> str:
        return token.replace("~", "~0").replace("/", "~1")

    @staticmethod
    def _slice_lines(data: bytes, start: int, end: int) -> str:
        if start < 1 or end < start:
            raise EvidenceInspectionError("invalid line range")
        lines = data.splitlines(keepends=True)
        if end > len(lines):
            raise EvidenceInspectionError(
                f"line locator exceeds retained artifact: L{start}-L{end}"
            )
        try:
            return b"".join(lines[start - 1 : end]).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceInspectionError("text locator targets non-UTF-8 bytes") from exc

    @staticmethod
    def _slice_byte_range(
        data: bytes,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
    ) -> str:
        if start_line < 1 or end_line < start_line or start_col < 0 or end_col < 0:
            raise EvidenceInspectionError("invalid line/column range")
        lines = data.splitlines(keepends=True)
        if end_line > len(lines):
            raise EvidenceInspectionError("line/column locator exceeds retained artifact")
        start_bytes = lines[start_line - 1]
        end_bytes = lines[end_line - 1]
        if start_col > len(start_bytes) or end_col > len(end_bytes):
            raise EvidenceInspectionError("column locator exceeds retained source line")
        if start_line == end_line:
            selected = start_bytes[start_col:end_col]
        else:
            selected = b"".join(
                [
                    start_bytes[start_col:],
                    *lines[start_line:end_line - 1],
                    end_bytes[:end_col],
                ]
            )
        try:
            return selected.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceInspectionError(
                "line/column locator does not align to UTF-8 byte boundaries"
            ) from exc
