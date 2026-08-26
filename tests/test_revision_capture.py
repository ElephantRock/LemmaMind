from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    RetrievalStatus,
    SourceRevision,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.revision_capture import (
    CaptureReconstructionError,
    CaptureReconstructionService,
    MaterialityReason,
    RevisionMaterialityError,
    RevisionMaterialityGate,
)
from lemmamind.storage import SQLiteContractStore

T0 = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
COMMIT_C = "c" * 40
TREE_A = "1" * 40
TREE_B = "2" * 40


def seed_revision(
    store: SQLiteContractStore,
    *,
    source_id: str = "github:42",
    commit_sha: str = COMMIT_A,
    tree_sha: str = TREE_A,
    observed_at: datetime = T0,
) -> SourceRevision:
    revision = SourceRevision(
        source_revision_id=f"{source_id}@{commit_sha}",
        source_id=source_id,
        commit_sha=commit_sha,
        tree_sha=tree_sha,
        observed_at=observed_at,
    )
    store.put(revision)
    return revision


def test_reconstructs_captured_and_missing_inputs_without_provider_reads(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    revision = seed_revision(store)
    data = b"# exact historical input\n"
    digest = objects.put(data)
    artifact = Artifact(
        artifact_id="artifact:readme",
        capture_id="capture:1",
        source_locator="README.md",
        content_hash=digest,
        media_type="text/markdown",
    )
    manifest = CaptureManifest(
        capture_id="capture:1",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="github.explicit-paths.v1",
        captured_at=T0 + timedelta(minutes=1),
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator=artifact.source_locator,
                content_hash=artifact.content_hash,
                media_type=artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
            CaptureArtifactRef(
                artifact_id="artifact:missing",
                source_locator="missing.md",
                retrieval_status=RetrievalStatus.MISSING,
            ),
        ),
    )
    store.put_many((artifact, manifest))

    result = CaptureReconstructionService(store, objects).reconstruct(manifest.capture_id)

    assert result.revision == revision
    assert result.manifest == manifest
    assert result.captured_bytes_by_locator() == {"README.md": data}
    assert result.artifacts[0].data == data
    assert result.artifacts[1].retrieval_status is RetrievalStatus.MISSING
    assert result.artifacts[1].data is None


def test_reconstruction_rejects_missing_artifact_row(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    revision = seed_revision(store)
    digest = objects.put(b"bytes")
    manifest = CaptureManifest(
        capture_id="capture:missing-row",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.v1",
        captured_at=T0,
        artifacts=(
            CaptureArtifactRef(
                artifact_id="artifact:not-persisted",
                source_locator="README.md",
                content_hash=digest,
                media_type="text/markdown",
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    store.put(manifest)

    with pytest.raises(CaptureReconstructionError, match="has no Artifact"):
        CaptureReconstructionService(store, objects).reconstruct(manifest.capture_id)


def test_reconstruction_rejects_manifest_artifact_metadata_disagreement(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    revision = seed_revision(store)
    digest = objects.put(b"bytes")
    artifact = Artifact(
        artifact_id="artifact:1",
        capture_id="capture:mismatch",
        source_locator="OTHER.md",
        content_hash=digest,
        media_type="text/markdown",
    )
    manifest = CaptureManifest(
        capture_id="capture:mismatch",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.v1",
        captured_at=T0,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator="README.md",
                content_hash=digest,
                media_type="text/markdown",
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    store.put_many((artifact, manifest))

    with pytest.raises(CaptureReconstructionError, match="metadata disagreement"):
        CaptureReconstructionService(store, objects).reconstruct(manifest.capture_id)


def test_reconstruction_rejects_unmanifested_artifact_row(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    revision = seed_revision(store)
    digest = objects.put(b"bytes")
    artifact = Artifact(
        artifact_id="artifact:extra",
        capture_id="capture:extra",
        source_locator="README.md",
        content_hash=digest,
        media_type="text/markdown",
    )
    manifest = CaptureManifest(
        capture_id="capture:extra",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.v1",
        captured_at=T0,
        artifacts=(),
    )
    store.put_many((artifact, manifest))

    with pytest.raises(CaptureReconstructionError, match="set disagreement"):
        CaptureReconstructionService(store, objects).reconstruct(manifest.capture_id)


def test_reconstruction_fails_closed_when_object_bytes_are_missing(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    revision = seed_revision(store)
    data = b"bytes"
    digest = objects.digest(data)
    artifact = Artifact(
        artifact_id="artifact:no-object",
        capture_id="capture:no-object",
        source_locator="README.md",
        content_hash=digest,
        media_type="text/markdown",
    )
    manifest = CaptureManifest(
        capture_id="capture:no-object",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.v1",
        captured_at=T0,
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
    store.put_many((artifact, manifest))

    with pytest.raises(CaptureReconstructionError, match="local object cannot satisfy"):
        CaptureReconstructionService(store, objects).reconstruct(manifest.capture_id)


def test_reconstruction_rejects_non_reconstructable_status(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    revision = seed_revision(store)
    manifest = CaptureManifest(
        capture_id="capture:error-status",
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.v1",
        captured_at=T0,
        artifacts=(
            CaptureArtifactRef(
                artifact_id="artifact:error",
                source_locator="README.md",
                retrieval_status=RetrievalStatus.ERROR,
            ),
        ),
    )
    store.put(manifest)

    with pytest.raises(CaptureReconstructionError, match="cannot reconstruct"):
        CaptureReconstructionService(store, objects).reconstruct(manifest.capture_id)


@pytest.mark.parametrize(
    ("current_commit", "current_tree", "material", "reason"),
    [
        (COMMIT_A, TREE_A, False, MaterialityReason.SAME_REVISION),
        (COMMIT_B, TREE_A, False, MaterialityReason.TREE_UNCHANGED),
        (COMMIT_C, TREE_B, True, MaterialityReason.TREE_CHANGED),
    ],
)
def test_revision_materiality_is_tree_based_and_non_semantic(
    tmp_path,
    current_commit,
    current_tree,
    material,
    reason,
) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    previous = seed_revision(store)
    if current_commit == COMMIT_A:
        current = previous
    else:
        current = seed_revision(
            store,
            commit_sha=current_commit,
            tree_sha=current_tree,
            observed_at=T0 + timedelta(minutes=1),
        )

    result = RevisionMaterialityGate(store).assess(
        previous.source_revision_id,
        current.source_revision_id,
    )

    assert result.material is material
    assert result.reason is reason
    assert result.source_id == previous.source_id


def test_revision_materiality_rejects_cross_source_comparison(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    previous = seed_revision(store, source_id="github:42")
    current = seed_revision(
        store,
        source_id="github:99",
        commit_sha=COMMIT_B,
        tree_sha=TREE_B,
        observed_at=T0 + timedelta(minutes=1),
    )

    with pytest.raises(RevisionMaterialityError, match="same Source"):
        RevisionMaterialityGate(store).assess(
            previous.source_revision_id,
            current.source_revision_id,
        )
