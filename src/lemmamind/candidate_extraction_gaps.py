"""Candidate-local extraction-gap signals for full M5.

A parser/extractor failure is not a semantic change claim and must not be
silently converted into structural evidence. ``ExtractionDiagnostic`` records
preserve the source-local failure; this module projects those diagnostics onto
the deterministic ``IntervalCandidateSegment`` review units so the attention
surface can explicitly say that a retained candidate contains an extraction gap.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import model_validator

from .contracts import (
    CONTRACT_TYPES,
    ContractModel,
    Identifier,
    PipelineRun,
    RunType,
    SourceLocator,
)
from .extraction_diagnostics import ExtractionDiagnostic
from .interval_segmentation_contracts import IntervalCandidateSegment


class CandidateExtractionGapSignal(ContractModel):
    """Explicit candidate-level signal that deterministic extraction was incomplete."""

    record_id_field = "candidate_extraction_gap_signal_id"

    candidate_extraction_gap_signal_id: Identifier
    interval_candidate_segment_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    paths: tuple[SourceLocator, ...]
    previous_diagnostic_ids: tuple[Identifier, ...] = ()
    current_diagnostic_ids: tuple[Identifier, ...] = ()
    segmentation_run_id: Identifier
    previous_extraction_run_id: Identifier
    current_extraction_run_id: Identifier
    reduction_run_id: Identifier

    @model_validator(mode="after")
    def validate_signal(self) -> "CandidateExtractionGapSignal":
        if not self.paths:
            raise ValueError("candidate extraction-gap signal cannot be empty")
        if self.paths != tuple(sorted(set(self.paths))):
            raise ValueError("paths must be sorted and unique")
        for field_name in ("previous_diagnostic_ids", "current_diagnostic_ids"):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        if not self.previous_diagnostic_ids and not self.current_diagnostic_ids:
            raise ValueError("candidate extraction-gap signal requires a diagnostic")
        return self


CONTRACT_TYPES[CandidateExtractionGapSignal.__name__] = CandidateExtractionGapSignal


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
                        paths,
                        previous_ids,
                        current_ids,
                    ),
                    interval_candidate_segment_id=candidate.interval_candidate_segment_id,
                    source_id=candidate.source_id,
                    previous_source_revision_id=candidate.previous_source_revision_id,
                    current_source_revision_id=candidate.current_source_revision_id,
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
        paths: tuple[str, ...],
        previous_ids: tuple[str, ...],
        current_ids: tuple[str, ...],
    ) -> str:
        material = "\0".join(
            (
                segmentation_run_id,
                reduction_run_id,
                candidate_id,
                *paths,
                "previous",
                *previous_ids,
                "current",
                *current_ids,
            )
        ).encode("utf-8")
        return f"candidate-extraction-gap:{hashlib.sha256(material).hexdigest()}"


CANDIDATE_EXTRACTION_GAP_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    CandidateExtractionGapSignal.__name__: CandidateExtractionGapSignal,
}
