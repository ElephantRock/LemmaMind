from datetime import datetime, timezone

import pytest

from lemmamind.candidate_evidence_packet_contracts import AssertionSnapshotSide
from lemmamind.candidate_evidence_packets import CandidateEvidencePacketService
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from lemmamind.change_interpretation import (
    ChangeInterpretationService,
    InterpretationProposal,
)
from lemmamind.change_interpretation_contracts import (
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
    ChangeInterpretationType,
)
from lemmamind.change_interpretation_generation_contracts import (
    ChangeInterpretationGeneration,
)
from lemmamind.change_intelligence import DeterministicChangeService
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureArtifactRef,
    CaptureManifest,
    PipelineRun,
    RetrievalStatus,
    ReviewDecisionType,
    RunType,
    SourceAssertion,
)
from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
from lemmamind.mechanism_review import (
    MechanismReviewGroupingError,
    MechanismReviewGroupingService,
)
from lemmamind.mechanism_review_contracts import MechanismReviewItem
from lemmamind.review import ReviewFeedbackService
from lemmamind.storage import SQLiteContractStore


NOW = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)
SOURCE_ID = "github:mechanism-grouping"
PREVIOUS_REVISION_ID = SOURCE_ID + "@" + "a" * 40
CURRENT_REVISION_ID = SOURCE_ID + "@" + "b" * 40
PREVIOUS_CAPTURE_ID = "capture:previous:grouping"
CURRENT_CAPTURE_ID = "capture:current:grouping"
PREVIOUS_EXTRACTION_RUN_ID = "run:extraction:previous:grouping"
CURRENT_EXTRACTION_RUN_ID = "run:extraction:current:grouping"
SEGMENTATION_RUN_ID = "run:segmentation:grouping"
REDUCTION_RUN_ID = "run:reduction:grouping"
PACKET_RUN_ID = "run:candidate-evidence-packet:grouping"
INTERPRETATION_RUN_ID = "run:change-interpretation:grouping"


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"grouping-{self.value}"


class GroupingInterpreter:
    name = "test-interpreter"
    version = "1"

    def interpret(self, packet):
        index = 1 if packet.paths[0].endswith("mechanism_1.py") else 2
        assertion = next(
            item
            for item in packet.assertion_previews
            if item.side is AssertionSnapshotSide.CURRENT
        )
        mechanism = (
            "Runtime  authority check"
            if index == 1
            else "runtime authority CHECK"
        )
        return InterpretationProposal(
            interpretation_types=(ChangeInterpretationType.AUTHORITY_GOVERNANCE,),
            mechanism=mechanism,
            summary=f"Candidate {index} changes the runtime authority check.",
            supports=(
                ChangeInterpretationSupportRef(
                    support_type=ChangeInterpretationSupportType.SOURCE_ASSERTION,
                    support_id=assertion.assertion_id,
                ),
            ),
        )


class DecliningInterpreter:
    name = "test-interpreter"
    version = "1"

    def interpret(self, packet):
        return None


def candidate(index: int) -> IntervalCandidateSegment:
    path = f"src/mechanism_{index}.py"
    return IntervalCandidateSegment(
        interval_candidate_segment_id=f"candidate:{index}",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        commit_path_snapshot_id=f"snapshot:{index}",
        commit_sha=f"{index:040x}",
        commit_ordinal=index,
        path_group="src",
        chunk_ordinal=1,
        git_path_delta_ids=(f"git-delta:{index}",),
        paths=(path,),
        segmentation_run_id=SEGMENTATION_RUN_ID,
    )


def reduction(index: int) -> CandidateFactualReduction:
    path = f"src/mechanism_{index}.py"
    return CandidateFactualReduction(
        candidate_factual_reduction_id=f"reduction:{index}",
        interval_candidate_segment_id=f"candidate:{index}",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(path,),
        affected_file_plan_ids=(f"plan:{index}",),
        capture_scoped_paths=(path,),
        assertion_changed_paths=(path,),
        signal_kinds=(CandidateSignalKind.AUTHORED_ASSERTION_CHANGE,),
        disposition=CandidateReductionDisposition.RETAIN,
        diff_run_id="run:diff:grouping",
        segmentation_run_id=SEGMENTATION_RUN_ID,
        planner_run_id="run:planner:grouping",
        previous_capture_id=PREVIOUS_CAPTURE_ID,
        current_capture_id=CURRENT_CAPTURE_ID,
        previous_extraction_run_id=PREVIOUS_EXTRACTION_RUN_ID,
        current_extraction_run_id=CURRENT_EXTRACTION_RUN_ID,
        change_run_id="run:change:grouping",
        reduction_run_id=REDUCTION_RUN_ID,
    )


def _artifact(side: str, index: int) -> CaptureArtifactRef:
    path = f"src/mechanism_{index}.py"
    return CaptureArtifactRef(
        artifact_id=f"artifact:{side}:{index}",
        source_locator=path,
        content_hash="sha256:" + ("1" if side == "previous" else "2") * 64,
        media_type="text/plain",
        retrieval_status=RetrievalStatus.CAPTURED,
    )


def _assertion(side: str, index: int) -> SourceAssertion:
    path = f"src/mechanism_{index}.py"
    run_id = (
        PREVIOUS_EXTRACTION_RUN_ID
        if side == "previous"
        else CURRENT_EXTRACTION_RUN_ID
    )
    statement = (
        "Runtime authority was checked after mutation."
        if side == "previous"
        else "Runtime authority is checked before mutation."
    )
    return SourceAssertion(
        assertion_id=f"assertion:{side}:{index}",
        artifact_id=f"artifact:{side}:{index}",
        locator=f"{path}:L1-L1",
        statement=statement,
        extractor_name="markdown-prose",
        extractor_version="1",
        run_id=run_id,
    )


def _extraction_run(run_id: str, assertions: tuple[SourceAssertion, ...]) -> PipelineRun:
    outputs = DeterministicChangeService._extraction_output_payload((), assertions)
    return PipelineRun(
        run_id=run_id,
        run_type=RunType.EXTRACTION,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="deterministic-evidence.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash="sha256:" + "0" * 64,
        outputs_hash=CandidateEvidencePacketService._digest_json(outputs),
    )


def seed_authenticated_generation(
    store: SQLiteContractStore,
    *,
    interpreter=None,
):
    candidates = (candidate(1), candidate(2))
    reductions = (reduction(1), reduction(2))
    previous_assertions = (_assertion("previous", 1), _assertion("previous", 2))
    current_assertions = (_assertion("current", 1), _assertion("current", 2))
    previous_manifest = CaptureManifest(
        capture_id=PREVIOUS_CAPTURE_ID,
        source_revision_id=PREVIOUS_REVISION_ID,
        capture_policy_version="mechanism-grouping.v1",
        captured_at=NOW,
        artifacts=(_artifact("previous", 1), _artifact("previous", 2)),
    )
    current_manifest = CaptureManifest(
        capture_id=CURRENT_CAPTURE_ID,
        source_revision_id=CURRENT_REVISION_ID,
        capture_policy_version="mechanism-grouping.v1",
        captured_at=NOW,
        artifacts=(_artifact("current", 1), _artifact("current", 2)),
    )
    reduction_run = PipelineRun(
        run_id=REDUCTION_RUN_ID,
        run_type=RunType.OTHER,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="candidate-factual-reduction.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash="sha256:" + "0" * 64,
        outputs_hash=CandidateEvidencePacketService._digest_json(
            [item.model_dump(mode="json", by_alias=True) for item in reductions]
        ),
    )
    store.put_many(
        (
            *candidates,
            *reductions,
            previous_manifest,
            current_manifest,
            *previous_assertions,
            *current_assertions,
            _extraction_run(PREVIOUS_EXTRACTION_RUN_ID, previous_assertions),
            _extraction_run(CURRENT_EXTRACTION_RUN_ID, current_assertions),
            reduction_run,
        )
    )
    packets = CandidateEvidencePacketService(
        store,
        clock=lambda: NOW,
        id_factory=lambda: "grouping",
    ).build_reduction(REDUCTION_RUN_ID)
    assert packets.run.run_id == PACKET_RUN_ID
    interpreted = ChangeInterpretationService(
        store,
        clock=lambda: NOW,
        id_factory=lambda: "grouping",
    ).produce_packet_run(
        packets.run.run_id,
        interpreter or GroupingInterpreter(),
    )
    assert interpreted.run.run_id == INTERPRETATION_RUN_ID
    return packets, interpreted


def test_exact_canonical_mechanism_grouping_collapses_duplicate_labels(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, interpreted = seed_authenticated_generation(store)
    service = MechanismReviewGroupingService(
        store, clock=lambda: NOW, id_factory=Ids()
    )

    result = service.group_interpretation_run(interpreted.run.run_id)

    assert len(result.items) == 1
    item = result.items[0]
    assert item.canonical_mechanism_key == "runtime authority check"
    assert item.change_interpretation_ids == tuple(
        sorted(value.change_interpretation_id for value in interpreted.interpretations)
    )
    assert item.interval_candidate_segment_ids == ("candidate:1", "candidate:2")
    assert item.candidate_factual_reduction_ids == ("reduction:1", "reduction:2")
    assert len(item.candidate_evidence_packet_ids) == 2
    assert store.get(MechanismReviewItem, item.mechanism_review_item_id) == item


def test_grouping_outputs_hash_is_stable_across_grouping_run_ids(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, interpreted = seed_authenticated_generation(store)
    ids = Ids()
    service = MechanismReviewGroupingService(store, clock=lambda: NOW, id_factory=ids)

    first = service.group_interpretation_run(interpreted.run.run_id)
    second = service.group_interpretation_run(interpreted.run.run_id)

    assert first.run.run_id != second.run.run_id
    assert first.items[0].mechanism_review_item_id != second.items[0].mechanism_review_item_id
    assert first.run.outputs_hash == second.run.outputs_hash


def test_grouping_fails_closed_on_post_run_interpretation_injection(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, interpreted = seed_authenticated_generation(store)
    injected = interpreted.interpretations[0].model_copy(
        update={"change_interpretation_id": "interpretation:injected"}
    )
    store.put(injected)

    with pytest.raises(
        MechanismReviewGroupingError,
        match="does not exactly name semantic outputs",
    ):
        MechanismReviewGroupingService(store).group_interpretation_run(
            interpreted.run.run_id
        )


def test_grouping_reauthenticates_packet_generation_before_review_projection(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    packets, interpreted = seed_authenticated_generation(store)
    injected = packets.packets[0].model_copy(
        update={"candidate_evidence_packet_id": "packet:injected"}
    )
    store.put(injected)

    with pytest.raises(
        MechanismReviewGroupingError,
        match="failed upstream reconstruction",
    ):
        MechanismReviewGroupingService(store).group_interpretation_run(
            interpreted.run.run_id
        )


def test_empty_interpretation_generation_authenticates_inputs_before_empty_review(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, interpreted = seed_authenticated_generation(
        store,
        interpreter=DecliningInterpreter(),
    )
    assert interpreted.interpretations == ()

    grouped = MechanismReviewGroupingService(
        store,
        clock=lambda: NOW,
        id_factory=Ids(),
    ).group_interpretation_run(interpreted.run.run_id)
    assert grouped.items == ()

    forged_run_id = "run:change-interpretation:forged-empty"
    forged_run = interpreted.run.model_copy(
        update={
            "run_id": forged_run_id,
            "inputs_hash": "sha256:" + "0" * 64,
        }
    )
    forged_generation = ChangeInterpretationGeneration(
        change_interpretation_generation_id=(
            f"change-interpretation-generation:{forged_run_id}"
        ),
        interpretation_run_id=forged_run_id,
        packet_run_id=PACKET_RUN_ID,
        interpreter_name="test-interpreter",
        interpreter_version="1",
        policy_version="change-interpretation.candidate.v1",
        change_interpretation_ids=(),
    )
    store.put_many((forged_run, forged_generation))

    with pytest.raises(
        MechanismReviewGroupingError,
        match="input envelope does not authenticate",
    ):
        MechanismReviewGroupingService(store).group_interpretation_run(forged_run_id)


def test_mechanism_review_item_is_append_only_reviewable(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _, interpreted = seed_authenticated_generation(store)
    grouped = MechanismReviewGroupingService(
        store, clock=lambda: NOW, id_factory=Ids()
    ).group_interpretation_run(interpreted.run.run_id)
    subject = grouped.items[0]

    feedback = ReviewFeedbackService(
        store, clock=lambda: NOW, id_factory=Ids()
    ).record(
        subject_type="MechanismReviewItem",
        subject_id=subject.mechanism_review_item_id,
        decision=ReviewDecisionType.ACCEPT,
        reviewer_id="reviewer:human",
    )

    assert feedback.feedback.subject_type == "MechanismReviewItem"
    assert store.get(MechanismReviewItem, subject.mechanism_review_item_id) == subject
