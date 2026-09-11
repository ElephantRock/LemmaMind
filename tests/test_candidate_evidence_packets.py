import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from lemmamind.candidate_evidence_packet_contracts import (
    AssertionSnapshotSide,
    CandidateEvidencePacket,
)
from lemmamind.candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
)
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from lemmamind.capture_planning_contracts import (
    AffectedFileCapturePlan,
    CapturePlanDisposition,
    CapturePlanReason,
    CapturePlanSide,
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
from lemmamind.path_change_contracts import ChangeSurface
from lemmamind.storage import SQLiteContractStore
from tests.m5_packet_fixture import seed_path_pipeline


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)
SOURCE_ID = "github:packet-test"
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{'a' * 40}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{'b' * 40}"
PREVIOUS_CAPTURE_ID = "capture:packet:previous"
CURRENT_CAPTURE_ID = "capture:packet:current"
PREVIOUS_EXTRACTION_RUN_ID = "run:packet:extract:previous"
CURRENT_EXTRACTION_RUN_ID = "run:packet:extract:current"
CHANGE_RUN_ID = "run:packet:change"
DIFF_RUN_ID = "run:packet:diff"
SEGMENTATION_RUN_ID = "run:packet:segmentation"
PLANNER_RUN_ID = "run:packet:planner"
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
EXTRACTOR_PROFILE = (
    {"name": "content", "version": "1"},
    {"name": "authored", "version": "1"},
)


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


def artifact_inputs(manifest):
    return [
        {
            "artifact_id": item.artifact_id,
            "source_locator": item.source_locator,
            "retrieval_status": item.retrieval_status.value,
            "content_hash": item.content_hash,
            "media_type": item.media_type,
        }
        for item in manifest.artifacts
    ]


def extraction_run(run_id, facts, assertions, offset, manifest):
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
        inputs_hash=digest_json(
            {
                "capture_manifest": manifest.model_dump(mode="json", by_alias=True),
                "artifact_extractors": list(EXTRACTOR_PROFILE),
                "policy_version": "deterministic-evidence.v1",
            }
        ),
        outputs_hash=digest_json(payload),
    )



def prepare(tmp_path):
    from lemmamind.candidate_reduction import CandidateFactualReductionService

    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    seeded = seed_path_pipeline(
        store,
        source_id=SOURCE_ID,
        previous_revision_id=PREVIOUS_REVISION_ID,
        current_revision_id=CURRENT_REVISION_ID,
        diff_run_id=DIFF_RUN_ID,
        segmentation_run_id=SEGMENTATION_RUN_ID,
        planner_run_id=PLANNER_RUN_ID,
        tracking_assignment_id="tracking:packet",
        now=NOW + timedelta(seconds=6),
        path_specs=(
            {
                "path": PATH,
                "previous_object_sha": "1" * 40,
                "current_object_sha": "2" * 40,
                "previous_size": 3,
                "current_size": 3,
            },
        ),
    )
    candidate = seeded.candidates[0]
    plan = seeded.plans[0]

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
        previous_manifest,
    )
    current_run = extraction_run(
        CURRENT_EXTRACTION_RUN_ID,
        (current_fact,),
        (current_assertion,),
        4,
        current_manifest,
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
    reduction = CandidateFactualReduction(
        candidate_factual_reduction_id=CandidateFactualReductionService._reduction_id(
            REDUCTION_RUN_ID, candidate.interval_candidate_segment_id
        ),
        interval_candidate_segment_id=candidate.interval_candidate_segment_id,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(PATH,),
        affected_file_plan_ids=(plan.affected_file_plan_id,),
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
        diff_run_id=DIFF_RUN_ID,
        segmentation_run_id=SEGMENTATION_RUN_ID,
        planner_run_id=PLANNER_RUN_ID,
        previous_capture_id=PREVIOUS_CAPTURE_ID,
        current_capture_id=CURRENT_CAPTURE_ID,
        previous_extraction_run_id=PREVIOUS_EXTRACTION_RUN_ID,
        current_extraction_run_id=CURRENT_EXTRACTION_RUN_ID,
        change_run_id=CHANGE_RUN_ID,
        reduction_run_id=REDUCTION_RUN_ID,
    )
    change_run = PipelineRun(
        run_id=CHANGE_RUN_ID,
        run_type=RunType.DIFF,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="candidate-factual-change.v1",
        started_at=NOW + timedelta(seconds=10),
        finished_at=NOW + timedelta(seconds=11),
        inputs_hash=digest_json(
            {
                "previous_capture_id": PREVIOUS_CAPTURE_ID,
                "current_capture_id": CURRENT_CAPTURE_ID,
                "previous_source_revision_id": PREVIOUS_REVISION_ID,
                "current_source_revision_id": CURRENT_REVISION_ID,
                "previous_extraction_run_id": PREVIOUS_EXTRACTION_RUN_ID,
                "current_extraction_run_id": CURRENT_EXTRACTION_RUN_ID,
                "artifact_extractors": list(EXTRACTOR_PROFILE),
                "policy_version": "candidate-factual-change.v1",
                "artifact_inputs": {
                    "previous": artifact_inputs(previous_manifest),
                    "current": artifact_inputs(current_manifest),
                },
            }
        ),
        outputs_hash=digest_json(
            {
                "artifact_deltas": [artifact_delta.model_dump(mode="json", by_alias=True)],
                "structural_deltas": [structural_delta.model_dump(mode="json", by_alias=True)],
            }
        ),
    )
    reduction_run = PipelineRun(
        run_id=REDUCTION_RUN_ID,
        run_type=RunType.OTHER,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="candidate-factual-reduction.v1",
        started_at=NOW + timedelta(seconds=12),
        finished_at=NOW + timedelta(seconds=13),
        inputs_hash=digest_json(
            {
                "diff_run_id": DIFF_RUN_ID,
                "segmentation_run_id": SEGMENTATION_RUN_ID,
                "planner_run_id": PLANNER_RUN_ID,
                "previous_capture": previous_manifest.model_dump(mode="json", by_alias=True),
                "current_capture": current_manifest.model_dump(mode="json", by_alias=True),
                "previous_extraction_run_id": PREVIOUS_EXTRACTION_RUN_ID,
                "current_extraction_run_id": CURRENT_EXTRACTION_RUN_ID,
                "artifact_extractors": list(EXTRACTOR_PROFILE),
                "change_run_id": CHANGE_RUN_ID,
                "candidates": [candidate.model_dump(mode="json", by_alias=True)],
                "affected_file_plans": [plan.model_dump(mode="json", by_alias=True)],
                "policy_version": "candidate-factual-reduction.v1",
            }
        ),
        outputs_hash=digest_json([reduction.model_dump(mode="json", by_alias=True)]),
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
            reduction,
            change_run,
            reduction_run,
        )
    )
    return store


def test_packet_builder_produces_bounded_auditable_candidate_input(tmp_path) -> None:
    store = prepare(tmp_path)
    result = CandidateEvidencePacketService(
        store,
        artifact_extractors=EXTRACTOR_PROFILE,
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
        artifact_extractors=EXTRACTOR_PROFILE,
        clock=FixedClock(NOW + timedelta(seconds=20)),
        id_factory=Ids("first"),
    ).build_reduction(REDUCTION_RUN_ID)
    second = CandidateEvidencePacketService(
        store,
        artifact_extractors=EXTRACTOR_PROFILE,
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
        CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE).build_reduction(REDUCTION_RUN_ID)


def test_packet_builder_rejects_self_hashed_reduction_that_omits_structural_evidence(
    tmp_path,
) -> None:
    store = prepare(tmp_path)
    originals = tuple(
        item
        for item in store.list(CandidateFactualReduction)
        if item.reduction_run_id == REDUCTION_RUN_ID
    )
    assert len(originals) == 1
    original = originals[0]
    original_run = store.get(PipelineRun, REDUCTION_RUN_ID)
    assert original_run is not None

    forged_run_id = "run:packet:reduction:forged"
    forged = original.model_copy(
        update={
            "candidate_factual_reduction_id": "reduction:packet:forged",
            "structural_delta_ids": (),
            "structural_delta_paths": (),
            "signal_kinds": (CandidateSignalKind.AUTHORED_ASSERTION_CHANGE,),
            "reduction_run_id": forged_run_id,
        }
    )
    forged_run = original_run.model_copy(
        update={
            "run_id": forged_run_id,
            "outputs_hash": digest_json(
                [forged.model_dump(mode="json", by_alias=True)]
            ),
        }
    )
    store.put_many((forged, forged_run))

    with pytest.raises(
        CandidateEvidencePacketError,
        match="disagrees with reconstructed upstream evidence",
    ):
        CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE).build_reduction(forged_run_id)


def test_assertion_preview_budget_reserves_both_snapshot_sides(tmp_path) -> None:
    store = prepare(tmp_path)
    previous = store.get(SourceAssertion, PREVIOUS_ASSERTION_ID)
    current = store.get(SourceAssertion, CURRENT_ASSERTION_ID)
    assert previous is not None and current is not None
    current_other = current.model_copy(
        update={
            "assertion_id": "assertion:current:other",
            "artifact_id": CURRENT_ARTIFACT_ID,
            "locator": f"{PATH}:L2-L2",
        }
    )
    items = (
        (AssertionSnapshotSide.CURRENT, "a.py", current),
        (AssertionSnapshotSide.CURRENT, "b.py", current_other),
        (AssertionSnapshotSide.PREVIOUS, "b.py", previous),
    )
    selected = CandidateEvidencePacketService(store)._round_robin_by_path(
        items,
        2,
        path_of=lambda item: item[1],
        item_key=lambda item: (item[0].value, item[2].assertion_id),
    )
    assert {item[0] for item in selected} == {
        AssertionSnapshotSide.PREVIOUS,
        AssertionSnapshotSide.CURRENT,
    }


def test_packet_contract_rejects_more_than_fifty_candidate_paths(tmp_path) -> None:
    store = prepare(tmp_path)
    packet = CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE).build_reduction(
        REDUCTION_RUN_ID
    ).packets[0]
    payload = packet.model_dump(mode="json", by_alias=True)
    payload["paths"] = [f"src/p{index}.py" for index in range(51)]
    with pytest.raises(ValidationError):
        CandidateEvidencePacket.model_validate(payload)



def test_segmentation_auth_rejects_incomplete_candidate_projection(tmp_path) -> None:
    from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
    from lemmamind.path_change_contracts import GitPathDelta, GitPathDiffSummary

    store = prepare(tmp_path)
    service = CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE)
    run = store.get(PipelineRun, SEGMENTATION_RUN_ID)
    summary = store.list(GitPathDiffSummary)[0]
    deltas = tuple(sorted(store.list(GitPathDelta), key=lambda item: item.path))
    with pytest.raises(CandidateEvidencePacketError, match="segmentation reconstruction"):
        service._authenticate_segmentation_generation(run, summary, deltas, ())


def test_planner_auth_rejects_incomplete_plan_projection(tmp_path) -> None:
    from lemmamind.path_change_contracts import GitPathDelta, GitPathDiffSummary

    store = prepare(tmp_path)
    service = CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE)
    run = store.get(PipelineRun, PLANNER_RUN_ID)
    summary = store.list(GitPathDiffSummary)[0]
    deltas = tuple(sorted(store.list(GitPathDelta), key=lambda item: item.path))
    previous_manifest = store.get(CaptureManifest, PREVIOUS_CAPTURE_ID)
    current_manifest = store.get(CaptureManifest, CURRENT_CAPTURE_ID)
    with pytest.raises(CandidateEvidencePacketError, match="plans disagree"):
        service._authenticate_plan_generation(
            run, summary, deltas, (), previous_manifest, current_manifest
        )


def test_assertion_preview_budget_alternates_sides_across_multiple_paths() -> None:
    def assertion(side, path, suffix):
        artifact_id = f"artifact:{side.value}:{suffix}"
        return (
            side,
            path,
            SourceAssertion(
                assertion_id=f"assertion:{side.value}:{suffix}",
                artifact_id=artifact_id,
                locator=f"{path}:L1-L1",
                statement=f"{side.value}-{suffix}",
                extractor_name="authored",
                extractor_version="1",
                run_id=f"run:{side.value}",
            ),
        )

    items = (
        assertion(AssertionSnapshotSide.PREVIOUS, "a.py", "a"),
        assertion(AssertionSnapshotSide.CURRENT, "a.py", "a"),
        assertion(AssertionSnapshotSide.PREVIOUS, "b.py", "b"),
        assertion(AssertionSnapshotSide.CURRENT, "b.py", "b"),
    )
    selected = CandidateEvidencePacketService._round_robin_by_path(
        items,
        2,
        path_of=lambda item: item[1],
        item_key=lambda item: (item[1], item[0].value, item[2].assertion_id),
    )
    assert {item[0] for item in selected} == {
        AssertionSnapshotSide.PREVIOUS,
        AssertionSnapshotSide.CURRENT,
    }
