from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    Observation,
    ObservationEpistemicType,
    PipelineRun,
    RepositoryIdentity,
    RetrievalStatus,
    RunType,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
    SupportType,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.observations import SupportRef
from lemmamind.storage import SQLiteContractStore
from lemmamind.tracking import RepositoryTrackingService, TrackingNotAllowed
from lemmamind.tracking_adapters import (
    TrackingAwareGitHubCaptureService,
    TrackingAwareGitHubProcessCaptureService,
    TrackingAwareGitHubProcessEventCaptureService,
    TrackingAwareObservationConstructionService,
)
from lemmamind.tracking_contracts import TrackingLevel

T0 = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40
DIGEST_1 = "sha256:" + "1" * 64
DIGEST_2 = "sha256:" + "2" * 64


class Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"id-{self.value}"


class FakeRepositoryReader:
    def __init__(self) -> None:
        self.metadata = {
            "id": 42,
            "owner": {"login": "Acme"},
            "name": "Repo",
            "default_branch": "main",
            "archived": False,
        }
        self.commit_calls = 0
        self.file_calls = 0

    def get_repository(self, owner: str, repo: str):
        return self.metadata

    def get_commit(self, owner: str, repo: str, ref: str):
        self.commit_calls += 1
        return {"sha": COMMIT_SHA, "commit": {"tree": {"sha": TREE_SHA}}}

    def get_file(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        self.file_calls += 1
        return b"# tracked\n"


class FailIfProcessRead:
    def get_issue(self, owner: str, repo: str, number: int):
        raise AssertionError("tracking gate must run before process reader")

    def get_pull(self, owner: str, repo: str, number: int):
        raise AssertionError("tracking gate must run before process reader")


class FailIfHistoryRead:
    def get_issue_events(self, owner: str, repo: str, number: int):
        raise AssertionError("tracking gate must run before history reader")


def seed_repository(store: SQLiteContractStore) -> tuple[Source, SourceRevision]:
    source = Source(
        source_id="github:42",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.UNKNOWN,
        canonical_locator="https://github.com/Acme/Repo",
        first_seen_at=T0,
        last_seen_at=T0,
    )
    repository = RepositoryIdentity(
        source_id=source.source_id,
        provider_repository_id="42",
        owner="Acme",
        name="Repo",
        default_branch="main",
        archived=False,
    )
    revision = SourceRevision(
        source_revision_id=f"{source.source_id}@{COMMIT_SHA}",
        source_id=source.source_id,
        commit_sha=COMMIT_SHA,
        tree_sha=TREE_SHA,
        observed_at=T0 + timedelta(minutes=5),
    )
    store.put_many((source, repository, revision))
    return source, revision


def make_tracking(store: SQLiteContractStore) -> RepositoryTrackingService:
    return RepositoryTrackingService(store, clock=Clock(T0 + timedelta(hours=3)))


def test_repository_file_capture_is_blocked_below_shallow_and_allowed_at_shallow(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source, _ = seed_repository(store)
    reader = FakeRepositoryReader()
    tracking = make_tracking(store)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.METADATA_ONLY,
        assigned_by="operator:test",
        reason="metadata only",
        effective_at=T0 + timedelta(hours=1),
    )
    capture = TrackingAwareGitHubCaptureService(
        reader,
        store,
        objects,
        tracking=tracking,
        clock=Clock(T0 + timedelta(hours=3)),
        id_factory=Ids(),
    )

    with pytest.raises(TrackingNotAllowed):
        capture.capture_repository("Acme/Repo", ["README.md"])
    assert reader.commit_calls == 0
    assert reader.file_calls == 0

    tracking.assign_level(
        source.source_id,
        TrackingLevel.SHALLOW,
        assigned_by="operator:test",
        reason="allow repository files",
        effective_at=T0 + timedelta(hours=2),
    )
    result = capture.capture_repository("Acme/Repo", ["README.md"])

    assert result.source.source_id == source.source_id
    assert reader.commit_calls == 1
    assert reader.file_calls == 1


def test_process_snapshot_gate_runs_before_provider_read(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source, revision = seed_repository(store)
    tracking = make_tracking(store)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="operator:test",
        reason="structural only",
        effective_at=T0 + timedelta(hours=1),
    )
    capture = TrackingAwareGitHubProcessCaptureService(
        FailIfProcessRead(),
        store,
        objects,
        tracking=tracking,
        clock=Clock(T0 + timedelta(hours=3)),
    )

    with pytest.raises(TrackingNotAllowed):
        capture.capture_process(revision.source_revision_id, [])


def test_process_history_gate_runs_before_provider_read(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source, revision = seed_repository(store)
    tracking = make_tracking(store)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="operator:test",
        reason="structural only",
        effective_at=T0 + timedelta(hours=1),
    )
    capture = TrackingAwareGitHubProcessEventCaptureService(
        FailIfHistoryRead(),
        store,
        objects,
        tracking=tracking,
        clock=Clock(T0 + timedelta(hours=3)),
    )

    with pytest.raises(TrackingNotAllowed):
        capture.capture_issue_events(revision.source_revision_id, [37])


def seed_evidence(store: SQLiteContractStore, revision: SourceRevision) -> EvidenceFact:
    artifact = Artifact(
        artifact_id="artifact:readme",
        capture_id="capture:readme",
        source_locator="README.md",
        content_hash=DIGEST_1,
        media_type="text/markdown",
    )
    manifest = CaptureManifest(
        capture_id=artifact.capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test-capture.v1",
        captured_at=T0 + timedelta(minutes=10),
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator=artifact.source_locator,
                content_hash=artifact.content_hash,
                media_type=artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    extraction_run = PipelineRun(
        run_id="run:extract",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version="lemmamind.m0.v1",
        policy_version="test-extraction.v1",
        started_at=T0 + timedelta(minutes=11),
        finished_at=T0 + timedelta(minutes=11),
        inputs_hash=DIGEST_1,
        outputs_hash=DIGEST_2,
    )
    fact = EvidenceFact(
        evidence_id="evidence:readme-heading",
        artifact_id=artifact.artifact_id,
        locator="README.md:1",
        raw_value="# tracked",
        normalized_value="tracked",
        extractor_name="test",
        extractor_version="1",
        run_id=extraction_run.run_id,
    )
    store.put_many((artifact, manifest, extraction_run, fact))
    return fact


def test_reasoning_requires_structural_or_deeper_tracking(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    source, revision = seed_repository(store)
    fact = seed_evidence(store, revision)
    tracking = make_tracking(store)
    tracking.assign_level(
        source.source_id,
        TrackingLevel.SHALLOW,
        assigned_by="operator:test",
        reason="capture only",
        effective_at=T0 + timedelta(hours=1),
    )
    service = TrackingAwareObservationConstructionService(
        store,
        tracking=tracking,
        clock=Clock(T0 + timedelta(hours=3)),
        id_factory=Ids(),
    )
    kwargs = {
        "logical_claim_id": "claim:tracked",
        "epistemic_type": ObservationEpistemicType.INTERPRETATION,
        "statement": "The repository documents a tracked mechanism.",
        "supports": (SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id),),
    }

    with pytest.raises(TrackingNotAllowed):
        service.create_candidate(**kwargs)
    assert store.list(Observation) == []

    tracking.assign_level(
        source.source_id,
        TrackingLevel.STRUCTURAL,
        assigned_by="operator:test",
        reason="eligible for source-local reasoning",
        effective_at=T0 + timedelta(hours=2),
    )
    result = service.create_candidate(**kwargs)

    assert result.source_revision_id == revision.source_revision_id
    assert result.observation.validation_state.value == "candidate"
