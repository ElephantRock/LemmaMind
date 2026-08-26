from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.change_contracts import (
    ArtifactDelta,
    ArtifactDeltaType,
    StructuralDelta,
    StructuralDeltaType,
)
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    Source,
    SourceAssertion,
    SourceKind,
    SourceRevision,
    SourceRole,
)
from lemmamind.profile_contracts import (
    ArchitectureProfile,
    TriageAssessment,
    TriageBand,
    TriageReason,
    TriageSensitivity,
)
from lemmamind.profiling import (
    ArchitectureProfilingService,
    DeterministicTriageService,
    ProfilingError,
)
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking import RepositoryTrackingService
from lemmamind.tracking_contracts import TrackingLevel

NOW = datetime(2026, 8, 26, 3, 0, tzinfo=timezone.utc)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"m6-{self.value}"


def complete_run(run_id: str, run_type: RunType, *, policy: str = "test.v1") -> PipelineRun:
    return PipelineRun(
        run_id=run_id,
        run_type=run_type,
        code_version="lemmamind-test",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version=policy,
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST_A,
        outputs_hash=DIGEST_B,
    )


def seed_source(store: SQLiteContractStore):
    source = Source(
        source_id="source:demo",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="example/demo",
        first_seen_at=NOW - timedelta(days=1),
        last_seen_at=NOW,
    )
    previous = SourceRevision(
        source_revision_id="revision:previous",
        source_id=source.source_id,
        commit_sha="1" * 40,
        tree_sha="2" * 40,
        observed_at=NOW - timedelta(hours=1),
    )
    current = SourceRevision(
        source_revision_id="revision:current",
        source_id=source.source_id,
        commit_sha="3" * 40,
        tree_sha="4" * 40,
        observed_at=NOW,
    )
    store.put_many((source, previous, current))
    return source, previous, current


def seed_evidence(
    store: SQLiteContractStore,
    revision: SourceRevision,
    *,
    run_id: str = "run:extract",
    extractor_names: tuple[str, ...] = ("python-ast", "github-workflow-metadata"),
):
    manifest = CaptureManifest(
        capture_id=f"capture:{revision.source_revision_id}",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=NOW,
        artifacts=tuple(
            CaptureArtifactRef(
                artifact_id=f"artifact:{index}",
                source_locator=("src/demo.py" if index == 1 else "$github/actions/runs/1"),
                content_hash=(DIGEST_A if index == 1 else DIGEST_B),
                media_type=("text/x-python" if index == 1 else "application/vnd.github.workflow-run+json"),
                retrieval_status=RetrievalStatus.CAPTURED,
            )
            for index in range(1, len(extractor_names) + 1)
        ),
    )
    artifacts = tuple(
        Artifact(
            artifact_id=ref.artifact_id,
            capture_id=manifest.capture_id,
            source_locator=ref.source_locator,
            content_hash=ref.content_hash,
            media_type=ref.media_type,
        )
        for ref in manifest.artifacts
    )
    run = complete_run(run_id, RunType.EXTRACTION, policy="evidence.v1")
    facts = tuple(
        EvidenceFact(
            evidence_id=f"fact:{index}",
            artifact_id=artifacts[index - 1].artifact_id,
            locator=f"{artifacts[index - 1].source_locator}#feature/{index}",
            raw_value={"kind": extractor},
            normalized_value={"kind": extractor},
            extractor_name=extractor,
            extractor_version=str(index),
            run_id=run.run_id,
        )
        for index, extractor in enumerate(extractor_names, start=1)
    )
    assertion = SourceAssertion(
        assertion_id="assertion:1",
        artifact_id=artifacts[0].artifact_id,
        locator="src/demo.py:L1-L1",
        statement="Authored statement.",
        extractor_name="python-docstring",
        extractor_version="1",
        run_id=run.run_id,
    )
    store.put_many((*artifacts, manifest, run, *facts, assertion))
    return run, facts, assertion


def build_profile(store: SQLiteContractStore, current: SourceRevision):
    extraction_run, _, _ = seed_evidence(store, current)
    service = ArchitectureProfilingService(
        store,
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    )
    return service.build_profile(current.source_revision_id, evidence_run_ids=(extraction_run.run_id,))


def seed_structural_delta(
    store: SQLiteContractStore,
    source: Source,
    previous: SourceRevision,
    current: SourceRevision,
) -> StructuralDelta:
    diff_run = complete_run("run:diff", RunType.DIFF, policy="change.v1")
    artifact_delta = ArtifactDelta(
        artifact_delta_id="artifact-delta:1",
        source_id=source.source_id,
        previous_source_revision_id=previous.source_revision_id,
        current_source_revision_id=current.source_revision_id,
        previous_capture_id="capture:previous",
        current_capture_id="capture:current",
        source_locator="src/demo.py",
        change_type=ArtifactDeltaType.CONTENT_CHANGED,
        previous_artifact_id="artifact:previous",
        current_artifact_id="artifact:1",
        previous_retrieval_status=RetrievalStatus.CAPTURED,
        current_retrieval_status=RetrievalStatus.CAPTURED,
        previous_content_hash=DIGEST_A,
        current_content_hash=DIGEST_C,
        previous_media_type="text/x-python",
        current_media_type="text/x-python",
        diff_run_id=diff_run.run_id,
    )
    structural = StructuralDelta(
        structural_delta_id="structural-delta:1",
        artifact_delta_id=artifact_delta.artifact_delta_id,
        source_id=source.source_id,
        previous_source_revision_id=previous.source_revision_id,
        current_source_revision_id=current.source_revision_id,
        source_locator="src/demo.py",
        structural_key="python-ast:function:demo",
        change_type=StructuralDeltaType.ADDED,
        extractor_name="python-ast",
        extractor_version="1",
        current_evidence_id="fact:1",
        current_locator="src/demo.py#feature/1",
        current_value={"kind": "function"},
        diff_run_id=diff_run.run_id,
    )
    store.put_many((diff_run, artifact_delta, structural))
    return structural


def test_profile_is_revision_bound_and_records_extractor_versions(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, _, current = seed_source(store)
    result = build_profile(store, current)

    profile = result.profile
    assert profile.source_revision_id == current.source_revision_id
    assert profile.evidence_fact_count == 2
    assert profile.source_assertion_count == 1
    assert profile.artifact_count == 2
    assert profile.extractor_families == (
        "github-workflow-metadata",
        "python-ast",
        "python-docstring",
    )
    assert profile.extractor_profiles == (
        "github-workflow-metadata@2",
        "python-ast@1",
        "python-docstring@1",
    )
    assert "language:python" in profile.feature_keys
    assert "surface:workflow" in profile.feature_keys
    assert result.run.run_type is RunType.PROFILING
    assert store.get(ArchitectureProfile, profile.architecture_profile_id) == profile


def test_profile_rejects_evidence_from_another_revision(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, previous, current = seed_source(store)
    run, _, _ = seed_evidence(store, previous)
    service = ArchitectureProfilingService(store, clock=lambda: NOW)

    with pytest.raises(ProfilingError, match="exactly its SourceRevision"):
        service.build_profile(current.source_revision_id, evidence_run_ids=(run.run_id,))


def test_profile_rejects_incomplete_or_non_extraction_runs(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, _, current = seed_source(store)
    bad = complete_run("run:bad", RunType.DIFF)
    store.put(bad)
    service = ArchitectureProfilingService(store, clock=lambda: NOW)

    with pytest.raises(ProfilingError, match="expected extraction"):
        service.build_profile(current.source_revision_id, evidence_run_ids=(bad.run_id,))


def test_empty_but_complete_evidence_generation_can_form_empty_profile(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, _, current = seed_source(store)
    run = complete_run("run:empty", RunType.EXTRACTION)
    store.put(run)
    result = ArchitectureProfilingService(
        store, clock=lambda: NOW, id_factory=DeterministicIds()
    ).build_profile(current.source_revision_id, evidence_run_ids=(run.run_id,))

    assert result.profile.evidence_fact_count == 0
    assert result.profile.source_assertion_count == 0
    assert result.profile.artifact_count == 0
    assert result.profile.feature_keys == ()


def test_unassigned_source_triages_to_ignore(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, _, current = seed_source(store)
    profile = build_profile(store, current).profile
    tracking = RepositoryTrackingService(store, clock=lambda: NOW)
    result = DeterministicTriageService(
        store, tracking, clock=lambda: NOW, id_factory=DeterministicIds()
    ).assess(profile.architecture_profile_id, domain_match=True)

    assert result.assessment.band is TriageBand.IGNORE
    assert result.assessment.tracking_level is TrackingLevel.IGNORE
    assert TriageReason.TRACKING_IGNORED in result.assessment.reasons


def test_domain_match_plus_rich_evidence_triages_to_review_without_weights(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source, _, current = seed_source(store)
    profile = build_profile(store, current).profile
    tracking = RepositoryTrackingService(store, clock=lambda: NOW)
    assignment = tracking.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="test",
        reason="structural review",
    )
    result = DeterministicTriageService(
        store, tracking, clock=lambda: NOW, id_factory=DeterministicIds()
    ).assess(profile.architecture_profile_id, domain_match=True)

    assert result.assessment.band is TriageBand.REVIEW
    assert result.assessment.tracking_assignment_id == assignment.tracking_assignment_id
    assert TriageReason.EVIDENCE_RICH in result.assessment.reasons
    assert TriageReason.WORKFLOW_RICH in result.assessment.reasons


def test_deep_dive_requires_domain_deep_tracking_change_and_sensitivity(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source, previous, current = seed_source(store)
    profile = build_profile(store, current).profile
    structural = seed_structural_delta(store, source, previous, current)
    tracking = RepositoryTrackingService(store, clock=lambda: NOW)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.DEEP,
        assigned_by="test",
        reason="deep tracking",
    )
    result = DeterministicTriageService(
        store, tracking, clock=lambda: NOW, id_factory=DeterministicIds()
    ).assess(
        profile.architecture_profile_id,
        domain_match=True,
        sensitivity_flags=(TriageSensitivity.GOVERNANCE,),
        structural_delta_ids=(structural.structural_delta_id,),
    )

    assert result.assessment.band is TriageBand.DEEP_DIVE
    assert TriageReason.RECENT_STRUCTURAL_CHANGE in result.assessment.reasons
    assert TriageReason.GOVERNANCE_SENSITIVE in result.assessment.reasons
    assert TriageReason.DEEP_TRACKING in result.assessment.reasons


def test_domain_mismatch_prevents_escalation_even_with_other_signals(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source, previous, current = seed_source(store)
    profile = build_profile(store, current).profile
    structural = seed_structural_delta(store, source, previous, current)
    tracking = RepositoryTrackingService(store, clock=lambda: NOW)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.CONTINUOUS,
        assigned_by="test",
        reason="continuous tracking",
    )
    result = DeterministicTriageService(
        store, tracking, clock=lambda: NOW, id_factory=DeterministicIds()
    ).assess(
        profile.architecture_profile_id,
        domain_match=False,
        sensitivity_flags=(TriageSensitivity.EXPERIMENT,),
        structural_delta_ids=(structural.structural_delta_id,),
    )

    assert result.assessment.band is TriageBand.WATCH
    assert TriageReason.DOMAIN_MISMATCH in result.assessment.reasons


def test_triage_rejects_structural_delta_with_broken_artifact_delta_chain(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source, previous, current = seed_source(store)
    profile = build_profile(store, current).profile
    structural = seed_structural_delta(store, source, previous, current)
    # Persist a new structural record that names a missing ArtifactDelta.
    broken = structural.model_copy(
        update={
            "structural_delta_id": "structural-delta:broken",
            "artifact_delta_id": "artifact-delta:missing",
        }
    )
    store.put(broken)
    tracking = RepositoryTrackingService(store, clock=lambda: NOW)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.DEEP,
        assigned_by="test",
        reason="deep tracking",
    )

    with pytest.raises(ProfilingError, match="missing ArtifactDelta"):
        DeterministicTriageService(store, tracking, clock=lambda: NOW).assess(
            profile.architecture_profile_id,
            domain_match=True,
            structural_delta_ids=(broken.structural_delta_id,),
        )


def test_profile_and_triage_contracts_roundtrip_through_generic_registry(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source, _, current = seed_source(store)
    profile = build_profile(store, current).profile
    tracking = RepositoryTrackingService(store, clock=lambda: NOW)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="test",
        reason="triage",
    )
    assessment = DeterministicTriageService(
        store, tracking, clock=lambda: NOW, id_factory=DeterministicIds()
    ).assess(profile.architecture_profile_id, domain_match=True).assessment

    assert store.get_untyped("ArchitectureProfile", profile.architecture_profile_id) == profile
    assert store.get_untyped("TriageAssessment", assessment.triage_assessment_id) == assessment
