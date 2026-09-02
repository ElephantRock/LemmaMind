"""Deterministic exact-mechanism collapse for the M5 human review surface."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .candidate_evidence_packet_contracts import CandidateEvidencePacket
from .candidate_evidence_packets import CandidateEvidencePacketService
from .candidate_reduction_contracts import CandidateFactualReduction
from .change_interpretation import ChangeInterpretationService
from .change_interpretation_contracts import (
    ChangeInterpretation,
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
)
from .contracts import CONTRACT_SCHEMA_VERSION, PipelineRun, RunType
from .interval_segmentation_contracts import IntervalCandidateSegment
from .mechanism_review_contracts import MechanismReviewItem


class MechanismReviewGroupingError(RuntimeError):
    """Interpretation generation cannot be projected safely into review items."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class MechanismReviewGroupingResult:
    interpretation_run_id: str
    items: tuple[MechanismReviewItem, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (*self.items, self.run)


class MechanismReviewGroupingService:
    """Collapse only canonically identical mechanism labels within one generation."""

    INTERPRETATION_POLICY = "change-interpretation.candidate.v1"
    PACKET_POLICY = "candidate-evidence-packet.v1"

    def __init__(
        self,
        store: ContractStore,
        *,
        policy_version: str = "mechanism-review-grouping.exact.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def group_interpretation_run(
        self, interpretation_run_id: str
    ) -> MechanismReviewGroupingResult:
        started_at = self._aware_now()
        interpretation_run, interpretations = self._authenticated_interpretations(
            interpretation_run_id
        )
        grouping_run_id = f"run:mechanism-review-grouping:{self.id_factory()}"

        grouped: dict[tuple, list[ChangeInterpretation]] = {}
        for item in interpretations:
            key = (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                tuple(kind.value for kind in item.interpretation_types),
                self._canonical_mechanism(item.mechanism),
            )
            grouped.setdefault(key, []).append(item)

        review_items = tuple(
            self._materialize_group(key, tuple(members), grouping_run_id)
            for key, members in sorted(grouped.items(), key=lambda pair: pair[0])
        )
        inputs_hash = self._digest_json(
            {
                "interpretation_run": interpretation_run.model_dump(
                    mode="json", by_alias=True
                ),
                "interpretations": [
                    ChangeInterpretationService._stable_interpretation_payload(item)
                    for item in interpretations
                ],
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            [self._stable_item_payload(item) for item in review_items]
        )
        run = PipelineRun(
            run_id=grouping_run_id,
            run_type=RunType.OTHER,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = MechanismReviewGroupingResult(
            interpretation_run_id=interpretation_run_id,
            items=review_items,
            run=run,
        )
        self.store.put_many(result.records())
        return result

    def _authenticated_interpretations(
        self, interpretation_run_id: str
    ) -> tuple[PipelineRun, tuple[ChangeInterpretation, ...]]:
        run = self._completed_run(
            interpretation_run_id, RunType.REASONING, "ChangeInterpretation"
        )
        if run.policy_version != self.INTERPRETATION_POLICY:
            raise MechanismReviewGroupingError(
                "mechanism grouping requires the known ChangeInterpretation policy"
            )
        interpretations = tuple(
            item
            for item in self.store.list(ChangeInterpretation)
            if item.interpretation_run_id == interpretation_run_id
        )
        if not interpretations:
            if run.outputs_hash != self._digest_json([]):
                raise MechanismReviewGroupingError(
                    "empty ChangeInterpretation generation does not authenticate"
                )
            return run, ()

        interpreter_generations = {
            (item.interpreter_name, item.interpreter_version) for item in interpretations
        }
        if len(interpreter_generations) != 1:
            raise MechanismReviewGroupingError(
                "one ChangeInterpretation run must use one interpreter generation"
            )
        interpreter_name, interpreter_version = next(iter(interpreter_generations))

        packet_run_ids: set[str] = set()
        interpretation_by_packet: dict[str, ChangeInterpretation] = {}
        for item in interpretations:
            if (
                len(item.interval_candidate_segment_ids) != 1
                or len(item.candidate_factual_reduction_ids) != 1
                or len(item.candidate_evidence_packet_ids) != 1
            ):
                raise MechanismReviewGroupingError(
                    "exact grouping v1 requires candidate-local interpretations"
                )
            packet_id = item.candidate_evidence_packet_ids[0]
            if packet_id in interpretation_by_packet:
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation run contains duplicate packet interpretations"
                )
            packet = self.store.get(CandidateEvidencePacket, packet_id)
            reduction = self.store.get(
                CandidateFactualReduction, item.candidate_factual_reduction_ids[0]
            )
            candidate = self.store.get(
                IntervalCandidateSegment, item.interval_candidate_segment_ids[0]
            )
            if packet is None or reduction is None or candidate is None:
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation references missing packet/reduction/candidate"
                )
            expected = (
                item.source_id,
                item.previous_source_revision_id,
                item.current_source_revision_id,
                item.interval_candidate_segment_ids[0],
                item.candidate_factual_reduction_ids[0],
            )
            packet_observed = (
                packet.source_id,
                packet.previous_source_revision_id,
                packet.current_source_revision_id,
                packet.interval_candidate_segment_id,
                packet.candidate_factual_reduction_id,
            )
            reduction_observed = (
                reduction.source_id,
                reduction.previous_source_revision_id,
                reduction.current_source_revision_id,
                reduction.interval_candidate_segment_id,
                reduction.candidate_factual_reduction_id,
            )
            candidate_observed = (
                candidate.source_id,
                candidate.previous_source_revision_id,
                candidate.current_source_revision_id,
                candidate.interval_candidate_segment_id,
                reduction.candidate_factual_reduction_id,
            )
            if packet_observed != expected or reduction_observed != expected or candidate_observed != expected:
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation lineage disagrees with packet/reduction/candidate"
                )
            self._validate_supports(item, packet)
            packet_run_ids.add(packet.packet_run_id)
            interpretation_by_packet[packet_id] = item

        if len(packet_run_ids) != 1:
            raise MechanismReviewGroupingError(
                "one ChangeInterpretation run must consume one packet generation"
            )
        packet_run_id = next(iter(packet_run_ids))
        packet_run = self._completed_run(packet_run_id, RunType.OTHER, "evidence packet")
        if packet_run.policy_version != self.PACKET_POLICY:
            raise MechanismReviewGroupingError(
                "mechanism grouping requires the known evidence-packet policy"
            )
        packets = tuple(
            item
            for item in self.store.list(CandidateEvidencePacket)
            if item.packet_run_id == packet_run_id
        )
        ordered_packets = tuple(sorted(packets, key=self._packet_order_key))
        expected_packet_outputs = self._digest_json(
            [
                CandidateEvidencePacketService._stable_packet_payload(item)
                for item in ordered_packets
            ]
        )
        if packet_run.outputs_hash != expected_packet_outputs:
            raise MechanismReviewGroupingError(
                "candidate evidence packet output envelope does not authenticate"
            )

        expected_inputs = self._digest_json(
            {
                "packet_run": packet_run.model_dump(mode="json", by_alias=True),
                "packets": [
                    CandidateEvidencePacketService._stable_packet_payload(item)
                    for item in ordered_packets
                ],
                "interpreter": {
                    "name": interpreter_name,
                    "version": interpreter_version,
                },
                "policy_version": run.policy_version,
            }
        )
        if run.inputs_hash != expected_inputs:
            raise MechanismReviewGroupingError(
                "ChangeInterpretation input envelope does not authenticate"
            )
        ordered_interpretations = tuple(
            interpretation_by_packet[item.candidate_evidence_packet_id]
            for item in ordered_packets
            if item.candidate_evidence_packet_id in interpretation_by_packet
        )
        expected_outputs = self._digest_json(
            [
                ChangeInterpretationService._stable_interpretation_payload(item)
                for item in ordered_interpretations
            ]
        )
        if run.outputs_hash != expected_outputs:
            raise MechanismReviewGroupingError(
                "ChangeInterpretation output envelope does not authenticate"
            )
        return run, ordered_interpretations

    def _packet_order_key(self, packet: CandidateEvidencePacket) -> tuple:
        candidate = self.store.get(
            IntervalCandidateSegment, packet.interval_candidate_segment_id
        )
        if candidate is None:
            raise MechanismReviewGroupingError(
                "candidate evidence packet references missing interval candidate"
            )
        return (
            candidate.commit_ordinal,
            candidate.path_group,
            candidate.chunk_ordinal,
            candidate.interval_candidate_segment_id,
        )

    @staticmethod
    def _validate_supports(
        interpretation: ChangeInterpretation, packet: CandidateEvidencePacket
    ) -> None:
        allowed = {
            ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION: {
                packet.candidate_factual_reduction_id
            },
            ChangeInterpretationSupportType.ARTIFACT_DELTA: set(packet.artifact_delta_ids),
            ChangeInterpretationSupportType.STRUCTURAL_DELTA: {
                item.structural_delta_id for item in packet.structural_delta_previews
            },
            ChangeInterpretationSupportType.SOURCE_ASSERTION: {
                item.assertion_id for item in packet.assertion_previews
            },
            ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL: set(
                packet.extraction_gap_signal_ids
            ),
        }
        for support in interpretation.supports:
            if support.support_id not in allowed[support.support_type]:
                raise MechanismReviewGroupingError(
                    "ChangeInterpretation support falls outside its exact evidence packet"
                )
        supplied_gap_ids = {
            item.support_id
            for item in interpretation.supports
            if item.support_type
            is ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL
        }
        if supplied_gap_ids != set(packet.extraction_gap_signal_ids):
            raise MechanismReviewGroupingError(
                "ChangeInterpretation does not expose exact packet extraction-gap support"
            )
        if supplied_gap_ids and not interpretation.uncertainty_notes:
            raise MechanismReviewGroupingError(
                "gap-bearing ChangeInterpretation requires explicit uncertainty"
            )

    def _materialize_group(
        self,
        key: tuple,
        members: tuple[ChangeInterpretation, ...],
        grouping_run_id: str,
    ) -> MechanismReviewItem:
        members = tuple(sorted(members, key=lambda item: item.change_interpretation_id))
        representative = min(
            members,
            key=lambda item: (
                item.mechanism.casefold(),
                item.mechanism,
                item.change_interpretation_id,
            ),
        )
        support_by_key: dict[tuple[str, str], ChangeInterpretationSupportRef] = {}
        for member in members:
            for support in member.supports:
                support_by_key[(support.support_type.value, support.support_id)] = support
        supports = tuple(support_by_key[key] for key in sorted(support_by_key))
        gap_ids = tuple(
            sorted(
                support.support_id
                for support in supports
                if support.support_type
                is ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL
            )
        )
        return MechanismReviewItem(
            mechanism_review_item_id=self._item_id(grouping_run_id, key),
            source_id=representative.source_id,
            previous_source_revision_id=representative.previous_source_revision_id,
            current_source_revision_id=representative.current_source_revision_id,
            canonical_mechanism_key=key[-1],
            interpretation_types=representative.interpretation_types,
            mechanism=representative.mechanism,
            representative_summary=representative.summary,
            representative_change_interpretation_id=(
                representative.change_interpretation_id
            ),
            change_interpretation_ids=tuple(
                sorted(item.change_interpretation_id for item in members)
            ),
            interval_candidate_segment_ids=tuple(
                sorted(
                    {
                        value
                        for item in members
                        for value in item.interval_candidate_segment_ids
                    }
                )
            ),
            candidate_factual_reduction_ids=tuple(
                sorted(
                    {
                        value
                        for item in members
                        for value in item.candidate_factual_reduction_ids
                    }
                )
            ),
            candidate_evidence_packet_ids=tuple(
                sorted(
                    {
                        value
                        for item in members
                        for value in item.candidate_evidence_packet_ids
                    }
                )
            ),
            supports=supports,
            extraction_gap_signal_ids=gap_ids,
            uncertainty_notes=tuple(
                sorted(
                    {
                        note
                        for item in members
                        for note in item.uncertainty_notes
                    }
                )
            ),
            interpretation_run_id=representative.interpretation_run_id,
            grouping_run_id=grouping_run_id,
        )

    def _completed_run(self, run_id: str, run_type: RunType, label: str) -> PipelineRun:
        run = self.store.get(PipelineRun, run_id)
        if run is None:
            raise MechanismReviewGroupingError(f"unknown {label} PipelineRun: {run_id}")
        if run.run_type is not run_type or run.finished_at is None:
            raise MechanismReviewGroupingError(
                f"{label} requires one completed {run_type.value} PipelineRun"
            )
        return run

    @staticmethod
    def _canonical_mechanism(value: str) -> str:
        return " ".join(value.split()).casefold()

    @staticmethod
    def _item_id(grouping_run_id: str, key: tuple) -> str:
        material = json.dumps(key, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        return (
            "mechanism-review-item:"
            + hashlib.sha256(grouping_run_id.encode("utf-8") + b"\0" + material).hexdigest()
        )

    @staticmethod
    def _stable_item_payload(item: MechanismReviewItem) -> dict:
        payload = item.model_dump(mode="json", by_alias=True)
        payload.pop("mechanism_review_item_id", None)
        payload.pop("grouping_run_id", None)
        return payload

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise MechanismReviewGroupingError(
                "mechanism grouping clock must return timezone-aware datetimes"
            )
        return value

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
