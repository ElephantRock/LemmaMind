from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    ObservationEpistemicType,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceRevision,
    SupportType,
)
from lemmamind.observations import ObservationConstructionError, SupportRef
from lemmamind.observations_v2 import ObservationConstructionServiceV2
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, 14, 45, tzinfo=timezone.utc)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"obs-v2-{self.value}"


def extraction_run() -> PipelineRun:
    return PipelineRun(
        run_id="run:extract",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="test.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST_A,
        outputs_hash=DIGEST_B,
    )


def add_fact(
    store: SQLiteContractStore,
    *,
    source_id: str,
    revision_id: str,
    sha_char: str,
    artifact_id: str,
    capture_id: str,
    fact_id: str,
) -> EvidenceFact:
    revision = SourceRevision(
        source_revision_id=revision_id,
        source_id=source_id,
        commit_sha=sha_char * 40,
        tree_sha=("f" if sha_char != "f" else "e") * 40,
        observed_at=NOW,
    )
    artifact = Artifact(
        artifact_id=artifact_id,
        capture_id=capture_id,
        source_locator="src/state.py",
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
        locator="src/state.py:L1:C0-L1:C12#python/assignment",
        raw_value={"state": revision_id},
        normalized_value={"state": revision_id},
        extractor_name="python-ast",
        extractor_version="1",
        run_id="run:extract",
    )
    store.put_many((revision, artifact, manifest, fact))
    return fact


def service(store: SQLiteContractStore) -> ObservationConstructionServiceV2:
    return ObservationConstructionServiceV2(
        store,
        clock=lambda: NOW,
        id_factory=DeterministicIds(),
    )


def test_allows_supersession_across_revisions_of_same_source(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put(extraction_run())
    old_fact = add_fact(
        store,
        source_id="source:repo",
        revision_id="revision:old",
        sha_char="a",
        artifact_id="artifact:old",
        capture_id="capture:old",
        fact_id="fact:old",
    )
    new_fact = add_fact(
        store,
        source_id="source:repo",
        revision_id="revision:new",
        sha_char="b",
        artifact_id="artifact:new",
        capture_id="capture:new",
        fact_id="fact:new",
    )
    builder = service(store)

    previous = builder.create_candidate(
        logical_claim_id="claim:frontier",
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement="The frontier is closed.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, old_fact.evidence_id),),
    )
    revised = builder.create_candidate(
        logical_claim_id="claim:frontier",
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement="Implementation is landed but qualification remains open.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, new_fact.evidence_id),),
        supersedes_observation_id=previous.observation.observation_id,
    )

    assert previous.source_revision_id == "revision:old"
    assert revised.source_revision_id == "revision:new"
    assert revised.observation.supersedes_observation_id == previous.observation.observation_id
    assert revised.run.policy_version == "supported-observation.v2"


def test_rejects_supersession_across_different_sources(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put(extraction_run())
    fact_a = add_fact(
        store,
        source_id="source:a",
        revision_id="revision:a",
        sha_char="a",
        artifact_id="artifact:a",
        capture_id="capture:a",
        fact_id="fact:a",
    )
    fact_b = add_fact(
        store,
        source_id="source:b",
        revision_id="revision:b",
        sha_char="b",
        artifact_id="artifact:b",
        capture_id="capture:b",
        fact_id="fact:b",
    )
    builder = service(store)
    previous = builder.create_candidate(
        logical_claim_id="claim:shared-name",
        epistemic_type=ObservationEpistemicType.INTERPRETATION,
        statement="Source A state.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, fact_a.evidence_id),),
    )

    with pytest.raises(ObservationConstructionError, match="same Source"):
        builder.create_candidate(
            logical_claim_id="claim:shared-name",
            epistemic_type=ObservationEpistemicType.INTERPRETATION,
            statement="Source B state.",
            supports=(SupportRef(SupportType.EVIDENCE_FACT, fact_b.evidence_id),),
            supersedes_observation_id=previous.observation.observation_id,
        )


def test_still_rejects_cross_revision_support_inside_one_observation(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put(extraction_run())
    fact_old = add_fact(
        store,
        source_id="source:repo",
        revision_id="revision:old",
        sha_char="a",
        artifact_id="artifact:old",
        capture_id="capture:old",
        fact_id="fact:old",
    )
    fact_new = add_fact(
        store,
        source_id="source:repo",
        revision_id="revision:new",
        sha_char="b",
        artifact_id="artifact:new",
        capture_id="capture:new",
        fact_id="fact:new",
    )

    with pytest.raises(ObservationConstructionError, match="requires all support to resolve to one"):
        service(store).create_candidate(
            logical_claim_id="claim:mixed",
            epistemic_type=ObservationEpistemicType.INFERENCE,
            statement="A mixed-revision claim should not be a source-level Observation.",
            supports=(
                SupportRef(SupportType.EVIDENCE_FACT, fact_old.evidence_id),
                SupportRef(SupportType.EVIDENCE_FACT, fact_new.evidence_id),
            ),
        )
