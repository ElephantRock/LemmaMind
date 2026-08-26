"""Deterministic affected-file capture planning over exact ``GitPathDelta`` records.

The planner converts factual path changes into an auditable byte-capture scope.
It performs no provider calls, repository checkout, source execution, semantic
ranking, or model inference. Generated/vendored blobs and blobs above the fixed
v1 size ceiling are explicitly suppressed rather than silently omitted; unknown
surfaces remain capture eligible.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .capture_planning_contracts import (
    AffectedFileCapturePlan,
    CapturePlanDisposition,
    CapturePlanReason,
    CapturePlanSide,
)
from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureManifest,
    PipelineRun,
    RunType,
    SourceRevision,
)
from .path_change_contracts import ChangeSurface, GitPathDelta, GitPathDeltaType
from .tracking import ArtifactClass, CaptureDepth, RepositoryTrackingService

MAX_CAPTURE_BLOB_BYTES_V1 = 1_000_000
_SUPPRESSED_SURFACES_V1 = {
    ChangeSurface.GENERATED: CapturePlanReason.GENERATED_SURFACE,
    ChangeSurface.VENDORED: CapturePlanReason.VENDORED_SURFACE,
}


class AffectedFilePlanningError(RuntimeError):
    """Persisted path-delta evidence cannot produce one deterministic capture plan."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class AffectedFilePlanningResult:
    diff_run_id: str
    plans: tuple[AffectedFileCapturePlan, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.plans, self.run)

    @property
    def previous_capture_paths(self) -> tuple[str, ...]:
        return self._capture_paths(previous=True)

    @property
    def current_capture_paths(self) -> tuple[str, ...]:
        return self._capture_paths(previous=False)

    @property
    def suppressed_paths(self) -> tuple[str, ...]:
        return tuple(
            plan.path
            for plan in self.plans
            if (
                plan.previous.disposition is CapturePlanDisposition.SUPPRESSED
                or plan.current.disposition is CapturePlanDisposition.SUPPRESSED
            )
        )

    def _capture_paths(self, *, previous: bool) -> tuple[str, ...]:
        paths: list[str] = []
        for plan in self.plans:
            side = plan.previous if previous else plan.current
            opposite = plan.current if previous else plan.previous
            if side.disposition is CapturePlanDisposition.CAPTURE:
                paths.append(plan.path)
            elif (
                side.disposition is CapturePlanDisposition.ABSENT
                and opposite.disposition is CapturePlanDisposition.CAPTURE
            ):
                # Request the path on the absent revision too so the eventual
                # explicit-file capture can retain a MISSING state rather than
                # silently changing capture scope for an add/remove transition.
                paths.append(plan.path)
        return tuple(sorted(paths))


class AffectedFileCapturePlanner:
    """Plan bounded exact-file capture from one persisted recursive diff run."""

    def __init__(
        self,
        store: ContractStore,
        tracking: RepositoryTrackingService,
        *,
        policy_version: str = "affected-file-plan.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.tracking = tracking
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def plan_diff(self, diff_run_id: str) -> AffectedFilePlanningResult:
        started_at = self._aware_now()
        diff_run = self.store.get(PipelineRun, diff_run_id)
        if diff_run is None:
            raise KeyError(f"unknown diff PipelineRun: {diff_run_id}")
        if diff_run.run_type is not RunType.DIFF or diff_run.finished_at is None:
            raise AffectedFilePlanningError(
                "affected-file planning requires one completed DIFF PipelineRun"
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
        if not deltas:
            raise AffectedFilePlanningError("diff run contains no GitPathDelta records")
        self._validate_delta_generation(deltas)

        first = deltas[0]
        previous_revision = self._revision(first.previous_source_revision_id)
        current_revision = self._revision(first.current_source_revision_id)
        if previous_revision.source_id != first.source_id or current_revision.source_id != first.source_id:
            raise AffectedFilePlanningError("GitPathDelta revision/source provenance disagrees")
        if previous_revision.observed_at > current_revision.observed_at:
            raise AffectedFilePlanningError(
                "previous SourceRevision must not be newer than current SourceRevision"
            )

        previous_manifest = self._manifest(first.previous_capture_id)
        current_manifest = self._manifest(first.current_capture_id)
        if previous_manifest.source_revision_id != previous_revision.source_revision_id:
            raise AffectedFilePlanningError(
                "previous GitPathDelta capture does not bind to previous SourceRevision"
            )
        if current_manifest.source_revision_id != current_revision.source_revision_id:
            raise AffectedFilePlanningError(
                "current GitPathDelta capture does not bind to current SourceRevision"
            )
        if previous_manifest.captured_at > current_manifest.captured_at:
            raise AffectedFilePlanningError(
                "previous CaptureManifest must not be newer than current CaptureManifest"
            )

        tracking_policy = self.tracking.require_capture_depth(
            first.source_id,
            CaptureDepth.SHALLOW,
        )
        if ArtifactClass.EXPLICIT_FILES not in tracking_policy.artifact_classes:
            raise AffectedFilePlanningError(
                "effective tracking policy does not permit explicit-file capture"
            )
        if tracking_policy.assignment_id is None:
            raise AffectedFilePlanningError(
                "capture-eligible tracking policy must have an assignment identity"
            )

        run_id = f"run:affected-file-plan:{self.id_factory()}"
        plans = tuple(
            self._plan_delta(
                delta,
                run_id=run_id,
                tracking_assignment_id=tracking_policy.assignment_id,
                tracking_level=tracking_policy.level.value,
            )
            for delta in deltas
        )

        inputs_hash = self._digest_json(
            {
                "diff_run_id": diff_run_id,
                "path_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in deltas
                ],
                "tracking_assignment_id": tracking_policy.assignment_id,
                "tracking_level": tracking_policy.level.value,
                "max_capture_blob_bytes": MAX_CAPTURE_BLOB_BYTES_V1,
                "suppressed_surfaces": sorted(
                    surface.value for surface in _SUPPRESSED_SURFACES_V1
                ),
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            [plan.model_dump(mode="json", by_alias=True) for plan in plans]
        )
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.OTHER,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = AffectedFilePlanningResult(diff_run_id, plans, run)
        self.store.put_many(result.records())
        return result

    def _validate_delta_generation(self, deltas: tuple[GitPathDelta, ...]) -> None:
        generations = {
            (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                item.previous_capture_id,
                item.current_capture_id,
            )
            for item in deltas
        }
        if len(generations) != 1:
            raise AffectedFilePlanningError(
                "one diff run must contain one SourceRevision/capture pair"
            )
        paths = [item.path for item in deltas]
        if len(paths) != len(set(paths)):
            raise AffectedFilePlanningError("diff run contains duplicate Git paths")

    def _revision(self, revision_id: str) -> SourceRevision:
        revision = self.store.get(SourceRevision, revision_id)
        if revision is None:
            raise AffectedFilePlanningError(
                f"GitPathDelta references missing SourceRevision: {revision_id}"
            )
        return revision

    def _manifest(self, capture_id: str) -> CaptureManifest:
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise AffectedFilePlanningError(
                f"GitPathDelta references missing CaptureManifest: {capture_id}"
            )
        return manifest

    def _plan_delta(
        self,
        delta: GitPathDelta,
        *,
        run_id: str,
        tracking_assignment_id: str,
        tracking_level: str,
    ) -> AffectedFileCapturePlan:
        suppress_large_modified_pair = (
            delta.change_type is GitPathDeltaType.MODIFIED
            and any(
                size is not None and size > MAX_CAPTURE_BLOB_BYTES_V1
                for size in (delta.previous_size, delta.current_size)
            )
        )
        previous = self._plan_side(
            delta.previous_source_revision_id,
            delta.surface,
            entry_type=delta.previous_entry_type,
            object_sha=delta.previous_object_sha,
            size=delta.previous_size,
            force_large_suppression=suppress_large_modified_pair,
        )
        current = self._plan_side(
            delta.current_source_revision_id,
            delta.surface,
            entry_type=delta.current_entry_type,
            object_sha=delta.current_object_sha,
            size=delta.current_size,
            force_large_suppression=suppress_large_modified_pair,
        )
        return AffectedFileCapturePlan(
            affected_file_plan_id=self._plan_id(run_id, delta.git_path_delta_id),
            git_path_delta_id=delta.git_path_delta_id,
            source_id=delta.source_id,
            previous_source_revision_id=delta.previous_source_revision_id,
            current_source_revision_id=delta.current_source_revision_id,
            path=delta.path,
            surface=delta.surface,
            previous=previous,
            current=current,
            tracking_assignment_id=tracking_assignment_id,
            tracking_level=tracking_level,
            diff_run_id=delta.diff_run_id,
            planner_run_id=run_id,
        )

    @staticmethod
    def _plan_side(
        source_revision_id: str,
        surface: ChangeSurface,
        *,
        entry_type: str | None,
        object_sha: str | None,
        size: int | None,
        force_large_suppression: bool = False,
    ) -> CapturePlanSide:
        if entry_type is None and object_sha is None:
            if size is not None:
                raise AffectedFilePlanningError("absent Git path side cannot carry size")
            return CapturePlanSide(
                source_revision_id=source_revision_id,
                disposition=CapturePlanDisposition.ABSENT,
                reason=CapturePlanReason.PATH_ABSENT,
            )
        if entry_type is None or object_sha is None:
            raise AffectedFilePlanningError(
                "Git path side has incomplete entry type/object provenance"
            )
        if entry_type == "tree":
            return CapturePlanSide(
                source_revision_id=source_revision_id,
                disposition=CapturePlanDisposition.NON_FILE,
                reason=CapturePlanReason.DIRECTORY_ENTRY,
                entry_type=entry_type,
                object_sha=object_sha,
                size=size,
            )
        if entry_type == "commit":
            return CapturePlanSide(
                source_revision_id=source_revision_id,
                disposition=CapturePlanDisposition.NON_FILE,
                reason=CapturePlanReason.SUBMODULE_POINTER,
                entry_type=entry_type,
                object_sha=object_sha,
                size=size,
            )
        if entry_type != "blob":
            raise AffectedFilePlanningError(f"unsupported Git entry type: {entry_type}")

        surface_reason = _SUPPRESSED_SURFACES_V1.get(surface)
        if surface_reason is not None:
            return CapturePlanSide(
                source_revision_id=source_revision_id,
                disposition=CapturePlanDisposition.SUPPRESSED,
                reason=surface_reason,
                entry_type=entry_type,
                object_sha=object_sha,
                size=size,
            )
        if force_large_suppression or (
            size is not None and size > MAX_CAPTURE_BLOB_BYTES_V1
        ):
            return CapturePlanSide(
                source_revision_id=source_revision_id,
                disposition=CapturePlanDisposition.SUPPRESSED,
                reason=CapturePlanReason.LARGE_BLOB,
                entry_type=entry_type,
                object_sha=object_sha,
                size=size,
            )
        return CapturePlanSide(
            source_revision_id=source_revision_id,
            disposition=CapturePlanDisposition.CAPTURE,
            reason=CapturePlanReason.ELIGIBLE_BLOB,
            entry_type=entry_type,
            object_sha=object_sha,
            size=size,
        )

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("affected-file planning clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _plan_id(run_id: str, git_path_delta_id: str) -> str:
        material = f"affected-file-plan\0{run_id}\0{git_path_delta_id}".encode("utf-8")
        return f"affected-file-plan:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
