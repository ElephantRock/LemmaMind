"""Versioned contracts selected from the LemmaMind golden corpus.

The module began as the M0 reproducible-evidence spine. Later corpus-selected
vertical slices add only the contracts required by demonstrated cases and roadmap
gates: M8-lite Pattern objects and M1 discovery lineage are additive here. Cohort,
prevalence, tension, insight, embedding, and autonomous reasoning objects remain
deferred until real cases require them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

CONTRACT_SCHEMA_VERSION = "lemmamind.m0.v1"

Identifier = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
GitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
ContentDigest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]


class ContractModel(BaseModel):
    """Immutable, strict base model for persisted LemmaMind contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[CONTRACT_SCHEMA_VERSION] = CONTRACT_SCHEMA_VERSION
    record_id_field: ClassVar[str]

    @property
    def record_id(self) -> str:
        return str(getattr(self, self.record_id_field))


class SourceKind(StrEnum):
    GITHUB_REPOSITORY = "github_repository"


class SourceRole(StrEnum):
    IMPLEMENTATION = "implementation"
    RESEARCH_INDEX = "research_index"
    RESEARCH_PROGRAM = "research_program"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DiscoveryChannelType(StrEnum):
    MANUAL_WATCHLIST = "manual_watchlist"
    GITHUB_STARS = "github_stars"
    SAVED_SEARCH = "saved_search"


class RetrievalStatus(StrEnum):
    CAPTURED = "captured"
    MISSING = "missing"
    ERROR = "error"
    NOT_MODIFIED = "not_modified"


class ObservationEpistemicType(StrEnum):
    INTERPRETATION = "Interpretation"
    INFERENCE = "Inference"
    HYPOTHESIS = "Hypothesis"
    EVALUATION = "Evaluation"
    OPINION = "Opinion"
    UNKNOWN = "Unknown"


class ValidationState(StrEnum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    VALIDATED = "validated"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class SupportType(StrEnum):
    EVIDENCE_FACT = "EvidenceFact"
    SOURCE_ASSERTION = "SourceAssertion"
    OBSERVATION = "Observation"


class PatternOccurrenceRole(StrEnum):
    SUPPORTING = "supporting"
    NEGATIVE_CONTROL = "negative_control"
    CONTRADICTING = "contradicting"


class RunType(StrEnum):
    DISCOVERY = "discovery"
    CAPTURE = "capture"
    EXTRACTION = "extraction"
    DIFF = "diff"
    PROFILING = "profiling"
    REASONING = "reasoning"
    SYNTHESIS = "synthesis"
    EVALUATION = "evaluation"
    OTHER = "other"


class RelationshipType(StrEnum):
    OWNED = "OWNED"
    CONTRIBUTABLE = "CONTRIBUTABLE"
    EXTERNAL = "EXTERNAL"
    READ_ONLY = "READ_ONLY"
    UNKNOWN = "UNKNOWN"


class ActionType(StrEnum):
    LEARN = "learn"
    INVESTIGATE = "investigate"
    ADOPT = "adopt"
    AVOID = "avoid"
    MITIGATE = "mitigate"
    PIN = "pin"
    MONITOR = "monitor"
    REPORT_UPSTREAM = "report_upstream"
    CONTRIBUTE_UPSTREAM = "contribute_upstream"
    FORK_VENDOR = "fork_vendor"
    REVALIDATE = "revalidate"
    PRESERVE = "preserve"
    RERUN = "rerun"
    CLASSIFY = "classify"
    PROMOTE = "promote"
    NO_ACTION = "no_action"


class ActionStatus(StrEnum):
    CANDIDATE = "candidate"
    RECOMMENDED = "recommended"
    AUTHORIZED = "authorized"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ReviewDecisionType(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    LOW_SIGNAL = "LOW_SIGNAL"
    DUPLICATE = "DUPLICATE"
    MERGE = "MERGE"
    PROMOTE = "PROMOTE"
    SNOOZE = "SNOOZE"
    DEEP_DIVE = "DEEP_DIVE"
    CONTRADICT = "CONTRADICT"


class Source(ContractModel):
    record_id_field = "source_id"

    source_id: Identifier
    source_kind: SourceKind
    source_role: SourceRole
    canonical_locator: Identifier
    first_seen_at: AwareDatetime
    last_seen_at: AwareDatetime

    @model_validator(mode="after")
    def validate_seen_window(self) -> Source:
        if self.last_seen_at < self.first_seen_at:
            raise ValueError("last_seen_at must not precede first_seen_at")
        return self


class RepositoryIdentity(ContractModel):
    record_id_field = "source_id"

    source_id: Identifier
    provider_repository_id: Identifier
    owner: Identifier
    name: Identifier
    default_branch: Identifier
    aliases: tuple[str, ...] = ()
    archived: bool = False


class SourceRevision(ContractModel):
    record_id_field = "source_revision_id"

    source_revision_id: Identifier
    source_id: Identifier
    commit_sha: GitSha
    tree_sha: GitSha
    observed_at: AwareDatetime


class DiscoveryChannel(ContractModel):
    """Stable configured entry point through which Sources may be discovered."""

    record_id_field = "discovery_channel_id"

    discovery_channel_id: Identifier
    channel_type: DiscoveryChannelType
    name: Identifier
    canonical_locator: Identifier
    created_at: AwareDatetime


class DiscoveryRun(ContractModel):
    """One domain-level execution of a DiscoveryChannel."""

    record_id_field = "discovery_run_id"

    discovery_run_id: Identifier
    discovery_channel_id: Identifier
    pipeline_run_id: Identifier
    observed_at: AwareDatetime
    hit_count: int = Field(ge=0)


class DiscoveryHit(ContractModel):
    """One raw channel hit, optionally linked to an already-resolved Source."""

    record_id_field = "discovery_hit_id"

    discovery_hit_id: Identifier
    discovery_run_id: Identifier
    source_id: Identifier | None = None
    ordinal: int = Field(ge=1)
    discovered_locator: Identifier


class CaptureArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: Identifier
    source_locator: Identifier
    content_hash: ContentDigest | None = None
    media_type: Identifier | None = None
    retrieval_status: RetrievalStatus

    @model_validator(mode="after")
    def require_capture_metadata(self) -> CaptureArtifactRef:
        if self.retrieval_status is RetrievalStatus.CAPTURED:
            if self.content_hash is None or self.media_type is None:
                raise ValueError("captured artifacts require content_hash and media_type")
        return self


class CaptureManifest(ContractModel):
    record_id_field = "capture_id"

    capture_id: Identifier
    source_revision_id: Identifier
    capture_policy_version: Identifier
    captured_at: AwareDatetime
    artifacts: tuple[CaptureArtifactRef, ...] = ()


class Artifact(ContractModel):
    record_id_field = "artifact_id"

    artifact_id: Identifier
    capture_id: Identifier
    source_locator: Identifier
    content_hash: ContentDigest
    media_type: Identifier


class PipelineRun(ContractModel):
    record_id_field = "run_id"

    run_id: Identifier
    run_type: RunType
    code_version: Identifier
    schema_version_used: Identifier = Field(alias="contract_schema_version")
    policy_version: Identifier
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    inputs_hash: ContentDigest
    outputs_hash: ContentDigest | None = None

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def validate_run_window(self) -> PipelineRun:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        return self


class EvidenceFact(ContractModel):
    record_id_field = "evidence_id"

    evidence_id: Identifier
    artifact_id: Identifier
    locator: Identifier
    raw_value: JsonValue
    normalized_value: JsonValue
    extractor_name: Identifier
    extractor_version: Identifier
    run_id: Identifier


class SourceAssertion(ContractModel):
    record_id_field = "assertion_id"

    assertion_id: Identifier
    artifact_id: Identifier
    locator: Identifier
    statement: Identifier
    extractor_name: Identifier
    extractor_version: Identifier
    run_id: Identifier


class Observation(ContractModel):
    record_id_field = "observation_id"

    observation_id: Identifier
    logical_claim_id: Identifier
    epistemic_type: ObservationEpistemicType
    statement: Identifier
    validation_state: ValidationState
    reasoning_run_id: Identifier
    created_at: AwareDatetime
    supersedes_observation_id: Identifier | None = None


class ObservationSupport(ContractModel):
    record_id_field = "support_edge_id"

    support_edge_id: Identifier
    observation_id: Identifier
    support_id: Identifier
    support_type: SupportType


class Pattern(ContractModel):
    """Cross-source derived claim whose provenance flows through occurrences."""

    record_id_field = "pattern_id"

    pattern_id: Identifier
    logical_claim_id: Identifier
    epistemic_type: ObservationEpistemicType
    statement: Identifier
    validation_state: ValidationState
    synthesis_run_id: Identifier
    created_at: AwareDatetime


class PatternOccurrence(ContractModel):
    """One source-revision-local instantiation or counterexample for a Pattern."""

    record_id_field = "occurrence_id"

    occurrence_id: Identifier
    pattern_id: Identifier
    source_revision_id: Identifier
    role: PatternOccurrenceRole
    summary: Identifier


class PatternOccurrenceSupport(ContractModel):
    """Trace a PatternOccurrence to one source-local Observation."""

    record_id_field = "support_edge_id"

    support_edge_id: Identifier
    occurrence_id: Identifier
    observation_id: Identifier


class RepositoryRelationship(ContractModel):
    record_id_field = "relationship_id"

    relationship_id: Identifier
    source_id: Identifier
    relationship_type: RelationshipType
    can_write: bool
    can_contribute: bool
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_permissions(self) -> RepositoryRelationship:
        if self.relationship_type is RelationshipType.READ_ONLY and self.can_write:
            raise ValueError("READ_ONLY relationships cannot have can_write=true")
        if self.relationship_type is RelationshipType.OWNED and not self.can_write:
            raise ValueError("OWNED relationships require can_write=true")
        return self


class ActionRecommendation(ContractModel):
    record_id_field = "action_id"

    action_id: Identifier
    subject_id: Identifier
    action_type: ActionType
    target: Identifier
    rationale: Identifier
    repository_modification_required: bool
    authorization_required: bool
    status: ActionStatus
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_no_action(self) -> ActionRecommendation:
        if self.action_type is ActionType.NO_ACTION and self.repository_modification_required:
            raise ValueError("no_action cannot require repository modification")
        return self


class ReviewDecision(ContractModel):
    record_id_field = "review_id"

    review_id: Identifier
    subject_id: Identifier
    decision: ReviewDecisionType
    decided_at: AwareDatetime
    notes: str = ""


CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    model.__name__: model
    for model in (
        Source,
        RepositoryIdentity,
        SourceRevision,
        DiscoveryChannel,
        DiscoveryRun,
        DiscoveryHit,
        CaptureManifest,
        Artifact,
        PipelineRun,
        EvidenceFact,
        SourceAssertion,
        Observation,
        ObservationSupport,
        Pattern,
        PatternOccurrence,
        PatternOccurrenceSupport,
        RepositoryRelationship,
        ActionRecommendation,
        ReviewDecision,
    )
}
