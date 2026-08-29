from datetime import datetime, timezone

import pytest

from lemmamind.candidate_evidence_packet_contracts import (
    AssertionSnapshotSide,
    CandidateEvidencePacket,
    SourceAssertionPreview,
)
from lemmamind.candidate_evidence_packets import CandidateEvidencePacketService
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from lemmamind.change_interpretation import ChangeInterpretationService
from lemmamind.change_interpretation_contracts import (
    ChangeInterpretation,
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
    ChangeInterpretationType,
)
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    PipelineRun,
    ReviewDecisionType,
    RunType,
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
PACKET_RUN_ID = "run:packet:grouping"
INTERPRETATION_RUN_ID = "run:interpretation:grouping"


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"grouping-{self.value}"


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
        segmentation_run_id="run:segmentation:grouping",
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
        segmentation_run_id="run:segmentation:grouping",
        planner_run_id="run:planner:grouping",
        previous_capture_id="capture:previous:grouping",
        current_capture_id="capture:current:grouping",
        previous_extraction_run_id="run:extraction:previous:grouping",
        current_extraction_run_id="run:extraction:current:grouping",
        change_run_id="run:change:grouping",
        reduction_run_id="run:reduction:grouping",
    )


def packet(index: int) -> CandidateEvidencePacket:
    path = f"src/mechanism_{index}.py"
    return CandidateEvidencePacket(
        candidate_evidence_packet_id=f"packet:{index}",
        interval_candidate_segment_id=f"candidate:{index}",
        candidate_factual_reduction_id=f"reduction:{index}",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(path,),
        signal_kinds=(CandidateSignalKind.AUTHORED_ASSERTION_CHANGE,),
        assertion_snapshot_total=1,
        assertion_previews=(
            SourceAssertionPreview(
                assertion_id=f"assertion:{index}",
                side=AssertionSnapshotSide.CURRENT,
                source_locator=path,
                locator=f"{path}:L1-L1",
                statement_preview="Runtime authority is checked before mutation.",
                statement_truncated=False,
                extractor_name="markdown-prose",
                extractor_version="1",
            ),
        ),
        assertion_snapshot_omitted_count=0,
        structural_delta_total=0,
        structural_delta_omitted_count=0,
        segmentation_run_id="run:segmentation:grouping",
        reduction_run_id="run:reduction:grouping",
        previous_extraction_run_id="run:extraction:previous:grouping",
        current_extraction_run_id="run:extraction:current:grouping",
        change_run_id="run:change:grouping",
        packet_run_id=PACKET_RUN_ID,
    )


def interpretation(index: int, mechanism: str) -> ChangeInterpretation:
    return ChangeInterpretation(
        change_interpretation_id=f"interpretation:{index}",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        interval_candidate_segment_ids=(f"candidate:{index}",),
        candidate_factual_reduction_ids=(f"reduction:{index}",),
        candidate_evidence_packet_ids=(f"packet:{index}",),
        interpretation_types=(ChangeInterpretationType.AUTHORITY_GOVERNANCE,),
        mechanism=mechanism,
        summary=f"Candidate {index} changes the runtime authority check.",
        supports=(
            ChangeInterpretationSupportRef(
                support_type=(
                    ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION
                ),
                support_id=f"reduction:{index}",
            ),
            ChangeInterpretationSupportRef(
                support_type=ChangeInterpretationSupportType.SOURCE_ASSERTION,
                support_id=f"assertion:{index}",
            ),
        ),
        interpreter_name="test-interpreter",
        interpreter_version="1",
        interpretation_run_id=INTERPRETATION_RUN_ID,
    )


def seed_authenticated_generation(store: SQLiteContractStore) -> tuple[ChangeInterpretation, ...]:
    candidates = (candidate(1), candidate(2))
    reductions = (reduction(1), reduction(2))
    packets = (packet(1), packet(2))
    interpretations = (
        interpretation(1, "Runtime  authority check"),
        interpretation(2, "runtime authority CHECK"),
    )
    helper = MechanismReviewGroupingService(store, clock=lambda: NOW)
    packet_outputs = helper._digest_json(
        [CandidateEvidencePacketService._stable_packet_payload(item) for item in packets]
    )
    packet_run = PipelineRun(
        run_id=PACKET_RUN_ID,
        run_type=RunType.OTHER,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="candidate-evidence-packet.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash="sha256:" + "0" * 64,
        outputs_hash=packet_outputs,
    )
    interpretation_inputs = helper._digest_json(
        {
            "packet_run": packet_run.model_dump(mode="json", by_alias=True),
            "packets": [
                CandidateEvidencePacketService._stable_packet_payload(item)
                for item in packets
            ],
            "interpreter": {"name": "test-interpreter", "version": "1"},
            "policy_version": "change-interpretation.candidate.v1",
        }
    )
    interpretation_outputs = helper._digest_json(
        [
            ChangeInterpretationService._stable_interpretation_payload(item)
            for item in interpretations
        ]
    )
    interpretation_run = PipelineRun(
        run_id=INTERPRETATION_RUN_ID,
        run_type=RunType.REASONING,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="change-interpretation.candidate.v1",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=interpretation_inputs,
        outputs_hash=interpretation_outputs,
    )
    store.put_many(
        (*candidates, *reductions, *packets, packet_run, *interpretations, interpretation_run)
    )
    return interpretations


def test_exact_canonical_mechanism_grouping_collapses_duplicate_labels(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    seed_authenticated_generation(store)
    service = MechanismReviewGroupingService(
        store, clock=lambda: NOW, id_factory=Ids()
    )

    result = service.group_interpretation_run(INTERPRETATION_RUN_ID)

    assert len(result.items) == 1
    item = result.items[0]
    assert item.canonical_mechanism_key == "runtime authority check"
    assert item.change_interpretation_ids == ("interpretation:1", "interpretation:2")
    assert item.interval_candidate_segment_ids == ("candidate:1", "candidate:2")
    assert item.candidate_factual_reduction_ids == ("reduction:1", "reduction:2")
    assert item.candidate_evidence_packet_ids == ("packet:1", "packet:2")
    assert store.get(MechanismReviewItem, item.mechanism_review_item_id) == item


def test_grouping_outputs_hash_is_stable_across_grouping_run_ids(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    seed_authenticated_generation(store)
    ids = Ids()
    service = MechanismReviewGroupingService(store, clock=lambda: NOW, id_factory=ids)

    first = service.group_interpretation_run(INTERPRETATION_RUN_ID)
    second = service.group_interpretation_run(INTERPRETATION_RUN_ID)

    assert first.run.run_id != second.run.run_id
    assert first.items[0].mechanism_review_item_id != second.items[0].mechanism_review_item_id
    assert first.run.outputs_hash == second.run.outputs_hash


def test_grouping_fails_closed_on_post_run_interpretation_injection(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    seed_authenticated_generation(store)
    injected = interpretation(1, "Injected mechanism").model_copy(
        update={"change_interpretation_id": "interpretation:injected"}
    )
    store.put(injected)

    with pytest.raises(MechanismReviewGroupingError):
        MechanismReviewGroupingService(store).group_interpretation_run(
            INTERPRETATION_RUN_ID
        )


def test_mechanism_review_item_is_append_only_reviewable(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    seed_authenticated_generation(store)
    grouped = MechanismReviewGroupingService(
        store, clock=lambda: NOW, id_factory=Ids()
    ).group_interpretation_run(INTERPRETATION_RUN_ID)
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
