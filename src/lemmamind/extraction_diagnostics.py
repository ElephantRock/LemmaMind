"""Durable extraction-gap diagnostics and paired fail-closed isolation for full M5.

The V1 ``DeterministicExtractionService`` remains strict: any recoverable source
parse/format error aborts that capture generation. Full M5 additionally needs to
process broad explicit-file capture sets where one parser-incompatible artifact
must not erase deterministic evidence from independent artifacts.

This module therefore provides an opt-in paired extraction service. It records
recoverable extractor failures as durable ``ExtractionDiagnostic`` records and,
critically, excludes every fact/assertion for a path from *both* sides whenever
that path has a diagnostic on either side. This prevents asymmetric parser
coverage from being misrepresented later as a ``StructuralDelta`` while keeping
byte-level ``ArtifactDelta`` evidence available to the candidate reducer.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    CONTRACT_TYPES,
    Artifact,
    CaptureManifest,
    ContractModel,
    EvidenceFact,
    Identifier,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
    SourceLocator,
)
from .extraction import (
    ArtifactExtractor,
    AssertionSpec,
    DeterministicExtractionService,
    ExtractionError,
    ExtractionResult,
    FactSpec,
)
from .python_ast import PythonAstExtractionError
from .typescript_ast import TypeScriptAstExtractionError


class ExtractionDiagnostic(ContractModel):
    """One recoverable extractor failure bound to an exact captured artifact."""

    record_id_field = "extraction_diagnostic_id"

    extraction_diagnostic_id: Identifier
    artifact_id: Identifier
    source_locator: SourceLocator
    extractor_name: Identifier
    extractor_version: Identifier
    error_type: Identifier
    error_message: str
    run_id: Identifier


CONTRACT_TYPES[ExtractionDiagnostic.__name__] = ExtractionDiagnostic


@dataclass(frozen=True)
class _DiagnosticSpec:
    artifact_id: str
    source_locator: str
    extractor_name: str
    extractor_version: str
    error_type: str
    error_message: str


@dataclass(frozen=True)
class _CollectedExtraction:
    manifest: CaptureManifest
    fact_specs: tuple[tuple[str, str, FactSpec], ...]
    assertion_specs: tuple[tuple[str, str, AssertionSpec], ...]
    diagnostics: tuple[_DiagnosticSpec, ...]


@dataclass(frozen=True)
class GapTolerantExtractionSideResult:
    extraction: ExtractionResult
    diagnostics: tuple[ExtractionDiagnostic, ...]
    excluded_paths: tuple[str, ...]


@dataclass(frozen=True)
class GapTolerantExtractionPairResult:
    previous: GapTolerantExtractionSideResult
    current: GapTolerantExtractionSideResult
    gap_paths: tuple[str, ...]


class GapTolerantExtractionPairService(DeterministicExtractionService):
    """Extract two capture generations while isolating recoverable path gaps.

    Only expected source/data extraction failures are recoverable. Programming
    errors and contract/storage violations still propagate immediately. If either
    side reports a recoverable diagnostic for a path, all fact/assertion specs for
    that path are excluded from both extraction generations. The path remains in
    the original CaptureManifest and therefore remains visible to ArtifactDelta.
    """

    _recoverable_errors = (
        ExtractionError,
        PythonAstExtractionError,
        TypeScriptAstExtractionError,
    )

    def __init__(
        self,
        store,
        object_store,
        *,
        artifact_extractors: Iterable[ArtifactExtractor] | None = None,
        extraction_policy_version: str = "deterministic-evidence.gap-tolerant-pair.v1",
        code_version: str = "lemmamind-0.1.0",
        clock=None,
        id_factory=None,
    ) -> None:
        super().__init__(
            store,
            object_store,
            artifact_extractors=artifact_extractors,
            extraction_policy_version=extraction_policy_version,
            code_version=code_version,
            clock=clock,
            id_factory=id_factory,
        )

    def extract_pair(
        self,
        previous_capture_id: str,
        current_capture_id: str,
    ) -> GapTolerantExtractionPairResult:
        previous = self._collect(previous_capture_id)
        current = self._collect(current_capture_id)

        gap_paths = tuple(
            sorted(
                {
                    item.source_locator
                    for item in (*previous.diagnostics, *current.diagnostics)
                }
            )
        )
        excluded = set(gap_paths)

        previous_result = self._persist_collected(previous, excluded)
        current_result = self._persist_collected(current, excluded)
        return GapTolerantExtractionPairResult(
            previous_result,
            current_result,
            gap_paths,
        )

    def _collect(self, capture_id: str) -> _CollectedExtraction:
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")

        fact_specs: list[tuple[str, str, FactSpec]] = []
        assertion_specs: list[tuple[str, str, AssertionSpec]] = []
        diagnostics: list[_DiagnosticSpec] = []

        for reference in manifest.artifacts:
            if reference.retrieval_status is not RetrievalStatus.CAPTURED:
                continue
            artifact = self.store.get(Artifact, reference.artifact_id)
            if artifact is None:
                raise RuntimeError(
                    f"manifest references missing Artifact record: {reference.artifact_id}"
                )
            self._validate_artifact(manifest, reference, artifact)
            data = self.object_store.get(artifact.content_hash)

            for extractor in self.artifact_extractors:
                if not extractor.supports(artifact):
                    continue
                try:
                    extracted = extractor.extract(artifact, data)
                except self._recoverable_errors as exc:
                    diagnostics.append(
                        _DiagnosticSpec(
                            artifact_id=artifact.artifact_id,
                            source_locator=artifact.source_locator,
                            extractor_name=extractor.name,
                            extractor_version=extractor.version,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                    continue

                for spec in extracted:
                    if isinstance(spec, FactSpec):
                        fact_specs.append(
                            (artifact.artifact_id, artifact.source_locator, spec)
                        )
                    else:
                        assertion_specs.append(
                            (artifact.artifact_id, artifact.source_locator, spec)
                        )

        diagnostics.sort(
            key=lambda item: (
                item.source_locator,
                item.extractor_name,
                item.extractor_version,
                item.error_type,
                item.error_message,
            )
        )
        return _CollectedExtraction(
            manifest,
            tuple(fact_specs),
            tuple(assertion_specs),
            tuple(diagnostics),
        )

    def _persist_collected(
        self,
        collected: _CollectedExtraction,
        excluded_paths: set[str],
    ) -> GapTolerantExtractionSideResult:
        started_at = self._aware_now()
        run_id = f"run:{self.id_factory()}"

        fact_specs = [
            (artifact_id, spec)
            for artifact_id, path, spec in collected.fact_specs
            if path not in excluded_paths
        ]
        assertion_specs = [
            (artifact_id, spec)
            for artifact_id, path, spec in collected.assertion_specs
            if path not in excluded_paths
        ]
        fact_specs.sort(
            key=lambda pair: (
                pair[1].extractor_name,
                pair[1].locator,
                self._stable_value(pair[1].normalized_value),
            )
        )
        assertion_specs.sort(key=lambda pair: self._assertion_sort_key(pair[1]))

        facts = tuple(
            EvidenceFact(
                evidence_id=self._record_id(
                    "fact", run_id, index, spec.extractor_name, spec.locator
                ),
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
        diagnostics = tuple(
            ExtractionDiagnostic(
                extraction_diagnostic_id=self._diagnostic_id(run_id, index, item),
                artifact_id=item.artifact_id,
                source_locator=item.source_locator,
                extractor_name=item.extractor_name,
                extractor_version=item.extractor_version,
                error_type=item.error_type,
                error_message=item.error_message,
                run_id=run_id,
            )
            for index, item in enumerate(collected.diagnostics, start=1)
        )

        inputs_hash = self._digest_json(
            {
                "capture_manifest": collected.manifest.model_dump(
                    mode="json", by_alias=True
                ),
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
                "assertions": [
                    self._spec_payload(spec) for _, spec in assertion_specs
                ],
                "diagnostics": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in diagnostics
                ],
                "paired_excluded_paths": sorted(excluded_paths),
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
        extraction = ExtractionResult(
            collected.manifest.capture_id,
            facts,
            assertions,
            run,
        )
        self.store.put_many((*extraction.records(), *diagnostics))
        return GapTolerantExtractionSideResult(
            extraction,
            diagnostics,
            tuple(sorted(excluded_paths)),
        )

    @staticmethod
    def _diagnostic_id(run_id: str, index: int, item: _DiagnosticSpec) -> str:
        material = (
            f"diagnostic\0{run_id}\0{index}\0{item.artifact_id}\0"
            f"{item.extractor_name}\0{item.extractor_version}\0{item.error_type}\0"
            f"{item.error_message}"
        ).encode("utf-8")
        return f"extraction-diagnostic:{hashlib.sha256(material).hexdigest()}"


EXTRACTION_DIAGNOSTIC_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    ExtractionDiagnostic.__name__: ExtractionDiagnostic,
}
