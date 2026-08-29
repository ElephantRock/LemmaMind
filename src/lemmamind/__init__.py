"""LemmaMind executable contracts and persistence."""

from .candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from .capture_planning_contracts import (
    AffectedFileCapturePlan,
    CapturePlanDisposition,
    CapturePlanReason,
    CapturePlanSide,
)
from .change_contracts import (
    ArtifactDelta,
    ArtifactDeltaType,
    StructuralDelta,
    StructuralDeltaType,
)
from .contracts import CONTRACT_SCHEMA_VERSION
from .interval_segmentation_contracts import (
    CommitPathSnapshot,
    CommitRangeStatus,
    CommitRangeSummary,
    IntervalCandidateSegment,
)
from .path_change_contracts import ChangeSurface, GitPathDelta, GitPathDeltaType
from .profile_contracts import (
    ArchitectureProfile,
    TriageAssessment,
    TriageBand,
    TriageReason,
    TriageSensitivity,
)
from .review_contracts import ReviewFeedback
from .tracking_contracts import RepositoryTrackingAssignment, TrackingLevel

__all__ = [
    "AffectedFileCapturePlan",
    "ArchitectureProfile",
    "ArtifactDelta",
    "ArtifactDeltaType",
    "CandidateFactualReduction",
    "CandidateReductionDisposition",
    "CandidateSignalKind",
    "CapturePlanDisposition",
    "CapturePlanReason",
    "CapturePlanSide",
    "ChangeSurface",
    "CommitPathSnapshot",
    "CommitRangeStatus",
    "CommitRangeSummary",
    "CONTRACT_SCHEMA_VERSION",
    "GitPathDelta",
    "GitPathDeltaType",
    "IntervalCandidateSegment",
    "RepositoryTrackingAssignment",
    "ReviewFeedback",
    "StructuralDelta",
    "StructuralDeltaType",
    "TrackingLevel",
    "TriageAssessment",
    "TriageBand",
    "TriageReason",
    "TriageSensitivity",
]
__version__ = "0.1.0"
