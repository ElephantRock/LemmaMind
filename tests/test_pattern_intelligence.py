from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    Observation,
    ObservationEpistemicType,
    Pattern,
    PatternOccurrence,
    PatternOccurrenceRole,
    PatternOccurrenceSupport,
    PipelineRun,
    RetrievalStatus,
    RunType,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
    SupportType,
    ValidationState,
)
from lemmamind.observations import SupportRef
from lemmamind.observations_v2 import ObservationConstructionServiceV2
from lemmamind.pattern_intelligence import (
    OccurrenceProposal,
    PatternConstructionError,
    PatternConstructionService,
)
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 16, 30, tzinfo=timezone.utc)


def digest(char: str) -> str:
    return "sha256:" + char * 64


def add_source_observation(
    store,
    *,
    source_id: str,
    commit_sha: str,
    tree_char: str,
    repository: str,
    statement: str,
    fact_value,
    index: int,
    validation_state: ValidationState = ValidationState.CANDIDATE,
):
    source = Source(
        source_id=source_id,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator=f"https://github.com/{repository}",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    revision = SourceRevision(
        source_revision_id=f"{source_id}@{commit_sha}",
        source_id=source_id,
        commit_sha=commit_sha,
        tree_sha=tree_char * 40,
        observed_at=NOW,
    )
    capture_id = f"capture:{index}"
    artifact = Artifact(
        artifact_id=f"artifact:{index}",
        capture_id=capture_id,
        source_locator=f"$fixture/{index}",
        content_hash=digest(hex(index % 16)[2:]),
        media_type="application/json",
    )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="pattern-fixture.v1",
        captured_at=NOW,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator=artifact.source_locator,
                content_hash=artifact.content_hash,
                media_type=artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    extraction = PipelineRun(
        run_id=f"run:extract:{index}",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="pattern-fixture.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=digest("a"),
        outputs_hash=digest("b"),
    )
    fact = EvidenceFact(
        evidence_id=f"evidence:{index}",
        artifact_id=artifact.artifact_id,
        locator=f"{artifact.source_locator}#/signature",
        raw_value=fact_value,
        normalized_value=fact_value,
        extractor_name="fixture",
        extractor_version="1",
        run_id=extraction.run_id,
    )
    store.put_many((source, revision, artifact, manifest, extraction, fact))

    created = ObservationConstructionServiceV2(store, clock=lambda: NOW).create_candidate(
        logical_claim_id=f"local:{index}",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement=statement,
        supports=(SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id),),
    )
    observation = created.observation
    if validation_state is not ValidationState.CANDIDATE:
        replacement = observation.model_copy(update={"validation_state": validation_state})
        # Store is append-only, so replace only in test setup by rebuilding before insert is impossible.
        # Return a detached replacement for tests that insert it into a fresh store instead.
        return revision, fact, replacement
    return revision, fact, observation


def build_private_actions_observations(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    rows = [
        (
            "github:1282740796",
            "8fd8250121baf75b3689e2bba7ba2df8fa3608cf",
            "1",
            "ElephantRock/ExpertOS",
            "ExpertOS run 32779830513 has four failed jobs with no recorded steps.",
            {"visibility": "private", "job_signature": "failure-zero-steps"},
        ),
        (
            "github:1315223184",
            "5dcde592808d07008c2b5ad953fce78acb02f656",
            "2",
            "ElephantRock/ExpertForge",
            "ExpertForge run 32778642199 has a failed first job with no recorded steps and skipped dependents.",
            {"visibility": "private", "job_signature": "failure-zero-steps"},
        ),
        (
            "github:1319545100",
            "d0078339601c431ccf2f8a12974dba0dba9724a6",
            "3",
            "ElephantRock/ERLab",
            "ERLab run 32334661409 executed normal test/lint steps successfully in a public repository.",
            {"visibility": "public", "job_signature": "success-with-steps"},
        ),
        (
            "github:1332389171",
            "7caa57fa3650ed29e00ffd482b99ac571d294fc3",
            "4",
            "ElephantRock/Resonance-ContextGraph",
            "Resonance-ContextGraph run 32780247570 executed pytest and other steps successfully in a public repository.",
            {"visibility": "public", "job_signature": "success-with-steps"},
        ),
    ]
    results = [
        add_source_observation(
            store,
            source_id=source_id,
            commit_sha=sha,
            tree_char=tree_char,
            repository=repo,
            statement=statement,
            fact_value=value,
            index=index,
        )
        for index, (source_id, sha, tree_char, repo, statement, value) in enumerate(rows, start=1)
    ]
    return store, results


def proposals(rows):
    expertos, expertforge, erlab, contextgraph = rows
    return (
        OccurrenceProposal(
            expertos[0].source_revision_id,
            PatternOccurrenceRole.SUPPORTING,
            "Private repository with matched pre-step failure signature.",
            (expertos[2].observation_id,),
        ),
        OccurrenceProposal(
            expertforge[0].source_revision_id,
            PatternOccurrenceRole.SUPPORTING,
            "Private repository with matched pre-step failure signature.",
            (expertforge[2].observation_id,),
        ),
        OccurrenceProposal(
            erlab[0].source_revision_id,
            PatternOccurrenceRole.NEGATIVE_CONTROL,
            "Public portfolio repository with successful GitHub Actions step execution.",
            (erlab[2].observation_id,),
        ),
        OccurrenceProposal(
            contextgraph[0].source_revision_id,
            PatternOccurrenceRole.NEGATIVE_CONTROL,
            "Public portfolio repository with successful GitHub Actions step execution.",
            (contextgraph[2].observation_id,),
        ),
    )


def test_constructs_candidate_pattern_with_positive_cases_and_negative_controls(tmp_path) -> None:
    store, rows = build_private_actions_observations(tmp_path)
    result = PatternConstructionService(store, clock=lambda: NOW).create_candidate(
        logical_claim_id="pattern:private-actions-pre-step-failure",
        epistemic_type=ObservationEpistemicType.INFERENCE,
        statement=(
            "The matched pre-step failure signature across two private repositories, contrasted "
            "with functioning public-repository Actions, supports a shared private-repository "
            "Actions provisioning, entitlement, or billing hypothesis more strongly than two "
            "independent code-test failures."
        ),
        occurrences=proposals(rows),
        minimum_supporting_sources=2,
        minimum_negative_control_sources=2,
    )

    assert isinstance(result.pattern, Pattern)
    assert result.pattern.validation_state is ValidationState.CANDIDATE
    assert result.pattern.epistemic_type is ObservationEpistemicType.INFERENCE
    assert result.run.run_type is RunType.SYNTHESIS
    assert len(result.occurrences) == 4
    assert len(result.supports) == 4
    assert {item.role for item in result.occurrences} == {
        PatternOccurrenceRole.SUPPORTING,
        PatternOccurrenceRole.NEGATIVE_CONTROL,
    }
    assert len({item.source_revision_id for item in result.occurrences}) == 4
    assert all(isinstance(item, PatternOccurrence) for item in result.occurrences)
    assert all(isinstance(item, PatternOccurrenceSupport) for item in result.supports)


def test_requires_requested_negative_controls(tmp_path) -> None:
    store, rows = build_private_actions_observations(tmp_path)

    with pytest.raises(PatternConstructionError, match="negative-control Sources"):
        PatternConstructionService(store, clock=lambda: NOW).create_candidate(
            logical_claim_id="pattern:private-actions-pre-step-failure",
            epistemic_type=ObservationEpistemicType.INFERENCE,
            statement="Candidate shared infrastructure hypothesis.",
            occurrences=proposals(rows)[:2],
            minimum_supporting_sources=2,
            minimum_negative_control_sources=1,
        )


def test_occurrence_observation_must_resolve_to_declared_revision(tmp_path) -> None:
    store, rows = build_private_actions_observations(tmp_path)
    expertos, expertforge, _, _ = rows
    malformed = (
        OccurrenceProposal(
            expertos[0].source_revision_id,
            PatternOccurrenceRole.SUPPORTING,
            "Wrongly attached observation.",
            (expertforge[2].observation_id,),
        ),
        OccurrenceProposal(
            expertforge[0].source_revision_id,
            PatternOccurrenceRole.SUPPORTING,
            "Second positive case.",
            (expertos[2].observation_id,),
        ),
    )

    with pytest.raises(PatternConstructionError, match="resolve exactly"):
        PatternConstructionService(store, clock=lambda: NOW).create_candidate(
            logical_claim_id="pattern:bad-provenance",
            epistemic_type=ObservationEpistemicType.INFERENCE,
            statement="Bad pattern.",
            occurrences=malformed,
        )


def test_same_source_cannot_be_counted_twice_as_independent_occurrences(tmp_path) -> None:
    store, rows = build_private_actions_observations(tmp_path)
    expertos = rows[0]
    second_revision = SourceRevision(
        source_revision_id="github:1282740796@" + "f" * 40,
        source_id="github:1282740796",
        commit_sha="f" * 40,
        tree_sha="e" * 40,
        observed_at=NOW,
    )
    store.put(second_revision)
    malformed = (
        OccurrenceProposal(
            expertos[0].source_revision_id,
            PatternOccurrenceRole.SUPPORTING,
            "First revision.",
            (expertos[2].observation_id,),
        ),
        OccurrenceProposal(
            second_revision.source_revision_id,
            PatternOccurrenceRole.SUPPORTING,
            "Same source counted again.",
            (expertos[2].observation_id,),
        ),
    )

    with pytest.raises(PatternConstructionError, match="pseudo-replication"):
        PatternConstructionService(store, clock=lambda: NOW).create_candidate(
            logical_claim_id="pattern:pseudoreplication",
            epistemic_type=ObservationEpistemicType.INFERENCE,
            statement="Bad repeated-source pattern.",
            occurrences=malformed,
        )


def test_pattern_is_persisted_with_traceable_occurrences(tmp_path) -> None:
    store, rows = build_private_actions_observations(tmp_path)
    result = PatternConstructionService(store, clock=lambda: NOW).create_candidate(
        logical_claim_id="pattern:trace",
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement=(
            "The affected PRs should be described as CI not executed rather than code tests failed "
            "until runner or provisioning state is resolved."
        ),
        occurrences=proposals(rows),
        minimum_supporting_sources=2,
        minimum_negative_control_sources=2,
    )

    assert store.get(Pattern, result.pattern.pattern_id) == result.pattern
    assert len(store.list(PatternOccurrence)) == 4
    assert len(store.list(PatternOccurrenceSupport)) == 4
    assert all(
        store.get(Observation, edge.observation_id) is not None
        for edge in result.supports
    )
