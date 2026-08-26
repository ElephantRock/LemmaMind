from datetime import datetime, timezone
import json

import pytest

from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
    SourceRevision,
)
from lemmamind.evidence_inspection import (
    EvidenceInspectionError,
    EvidenceInspectionService,
    InspectionLocationKind,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

T0 = datetime(2026, 8, 26, tzinfo=timezone.utc)
DIGEST = "sha256:" + "0" * 64


def seed_artifact(tmp_path, *, source_locator, media_type, data, suffix="1"):
    store = SQLiteContractStore(tmp_path / f"{suffix}.db")
    objects = ContentAddressedFileStore(tmp_path / f"objects-{suffix}")
    revision = SourceRevision(
        source_revision_id=f"github:42@{'a' * 40}",
        source_id="github:42",
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        observed_at=T0,
    )
    content_hash = objects.put(data)
    capture_id = f"capture:{suffix}"
    artifact = Artifact(
        artifact_id=f"artifact:{suffix}",
        capture_id=capture_id,
        source_locator=source_locator,
        content_hash=content_hash,
        media_type=media_type,
    )
    manifest = CaptureManifest(
        capture_id=capture_id,
        source_revision_id=revision.source_revision_id,
        capture_policy_version="test.capture.v1",
        captured_at=T0,
        artifacts=(
            CaptureArtifactRef(
                artifact_id=artifact.artifact_id,
                source_locator=source_locator,
                content_hash=content_hash,
                media_type=media_type,
                retrieval_status=RetrievalStatus.CAPTURED,
            ),
        ),
    )
    run = PipelineRun(
        run_id=f"run:{suffix}",
        run_type=RunType.EXTRACTION,
        code_version="test",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version="test.evidence.v1",
        started_at=T0,
        finished_at=T0,
        inputs_hash=DIGEST,
        outputs_hash=DIGEST,
    )
    store.put_many((revision, artifact, manifest, run))
    return store, objects, artifact, run


def add_fact(store, artifact, run, *, evidence_id, locator, value):
    fact = EvidenceFact(
        evidence_id=evidence_id,
        artifact_id=artifact.artifact_id,
        locator=locator,
        raw_value=value,
        normalized_value=value,
        extractor_name="test",
        extractor_version="1",
        run_id=run.run_id,
    )
    store.put(fact)
    return fact


def add_assertion(store, artifact, run, *, assertion_id, locator, statement):
    assertion = SourceAssertion(
        assertion_id=assertion_id,
        artifact_id=artifact.artifact_id,
        locator=locator,
        statement=statement,
        extractor_name="test",
        extractor_version="1",
        run_id=run.run_id,
    )
    store.put(assertion)
    return assertion


def test_resolves_markdown_line_range_to_exact_retained_text(tmp_path) -> None:
    data = b"first\nsecond line\nthird\n"
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="README.md",
        media_type="text/markdown",
        data=data,
    )
    assertion = add_assertion(
        store,
        artifact,
        run,
        assertion_id="assertion:markdown",
        locator="README.md:L2-L2",
        statement="second line",
    )

    result = EvidenceInspectionService(store, objects).inspect_assertion(assertion.assertion_id)

    assert result.location_kind is InspectionLocationKind.TEXT_LINES
    assert result.resolved_locator == "README.md:L2-L2"
    assert result.source_text == "second line\n"
    assert result.source_revision_id == f"github:42@{'a' * 40}"


def test_resolves_ast_byte_columns_without_character_index_assumptions(tmp_path) -> None:
    # Python/tree-sitter columns are byte offsets. The multibyte pi before target
    # makes a character-index slice incorrect while the byte slice remains exact.
    data = "π = 1\ntarget()\n".encode("utf-8")
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="sample.py",
        media_type="text/x-python",
        data=data,
        suffix="ast",
    )
    fact = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:ast",
        locator="sample.py:L2:C0-L2:C8#python/call",
        value={"kind": "call"},
    )

    result = EvidenceInspectionService(store, objects).inspect_fact(fact.evidence_id)

    assert result.location_kind is InspectionLocationKind.TEXT_RANGE
    assert result.resolved_locator == "sample.py:L2:C0-L2:C8"
    assert result.source_text == "target()"


def test_resolves_toml_key_and_artifact_path_derivation(tmp_path) -> None:
    data = b'[project]\nname = "lemma"\nrequires-python = ">=3.11"\n'
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="pyproject.toml",
        media_type="application/toml",
        data=data,
        suffix="toml",
    )
    name = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:toml-name",
        locator="pyproject.toml#project.name",
        value="lemma",
    )
    manifest_kind = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:toml-kind",
        locator="pyproject.toml#$manifest.kind",
        value="pyproject.toml",
    )
    basename = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:path",
        locator="pyproject.toml#$path.basename",
        value="pyproject.toml",
    )

    service = EvidenceInspectionService(store, objects)
    assert service.inspect_fact(name.evidence_id).source_value == "lemma"
    kind_result = service.inspect_fact(manifest_kind.evidence_id)
    assert kind_result.location_kind is InspectionLocationKind.ARTIFACT_METADATA
    assert kind_result.source_value == "pyproject.toml"
    assert service.inspect_fact(basename.evidence_id).source_value == "pyproject.toml"


def test_resolves_git_tree_semantic_entry_path_to_canonical_array_pointer(tmp_path) -> None:
    document = {
        "tree_sha": "b" * 40,
        "recursive": False,
        "truncated": False,
        "entries": [
            {"path": "README.md", "mode": "100644", "type": "blob", "sha": "c" * 40},
            {"path": "src", "mode": "040000", "type": "tree", "sha": "d" * 40},
        ],
    }
    data = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="$git/tree/root",
        media_type="application/vnd.lemmamind.git-tree+json",
        data=data,
        suffix="tree",
    )
    entry = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:tree-entry",
        locator="$git/tree/root#/entries/src/type",
        value="tree",
    )
    count = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:tree-count",
        locator="$git/tree/root#/entry_count",
        value=2,
    )

    service = EvidenceInspectionService(store, objects)
    entry_result = service.inspect_fact(entry.evidence_id)
    assert entry_result.resolved_locator == "$git/tree/root#/entries/1/type"
    assert entry_result.source_value == "tree"
    count_result = service.inspect_fact(count.evidence_id)
    assert count_result.location_kind is InspectionLocationKind.DERIVED_STRUCTURE
    assert count_result.resolved_locator == "$git/tree/root#/entries"
    assert len(count_result.source_value) == 2


def test_resolves_repository_metadata_relative_resource_locator(tmp_path) -> None:
    document = {
        "resource_type": "repository_metadata",
        "analysis_anchor_source_revision_id": f"github:42@{'a' * 40}",
        "repository": {
            "id": 42,
            "full_name": "Acme/Repo",
            "visibility": "private",
            "private": True,
            "archived": False,
            "fork": False,
            "default_branch": "main",
        },
    }
    data = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="$github/repository",
        media_type="application/vnd.lemmamind.github-repository-metadata+json",
        data=data,
        suffix="repo-meta",
    )
    fact = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:visibility",
        locator="$github/repository#/visibility",
        value="private",
    )

    result = EvidenceInspectionService(store, objects).inspect_fact(fact.evidence_id)

    assert result.resolved_locator == "$github/repository#/repository/visibility"
    assert result.source_value == "private"


def test_resolves_workflow_provider_ids_and_step_numbers_to_array_indexes(tmp_path) -> None:
    document = {
        "resource_type": "workflow_run",
        "run": {"id": 77, "status": "completed"},
        "jobs": [
            {
                "id": 9001,
                "name": "test",
                "status": "completed",
                "steps": [
                    {"number": 1, "name": "checkout", "status": "completed"},
                    {"number": 2, "name": "pytest", "status": "completed"},
                ],
            }
        ],
        "job_count": 1,
        "artifacts": [{"id": 501, "name": "report"}],
        "artifact_count": 1,
    }
    data = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="$github/actions/run/77",
        media_type="application/vnd.lemmamind.github-workflow-run+json",
        data=data,
        suffix="workflow",
    )
    job = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:job",
        locator="$github/actions/run/77#/jobs/9001/name",
        value="test",
    )
    step = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:step",
        locator="$github/actions/run/77#/jobs/9001/steps/2/name",
        value="pytest",
    )
    report = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:artifact",
        locator="$github/actions/run/77#/artifacts/501/name",
        value="report",
    )

    service = EvidenceInspectionService(store, objects)
    assert service.inspect_fact(job.evidence_id).resolved_locator.endswith("#/jobs/0/name")
    assert service.inspect_fact(step.evidence_id).resolved_locator.endswith("#/jobs/0/steps/1/name")
    assert service.inspect_fact(step.evidence_id).source_value == "pytest"
    assert service.inspect_fact(report.evidence_id).resolved_locator.endswith("#/artifacts/0/name")


def test_resolves_process_event_aggregate_to_exact_event_container(tmp_path) -> None:
    document = {
        "resource_type": "issue_event_history",
        "repository_full_name": "Acme/Repo",
        "issue_number": 7,
        "events": [
            {"provider_id": "1", "event": "closed"},
            {"provider_id": "2", "event": "reopened"},
        ],
    }
    data = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="$github/issue/7/events",
        media_type="application/vnd.lemmamind.github-issue-events+json",
        data=data,
        suffix="events",
    )
    count = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:event-count",
        locator="$github/issue/7/events#/event_count",
        value=2,
    )
    event = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:event",
        locator="$github/issue/7/events#/events/1/event",
        value="reopened",
    )

    service = EvidenceInspectionService(store, objects)
    count_result = service.inspect_fact(count.evidence_id)
    assert count_result.location_kind is InspectionLocationKind.DERIVED_STRUCTURE
    assert count_result.resolved_locator.endswith("#/events")
    assert service.inspect_fact(event.evidence_id).source_value == "reopened"


def test_resolves_plain_json_authored_field_and_commit_parent_derivation(tmp_path) -> None:
    document = {
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "parents": ["c" * 40],
        "author_timestamp": "2026-08-26T00:00:00Z",
        "committer_timestamp": "2026-08-26T00:00:00Z",
        "message": "source-authored commit message",
    }
    data = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="$git/commit",
        media_type="application/vnd.lemmamind.git-commit+json",
        data=data,
        suffix="commit",
    )
    assertion = add_assertion(
        store,
        artifact,
        run,
        assertion_id="assertion:commit-message",
        locator="$git/commit#message",
        statement="source-authored commit message",
    )
    count = add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:parent-count",
        locator="$git/commit#/parent_count",
        value=1,
    )

    service = EvidenceInspectionService(store, objects)
    assertion_result = service.inspect_assertion(assertion.assertion_id)
    assert assertion_result.source_value == "source-authored commit message"
    count_result = service.inspect_fact(count.evidence_id)
    assert count_result.location_kind is InspectionLocationKind.DERIVED_STRUCTURE
    assert count_result.resolved_locator == "$git/commit#/parents"


def test_audit_all_fails_closed_on_unanchored_or_unresolvable_locator(tmp_path) -> None:
    store, objects, artifact, run = seed_artifact(
        tmp_path,
        source_locator="package.json",
        media_type="application/json",
        data=b'{"name":"lemma"}\n',
        suffix="bad",
    )
    add_fact(
        store,
        artifact,
        run,
        evidence_id="fact:bad",
        locator="other.json#/name",
        value="lemma",
    )

    with pytest.raises(EvidenceInspectionError, match="not anchored"):
        EvidenceInspectionService(store, objects).audit_all()
