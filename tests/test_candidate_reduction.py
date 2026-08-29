from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.candidate_reduction import (
    CandidateFactualReductionError,
    CandidateFactualReductionService,
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
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    PipelineRun,
    RetrievalStatus,
    RunType,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
)
from lemmamind.extraction import (
    ArtifactPathExtractor,
    AssertionSpec,
    DeterministicExtractionService,
    FactSpec,
)
from lemmamind.interval_segmentation_contracts import (
    CommitRangeStatus,
    CommitRangeSummary,
    IntervalCandidateSegment,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.path_change_contracts import (
    ChangeSurface,
    GitPathDelta,
    GitPathDeltaType,
    GitPathDiffSummary,
)
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)
SOURCE_ID = "github:candidate-reduction"
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{'a' * 40}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{'b' * 40}"
RECURSIVE_PREVIOUS_CAPTURE_ID = "capture-recursive-tree:previous"
RECURSIVE_CURRENT_CAPTURE_ID = "capture-recursive-tree:current"
PREVIOUS_CAPTURE_ID = "capture:candidate-previous"
CURRENT_CAPTURE_ID = "capture:candidate-current"
DIFF_RUN_ID = "run:recursive-path-diff:test"
SEGMENTATION_RUN_ID = "run:interval-segmentation:test"
PLANNER_RUN_ID = "run:affected-file-plan:test"
PATH = "src/core.py"
DIGEST = "sha256:" + "0" * 64


class FixedClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class Ids:
    def __init__(self, prefix):
        self.prefix = prefix
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"{self.prefix}-{self.value}"


class ContentFactExtractor:
    name = "content-fact"
    version = "1"

    def supports(self, artifact):
        return True

    def extract(self, artifact, data):
        value = data.decode("utf-8")
        return (
            FactSpec(
                locator=f"{artifact.source_locator}#content",
                raw_value=value,
                normalized_value=value,
                extractor_name=self.name,
                extractor_version=self.version,
            ),
        )


class ContentAssertionExtractor:
    name = "content-assertion"
    version = "1"

    def supports(self, artifact):
        return True

    def extract(self, artifact, data):
        return (
            AssertionSpec(
                locator=f"{artifact.source_locator}:L1-L1",
                statement=data.decode("utf-8"),
                extractor_name=self.name,
                extractor_version=self.version,
            ),
        )


def pipeline_run(run_id, run_type, offset):
    return PipelineRun(
        run_id=run_id,
        run_type=run_type,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="test.v1",
        started_at=NOW + timedelta(seconds=offset),
        finished_at=NOW + timedelta(seconds=offset + 1),
        inputs_hash=DIGEST,
        outputs_hash=DIGEST,
    )


def captured_manifest(store, objects, capture_id, revision_id, data, *, path=PATH):
    if data is None:
        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision_id,
            capture_policy_version="candidate-test.v1",
            captured_at=(
                NOW + timedelta(seconds=20)
                if revision_id == PREVIOUS_REVISION_ID
                else NOW + timedelta(seconds=21)
            ),
            artifacts=(),
        )
        store.put_many((manifest,))
        return manifest

    digest = objects.put(data)
    artifact_id = f"artifact:{capture_id}:{path}"
    artifact = Artifact(
        artifact_id=artifact_id,
        capture_id=capture_id,
        source_locator=path,
        content_hash=digest,
        media_type="text/plain",
    )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision_id,
        capture_policy_version="candidate-test.v1",
        captured_at=(
            NOW + timedelta(seconds=20)
            if revision_id == PREVIOUS_REVISION_ID
            else NOW + timedelta(seconds=21)
        ),
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact_id,
                source_locator=path,
                content_hash=digest,
                media_type="text/plain",
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    store.put_many((artifact, manifest))
    return manifest


def prepare(
    tmp_path,
    *,
    previous_data=b"old",
    current_data=b"new",
    policy_suppressed=False,
    mode_only=False,
    path=PATH,
):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source = Source(
        source_id=SOURCE_ID,
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/example/repo",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    previous_revision = SourceRevision(
        source_revision_id=PREVIOUS_REVISION_ID,
        source_id=SOURCE_ID,
        commit_sha="a" * 40,
        tree_sha="1" * 40,
        observed_at=NOW,
    )
    current_revision = SourceRevision(
        source_revision_id=CURRENT_REVISION_ID,
        source_id=SOURCE_ID,
        commit_sha="b" * 40,
        tree_sha="2" * 40,
        observed_at=NOW + timedelta(seconds=1),
    )

    previous_object_sha = "c" * 40
    current_object_sha = previous_object_sha if mode_only else "d" * 40
    previous_mode = "100644"
    current_mode = "100755" if mode_only else "100644"
    delta = GitPathDelta(
        git_path_delta_id="git-path-delta:test",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        previous_capture_id=RECURSIVE_PREVIOUS_CAPTURE_ID,
        current_capture_id=RECURSIVE_CURRENT_CAPTURE_ID,
        path=path,
        change_type=GitPathDeltaType.MODIFIED,
        surface=(ChangeSurface.GENERATED if policy_suppressed else ChangeSurface.SOURCE),
        previous_entry_type="blob",
        current_entry_type="blob",
        previous_mode=previous_mode,
        current_mode=current_mode,
        previous_object_sha=previous_object_sha,
        current_object_sha=current_object_sha,
        previous_size=len(previous_data or b""),
        current_size=len(current_data or b""),
        diff_run_id=DIFF_RUN_ID,
    )
    diff_summary = GitPathDiffSummary(
        git_path_diff_summary_id="git-path-diff-summary:test",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        previous_capture_id=RECURSIVE_PREVIOUS_CAPTURE_ID,
        current_capture_id=RECURSIVE_CURRENT_CAPTURE_ID,
        delta_count=1,
        diff_run_id=DIFF_RUN_ID,
    )
    range_summary = CommitRangeSummary(
        commit_range_summary_id="commit-range-summary:test",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        provider_status=CommitRangeStatus.AHEAD,
        total_commits=1,
        commit_shas=("b" * 40,),
        segmentation_run_id=SEGMENTATION_RUN_ID,
    )
    candidate = IntervalCandidateSegment(
        interval_candidate_segment_id="interval-candidate:test",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        commit_path_snapshot_id="commit-path-snapshot:test",
        commit_sha="b" * 40,
        commit_ordinal=1,
        path_group='top-level:"src"',
        chunk_ordinal=1,
        git_path_delta_ids=(delta.git_path_delta_id,),
        paths=(path,),
        segmentation_run_id=SEGMENTATION_RUN_ID,
    )

    disposition = (
        CapturePlanDisposition.SUPPRESSED
        if policy_suppressed
        else CapturePlanDisposition.CAPTURE
    )
    reason = (
        CapturePlanReason.GENERATED_SURFACE
        if policy_suppressed
        else CapturePlanReason.ELIGIBLE_BLOB
    )
    plan = AffectedFileCapturePlan(
        affected_file_plan_id="affected-file-plan:test",
        git_path_delta_id=delta.git_path_delta_id,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        path=path,
        surface=delta.surface,
        previous=CapturePlanSide(
            source_revision_id=PREVIOUS_REVISION_ID,
            disposition=disposition,
            reason=reason,
            entry_type="blob",
            object_sha=previous_object_sha,
            size=len(previous_data or b""),
        ),
        current=CapturePlanSide(
            source_revision_id=CURRENT_REVISION_ID,
            disposition=disposition,
            reason=reason,
            entry_type="blob",
            object_sha=current_object_sha,
            size=len(current_data or b""),
        ),
        tracking_assignment_id="tracking:test",
        tracking_level="3",
        diff_run_id=DIFF_RUN_ID,
        planner_run_id=PLANNER_RUN_ID,
    )

    store.put_many(
        (
            source,
            previous_revision,
            current_revision,
            pipeline_run(DIFF_RUN_ID, RunType.DIFF, 2),
            pipeline_run(SEGMENTATION_RUN_ID, RunType.OTHER, 4),
            pipeline_run(PLANNER_RUN_ID, RunType.OTHER, 6),
            diff_summary,
            delta,
            range_summary,
            candidate,
            plan,
        )
    )

    if policy_suppressed:
        previous_manifest = captured_manifest(
            store, objects, PREVIOUS_CAPTURE_ID, PREVIOUS_REVISION_ID, None, path=path
        )
        current_manifest = captured_manifest(
            store, objects, CURRENT_CAPTURE_ID, CURRENT_REVISION_ID, None, path=path
        )
    else:
        previous_manifest = captured_manifest(
            store, objects, PREVIOUS_CAPTURE_ID, PREVIOUS_REVISION_ID, previous_data, path=path
        )
        current_manifest = captured_manifest(
            store, objects, CURRENT_CAPTURE_ID, CURRENT_REVISION_ID, current_data, path=path
        )

    return store, objects, previous_manifest, current_manifest


def extract_pair(store, objects, extractors):
    ids = Ids("extract")
    service = DeterministicExtractionService(
        store,
        objects,
        artifact_extractors=extractors,
        clock=FixedClock(NOW + timedelta(seconds=30)),
        id_factory=ids,
    )
    previous = service.extract_capture(PREVIOUS_CAPTURE_ID)
    current = service.extract_capture(CURRENT_CAPTURE_ID)
    return previous, current


def reduce(store, objects, extractors, previous_extraction, current_extraction):
    return CandidateFactualReductionService(
        store,
        objects,
        clock=FixedClock(NOW + timedelta(seconds=40)),
        id_factory=Ids("reduce"),
    ).reduce_segmentation(
        diff_run_id=DIFF_RUN_ID,
        segmentation_run_id=SEGMENTATION_RUN_ID,
        planner_run_id=PLANNER_RUN_ID,
        previous_capture_id=PREVIOUS_CAPTURE_ID,
        current_capture_id=CURRENT_CAPTURE_ID,
        previous_extraction_run_id=previous_extraction.run.run_id,
        current_extraction_run_id=current_extraction.run.run_id,
        artifact_extractors=extractors,
    )


def test_structural_delta_retains_candidate_with_exact_provenance(tmp_path) -> None:
    store, objects, _, _ = prepare(tmp_path)
    extractors = (ContentFactExtractor(),)
    previous, current = extract_pair(store, objects, extractors)

    result = reduce(store, objects, extractors, previous, current)

    assert result.retained_count == 1
    assert result.suppressed_count == 0
    item = result.reductions[0]
    assert item.disposition is CandidateReductionDisposition.RETAIN
    assert item.signal_kinds == (CandidateSignalKind.STRUCTURAL_DELTA,)
    assert item.structural_delta_paths == (PATH,)
    assert item.artifact_delta_paths == (PATH,)
    assert item.change_run_id == result.change.run.run_id
    assert store.list(CandidateFactualReduction) == [item]


def test_authored_assertion_change_is_retained_without_promoting_it_to_structural_fact(tmp_path) -> None:
    store, objects, _, _ = prepare(tmp_path, previous_data=b"claim one", current_data=b"claim two")
    extractors = (ContentAssertionExtractor(),)
    previous, current = extract_pair(store, objects, extractors)

    result = reduce(store, objects, extractors, previous, current)
    item = result.reductions[0]

    assert item.structural_delta_ids == ()
    assert item.assertion_changed_paths == (PATH,)
    assert item.artifact_only_paths == ()
    assert item.signal_kinds == (CandidateSignalKind.AUTHORED_ASSERTION_CHANGE,)
    assert item.disposition is CandidateReductionDisposition.RETAIN


def test_changed_bytes_without_selected_signal_fail_closed_to_retained_artifact_delta(tmp_path) -> None:
    store, objects, _, _ = prepare(tmp_path)
    extractors = (ArtifactPathExtractor(),)
    previous, current = extract_pair(store, objects, extractors)

    result = reduce(store, objects, extractors, previous, current)
    item = result.reductions[0]

    assert item.structural_delta_ids == ()
    assert item.assertion_changed_paths == ()
    assert item.artifact_only_paths == (PATH,)
    assert item.signal_kinds == (
        CandidateSignalKind.ARTIFACT_DELTA_WITHOUT_EXTRACTED_SIGNAL,
    )
    assert item.disposition is CandidateReductionDisposition.RETAIN


def test_git_mode_only_change_is_not_suppressed_when_captured_bytes_are_equal(tmp_path) -> None:
    store, objects, _, _ = prepare(
        tmp_path,
        previous_data=b"same",
        current_data=b"same",
        mode_only=True,
    )
    extractors = (ArtifactPathExtractor(),)
    previous, current = extract_pair(store, objects, extractors)

    result = reduce(store, objects, extractors, previous, current)
    item = result.reductions[0]

    assert result.change.artifact_deltas == ()
    assert item.git_only_paths == (PATH,)
    assert item.signal_kinds == (CandidateSignalKind.GIT_ONLY_CHANGE,)
    assert item.disposition is CandidateReductionDisposition.RETAIN


def test_fully_policy_suppressed_candidate_is_the_only_automatic_suppression(tmp_path) -> None:
    store, objects, _, _ = prepare(
        tmp_path,
        previous_data=b"generated old",
        current_data=b"generated new",
        policy_suppressed=True,
    )
    extractors = (ArtifactPathExtractor(),)
    previous, current = extract_pair(store, objects, extractors)

    result = reduce(store, objects, extractors, previous, current)
    item = result.reductions[0]

    assert result.retained_count == 0
    assert result.suppressed_count == 1
    assert item.capture_scoped_paths == ()
    assert item.policy_suppressed_paths == (PATH,)
    assert item.signal_kinds == (CandidateSignalKind.POLICY_SUPPRESSED,)
    assert item.disposition is CandidateReductionDisposition.SUPPRESS


def test_capture_scope_must_exactly_match_affected_file_plan_before_change_generation(tmp_path) -> None:
    store, objects, _, current_manifest = prepare(tmp_path)
    empty_previous = CaptureManifest(
        capture_id="capture:wrong-previous",
        source_revision_id=PREVIOUS_REVISION_ID,
        capture_policy_version="candidate-test.v1",
        captured_at=NOW + timedelta(seconds=20),
        artifacts=(),
    )
    store.put_many((empty_previous,))

    service = CandidateFactualReductionService(
        store,
        objects,
        clock=FixedClock(NOW + timedelta(seconds=40)),
        id_factory=Ids("reduce"),
    )
    with pytest.raises(
        CandidateFactualReductionError,
        match="exactly match affected-file plan scope",
    ):
        service.reduce_segmentation(
            diff_run_id=DIFF_RUN_ID,
            segmentation_run_id=SEGMENTATION_RUN_ID,
            planner_run_id=PLANNER_RUN_ID,
            previous_capture_id=empty_previous.capture_id,
            current_capture_id=current_manifest.capture_id,
            previous_extraction_run_id="run:not-needed",
            current_extraction_run_id="run:not-needed",
            artifact_extractors=(ArtifactPathExtractor(),),
        )

    assert store.list(CandidateFactualReduction) == []
