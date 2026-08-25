from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    Observation,
    ObservationEpistemicType,
    ObservationSupport,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
    SourceRevision,
    SupportType,
    ValidationState,
)
from lemmamind.observations import (
    ObservationConstructionError,
    ObservationConstructionService,
    SupportRef,
)
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 13, 10, tzinfo=timezone.utc)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"obs-{self.value}"


def complete_run(run_id: str, run_type: RunType = RunType.EXTRACTION) -> PipelineRun:
    return PipelineRun(
        run_id=run_id,
        run_type=run_type,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="test.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST_A,
        outputs_hash=DIGEST_B,
    )


def add_revision_support(
    store: SQLiteContractStore,
    *,
    revision_suffix: str,
    artifact_id: str,
    capture_id: str,
    fact_id: str,
    assertion_id: str,
) -> tuple[EvidenceFact, SourceAssertion]:
    revision = SourceRevision(
        source_revision_id=f"revision:{revision_suffix}",
        source_id=f"source:{revision_suffix}",
        commit_sha=revision_suffix * 40,
        tree_sha=("f" if revision_suffix != "f" else "e") * 40,
        observed_at=NOW,
    )
    artifact = Artifact(
        artifact_id=artifact_id,
        capture_id=capture_id,
        source_locator="src/example.py",
        content_hash=DIGEST_A,
        media_type="text/x-python",
    )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=NOW,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact_id,
                source_locator=artifact.source_locator,
                content_hash=artifact.content_hash,
                media_type=artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    fact = EvidenceFact(
        evidence_id=fact_id,
        artifact_id=artifact_id,
        locator="src/example.py:L1:C0-L1:C8#python/call",
        raw_value={"kind": "call", "callee": "host.allow"},
        normalized_value={"kind": "call", "callee": "host.allow"},
        extractor_name="python-ast",
        extractor_version="1",
        run_id="run:extract",
    )
    assertion = SourceAssertion(
        assertion_id=assertion_id,
        artifact_id=artifact_id,
        locator="src/example.py:L2-L2",
        statement="The host remains authoritative.",
        extractor_name="python-docstring",
        extractor_version="1",
        run_id="run:extract",
    )
    store.put_many((revision, artifact, manifest, fact, assertion))
    return fact, assertion


def build_store(tmp_path) -> tuple[SQLiteContractStore, EvidenceFact, SourceAssertion]:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put(complete_run("run:extract"))
    fact, assertion = add_revision_support(
        store,
        revision_suffix="a",
        artifact_id="artifact:a",
        capture_id="capture:a",
        fact_id="fact:a",
        assertion_id="assertion:a",
    )
    return store, fact, assertion


def service(store: SQLiteContractStore) -> ObservationConstructionService:
    return ObservationConstructionService(
        store,
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    )


def test_constructs_candidate_with_atomic_support_and_reasoning_run(tmp_path) -> None:
    store, fact, assertion = build_store(tmp_path)

    result = service(store).create_candidate(
        logical_claim_id="claim:host-authority",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement="Capability use is constrained by host authority.",
        supports=(
            SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id),
            SupportRef(SupportType.SOURCE_ASSERTION, assertion.assertion_id),
        ),
    )

    assert result.source_revision_id == "revision:a"
    assert result.observation.validation_state is ValidationState.CANDIDATE
    assert result.observation.reasoning_run_id == result.run.run_id
    assert result.run.run_type is RunType.REASONING
    assert result.run.finished_at == NOW
    assert result.run.outputs_hash is not None
    assert {edge.support_type for edge in result.supports} == {
        SupportType.EVIDENCE_FACT,
        SupportType.SOURCE_ASSERTION,
    }
    assert store.get(Observation, result.observation.observation_id) == result.observation
    assert len(store.list(ObservationSupport)) == 2


def test_rejects_missing_or_mistyped_support_before_persisting(tmp_path) -> None:
    store, fact, _ = build_store(tmp_path)
    builder = service(store)

    with pytest.raises(ObservationConstructionError, match="missing SourceAssertion support"):
        builder.create_candidate(
            logical_claim_id="claim:x",
            epistemic_type=ObservationEpistemicType.INFERENCE,
            statement="A claim.",
            supports=(SupportRef(SupportType.SOURCE_ASSERTION, fact.evidence_id),),
        )

    assert store.list(Observation) == []
    assert store.list(ObservationSupport) == []
    assert [run for run in store.list(PipelineRun) if run.run_type is RunType.REASONING] == []


def test_rejects_cross_revision_support(tmp_path) -> None:
    store, fact_a, _ = build_store(tmp_path)
    fact_b, _ = add_revision_support(
        store,
        revision_suffix="b",
        artifact_id="artifact:b",
        capture_id="capture:b",
        fact_id="fact:b",
        assertion_id="assertion:b",
    )

    with pytest.raises(ObservationConstructionError, match="requires all support to resolve to one"):
        service(store).create_candidate(
            logical_claim_id="claim:cross-source",
            epistemic_type=ObservationEpistemicType.INTERPRETATION,
            statement="A cross-revision statement.",
            supports=(
                SupportRef(SupportType.EVIDENCE_FACT, fact_a.evidence_id),
                SupportRef(SupportType.EVIDENCE_FACT, fact_b.evidence_id),
            ),
        )


def test_observation_can_support_later_observation_on_same_revision(tmp_path) -> None:
    store, fact, _ = build_store(tmp_path)
    builder = service(store)
    first = builder.create_candidate(
        logical_claim_id="claim:first",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement="The host checks authority.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id),),
    )

    second = builder.create_candidate(
        logical_claim_id="claim:second",
        epistemic_type=ObservationEpistemicType.INFERENCE,
        statement="Extension autonomy is bounded by host checks.",
        supports=(
            SupportRef(SupportType.OBSERVATION, first.observation.observation_id),
        ),
    )

    assert second.source_revision_id == "revision:a"
    assert second.supports[0].support_type is SupportType.OBSERVATION


def test_supersession_requires_same_logical_claim_and_revision(tmp_path) -> None:
    store, fact, _ = build_store(tmp_path)
    builder = service(store)
    first = builder.create_candidate(
        logical_claim_id="claim:stable",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement="Initial interpretation.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id),),
    )

    with pytest.raises(ObservationConstructionError, match="same logical_claim_id"):
        builder.create_candidate(
            logical_claim_id="claim:different",
            epistemic_type=ObservationEpistemicType.INTERPRETATION,
            statement="Replacement interpretation.",
            supports=(SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id),),
            supersedes_observation_id=first.observation.observation_id,
        )

    revised = builder.create_candidate(
        logical_claim_id="claim:stable",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement="Revised interpretation.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id),),
        supersedes_observation_id=first.observation.observation_id,
    )
    assert revised.observation.supersedes_observation_id == first.observation.observation_id


def test_rejects_incomplete_evidence_producer_run(tmp_path) -> None:
    store, fact, _ = build_store(tmp_path)
    broken = EvidenceFact(
        evidence_id="fact:broken",
        artifact_id=fact.artifact_id,
        locator=fact.locator,
        raw_value=fact.raw_value,
        normalized_value=fact.normalized_value,
        extractor_name=fact.extractor_name,
        extractor_version=fact.extractor_version,
        run_id="run:unfinished",
    )
    unfinished = PipelineRun(
        run_id="run:unfinished",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="test.v1",
        started_at=NOW,
        finished_at=None,
        inputs_hash=DIGEST_A,
        outputs_hash=None,
    )
    store.put_many((unfinished, broken))

    with pytest.raises(ObservationConstructionError, match="support run is incomplete"):
        service(store).create_candidate(
            logical_claim_id="claim:unfinished",
            epistemic_type=ObservationEpistemicType.EVALUATION,
            statement="This should not persist.",
            supports=(SupportRef(SupportType.EVIDENCE_FACT, broken.evidence_id),),
        )
