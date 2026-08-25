"""Tracking-aware adapters for existing capture and reasoning services.

The original services remain unchanged. These adapters add one M2 operational
precondition: the latest effective tracking policy must permit the requested path.
"""
from __future__ import annotations

from .contracts import SourceRevision
from .git_commit import GitHubCommitCaptureService
from .git_tree import GitHubRootTreeCaptureService
from .github_process import GitHubProcessCaptureService
from .github_process_events import GitHubProcessEventCaptureService
from .github_repository_metadata import GitHubRepositoryMetadataCaptureService
from .github_workflow import GitHubWorkflowCaptureService
from .observations import ObservationConstructionService
from .registry_aware_capture import RegistryAwareGitHubCaptureService
from .tracking import ArtifactClass, CaptureDepth, RepositoryTrackingService


class _TrackingAwareRevisionService:
    """Shared SourceRevision-to-Source tracking lookup for capture adapters."""

    tracking: RepositoryTrackingService

    def _tracked_source_id(self, source_revision_id: str) -> str | None:
        revision = self.store.get(SourceRevision, source_revision_id)
        return revision.source_id if revision is not None else None


class TrackingAwareGitHubRepositoryMetadataCaptureService(
    _TrackingAwareRevisionService,
    GitHubRepositoryMetadataCaptureService,
):
    """Require metadata tracking before repository-metadata snapshot capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_metadata(self, source_revision_id):
        source_id = self._tracked_source_id(source_revision_id)
        if source_id is not None:
            self.tracking.require_capture_depth(source_id, CaptureDepth.METADATA)
            self.tracking.require_artifact_class(
                source_id,
                ArtifactClass.REPOSITORY_METADATA,
            )
        return super().capture_metadata(source_revision_id)


class TrackingAwareGitHubCaptureService(RegistryAwareGitHubCaptureService):
    """Require level >= 2 before capturing explicit repository files."""

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


class TrackingAwareGitHubCommitCaptureService(
    _TrackingAwareRevisionService,
    GitHubCommitCaptureService,
):
    """Require shallow-or-deeper tracking before commit-metadata capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_commit(self, source_revision_id):
        source_id = self._tracked_source_id(source_revision_id)
        if source_id is not None:
            self.tracking.require_capture_depth(source_id, CaptureDepth.SHALLOW)
            self.tracking.require_artifact_class(source_id, ArtifactClass.COMMIT_METADATA)
        return super().capture_commit(source_revision_id)


class TrackingAwareGitHubRootTreeCaptureService(
    _TrackingAwareRevisionService,
    GitHubRootTreeCaptureService,
):
    """Require structural-or-deeper tracking before root-tree capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_root_tree(self, source_revision_id):
        source_id = self._tracked_source_id(source_revision_id)
        if source_id is not None:
            self.tracking.require_capture_depth(source_id, CaptureDepth.STRUCTURAL)
            self.tracking.require_artifact_class(source_id, ArtifactClass.GIT_TREE)
        return super().capture_root_tree(source_revision_id)


class TrackingAwareGitHubProcessCaptureService(
    _TrackingAwareRevisionService,
    GitHubProcessCaptureService,
):
    """Require deep tracking before current issue/PR snapshot capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_process(self, source_revision_id, refs):
        source_id = self._tracked_source_id(source_revision_id)
        if source_id is not None:
            self.tracking.require_process_current(source_id)
            self.tracking.require_artifact_class(source_id, ArtifactClass.PROCESS_CURRENT)
        return super().capture_process(source_revision_id, refs)


class TrackingAwareGitHubProcessEventCaptureService(
    _TrackingAwareRevisionService,
    GitHubProcessEventCaptureService,
):
    """Require deep tracking before durable issue-event history capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_issue_events(self, source_revision_id, issue_numbers):
        source_id = self._tracked_source_id(source_revision_id)
        if source_id is not None:
            self.tracking.require_process_history(source_id)
            self.tracking.require_artifact_class(source_id, ArtifactClass.PROCESS_HISTORY)
        return super().capture_issue_events(source_revision_id, issue_numbers)


class TrackingAwareGitHubWorkflowCaptureService(
    _TrackingAwareRevisionService,
    GitHubWorkflowCaptureService,
):
    """Require deep tracking before workflow-run evidence capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_run(self, source_revision_id, run_id):
        source_id = self._tracked_source_id(source_revision_id)
        if source_id is not None:
            self.tracking.require_capture_depth(source_id, CaptureDepth.DEEP)
            self.tracking.require_artifact_class(source_id, ArtifactClass.WORKFLOW_RUNS)
        return super().capture_run(source_revision_id, run_id)


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
