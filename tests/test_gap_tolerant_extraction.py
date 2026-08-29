from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.candidate_extraction_gaps import (
    CandidateExtractionGapService,
    CandidateExtractionGapSignal,
)
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
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
    DeterministicExtractionService,
    ExtractionError,
    FactSpec,
)
from lemmamind.extraction_diagnostics import (
    ExtractionDiagnostic,
    GapTolerantExtractionPairService,
)
from lemmamind.gap_aware_change import GapAwareDeterministicChangeService
from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)
SOURCE_ID = "github:gap-test"
PREVIOUS_REVISION_ID = f"{SOURCE_ID}@{'a' * 40}"
CURRENT_REVISION_ID = f"{SOURCE_ID}@{'b' * 40}"
DIGEST = "sha256:" + "0" * 64
GOOD_PATH = "src/good.txt"
BAD_PATH = "src/bad.ts"


class FixedClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        self.value += timedelta(milliseconds=1)
        return self.value


class Ids:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"gap-test-{self.value}"


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


class RecoverableSyntaxExtractor:
    name = "recoverable-syntax"
    version = "1"

    def supports(self, artifact):
        return artifact.source_locator.endswith(".ts")

    def extract(self, artifact, data):
        value = data.decode("utf-8")
        if "INVALID" in value:
            raise ExtractionError(f"invalid fixture syntax: {artifact.source_locator}")
        return (
            FactSpec(
                locator=f"{artifact.source_locator}#syntax",
                raw_value="valid",
                normalized_value="valid",
                extractor_name=self.name,
                extractor_version=self.version,
            ),
        )


def _pipeline_run(run_id, run_type, offset):
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


def _capture(store, objects, *, capture_id, revision_id, captured_at, contents):
    references = []
    records = []
    for path, data in sorted(contents.items()):
        content_hash = objects.put(data)
        artifact_id = f"artifact:{capture_id}:{path}"
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=path,
            content_hash=content_hash,
            media_type="text/plain",
        )
        records.append(artifact)
        references.append(
            CaptureArtifactRef(
                artifact_id=artifact_id,
                source_locator=path,
                content_hash=content_hash,
                media_type="text/plain",
                retrieval_status=RetrievalStatus.CAPTURED,
            )
        )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision_id,
        capture_policy_version="gap-test.v1",
        captured_at=captured_at,
        artifacts=tuple(references),
    )
    store.put_many((*records, manifest))
    return manifest


def _prepare(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    store.put_many(
        (
            Source(
                source_id=SOURCE_ID,
                source_kind=SourceKind.GITHUB_REPOSITORY,
                source_role=SourceRole.IMPLEMENTATION,
                canonical_locator="https://github.com/example/gap-test",
                first_seen_at=NOW,
                last_seen_at=NOW + timedelta(seconds=1),
            ),
            SourceRevision(
                source_revision_id=PREVIOUS_REVISION_ID,
                source_id=SOURCE_ID,
                commit_sha="a" * 40,
                tree_sha="1" * 40,
                observed_at=NOW,
            ),
            SourceRevision(
                source_revision_id=CURRENT_REVISION_ID,
                source_id=SOURCE_ID,
                commit_sha="b" * 40,
                tree_sha="2" * 40,
                observed_at=NOW + timedelta(seconds=1),
            ),
        )
    )
    previous = _capture(
        store,
        objects,
        capture_id="capture:previous",
        revision_id=PREVIOUS_REVISION_ID,
        captured_at=NOW + timedelta(seconds=2),
        contents={GOOD_PATH: b"old", BAD_PATH: b"valid"},
    )
    current = _capture(
        store,
        objects,
        capture_id="capture:current",
        revision_id=CURRENT_REVISION_ID,
        captured_at=NOW + timedelta(seconds=3),
        contents={GOOD_PATH: b"new", BAD_PATH: b"INVALID"},
    )
    return store, objects, previous, current


def test_pair_records_source_local_gap_and_gap_aware_change_excludes_it(tmp_path) -> None:
    store, objects, previous, current = _prepare(tmp_path)
    extractors = (ContentFactExtractor(), RecoverableSyntaxExtractor())
    pair = GapTolerantExtractionPairService(
        store,
        objects,
        artifact_extractors=extractors,
        clock=FixedClock(NOW + timedelta(seconds=10)),
        id_factory=Ids(),
    ).extract_pair(previous.capture_id, current.capture_id)

    assert pair.gap_paths == (BAD_PATH,)
    assert pair.previous.diagnostics == ()
    assert len(pair.current.diagnostics) == 1
    diagnostic = pair.current.diagnostics[0]
    assert diagnostic.capture_id == current.capture_id
    assert diagnostic.source_revision_id == CURRENT_REVISION_ID
    assert diagnostic.source_locator == BAD_PATH
    assert diagnostic.extractor_name == "recoverable-syntax"
    assert store.list(ExtractionDiagnostic) == [diagnostic]

    assert any(
        fact.locator == f"{BAD_PATH}#syntax" for fact in pair.previous.extraction.facts
    )
    assert not any(
        fact.locator == f"{BAD_PATH}#syntax" for fact in pair.current.extraction.facts
    )
    for side in (pair.previous, pair.current):
        assert any(fact.locator.startswith(BAD_PATH) for fact in side.extraction.facts)
        assert any(fact.locator.startswith(GOOD_PATH) for fact in side.extraction.facts)

    changed = GapAwareDeterministicChangeService(
        store,
        objects,
        clock=FixedClock(NOW + timedelta(seconds=20)),
        id_factory=lambda: "gap-change",
    ).compare_captures(
        previous.capture_id,
        current.capture_id,
        previous_extraction_run_id=pair.previous.extraction.run.run_id,
        current_extraction_run_id=pair.current.extraction.run.run_id,
        artifact_extractors=extractors,
    )

    assert {item.source_locator for item in changed.artifact_deltas} == {
        GOOD_PATH,
        BAD_PATH,
    }
    assert {item.source_locator for item in changed.structural_deltas} == {GOOD_PATH}


def test_strict_v1_extraction_still_fails_on_same_recoverable_error(tmp_path) -> None:
    store, objects, _, current = _prepare(tmp_path)
    extractors = (ContentFactExtractor(), RecoverableSyntaxExtractor())

    with pytest.raises(ExtractionError, match="invalid fixture syntax"):
        DeterministicExtractionService(
            store,
            objects,
            artifact_extractors=extractors,
        ).extract_capture(current.capture_id)


def test_candidate_gap_signal_closes_capture_and_reduction_lineage(tmp_path) -> None:
    store, objects, previous, current = _prepare(tmp_path)
    extractors = (ContentFactExtractor(), RecoverableSyntaxExtractor())
    pair = GapTolerantExtractionPairService(
        store,
        objects,
        artifact_extractors=extractors,
        clock=FixedClock(NOW + timedelta(seconds=10)),
        id_factory=Ids(),
    ).extract_pair(previous.capture_id, current.capture_id)

    segmentation_run_id = "run:segmentation:test"
    reduction_run_id = "run:reduction:test"
    candidate = IntervalCandidateSegment(
        interval_candidate_segment_id="candidate:test",
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        commit_path_snapshot_id="snapshot:test",
        commit_sha="b" * 40,
        commit_ordinal=1,
        path_group='top-level:"src"',
        chunk_ordinal=1,
        git_path_delta_ids=("delta:bad", "delta:good"),
        paths=(BAD_PATH, GOOD_PATH),
        segmentation_run_id=segmentation_run_id,
    )
    reduction = CandidateFactualReduction(
        candidate_factual_reduction_id="candidate-reduction:test",
        interval_candidate_segment_id=candidate.interval_candidate_segment_id,
        source_id=SOURCE_ID,
        previous_source_revision_id=PREVIOUS_REVISION_ID,
        current_source_revision_id=CURRENT_REVISION_ID,
        paths=(BAD_PATH, GOOD_PATH),
        affected_file_plan_ids=("plan:bad", "plan:good"),
        capture_scoped_paths=(BAD_PATH, GOOD_PATH),
        git_only_paths=(BAD_PATH, GOOD_PATH),
        signal_kinds=(CandidateSignalKind.GIT_ONLY_CHANGE,),
        disposition=CandidateReductionDisposition.RETAIN,
        diff_run_id="run:diff:test",
        segmentation_run_id=segmentation_run_id,
        planner_run_id="run:planner:test",
        previous_capture_id=previous.capture_id,
        current_capture_id=current.capture_id,
        previous_extraction_run_id=pair.previous.extraction.run.run_id,
        current_extraction_run_id=pair.current.extraction.run.run_id,
        change_run_id="run:change:test",
        reduction_run_id=reduction_run_id,
    )
    store.put_many(
        (
            _pipeline_run(segmentation_run_id, RunType.DIFF, 30),
            _pipeline_run(reduction_run_id, RunType.OTHER, 32),
            candidate,
            reduction,
        )
    )

    result = CandidateExtractionGapService(store).record_signals(
        segmentation_run_id=segmentation_run_id,
        previous_extraction_run_id=pair.previous.extraction.run.run_id,
        current_extraction_run_id=pair.current.extraction.run.run_id,
        reduction_run_id=reduction_run_id,
    )

    assert result.candidate_count == 1
    assert result.paths == (BAD_PATH,)
    signal = result.signals[0]
    assert signal.interval_candidate_segment_id == candidate.interval_candidate_segment_id
    assert signal.previous_capture_id == previous.capture_id
    assert signal.current_capture_id == current.capture_id
    assert signal.paths == (BAD_PATH,)
    assert signal.previous_diagnostic_ids == ()
    assert signal.current_diagnostic_ids == (
        pair.current.diagnostics[0].extraction_diagnostic_id,
    )
    assert store.list(CandidateExtractionGapSignal) == [signal]
