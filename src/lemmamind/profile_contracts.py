"""Durable M6-lite architecture-profile and triage contracts.

ArchitectureProfile is revision-bound and derived only from explicit deterministic
EvidenceFact / SourceAssertion generations. TriageAssessment is a deterministic
attention-routing result over one profile plus explicit operational/manual signals.
Neither contract is an architectural interpretation or model-generated judgment.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .contracts import CONTRACT_TYPES, ContractModel, Identifier
from .tracking_contracts import TrackingLevel


class TriageBand(StrEnum):
    IGNORE = "ignore"
    WATCH = "watch"
    REVIEW = "review"
    DEEP_DIVE = "deep_dive"


class TriageSensitivity(StrEnum):
    GOVERNANCE = "governance"
    EXPERIMENT = "experiment"


class TriageReason(StrEnum):
    TRACKING_IGNORED = "tracking_ignored"
    TRACKING_ACTIVE = "tracking_active"
    DOMAIN_MATCH = "domain_match"
    DOMAIN_MISMATCH = "domain_mismatch"
    EVIDENCE_RICH = "evidence_rich"
    PROCESS_RICH = "process_rich"
    WORKFLOW_RICH = "workflow_rich"
    RECENT_STRUCTURAL_CHANGE = "recent_structural_change"
    GOVERNANCE_SENSITIVE = "governance_sensitive"
    EXPERIMENT_SENSITIVE = "experiment_sensitive"
    DEEP_TRACKING = "deep_tracking"


class ArchitectureProfile(ContractModel):
    """Immutable deterministic feature profile for one exact SourceRevision."""

    record_id_field = "architecture_profile_id"

    architecture_profile_id: Identifier
    source_id: Identifier
    source_revision_id: Identifier
    profile_schema_version: Identifier
    profiling_run_id: Identifier

    evidence_run_ids: tuple[Identifier, ...]
    artifact_ids: tuple[Identifier, ...]
    evidence_fact_ids: tuple[Identifier, ...]
    source_assertion_ids: tuple[Identifier, ...]

    evidence_fact_count: int = Field(ge=0)
    source_assertion_count: int = Field(ge=0)
    artifact_count: int = Field(ge=0)
    extractor_families: tuple[Identifier, ...]
    artifact_media_types: tuple[Identifier, ...]
    feature_keys: tuple[Identifier, ...]

    @model_validator(mode="after")
    def validate_counts_and_ordering(self) -> "ArchitectureProfile":
        if self.evidence_fact_count != len(self.evidence_fact_ids):
            raise ValueError("evidence_fact_count must equal evidence_fact_ids length")
        if self.source_assertion_count != len(self.source_assertion_ids):
            raise ValueError("source_assertion_count must equal source_assertion_ids length")
        if self.artifact_count != len(self.artifact_ids):
            raise ValueError("artifact_count must equal artifact_ids length")
        for field_name in (
            "evidence_run_ids",
            "artifact_ids",
            "evidence_fact_ids",
            "source_assertion_ids",
            "extractor_families",
            "artifact_media_types",
            "feature_keys",
        ):
            values = getattr(self, field_name)
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{field_name} must be sorted and duplicate-free")
        if not self.evidence_run_ids:
            raise ValueError("ArchitectureProfile requires at least one evidence run")
        return self


class TriageAssessment(ContractModel):
    """Deterministic V1 attention-routing assessment; not a confidence score."""

    record_id_field = "triage_assessment_id"

    triage_assessment_id: Identifier
    architecture_profile_id: Identifier
    source_id: Identifier
    source_revision_id: Identifier
    triage_run_id: Identifier
    policy_version: Identifier

    tracking_level: TrackingLevel
    tracking_assignment_id: Identifier | None = None
    domain_match: bool
    sensitivity_flags: tuple[TriageSensitivity, ...] = ()
    structural_delta_ids: tuple[Identifier, ...] = ()
    band: TriageBand
    reasons: tuple[TriageReason, ...]

    @model_validator(mode="after")
    def validate_ordering(self) -> "TriageAssessment":
        if tuple(sorted(set(self.sensitivity_flags), key=lambda item: item.value)) != self.sensitivity_flags:
            raise ValueError("sensitivity_flags must be sorted and duplicate-free")
        if tuple(sorted(set(self.structural_delta_ids))) != self.structural_delta_ids:
            raise ValueError("structural_delta_ids must be sorted and duplicate-free")
        if tuple(sorted(set(self.reasons), key=lambda item: item.value)) != self.reasons:
            raise ValueError("reasons must be sorted and duplicate-free")
        return self


CONTRACT_TYPES[ArchitectureProfile.__name__] = ArchitectureProfile
CONTRACT_TYPES[TriageAssessment.__name__] = TriageAssessment

PROFILE_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    ArchitectureProfile.__name__: ArchitectureProfile,
    TriageAssessment.__name__: TriageAssessment,
}
