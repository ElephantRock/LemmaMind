from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from lemmamind.contracts import (
    ActionRecommendation,
    ActionStatus,
    ActionType,
    CaptureArtifactRef,
    Observation,
    ObservationEpistemicType,
    RelationshipType,
    RepositoryRelationship,
    RetrievalStatus,
    Source,
    SourceKind,
    SourceRole,
    ValidationState,
)

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
SHA256_ZERO = "sha256:" + "0" * 64


def test_source_seen_window_is_monotonic() -> None:
    with pytest.raises(ValidationError):
        Source(
            source_id="source:example",
            source_kind=SourceKind.GITHUB_REPOSITORY,
            source_role=SourceRole.IMPLEMENTATION,
            canonical_locator="https://github.com/example/repo",
            first_seen_at=NOW,
            last_seen_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )


def test_captured_artifact_requires_hash_and_media_type() -> None:
    with pytest.raises(ValidationError):
        CaptureArtifactRef(
            artifact_id="artifact:readme",
            source_locator="README.md",
            retrieval_status=RetrievalStatus.CAPTURED,
        )

    artifact = CaptureArtifactRef(
        artifact_id="artifact:readme",
        source_locator="README.md",
        content_hash=SHA256_ZERO,
        media_type="text/markdown",
        retrieval_status=RetrievalStatus.CAPTURED,
    )
    assert artifact.content_hash == SHA256_ZERO


def test_read_only_relationship_cannot_claim_write_authority() -> None:
    with pytest.raises(ValidationError):
        RepositoryRelationship(
            relationship_id="relationship:external",
            source_id="source:external",
            relationship_type=RelationshipType.READ_ONLY,
            can_write=True,
            can_contribute=False,
            observed_at=NOW,
        )


def test_no_action_never_requires_repository_modification() -> None:
    with pytest.raises(ValidationError):
        ActionRecommendation(
            action_id="action:none",
            subject_id="observation:1",
            action_type=ActionType.NO_ACTION,
            target="example/repo",
            rationale="No intervention is warranted.",
            repository_modification_required=True,
            authorization_required=False,
            status=ActionStatus.RECOMMENDED,
            created_at=NOW,
        )


def test_observation_epistemic_type_cannot_be_source_evidence_class() -> None:
    observation = Observation(
        observation_id="observation:1",
        logical_claim_id="claim:1",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement="Runtime authority is distinct from instruction content.",
        validation_state=ValidationState.REVIEWED,
        reasoning_run_id="run:reasoning:1",
        created_at=NOW,
    )
    assert observation.epistemic_type is ObservationEpistemicType.INTERPRETATION

    with pytest.raises(ValidationError):
        Observation(
            observation_id="observation:bad",
            logical_claim_id="claim:bad",
            epistemic_type="ObservedFact",
            statement="This belongs in EvidenceFact, not Observation.",
            validation_state=ValidationState.CANDIDATE,
            reasoning_run_id="run:reasoning:1",
            created_at=NOW,
        )
