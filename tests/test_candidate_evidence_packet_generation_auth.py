from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from lemmamind.candidate_evidence_packet_auth import (
    CandidateEvidencePacketGenerationAuthenticator,
)
from lemmamind.candidate_evidence_packet_contracts import StructuralDeltaPreview
from lemmamind.candidate_evidence_packet_generation_contracts import (
    CandidateEvidencePacketGeneration,
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
from lemmamind.change_contracts import StructuralDeltaType
from lemmamind.change_intelligence import DeterministicChangeService
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureManifest,
    PipelineRun,
    RunType,
)
from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
from lemmamind.path_change_contracts import ChangeSurface
from lemmamind.storage import SQLiteContractStore


NOW = datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)
SOURCE_ID = "github:packet-profile"
PREVIOUS_REVISION_ID = SOURCE_ID + "@" + "a" * 40
CURRENT_REVISION_ID = SOURCE_ID + "@" + "b" * 40
PATH = "src/profile.py"
DIFF_RUN_ID = "run:packet-profile:diff"
SEGMENTATION_RUN_ID = "run:packet-profile:segmentation"
PLANNER_RUN_ID = "run:packet-profile:planner"
CHANGE_RUN_ID = "run:packet-profile:change"
REDUCTION_RUN_ID = "run:packet-profile:reduction"
PREVIOUS_EXTRACTION_RUN_ID = "run:packet-profile:extract:previous"
CURRENT_EXTRACTION_RUN_ID = "run:packet-profile:extract:current"
PREVIOUS_CAPTURE_ID = "capture:packet-profile:previous"
CURRENT_CAPTURE_ID = "capture:packet-profile:current"
EXTRACTOR_PROFILE = (
    {"name": "artifact-path", "version": "1"},
    {"name": "pyproject", "version": "1"},
    {"name": "package-json", "version": "1"},
    {"name": "markdown-prose", "version": "1"},
    {"name": "markdown-list", "version": "1"},
)


def _digest(value):
    return CandidateEvidencePacketService._digest_json(value)


def _run(run_id, run_type, policy, inputs_hash, outputs_hash) -> PipelineRun:
    return PipelineRun(
        run_id=run_id,
        run_type=run_type,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version=policy,
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=inputs_hash,
        outputs_hash=outputs_hash,
    )


def _seed_retained_git_only_generation(store: SQLiteContractStore) -> None:
    candidate = IntervalCandidateSegment(
        interval_candidate_segment_id="candidate:packet-profile",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        commit_path_snapshot_id="snapshot:packet-profile",
        commit_sha="b" * 40,
        commit_ordinal=1,
        path_group="src",
        chunk_ordinal=1,
        git_path_delta_ids=("git-delta:packet-profile",),
        paths=(PATH,),
        segmentation_run_id=SEGMENTATION_RUN_ID,
    )
    plan = AffectedFileCapturePlan(
        affected_file_plan_id="plan:packet-profile",
        git_path_delta_id="git-delta:packet-profile",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        path=PATH,
        surface=ChangeSurface.SOURCE,
        previous=CapturePlanSide(
            source_revision_id=PREVIOUS_REVISION_ID,
            disposition=CapturePlanDisposition.NON_FILE,
            reason=CapturePlanReason.DIRECTORY_ENTRY,
            entry_type="tree",
            object_sha="1" * 40,
        ),
        current=CapturePlanSide(
            source_revision_id=CURRENT_REVISION_ID,
            disposition=CapturePlanDisposition.NON_FILE,
            reason=CapturePlanReason.DIRECTORY_ENTRY,
            entry_type="tree",
            object_sha="2" * 40,
        ),
        tracking_assignment_id="tracking:packet-profile",
        tracking_level="3",
        diff_run_id=DIFF_RUN_ID,
        planner_run_id=PLANNER_RUN_ID,
    )
    reduction = CandidateFactualReduction(
        candidate_factual_reduction_id="reduction:packet-profile",
        interval_candidate_segment_id=candidate.interval_candidate_segment_id,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(PATH,),
        affected_file_plan_ids=(plan.affected_file_plan_id,),
        git_only_paths=(PATH,),
        signal_kinds=(CandidateSignalKind.GIT_ONLY_CHANGE,),
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
    previous_manifest = CaptureManifest(
        capture_id=PREVIOUS_CAPTURE_ID,
        source_revision_id=PREVIOUS_REVISION_ID,
        capture_policy_version="packet-profile.v1",
        captured_at=NOW,
        artifacts=(),
    )
    current_manifest = CaptureManifest(
        capture_id=CURRENT_CAPTURE_ID,
        source_revision_id=CURRENT_REVISION_ID,
        capture_policy_version="packet-profile.v1",
        captured_at=NOW,
        artifacts=(),
    )
    extraction_outputs = DeterministicChangeService._extraction_output_payload((), ())
    previous_extraction_run = _run(
        PREVIOUS_EXTRACTION_RUN_ID,
        RunType.EXTRACTION,
        "deterministic-evidence.v1",
        _digest(
            {
                "capture_manifest": previous_manifest.model_dump(
                    mode="json", by_alias=True
                ),
                "artifact_extractors": list(EXTRACTOR_PROFILE),
                "policy_version": "deterministic-evidence.v1",
            }
        ),
        _digest(extraction_outputs),
    )
    current_extraction_run = _run(
        CURRENT_EXTRACTION_RUN_ID,
        RunType.EXTRACTION,
        "deterministic-evidence.v1",
        _digest(
            {
                "capture_manifest": current_manifest.model_dump(
                    mode="json", by_alias=True
                ),
                "artifact_extractors": list(EXTRACTOR_PROFILE),
                "policy_version": "deterministic-evidence.v1",
            }
        ),
        _digest(extraction_outputs),
    )
    segmentation_run = _run(
        SEGMENTATION_RUN_ID,
        RunType.DIFF,
        "interval-candidate-segmentation.v1",
        _digest({"fixture": "segmentation"}),
        _digest({"fixture": "segmentation"}),
    )
    planner_run = _run(
        PLANNER_RUN_ID,
        RunType.OTHER,
        "affected-file-plan.v1",
        _digest({"fixture": "planner"}),
        _digest([plan.model_dump(mode="json", by_alias=True)]),
    )
    change_run = _run(
        CHANGE_RUN_ID,
        RunType.DIFF,
        "candidate-factual-change.v1",
        _digest(
            {
                "previous_capture_id": PREVIOUS_CAPTURE_ID,
                "current_capture_id": CURRENT_CAPTURE_ID,
                "previous_source_revision_id": PREVIOUS_REVISION_ID,
                "current_source_revision_id": CURRENT_REVISION_ID,
                "previous_extraction_run_id": PREVIOUS_EXTRACTION_RUN_ID,
                "current_extraction_run_id": CURRENT_EXTRACTION_RUN_ID,
                "artifact_extractors": list(EXTRACTOR_PROFILE),
                "policy_version": "candidate-factual-change.v1",
                "artifact_inputs": {"previous": [], "current": []},
            }
        ),
        _digest({"artifact_deltas": [], "structural_deltas": []}),
    )
    reduction_run = _run(
        REDUCTION_RUN_ID,
        RunType.OTHER,
        "candidate-factual-reduction.v1",
        _digest(
            {
                "diff_run_id": DIFF_RUN_ID,
                "segmentation_run_id": SEGMENTATION_RUN_ID,
                "planner_run_id": PLANNER_RUN_ID,
                "previous_capture": previous_manifest.model_dump(
                    mode="json", by_alias=True
                ),
                "current_capture": current_manifest.model_dump(
                    mode="json", by_alias=True
                ),
                "previous_extraction_run_id": PREVIOUS_EXTRACTION_RUN_ID,
                "current_extraction_run_id": CURRENT_EXTRACTION_RUN_ID,
                "artifact_extractors": list(EXTRACTOR_PROFILE),
                "change_run_id": CHANGE_RUN_ID,
                "candidates": [candidate.model_dump(mode="json", by_alias=True)],
                "affected_file_plans": [
                    plan.model_dump(mode="json", by_alias=True)
                ],
                "policy_version": "candidate-factual-reduction.v1",
            }
        ),
        _digest([reduction.model_dump(mode="json", by_alias=True)]),
    )
    store.put_many(
        (
            candidate,
            plan,
            reduction,
            previous_manifest,
            current_manifest,
            previous_extraction_run,
            current_extraction_run,
            segmentation_run,
            planner_run,
            change_run,
            reduction_run,
        )
    )


def test_packet_authenticator_recovers_non_default_bounded_profile(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _seed_retained_git_only_generation(store)
    built = CandidateEvidencePacketService(
        store,
        max_structural_previews=1,
        max_assertion_previews=2,
        preview_chars=64,
        clock=lambda: NOW,
        id_factory=lambda: "custom-profile",
    ).build_reduction(REDUCTION_RUN_ID)

    authenticated_run, authenticated_packets = (
        CandidateEvidencePacketGenerationAuthenticator(store).authenticate(
            built.run.run_id
        )
    )

    assert authenticated_run == built.run
    assert authenticated_packets == built.packets
    generation = store.list(CandidateEvidencePacketGeneration)[0]
    assert generation.max_structural_previews == 1
    assert generation.max_assertion_previews == 2
    assert generation.preview_chars == 64
    assert generation.candidate_evidence_packet_ids == tuple(
        sorted(item.candidate_evidence_packet_id for item in built.packets)
    )


def test_packet_authenticator_rejects_unknown_packet_policy(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _seed_retained_git_only_generation(store)
    built = CandidateEvidencePacketService(
        store,
        policy_version="candidate-evidence-packet.typo",
        clock=lambda: NOW,
        id_factory=lambda: "unknown-policy",
    ).build_reduction(REDUCTION_RUN_ID)

    with pytest.raises(
        CandidateEvidencePacketError,
        match="unrecognized packet policies",
    ):
        CandidateEvidencePacketGenerationAuthenticator(store).authenticate(
            built.run.run_id
        )


def test_preview_identifiers_are_bounded_for_interpreter_context() -> None:
    with pytest.raises(ValidationError):
        StructuralDeltaPreview(
            structural_delta_id="s" * 257,
            source_locator=PATH,
            structural_key="key",
            change_type=StructuralDeltaType.MODIFIED,
            extractor_name="extractor",
            extractor_version="1",
        )

    with pytest.raises(ValidationError):
        StructuralDeltaPreview(
            structural_delta_id="structural:bounded",
            source_locator=PATH,
            structural_key="key",
            change_type=StructuralDeltaType.MODIFIED,
            extractor_name="e" * 257,
            extractor_version="1",
        )
