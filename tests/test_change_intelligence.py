from datetime import datetime, timedelta, timezone
import json

import pytest

from lemmamind.change_contracts import (
    ArtifactDelta,
    ArtifactDeltaType,
    StructuralDelta,
    StructuralDeltaType,
)
from lemmamind.change_intelligence import (
    ChangeIntelligenceError,
    DeterminismViolation,
    DeterministicChangeService,
)
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
from lemmamind.extraction import DeterministicExtractionService
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

T0 = datetime(2026, 8, 26, 1, 0, tzinfo=timezone.utc)
SOURCE_ID = "github:42"


def seed_revision(
    store: SQLiteContractStore,
    *,
    source_id: str = SOURCE_ID,
    suffix: str,
    observed_at: datetime,
) -> SourceRevision:
    revision = SourceRevision(
        source_revision_id=f"{source_id}@{'a' * 39}{suffix}",
        source_id=source_id,
        commit_sha=("a" * 39) + suffix,
        tree_sha=("1" * 39) + suffix,
        observed_at=observed_at,
    )
    store.put(revision)
    return revision


def media_type(path: str) -> str:
    if path.endswith(".md"):
        return "text/markdown"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".toml"):
        return "application/toml"
    return "text/plain"


def seed_capture(
    store: SQLiteContractStore,
    objects: ContentAddressedFileStore,
    revision: SourceRevision,
    capture_id: str,
    entries: dict[str, bytes | None],
    *,
    captured_at: datetime | None = None,
) -> CaptureManifest:
    artifacts = []
    refs = []
    for index, (path, data) in enumerate(entries.items(), start=1):
        artifact_id = f"artifact:{capture_id}:{index}"
        if data is None:
            refs.append(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=path,
                    retrieval_status=RetrievalStatus.MISSING,
                )
            )
            continue
        digest = objects.put(data)
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=path,
            content_hash=digest,
            media_type=media_type(path),
        )
        artifacts.append(artifact)
        refs.append(
            CaptureArtifactRef(
                artifact_id=artifact_id,
                source_locator=path,
                content_hash=digest,
                media_type=artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            )
        )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=captured_at or (revision.observed_at + timedelta(seconds=1)),
        artifacts=tuple(refs),
    )
    store.put_many((*artifacts, manifest))
    return manifest


def seed_manual_extraction(
    store: SQLiteContractStore,
    *,
    run_id: str,
    artifact_id: str,
    locator: str,
    value: object,
    code_version: str = "lemmamind-0.1.0",
    policy_version: str = "deterministic-evidence.v1",
) -> PipelineRun:
    run = PipelineRun(
        run_id=run_id,
        run_type=RunType.EXTRACTION,
        code_version=code_version,
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version=policy_version,
        started_at=T0,
        finished_at=T0 + timedelta(seconds=1),
        inputs_hash="sha256:" + "1" * 64,
        outputs_hash="sha256:" + "2" * 64,
    )
    fact = EvidenceFact(
        evidence_id=f"evidence:{run_id}",
        artifact_id=artifact_id,
        locator=locator,
        raw_value=value,
        normalized_value=value,
        extractor_name="manual-test",
        extractor_version="1",
        run_id=run_id,
    )
    store.put_many((fact, run))
    return run


def test_artifact_delta_distinguishes_scope_availability_and_content(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_revision = seed_revision(store, suffix="a", observed_at=T0)
    current_revision = seed_revision(
        store, suffix="b", observed_at=T0 + timedelta(minutes=1)
    )
    seed_capture(
        store,
        objects,
        previous_revision,
        "capture:previous",
        {
            "README.md": b"old\n",
            "appears.md": None,
            "disappears.md": b"present\n",
            "old-scope.txt": b"scope\n",
        },
    )
    seed_capture(
        store,
        objects,
        current_revision,
        "capture:current",
        {
            "README.md": b"new\n",
            "appears.md": b"now present\n",
            "disappears.md": None,
            "new-scope.txt": b"scope\n",
        },
    )

    result = DeterministicChangeService(
        store,
        objects,
        id_factory=lambda: "artifact-diff",
        clock=lambda: T0 + timedelta(minutes=2),
    ).compare_captures("capture:previous", "capture:current")

    by_locator = {item.source_locator: item.change_type for item in result.artifact_deltas}
    assert by_locator == {
        "README.md": ArtifactDeltaType.CONTENT_CHANGED,
        "appears.md": ArtifactDeltaType.BECAME_CAPTURED,
        "disappears.md": ArtifactDeltaType.BECAME_MISSING,
        "new-scope.txt": ArtifactDeltaType.CAPTURE_SCOPE_ADDED,
        "old-scope.txt": ArtifactDeltaType.CAPTURE_SCOPE_REMOVED,
    }
    assert result.structural_deltas == ()
    assert result.run.run_type is RunType.DIFF
    assert len(store.list(ArtifactDelta)) == 5


def test_real_extractor_generations_produce_add_remove_and_modify_deltas(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_revision = seed_revision(store, suffix="a", observed_at=T0)
    current_revision = seed_revision(
        store, suffix="b", observed_at=T0 + timedelta(minutes=1)
    )
    previous_package = json.dumps(
        {
            "name": "demo",
            "dependencies": {"alpha": "^1"},
            "scripts": {"test": "pytest"},
            "engines": {"node": ">=20"},
        },
        separators=(",", ":"),
    ).encode()
    current_package = json.dumps(
        {
            "name": "demo",
            "dependencies": {"alpha": "^2"},
            "scripts": {"build": "tsc", "test": "pytest"},
            "packageManager": "pnpm@10",
        },
        separators=(",", ":"),
    ).encode()
    seed_capture(
        store,
        objects,
        previous_revision,
        "capture:previous",
        {"package.json": previous_package},
    )
    seed_capture(
        store,
        objects,
        current_revision,
        "capture:current",
        {"package.json": current_package},
    )
    extraction = DeterministicExtractionService(
        store,
        objects,
        clock=lambda: T0 + timedelta(minutes=2),
    )
    previous_extract = extraction.extract_capture("capture:previous")
    current_extract = extraction.extract_capture("capture:current")

    result = DeterministicChangeService(
        store,
        objects,
        id_factory=lambda: "structural-diff",
        clock=lambda: T0 + timedelta(minutes=3),
    ).compare_captures(
        "capture:previous",
        "capture:current",
        previous_extraction_run_id=previous_extract.run.run_id,
        current_extraction_run_id=current_extract.run.run_id,
    )

    assert [item.change_type for item in result.artifact_deltas] == [
        ArtifactDeltaType.CONTENT_CHANGED
    ]
    structural = {item.structural_key: item for item in result.structural_deltas}
    assert set(structural) == {
        "package-json@1:#dependencies",
        "package-json@1:#engines",
        "package-json@1:#packageManager",
        "package-json@1:#scripts",
    }
    assert structural["package-json@1:#dependencies"].change_type is StructuralDeltaType.MODIFIED
    assert structural["package-json@1:#scripts"].change_type is StructuralDeltaType.MODIFIED
    assert structural["package-json@1:#engines"].change_type is StructuralDeltaType.REMOVED
    assert structural["package-json@1:#packageManager"].change_type is StructuralDeltaType.ADDED
    assert structural["package-json@1:#dependencies"].previous_value == {"alpha": "^1"}
    assert structural["package-json@1:#dependencies"].current_value == {"alpha": "^2"}
    assert structural["package-json@1:#scripts"].previous_value == ["test"]
    assert structural["package-json@1:#scripts"].current_value == ["build", "test"]
    assert structural["package-json@1:#engines"].current_evidence_id is None
    assert structural["package-json@1:#packageManager"].previous_evidence_id is None
    assert len(store.list(StructuralDelta)) == 4


def test_normalized_structure_suppresses_formatting_only_artifact_churn(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_revision = seed_revision(store, suffix="a", observed_at=T0)
    current_revision = seed_revision(
        store, suffix="b", observed_at=T0 + timedelta(minutes=1)
    )
    document = {"name": "demo", "dependencies": {"alpha": "^1"}}
    seed_capture(
        store,
        objects,
        previous_revision,
        "capture:previous",
        {"package.json": json.dumps(document, separators=(",", ":")).encode()},
    )
    seed_capture(
        store,
        objects,
        current_revision,
        "capture:current",
        {"package.json": (json.dumps(document, indent=2) + "\n").encode()},
    )
    extraction = DeterministicExtractionService(store, objects, clock=lambda: T0)
    previous_extract = extraction.extract_capture("capture:previous")
    current_extract = extraction.extract_capture("capture:current")

    result = DeterministicChangeService(
        store,
        objects,
        id_factory=lambda: "format-diff",
        clock=lambda: T0 + timedelta(minutes=3),
    ).compare_captures(
        "capture:previous",
        "capture:current",
        previous_extraction_run_id=previous_extract.run.run_id,
        current_extraction_run_id=current_extract.run.run_id,
    )

    assert len(result.artifact_deltas) == 1
    assert result.artifact_deltas[0].change_type is ArtifactDeltaType.CONTENT_CHANGED
    assert result.structural_deltas == ()


def test_capture_scope_only_evidence_is_not_promoted_to_source_structure_change(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_revision = seed_revision(store, suffix="a", observed_at=T0)
    current_revision = seed_revision(
        store, suffix="b", observed_at=T0 + timedelta(minutes=1)
    )
    package = b'{"name":"demo"}\n'
    seed_capture(
        store,
        objects,
        previous_revision,
        "capture:previous",
        {"package.json": package},
    )
    seed_capture(
        store,
        objects,
        current_revision,
        "capture:current",
        {"package.json": package, "new.md": b"New source assertion.\n"},
    )
    extraction = DeterministicExtractionService(store, objects, clock=lambda: T0)
    previous_extract = extraction.extract_capture("capture:previous")
    current_extract = extraction.extract_capture("capture:current")

    result = DeterministicChangeService(
        store,
        objects,
        id_factory=lambda: "scope-diff",
        clock=lambda: T0 + timedelta(minutes=3),
    ).compare_captures(
        "capture:previous",
        "capture:current",
        previous_extraction_run_id=previous_extract.run.run_id,
        current_extraction_run_id=current_extract.run.run_id,
    )

    assert len(result.artifact_deltas) == 1
    assert result.artifact_deltas[0].source_locator == "new.md"
    assert result.artifact_deltas[0].change_type is ArtifactDeltaType.CAPTURE_SCOPE_ADDED
    assert result.structural_deltas == ()


def test_identical_capture_state_with_different_facts_is_determinism_violation(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_revision = seed_revision(store, suffix="a", observed_at=T0)
    current_revision = seed_revision(
        store, suffix="b", observed_at=T0 + timedelta(minutes=1)
    )
    data = b'{"name":"demo"}\n'
    previous_manifest = seed_capture(
        store,
        objects,
        previous_revision,
        "capture:previous",
        {"package.json": data},
    )
    current_manifest = seed_capture(
        store,
        objects,
        current_revision,
        "capture:current",
        {"package.json": data},
    )
    seed_manual_extraction(
        store,
        run_id="run:previous-extract",
        artifact_id=previous_manifest.artifacts[0].artifact_id,
        locator="package.json#/name",
        value="demo",
    )
    seed_manual_extraction(
        store,
        run_id="run:current-extract",
        artifact_id=current_manifest.artifacts[0].artifact_id,
        locator="package.json#/name",
        value="different",
    )

    with pytest.raises(DeterminismViolation, match="without an ArtifactDelta"):
        DeterministicChangeService(
            store,
            objects,
            id_factory=lambda: "bad-diff",
            clock=lambda: T0 + timedelta(minutes=3),
        ).compare_captures(
            "capture:previous",
            "capture:current",
            previous_extraction_run_id="run:previous-extract",
            current_extraction_run_id="run:current-extract",
        )


def test_structural_comparison_rejects_extractor_generation_drift(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_revision = seed_revision(store, suffix="a", observed_at=T0)
    current_revision = seed_revision(
        store, suffix="b", observed_at=T0 + timedelta(minutes=1)
    )
    previous_manifest = seed_capture(
        store,
        objects,
        previous_revision,
        "capture:previous",
        {"package.json": b'{"name":"old"}\n'},
    )
    current_manifest = seed_capture(
        store,
        objects,
        current_revision,
        "capture:current",
        {"package.json": b'{"name":"new"}\n'},
    )
    seed_manual_extraction(
        store,
        run_id="run:previous-extract",
        artifact_id=previous_manifest.artifacts[0].artifact_id,
        locator="package.json#/name",
        value="old",
        code_version="extractor-a",
    )
    seed_manual_extraction(
        store,
        run_id="run:current-extract",
        artifact_id=current_manifest.artifacts[0].artifact_id,
        locator="package.json#/name",
        value="new",
        code_version="extractor-b",
    )

    with pytest.raises(ChangeIntelligenceError, match="matching deterministic extraction"):
        DeterministicChangeService(
            store,
            objects,
            id_factory=lambda: "generation-diff",
            clock=lambda: T0 + timedelta(minutes=3),
        ).compare_captures(
            "capture:previous",
            "capture:current",
            previous_extraction_run_id="run:previous-extract",
            current_extraction_run_id="run:current-extract",
        )


def test_change_comparison_rejects_cross_source_revision_and_capture_time_reversal(
    tmp_path,
) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    early = seed_revision(store, suffix="a", observed_at=T0)
    late = seed_revision(store, suffix="b", observed_at=T0 + timedelta(minutes=1))
    other = seed_revision(
        store,
        source_id="github:99",
        suffix="c",
        observed_at=T0 + timedelta(minutes=2),
    )
    seed_capture(store, objects, early, "capture:early", {"README.md": b"a\n"})
    seed_capture(store, objects, late, "capture:late", {"README.md": b"b\n"})
    seed_capture(store, objects, other, "capture:other", {"README.md": b"c\n"})
    service = DeterministicChangeService(
        store,
        objects,
        id_factory=lambda: "guard-diff",
        clock=lambda: T0 + timedelta(minutes=3),
    )

    with pytest.raises(ChangeIntelligenceError, match="same Source"):
        service.compare_captures("capture:early", "capture:other")
    with pytest.raises(ChangeIntelligenceError, match="SourceRevision"):
        service.compare_captures("capture:late", "capture:early")

    same_revision = seed_revision(
        store, suffix="d", observed_at=T0 + timedelta(minutes=4)
    )
    seed_capture(
        store,
        objects,
        same_revision,
        "capture:newer",
        {"README.md": b"newer\n"},
        captured_at=T0 + timedelta(minutes=6),
    )
    seed_capture(
        store,
        objects,
        same_revision,
        "capture:older",
        {"README.md": b"older\n"},
        captured_at=T0 + timedelta(minutes=5),
    )
    with pytest.raises(ChangeIntelligenceError, match="CaptureManifest"):
        service.compare_captures("capture:newer", "capture:older")


def test_change_contracts_are_available_through_generic_store_registry(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    previous_revision = seed_revision(store, suffix="a", observed_at=T0)
    current_revision = seed_revision(
        store, suffix="b", observed_at=T0 + timedelta(minutes=1)
    )
    seed_capture(store, objects, previous_revision, "capture:previous", {"x.txt": b"a"})
    seed_capture(store, objects, current_revision, "capture:current", {"x.txt": b"b"})

    result = DeterministicChangeService(
        store,
        objects,
        id_factory=lambda: "registry-diff",
        clock=lambda: T0 + timedelta(minutes=2),
    ).compare_captures("capture:previous", "capture:current")

    delta = result.artifact_deltas[0]
    assert store.get_untyped("ArtifactDelta", delta.artifact_delta_id) == delta
