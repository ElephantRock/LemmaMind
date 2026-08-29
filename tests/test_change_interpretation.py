from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.candidate_evidence_packet_contracts import (
    CandidateEvidencePacket,
    StructuralDeltaPreview,
)
from lemmamind.candidate_evidence_packets import CandidateEvidencePacketService
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from lemmamind.change_contracts import StructuralDeltaType
from lemmamind.change_interpretation import (
    ChangeInterpretationError,
    ChangeInterpretationService,
    InterpretationProposal,
)
from lemmamind.change_interpretation_contracts import (
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
    ChangeInterpretationType,
)
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    PipelineRun,
    RunType,
    ValidationState,
)
from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
from lemmamind.storage import SQLiteContractStore


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)
SOURCE_ID = "github:interpretation-test"
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{'a' * 40}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{'b' * 40}"
CANDIDATE_ID = "candidate:interpretation"
REDUCTION_ID = "reduction:interpretation"
REDUCTION_RUN_ID = "run:reduction:interpretation"
PACKET_ID = "packet:interpretation"
PACKET_RUN_ID = "run:packet:interpretation"
STRUCTURAL_ID = "structural:interpretation"
PATH = "src/clock.py"


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


class SupportedInterpreter:
    name = "fixture-interpreter"
    version = "1"

    def interpret(self, packet):
        return InterpretationProposal(
            interpretation_types=(ChangeInterpretationType.TEMPORAL_CORRECTNESS,),
            mechanism="Preserve timeout deadlines across wall-clock changes",
            summary=(
                "Timeout accounting moves to a stable elapsed-time basis so a wall-clock "
                "adjustment cannot silently extend or shorten worker lifetime."
            ),
            supports=(
                ChangeInterpretationSupportRef(
                    support_type=ChangeInterpretationSupportType.STRUCTURAL_DELTA,
                    support_id=STRUCTURAL_ID,
                ),
            ),
        )


class DecliningInterpreter:
    name = "fixture-interpreter"
    version = "1"

    def interpret(self, packet):
        return None


class ForeignSupportInterpreter:
    name = "fixture-interpreter"
    version = "1"

    def interpret(self, packet):
        return InterpretationProposal(
            interpretation_types=(ChangeInterpretationType.MODIFICATION,),
            mechanism="Unsupported mechanism",
            summary="This proposal references evidence that was never visible in the packet.",
            supports=(
                ChangeInterpretationSupportRef(
                    support_type=ChangeInterpretationSupportType.STRUCTURAL_DELTA,
                    support_id="structural:foreign",
                ),
            ),
        )


class GapAwareInterpreter:
    name = "fixture-interpreter"
    version = "1"

    def interpret(self, packet):
        return InterpretationProposal(
            interpretation_types=(ChangeInterpretationType.TEMPORAL_CORRECTNESS,),
            mechanism="Preserve timeout deadlines across wall-clock changes",
            summary="The supported path changes timeout accounting, with incomplete nearby extraction coverage.",
            uncertainty_notes=(
                "One candidate path has incomplete deterministic extraction coverage.",
            ),
            supports=(
                ChangeInterpretationSupportRef(
                    support_type=ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL,
                    support_id="gap:interpretation",
                ),
                ChangeInterpretationSupportRef(
                    support_type=ChangeInterpretationSupportType.STRUCTURAL_DELTA,
                    support_id=STRUCTURAL_ID,
                ),
            ),
        )


def prepare(tmp_path, *, gap=False):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    candidate = IntervalCandidateSegment(
        interval_candidate_segment_id=CANDIDATE_ID,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        commit_path_snapshot_id="snapshot:interpretation",
        commit_sha="b" * 40,
        commit_ordinal=1,
        path_group='top-level:"src"',
        chunk_ordinal=1,
        git_path_delta_ids=("git-delta:interpretation",),
        paths=(PATH,),
        segmentation_run_id="run:segmentation:interpretation",
    )
    reduction = CandidateFactualReduction(
        candidate_factual_reduction_id=REDUCTION_ID,
        interval_candidate_segment_id=CANDIDATE_ID,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(PATH,),
        affected_file_plan_ids=("plan:interpretation",),
        capture_scoped_paths=(PATH,),
        artifact_delta_ids=("artifact-delta:interpretation",),
        artifact_delta_paths=(PATH,),
        structural_delta_ids=(STRUCTURAL_ID,),
        structural_delta_paths=(PATH,),
        signal_kinds=(CandidateSignalKind.STRUCTURAL_DELTA,),
        disposition=CandidateReductionDisposition.RETAIN,
        diff_run_id="run:diff:interpretation",
        segmentation_run_id="run:segmentation:interpretation",
        planner_run_id="run:planner:interpretation",
        previous_capture_id="capture:previous:interpretation",
        current_capture_id="capture:current:interpretation",
        previous_extraction_run_id="run:extract:previous:interpretation",
        current_extraction_run_id="run:extract:current:interpretation",
        change_run_id="run:change:interpretation",
        reduction_run_id=REDUCTION_RUN_ID,
    )
    packet = CandidateEvidencePacket(
        candidate_evidence_packet_id=PACKET_ID,
        interval_candidate_segment_id=CANDIDATE_ID,
        candidate_factual_reduction_id=REDUCTION_ID,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(PATH,),
        signal_kinds=(CandidateSignalKind.STRUCTURAL_DELTA,),
        artifact_delta_ids=("artifact-delta:interpretation",),
        structural_delta_total=1,
        structural_delta_previews=(
            StructuralDeltaPreview(
                structural_delta_id=STRUCTURAL_ID,
                source_locator=PATH,
                structural_key="clock@1:timeout_basis",
                change_type=StructuralDeltaType.MODIFIED,
                extractor_name="clock",
                extractor_version="1",
                previous_value_preview='"wall"',
                current_value_preview='"monotonic"',
            ),
        ),
        structural_delta_omitted_count=0,
        assertion_snapshot_total=0,
        assertion_snapshot_omitted_count=0,
        extraction_gap_signal_ids=(("gap:interpretation",) if gap else ()),
        extraction_gap_paths=((PATH,) if gap else ()),
        segmentation_run_id="run:segmentation:interpretation",
        reduction_run_id=REDUCTION_RUN_ID,
        previous_extraction_run_id="run:extract:previous:interpretation",
        current_extraction_run_id="run:extract:current:interpretation",
        change_run_id="run:change:interpretation",
        packet_run_id=PACKET_RUN_ID,
    )
    packet_run = PipelineRun(
        run_id=PACKET_RUN_ID,
        run_type=RunType.OTHER,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="candidate-evidence-packet.v1",
        started_at=NOW,
        finished_at=NOW + timedelta(seconds=1),
        inputs_hash="sha256:" + "0" * 64,
        outputs_hash=ChangeInterpretationService._digest_json(
            [CandidateEvidencePacketService._stable_packet_payload(packet)]
        ),
    )
    store.put_many((candidate, reduction, packet, packet_run))
    return store


def test_interpretation_service_persists_only_packet_supported_candidate_output(tmp_path) -> None:
    store = prepare(tmp_path)
    result = ChangeInterpretationService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=10)),
        id_factory=Ids("interpretation"),
    ).produce_packet_run(PACKET_RUN_ID, SupportedInterpreter())

    assert result.run.run_type is RunType.REASONING
    assert len(result.interpretations) == 1
    item = result.interpretations[0]
    assert item.validation_state is ValidationState.CANDIDATE
    assert item.interpreter_name == "fixture-interpreter"
    assert item.interpreter_version == "1"
    assert item.candidate_evidence_packet_ids == (PACKET_ID,)
    assert item.candidate_factual_reduction_ids == (REDUCTION_ID,)
    assert {
        (support.support_type, support.support_id) for support in item.supports
    } == {
        (
            ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION,
            REDUCTION_ID,
        ),
        (ChangeInterpretationSupportType.STRUCTURAL_DELTA, STRUCTURAL_ID),
    }


def test_interpreter_may_decline_low_signal_candidate(tmp_path) -> None:
    store = prepare(tmp_path)
    result = ChangeInterpretationService(store).produce_packet_run(
        PACKET_RUN_ID,
        DecliningInterpreter(),
    )

    assert result.interpretations == ()


def test_interpretation_service_rejects_support_outside_packet(tmp_path) -> None:
    store = prepare(tmp_path)

    with pytest.raises(ChangeInterpretationError, match="outside the exact bounded evidence packet"):
        ChangeInterpretationService(store).produce_packet_run(
            PACKET_RUN_ID,
            ForeignSupportInterpreter(),
        )


def test_gap_bearing_packet_requires_explicit_gap_support_and_uncertainty(tmp_path) -> None:
    store = prepare(tmp_path, gap=True)

    with pytest.raises(ChangeInterpretationError, match="must expose every packet extraction-gap signal"):
        ChangeInterpretationService(store).produce_packet_run(
            PACKET_RUN_ID,
            SupportedInterpreter(),
        )

    result = ChangeInterpretationService(
        store,
        id_factory=Ids("gap-interpretation"),
    ).produce_packet_run(PACKET_RUN_ID, GapAwareInterpreter())
    assert result.interpretations[0].uncertainty_notes


def test_interpretation_outputs_hash_is_stable_across_reasoning_run_ids(tmp_path) -> None:
    store = prepare(tmp_path)
    first = ChangeInterpretationService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=10)),
        id_factory=Ids("first"),
    ).produce_packet_run(PACKET_RUN_ID, SupportedInterpreter())
    second = ChangeInterpretationService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=20)),
        id_factory=Ids("second"),
    ).produce_packet_run(PACKET_RUN_ID, SupportedInterpreter())

    assert first.run.run_id != second.run.run_id
    assert first.interpretations[0].change_interpretation_id != second.interpretations[0].change_interpretation_id
    assert first.run.outputs_hash == second.run.outputs_hash
