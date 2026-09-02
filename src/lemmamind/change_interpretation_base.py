"""Constrained producer for provenance-bound full-M5 ChangeInterpretation.

The producer is deliberately model/provider neutral. An interpreter receives only
a deterministic bounded ``CandidateEvidencePacket`` and may either return one
candidate-level semantic proposal or decline. The service validates every support
reference against the exact packet before persisting inferred output.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from .candidate_evidence_packet_contracts import CandidateEvidencePacket
from .candidate_evidence_packets import CandidateEvidencePacketService
from .candidate_reduction_contracts import CandidateFactualReduction
from .change_interpretation_contracts import (
    ChangeInterpretation,
    ChangeInterpretationSupportRef,
    ChangeInterpretationSupportType,
    ChangeInterpretationType,
    InterpretationSummaryText,
    MechanismText,
    UncertaintyText,
)
from .contracts import CONTRACT_SCHEMA_VERSION, PipelineRun, RunType
from .interval_segmentation_contracts import IntervalCandidateSegment


class ChangeInterpretationError(RuntimeError):
    """Interpreter output or packet provenance is invalid."""


class InterpretationProposal(BaseModel):
    """Untrusted semantic proposal returned by an interpreter adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    interpretation_types: tuple[ChangeInterpretationType, ...]
    mechanism: MechanismText
    summary: InterpretationSummaryText
    uncertainty_notes: tuple[UncertaintyText, ...] = ()
    supports: tuple[ChangeInterpretationSupportRef, ...]

    @model_validator(mode="after")
    def validate_proposal(self) -> "InterpretationProposal":
        if not self.interpretation_types:
            raise ValueError("InterpretationProposal requires an interpretation type")
        if self.interpretation_types != tuple(
            sorted(set(self.interpretation_types), key=lambda item: item.value)
        ):
            raise ValueError("interpretation_types must be sorted and unique")
        if (
            ChangeInterpretationType.UNKNOWN in self.interpretation_types
            and len(self.interpretation_types) != 1
        ):
            raise ValueError("unknown cannot be combined with specific interpretation types")
        if not self.supports:
            raise ValueError("InterpretationProposal requires specific evidence support")
        support_keys = tuple(
            (item.support_type.value, item.support_id) for item in self.supports
        )
        if support_keys != tuple(sorted(set(support_keys))):
            raise ValueError("proposal supports must be sorted and unique")
        if any(
            item.support_type
            is ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION
            for item in self.supports
        ):
            raise ValueError(
                "interpreter proposals must not manufacture factual-reduction support edges"
            )
        if self.uncertainty_notes != tuple(sorted(set(self.uncertainty_notes))):
            raise ValueError("uncertainty_notes must be sorted and unique")
        return self


class CandidateChangeInterpreter(Protocol):
    """Provider-neutral semantic adapter over one bounded candidate packet."""

    name: str
    version: str

    def interpret(
        self,
        packet: CandidateEvidencePacket,
    ) -> InterpretationProposal | None: ...


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


@dataclass(frozen=True)
class ChangeInterpretationResult:
    packet_run_id: str
    interpretations: tuple[ChangeInterpretation, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (self.run, *self.interpretations)


class ChangeInterpretationService:
    """Validate candidate-local semantic output against exact packet evidence."""

    PACKET_POLICY_VERSION = "candidate-evidence-packet.v1"

    def __init__(
        self,
        store: ContractStore,
        *,
        policy_version: str = "change-interpretation.candidate.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def produce_packet_run(
        self,
        packet_run_id: str,
        interpreter: CandidateChangeInterpreter,
    ) -> ChangeInterpretationResult:
        interpreter_name = str(getattr(interpreter, "name", "")).strip()
        interpreter_version = str(getattr(interpreter, "version", "")).strip()
        if not interpreter_name or not interpreter_version:
            raise ChangeInterpretationError(
                "interpreter must expose non-empty name and version"
            )

        packet_run, packets = self._authenticated_packet_generation(packet_run_id)
        started_at = self._aware_now()
        interpretation_run_id = f"run:change-interpretation:{self.id_factory()}"

        interpretations: list[ChangeInterpretation] = []
        for packet in packets:
            proposal = interpreter.interpret(packet)
            if proposal is None:
                continue
            if not isinstance(proposal, InterpretationProposal):
                try:
                    proposal = InterpretationProposal.model_validate(proposal)
                except Exception as exc:
                    raise ChangeInterpretationError(
                        "interpreter returned an invalid interpretation proposal"
                    ) from exc
            interpretations.append(
                self._materialize(
                    packet,
                    proposal,
                    interpretation_run_id,
                    interpreter_name,
                    interpreter_version,
                )
            )

        inputs_hash = self._digest_json(
            {
                "packet_run": packet_run.model_dump(mode="json", by_alias=True),
                "packets": [
                    CandidateEvidencePacketService._stable_packet_payload(item)
                    for item in packets
                ],
                "interpreter": {
                    "name": interpreter_name,
                    "version": interpreter_version,
                },
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            [self._stable_interpretation_payload(item) for item in interpretations]
        )
        run = PipelineRun(
            run_id=interpretation_run_id,
            run_type=RunType.REASONING,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = ChangeInterpretationResult(
            packet_run_id=packet_run_id,
            interpretations=tuple(interpretations),
            run=run,
        )
        self.store.put_many(result.records())
        return result

    def _authenticated_packet_generation(
        self,
        packet_run_id: str,
    ) -> tuple[PipelineRun, tuple[CandidateEvidencePacket, ...]]:
        run = self.store.get(PipelineRun, packet_run_id)
        if run is None:
            raise ChangeInterpretationError(
                f"unknown candidate evidence packet PipelineRun: {packet_run_id}"
            )
        if run.run_type is not RunType.OTHER or run.finished_at is None:
            raise ChangeInterpretationError(
                "ChangeInterpretation requires a completed candidate evidence packet run"
            )
        if run.policy_version != self.PACKET_POLICY_VERSION:
            raise ChangeInterpretationError(
                "ChangeInterpretation requires the known candidate evidence packet policy"
            )

        packets = tuple(
            item
            for item in self.store.list(CandidateEvidencePacket)
            if item.packet_run_id == packet_run_id
        )
        if not packets:
            expected = self._digest_json([])
            if run.outputs_hash != expected:
                raise ChangeInterpretationError(
                    "empty packet generation does not authenticate against outputs_hash"
                )
            return run, ()

        reduction_run_ids = {item.reduction_run_id for item in packets}
        if len(reduction_run_ids) != 1:
            raise ChangeInterpretationError(
                "candidate evidence packets span multiple factual-reduction generations"
            )

        packet_by_candidate: dict[str, CandidateEvidencePacket] = {}
        ordered_candidates: list[IntervalCandidateSegment] = []
        for packet in packets:
            if packet.interval_candidate_segment_id in packet_by_candidate:
                raise ChangeInterpretationError(
                    "candidate evidence packet generation contains duplicate candidates"
                )
            packet_by_candidate[packet.interval_candidate_segment_id] = packet
            candidate = self.store.get(
                IntervalCandidateSegment,
                packet.interval_candidate_segment_id,
            )
            reduction = self.store.get(
                CandidateFactualReduction,
                packet.candidate_factual_reduction_id,
            )
            if candidate is None or reduction is None:
                raise ChangeInterpretationError(
                    "candidate evidence packet references missing candidate/reduction"
                )
            expected = (
                candidate.interval_candidate_segment_id,
                candidate.source_id,
                candidate.previous_source_revision_id,
                candidate.current_source_revision_id,
                candidate.paths,
                reduction.candidate_factual_reduction_id,
                reduction.reduction_run_id,
            )
            observed = (
                packet.interval_candidate_segment_id,
                packet.source_id,
                packet.previous_source_revision_id,
                packet.current_source_revision_id,
                packet.paths,
                packet.candidate_factual_reduction_id,
                packet.reduction_run_id,
            )
            if observed != expected:
                raise ChangeInterpretationError(
                    "candidate evidence packet lineage disagrees with candidate/reduction"
                )
            if (
                reduction.interval_candidate_segment_id
                != candidate.interval_candidate_segment_id
                or reduction.paths != candidate.paths
                or reduction.source_id != candidate.source_id
                or reduction.previous_source_revision_id
                != candidate.previous_source_revision_id
                or reduction.current_source_revision_id
                != candidate.current_source_revision_id
            ):
                raise ChangeInterpretationError(
                    "factual reduction lineage disagrees with candidate evidence packet"
                )
            ordered_candidates.append(candidate)

        ordered_candidates.sort(
            key=lambda item: (
                item.commit_ordinal,
                item.path_group,
                item.chunk_ordinal,
                item.interval_candidate_segment_id,
            )
        )
        ordered_packets = tuple(
            packet_by_candidate[item.interval_candidate_segment_id]
            for item in ordered_candidates
        )
        expected_outputs_hash = self._digest_json(
            [
                CandidateEvidencePacketService._stable_packet_payload(item)
                for item in ordered_packets
            ]
        )
        if run.outputs_hash != expected_outputs_hash:
            raise ChangeInterpretationError(
                "candidate evidence packet output envelope does not authenticate"
            )
        return run, ordered_packets

    def _materialize(
        self,
        packet: CandidateEvidencePacket,
        proposal: InterpretationProposal,
        interpretation_run_id: str,
        interpreter_name: str,
        interpreter_version: str,
    ) -> ChangeInterpretation:
        allowed: dict[ChangeInterpretationSupportType, set[str]] = {
            ChangeInterpretationSupportType.ARTIFACT_DELTA: set(
                packet.artifact_delta_ids
            ),
            ChangeInterpretationSupportType.STRUCTURAL_DELTA: {
                item.structural_delta_id
                for item in packet.structural_delta_previews
            },
            ChangeInterpretationSupportType.SOURCE_ASSERTION: {
                item.assertion_id for item in packet.assertion_previews
            },
            ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL: set(
                packet.extraction_gap_signal_ids
            ),
        }

        for support in proposal.supports:
            support_ids = allowed.get(support.support_type)
            if support_ids is None or support.support_id not in support_ids:
                raise ChangeInterpretationError(
                    "interpretation support is outside the exact bounded evidence packet: "
                    f"{support.support_type.value}:{support.support_id}"
                )

        semantic_support = any(
            support.support_type
            in {
                ChangeInterpretationSupportType.STRUCTURAL_DELTA,
                ChangeInterpretationSupportType.SOURCE_ASSERTION,
            }
            for support in proposal.supports
        )
        if not semantic_support:
            raise ChangeInterpretationError(
                "mechanism-level interpretation requires structural or authored-assertion support"
            )

        required_gap_ids = set(packet.extraction_gap_signal_ids)
        supplied_gap_ids = {
            support.support_id
            for support in proposal.supports
            if support.support_type
            is ChangeInterpretationSupportType.CANDIDATE_EXTRACTION_GAP_SIGNAL
        }
        if required_gap_ids:
            if supplied_gap_ids != required_gap_ids:
                raise ChangeInterpretationError(
                    "interpretations of gap-bearing packets must expose every packet extraction-gap signal"
                )
            if not proposal.uncertainty_notes:
                raise ChangeInterpretationError(
                    "interpretations of gap-bearing packets require explicit uncertainty"
                )
        elif supplied_gap_ids:
            raise ChangeInterpretationError(
                "interpretation references extraction-gap support absent from the packet"
            )

        supports = tuple(
            sorted(
                (
                    ChangeInterpretationSupportRef(
                        support_type=ChangeInterpretationSupportType.CANDIDATE_FACTUAL_REDUCTION,
                        support_id=packet.candidate_factual_reduction_id,
                    ),
                    *proposal.supports,
                ),
                key=lambda item: (item.support_type.value, item.support_id),
            )
        )
        return ChangeInterpretation(
            change_interpretation_id=self._interpretation_id(
                interpretation_run_id,
                packet.interval_candidate_segment_id,
            ),
            source_id=packet.source_id,
            previous_source_revision_id=packet.previous_source_revision_id,
            current_source_revision_id=packet.current_source_revision_id,
            interval_candidate_segment_ids=(
                packet.interval_candidate_segment_id,
            ),
            candidate_factual_reduction_ids=(
                packet.candidate_factual_reduction_id,
            ),
            candidate_evidence_packet_ids=(
                packet.candidate_evidence_packet_id,
            ),
            interpretation_types=proposal.interpretation_types,
            mechanism=proposal.mechanism,
            summary=proposal.summary,
            uncertainty_notes=proposal.uncertainty_notes,
            supports=supports,
            interpreter_name=interpreter_name,
            interpreter_version=interpreter_version,
            interpretation_run_id=interpretation_run_id,
        )

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ChangeInterpretationError(
                "change-interpretation clock must return timezone-aware datetimes"
            )
        return value

    @staticmethod
    def _interpretation_id(run_id: str, candidate_id: str) -> str:
        material = f"change-interpretation\0{run_id}\0{candidate_id}".encode(
            "utf-8"
        )
        return f"change-interpretation:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _stable_interpretation_payload(item: ChangeInterpretation) -> dict:
        payload = item.model_dump(mode="json", by_alias=True)
        payload.pop("change_interpretation_id", None)
        payload.pop("interpretation_run_id", None)
        return payload

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
