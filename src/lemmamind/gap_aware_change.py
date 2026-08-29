"""Gap-aware deterministic StructuralDelta comparison for full M5.

``ExtractionDiagnostic`` is evidence about extraction coverage, not evidence that
source structure was added or removed. This change service keeps ArtifactDelta
unchanged, but excludes any source path with a recoverable extraction diagnostic
on either revision from StructuralDelta comparison. The exclusion is symmetric
across the pair so parser coverage cannot manufacture a structural change.
"""
from __future__ import annotations

from .change_contracts import (
    ArtifactDelta,
    ArtifactDeltaType,
    StructuralDelta,
    StructuralDeltaType,
)
from .change_intelligence import (
    ChangeIntelligenceError,
    DeterminismViolation,
    DeterministicChangeService,
)
from .extraction_diagnostics import ExtractionDiagnostic
from .revision_capture import ReconstructedCapture


class GapAwareDeterministicChangeService(DeterministicChangeService):
    """Compare deterministic facts while treating extraction gaps as unknown."""

    def __init__(
        self,
        store,
        object_store,
        *,
        policy_version: str = "deterministic-change.gap-aware.v1",
        code_version: str = "lemmamind-0.1.0",
        clock=None,
        id_factory=None,
    ) -> None:
        super().__init__(
            store,
            object_store,
            policy_version=policy_version,
            code_version=code_version,
            clock=clock,
            id_factory=id_factory,
        )

    def _structural_deltas(
        self,
        previous: ReconstructedCapture,
        current: ReconstructedCapture,
        artifact_deltas: tuple[ArtifactDelta, ...],
        previous_extraction_run_id: str,
        current_extraction_run_id: str,
        extractor_descriptors: tuple[dict[str, str], ...],
        run_id: str,
    ) -> tuple[StructuralDelta, ...]:
        previous_run, previous_facts = self._extraction_generation(
            previous, previous_extraction_run_id, extractor_descriptors
        )
        current_run, current_facts = self._extraction_generation(
            current, current_extraction_run_id, extractor_descriptors
        )
        self._require_compatible_extraction_runs(previous_run, current_run)

        excluded_paths = self._diagnostic_paths(
            previous,
            previous_extraction_run_id,
            extractor_descriptors,
        ) | self._diagnostic_paths(
            current,
            current_extraction_run_id,
            extractor_descriptors,
        )

        previous_map = self._fact_map(previous, previous_facts)
        current_map = self._fact_map(current, current_facts)
        comparable_locators = (
            {item.source_locator for item in previous.artifacts}
            & {item.source_locator for item in current.artifacts}
        ) - excluded_paths
        artifact_delta_by_locator = {
            item.source_locator: item
            for item in artifact_deltas
            if item.change_type
            not in {
                ArtifactDeltaType.CAPTURE_SCOPE_ADDED,
                ArtifactDeltaType.CAPTURE_SCOPE_REMOVED,
            }
        }

        structural: list[StructuralDelta] = []
        for key in sorted(set(previous_map) | set(current_map)):
            source_locator, extractor_name, extractor_version, relative_locator = key
            if source_locator not in comparable_locators:
                continue

            old = previous_map.get(key)
            new = current_map.get(key)
            if old is not None and new is not None:
                if old.normalized_value == new.normalized_value:
                    continue
                change_type = StructuralDeltaType.MODIFIED
            elif old is None:
                change_type = StructuralDeltaType.ADDED
            else:
                change_type = StructuralDeltaType.REMOVED

            artifact_delta = artifact_delta_by_locator.get(source_locator)
            if artifact_delta is None:
                raise DeterminismViolation(
                    "deterministic evidence changed without an ArtifactDelta for "
                    f"{source_locator}; identical capture state cannot yield a structural delta"
                )

            structural_key = (
                f"{extractor_name}@{extractor_version}:{relative_locator or '#root'}"
            )
            structural.append(
                StructuralDelta(
                    structural_delta_id=self._structural_delta_id(
                        run_id,
                        artifact_delta.artifact_delta_id,
                        structural_key,
                        change_type,
                    ),
                    artifact_delta_id=artifact_delta.artifact_delta_id,
                    source_id=current.revision.source_id,
                    previous_source_revision_id=previous.revision.source_revision_id,
                    current_source_revision_id=current.revision.source_revision_id,
                    source_locator=source_locator,
                    structural_key=structural_key,
                    change_type=change_type,
                    extractor_name=extractor_name,
                    extractor_version=extractor_version,
                    previous_evidence_id=None if old is None else old.evidence_id,
                    current_evidence_id=None if new is None else new.evidence_id,
                    previous_locator=None if old is None else old.locator,
                    current_locator=None if new is None else new.locator,
                    previous_value=None if old is None else old.normalized_value,
                    current_value=None if new is None else new.normalized_value,
                    diff_run_id=run_id,
                )
            )
        return tuple(structural)

    def _diagnostic_paths(
        self,
        capture: ReconstructedCapture,
        run_id: str,
        extractor_descriptors: tuple[dict[str, str], ...],
    ) -> set[str]:
        diagnostics = tuple(
            item
            for item in self.store.list(ExtractionDiagnostic)
            if item.run_id == run_id
        )
        if not diagnostics:
            return set()

        artifact_by_id = {
            item.artifact_id: item for item in capture.artifacts if item.is_captured
        }
        allowed_extractors = {
            (item["name"], item["version"]) for item in extractor_descriptors
        }
        paths: set[str] = set()
        for item in diagnostics:
            if item.capture_id != capture.manifest.capture_id:
                raise ChangeIntelligenceError(
                    "ExtractionDiagnostic capture disagrees with extraction generation: "
                    f"{item.extraction_diagnostic_id}"
                )
            if item.source_revision_id != capture.revision.source_revision_id:
                raise ChangeIntelligenceError(
                    "ExtractionDiagnostic revision disagrees with extraction generation: "
                    f"{item.extraction_diagnostic_id}"
                )

            artifact = artifact_by_id.get(item.artifact_id)
            if artifact is None:
                raise ChangeIntelligenceError(
                    f"ExtractionDiagnostic references non-captured artifact: {item.artifact_id}"
                )
            if artifact.source_locator != item.source_locator:
                raise ChangeIntelligenceError(
                    "ExtractionDiagnostic source locator disagrees with captured artifact: "
                    f"{item.extraction_diagnostic_id}"
                )
            if (item.extractor_name, item.extractor_version) not in allowed_extractors:
                raise ChangeIntelligenceError(
                    "ExtractionDiagnostic extractor is outside the supplied extraction profile: "
                    f"{item.extraction_diagnostic_id}"
                )
            paths.add(item.source_locator)
        return paths
