"""M3 local reconstruction and deterministic revision materiality.

M3 separates exact upstream Git state (``SourceRevision``) from the exact local
analysis inputs retained in ``CaptureManifest`` / ``Artifact`` records and the
content-addressed object store.

This module deliberately does not interpret change significance.  The materiality
gate answers only whether repository tree content changed; semantic/structural
change intelligence belongs to M5.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .contracts import Artifact, CaptureManifest, RetrievalStatus, SourceRevision
from .objects import ContentAddressedFileStore


class CaptureReconstructionError(RuntimeError):
    """Persisted capture records cannot reconstruct one exact local input set."""


class RevisionMaterialityError(RuntimeError):
    """Revision materiality cannot be evaluated under the M3 source-local contract."""


class MaterialityReason(StrEnum):
    SAME_REVISION = "same_revision"
    TREE_UNCHANGED = "tree_unchanged"
    TREE_CHANGED = "tree_changed"


@dataclass(frozen=True)
class ReconstructedArtifact:
    artifact_id: str
    source_locator: str
    retrieval_status: RetrievalStatus
    content_hash: str | None
    media_type: str | None
    data: bytes | None

    @property
    def is_captured(self) -> bool:
        return self.retrieval_status is RetrievalStatus.CAPTURED


@dataclass(frozen=True)
class ReconstructedCapture:
    revision: SourceRevision
    manifest: CaptureManifest
    artifacts: tuple[ReconstructedArtifact, ...]

    def captured_bytes_by_locator(self) -> dict[str, bytes]:
        """Return exact captured bytes keyed by unique source locator."""

        return {
            item.source_locator: item.data
            for item in self.artifacts
            if item.is_captured and item.data is not None
        }


@dataclass(frozen=True)
class RevisionMateriality:
    source_id: str
    previous_source_revision_id: str
    current_source_revision_id: str
    material: bool
    reason: MaterialityReason


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...


class CaptureReconstructionService:
    """Reconstruct one historical capture entirely from local durable state.

    The service performs no provider reads.  It verifies that the manifest,
    Artifact rows, and content-addressed bytes form one exact closed set before
    returning any input bytes.
    """

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
    ) -> None:
        self.store = store
        self.object_store = object_store

    def reconstruct(self, capture_id: str) -> ReconstructedCapture:
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise CaptureReconstructionError(f"unknown CaptureManifest: {capture_id}")

        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise CaptureReconstructionError(
                "CaptureManifest references missing SourceRevision: "
                f"{manifest.source_revision_id}"
            )

        artifact_ids: set[str] = set()
        source_locators: set[str] = set()
        reconstructed: list[ReconstructedArtifact] = []
        expected_persisted_artifact_ids: set[str] = set()

        for ref in manifest.artifacts:
            if ref.artifact_id in artifact_ids:
                raise CaptureReconstructionError(
                    f"CaptureManifest repeats artifact_id: {ref.artifact_id}"
                )
            if ref.source_locator in source_locators:
                raise CaptureReconstructionError(
                    f"CaptureManifest repeats source_locator: {ref.source_locator}"
                )
            artifact_ids.add(ref.artifact_id)
            source_locators.add(ref.source_locator)

            if ref.retrieval_status is RetrievalStatus.CAPTURED:
                artifact = self.store.get(Artifact, ref.artifact_id)
                if artifact is None:
                    raise CaptureReconstructionError(
                        f"captured manifest ref has no Artifact: {ref.artifact_id}"
                    )
                self._require_artifact_match(manifest, ref, artifact)
                expected_persisted_artifact_ids.add(artifact.artifact_id)
                data = self.object_store.get(artifact.content_hash)
                reconstructed.append(
                    ReconstructedArtifact(
                        artifact_id=artifact.artifact_id,
                        source_locator=artifact.source_locator,
                        retrieval_status=ref.retrieval_status,
                        content_hash=artifact.content_hash,
                        media_type=artifact.media_type,
                        data=data,
                    )
                )
                continue

            if ref.retrieval_status is RetrievalStatus.MISSING:
                artifact = self.store.get(Artifact, ref.artifact_id)
                if artifact is not None:
                    raise CaptureReconstructionError(
                        "missing manifest ref unexpectedly has an Artifact: "
                        f"{ref.artifact_id}"
                    )
                if ref.content_hash is not None or ref.media_type is not None:
                    raise CaptureReconstructionError(
                        "missing manifest ref must not claim captured content metadata: "
                        f"{ref.artifact_id}"
                    )
                reconstructed.append(
                    ReconstructedArtifact(
                        artifact_id=ref.artifact_id,
                        source_locator=ref.source_locator,
                        retrieval_status=ref.retrieval_status,
                        content_hash=None,
                        media_type=None,
                        data=None,
                    )
                )
                continue

            raise CaptureReconstructionError(
                "retrieval status cannot reconstruct exact historical bytes under M3 v1: "
                f"{ref.retrieval_status.value} for {ref.artifact_id}"
            )

        persisted_artifact_ids = {
            artifact.artifact_id
            for artifact in self.store.list(Artifact)
            if artifact.capture_id == manifest.capture_id
        }
        if persisted_artifact_ids != expected_persisted_artifact_ids:
            extras = sorted(persisted_artifact_ids - expected_persisted_artifact_ids)
            missing = sorted(expected_persisted_artifact_ids - persisted_artifact_ids)
            raise CaptureReconstructionError(
                "CaptureManifest/Artifact set disagreement for "
                f"{capture_id}; extras={extras}, missing={missing}"
            )

        return ReconstructedCapture(
            revision=revision,
            manifest=manifest,
            artifacts=tuple(reconstructed),
        )

    @staticmethod
    def _require_artifact_match(manifest, ref, artifact: Artifact) -> None:
        if artifact.capture_id != manifest.capture_id:
            raise CaptureReconstructionError(
                f"Artifact belongs to another capture: {artifact.artifact_id}"
            )
        expected = (ref.source_locator, ref.content_hash, ref.media_type)
        actual = (artifact.source_locator, artifact.content_hash, artifact.media_type)
        if actual != expected:
            raise CaptureReconstructionError(
                "CaptureManifest/Artifact metadata disagreement for "
                f"{artifact.artifact_id}"
            )


class RevisionMaterialityGate:
    """Cheap M3 gate over immutable Git revision identity and root-tree content.

    ``material=True`` means only that repository tree content changed and later
    analysis is eligible.  It is not a claim that the change is meaningful.
    """

    def __init__(self, store: ContractStore) -> None:
        self.store = store

    def assess(
        self,
        previous_source_revision_id: str,
        current_source_revision_id: str,
    ) -> RevisionMateriality:
        previous = self._revision(previous_source_revision_id)
        current = self._revision(current_source_revision_id)
        if previous.source_id != current.source_id:
            raise RevisionMaterialityError(
                "M3 materiality comparison requires revisions of the same Source"
            )

        if previous.commit_sha == current.commit_sha:
            reason = MaterialityReason.SAME_REVISION
            material = False
        elif previous.tree_sha == current.tree_sha:
            reason = MaterialityReason.TREE_UNCHANGED
            material = False
        else:
            reason = MaterialityReason.TREE_CHANGED
            material = True

        return RevisionMateriality(
            source_id=current.source_id,
            previous_source_revision_id=previous.source_revision_id,
            current_source_revision_id=current.source_revision_id,
            material=material,
            reason=reason,
        )

    def _revision(self, source_revision_id: str) -> SourceRevision:
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise RevisionMaterialityError(
                f"unknown SourceRevision: {source_revision_id}"
            )
        return revision
