from datetime import datetime, timezone

import pytest

from lemmamind.candidate_evidence_packet_contracts import AssertionSnapshotSide
from lemmamind.candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
)
from lemmamind.candidate_extraction_gap_contracts import CandidateExtractionGapSignal
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    PipelineRun,
    RunType,
    SourceAssertion,
)
from lemmamind.extraction_diagnostic_contracts import ExtractionDiagnostic
from lemmamind.storage import SQLiteContractStore


NOW = datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)
PATH = "src/core.py"
SOURCE_ID = "github:packet-hardening"
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{'a' * 40}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{'b' * 40}"
PREVIOUS_CAPTURE_ID = "capture:hardening:previous"
CURRENT_CAPTURE_ID = "capture:hardening:current"
PREVIOUS_EXTRACTION_RUN_ID = "run:hardening:extract:previous"
CURRENT_EXTRACTION_RUN_ID = "run:hardening:extract:current"
REDUCTION_RUN_ID = "run:hardening:reduction"
SEGMENTATION_RUN_ID = "run:hardening:segmentation"
CANDIDATE_ID = "candidate:hardening"


def reduction() -> CandidateFactualReduction:
    return CandidateFactualReduction(
        candidate_factual_reduction_id="reduction:hardening",
        interval_candidate_segment_id=CANDIDATE_ID,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(PATH,),
        affected_file_plan_ids=("plan:hardening",),
        capture_scoped_paths=(PATH,),
        signal_kinds=(CandidateSignalKind.GIT_ONLY_CHANGE,),
        disposition=CandidateReductionDisposition.RETAIN,
        diff_run_id="run:hardening:diff",
        segmentation_run_id=SEGMENTATION_RUN_ID,
        planner_run_id="run:hardening:planner",
        previous_capture_id=PREVIOUS_CAPTURE_ID,
        current_capture_id=CURRENT_CAPTURE_ID,
        previous_extraction_run_id=PREVIOUS_EXTRACTION_RUN_ID,
        current_extraction_run_id=CURRENT_EXTRACTION_RUN_ID,
        change_run_id="run:hardening:change",
        reduction_run_id=REDUCTION_RUN_ID,
    )


def diagnostic(diagnostic_id: str, extractor: str) -> ExtractionDiagnostic:
    return ExtractionDiagnostic(
        extraction_diagnostic_id=diagnostic_id,
        capture_id=PREVIOUS_CAPTURE_ID,
        source_revision_id=PREVIOUS_REVISION_ID,
        artifact_id="artifact:hardening:previous",
        source_locator=PATH,
        extractor_name=extractor,
        extractor_version="1",
        error_type="ParseError",
        error_message=f"{extractor} failed",
        run_id=PREVIOUS_EXTRACTION_RUN_ID,
    )


def test_gap_signals_must_exactly_cover_authenticated_candidate_diagnostics(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    first = diagnostic("diagnostic:first", "typescript-ast")
    second = diagnostic("diagnostic:second", "markdown")
    signal = CandidateExtractionGapSignal(
        candidate_extraction_gap_signal_id="gap:partial",
        interval_candidate_segment_id=CANDIDATE_ID,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        previous_capture_id=PREVIOUS_CAPTURE_ID,
        current_capture_id=CURRENT_CAPTURE_ID,
        paths=(PATH,),
        previous_diagnostic_ids=(first.extraction_diagnostic_id,),
        segmentation_run_id=SEGMENTATION_RUN_ID,
        previous_extraction_run_id=PREVIOUS_EXTRACTION_RUN_ID,
        current_extraction_run_id=CURRENT_EXTRACTION_RUN_ID,
        reduction_run_id=REDUCTION_RUN_ID,
    )
    store.put_many((first, second, signal))

    with pytest.raises(
        CandidateEvidencePacketError,
        match="do not exactly cover authenticated diagnostics",
    ):
        CandidateEvidencePacketService(store)._gap_signals(reduction())


def test_gap_signals_cannot_be_omitted_when_candidate_has_diagnostic(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    store.put(diagnostic("diagnostic:only", "typescript-ast"))

    with pytest.raises(
        CandidateEvidencePacketError,
        match="do not exactly cover authenticated diagnostics",
    ):
        CandidateEvidencePacketService(store)._gap_signals(reduction())


def test_packet_builder_rejects_unrecognized_extraction_policy(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    run = PipelineRun(
        run_id="run:hardening:unknown-policy",
        run_type=RunType.EXTRACTION,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="deterministic-evidence.gap-tolerant.v2-typo",
        started_at=NOW,
        finished_at=NOW,
        inputs_hash="sha256:" + "0" * 64,
        outputs_hash="sha256:" + "1" * 64,
    )
    store.put(run)

    with pytest.raises(
        CandidateEvidencePacketError,
        match="reject unrecognized extraction policies",
    ):
        CandidateEvidencePacketService(store)._authenticate_extraction_run(run.run_id)


def test_assertion_preview_round_robin_reserves_capacity_for_both_sides() -> None:
    items = tuple(
        (
            side,
            PATH,
            SourceAssertion(
                assertion_id=f"assertion:{side.value}:{index}",
                artifact_id=f"artifact:{side.value}",
                locator=f"{PATH}:L{index}-L{index}",
                statement=f"{side.value} assertion {index}",
                extractor_name="markdown-prose",
                extractor_version="1",
                run_id=f"run:{side.value}",
            ),
        )
        for side in (AssertionSnapshotSide.CURRENT, AssertionSnapshotSide.PREVIOUS)
        for index in range(1, 5)
    )

    selected = CandidateEvidencePacketService._round_robin_by_path(
        items,
        2,
        path_of=lambda item: item[1],
        item_key=lambda item: (
            item[0].value,
            item[2].locator,
            item[2].assertion_id,
        ),
    )

    assert {item[0] for item in selected} == {
        AssertionSnapshotSide.CURRENT,
        AssertionSnapshotSide.PREVIOUS,
    }


def test_assertion_preview_budget_cannot_disable_two_sided_comparison(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    with pytest.raises(ValueError, match="at least 2"):
        CandidateEvidencePacketService(store, max_assertion_previews=1)
