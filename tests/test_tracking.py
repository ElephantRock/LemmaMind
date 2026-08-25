from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import Source, SourceKind, SourceRole
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking import (
    ArtifactClass,
    CaptureDepth,
    PollingMode,
    RepositoryTrackingService,
    TrackingConflict,
    TrackingNotAllowed,
)
from lemmamind.tracking_contracts import RepositoryTrackingAssignment, TrackingLevel

T0 = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def seed_source(store: SQLiteContractStore, source_id: str = "github:42") -> Source:
    source = Source(
        source_id=source_id,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.UNKNOWN,
        canonical_locator="https://github.com/Acme/Repo",
        first_seen_at=T0,
        last_seen_at=T0,
    )
    store.put(source)
    return source


def make_service(tmp_path, *, now: datetime = T0 + timedelta(hours=1)):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source = seed_source(store)
    clock = Clock(now)
    service = RepositoryTrackingService(store, clock=clock)
    return store, source, clock, service


def test_unassigned_source_fails_closed_without_fabricating_history(tmp_path) -> None:
    store, source, _, service = make_service(tmp_path)

    policy = service.policy_for(source.source_id)

    assert policy.level is TrackingLevel.IGNORE
    assert policy.capture_depth is CaptureDepth.NONE
    assert policy.polling_mode is PollingMode.NEVER
    assert policy.assignment_id is None
    assert not policy.is_assigned
    assert store.list(RepositoryTrackingAssignment) == []
    with pytest.raises(TrackingNotAllowed):
        service.require_capture_depth(source.source_id, CaptureDepth.SHALLOW)
    with pytest.raises(TrackingNotAllowed):
        service.require_reasoning(source.source_id)


def test_assignments_are_append_only_and_latest_effective_is_time_aware(tmp_path) -> None:
    _, source, clock, service = make_service(tmp_path)
    first_effective = T0 + timedelta(hours=1)
    second_effective = T0 + timedelta(hours=3)

    first = service.assign_level(
        source.source_id,
        TrackingLevel.SHALLOW,
        assigned_by="operator:test",
        reason="initial repository capture",
        effective_at=first_effective,
    )
    clock.value = T0 + timedelta(hours=2)
    second = service.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="operator:test",
        reason="promote after useful deterministic evidence",
        effective_at=second_effective,
    )

    assert second.supersedes_tracking_assignment_id == first.tracking_assignment_id
    assert service.history(source.source_id) == (first, second)
    assert service.latest_effective(
        source.source_id,
        as_of=T0 + timedelta(hours=2, minutes=30),
    ) == first
    assert service.latest_effective(
        source.source_id,
        as_of=T0 + timedelta(hours=4),
    ) == second


def test_exact_assignment_replay_is_idempotent(tmp_path) -> None:
    store, source, clock, service = make_service(tmp_path)
    effective = T0 + timedelta(hours=1)

    first = service.assign_level(
        source.source_id,
        TrackingLevel.DEEP,
        assigned_by="operator:test",
        reason="deep investigation",
        effective_at=effective,
    )
    clock.value = T0 + timedelta(hours=5)
    replay = service.assign_level(
        source.source_id,
        TrackingLevel.DEEP,
        assigned_by="operator:test",
        reason="deep investigation",
        effective_at=effective,
    )

    assert replay == first
    assert len(store.list(RepositoryTrackingAssignment)) == 1


def test_same_effective_time_cannot_be_rewritten(tmp_path) -> None:
    _, source, _, service = make_service(tmp_path)
    effective = T0 + timedelta(hours=1)
    service.assign_level(
        source.source_id,
        TrackingLevel.SHALLOW,
        assigned_by="operator:test",
        reason="initial",
        effective_at=effective,
    )

    with pytest.raises(TrackingConflict):
        service.assign_level(
            source.source_id,
            TrackingLevel.DEEP,
            assigned_by="operator:test",
            reason="rewrite",
            effective_at=effective,
        )


def test_backdated_change_is_rejected(tmp_path) -> None:
    _, source, _, service = make_service(tmp_path, now=T0 + timedelta(hours=5))
    service.assign_level(
        source.source_id,
        TrackingLevel.DEEP,
        assigned_by="operator:test",
        reason="deep",
        effective_at=T0 + timedelta(hours=4),
    )

    with pytest.raises(TrackingConflict):
        service.assign_level(
            source.source_id,
            TrackingLevel.SHALLOW,
            assigned_by="operator:test",
            reason="retroactive downgrade",
            effective_at=T0 + timedelta(hours=2),
        )


def test_tracking_contract_roundtrips_through_generic_untyped_store(tmp_path) -> None:
    store, source, _, service = make_service(tmp_path)
    assignment = service.assign_level(
        source.source_id,
        TrackingLevel.METADATA_ONLY,
        assigned_by="operator:test",
        reason="metadata watch",
    )

    restored = store.get_untyped("RepositoryTrackingAssignment", assignment.record_id)

    assert restored == assignment
    assert isinstance(restored, RepositoryTrackingAssignment)


@pytest.mark.parametrize(
    ("level", "capture", "polling", "reasoning", "process_current", "process_history"),
    [
        (TrackingLevel.IGNORE, CaptureDepth.NONE, PollingMode.NEVER, False, False, False),
        (
            TrackingLevel.METADATA_ONLY,
            CaptureDepth.METADATA,
            PollingMode.METADATA,
            False,
            False,
            False,
        ),
        (TrackingLevel.SHALLOW, CaptureDepth.SHALLOW, PollingMode.REVISION, False, False, False),
        (
            TrackingLevel.STRUCTURAL,
            CaptureDepth.STRUCTURAL,
            PollingMode.REVISION,
            True,
            False,
            False,
        ),
        (TrackingLevel.DEEP, CaptureDepth.DEEP, PollingMode.REVISION, True, True, True),
        (
            TrackingLevel.CONTINUOUS,
            CaptureDepth.DEEP,
            PollingMode.CONTINUOUS,
            True,
            True,
            True,
        ),
    ],
)
def test_tracking_level_policy_matrix(
    tmp_path,
    level,
    capture,
    polling,
    reasoning,
    process_current,
    process_history,
) -> None:
    _, source, _, service = make_service(tmp_path)
    service.assign_level(
        source.source_id,
        level,
        assigned_by="operator:test",
        reason=f"set level {level.value}",
    )

    policy = service.policy_for(source.source_id)

    assert policy.capture_depth is capture
    assert policy.polling_mode is polling
    assert policy.reasoning_allowed is reasoning
    assert policy.process_current_allowed is process_current
    assert policy.process_history_allowed is process_history
    if level is TrackingLevel.METADATA_ONLY:
        assert policy.artifact_classes == frozenset({ArtifactClass.REPOSITORY_METADATA})
    if level is TrackingLevel.DEEP:
        assert ArtifactClass.PROCESS_HISTORY in policy.artifact_classes
