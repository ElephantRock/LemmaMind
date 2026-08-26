from datetime import datetime, timezone

from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceRevision,
)
from lemmamind.evidence_inspection import EvidenceInspectionService, InspectionLocationKind
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore


def test_json_pointer_scalar_root_locator_is_inspectable(tmp_path) -> None:
    now = datetime(2026, 8, 26, tzinfo=timezone.utc)
    store = SQLiteContractStore(tmp_path / "db.sqlite")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    revision = SourceRevision(
        source_revision_id=f"github:42@{'a' * 40}",
        source_id="github:42",
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        observed_at=now,
    )
    data = b'"root-value"\n'
    digest = objects.put(data)
    artifact = Artifact(
        artifact_id="artifact:root-json",
        capture_id="capture:root-json",
        source_locator="value.json",
        content_hash=digest,
        media_type="application/json",
    )
    manifest = CaptureManifest(
        capture_id=artifact.capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=now,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator=artifact.source_locator,
                content_hash=digest,
                media_type=artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    zero_hash = "sha256:" + "0" * 64
    run = PipelineRun(
        run_id="run:root-json",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="test.evidence.v1",
        started_at=now,
        finished_at=now,
        inputs_hash=zero_hash,
        outputs_hash=zero_hash,
    )
    fact = EvidenceFact(
        evidence_id="fact:root-json",
        artifact_id=artifact.artifact_id,
        locator="value.json#",
        raw_value="root-value",
        normalized_value="root-value",
        extractor_name="json-pointer",
        extractor_version="1",
        run_id=run.run_id,
    )
    store.put_many((revision, artifact, manifest, run, fact))

    result = EvidenceInspectionService(store, objects).inspect_fact(fact.evidence_id)

    assert result.location_kind is InspectionLocationKind.STRUCTURED_VALUE
    assert result.resolved_locator == "value.json#"
    assert result.source_value == "root-value"
