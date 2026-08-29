"""Durable M5-lite deterministic change contracts.

ArtifactDelta records exact differences between two locally reconstructable capture
manifests. StructuralDelta records normalized EvidenceFact differences over one
explicitly compatible extraction generation. Neither contract carries semantic
significance or ChangeInterpretation.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import JsonValue, model_validator

from .contracts import (
    CONTRACT_TYPES,
    ContentDigest,
    ContractModel,
    Identifier,
    RetrievalStatus,
    SourceLocator,
)


class ArtifactDeltaType(StrEnum):
    CAPTURE_SCOPE_ADDED = "capture_scope_added"
    CAPTURE_SCOPE_REMOVED = "capture_scope_removed"
    BECAME_CAPTURED = "became_captured"
    BECAME_MISSING = "became_missing"
    CONTENT_CHANGED = "content_changed"
    METADATA_CHANGED = "metadata_changed"


class StructuralDeltaType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class ArtifactDelta(ContractModel):
    """One factual source-locator delta between two exact capture manifests."""

    record_id_field = "artifact_delta_id"

    artifact_delta_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    previous_capture_id: Identifier
    current_capture_id: Identifier
    source_locator: SourceLocator
    change_type: ArtifactDeltaType

    previous_artifact_id: Identifier | None = None
    current_artifact_id: Identifier | None = None
    previous_retrieval_status: RetrievalStatus | None = None
    current_retrieval_status: RetrievalStatus | None = None
    previous_content_hash: ContentDigest | None = None
    current_content_hash: ContentDigest | None = None
    previous_media_type: Identifier | None = None
    current_media_type: Identifier | None = None
    diff_run_id: Identifier

    @model_validator(mode="after")
    def validate_transition(self) -> "ArtifactDelta":
        previous_present = self.previous_retrieval_status is not None
        current_present = self.current_retrieval_status is not None

        if self.change_type is ArtifactDeltaType.CAPTURE_SCOPE_ADDED:
            if previous_present or not current_present:
                raise ValueError("capture_scope_added requires only current manifest state")
        elif self.change_type is ArtifactDeltaType.CAPTURE_SCOPE_REMOVED:
            if not previous_present or current_present:
                raise ValueError("capture_scope_removed requires only previous manifest state")
        elif self.change_type is ArtifactDeltaType.BECAME_CAPTURED:
            if (
                self.previous_retrieval_status is not RetrievalStatus.MISSING
                or self.current_retrieval_status is not RetrievalStatus.CAPTURED
            ):
                raise ValueError("became_captured requires MISSING -> CAPTURED")
        elif self.change_type is ArtifactDeltaType.BECAME_MISSING:
            if (
                self.previous_retrieval_status is not RetrievalStatus.CAPTURED
                or self.current_retrieval_status is not RetrievalStatus.MISSING
            ):
                raise ValueError("became_missing requires CAPTURED -> MISSING")
        elif self.change_type is ArtifactDeltaType.CONTENT_CHANGED:
            if (
                self.previous_retrieval_status is not RetrievalStatus.CAPTURED
                or self.current_retrieval_status is not RetrievalStatus.CAPTURED
                or self.previous_content_hash == self.current_content_hash
            ):
                raise ValueError("content_changed requires two captured unequal content hashes")
        elif self.change_type is ArtifactDeltaType.METADATA_CHANGED:
            if (
                self.previous_retrieval_status is not RetrievalStatus.CAPTURED
                or self.current_retrieval_status is not RetrievalStatus.CAPTURED
                or self.previous_content_hash != self.current_content_hash
                or self.previous_media_type == self.current_media_type
            ):
                raise ValueError(
                    "metadata_changed requires equal captured bytes and changed media type"
                )

        for status, content_hash, media_type, side in (
            (
                self.previous_retrieval_status,
                self.previous_content_hash,
                self.previous_media_type,
                "previous",
            ),
            (
                self.current_retrieval_status,
                self.current_content_hash,
                self.current_media_type,
                "current",
            ),
        ):
            if status is RetrievalStatus.CAPTURED:
                if content_hash is None or media_type is None:
                    raise ValueError(f"{side} captured state requires content metadata")
            elif status is RetrievalStatus.MISSING:
                if content_hash is not None or media_type is not None:
                    raise ValueError(f"{side} missing state cannot carry content metadata")
            elif status is not None:
                raise ValueError(
                    f"M5-lite only compares reconstructable CAPTURED/MISSING state: {side}"
                )

        return self


class StructuralDelta(ContractModel):
    """One normalized EvidenceFact delta tied to an ArtifactDelta."""

    record_id_field = "structural_delta_id"

    structural_delta_id: Identifier
    artifact_delta_id: Identifier
    source_id: Identifier
    previous_source_revision_id: Identifier
    current_source_revision_id: Identifier
    source_locator: SourceLocator
    structural_key: Identifier
    change_type: StructuralDeltaType
    extractor_name: Identifier
    extractor_version: Identifier

    previous_evidence_id: Identifier | None = None
    current_evidence_id: Identifier | None = None
    previous_locator: SourceLocator | None = None
    current_locator: SourceLocator | None = None
    previous_value: JsonValue | None = None
    current_value: JsonValue | None = None
    diff_run_id: Identifier

    @model_validator(mode="after")
    def validate_transition(self) -> "StructuralDelta":
        previous_present = self.previous_evidence_id is not None
        current_present = self.current_evidence_id is not None

        if self.change_type is StructuralDeltaType.ADDED:
            if previous_present or not current_present:
                raise ValueError("added structural delta requires only current evidence")
        elif self.change_type is StructuralDeltaType.REMOVED:
            if not previous_present or current_present:
                raise ValueError("removed structural delta requires only previous evidence")
        elif self.change_type is StructuralDeltaType.MODIFIED:
            if not previous_present or not current_present:
                raise ValueError("modified structural delta requires evidence on both sides")
            if self.previous_value == self.current_value:
                raise ValueError("modified structural delta requires unequal normalized values")

        if previous_present != (self.previous_locator is not None):
            raise ValueError("previous evidence and locator presence must agree")
        if current_present != (self.current_locator is not None):
            raise ValueError("current evidence and locator presence must agree")
        return self


# Milestone-local contracts remain additive to the generic typed persistence registry.
CONTRACT_TYPES[ArtifactDelta.__name__] = ArtifactDelta
CONTRACT_TYPES[StructuralDelta.__name__] = StructuralDelta

CHANGE_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    ArtifactDelta.__name__: ArtifactDelta,
    StructuralDelta.__name__: StructuralDelta,
}
