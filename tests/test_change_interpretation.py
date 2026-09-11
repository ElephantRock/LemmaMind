from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.candidate_evidence_packets import CandidateEvidencePacketService
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
from tests.test_candidate_evidence_packets import (
    REDUCTION_RUN_ID,
    EXTRACTOR_PROFILE,
    STRUCTURAL_DELTA_ID,
    prepare as prepare_packet_store,
)


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)


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
                    support_id=STRUCTURAL_DELTA_ID,
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


def prepare_packet_run(tmp_path):
    store = prepare_packet_store(tmp_path)
    result = CandidateEvidencePacketService(
        store,
        artifact_extractors=EXTRACTOR_PROFILE,
        clock=FixedClock(NOW + timedelta(seconds=20)),
        id_factory=Ids("packet"),
    ).build_reduction(REDUCTION_RUN_ID)
    assert len(result.packets) == 1
    return store, result


def test_interpretation_service_persists_only_packet_supported_candidate_output(tmp_path) -> None:
    store, packets = prepare_packet_run(tmp_path)
    packet = packets.packets[0]
    result = ChangeInterpretationService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=30)),
        id_factory=Ids("interpretation"),
    ).produce_packet_run(packets.run.run_id, SupportedInterpreter())

    assert result.run.run_type is RunType.REASONING
    assert len(result.interpretations) == 1
    item = result.interpretations[0]
    assert item.validation_state is ValidationState.CANDIDATE
    assert item.interpreter_name == "fixture-interpreter"
    assert item.interpreter_version == "1"
    assert item.candidate_evidence_packet_ids == (
        packet.candidate_evidence_packet_id,
    )
    assert item.candidate_factual_reduction_ids == (
        packet.candidate_factual_reduction_id,
    )
    assert {
        (support.support_type, support.support_id) for support in item.supports
    } == {
        (
            ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION,
            packet.candidate_factual_reduction_id,
        ),
        (ChangeInterpretationSupportType.STRUCTURAL_DELTA, STRUCTURAL_DELTA_ID),
    }


def test_interpreter_may_decline_low_signal_candidate(tmp_path) -> None:
    store, packets = prepare_packet_run(tmp_path)
    result = ChangeInterpretationService(store).produce_packet_run(
        packets.run.run_id,
        DecliningInterpreter(),
    )

    assert result.interpretations == ()


def test_interpretation_service_rejects_support_outside_packet(tmp_path) -> None:
    store, packets = prepare_packet_run(tmp_path)

    with pytest.raises(
        ChangeInterpretationError,
        match="outside the exact bounded evidence packet",
    ):
        ChangeInterpretationService(store).produce_packet_run(
            packets.run.run_id,
            ForeignSupportInterpreter(),
        )


def test_gap_bearing_packet_requires_explicit_gap_support_and_uncertainty(tmp_path) -> None:
    store, packets = prepare_packet_run(tmp_path)
    packet = packets.packets[0]
    gap_packet = packet.model_copy(
        update={
            "extraction_gap_signal_ids": ("gap:interpretation",),
            "extraction_gap_paths": packet.paths,
        }
    )
    service = ChangeInterpretationService(store)
    unsupported = SupportedInterpreter().interpret(gap_packet)
    assert unsupported is not None

    with pytest.raises(
        ChangeInterpretationError,
        match="must expose every packet extraction-gap signal",
    ):
        service._materialize(
            gap_packet,
            unsupported,
            "run:change-interpretation:gap-test",
            "fixture-interpreter",
            "1",
        )

    supported = InterpretationProposal(
        interpretation_types=(ChangeInterpretationType.TEMPORAL_CORRECTNESS,),
        mechanism="Preserve timeout deadlines across wall-clock changes",
        summary=(
            "The supported path changes timeout accounting, with incomplete nearby "
            "extraction coverage."
        ),
        uncertainty_notes=(
            "One candidate path has incomplete deterministic extraction coverage.",
        ),
        supports=tuple(
            sorted(
                (
                    ChangeInterpretationSupportRef(
                        support_type=(
                            ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL
                        ),
                        support_id="gap:interpretation",
                    ),
                    ChangeInterpretationSupportRef(
                        support_type=ChangeInterpretationSupportType.STRUCTURAL_DELTA,
                        support_id=STRUCTURAL_DELTA_ID,
                    ),
                ),
                key=lambda item: (item.support_type.value, item.support_id),
            )
        ),
    )
    item = service._materialize(
        gap_packet,
        supported,
        "run:change-interpretation:gap-test-supported",
        "fixture-interpreter",
        "1",
    )
    assert item.uncertainty_notes


def test_interpretation_outputs_hash_is_stable_across_reasoning_run_ids(tmp_path) -> None:
    store, packets = prepare_packet_run(tmp_path)
    first = ChangeInterpretationService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=30)),
        id_factory=Ids("first"),
    ).produce_packet_run(packets.run.run_id, SupportedInterpreter())
    second = ChangeInterpretationService(
        store,
        clock=FixedClock(NOW + timedelta(seconds=40)),
        id_factory=Ids("second"),
    ).produce_packet_run(packets.run.run_id, SupportedInterpreter())

    assert first.run.run_id != second.run.run_id
    assert (
        first.interpretations[0].change_interpretation_id
        != second.interpretations[0].change_interpretation_id
    )
    assert first.run.outputs_hash == second.run.outputs_hash


def test_semantic_boundary_rejects_self_consistent_forged_packet(tmp_path) -> None:
    store, packets = prepare_packet_run(tmp_path)
    real_packet = packets.packets[0]
    forged_run_id = "run:packet:forged"
    forged_preview = real_packet.structural_delta_previews[0].model_copy(
        update={"structural_delta_id": "structural:foreign"}
    )
    forged_packet = real_packet.model_copy(
        update={
            "candidate_evidence_packet_id": CandidateEvidencePacketService._packet_id(
                forged_run_id,
                real_packet.interval_candidate_segment_id,
            ),
            "structural_delta_previews": (forged_preview,),
            "packet_run_id": forged_run_id,
        }
    )
    forged_run = PipelineRun(
        run_id=forged_run_id,
        run_type=RunType.OTHER,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="candidate-evidence-packet.v1",
        started_at=NOW + timedelta(seconds=50),
        finished_at=NOW + timedelta(seconds=51),
        inputs_hash=packets.run.inputs_hash,
        outputs_hash=CandidateEvidencePacketService._digest_json(
            [CandidateEvidencePacketService._stable_packet_payload(forged_packet)]
        ),
    )
    store.put_many((forged_packet, forged_run))

    with pytest.raises(
        ChangeInterpretationError,
        match="failed upstream reconstruction",
    ):
        ChangeInterpretationService(store).produce_packet_run(
            forged_run_id,
            SupportedInterpreter(),
        )
