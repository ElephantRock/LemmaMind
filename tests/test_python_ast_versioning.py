from datetime import datetime, timezone

from lemmamind.contracts import Artifact, CaptureArtifactRef, CaptureManifest, RetrievalStatus
from lemmamind.extraction import DeterministicExtractionService
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.python_ast import PythonAstExtractor
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_docstring_canonicalization_is_bound_to_python_ast_v2(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source = b'''def configured():
    """
    Preserve the semantic statement.

    Do not retain incidental outer whitespace.
    """
    return True
'''
    digest = objects.put(source)
    artifact = Artifact(
        artifact_id="artifact:python-version",
        capture_id="capture:python-version",
        source_locator="configured.py",
        content_hash=digest,
        media_type="text/x-python",
    )
    manifest = CaptureManifest(
        capture_id=artifact.capture_id,
        source_revision_id="github:42@" + "a" * 40,
        capture_policy_version="github.explicit-paths.v1",
        captured_at=NOW,
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
    store.put_many((artifact, manifest))

    extractor = PythonAstExtractor()
    service = DeterministicExtractionService(
        store,
        objects,
        artifact_extractors=(extractor,),
        clock=lambda: NOW,
        id_factory=lambda: "python-version",
    )
    result = service.extract_capture(manifest.capture_id)

    v2_inputs_hash = service._digest_json(
        {
            "capture_manifest": manifest.model_dump(mode="json", by_alias=True),
            "artifact_extractors": [{"name": "python-ast", "version": "2"}],
            "policy_version": "deterministic-evidence.v1",
        }
    )
    legacy_v1_inputs_hash = service._digest_json(
        {
            "capture_manifest": manifest.model_dump(mode="json", by_alias=True),
            "artifact_extractors": [{"name": "python-ast", "version": "1"}],
            "policy_version": "deterministic-evidence.v1",
        }
    )

    assert extractor.version == "2"
    assert result.run.inputs_hash == v2_inputs_hash
    assert result.run.inputs_hash != legacy_v1_inputs_hash
    assert result.facts
    assert all(fact.extractor_version == "2" for fact in result.facts)
    assert len(result.assertions) == 1
    assert result.assertions[0].extractor_name == "python-docstring"
    assert result.assertions[0].extractor_version == "2"
    assert result.assertions[0].statement == result.assertions[0].statement.strip()
