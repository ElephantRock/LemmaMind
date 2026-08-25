"""Tracking-aware adapters for existing capture and reasoning services.

The original services remain unchanged. These adapters add one M2 operational
precondition: the latest effective tracking policy must permit the requested path.
"""
from __future__ import annotations

from .contracts import SourceRevision
from .github_process import GitHubProcessCaptureService
from .github_process_events import GitHubProcessEventCaptureService
from .observations import ObservationConstructionService
from .registry_aware_capture import RegistryAwareGitHubCaptureService
from .tracking import ArtifactClass, CaptureDepth, RepositoryTrackingService


class TrackingAwareGitHubCaptureService(RegistryAwareGitHubCaptureService):
    """Require level >= 2 before capturing repository files."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def _stable_source(self, source_id, canonical_locator, source_role, observed_at):
        self.tracking.require_capture_depth(source_id, CaptureDepth.SHALLOW)
        self.tracking.require_artifact_class(source_id, ArtifactClass.EXPLICIT_FILES)
        return super()._stable_source(
            source_id,
            canonical_locator,
            source_role,
            observed_at,
        )


class TrackingAwareGitHubProcessCaptureService(GitHubProcessCaptureService):
    """Require deep tracking before current issue/PR snapshot capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_process(self, source_revision_id, refs):
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is not None:
            self.tracking.require_process_current(revision.source_id)
            self.tracking.require_artifact_class(
                revision.source_id,
                ArtifactClass.PROCESS_CURRENT,
            )
        return super().capture_process(source_revision_id, refs)


class TrackingAwareGitHubProcessEventCaptureService(GitHubProcessEventCaptureService):
    """Require deep tracking before durable issue-event history capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_issue_events(self, source_revision_id, issue_numbers):
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is not None:
            self.tracking.require_process_history(revision.source_id)
            self.tracking.require_artifact_class(
                revision.source_id,
                ArtifactClass.PROCESS_HISTORY,
            )
        return super().capture_issue_events(source_revision_id, issue_numbers)


class TrackingAwareObservationConstructionService(ObservationConstructionService):
    """Require structural-or-deeper tracking before source-local reasoning."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def create_candidate(self, **kwargs):
        supports = tuple(kwargs.get("supports", ()))
        resolved_revisions: set[str] = set()
        for support in supports:
            revisions = self._resolve_support_revisions(
                support,
                seen_observations=frozenset(),
            )
            resolved_revisions.update(revisions)
        if len(resolved_revisions) == 1:
            source_revision_id = next(iter(resolved_revisions))
            revision = self.store.get(SourceRevision, source_revision_id)
            if revision is not None:
                self.tracking.require_reasoning(revision.source_id)
        return super().create_candidate(**kwargs)
