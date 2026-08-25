"""Durable M2 repository tracking-level contracts.

Tracking is operational policy, not epistemic evidence. Assignments are immutable
history records that say which level becomes effective for one canonical Source.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import AwareDatetime

from .contracts import CONTRACT_TYPES, ContractModel, Identifier


class TrackingLevel(StrEnum):
    """Roadmap M2 repository tracking levels."""

    IGNORE = "0"
    METADATA_ONLY = "1"
    SHALLOW = "2"
    STRUCTURAL = "3"
    DEEP = "4"
    CONTINUOUS = "5"


class RepositoryTrackingAssignment(ContractModel):
    """One immutable governed tracking-level assignment for a Source."""

    record_id_field = "tracking_assignment_id"

    tracking_assignment_id: Identifier
    source_id: Identifier
    level: TrackingLevel
    effective_at: AwareDatetime
    recorded_at: AwareDatetime
    assigned_by: Identifier
    reason: Identifier
    policy_version: Identifier
    supersedes_tracking_assignment_id: Identifier | None = None


# Register the additive M2 contract with the generic typed persistence registry.
# Package import loads this module, so get_untyped() can reconstruct it without
# changing the frozen M0 contract module merely to add one milestone-local type.
CONTRACT_TYPES[RepositoryTrackingAssignment.__name__] = RepositoryTrackingAssignment

TRACKING_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    RepositoryTrackingAssignment.__name__: RepositoryTrackingAssignment,
}
