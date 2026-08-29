"""Durable contracts for candidate-scoped factual reduction in full M5.

These records summarize deterministic evidence already bound to one
``IntervalCandidateSegment``. They do not rank architectural importance and do
not perform ``ChangeInterpretation``. The only automatic suppression permitted
here is the suppression already authorized by the affected-file planning policy;
missing deterministic extractor coverage remains visible and retained.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from .contracts import CONTRACT_TYPES, ContractModel, Identifier, SourceLocator


class CandidateReductionDisposition(StrEnum):
    RETAIN = "retain"
    SUPPRESS = "suppress"


class CandidateSignalKind(StrEnum):
    STRUCTURAL_DELTA = "structural_delta"
    AUTHORED_ASSERTION_CHANGE = "authored_assertion_change"
    ARTIFACT_DELTA_WITHOUT_EXTRACTED_SIGNAL = (
        "artifact_delta_without_extracted_signal"
    )
    GIT_ONLY_CHANGE = "git_only_change"
    POLICY_SUPPRESSED = "policy_suppressed"


class CandidateFactualReduction(ContractModel):
    """Auditable factual signal summary for one deterministic interval candidate."""

    record_id_field = "candidate_factual_reduction_id"

    candidate_factual_reduction_id: Identifier
    interval_candidate_segment_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier

    paths: tuple[SourceLocator, ...]
    affected_file_plan_ids: tuple[Identifier, ...]
    capture_scoped_paths: tuple[SourceLocator, ...] = ()
    policy_suppressed_paths: tuple[SourceLocator, ...] = ()

    artifact_delta_ids: tuple[Identifier, ...] = ()
    artifact_delta_paths: tuple[SourceLocator, ...] = ()
    structural_delta_ids: tuple[Identifier, ...] = ()
    structural_delta_paths: tuple[SourceLocator, ...] = ()
    assertion_changed_paths: tuple[SourceLocator, ...] = ()
    artifact_only_paths: tuple[SourceLocator, ...] = ()
    git_only_paths: tuple[SourceLocator, ...] = ()

    signal_kinds: tuple[CandidateSignalKind, ...]
    disposition: CandidateReductionDisposition

    diff_run_id: Identifier
    segmentation_run_id: Identifier
    planner_run_id: Identifier
    previous_capture_id: Identifier
    current_capture_id: Identifier
    previous_extraction_run_id: Identifier
    current_extraction_run_id: Identifier
    change_run_id: Identifier
    reduction_run_id: Identifier

    @model_validator(mode="after")
    def validate_membership(self) -> "CandidateFactualReduction":
        if not self.paths:
            raise ValueError("candidate factual reduction cannot be empty")

        for field_name in (
            "paths",
            "affected_file_plan_ids",
            "capture_scoped_paths",
            "policy_suppressed_paths",
            "artifact_delta_ids",
            "artifact_delta_paths",
            "structural_delta_ids",
            "structural_delta_paths",
            "assertion_changed_paths",
            "artifact_only_paths",
            "git_only_paths",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")

        if self.signal_kinds != tuple(
            sorted(set(self.signal_kinds), key=lambda item: item.value)
        ):
            raise ValueError("signal_kinds must be sorted and unique")
        if not self.signal_kinds:
            raise ValueError("candidate factual reduction requires at least one signal kind")

        path_set = set(self.paths)
        for field_name in (
            "capture_scoped_paths",
            "policy_suppressed_paths",
            "artifact_delta_paths",
            "structural_delta_paths",
            "assertion_changed_paths",
            "artifact_only_paths",
            "git_only_paths",
        ):
            if not set(getattr(self, field_name)).issubset(path_set):
                raise ValueError(f"{field_name} must be a subset of candidate paths")

        if not set(self.structural_delta_paths).issubset(set(self.artifact_delta_paths)):
            raise ValueError("structural_delta_paths must be backed by artifact deltas")
        if not set(self.artifact_only_paths).issubset(set(self.artifact_delta_paths)):
            raise ValueError("artifact_only_paths must be backed by artifact deltas")
        if set(self.artifact_only_paths) & set(self.structural_delta_paths):
            raise ValueError("artifact_only_paths cannot also carry structural deltas")
        if set(self.artifact_only_paths) & set(self.assertion_changed_paths):
            raise ValueError("artifact_only_paths cannot also carry assertion changes")

        if self.disposition is CandidateReductionDisposition.SUPPRESS:
            if set(self.paths) != set(self.policy_suppressed_paths):
                raise ValueError(
                    "automatic suppression is allowed only when every candidate path "
                    "was already policy-suppressed"
                )
            if self.signal_kinds != (CandidateSignalKind.POLICY_SUPPRESSED,):
                raise ValueError(
                    "fully suppressed candidates may carry only policy_suppressed signal"
                )
        elif set(self.paths) == set(self.policy_suppressed_paths):
            raise ValueError("fully policy-suppressed candidates must be suppressed")

        return self


CONTRACT_TYPES[CandidateFactualReduction.__name__] = CandidateFactualReduction

CANDIDATE_REDUCTION_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    CandidateFactualReduction.__name__: CandidateFactualReduction,
}
