"""M6-lite deterministic architecture profiling and triage.

This module deliberately stays below architectural interpretation. Profiles summarize
which deterministic evidence families are present at one exact SourceRevision. Triage
uses explicit rule precedence over manual tracking/domain/sensitivity inputs and factual
StructuralDelta provenance; it does not compute learned or weighted relevance scores.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Protocol

from .change_contracts import ArtifactDelta, StructuralDelta
from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RunType,
    Source,
    SourceAssertion,
    SourceRevision,
)
from .profile_contracts import (
    ArchitectureProfile,
    TriageAssessment,
    TriageBand,
    TriageReason,
    TriageSensitivity,
)
from .tracking import RepositoryTrackingService
from .tracking_contracts import TrackingLevel


class ProfilingError(RuntimeError):
    """Profile or triage provenance is incomplete or inconsistent."""


class ProfileStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class ArchitectureProfileResult:
    profile: ArchitectureProfile
    run: PipelineRun

    def records(self) -> tuple:
        return (self.run, self.profile)


@dataclass(frozen=True)
class TriageResult:
    assessment: TriageAssessment
    run: PipelineRun

    def records(self) -> tuple:
        return (self.run, self.assessment)


class ArchitectureProfilingService:
    """Build immutable revision-bound profiles from explicit deterministic evidence runs."""

    def __init__(
        self,
        store: ProfileStore,
        *,
        profile_schema_version: str = "architecture-profile.v1",
        policy_version: str = "architecture-profiling.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.profile_schema_version = profile_schema_version
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def build_profile(
        self,
        source_revision_id: str,
        *,
        evidence_run_ids: Iterable[str],
    ) -> ArchitectureProfileResult:
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise ProfilingError(f"unknown SourceRevision: {source_revision_id}")
        source = self.store.get(Source, revision.source_id)
        if source is None:
            raise ProfilingError(f"SourceRevision references missing Source: {revision.source_id}")

        run_ids = tuple(sorted(set(item.strip() for item in evidence_run_ids if item.strip())))
        if not run_ids:
            raise ProfilingError("ArchitectureProfile requires at least one evidence run")
        for run_id in run_ids:
            self._require_complete_run(run_id, RunType.EXTRACTION)

        facts = tuple(
            sorted(
                (item for item in self.store.list(EvidenceFact) if item.run_id in run_ids),
                key=lambda item: item.evidence_id,
            )
        )
        assertions = tuple(
            sorted(
                (item for item in self.store.list(SourceAssertion) if item.run_id in run_ids),
                key=lambda item: item.assertion_id,
            )
        )

        artifact_ids: set[str] = set()
        media_types: set[str] = set()
        extractor_families: set[str] = set()
        extractor_profiles: set[str] = set()
        for record in (*facts, *assertions):
            artifact = self._require_artifact_revision(record.artifact_id, revision.source_revision_id)
            artifact_ids.add(artifact.artifact_id)
            media_types.add(artifact.media_type)
            extractor_families.add(record.extractor_name)
            extractor_profiles.add(f"{record.extractor_name}@{record.extractor_version}")

        feature_keys = self._feature_keys(extractor_families, media_types)
        created_at = self._aware_now()
        profiling_run_id = f"run:{self.id_factory()}"
        profile_id = f"architecture-profile:{self.id_factory()}"

        inputs = {
            "source_id": source.source_id,
            "source_revision_id": revision.source_revision_id,
            "evidence_run_ids": list(run_ids),
            "evidence_fact_ids": [item.evidence_id for item in facts],
            "source_assertion_ids": [item.assertion_id for item in assertions],
            "extractor_profiles": sorted(extractor_profiles),
            "profile_schema_version": self.profile_schema_version,
            "policy_version": self.policy_version,
        }
        profile = ArchitectureProfile(
            architecture_profile_id=profile_id,
            source_id=source.source_id,
            source_revision_id=revision.source_revision_id,
            profile_schema_version=self.profile_schema_version,
            profiling_run_id=profiling_run_id,
            evidence_run_ids=run_ids,
            artifact_ids=tuple(sorted(artifact_ids)),
            evidence_fact_ids=tuple(item.evidence_id for item in facts),
            source_assertion_ids=tuple(item.assertion_id for item in assertions),
            evidence_fact_count=len(facts),
            source_assertion_count=len(assertions),
            artifact_count=len(artifact_ids),
            extractor_families=tuple(sorted(extractor_families)),
            extractor_profiles=tuple(sorted(extractor_profiles)),
            artifact_media_types=tuple(sorted(media_types)),
            feature_keys=feature_keys,
        )
        outputs_hash = self._digest_json(profile.model_dump(mode="json"))
        run = PipelineRun(
            run_id=profiling_run_id,
            run_type=RunType.PROFILING,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=created_at,
            finished_at=created_at,
            inputs_hash=self._digest_json(inputs),
            outputs_hash=outputs_hash,
        )
        self.store.put_many((run, profile))
        return ArchitectureProfileResult(profile=profile, run=run)

    def _require_complete_run(self, run_id: str, expected: RunType) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise ProfilingError(f"missing PipelineRun: {run_id}")
        if run.run_type is not expected:
            raise ProfilingError(
                f"PipelineRun {run_id} has type {run.run_type.value}; expected {expected.value}"
            )
        if run.finished_at is None or run.outputs_hash is None:
            raise ProfilingError(f"PipelineRun is incomplete: {run_id}")
        return run

    def _require_artifact_revision(self, artifact_id: str, expected_revision_id: str) -> Artifact:
        artifact = self.store.get(Artifact, artifact_id)
        if artifact is None:
            raise ProfilingError(f"evidence references missing Artifact: {artifact_id}")
        manifest = self.store.get(CaptureManifest, artifact.capture_id)
        if manifest is None:
            raise ProfilingError(f"Artifact references missing CaptureManifest: {artifact.capture_id}")
        if manifest.source_revision_id != expected_revision_id:
            raise ProfilingError(
                "ArchitectureProfile evidence must resolve to exactly its SourceRevision; "
                f"expected {expected_revision_id}, got {manifest.source_revision_id}"
            )
        if not any(
            ref.artifact_id == artifact.artifact_id
            and ref.source_locator == artifact.source_locator
            and ref.content_hash == artifact.content_hash
            and ref.media_type == artifact.media_type
            for ref in manifest.artifacts
        ):
            raise ProfilingError("Artifact is not consistently represented in its CaptureManifest")
        return artifact

    @staticmethod
    def _feature_keys(extractor_families: set[str], media_types: set[str]) -> tuple[str, ...]:
        features = {f"extractor:{name}" for name in extractor_families}
        features.update(f"media:{media}" for media in media_types)
        mapping = {
            "python-ast": "language:python",
            "typescript-ast": "language:typescript",
            "pyproject": "manifest:python-project",
            "package-json": "manifest:node-package",
            "github-workflow-metadata": "surface:workflow",
            "github-process-metadata": "surface:process-current",
            "github-issue-events": "surface:process-history",
            "github-repository-metadata": "surface:repository-metadata",
            "git-tree": "surface:git-tree",
            "git-commit": "surface:git-commit",
        }
        for extractor, feature in mapping.items():
            if extractor in extractor_families:
                features.add(feature)
        return tuple(sorted(features))

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ProfilingError("profiling clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


class DeterministicTriageService:
    """Route one ArchitectureProfile with rule precedence rather than numeric weights."""

    def __init__(
        self,
        store: ProfileStore,
        tracking: RepositoryTrackingService,
        *,
        policy_version: str = "deterministic-triage.v1",
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

    def assess(
        self,
        architecture_profile_id: str,
        *,
        domain_match: bool,
        sensitivity_flags: Iterable[TriageSensitivity] = (),
        structural_delta_ids: Iterable[str] = (),
    ) -> TriageResult:
        profile = self.store.get(ArchitectureProfile, architecture_profile_id)
        if profile is None:
            raise ProfilingError(f"unknown ArchitectureProfile: {architecture_profile_id}")
        profile_run = self._require_complete_run(profile.profiling_run_id, RunType.PROFILING)
        revision = self.store.get(SourceRevision, profile.source_revision_id)
        if revision is None or revision.source_id != profile.source_id:
            raise ProfilingError("ArchitectureProfile source/revision provenance is inconsistent")

        sensitivities = tuple(sorted(set(sensitivity_flags), key=lambda item: item.value))
        delta_ids = tuple(sorted(set(item.strip() for item in structural_delta_ids if item.strip())))
        for delta_id in delta_ids:
            delta = self.store.get(StructuralDelta, delta_id)
            if delta is None:
                raise ProfilingError(f"missing StructuralDelta: {delta_id}")
            if delta.source_id != profile.source_id or delta.current_source_revision_id != profile.source_revision_id:
                raise ProfilingError(
                    "triage StructuralDelta must terminate at the ArchitectureProfile SourceRevision"
                )
            artifact_delta = self.store.get(ArtifactDelta, delta.artifact_delta_id)
            if artifact_delta is None:
                raise ProfilingError(
                    f"StructuralDelta references missing ArtifactDelta: {delta.artifact_delta_id}"
                )
            if (
                artifact_delta.source_id != delta.source_id
                or artifact_delta.current_source_revision_id != delta.current_source_revision_id
                or artifact_delta.diff_run_id != delta.diff_run_id
            ):
                raise ProfilingError("StructuralDelta and ArtifactDelta provenance disagree")
            self._require_complete_run(delta.diff_run_id, RunType.DIFF)

        now = self._aware_now()
        policy = self.tracking.policy_for(profile.source_id, as_of=now)
        reasons: set[TriageReason] = set()
        if policy.level is TrackingLevel.IGNORE:
            reasons.add(TriageReason.TRACKING_IGNORED)
        else:
            reasons.add(TriageReason.TRACKING_ACTIVE)
        reasons.add(TriageReason.DOMAIN_MATCH if domain_match else TriageReason.DOMAIN_MISMATCH)

        evidence_rich = profile.evidence_fact_count > 0 and len(profile.extractor_families) >= 2
        process_rich = any(
            key in profile.feature_keys
            for key in ("surface:process-current", "surface:process-history")
        )
        workflow_rich = "surface:workflow" in profile.feature_keys
        recent_structural_change = bool(delta_ids)
        deep_tracking = policy.level in {TrackingLevel.DEEP, TrackingLevel.CONTINUOUS}

        if evidence_rich:
            reasons.add(TriageReason.EVIDENCE_RICH)
        if process_rich:
            reasons.add(TriageReason.PROCESS_RICH)
        if workflow_rich:
            reasons.add(TriageReason.WORKFLOW_RICH)
        if recent_structural_change:
            reasons.add(TriageReason.RECENT_STRUCTURAL_CHANGE)
        if TriageSensitivity.GOVERNANCE in sensitivities:
            reasons.add(TriageReason.GOVERNANCE_SENSITIVE)
        if TriageSensitivity.EXPERIMENT in sensitivities:
            reasons.add(TriageReason.EXPERIMENT_SENSITIVE)
        if deep_tracking:
            reasons.add(TriageReason.DEEP_TRACKING)

        if policy.level is TrackingLevel.IGNORE:
            band = TriageBand.IGNORE
        elif domain_match and deep_tracking and recent_structural_change and sensitivities:
            band = TriageBand.DEEP_DIVE
        elif domain_match and (
            recent_structural_change
            or sensitivities
            or process_rich
            or workflow_rich
            or evidence_rich
        ):
            band = TriageBand.REVIEW
        else:
            band = TriageBand.WATCH

        triage_run_id = f"run:{self.id_factory()}"
        assessment_id = f"triage:{self.id_factory()}"
        assessment = TriageAssessment(
            triage_assessment_id=assessment_id,
            architecture_profile_id=profile.architecture_profile_id,
            source_id=profile.source_id,
            source_revision_id=profile.source_revision_id,
            triage_run_id=triage_run_id,
            policy_version=self.policy_version,
            tracking_level=policy.level,
            tracking_assignment_id=policy.assignment_id,
            domain_match=domain_match,
            sensitivity_flags=sensitivities,
            structural_delta_ids=delta_ids,
            band=band,
            reasons=tuple(sorted(reasons, key=lambda item: item.value)),
        )
        inputs_hash = self._digest_json(
            {
                "architecture_profile_id": profile.architecture_profile_id,
                "architecture_profile_run_id": profile_run.run_id,
                "tracking_level": policy.level.value,
                "tracking_assignment_id": policy.assignment_id,
                "domain_match": domain_match,
                "sensitivity_flags": [item.value for item in sensitivities],
                "structural_delta_ids": list(delta_ids),
                "policy_version": self.policy_version,
            }
        )
        run = PipelineRun(
            run_id=triage_run_id,
            run_type=RunType.PROFILING,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=now,
            finished_at=now,
            inputs_hash=inputs_hash,
            outputs_hash=self._digest_json(assessment.model_dump(mode="json")),
        )
        self.store.put_many((run, assessment))
        return TriageResult(assessment=assessment, run=run)

    def _require_complete_run(self, run_id: str, expected: RunType) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise ProfilingError(f"missing PipelineRun: {run_id}")
        if run.run_type is not expected:
            raise ProfilingError(
                f"PipelineRun {run_id} has type {run.run_type.value}; expected {expected.value}"
            )
        if run.finished_at is None or run.outputs_hash is None:
            raise ProfilingError(f"PipelineRun is incomplete: {run_id}")
        return run

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ProfilingError("triage clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
