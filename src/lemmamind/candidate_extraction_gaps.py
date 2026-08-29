"""Candidate-local extraction-gap signals for full M5.

A parser/extractor failure is not a semantic change claim and must not be
silently converted into structural evidence. ``ExtractionDiagnostic`` records
preserve the source-local failure; this module projects those diagnostics onto
the deterministic ``IntervalCandidateSegment`` review units so the attention
surface can explicitly say that a retained candidate contains an extraction gap.

Projection is fail-closed across the complete lineage: segmentation candidate →
candidate factual reduction → exact previous/current captures and extraction
runs → source-local diagnostic. Matching only by path is never sufficient.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .candidate_extraction_gap_contracts import CandidateExtractionGapSignal
from .candidate_reduction_contracts import CandidateFactualReduction
from .contracts import CaptureManifest, PipelineRun, RetrievalStatus, RunType
from .extraction_diagnostic_contracts import ExtractionDiagnostic
from .interval_segmentation_contracts import IntervalCandidateSegment


class CandidateExtractionGapError(RuntimeError):
    """Extraction diagnostics cannot be projected onto one candidate generation."""


class ContractStore:
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class CandidateExtractionGapResult:
    signals: tuple[CandidateExtractionGapSignal, ...]

    @property
    def candidate_count(self) -> int:
        return len(self.signals)

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(
            sorted({path for signal in self.signals for path in signal.paths})
        )


class CandidateExtractionGapService:
    """Bind extraction diagnostics to deterministic interval candidates."""

    def __init__(self, store) -> None:
        self.store = store

    def record_signals(
        self,
        *,
        segmentation_run_id: str,
        previous_extraction_run_id: str,
        current_extraction_run_id: str,
        reduction_run_id: str,
    ) -> CandidateExtractionGapResult:
        self._completed_run(segmentation_run_id, RunType.DIFF, "segmentation")
        self._completed_run(
            previous_extraction_run_id,
            RunType.EXTRACTION,
            "previous extraction",
        )
        self._completed_run(
            current_extraction_run_id,
            RunType.EXTRACTION,
            "current extraction",
        )
        self._completed_run(reduction_run_id, RunType.OTHER, "candidate reduction")

        candidates = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(IntervalCandidateSegment)
                    if item.segmentation_run_id == segmentation_run_id
                ),
                key=lambda item: item.interval_candidate_segment_id,
            )
        )
        path_to_candidate: dict[str, IntervalCandidateSegment] = {}
        for candidate in candidates:
            for path in candidate.paths:
                if path in path_to_candidate:
                    raise CandidateExtractionGapError(
                        "Git path is assigned to more than one interval candidate"
                    )
                path_to_candidate[path] = candidate

        reductions = tuple(
            item
            for item in self.store.list(CandidateFactualReduction)
            if item.reduction_run_id == reduction_run_id
        )
        reduction_by_candidate: dict[str, CandidateFactualReduction] = {}
        for reduction in reductions:
            if reduction.interval_candidate_segment_id in reduction_by_candidate:
                raise CandidateExtractionGapError(
                    "candidate reduction generation contains duplicate candidate identities"
                )
            reduction_by_candidate[reduction.interval_candidate_segment_id] = reduction

        expected_candidate_ids = {
            item.interval_candidate_segment_id for item in candidates
        }
        if set(reduction_by_candidate) != expected_candidate_ids:
            raise CandidateExtractionGapError(
                "candidate reduction generation does not cover the segmentation exactly"
            )

        for candidate in candidates:
            reduction = reduction_by_candidate[candidate.interval_candidate_segment_id]
            expected = (
                candidate.source_id,
                candidate.previous_source_revision_id,
                candidate.current_source_revision_id,
                candidate.segmentation_run_id,
                previous_extraction_run_id,
                current_extraction_run_id,
                reduction_run_id,
            )
            observed = (
                reduction.source_id,
                reduction.previous_source_revision_id,
                reduction.current_source_revision_id,
                reduction.segmentation_run_id,
                reduction.previous_extraction_run_id,
                reduction.current_extraction_run_id,
                reduction.reduction_run_id,
            )
            if observed != expected:
                raise CandidateExtractionGapError(
                    "candidate reduction lineage disagrees with supplied generation"
                )
            if reduction.paths != candidate.paths:
                raise CandidateExtractionGapError(
                    "candidate reduction paths disagree with interval candidate"
                )

        previous = tuple(
            item
            for item in self.store.list(ExtractionDiagnostic)
            if item.run_id == previous_extraction_run_id
        )
        current = tuple(
            item
            for item in self.store.list(ExtractionDiagnostic)
            if item.run_id == current_extraction_run_id
        )
        diagnostics = (*previous, *current)

        foreign_paths = sorted(
            {
                item.source_locator
                for item in diagnostics
                if item.source_locator not in path_to_candidate
            }
        )
        if foreign_paths:
            raise CandidateExtractionGapError(
                "extraction diagnostics fall outside the segmentation generation: "
                f"{foreign_paths}"
            )

        self._validate_diagnostic_generation(
            previous,
            path_to_candidate,
            reduction_by_candidate,
            previous=True,
        )
        self._validate_diagnostic_generation(
            current,
            path_to_candidate,
            reduction_by_candidate,
            previous=False,
        )

        previous_by_candidate: dict[str, list[ExtractionDiagnostic]] = {}
        current_by_candidate: dict[str, list[ExtractionDiagnostic]] = {}
        for item in previous:
            candidate_id = path_to_candidate[item.source_locator].interval_candidate_segment_id
            previous_by_candidate.setdefault(candidate_id, []).append(item)
        for item in current:
            candidate_id = path_to_candidate[item.source_locator].interval_candidate_segment_id
            current_by_candidate.setdefault(candidate_id, []).append(item)

        signals: list[CandidateExtractionGapSignal] = []
        for candidate in candidates:
            previous_items = previous_by_candidate.get(
                candidate.interval_candidate_segment_id, []
            )
            current_items = current_by_candidate.get(
                candidate.interval_candidate_segment_id, []
            )
            if not previous_items and not current_items:
                continue

            reduction = reduction_by_candidate[candidate.interval_candidate_segment_id]
            paths = tuple(
                sorted(
                    {
                        item.source_locator
                        for item in (*previous_items, *current_items)
                    }
                )
            )
            previous_ids = tuple(
                sorted(item.extraction_diagnostic_id for item in previous_items)
            )
            current_ids = tuple(
                sorted(item.extraction_diagnostic_id for item in current_items)
            )
            signals.append(
                CandidateExtractionGapSignal(
                    candidate_extraction_gap_signal_id=self._stable_id(
                        segmentation_run_id,
                        reduction_run_id,
                        candidate.interval_candidate_segment_id,
                        reduction.previous_capture_id,
                        reduction.current_capture_id,
                        paths,
                        previous_ids,
                        current_ids,
                    ),
                    interval_candidate_segment_id=candidate.interval_candidate_segment_id,
                    source_id=candidate.source_id,
                    previous_source_revision_id=candidate.previous_source_revision_id,
                    current_source_revision_id=candidate.current_source_revision_id,
                    previous_capture_id=reduction.previous_capture_id,
                    current_capture_id=reduction.current_capture_id,
                    paths=paths,
                    previous_diagnostic_ids=previous_ids,
                    current_diagnostic_ids=current_ids,
                    segmentation_run_id=segmentation_run_id,
                    previous_extraction_run_id=previous_extraction_run_id,
                    current_extraction_run_id=current_extraction_run_id,
                    reduction_run_id=reduction_run_id,
                )
            )

        result = CandidateExtractionGapResult(tuple(signals))
        self.store.put_many(result.signals)
        return result

    def _validate_diagnostic_generation(
        self,
        diagnostics: tuple[ExtractionDiagnostic, ...],
        path_to_candidate: dict[str, IntervalCandidateSegment],
        reduction_by_candidate: dict[str, CandidateFactualReduction],
        *,
        previous: bool,
    ) -> None:
        for item in diagnostics:
            candidate = path_to_candidate[item.source_locator]
            reduction = reduction_by_candidate[candidate.interval_candidate_segment_id]
            expected_revision_id = (
                reduction.previous_source_revision_id
                if previous
                else reduction.current_source_revision_id
            )
            expected_capture_id = (
                reduction.previous_capture_id if previous else reduction.current_capture_id
            )
            if item.source_revision_id != expected_revision_id:
                raise CandidateExtractionGapError(
                    "extraction diagnostic revision disagrees with candidate reduction"
                )
            if item.capture_id != expected_capture_id:
                raise CandidateExtractionGapError(
                    "extraction diagnostic capture disagrees with candidate reduction"
                )

            manifest = self.store.get(CaptureManifest, expected_capture_id)
            if manifest is None:
                raise CandidateExtractionGapError(
                    f"missing candidate capture manifest: {expected_capture_id}"
                )
            if manifest.source_revision_id != expected_revision_id:
                raise CandidateExtractionGapError(
                    "candidate capture revision disagrees with candidate reduction"
                )
            references = tuple(
                reference
                for reference in manifest.artifacts
                if reference.artifact_id == item.artifact_id
            )
            if len(references) != 1:
                raise CandidateExtractionGapError(
                    "extraction diagnostic artifact is not uniquely present in candidate capture"
                )
            reference = references[0]
            if (
                reference.source_locator != item.source_locator
                or reference.retrieval_status is not RetrievalStatus.CAPTURED
            ):
                raise CandidateExtractionGapError(
                    "extraction diagnostic artifact/path state disagrees with candidate capture"
                )

    def _completed_run(self, run_id: str, run_type: RunType, label: str) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise CandidateExtractionGapError(f"unknown {label} PipelineRun: {run_id}")
        if run.run_type is not run_type or run.finished_at is None:
            raise CandidateExtractionGapError(
                f"{label} requires one completed {run_type.value} PipelineRun"
            )
        return run

    @staticmethod
    def _stable_id(
        segmentation_run_id: str,
        reduction_run_id: str,
        candidate_id: str,
        previous_capture_id: str,
        current_capture_id: str,
        paths: tuple[str, ...],
        previous_ids: tuple[str, ...],
        current_ids: tuple[str, ...],
    ) -> str:
        material = "\0".join(
            (
                segmentation_run_id,
                reduction_run_id,
                candidate_id,
                previous_capture_id,
                current_capture_id,
                *paths,
                "previous",
                *previous_ids,
                "current",
                *current_ids,
            )
        ).encode("utf-8")
        return f"candidate-extraction-gap:{hashlib.sha256(material).hexdigest()}"
