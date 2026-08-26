"""Exact recursive Git-tree capture and deterministic path-level change localization.

This is the first full-M5 change-signal slice selected by the V2-P0 product-value
probe. It extends the V1 root-tree boundary without interpreting architectural
importance: Git object changes are factual evidence, and surface classification
is deterministic routing metadata only.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    Artifact,
    CaptureArtifactRef,
    CaptureManifest,
    PipelineRun,
    RepositoryIdentity,
    RetrievalStatus,
    RunType,
    SourceRevision,
)
from .git_tree import GitHubTreeRESTReader
from .objects import ContentAddressedFileStore
from .path_change_contracts import (
    ChangeSurface,
    GitPathDelta,
    GitPathDeltaType,
    GitPathDiffSummary,
)
from .tracking import ArtifactClass, CaptureDepth, RepositoryTrackingService

GIT_RECURSIVE_TREE_MEDIA_TYPE = "application/vnd.lemmamind.git-recursive-tree+json"
GIT_RECURSIVE_TREE_LOCATOR = "$git/tree/recursive"
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_TYPES = {"blob", "tree", "commit"}


class RecursiveGitTreeError(RuntimeError):
    """Recursive Git tree evidence is incomplete, malformed, or inconsistent."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


class GitHubRecursiveTreeRESTReader(GitHubTreeRESTReader):
    """Read-only GitHub reader for the complete recursive Git Trees projection."""

    def get_recursive_tree(self, owner: str, repo: str, tree_sha: str) -> Mapping[str, Any]:
        payload = self._get_json(  # noqa: SLF001 - stable read-only extension
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/git/trees/{quote(tree_sha, safe='')}",
            {"recursive": "1"},
        )
        if not isinstance(payload, Mapping):
            raise RecursiveGitTreeError("GitHub recursive tree response must be an object")
        return payload


@dataclass(frozen=True)
class RecursiveGitTreeCaptureResult:
    manifest: CaptureManifest
    artifact: Artifact
    run: PipelineRun

    def records(self) -> tuple:
        return (self.artifact, self.manifest, self.run)


@dataclass(frozen=True)
class RecursiveGitTreeDiffResult:
    previous_capture_id: str
    current_capture_id: str
    summary: GitPathDiffSummary
    deltas: tuple[GitPathDelta, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (self.summary, *self.deltas, self.run)


class GitHubRecursiveTreeCaptureService:
    """Capture one complete recursive tree tied to an exact SourceRevision.

    GitHub may truncate recursive tree responses for large repositories. A
    truncated response is rejected before persistence because a partial path set
    cannot support a completeness claim or a safe affected-file plan.
    """

    def __init__(
        self,
        reader: GitHubRecursiveTreeRESTReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.recursive-tree.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.reader = reader
        self.store = store
        self.object_store = object_store
        self.capture_policy_version = capture_policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def capture_recursive_tree(self, source_revision_id: str) -> RecursiveGitTreeCaptureResult:
        started_at = self._aware_now()
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is None:
            raise KeyError(f"unknown source revision: {source_revision_id}")
        repository = self.store.get(RepositoryIdentity, revision.source_id)
        if repository is None:
            raise KeyError(f"unknown repository identity: {revision.source_id}")

        payload = self.reader.get_recursive_tree(repository.owner, repository.name, revision.tree_sha)
        canonical = self._canonical_tree(payload, expected_tree_sha=revision.tree_sha)
        data = (json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        content_hash = self.object_store.put(data)
        capture_id = f"capture-recursive-tree:{self.id_factory()}"
        artifact_id = self._artifact_id(capture_id, revision.tree_sha)
        artifact = Artifact(
            artifact_id=artifact_id,
            capture_id=capture_id,
            source_locator=GIT_RECURSIVE_TREE_LOCATOR,
            content_hash=content_hash,
            media_type=GIT_RECURSIVE_TREE_MEDIA_TYPE,
        )
        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision.source_revision_id,
            capture_policy_version=self.capture_policy_version,
            captured_at=self._aware_now(),
            artifacts=(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=GIT_RECURSIVE_TREE_LOCATOR,
                    content_hash=content_hash,
                    media_type=GIT_RECURSIVE_TREE_MEDIA_TYPE,
                    retrieval_status=RetrievalStatus.CAPTURED,
                ),
            ),
        )
        inputs_hash = self._digest_json(
            {
                "source_revision_id": revision.source_revision_id,
                "tree_sha": revision.tree_sha,
                "recursive": True,
                "capture_policy_version": self.capture_policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "artifact": artifact.model_dump(mode="json", by_alias=True),
                "manifest": manifest.model_dump(mode="json", by_alias=True),
            }
        )
        run = PipelineRun(
            run_id=f"run:recursive-tree:{self.id_factory()}",
            run_type=RunType.CAPTURE,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.capture_policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = RecursiveGitTreeCaptureResult(manifest, artifact, run)
        self.store.put_many(result.records())
        return result

    @classmethod
    def _canonical_tree(cls, payload: Mapping[str, Any], *, expected_tree_sha: str) -> dict[str, Any]:
        tree_sha = payload.get("sha")
        if tree_sha != expected_tree_sha:
            raise RecursiveGitTreeError(
                f"tree SHA mismatch: expected {expected_tree_sha}, received {tree_sha!r}"
            )
        if bool(payload.get("truncated", False)):
            raise RecursiveGitTreeError("recursive Git tree response is truncated")
        entries_raw = payload.get("tree")
        if not isinstance(entries_raw, list):
            raise RecursiveGitTreeError("GitHub recursive tree response omitted tree entries")

        entries: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for raw in entries_raw:
            if not isinstance(raw, Mapping):
                raise RecursiveGitTreeError("recursive Git tree entry must be an object")
            path = raw.get("path")
            mode = raw.get("mode")
            entry_type = raw.get("type")
            sha = raw.get("sha")
            size = raw.get("size")
            cls._validate_path(path)
            assert isinstance(path, str)
            if path in seen_paths:
                raise RecursiveGitTreeError(f"duplicate recursive tree path: {path}")
            seen_paths.add(path)
            if not isinstance(mode, str) or not mode:
                raise RecursiveGitTreeError(f"tree entry {path!r} omitted mode")
            if entry_type not in _ALLOWED_TYPES:
                raise RecursiveGitTreeError(
                    f"tree entry {path!r} has unsupported type {entry_type!r}"
                )
            if not isinstance(sha, str) or _GIT_SHA.fullmatch(sha) is None:
                raise RecursiveGitTreeError(f"tree entry {path!r} has invalid SHA")
            entry: dict[str, Any] = {
                "path": path,
                "mode": mode,
                "type": entry_type,
                "sha": sha,
            }
            if size is not None:
                if not isinstance(size, int) or size < 0:
                    raise RecursiveGitTreeError(f"tree entry {path!r} has invalid size")
                entry["size"] = size
            entries.append(entry)

        entries.sort(key=lambda item: item["path"])
        return {
            "tree_sha": expected_tree_sha,
            "recursive": True,
            "truncated": False,
            "entries": entries,
        }

    @staticmethod
    def _validate_path(path: object) -> None:
        if not isinstance(path, str) or not path or path.startswith("/") or path.endswith("/"):
            raise RecursiveGitTreeError(f"recursive tree contains invalid path: {path!r}")
        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise RecursiveGitTreeError(f"recursive tree contains unsafe path: {path!r}")

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recursive tree capture clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _artifact_id(capture_id: str, tree_sha: str) -> str:
        material = f"{capture_id}\0{tree_sha}\0recursive-tree".encode("utf-8")
        return f"artifact:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


class TrackingAwareGitHubRecursiveTreeCaptureService(GitHubRecursiveTreeCaptureService):
    """Require Structural-or-deeper tracking for complete recursive tree capture."""

    def __init__(self, *args, tracking: RepositoryTrackingService, **kwargs) -> None:
        self.tracking = tracking
        super().__init__(*args, **kwargs)

    def capture_recursive_tree(self, source_revision_id: str) -> RecursiveGitTreeCaptureResult:
        revision = self.store.get(SourceRevision, source_revision_id)
        if revision is not None:
            self.tracking.require_capture_depth(revision.source_id, CaptureDepth.STRUCTURAL)
            self.tracking.require_artifact_class(revision.source_id, ArtifactClass.GIT_TREE)
        return super().capture_recursive_tree(source_revision_id)


class RecursiveGitTreeDiffService:
    """Compare two retained complete recursive trees without provider fallback.

    Changed directory tree hashes are carrier metadata for descendant changes and
    are not emitted as candidates. Leaf blobs/submodules and path type changes
    are emitted so parent-directory hash churn does not flood the candidate set.
    """

    def __init__(
        self,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        policy_version: str = "recursive-git-path-diff.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.object_store = object_store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def compare_captures(
        self,
        previous_capture_id: str,
        current_capture_id: str,
    ) -> RecursiveGitTreeDiffResult:
        started_at = self._aware_now()
        previous_manifest, previous_revision, previous_entries = self._load_capture(
            previous_capture_id
        )
        current_manifest, current_revision, current_entries = self._load_capture(
            current_capture_id
        )
        if previous_revision.source_id != current_revision.source_id:
            raise RecursiveGitTreeError("recursive tree comparison requires one Source")
        if previous_revision.observed_at > current_revision.observed_at:
            raise RecursiveGitTreeError(
                "previous SourceRevision must not be newer than current SourceRevision"
            )
        if previous_manifest.captured_at > current_manifest.captured_at:
            raise RecursiveGitTreeError(
                "previous CaptureManifest must not be newer than current CaptureManifest"
            )
        if previous_revision.source_revision_id == current_revision.source_revision_id:
            raise RecursiveGitTreeError("recursive tree comparison requires two distinct revisions")

        run_id = f"run:recursive-path-diff:{self.id_factory()}"
        deltas: list[GitPathDelta] = []
        for path in sorted(set(previous_entries) | set(current_entries)):
            previous = previous_entries.get(path)
            current = current_entries.get(path)
            change_type = self._change_type(previous, current)
            if change_type is None:
                continue
            deltas.append(
                GitPathDelta(
                    git_path_delta_id=self._delta_id(
                        run_id,
                        previous_revision.source_revision_id,
                        current_revision.source_revision_id,
                        path,
                        change_type,
                    ),
                    source_id=current_revision.source_id,
                    previous_source_revision_id=previous_revision.source_revision_id,
                    current_source_revision_id=current_revision.source_revision_id,
                    previous_capture_id=previous_manifest.capture_id,
                    current_capture_id=current_manifest.capture_id,
                    path=path,
                    change_type=change_type,
                    surface=classify_change_surface(path),
                    previous_entry_type=self._entry_value(previous, "type"),
                    current_entry_type=self._entry_value(current, "type"),
                    previous_mode=self._entry_value(previous, "mode"),
                    current_mode=self._entry_value(current, "mode"),
                    previous_object_sha=self._entry_value(previous, "sha"),
                    current_object_sha=self._entry_value(current, "sha"),
                    previous_size=self._entry_value(previous, "size"),
                    current_size=self._entry_value(current, "size"),
                    diff_run_id=run_id,
                )
            )

        summary = GitPathDiffSummary(
            git_path_diff_summary_id=self._summary_id(run_id),
            source_id=current_revision.source_id,
            previous_source_revision_id=previous_revision.source_revision_id,
            current_source_revision_id=current_revision.source_revision_id,
            previous_capture_id=previous_manifest.capture_id,
            current_capture_id=current_manifest.capture_id,
            delta_count=len(deltas),
            diff_run_id=run_id,
        )
        inputs_hash = self._digest_json(
            {
                "previous_capture_id": previous_manifest.capture_id,
                "current_capture_id": current_manifest.capture_id,
                "previous_source_revision_id": previous_revision.source_revision_id,
                "current_source_revision_id": current_revision.source_revision_id,
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "summary": summary.model_dump(mode="json", by_alias=True),
                "deltas": [
                    {
                        "path": delta.path,
                        "change_type": delta.change_type.value,
                        "surface": delta.surface.value,
                        "previous_entry_type": delta.previous_entry_type,
                        "current_entry_type": delta.current_entry_type,
                        "previous_mode": delta.previous_mode,
                        "current_mode": delta.current_mode,
                        "previous_object_sha": delta.previous_object_sha,
                        "current_object_sha": delta.current_object_sha,
                        "previous_size": delta.previous_size,
                        "current_size": delta.current_size,
                    }
                    for delta in deltas
                ],
            }
        )
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.DIFF,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = RecursiveGitTreeDiffResult(
            previous_manifest.capture_id,
            current_manifest.capture_id,
            summary,
            tuple(deltas),
            run,
        )
        self.store.put_many(result.records())
        return result

    def _load_capture(
        self, capture_id: str
    ) -> tuple[CaptureManifest, SourceRevision, dict[str, Mapping[str, Any]]]:
        manifest = self.store.get(CaptureManifest, capture_id)
        if manifest is None:
            raise KeyError(f"unknown capture: {capture_id}")
        if len(manifest.artifacts) != 1:
            raise RecursiveGitTreeError("recursive tree capture must contain exactly one artifact")
        reference = manifest.artifacts[0]
        if (
            reference.retrieval_status is not RetrievalStatus.CAPTURED
            or reference.media_type != GIT_RECURSIVE_TREE_MEDIA_TYPE
            or reference.source_locator != GIT_RECURSIVE_TREE_LOCATOR
        ):
            raise RecursiveGitTreeError("capture is not a complete recursive Git tree")
        artifact = self.store.get(Artifact, reference.artifact_id)
        if artifact is None:
            raise RecursiveGitTreeError("recursive tree manifest references missing Artifact")
        if (
            artifact.capture_id != manifest.capture_id
            or artifact.content_hash != reference.content_hash
            or artifact.media_type != GIT_RECURSIVE_TREE_MEDIA_TYPE
            or artifact.source_locator != GIT_RECURSIVE_TREE_LOCATOR
        ):
            raise RecursiveGitTreeError("recursive tree Artifact disagrees with CaptureManifest")
        revision = self.store.get(SourceRevision, manifest.source_revision_id)
        if revision is None:
            raise RecursiveGitTreeError("recursive tree capture references missing SourceRevision")
        try:
            document = json.loads(self.object_store.get(artifact.content_hash).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RecursiveGitTreeError("retained recursive tree is not canonical UTF-8 JSON") from exc
        if not isinstance(document, Mapping):
            raise RecursiveGitTreeError("retained recursive tree must be an object")
        if document.get("tree_sha") != revision.tree_sha:
            raise RecursiveGitTreeError("retained recursive tree disagrees with SourceRevision.tree_sha")
        if document.get("recursive") is not True or document.get("truncated") is not False:
            raise RecursiveGitTreeError("retained recursive tree is incomplete")
        entries_raw = document.get("entries")
        if not isinstance(entries_raw, list):
            raise RecursiveGitTreeError("retained recursive tree omitted entries")
        entries: dict[str, Mapping[str, Any]] = {}
        for entry in entries_raw:
            if not isinstance(entry, Mapping):
                raise RecursiveGitTreeError("retained recursive tree entry must be an object")
            path = entry.get("path")
            GitHubRecursiveTreeCaptureService._validate_path(path)
            assert isinstance(path, str)
            if path in entries:
                raise RecursiveGitTreeError(f"duplicate retained recursive tree path: {path}")
            entries[path] = entry
        return manifest, revision, entries

    @staticmethod
    def _change_type(
        previous: Mapping[str, Any] | None,
        current: Mapping[str, Any] | None,
    ) -> GitPathDeltaType | None:
        if previous is None:
            return None if current is None or current.get("type") == "tree" else GitPathDeltaType.ADDED
        if current is None:
            return None if previous.get("type") == "tree" else GitPathDeltaType.REMOVED
        previous_type = previous.get("type")
        current_type = current.get("type")
        if previous_type != current_type:
            return GitPathDeltaType.TYPE_CHANGED
        if previous_type == "tree":
            return None
        if (
            previous.get("sha") != current.get("sha")
            or previous.get("mode") != current.get("mode")
            or previous.get("size") != current.get("size")
        ):
            return GitPathDeltaType.MODIFIED
        return None

    @staticmethod
    def _entry_value(entry: Mapping[str, Any] | None, key: str):
        return None if entry is None else entry.get(key)

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recursive path diff clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _summary_id(run_id: str) -> str:
        material = f"git-path-diff-summary\0{run_id}".encode("utf-8")
        return f"git-path-diff-summary:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _delta_id(
        run_id: str,
        previous_revision_id: str,
        current_revision_id: str,
        path: str,
        change_type: GitPathDeltaType,
    ) -> str:
        material = (
            f"git-path-delta\0{run_id}\0{previous_revision_id}\0{current_revision_id}"
            f"\0{path}\0{change_type.value}"
        ).encode("utf-8")
        return f"git-path-delta:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


_LOCKFILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
    "cargo.lock",
    "go.sum",
    "composer.lock",
    "gemfile.lock",
}
_MANIFESTS = {
    "pyproject.toml",
    "package.json",
    "cargo.toml",
    "go.mod",
    "composer.json",
    "gemfile",
}
_SOURCE_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".rs", ".go", ".java", ".kt", ".kts", ".c", ".h", ".cc", ".cpp",
    ".hpp", ".cs", ".rb", ".php", ".swift", ".scala", ".sh",
}
_DOC_SUFFIXES = {".md", ".rst", ".adoc"}
_CONFIG_SUFFIXES = {".toml", ".yaml", ".yml", ".ini", ".cfg", ".json"}


def classify_change_surface(path: str) -> ChangeSurface:
    """Classify one path using only deterministic lexical/path information."""

    normalized = path.lower()
    parts = tuple(part for part in normalized.split("/") if part)
    basename = parts[-1] if parts else normalized
    suffix = PurePosixPath(basename).suffix.lower()

    if normalized.startswith(".github/workflows/"):
        return ChangeSurface.WORKFLOW
    if basename in _LOCKFILES:
        return ChangeSurface.LOCKFILE
    if basename in _MANIFESTS or basename.startswith("requirements") and basename.endswith(".txt"):
        return ChangeSurface.MANIFEST
    if any(part in {"vendor", "vendored", "third_party", "third-party"} for part in parts):
        return ChangeSurface.VENDORED
    if any(part in {"generated", "gen"} for part in parts) or basename.endswith(".min.js"):
        return ChangeSurface.GENERATED
    if (
        any(part in {"tests", "test", "__tests__"} for part in parts)
        or basename.startswith("test_")
        or basename.endswith("_test.py")
        or basename.endswith((".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx", ".spec.js"))
    ):
        return ChangeSurface.TEST
    if (
        parts and parts[0] in {"docs", "doc"}
        or basename.startswith("readme")
        or basename.startswith("changelog")
        or suffix in _DOC_SUFFIXES
    ):
        return ChangeSurface.DOCS
    if basename == "dockerfile" or basename.startswith("docker-compose") or suffix in _CONFIG_SUFFIXES:
        return ChangeSurface.CONFIG
    if suffix in _SOURCE_SUFFIXES:
        return ChangeSurface.SOURCE
    return ChangeSurface.UNKNOWN
