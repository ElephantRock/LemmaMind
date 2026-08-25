from datetime import datetime, timedelta, timezone

import pytest

from lemmamind.contracts import (
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
)
from lemmamind.extraction import (
    ArtifactContractMismatch,
    DeterministicExtractionService,
    ExtractionError,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


class IncrementingClock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        value = self.value
        self.value += timedelta(seconds=1)
        return value


class DeterministicIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"extract-{self.value}"


def build_capture(tmp_path, files: dict[str, bytes], *, missing: tuple[str, ...] = ()):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    capture_id = "capture:test"
    artifacts = []
    references = []

    for index, (path, data) in enumerate(sorted(files.items()), start=1):
        artifact_id = f"artifact:{index}"
        digest = objects.put(data)
        media_type = {
            ".md": "text/markdown",
            ".toml": "application/toml",
            ".json": "application/json",
        }.get("." + path.rsplit(".", 1)[-1] if "." in path else "", "application/octet-stream")
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=path,
            content_hash=digest,
            media_type=media_type,
        )
        artifacts.append(artifact)
        references.append(
            CaptureArtifactRef(
                artifact_id=artifact_id,
                source_locator=path,
                content_hash=digest,
                media_type=media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            )
        )

    for index, path in enumerate(sorted(missing), start=len(artifacts) + 1):
        references.append(
            CaptureArtifactRef(
                artifact_id=f"artifact:{index}",
                source_locator=path,
                retrieval_status=RetrievalStatus.MISSING,
            )
        )

    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id="github:42@" + "a" * 40,
        capture_policy_version="github.explicit-paths.v1",
        captured_at=NOW,
        artifacts=tuple(references),
    )
    store.put_many((*artifacts, manifest))
    service = DeterministicExtractionService(
        store,
        objects,
        clock=IncrementingClock(),
        id_factory=DeterministicIds(),
    )
    return store, objects, manifest, artifacts, service


def semantic_facts(result):
    return [
        (
            fact.artifact_id,
            fact.locator,
            fact.raw_value,
            fact.normalized_value,
            fact.extractor_name,
            fact.extractor_version,
        )
        for fact in result.facts
    ]


def semantic_assertions(result):
    return [
        (
            assertion.artifact_id,
            assertion.locator,
            assertion.statement,
            assertion.extractor_name,
            assertion.extractor_version,
        )
        for assertion in result.assertions
    ]


def test_extracts_manifest_path_facts_and_markdown_source_assertions(tmp_path) -> None:
    readme = b"""# Demo\n\nLemmaMind preserves exact evidence.\nThis remains the source's own claim.\n\n- list item is intentionally excluded\n\n```python\nprint('not an assertion')\n```\n\nA second explicit paragraph.\n"""
    pyproject = b"""[build-system]\nrequires = [\"wheel\", \"setuptools>=68\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[project]\nname = \"demo\"\nversion = \"1.2.3\"\nrequires-python = \">=3.11\"\ndependencies = [\"zeta>=1\", \"alpha>=2\", \"alpha>=2\"]\n\n[project.optional-dependencies]\ntest = [\"pytest\"]\ndocs = [\"mkdocs\"]\n"""
    store, _, manifest, artifacts, service = build_capture(
        tmp_path,
        {"README.md": readme, "pyproject.toml": pyproject},
    )

    result = service.extract_capture(manifest.capture_id)

    assert result.run.run_type is RunType.EXTRACTION
    assert result.run.inputs_hash.startswith("sha256:")
    assert result.run.outputs_hash is not None
    assert len(store.list(PipelineRun)) == 1

    facts_by_locator = {fact.locator: fact for fact in result.facts}
    assert facts_by_locator["pyproject.toml#project.name"].normalized_value == "demo"
    assert facts_by_locator["pyproject.toml#project.dependencies"].normalized_value == [
        "alpha>=2",
        "zeta>=1",
    ]
    assert facts_by_locator["pyproject.toml#project.optional-dependencies"].normalized_value == [
        "docs",
        "test",
    ]
    assert facts_by_locator["README.md#$path.basename"].normalized_value == "README.md"
    assert facts_by_locator["README.md#$path.path_depth"].normalized_value == 1
    assert all(fact.artifact_id in {artifact.artifact_id for artifact in artifacts} for fact in result.facts)

    assert [(item.locator, item.statement) for item in result.assertions] == [
        (
            "README.md:L3-L4",
            "LemmaMind preserves exact evidence. This remains the source's own claim.",
        ),
        ("README.md:L13-L13", "A second explicit paragraph."),
    ]
    assert len(store.list(EvidenceFact)) == len(result.facts)
    assert len(store.list(SourceAssertion)) == 2


def test_extracts_package_json_without_interpreting_dependency_meaning(tmp_path) -> None:
    package_json = b'''{
      "name": "demo-js",
      "version": "0.3.0",
      "type": "module",
      "packageManager": "pnpm@10.0.0",
      "engines": {"node": ">=22"},
      "dependencies": {"zeta": "^2", "alpha": "^1"},
      "scripts": {"test": "vitest", "build": "tsc"}
    }'''
    _, _, manifest, _, service = build_capture(tmp_path, {"package.json": package_json})

    result = service.extract_capture(manifest.capture_id)
    facts = {fact.locator: fact.normalized_value for fact in result.facts}

    assert facts["package.json#name"] == "demo-js"
    assert facts["package.json#dependencies"] == {"alpha": "^1", "zeta": "^2"}
    assert facts["package.json#scripts"] == ["build", "test"]
    assert result.assertions == ()


def test_repeat_extraction_is_semantically_deterministic(tmp_path) -> None:
    store, _, manifest, _, service = build_capture(
        tmp_path,
        {
            "README.md": b"# Heading\n\nA stable assertion.\n",
            "pyproject.toml": b"[project]\nname='stable'\n",
        },
    )

    first = service.extract_capture(manifest.capture_id)
    second = service.extract_capture(manifest.capture_id)

    assert first.run.run_id != second.run.run_id
    assert first.run.inputs_hash == second.run.inputs_hash
    assert first.run.outputs_hash == second.run.outputs_hash
    assert semantic_facts(first) == semantic_facts(second)
    assert semantic_assertions(first) == semantic_assertions(second)
    assert len(store.list(PipelineRun)) == 2


def test_missing_capture_entries_are_not_fabricated_into_artifact_facts(tmp_path) -> None:
    store, _, manifest, _, service = build_capture(tmp_path, {}, missing=("missing.md",))

    result = service.extract_capture(manifest.capture_id)

    assert result.facts == ()
    assert result.assertions == ()
    assert len(store.list(EvidenceFact)) == 0
    assert len(store.list(SourceAssertion)) == 0
    assert result.run.outputs_hash is not None


def test_captured_reference_requires_a_matching_artifact_record(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    manifest = CaptureManifest(
        capture_id="capture:broken",
        source_revision_id="github:42@" + "a" * 40,
        capture_policy_version="github.explicit-paths.v1",
        captured_at=NOW,
        artifacts=(
            CaptureArtifactRef(
                artifact_id="artifact:missing-row",
                source_locator="README.md",
                content_hash="sha256:" + "0" * 64,
                media_type="text/markdown",
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    store.put(manifest)
    service = DeterministicExtractionService(store, objects)

    with pytest.raises(ArtifactContractMismatch):
        service.extract_capture(manifest.capture_id)

    assert store.list(PipelineRun) == []
    assert store.list(EvidenceFact) == []


def test_artifact_metadata_must_match_capture_manifest(tmp_path) -> None:
    store, _, manifest, artifacts, service = build_capture(
        tmp_path,
        {"README.md": b"A claim.\n"},
    )
    artifact = artifacts[0]
    changed_manifest = CaptureManifest(
        capture_id="capture:mismatch",
        source_revision_id=manifest.source_revision_id,
        capture_policy_version=manifest.capture_policy_version,
        captured_at=NOW,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator="different.md",
                content_hash=artifact.content_hash,
                media_type=artifact.media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    store.put(changed_manifest)

    with pytest.raises(ArtifactContractMismatch):
        service.extract_capture(changed_manifest.capture_id)


def test_invalid_manifest_content_fails_closed_before_persistence(tmp_path) -> None:
    store, _, manifest, _, service = build_capture(
        tmp_path,
        {"pyproject.toml": b"[project\nname = 'broken'\n"},
    )

    with pytest.raises(ExtractionError):
        service.extract_capture(manifest.capture_id)

    assert store.list(EvidenceFact) == []
    assert store.list(SourceAssertion) == []
    assert store.list(PipelineRun) == []
