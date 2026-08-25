"""Deterministic extraction from captured M0 artifacts.

This module deliberately stops at source-addressed EvidenceFact and
SourceAssertion records. It does not infer meaning, classify architecture, call a
model, or promote observations.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Callable, Iterable, Protocol

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
)
from .objects import ContentAddressedFileStore


class ExtractionError(RuntimeError):
    """Captured input cannot be deterministically interpreted under the policy."""


class ArtifactContractMismatch(ExtractionError):
    """Artifact metadata disagrees with its capture manifest."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class FactSpec:
    locator: str
    raw_value: object
    normalized_value: object
    extractor_name: str
    extractor_version: str


@dataclass(frozen=True)
class AssertionSpec:
    locator: str
    statement: str
    extractor_name: str
    extractor_version: str


class ArtifactExtractor(Protocol):
    name: str
    version: str

    def supports(self, artifact: Artifact) -> bool: ...

    def extract(self, artifact: Artifact, data: bytes) -> tuple[FactSpec | AssertionSpec, ...]: ...


class ArtifactPathExtractor:
    """Emit path facts about one captured artifact, not the whole repository."""

    name = "artifact-path"
    version = "1"

    def supports(self, artifact: Artifact) -> bool:
        return True

    def extract(self, artifact: Artifact, data: bytes) -> tuple[FactSpec, ...]:
        del data
        path = PurePosixPath(artifact.source_locator)
        parts = path.parts
        return (
            self._fact(artifact, "basename", path.name),
            self._fact(artifact, "suffix", path.suffix.lower()),
            self._fact(artifact, "path_depth", len(parts)),
            self._fact(artifact, "top_level_entry", parts[0]),
        )

    def _fact(self, artifact: Artifact, key: str, value: object) -> FactSpec:
        return FactSpec(
            locator=f"{artifact.source_locator}#$path.{key}",
            raw_value=value,
            normalized_value=value,
            extractor_name=self.name,
            extractor_version=self.version,
        )


class PyProjectExtractor:
    """Extract a small stable set of facts from ``pyproject.toml``."""

    name = "pyproject"
    version = "1"

    def supports(self, artifact: Artifact) -> bool:
        return PurePosixPath(artifact.source_locator).name.lower() == "pyproject.toml"

    def extract(self, artifact: Artifact, data: bytes) -> tuple[FactSpec, ...]:
        try:
            document = tomllib.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise ExtractionError(f"invalid pyproject.toml: {artifact.source_locator}") from exc

        facts: list[FactSpec] = [
            self._fact(artifact, "$manifest.kind", "pyproject.toml", "pyproject.toml")
        ]
        project = document.get("project")
        if isinstance(project, dict):
            for key in ("name", "version", "requires-python"):
                value = project.get(key)
                if isinstance(value, str):
                    facts.append(self._fact(artifact, f"project.{key}", value, value.strip()))

            dependencies = project.get("dependencies")
            if isinstance(dependencies, list) and all(isinstance(item, str) for item in dependencies):
                facts.append(
                    self._fact(
                        artifact,
                        "project.dependencies",
                        dependencies,
                        sorted(dict.fromkeys(item.strip() for item in dependencies)),
                    )
                )

            optional = project.get("optional-dependencies")
            if isinstance(optional, dict):
                groups = sorted(str(key) for key in optional)
                facts.append(self._fact(artifact, "project.optional-dependencies", groups, groups))

        build_system = document.get("build-system")
        if isinstance(build_system, dict):
            backend = build_system.get("build-backend")
            if isinstance(backend, str):
                facts.append(self._fact(artifact, "build-system.build-backend", backend, backend.strip()))
            requires = build_system.get("requires")
            if isinstance(requires, list) and all(isinstance(item, str) for item in requires):
                facts.append(
                    self._fact(
                        artifact,
                        "build-system.requires",
                        requires,
                        sorted(dict.fromkeys(item.strip() for item in requires)),
                    )
                )
        return tuple(facts)

    def _fact(self, artifact: Artifact, key: str, raw: object, normalized: object) -> FactSpec:
        return FactSpec(
            locator=f"{artifact.source_locator}#{key}",
            raw_value=raw,
            normalized_value=normalized,
            extractor_name=self.name,
            extractor_version=self.version,
        )


class PackageJsonExtractor:
    """Extract a small stable set of facts from ``package.json``."""

    name = "package-json"
    version = "1"

    def supports(self, artifact: Artifact) -> bool:
        return PurePosixPath(artifact.source_locator).name.lower() == "package.json"

    def extract(self, artifact: Artifact, data: bytes) -> tuple[FactSpec, ...]:
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExtractionError(f"invalid package.json: {artifact.source_locator}") from exc
        if not isinstance(document, dict):
            raise ExtractionError(f"package.json root must be an object: {artifact.source_locator}")

        facts: list[FactSpec] = [
            self._fact(artifact, "$manifest.kind", "package.json", "package.json")
        ]
        for key in ("name", "version", "type", "packageManager"):
            value = document.get(key)
            if isinstance(value, str):
                facts.append(self._fact(artifact, key, value, value.strip()))

        engines = document.get("engines")
        if isinstance(engines, dict):
            normalized = {
                str(key): value
                for key, value in sorted(engines.items())
                if isinstance(value, str)
            }
            facts.append(self._fact(artifact, "engines", engines, normalized))

        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            value = document.get(key)
            if isinstance(value, dict):
                normalized = {
                    str(name): constraint
                    for name, constraint in sorted(value.items())
                    if isinstance(constraint, str)
                }
                facts.append(self._fact(artifact, key, value, normalized))

        scripts = document.get("scripts")
        if isinstance(scripts, dict):
            names = sorted(str(name) for name in scripts)
            facts.append(self._fact(artifact, "scripts", names, names))
        return tuple(facts)

    def _fact(self, artifact: Artifact, key: str, raw: object, normalized: object) -> FactSpec:
        return FactSpec(
            locator=f"{artifact.source_locator}#{key}",
            raw_value=raw,
            normalized_value=normalized,
            extractor_name=self.name,
            extractor_version=self.version,
        )


class MarkdownAssertionExtractor:
    """Preserve explicit prose paragraphs from Markdown as source assertions.

    Headings, fenced code, block quotes, tables, and list items are intentionally
    excluded in v1. The extractor stores the source's own prose; it does not
    paraphrase or judge it.
    """

    name = "markdown-prose"
    version = "1"
    _list_item = re.compile(r"^(?:[-+*]\s+|\d+[.)]\s+)")

    def supports(self, artifact: Artifact) -> bool:
        return PurePosixPath(artifact.source_locator).suffix.lower() in {".md", ".markdown"}

    def extract(self, artifact: Artifact, data: bytes) -> tuple[AssertionSpec, ...]:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExtractionError(f"Markdown is not UTF-8: {artifact.source_locator}") from exc

        assertions: list[AssertionSpec] = []
        paragraph: list[str] = []
        start_line: int | None = None
        in_fence = False

        def flush(end_line: int) -> None:
            nonlocal paragraph, start_line
            if paragraph and start_line is not None:
                statement = " ".join(part.strip() for part in paragraph if part.strip()).strip()
                if statement:
                    assertions.append(
                        AssertionSpec(
                            locator=f"{artifact.source_locator}:L{start_line}-L{end_line}",
                            statement=statement,
                            extractor_name=self.name,
                            extractor_version=self.version,
                        )
                    )
            paragraph = []
            start_line = None

        lines = text.splitlines()
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                flush(index - 1)
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if not stripped:
                flush(index - 1)
                continue
            if self._excluded_line(stripped):
                flush(index - 1)
                continue
            if start_line is None:
                start_line = index
            paragraph.append(stripped)
        flush(len(lines))
        return tuple(assertions)

    def _excluded_line(self, line: str) -> bool:
        if line.startswith(("#", ">", "<", "<!--")):
            return True
        if self._list_item.match(line):
            return True
        if line.startswith("|") or ("|" in line and re.fullmatch(r"[|:\-\s]+", line)):
            return True
        return False


@dataclass(frozen=True)
class ExtractionResult:
    capture_id: str
    facts: tuple[EvidenceFact, ...]
    assertions: tuple[SourceAssertion, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.facts, *self.assertions, self.run)


class DeterministicExtractionService:
    """Extract facts/assertions from one persisted capture without inference."""

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        artifact_extractors: Iterable[ArtifactExtractor] | None = None,
        extraction_policy_version: str = "deterministic-evidence.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.object_store = object_store
        self.artifact_extractors = tuple(
            artifact_extractors
            if artifact_extractors is not None
            else (
                ArtifactPathExtractor(),
                PyProjectExtractor(),
                PackageJsonExtractor(),
                MarkdownAssertionExtractor(),
            )
        )
        self.extraction_policy_version = extraction_policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def extract_capture(self, capture_id: str) -> ExtractionResult:
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")

        started_at = self._aware_now()
        run_id = f"run:{self.id_factory()}"
        fact_specs: list[tuple[str, FactSpec]] = []
        assertion_specs: list[tuple[str, AssertionSpec]] = []

        for reference in manifest.artifacts:
            if reference.retrieval_status is not RetrievalStatus.CAPTURED:
                continue
            artifact = self.store.get(Artifact, reference.artifact_id)
            if artifact is None:
                raise ArtifactContractMismatch(
                    f"manifest references missing Artifact record: {reference.artifact_id}"
                )
            self._validate_artifact(manifest, reference, artifact)
            data = self.object_store.get(artifact.content_hash)
            for extractor in self.artifact_extractors:
                if not extractor.supports(artifact):
                    continue
                for spec in extractor.extract(artifact, data):
                    if isinstance(spec, FactSpec):
                        fact_specs.append((artifact.artifact_id, spec))
                    else:
                        assertion_specs.append((artifact.artifact_id, spec))

        fact_specs.sort(
            key=lambda pair: (
                pair[1].extractor_name,
                pair[1].locator,
                self._stable_value(pair[1].normalized_value),
            )
        )
        assertion_specs.sort(
            key=lambda pair: (pair[1].extractor_name, pair[1].locator, pair[1].statement)
        )

        facts = tuple(
            EvidenceFact(
                evidence_id=self._record_id("fact", run_id, index, spec.extractor_name, spec.locator),
                artifact_id=artifact_id,
                locator=spec.locator,
                raw_value=spec.raw_value,
                normalized_value=spec.normalized_value,
                extractor_name=spec.extractor_name,
                extractor_version=spec.extractor_version,
                run_id=run_id,
            )
            for index, (artifact_id, spec) in enumerate(fact_specs, start=1)
        )
        assertions = tuple(
            SourceAssertion(
                assertion_id=self._record_id(
                    "assertion", run_id, index, spec.extractor_name, spec.locator
                ),
                artifact_id=artifact_id,
                locator=spec.locator,
                statement=spec.statement,
                extractor_name=spec.extractor_name,
                extractor_version=spec.extractor_version,
                run_id=run_id,
            )
            for index, (artifact_id, spec) in enumerate(assertion_specs, start=1)
        )

        inputs_hash = self._digest_json(
            {
                "capture_manifest": manifest.model_dump(mode="json", by_alias=True),
                "artifact_extractors": [
                    {"name": extractor.name, "version": extractor.version}
                    for extractor in self.artifact_extractors
                ],
                "policy_version": self.extraction_policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "facts": [self._spec_payload(spec) for _, spec in fact_specs],
                "assertions": [self._spec_payload(spec) for _, spec in assertion_specs],
            }
        )
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.EXTRACTION,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.extraction_policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = ExtractionResult(capture_id, facts, assertions, run)
        self.store.put_many(result.records())
        return result

    @staticmethod
    def _validate_artifact(manifest, reference, artifact: Artifact) -> None:
        expected = (
            manifest.capture_id,
            reference.source_locator,
            reference.content_hash,
            reference.media_type,
        )
        actual = (
            artifact.capture_id,
            artifact.source_locator,
            artifact.content_hash,
            artifact.media_type,
        )
        if actual != expected:
            raise ArtifactContractMismatch(
                f"Artifact record disagrees with capture manifest: {artifact.artifact_id}"
            )

    @staticmethod
    def _record_id(kind: str, run_id: str, index: int, extractor_name: str, locator: str) -> str:
        material = f"{kind}\0{run_id}\0{index}\0{extractor_name}\0{locator}".encode("utf-8")
        return f"{kind}:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _spec_payload(spec: FactSpec | AssertionSpec) -> dict[str, object]:
        if isinstance(spec, FactSpec):
            return {
                "kind": "fact",
                "locator": spec.locator,
                "raw_value": spec.raw_value,
                "normalized_value": spec.normalized_value,
                "extractor_name": spec.extractor_name,
                "extractor_version": spec.extractor_version,
            }
        return {
            "kind": "assertion",
            "locator": spec.locator,
            "statement": spec.statement,
            "extractor_name": spec.extractor_name,
            "extractor_version": spec.extractor_version,
        }

    @staticmethod
    def _stable_value(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("extraction clock must return timezone-aware datetimes")
        return value
