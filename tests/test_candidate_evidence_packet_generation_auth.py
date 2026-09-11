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
from tests.m5_packet_fixture import seed_path_pipeline


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



def _seed_retained_git_only_generation(
    store: SQLiteContractStore,
    *,
    extractor_profile=EXTRACTOR_PROFILE,
    max_paths_per_candidate: int = 50,
) -> None:
    from lemmamind.candidate_reduction import CandidateFactualReductionService

    seeded = seed_path_pipeline(
        store,
        source_id=SOURCE_ID,
        previous_revision_id=PREVIOUS_REVISION_ID,
        current_revision_id=CURRENT_REVISION_ID,
        diff_run_id=DIFF_RUN_ID,
        segmentation_run_id=SEGMENTATION_RUN_ID,
        planner_run_id=PLANNER_RUN_ID,
        tracking_assignment_id="tracking:packet-profile",
        now=NOW,
        max_paths_per_candidate=max_paths_per_candidate,
        path_specs=(
            {
                "path": PATH,
                "previous_entry_type": "commit",
                "current_entry_type": "commit",
                "previous_mode": "160000",
                "current_mode": "160000",
                "previous_object_sha": "1" * 40,
                "current_object_sha": "2" * 40,
                "previous_size": None,
                "current_size": None,
            },
        ),
    )
    candidate = seeded.candidates[0]
    plan = seeded.plans[0]
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
                "capture_manifest": previous_manifest.model_dump(mode="json", by_alias=True),
                "artifact_extractors": list(extractor_profile),
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
                "capture_manifest": current_manifest.model_dump(mode="json", by_alias=True),
                "artifact_extractors": list(extractor_profile),
                "policy_version": "deterministic-evidence.v1",
            }
        ),
        _digest(extraction_outputs),
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
                "artifact_extractors": list(extractor_profile),
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
                "previous_capture": previous_manifest.model_dump(mode="json", by_alias=True),
                "current_capture": current_manifest.model_dump(mode="json", by_alias=True),
                "previous_extraction_run_id": PREVIOUS_EXTRACTION_RUN_ID,
                "current_extraction_run_id": CURRENT_EXTRACTION_RUN_ID,
                "artifact_extractors": list(extractor_profile),
                "change_run_id": CHANGE_RUN_ID,
                "candidates": [candidate.model_dump(mode="json", by_alias=True)],
                "affected_file_plans": [plan.model_dump(mode="json", by_alias=True)],
                "policy_version": "candidate-factual-reduction.v1",
            }
        ),
        _digest([reduction.model_dump(mode="json", by_alias=True)]),
    )
    store.put_many(
        (
            reduction,
            previous_manifest,
            current_manifest,
            previous_extraction_run,
            current_extraction_run,
            change_run,
            reduction_run,
        )
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



def test_packet_generation_preserves_large_custom_profile_with_silent_extractor(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    custom_profile = tuple(
        {"name": f"custom-{index}", "version": "1"}
        for index in range(7)
    ) + ({"name": "silent-extractor", "version": "1"},)
    _seed_retained_git_only_generation(store, extractor_profile=custom_profile)
    built = CandidateEvidencePacketService(
        store,
        artifact_extractors=custom_profile,
        clock=lambda: NOW,
        id_factory=lambda: "large-custom-profile",
    ).build_reduction(REDUCTION_RUN_ID)

    generation = store.list(CandidateEvidencePacketGeneration)[0]
    assert tuple((item.name, item.version) for item in generation.artifact_extractors) == tuple(
        (item["name"], item["version"]) for item in custom_profile
    )
    authenticated_run, authenticated_packets = (
        CandidateEvidencePacketGenerationAuthenticator(store).authenticate(built.run.run_id)
    )
    assert authenticated_run == built.run
    assert authenticated_packets == built.packets


def test_packet_authenticates_safe_candidate_from_segmentation_bound_above_50(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    _seed_retained_git_only_generation(store, max_paths_per_candidate=100)

    built = CandidateEvidencePacketService(
        store,
        artifact_extractors=EXTRACTOR_PROFILE,
        clock=lambda: NOW,
        id_factory=lambda: "segmentation-bound-100",
    ).build_reduction(REDUCTION_RUN_ID)

    assert len(built.packets) == 1
    assert built.packets[0].paths == (PATH,)
    authenticated_run, authenticated_packets = (
        CandidateEvidencePacketGenerationAuthenticator(store).authenticate(built.run.run_id)
    )
    assert authenticated_run == built.run
    assert authenticated_packets == built.packets


def test_packet_preserves_repeated_extractor_descriptors_in_exact_order(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    repeated_profile = (
        {"name": "silent-duplicate", "version": "1"},
        {"name": "silent-duplicate", "version": "1"},
        {"name": "other-silent", "version": "2"},
    )
    _seed_retained_git_only_generation(store, extractor_profile=repeated_profile)

    built = CandidateEvidencePacketService(
        store,
        artifact_extractors=repeated_profile,
        clock=lambda: NOW,
        id_factory=lambda: "repeated-extractor-profile",
    ).build_reduction(REDUCTION_RUN_ID)

    generation = store.list(CandidateEvidencePacketGeneration)[0]
    assert tuple((item.name, item.version) for item in generation.artifact_extractors) == (
        ("silent-duplicate", "1"),
        ("silent-duplicate", "1"),
        ("other-silent", "2"),
    )
    authenticated_run, authenticated_packets = (
        CandidateEvidencePacketGenerationAuthenticator(store).authenticate(built.run.run_id)
    )
    assert authenticated_run == built.run
    assert authenticated_packets == built.packets
