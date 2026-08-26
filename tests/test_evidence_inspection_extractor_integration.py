from datetime import datetime, timezone

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    RetrievalStatus,
    SourceRevision,
)
from lemmamind.evidence_inspection import EvidenceInspectionService
from lemmamind.extraction import DeterministicExtractionService
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore
from lemmamind.typescript_ast import typescript_aware_extractors


def test_real_source_file_extractor_surface_is_fully_inspectable(tmp_path) -> None:
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
    capture_id = "capture:extractor-integration"
    payloads = {
        "README.md": ("text/markdown", b"Ordinary paragraph.\n\n- Explicit list assertion.\n"),
        "pyproject.toml": (
            "application/toml",
            b'[project]\nname = "lemma"\nversion = "0.1"\noptional-dependencies = { test = ["pytest"] }\n',
        ),
        "package.json": (
            "application/json",
            b'{"name":"lemma","scripts":{"test":"pytest"},"dependencies":{"x":"1"}}\n',
        ),
        "sample.py": (
            "text/x-python",
            b'"""Module assertion."""\n\ndef run():\n    return helper()\n',
        ),
        "sample.ts": (
            "text/typescript",
            b'// authored assertion\nexport function run() { return helper(); }\n',
        ),
    }
    artifacts = []
    refs = []
    for index, (path, (media_type, data)) in enumerate(payloads.items(), start=1):
        digest = objects.put(data)
        artifact = Artifact(
            artifact_id=f"artifact:integration:{index}",
            capture_id=capture_id,
            source_locator=path,
            content_hash=digest,
            media_type=media_type,
        )
        artifacts.append(artifact)
        refs.append(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator=path,
                content_hash=digest,
                media_type=media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            )
        )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=now,
        artifacts=tuple(refs),
    )
    store.put_many((revision, *artifacts, manifest))

    extraction = DeterministicExtractionService(
        store,
        objects,
        artifact_extractors=typescript_aware_extractors(),
    ).extract_capture(capture_id)

    inspections = EvidenceInspectionService(store, objects).audit_all()

    assert len(inspections) == len(extraction.facts) + len(extraction.assertions)
    assert {item.record_id for item in inspections} == {
        *[fact.evidence_id for fact in extraction.facts],
        *[assertion.assertion_id for assertion in extraction.assertions],
    }
