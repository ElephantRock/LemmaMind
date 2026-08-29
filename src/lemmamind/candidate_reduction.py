"""Candidate-scoped deterministic factual reduction for full M5.

This layer consumes already-localized ``GitPathDelta`` evidence, deterministic
interval candidates, affected-file plans, exact explicit-file captures, and
compatible extraction generations. It produces one auditable factual summary per
candidate and deliberately stops before semantic ``ChangeInterpretation``.

The fail-closed rule is important: a changed artifact that produces no selected
fact/assertion delta is retained as an unexplained artifact delta rather than
being silently treated as low-value churn. Automatic suppression is limited to
candidates whose every path was already suppressed by the versioned affected-file
planning policy.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Protocol

from .candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from .capture_planning_contracts import (
    AffectedFileCapturePlan,
    CapturePlanDisposition,
    CapturePlanSide,
)
from .change_intelligence import DeterministicChangeResult, DeterministicChangeService
from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureManifest,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
)
from .extraction import ArtifactExtractor
from .interval_segmentation_contracts import CommitRangeSummary, IntervalCandidateSegment
from .objects import ContentAddressedFileStore
from .path_change_contracts import GitPathDelta, GitPathDiffSummary


class CandidateFactualReductionError(RuntimeError):
    """Persisted M5 generations cannot be reduced without corrupting provenance."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class CandidateFactualReductionResult:
    diff_run_id: str
    segmentation_run_id: str
    planner_run_id: str
    reductions: tuple[CandidateFactualReduction, ...]
    change: DeterministicChangeResult
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.reductions, self.run)

    @property
    def retained_count(self) -> int:
        return sum(
            item.disposition is CandidateReductionDisposition.RETAIN
            for item in self.reductions
        )

    @property
    def suppressed_count(self) -> int:
        return sum(
            item.disposition is CandidateReductionDisposition.SUPPRESS
            for item in self.reductions
        )


class CandidateFactualReductionService:
    """Reduce one segmentation generation using exact candidate-local evidence."""

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "candidate-factual-reduction.v1",
        change_policy_version: str = "candidate-factual-change.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.object_store = object_store
        self.policy_version = policy_version
        self.change_policy_version = change_policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

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
        artifact_extractors: Iterable[ArtifactExtractor],
    ) -> CandidateFactualReductionResult:
        started_at = self._aware_now()
        extractor_profile = tuple(artifact_extractors)
        if not extractor_profile:
            raise ValueError("artifact_extractors must not be empty")

        self._completed_run(segmentation_run_id, RunType.OTHER, "segmentation")
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

        change = DeterministicChangeService(
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

        previous_assertions = self._assertion_signatures(
            previous_manifest,
            previous_extraction_run_id,
        )
        current_assertions = self._assertion_signatures(
            current_manifest,
            current_extraction_run_id,
        )

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

    def _reduce_candidate(
        self,
        candidate: IntervalCandidateSegment,
        plan_by_delta_id: dict[str, AffectedFileCapturePlan],
        artifact_by_path: dict,
        structural_by_path: dict[str, list],
        previous_assertions: dict[str, tuple[tuple[str, str, str], ...]],
        current_assertions: dict[str, tuple[tuple[str, str, str], ...]],
        *,
        previous_required: set[str],
        current_required: set[str],
        diff_run_id: str,
        planner_run_id: str,
        previous_capture_id: str,
        current_capture_id: str,
        previous_extraction_run_id: str,
        current_extraction_run_id: str,
        change_run_id: str,
        reduction_run_id: str,
    ) -> CandidateFactualReduction:
        paths = tuple(candidate.paths)
        path_set = set(paths)
        candidate_plans = tuple(
            plan_by_delta_id[item_id] for item_id in candidate.git_path_delta_ids
        )
        affected_file_plan_ids = tuple(
            sorted(item.affected_file_plan_id for item in candidate_plans)
        )
        capture_scoped_paths = tuple(
            sorted(path_set & (previous_required | current_required))
        )
        policy_suppressed_paths = tuple(
            sorted(
                item.path
                for item in candidate_plans
                if self._is_policy_suppressed(item)
            )
        )

        artifact_items = tuple(
            sorted(
                (artifact_by_path[path] for path in path_set if path in artifact_by_path),
                key=lambda item: item.source_locator,
            )
        )
        artifact_delta_paths = tuple(item.source_locator for item in artifact_items)
        artifact_delta_ids = tuple(sorted(item.artifact_delta_id for item in artifact_items))

        structural_items = tuple(
            sorted(
                (
                    item
                    for path in path_set
                    for item in structural_by_path.get(path, ())
                ),
                key=lambda item: item.structural_delta_id,
            )
        )
        structural_delta_ids = tuple(item.structural_delta_id for item in structural_items)
        structural_delta_paths = tuple(
            sorted({item.source_locator for item in structural_items})
        )

        assertion_changed_paths = tuple(
            sorted(
                path
                for path in path_set
                if previous_assertions.get(path, ()) != current_assertions.get(path, ())
            )
        )
        artifact_only_paths = tuple(
            sorted(
                set(artifact_delta_paths)
                - set(structural_delta_paths)
                - set(assertion_changed_paths)
            )
        )
        git_only_paths = tuple(
            sorted(
                path_set
                - set(artifact_delta_paths)
                - set(structural_delta_paths)
                - set(assertion_changed_paths)
                - set(policy_suppressed_paths)
            )
        )

        signals: set[CandidateSignalKind] = set()
        if structural_delta_ids:
            signals.add(CandidateSignalKind.STRUCTURAL_DELTA)
        if assertion_changed_paths:
            signals.add(CandidateSignalKind.AUTHORED_ASSERTION_CHANGE)
        if artifact_only_paths:
            signals.add(CandidateSignalKind.ARTIFACT_DELTA_WITHOUT_EXTRACTED_SIGNAL)
        if git_only_paths:
            signals.add(CandidateSignalKind.GIT_ONLY_CHANGE)
        if policy_suppressed_paths:
            signals.add(CandidateSignalKind.POLICY_SUPPRESSED)

        fully_policy_suppressed = path_set == set(policy_suppressed_paths)
        disposition = (
            CandidateReductionDisposition.SUPPRESS
            if fully_policy_suppressed
            else CandidateReductionDisposition.RETAIN
        )
        if fully_policy_suppressed:
            signals = {CandidateSignalKind.POLICY_SUPPRESSED}
        elif not signals:
            # A persisted GitPathDelta means something changed at the Git layer.
            # If no downstream artifact/assertion/structural signal explains it,
            # retain it rather than manufacturing an equivalence claim.
            signals.add(CandidateSignalKind.GIT_ONLY_CHANGE)
            git_only_paths = paths

        return CandidateFactualReduction(
            candidate_factual_reduction_id=self._reduction_id(
                reduction_run_id,
                candidate.interval_candidate_segment_id,
            ),
            interval_candidate_segment_id=candidate.interval_candidate_segment_id,
            source_id=candidate.source_id,
            previous_source_revision_id=candidate.previous_source_revision_id,
            current_source_revision_id=candidate.current_source_revision_id,
            paths=paths,
            affected_file_plan_ids=affected_file_plan_ids,
            capture_scoped_paths=capture_scoped_paths,
            policy_suppressed_paths=policy_suppressed_paths,
            artifact_delta_ids=artifact_delta_ids,
            artifact_delta_paths=artifact_delta_paths,
            structural_delta_ids=structural_delta_ids,
            structural_delta_paths=structural_delta_paths,
            assertion_changed_paths=assertion_changed_paths,
            artifact_only_paths=artifact_only_paths,
            git_only_paths=git_only_paths,
            signal_kinds=tuple(sorted(signals, key=lambda item: item.value)),
            disposition=disposition,
            diff_run_id=diff_run_id,
            segmentation_run_id=candidate.segmentation_run_id,
            planner_run_id=planner_run_id,
            previous_capture_id=previous_capture_id,
            current_capture_id=current_capture_id,
            previous_extraction_run_id=previous_extraction_run_id,
            current_extraction_run_id=current_extraction_run_id,
            change_run_id=change_run_id,
            reduction_run_id=reduction_run_id,
        )

    def _completed_run(self, run_id: str, run_type: RunType, label: str) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise CandidateFactualReductionError(f"unknown {label} PipelineRun: {run_id}")
        if run.run_type is not run_type or run.finished_at is None:
            raise CandidateFactualReductionError(
                f"{label} requires one completed {run_type.value} PipelineRun"
            )
        return run

    def _diff_summary(self, diff_run_id: str) -> GitPathDiffSummary:
        self._completed_run(diff_run_id, RunType.DIFF, "recursive path diff")
        summaries = tuple(
            item
            for item in self.store.list(GitPathDiffSummary)
            if item.diff_run_id == diff_run_id
        )
        if len(summaries) != 1:
            raise CandidateFactualReductionError(
                "candidate reduction requires exactly one GitPathDiffSummary"
            )
        return summaries[0]

    def _range_summary(self, segmentation_run_id: str) -> CommitRangeSummary:
        summaries = tuple(
            item
            for item in self.store.list(CommitRangeSummary)
            if item.segmentation_run_id == segmentation_run_id
        )
        if len(summaries) != 1:
            raise CandidateFactualReductionError(
                "candidate reduction requires exactly one CommitRangeSummary"
            )
        return summaries[0]

    @staticmethod
    def _validate_delta_generation(
        summary: GitPathDiffSummary,
        deltas: tuple[GitPathDelta, ...],
    ) -> None:
        expected = (
            summary.source_id,
            summary.previous_source_revision_id,
            summary.current_source_revision_id,
            summary.previous_capture_id,
            summary.current_capture_id,
            summary.diff_run_id,
        )
        seen_paths: set[str] = set()
        for item in deltas:
            actual = (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                item.previous_capture_id,
                item.current_capture_id,
                item.diff_run_id,
            )
            if actual != expected:
                raise CandidateFactualReductionError(
                    "GitPathDelta generation provenance disagrees with GitPathDiffSummary"
                )
            if item.path in seen_paths:
                raise CandidateFactualReductionError("diff run contains duplicate Git paths")
            seen_paths.add(item.path)

    @staticmethod
    def _validate_candidate_coverage(
        summary: GitPathDiffSummary,
        deltas: tuple[GitPathDelta, ...],
        candidates: tuple[IntervalCandidateSegment, ...],
    ) -> None:
        delta_by_id = {item.git_path_delta_id: item for item in deltas}
        assigned_ids: list[str] = []
        assigned_paths: list[str] = []
        for candidate in candidates:
            if (
                candidate.source_id,
                candidate.previous_source_revision_id,
                candidate.current_source_revision_id,
            ) != (
                summary.source_id,
                summary.previous_source_revision_id,
                summary.current_source_revision_id,
            ):
                raise CandidateFactualReductionError(
                    "IntervalCandidateSegment provenance disagrees with path diff"
                )
            for delta_id, path in zip(
                candidate.git_path_delta_ids,
                candidate.paths,
                strict=True,
            ):
                delta = delta_by_id.get(delta_id)
                if delta is None or delta.path != path:
                    raise CandidateFactualReductionError(
                        "candidate delta/path membership disagrees with GitPathDelta"
                    )
                assigned_ids.append(delta_id)
                assigned_paths.append(path)
        if len(assigned_ids) != len(set(assigned_ids)):
            raise CandidateFactualReductionError(
                "GitPathDelta is assigned to more than one interval candidate"
            )
        if set(assigned_ids) != set(delta_by_id):
            raise CandidateFactualReductionError(
                "interval candidates do not cover the complete GitPathDelta generation"
            )
        if len(assigned_paths) != len(set(assigned_paths)):
            raise CandidateFactualReductionError(
                "Git path is assigned to more than one interval candidate"
            )

    @staticmethod
    def _validate_plan_coverage(
        summary: GitPathDiffSummary,
        deltas: tuple[GitPathDelta, ...],
        plans: tuple[AffectedFileCapturePlan, ...],
        planner_run_id: str,
    ) -> None:
        delta_by_id = {item.git_path_delta_id: item for item in deltas}
        plan_by_delta: dict[str, AffectedFileCapturePlan] = {}
        for plan in plans:
            delta = delta_by_id.get(plan.git_path_delta_id)
            if delta is None:
                raise CandidateFactualReductionError(
                    "affected-file plan references a foreign GitPathDelta"
                )
            if plan.git_path_delta_id in plan_by_delta:
                raise CandidateFactualReductionError(
                    "affected-file planner produced duplicate plans for one GitPathDelta"
                )
            if (
                plan.source_id,
                plan.previous_source_revision_id,
                plan.current_source_revision_id,
                plan.diff_run_id,
                plan.planner_run_id,
                plan.path,
            ) != (
                summary.source_id,
                summary.previous_source_revision_id,
                summary.current_source_revision_id,
                summary.diff_run_id,
                planner_run_id,
                delta.path,
            ):
                raise CandidateFactualReductionError(
                    "affected-file plan provenance disagrees with GitPathDelta generation"
                )
            plan_by_delta[plan.git_path_delta_id] = plan
        if set(plan_by_delta) != set(delta_by_id):
            raise CandidateFactualReductionError(
                "affected-file plans do not cover the complete GitPathDelta generation"
            )

    @staticmethod
    def _required_paths(
        plans: tuple[AffectedFileCapturePlan, ...],
        *,
        previous: bool,
    ) -> tuple[str, ...]:
        result: list[str] = []
        for plan in plans:
            side = plan.previous if previous else plan.current
            opposite = plan.current if previous else plan.previous
            if CandidateFactualReductionService._requests_path(side, opposite):
                result.append(plan.path)
        return tuple(sorted(result))

    @staticmethod
    def _requests_path(side: CapturePlanSide, opposite: CapturePlanSide) -> bool:
        return (
            side.disposition is CapturePlanDisposition.CAPTURE
            or (
                side.disposition is CapturePlanDisposition.ABSENT
                and opposite.disposition is CapturePlanDisposition.CAPTURE
            )
        )

    def _validate_capture_scope(
        self,
        manifest: CaptureManifest,
        plans: tuple[AffectedFileCapturePlan, ...],
        *,
        previous: bool,
    ) -> None:
        required = self._required_paths(plans, previous=previous)
        by_path = {}
        for reference in manifest.artifacts:
            if reference.source_locator in by_path:
                raise CandidateFactualReductionError(
                    "candidate capture manifest contains duplicate source locators"
                )
            by_path[reference.source_locator] = reference
        if set(by_path) != set(required):
            raise CandidateFactualReductionError(
                "candidate capture manifest does not exactly match affected-file plan scope"
            )

        plan_by_path = {item.path: item for item in plans}
        for path in required:
            plan = plan_by_path[path]
            side = plan.previous if previous else plan.current
            reference = by_path[path]
            if side.disposition is CapturePlanDisposition.CAPTURE:
                if reference.retrieval_status is not RetrievalStatus.CAPTURED:
                    raise CandidateFactualReductionError(
                        f"planned captured path was not captured: {path!r}"
                    )
            elif side.disposition is CapturePlanDisposition.ABSENT:
                if reference.retrieval_status is not RetrievalStatus.MISSING:
                    raise CandidateFactualReductionError(
                        f"planned absent path did not remain missing: {path!r}"
                    )
            else:
                raise CandidateFactualReductionError(
                    "non-capture plan side unexpectedly appeared in capture scope"
                )

    @staticmethod
    def _is_policy_suppressed(plan: AffectedFileCapturePlan) -> bool:
        sides = (plan.previous, plan.current)
        if any(side.disposition is CapturePlanDisposition.CAPTURE for side in sides):
            return False
        return any(side.disposition is CapturePlanDisposition.SUPPRESSED for side in sides)

    def _assertion_signatures(
        self,
        manifest: CaptureManifest,
        extraction_run_id: str,
    ) -> dict[str, tuple[tuple[str, str, str], ...]]:
        artifact_to_path = {
            item.artifact_id: item.source_locator
            for item in manifest.artifacts
            if item.retrieval_status is RetrievalStatus.CAPTURED
        }
        collected: dict[str, list[tuple[str, str, str]]] = {}
        for assertion in self.store.list(SourceAssertion):
            if assertion.run_id != extraction_run_id:
                continue
            path = artifact_to_path.get(assertion.artifact_id)
            if path is None:
                raise CandidateFactualReductionError(
                    "SourceAssertion extraction provenance is outside candidate capture"
                )
            collected.setdefault(path, []).append(
                (
                    assertion.extractor_name,
                    assertion.extractor_version,
                    assertion.statement,
                )
            )
        return {
            path: tuple(sorted(values))
            for path, values in collected.items()
        }

    def _manifest(self, capture_id: str) -> CaptureManifest:
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise CandidateFactualReductionError(f"unknown candidate capture: {capture_id}")
        return manifest

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("candidate reduction clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _reduction_id(run_id: str, candidate_id: str) -> str:
        material = f"candidate-factual-reduction\0{run_id}\0{candidate_id}".encode("utf-8")
        return f"candidate-factual-reduction:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
