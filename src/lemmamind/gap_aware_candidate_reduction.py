"""Gap-aware candidate factual reduction for broad full-M5 capture sets.

The V1-compatible ``CandidateFactualReductionService`` remains unchanged. This
opt-in full-M5 variant preserves the same provenance/capture/plan validation but
uses ``GapAwareDeterministicChangeService`` and suppresses authored-assertion
comparison on paths whose extraction coverage is explicitly incomplete. Those
paths remain retained through ArtifactDelta and are projected separately as
``CandidateExtractionGapSignal`` records.
"""
from __future__ import annotations

from .candidate_reduction import (
    CandidateFactualReductionError,
    CandidateFactualReductionResult,
    CandidateFactualReductionService,
)
from .capture_planning_contracts import AffectedFileCapturePlan
from .contracts import CONTRACT_SCHEMA_VERSION, PipelineRun, RunType
from .extraction import ArtifactExtractor
from .extraction_diagnostics import ExtractionDiagnostic
from .gap_aware_change import GapAwareDeterministicChangeService
from .interval_segmentation_contracts import CommitRangeSummary, IntervalCandidateSegment
from .path_change_contracts import GitPathDelta


class GapAwareCandidateFactualReductionService(CandidateFactualReductionService):
    """Reduce one segmentation while preserving explicit extraction uncertainty."""

    def __init__(
        self,
        store,
        object_store,
        *,
        policy_version: str = "candidate-factual-reduction.gap-aware.v1",
        change_policy_version: str = "candidate-factual-change.gap-aware.v1",
        code_version: str = "lemmamind-0.1.0",
        clock=None,
        id_factory=None,
    ) -> None:
        super().__init__(
            store,
            object_store,
            policy_version=policy_version,
            change_policy_version=change_policy_version,
            code_version=code_version,
            clock=clock,
            id_factory=id_factory,
        )

    def reduce_segmentation(
        self,
        *,
        diff_run_id: str,
        segmentation_run_id: str,
        planner_run_id: str,
        previous_capture_id: str,
        current_capture_id: str,
        previous_extraction_run_id: str,
        current_extraction_run_id: str,
        artifact_extractors: tuple[ArtifactExtractor, ...] | list[ArtifactExtractor],
    ) -> CandidateFactualReductionResult:
        started_at = self._aware_now()
        extractor_profile = tuple(artifact_extractors)
        if not extractor_profile:
            raise ValueError("artifact_extractors must not be empty")

        self._completed_run(segmentation_run_id, RunType.DIFF, "segmentation")
        self._completed_run(planner_run_id, RunType.OTHER, "affected-file planner")

        summary = self._diff_summary(diff_run_id)
        range_summary = self._range_summary(segmentation_run_id)
        if (
            range_summary.source_id,
            range_summary.previous_source_revision_id,
            range_summary.current_source_revision_id,
        ) != (
            summary.source_id,
            summary.previous_source_revision_id,
            summary.current_source_revision_id,
        ):
            raise CandidateFactualReductionError(
                "commit-range generation disagrees with recursive path-diff provenance"
            )

        deltas = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(GitPathDelta)
                    if item.diff_run_id == diff_run_id
                ),
                key=lambda item: item.path,
            )
        )
        if len(deltas) != summary.delta_count:
            raise CandidateFactualReductionError(
                "GitPathDiffSummary.delta_count disagrees with persisted GitPathDelta records"
            )
        self._validate_delta_generation(summary, deltas)

        candidates = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(IntervalCandidateSegment)
                    if item.segmentation_run_id == segmentation_run_id
                ),
                key=lambda item: (
                    item.commit_ordinal,
                    item.path_group,
                    item.chunk_ordinal,
                    item.interval_candidate_segment_id,
                ),
            )
        )
        self._validate_candidate_coverage(summary, deltas, candidates)

        plans = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(AffectedFileCapturePlan)
                    if item.planner_run_id == planner_run_id
                ),
                key=lambda item: item.path,
            )
        )
        self._validate_plan_coverage(summary, deltas, plans, planner_run_id)

        previous_manifest = self._manifest(previous_capture_id)
        current_manifest = self._manifest(current_capture_id)
        if previous_manifest.source_revision_id != summary.previous_source_revision_id:
            raise CandidateFactualReductionError(
                "previous candidate capture does not bind to previous SourceRevision"
            )
        if current_manifest.source_revision_id != summary.current_source_revision_id:
            raise CandidateFactualReductionError(
                "current candidate capture does not bind to current SourceRevision"
            )

        previous_required = self._required_paths(plans, previous=True)
        current_required = self._required_paths(plans, previous=False)
        self._validate_capture_scope(previous_manifest, plans, previous=True)
        self._validate_capture_scope(current_manifest, plans, previous=False)

        change = GapAwareDeterministicChangeService(
            self.store,
            self.object_store,
            policy_version=self.change_policy_version,
            code_version=self.code_version,
            clock=self.clock,
            id_factory=self.id_factory,
        ).compare_captures(
            previous_capture_id,
            current_capture_id,
            previous_extraction_run_id=previous_extraction_run_id,
            current_extraction_run_id=current_extraction_run_id,
            artifact_extractors=extractor_profile,
        )

        gap_paths = {
            item.source_locator
            for item in self.store.list(ExtractionDiagnostic)
            if item.run_id
            in {previous_extraction_run_id, current_extraction_run_id}
        }
        previous_assertions = {
            path: value
            for path, value in self._assertion_signatures(
                previous_manifest,
                previous_extraction_run_id,
            ).items()
            if path not in gap_paths
        }
        current_assertions = {
            path: value
            for path, value in self._assertion_signatures(
                current_manifest,
                current_extraction_run_id,
            ).items()
            if path not in gap_paths
        }

        plan_by_delta_id = {item.git_path_delta_id: item for item in plans}
        artifact_by_path = {
            item.source_locator: item for item in change.artifact_deltas
        }
        structural_by_path: dict[str, list] = {}
        for item in change.structural_deltas:
            structural_by_path.setdefault(item.source_locator, []).append(item)

        reduction_run_id = f"run:candidate-factual-reduction:{self.id_factory()}"
        reductions = tuple(
            self._reduce_candidate(
                candidate,
                plan_by_delta_id,
                artifact_by_path,
                structural_by_path,
                previous_assertions,
                current_assertions,
                previous_required=set(previous_required),
                current_required=set(current_required),
                diff_run_id=diff_run_id,
                planner_run_id=planner_run_id,
                previous_capture_id=previous_capture_id,
                current_capture_id=current_capture_id,
                previous_extraction_run_id=previous_extraction_run_id,
                current_extraction_run_id=current_extraction_run_id,
                change_run_id=change.run.run_id,
                reduction_run_id=reduction_run_id,
            )
            for candidate in candidates
        )

        inputs_hash = self._digest_json(
            {
                "diff_run_id": diff_run_id,
                "segmentation_run_id": segmentation_run_id,
                "planner_run_id": planner_run_id,
                "previous_capture": previous_manifest.model_dump(mode="json", by_alias=True),
                "current_capture": current_manifest.model_dump(mode="json", by_alias=True),
                "previous_extraction_run_id": previous_extraction_run_id,
                "current_extraction_run_id": current_extraction_run_id,
                "artifact_extractors": [
                    {"name": item.name, "version": item.version}
                    for item in extractor_profile
                ],
                "extraction_gap_paths": sorted(gap_paths),
                "change_run_id": change.run.run_id,
                "candidates": [
                    item.model_dump(mode="json", by_alias=True) for item in candidates
                ],
                "affected_file_plans": [
                    item.model_dump(mode="json", by_alias=True) for item in plans
                ],
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            [item.model_dump(mode="json", by_alias=True) for item in reductions]
        )
        run = PipelineRun(
            run_id=reduction_run_id,
            run_type=RunType.OTHER,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = CandidateFactualReductionResult(
            diff_run_id,
            segmentation_run_id,
            planner_run_id,
            reductions,
            change,
            run,
        )
        self.store.put_many(result.records())
        return result
