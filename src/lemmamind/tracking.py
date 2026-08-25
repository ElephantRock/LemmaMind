"""M2 governed repository tracking-level history and deterministic policy resolution.

Tracking levels control operational eligibility only. They do not change evidence
truth, validation state, repository relationship, or authorization.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Protocol

from .contracts import Source
from .tracking_contracts import RepositoryTrackingAssignment, TrackingLevel


class TrackingPolicyError(RuntimeError):
    """Tracking history or policy state is incomplete or inconsistent."""


class TrackingConflict(TrackingPolicyError):
    """An immutable tracking timeline would be ambiguously or retroactively changed."""


class TrackingNotAllowed(TrackingPolicyError):
    """The effective tracking level does not permit the requested operation."""


class CaptureDepth(StrEnum):
    NONE = "none"
    METADATA = "metadata"
    SHALLOW = "shallow"
    STRUCTURAL = "structural"
    DEEP = "deep"


class PollingMode(StrEnum):
    NEVER = "never"
    METADATA = "metadata"
    REVISION = "revision"
    CONTINUOUS = "continuous"


class ArtifactClass(StrEnum):
    REPOSITORY_METADATA = "repository_metadata"
    EXPLICIT_FILES = "explicit_files"
    COMMIT_METADATA = "commit_metadata"
    GIT_TREE = "git_tree"
    DETERMINISTIC_STRUCTURE = "deterministic_structure"
    PROCESS_CURRENT = "process_current"
    PROCESS_HISTORY = "process_history"
    WORKFLOW_RUNS = "workflow_runs"


@dataclass(frozen=True)
class TrackingPolicy:
    level: TrackingLevel
    capture_depth: CaptureDepth
    polling_mode: PollingMode
    artifact_classes: frozenset[ArtifactClass]
    process_current_allowed: bool
    process_history_allowed: bool
    reasoning_allowed: bool
    assignment_id: str | None

    @property
    def is_assigned(self) -> bool:
        return self.assignment_id is not None


_POLICY_BY_LEVEL: dict[TrackingLevel, TrackingPolicy] = {
    TrackingLevel.IGNORE: TrackingPolicy(
        level=TrackingLevel.IGNORE,
        capture_depth=CaptureDepth.NONE,
        polling_mode=PollingMode.NEVER,
        artifact_classes=frozenset(),
        process_current_allowed=False,
        process_history_allowed=False,
        reasoning_allowed=False,
        assignment_id=None,
    ),
    TrackingLevel.METADATA_ONLY: TrackingPolicy(
        level=TrackingLevel.METADATA_ONLY,
        capture_depth=CaptureDepth.METADATA,
        polling_mode=PollingMode.METADATA,
        artifact_classes=frozenset({ArtifactClass.REPOSITORY_METADATA}),
        process_current_allowed=False,
        process_history_allowed=False,
        reasoning_allowed=False,
        assignment_id=None,
    ),
    TrackingLevel.SHALLOW: TrackingPolicy(
        level=TrackingLevel.SHALLOW,
        capture_depth=CaptureDepth.SHALLOW,
        polling_mode=PollingMode.REVISION,
        artifact_classes=frozenset(
            {
                ArtifactClass.REPOSITORY_METADATA,
                ArtifactClass.EXPLICIT_FILES,
                ArtifactClass.COMMIT_METADATA,
            }
        ),
        process_current_allowed=False,
        process_history_allowed=False,
        reasoning_allowed=False,
        assignment_id=None,
    ),
    TrackingLevel.STRUCTURAL: TrackingPolicy(
        level=TrackingLevel.STRUCTURAL,
        capture_depth=CaptureDepth.STRUCTURAL,
        polling_mode=PollingMode.REVISION,
        artifact_classes=frozenset(
            {
                ArtifactClass.REPOSITORY_METADATA,
                ArtifactClass.EXPLICIT_FILES,
                ArtifactClass.COMMIT_METADATA,
                ArtifactClass.GIT_TREE,
                ArtifactClass.DETERMINISTIC_STRUCTURE,
            }
        ),
        process_current_allowed=False,
        process_history_allowed=False,
        reasoning_allowed=True,
        assignment_id=None,
    ),
    TrackingLevel.DEEP: TrackingPolicy(
        level=TrackingLevel.DEEP,
        capture_depth=CaptureDepth.DEEP,
        polling_mode=PollingMode.REVISION,
        artifact_classes=frozenset(ArtifactClass),
        process_current_allowed=True,
        process_history_allowed=True,
        reasoning_allowed=True,
        assignment_id=None,
    ),
    TrackingLevel.CONTINUOUS: TrackingPolicy(
        level=TrackingLevel.CONTINUOUS,
        capture_depth=CaptureDepth.DEEP,
        polling_mode=PollingMode.CONTINUOUS,
        artifact_classes=frozenset(ArtifactClass),
        process_current_allowed=True,
        process_history_allowed=True,
        reasoning_allowed=True,
        assignment_id=None,
    ),
}

_CAPTURE_RANK = {
    CaptureDepth.NONE: 0,
    CaptureDepth.METADATA: 1,
    CaptureDepth.SHALLOW: 2,
    CaptureDepth.STRUCTURAL: 3,
    CaptureDepth.DEEP: 4,
}


class TrackingStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put(self, record): ...


class RepositoryTrackingService:
    """Append tracking assignments and resolve the effective operational policy.

    V1 accepts only immediately effective new assignments. Scheduled future changes
    and retroactive corrections need explicit cancellation/correction semantics and
    are therefore deferred rather than smuggled into this append-only timeline.
    Exact replay of an existing assignment remains idempotent.
    """

    def __init__(
        self,
        store: TrackingStore,
        *,
        policy_version: str = "repository-tracking.v1",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.policy_version = policy_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def assign_level(
        self,
        source_id: str,
        level: TrackingLevel,
        *,
        assigned_by: str,
        reason: str,
        effective_at: datetime | None = None,
    ) -> RepositoryTrackingAssignment:
        source = self.store.get(Source, source_id)
        if source is None:
            raise TrackingPolicyError(f"unknown Source: {source_id}")

        recorded_at = self._aware_now()
        effective = effective_at or recorded_at
        if effective.tzinfo is None or effective.utcoffset() is None:
            raise TrackingPolicyError("tracking effective_at must be timezone-aware")

        assigned_by = assigned_by.strip()
        reason = reason.strip()
        if not assigned_by:
            raise TrackingPolicyError("assigned_by must not be empty")
        if not reason:
            raise TrackingPolicyError("reason must not be empty")

        history = self.history(source_id)
        same_effective = [item for item in history if item.effective_at == effective]
        if same_effective:
            if len(same_effective) != 1:
                raise TrackingConflict("tracking history has multiple assignments at one effective_at")
            existing = same_effective[0]
            if (
                existing.level is level
                and existing.assigned_by == assigned_by
                and existing.reason == reason
                and existing.policy_version == self.policy_version
            ):
                return existing
            raise TrackingConflict(
                "tracking effective_at is already occupied; append a later immediate change"
            )

        if effective != recorded_at:
            raise TrackingConflict(
                "repository-tracking.v1 permits only immediately effective new assignments; "
                "future scheduling and backdating are deferred"
            )
        if effective < source.first_seen_at:
            raise TrackingConflict("tracking level cannot become effective before Source first_seen_at")

        latest = history[-1] if history else None
        if latest is not None and recorded_at < latest.recorded_at:
            raise TrackingConflict("tracking clock moved backward relative to existing history")

        assignment = RepositoryTrackingAssignment(
            tracking_assignment_id=self._assignment_id(source_id, effective),
            source_id=source_id,
            level=level,
            effective_at=effective,
            recorded_at=recorded_at,
            assigned_by=assigned_by,
            reason=reason,
            policy_version=self.policy_version,
            supersedes_tracking_assignment_id=(
                latest.tracking_assignment_id if latest is not None else None
            ),
        )
        self.store.put(assignment)
        return assignment

    def history(self, source_id: str) -> tuple[RepositoryTrackingAssignment, ...]:
        records = [
            item
            for item in self.store.list(RepositoryTrackingAssignment)
            if item.source_id == source_id
        ]
        records.sort(
            key=lambda item: (
                item.effective_at,
                item.recorded_at,
                item.tracking_assignment_id,
            )
        )
        return tuple(records)

    def latest_effective(
        self,
        source_id: str,
        *,
        as_of: datetime | None = None,
    ) -> RepositoryTrackingAssignment | None:
        if self.store.get(Source, source_id) is None:
            raise TrackingPolicyError(f"unknown Source: {source_id}")
        point = as_of or self._aware_now()
        if point.tzinfo is None or point.utcoffset() is None:
            raise TrackingPolicyError("tracking as_of must be timezone-aware")
        effective = [item for item in self.history(source_id) if item.effective_at <= point]
        if not effective:
            return None
        latest_time = effective[-1].effective_at
        tied = [item for item in effective if item.effective_at == latest_time]
        if len(tied) != 1:
            raise TrackingConflict("tracking history is ambiguous at latest effective_at")
        return tied[0]

    def policy_for(
        self,
        source_id: str,
        *,
        as_of: datetime | None = None,
    ) -> TrackingPolicy:
        assignment = self.latest_effective(source_id, as_of=as_of)
        level = assignment.level if assignment is not None else TrackingLevel.IGNORE
        template = _POLICY_BY_LEVEL[level]
        return TrackingPolicy(
            level=template.level,
            capture_depth=template.capture_depth,
            polling_mode=template.polling_mode,
            artifact_classes=template.artifact_classes,
            process_current_allowed=template.process_current_allowed,
            process_history_allowed=template.process_history_allowed,
            reasoning_allowed=template.reasoning_allowed,
            assignment_id=(assignment.tracking_assignment_id if assignment is not None else None),
        )

    def require_capture_depth(
        self,
        source_id: str,
        minimum: CaptureDepth,
        *,
        as_of: datetime | None = None,
    ) -> TrackingPolicy:
        policy = self.policy_for(source_id, as_of=as_of)
        if _CAPTURE_RANK[policy.capture_depth] < _CAPTURE_RANK[minimum]:
            raise TrackingNotAllowed(
                f"tracking level {policy.level.value} permits {policy.capture_depth.value} capture; "
                f"{minimum.value} is required"
            )
        return policy

    def require_artifact_class(
        self,
        source_id: str,
        artifact_class: ArtifactClass,
        *,
        as_of: datetime | None = None,
    ) -> TrackingPolicy:
        policy = self.policy_for(source_id, as_of=as_of)
        if artifact_class not in policy.artifact_classes:
            raise TrackingNotAllowed(
                f"tracking level {policy.level.value} does not permit artifact class "
                f"{artifact_class.value}"
            )
        return policy

    def require_process_current(
        self,
        source_id: str,
        *,
        as_of: datetime | None = None,
    ) -> TrackingPolicy:
        policy = self.policy_for(source_id, as_of=as_of)
        if not policy.process_current_allowed:
            raise TrackingNotAllowed(
                f"tracking level {policy.level.value} does not permit current process capture"
            )
        return policy

    def require_process_history(
        self,
        source_id: str,
        *,
        as_of: datetime | None = None,
    ) -> TrackingPolicy:
        policy = self.policy_for(source_id, as_of=as_of)
        if not policy.process_history_allowed:
            raise TrackingNotAllowed(
                f"tracking level {policy.level.value} does not permit process-history capture"
            )
        return policy

    def require_reasoning(
        self,
        source_id: str,
        *,
        as_of: datetime | None = None,
    ) -> TrackingPolicy:
        policy = self.policy_for(source_id, as_of=as_of)
        if not policy.reasoning_allowed:
            raise TrackingNotAllowed(
                f"tracking level {policy.level.value} does not permit reasoning eligibility"
            )
        return policy

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise TrackingPolicyError("tracking clock must return a timezone-aware datetime")
        return value

    def _assignment_id(self, source_id: str, effective_at: datetime) -> str:
        payload = (
            f"{source_id}\0{effective_at.isoformat()}\0{self.policy_version}"
        ).encode("utf-8")
        return f"tracking:{hashlib.sha256(payload).hexdigest()}"
