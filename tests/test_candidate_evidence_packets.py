import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.candidate_evidence_packet_contracts import CandidateEvidencePacket
from lemmamind.candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
)
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from lemmamind.change_contracts import (
    ArtifactDelta,
    ArtifactDeltaType,
    StructuralDelta,
    StructuralDeltaType,
)
from lemmamind.change_intelligence import DeterministicChangeService
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
)
from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
from lemmamind.storage import SQLiteContractStore


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)
SOURCE_ID = "github:packet-test"
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{'a' * 40}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{'b' * 40}"
PREVIOUS_CAPTURE_ID = "capture:packet:previous"
CURRENT_CAPTURE_ID = "capture:packet:current"
PREVIOUS_EXTRACTION_RUN_ID = "run:packet:extract:previous"
CURRENT_EXTRACTION_RUN_ID = "run:packet:extract:current"
CHANGE_RUN_ID = "run:packet:change"
SEGMENTATION_RUN_ID = "run:packet:segmentation"
REDUCTION_RUN_ID = "run:packet:reduction"
PATH = "src/core.py"
PREVIOUS_ARTIFACT_ID = "artifact:packet:previous"
CURRENT_ARTIFACT_ID = "artifact:packet:current"
ARTIFACT_DELTA_ID = "artifact-delta:packet"
STRUCTURAL_DELTA_ID = "structural-delta:packet"
PREVIOUS_EVIDENCE_ID = "fact:packet:previous"
CURRENT_EVIDENCE_ID = "fact:packet:current"
PREVIOUS_ASSERTION_ID = "assertion:packet:previous"
CURRENT_ASSERTION_ID = "assertion:packet:current"


class FixedClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        self.value += timedelta(milliseconds=1)
        return self.value


class Ids:
    def __init__(self, prefix):
        self.prefix = prefix
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"{self.prefix}-{self.value}"


def digest_json(value):
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def extraction_run(run_id, facts, assertions, offset):
    payload = DeterministicChangeService._extraction_output_payload(
        tuple(facts),
        tuple(assertions),
    )
    return PipelineRun(
        run_id=run_id,
        run_type=RunType.EXTRACTION,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="deterministic-evidence.v1",
        started_at=NOW + timedelta(seconds=offset),
        finished_at=NOW + timedelta(seconds=offset + 1),
        inputs_hash="sha256:" + "0" * 64,
        outputs_hash=digest_json(payload),
    )


def prepare(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")

    previous_manifest = CaptureManifest(
        capture_id=PREVIOUS_CAPTURE_ID,
        source_revision_id=PREVIOUS_REVISION_ID,
        capture_policy_version="packet-test.v1",
        captured_at=NOW,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=PREVIOUS_ARTIFACT_ID,
                source_locator=PATH,
                content_hash="sha256:" + "1" * 64,
                media_type="text/plain",
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    current_manifest = CaptureManifest(
        capture_id=CURRENT_CAPTURE_ID,
        source_revision_id=CURRENT_REVISION_ID,
        capture_policy_version="packet-test.v1",
        captured_at=NOW + timedelta(seconds=1),
        artifacts=(
            CaptureArtifactRef(
                artifact_id=CURRENT_ARTIFACT_ID,
                source_locator=PATH,
                content_hash="sha256:" + "2" * 64,
                media_type="text/plain",
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )

    previous_fact = EvidenceFact(
        evidence_id=PREVIOUS_EVIDENCE_ID,
        artifact_id=PREVIOUS_ARTIFACT_ID,
        locator=f"{PATH}#content",
        raw_value="old",
        normalized_value="old",
        extractor_name="content",
        extractor_version="1",
        run_id=PREVIOUS_EXTRACTION_RUN_ID,
    )
    current_fact = EvidenceFact(
        evidence_id=CURRENT_EVIDENCE_ID,
        artifact_id=CURRENT_ARTIFACT_ID,
        locator=f"{PATH}#content",
        raw_value="new",
        normalized_value="new",
        extractor_name="content",
        extractor_version="1",
        run_id=CURRENT_EXTRACTION_RUN_ID,
    )
    previous_assertion = SourceAssertion(
        assertion_id=PREVIOUS_ASSERTION_ID,
        artifact_id=PREVIOUS_ARTIFACT_ID,
        locator=f"{PATH}:L1-L1",
        statement="old authored statement",
        extractor_name="authored",
        extractor_version="1",
        run_id=PREVIOUS_EXTRACTION_RUN_ID,
    )
    current_assertion = SourceAssertion(
        assertion_id=CURRENT_ASSERTION_ID,
        artifact_id=CURRENT_ARTIFACT_ID,
        locator=f"{PATH}:L1-L1",
        statement="new authored statement",
        extractor_name="authored",
        extractor_version="1",
        run_id=CURRENT_EXTRACTION_RUN_ID,
    )
    previous_run = extraction_run(
        PREVIOUS_EXTRACTION_RUN_ID,
        (previous_fact,),
        (previous_assertion,),
        2,
    )
    current_run = extraction_run(
        CURRENT_EXTRACTION_RUN_ID,
        (current_fact,),
        (current_assertion,),
        4,
    )

    artifact_delta = ArtifactDelta(
        artifact_delta_id=ARTIFACT_DELTA_ID,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        previous_capture_id=PREVIOUS_CAPTURE_ID,
        current_capture_id=CURRENT_CAPTURE_ID,
        source_locator=PATH,
        change_type=ArtifactDeltaType.CONTENT_CHANGED,
        previous_artifact_id=PREVIOUS_ARTIFACT_ID,
        current_artifact_id=CURRENT_ARTIFACT_ID,
        previous_retrieval_status=RetrievalStatus.CAPTURED,
        current_retrieval_status=RetrievalStatus.CAPTURED,
        previous_content_hash="sha256:" + "1" * 64,
        current_content_hash="sha256:" + "2" * 64,
        previous_media_type="text/plain",
        current_media_type="text/plain",
        diff_run_id=CHANGE_RUN_ID,
    )
    structural_delta = StructuralDelta(
        structural_delta_id=STRUCTURAL_DELTA_ID,
        artifact_delta_id=ARTIFACT_DELTA_ID,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        source_locator=PATH,
        structural_key="content@1:#content",
        change_type=StructuralDeltaType.MODIFIED,
        extractor_name="content",
        extractor_version="1",
        previous_evidence_id=PREVIOUS_EVIDENCE_ID,
        current_evidence_id=CURRENT_EVIDENCE_ID,
        previous_locator=f"{PATH}#content",
        current_locator=f"{PATH}#content",
        previous_value="old",
        current_value="new",
        diff_run_id=CHANGE_RUN_ID,
    )

    candidate = IntervalCandidateSegment(
        interval_candidate_segment_id="candidate:packet",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        commit_path_snapshot_id="snapshot:packet",
        commit_sha="b" * 40,
        commit_ordinal=1,
        path_group='top-level:"src"',
        chunk_ordinal=1,
        git_path_delta_ids=("git-delta:packet",),
        paths=(PATH,),
        segmentation_run_id=SEGMENTATION_RUN_ID,
    )
    reduction = CandidateFactualReduction(
        candidate_factual_reduction_id="reduction:packet",
        interval_candidate_segment_id=candidate.interval_candidate_segment_id,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(PATH,),
        affected_file_plan_ids=("plan:packet",),
        capture_scoped_paths=(PATH,),
        artifact_delta_ids=(ARTIFACT_DELTA_ID,),
        artifact_delta_paths=(PATH,),
        structural_delta_ids=(STRUCTURAL_DELTA_ID,),
        structural_delta_paths=(PATH,),
        assertion_changed_paths=(PATH,),
        signal_kinds=(
            CandidateSignalKind.AUTHORED_ASSERTION_CHANGE,
            CandidateSignalKind.STRUCTURAL_DELTA,
        ),
        disposition=CandidateReductionDisposition.RETAIN,
        diff_run_id="run:packet:diff",
        segmentation_run_id=SEGMENTATION_RUN_ID,
        planner_run_id="run:packet:planner",
        previous_capture_id=PREVIOUS_CAPTURE_ID,
        current_capture_id=CURRENT_CAPTURE_ID,
        previous_extraction_run_id=PREVIOUS_EXTRACTION_RUN_ID,
        current_extraction_run_id=CURRENT_EXTRACTION_RUN_ID,
        change_run_id=CHANGE_RUN_ID,
        reduction_run_id=REDUCTION_RUN_ID,
    )
    reduction_run = PipelineRun(
        run_id=REDUCTION_RUN_ID,
        run_type=RunType.OTHER,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="candidate-factual-reduction.v1",
        started_at=NOW + timedelta(seconds=6),
        finished_at=NOW + timedelta(seconds=7),
        inputs_hash="sha256:" + "0" * 64,
        outputs_hash=digest_json(
            [reduction.model_dump(mode="json", by_alias=True)]
        ),
    )

    store.put_many(
        (
            previous_manifest,
            current_manifest,
            previous_fact,
            current_fact,
            previous_assertion,
            current_assertion,
            previous_run,
            current_run,
            artifact_delta,
            structural_delta,
            candidate,
            reduction,
            reduction_run,
        )
    )
    return store


def test_packet_builder_produces_bounded_auditable_candidate_input(tmp_path) -> None:
    store = prepare(tmp_path)
    result = CandidateEvidencePacketService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=20)),
        id_factory=Ids("packet"),
    ).build_reduction(REDUCTION_RUN_ID)

    assert len(result.packets) == 1
    packet = result.packets[0]
    assert packet.paths == (PATH,)
    assert packet.artifact_delta_ids == (ARTIFACT_DELTA_ID,)
    assert packet.structural_delta_total == 1
    assert packet.structural_delta_omitted_count == 0
    assert packet.structural_delta_previews[0].structural_delta_id == STRUCTURAL_DELTA_ID
    assert packet.assertion_snapshot_total == 2
    assert {item.assertion_id for item in packet.assertion_previews} == {
        PREVIOUS_ASSERTION_ID,
        CURRENT_ASSERTION_ID,
    }
    assert packet.extraction_gap_signal_ids == ()
    assert store.get(CandidateEvidencePacket, packet.candidate_evidence_packet_id) == packet


def test_packet_outputs_hash_is_stable_across_packet_run_ids(tmp_path) -> None:
    store = prepare(tmp_path)
    first = CandidateEvidencePacketService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=20)),
        id_factory=Ids("first"),
    ).build_reduction(REDUCTION_RUN_ID)
    second = CandidateEvidencePacketService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=30)),
        id_factory=Ids("second"),
    ).build_reduction(REDUCTION_RUN_ID)

    assert first.run.run_id != second.run.run_id
    assert first.packets[0].candidate_evidence_packet_id != second.packets[0].candidate_evidence_packet_id
    assert first.run.outputs_hash == second.run.outputs_hash


def test_packet_builder_rejects_post_run_extraction_tampering(tmp_path) -> None:
    store = prepare(tmp_path)
    store.put(
        SourceAssertion(
            assertion_id="assertion:tampered",
            artifact_id=CURRENT_ARTIFACT_ID,
            locator=f"{PATH}:L2-L2",
            statement="appended after extraction completion",
            extractor_name="authored",
            extractor_version="1",
            run_id=CURRENT_EXTRACTION_RUN_ID,
        )
    )

    with pytest.raises(
        CandidateEvidencePacketError,
        match="output envelope does not authenticate",
    ):
        CandidateEvidencePacketService(store).build_reduction(REDUCTION_RUN_ID)
