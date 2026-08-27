"""Deterministic full-M5 interval and candidate segmentation.

The service turns one completed recursive Git path diff into smaller temporal/path
review units without semantic ranking. It enumerates the exact Git commit range,
retains each commit's complete changed-path projection, assigns every net
``GitPathDelta`` to its latest touching commit, and groups those assignments by
stable path structure with a fixed attention bound.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    PipelineRun,
    RepositoryIdentity,
    RunType,
    SourceRevision,
)
from .interval_segmentation_contracts import (
    CommitPathSnapshot,
    CommitRangeStatus,
    CommitRangeSummary,
    IntervalCandidateSegment,
)
from .path_change_contracts import GitPathDelta, GitPathDiffSummary
from .recursive_tree import GitHubRecursiveTreeRESTReader
from .tracking import CaptureDepth, RepositoryTrackingService

COMPARE_PAGE_SIZE = 100
COMMIT_FILES_PAGE_SIZE = 100
MAX_COMMITS_PER_INTERVAL_V1 = 2_000
MAX_GITHUB_FILES_PER_COMMIT = 3_000
MAX_PATHS_PER_CANDIDATE_V1 = 50


class IntervalSegmentationError(RuntimeError):
    """Provider or persisted evidence cannot support one complete segmentation."""


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def list(self, model: type): ...

    def put_many(self, records): ...


class GitHubIntervalRESTReader(GitHubRecursiveTreeRESTReader):
    """Read-only GitHub reader for recursive trees plus commit-range evidence."""

    def get_compare_page(
        self,
        owner: str,
        repo: str,
        base_sha: str,
        head_sha: str,
        *,
        page: int,
        per_page: int = COMPARE_PAGE_SIZE,
    ) -> Mapping[str, Any]:
        basehead = quote(f"{base_sha}...{head_sha}", safe=".")
        payload = self._get_json(  # noqa: SLF001 - stable read-only extension
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/compare/{basehead}",
            {"page": str(page), "per_page": str(per_page)},
        )
        if not isinstance(payload, Mapping):
            raise IntervalSegmentationError("GitHub compare response must be an object")
        return payload

    def get_commit_page(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        *,
        page: int,
        per_page: int = COMMIT_FILES_PAGE_SIZE,
    ) -> Mapping[str, Any]:
        payload = self._get_json(  # noqa: SLF001 - stable read-only extension
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/commits/{quote(commit_sha, safe='')}",
            {"page": str(page), "per_page": str(per_page)},
        )
        if not isinstance(payload, Mapping):
            raise IntervalSegmentationError("GitHub commit response must be an object")
        return payload


@dataclass(frozen=True)
class IntervalSegmentationResult:
    diff_run_id: str
    commit_range: CommitRangeSummary
    commit_snapshots: tuple[CommitPathSnapshot, ...]
    candidates: tuple[IntervalCandidateSegment, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (self.commit_range, *self.commit_snapshots, *self.candidates, self.run)

    @property
    def candidate_paths(self) -> tuple[str, ...]:
        return tuple(path for candidate in self.candidates for path in candidate.paths)


class IntervalCandidateSegmentationService:
    """Segment net path changes by latest touching commit and typed path group."""

    def __init__(
        self,
        reader: GitHubIntervalRESTReader,
        store: ContractStore,
        tracking: RepositoryTrackingService,
        *,
        max_paths_per_candidate: int = MAX_PATHS_PER_CANDIDATE_V1,
        policy_version: str = "interval-candidate-segmentation.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_paths_per_candidate < 1:
            raise ValueError("max_paths_per_candidate must be positive")
        self.reader = reader
        self.store = store
        self.tracking = tracking
        self.max_paths_per_candidate = max_paths_per_candidate
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def segment_diff(self, diff_run_id: str) -> IntervalSegmentationResult:
        started_at = self._aware_now()
        diff_run = self.store.get(PipelineRun, diff_run_id)
        if diff_run is None:
            raise KeyError(f"unknown diff PipelineRun: {diff_run_id}")
        if diff_run.run_type is not RunType.DIFF or diff_run.finished_at is None:
            raise IntervalSegmentationError(
                "interval segmentation requires one completed DIFF PipelineRun"
            )

        summaries = tuple(
            item
            for item in self.store.list(GitPathDiffSummary)
            if item.diff_run_id == diff_run_id
        )
        if len(summaries) != 1:
            raise IntervalSegmentationError(
                "interval segmentation requires exactly one GitPathDiffSummary"
            )
        diff_summary = summaries[0]
        deltas = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(GitPathDelta)
                    if item.diff_run_id == diff_run_id
                ),
                key=lambda item: item.path,
            )
        )
        if len(deltas) != diff_summary.delta_count:
            raise IntervalSegmentationError(
                "GitPathDiffSummary delta_count disagrees with persisted GitPathDelta records"
            )
        self._validate_delta_generation(diff_summary, deltas)
        if len({item.path for item in deltas}) != len(deltas):
            raise IntervalSegmentationError("diff run contains duplicate Git paths")

        previous_revision = self._revision(diff_summary.previous_source_revision_id)
        current_revision = self._revision(diff_summary.current_source_revision_id)
        if (
            previous_revision.source_id != diff_summary.source_id
            or current_revision.source_id != diff_summary.source_id
        ):
            raise IntervalSegmentationError("diff summary revision/source provenance disagrees")
        if previous_revision.observed_at > current_revision.observed_at:
            raise IntervalSegmentationError(
                "previous SourceRevision must not be newer than current SourceRevision"
            )
        repository = self.store.get(RepositoryIdentity, diff_summary.source_id)
        if repository is None:
            raise IntervalSegmentationError(
                f"missing RepositoryIdentity for {diff_summary.source_id}"
            )

        tracking_policy = self.tracking.require_capture_depth(
            diff_summary.source_id,
            CaptureDepth.STRUCTURAL,
        )
        if tracking_policy.assignment_id is None:
            raise IntervalSegmentationError(
                "interval segmentation requires a persisted tracking assignment"
            )

        run_id = f"run:interval-segmentation:{self.id_factory()}"
        provider_status, commit_shas = self._load_commit_range(
            repository.owner,
            repository.name,
            previous_revision.commit_sha,
            current_revision.commit_sha,
        )
        commit_range = CommitRangeSummary(
            commit_range_summary_id=self._stable_id(
                "commit-range-summary",
                run_id,
                previous_revision.source_revision_id,
                current_revision.source_revision_id,
            ),
            source_id=diff_summary.source_id,
            previous_source_revision_id=previous_revision.source_revision_id,
            current_source_revision_id=current_revision.source_revision_id,
            provider_status=provider_status,
            total_commits=len(commit_shas),
            commit_shas=commit_shas,
            segmentation_run_id=run_id,
        )

        snapshots = tuple(
            self._commit_snapshot(
                repository.owner,
                repository.name,
                commit_sha,
                ordinal=ordinal,
                run_id=run_id,
                source_id=diff_summary.source_id,
                previous_source_revision_id=previous_revision.source_revision_id,
                current_source_revision_id=current_revision.source_revision_id,
            )
            for ordinal, commit_sha in enumerate(commit_shas, start=1)
        )
        self._validate_linear_commit_chain(
            previous_revision.commit_sha,
            current_revision.commit_sha,
            snapshots,
        )
        latest_touch = self._assign_latest_touch(deltas, snapshots)
        candidates = self._build_candidates(
            deltas,
            latest_touch,
            run_id=run_id,
            source_id=diff_summary.source_id,
            previous_source_revision_id=previous_revision.source_revision_id,
            current_source_revision_id=current_revision.source_revision_id,
        )

        assigned_delta_ids = tuple(
            delta_id
            for candidate in candidates
            for delta_id in candidate.git_path_delta_ids
        )
        expected_delta_ids = tuple(sorted(item.git_path_delta_id for item in deltas))
        if tuple(sorted(assigned_delta_ids)) != expected_delta_ids:
            raise IntervalSegmentationError(
                "candidate segmentation must assign every GitPathDelta exactly once"
            )

        inputs_hash = self._digest_json(
            {
                "diff_run_id": diff_run_id,
                "diff_summary": diff_summary.model_dump(mode="json", by_alias=True),
                "path_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in deltas
                ],
                "tracking_assignment_id": tracking_policy.assignment_id,
                "tracking_level": tracking_policy.level.value,
                "max_paths_per_candidate": self.max_paths_per_candidate,
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "commit_range": commit_range.model_dump(mode="json", by_alias=True),
                "commit_snapshots": [
                    item.model_dump(mode="json", by_alias=True) for item in snapshots
                ],
                "candidates": [
                    item.model_dump(mode="json", by_alias=True) for item in candidates
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
        result = IntervalSegmentationResult(
            diff_run_id,
            commit_range,
            snapshots,
            candidates,
            run,
        )
        self.store.put_many(result.records())
        return result

    @staticmethod
    def _validate_delta_generation(
        summary: GitPathDiffSummary,
        deltas: tuple[GitPathDelta, ...],
    ) -> None:
        expected = (
            summary.source_id,
            summary.previous_source_revision_id,
            summary.current_source_revision_id,
            summary.previous_capture_id,
            summary.current_capture_id,
            summary.diff_run_id,
        )
        for delta in deltas:
            observed = (
                delta.source_id,
                delta.previous_source_revision_id,
                delta.current_source_revision_id,
                delta.previous_capture_id,
                delta.current_capture_id,
                delta.diff_run_id,
            )
            if observed != expected:
                raise IntervalSegmentationError(
                    "GitPathDelta generation provenance disagrees with GitPathDiffSummary"
                )

    def _load_commit_range(
        self,
        owner: str,
        repo: str,
        base_sha: str,
        head_sha: str,
    ) -> tuple[CommitRangeStatus, tuple[str, ...]]:
        commits: list[str] = []
        expected_total: int | None = None
        expected_status: CommitRangeStatus | None = None
        page = 1
        while True:
            payload = self.reader.get_compare_page(
                owner,
                repo,
                base_sha,
                head_sha,
                page=page,
                per_page=COMPARE_PAGE_SIZE,
            )
            status_raw = payload.get("status")
            try:
                status = CommitRangeStatus(str(status_raw))
            except ValueError as exc:
                raise IntervalSegmentationError(
                    f"unsupported GitHub compare status: {status_raw!r}"
                ) from exc
            total = payload.get("total_commits")
            if not isinstance(total, int) or total < 0:
                raise IntervalSegmentationError("GitHub compare omitted total_commits")
            if total > MAX_COMMITS_PER_INTERVAL_V1:
                raise IntervalSegmentationError(
                    f"commit interval exceeds v1 limit of {MAX_COMMITS_PER_INTERVAL_V1}"
                )
            if expected_total is None:
                expected_total = total
                expected_status = status
                base_commit = payload.get("base_commit")
                merge_base = payload.get("merge_base_commit")
                if not isinstance(base_commit, Mapping) or base_commit.get("sha") != base_sha:
                    raise IntervalSegmentationError("GitHub compare base_commit disagrees")
                if status is CommitRangeStatus.AHEAD:
                    if not isinstance(merge_base, Mapping) or merge_base.get("sha") != base_sha:
                        raise IntervalSegmentationError(
                            "baseline is not the merge base; interval is not an ahead frontier"
                        )
            elif total != expected_total or status is not expected_status:
                raise IntervalSegmentationError(
                    "GitHub compare pagination changed status or total_commits"
                )

            raw_commits = payload.get("commits")
            if not isinstance(raw_commits, list):
                raise IntervalSegmentationError("GitHub compare omitted commits list")
            page_shas: list[str] = []
            for raw in raw_commits:
                if not isinstance(raw, Mapping):
                    raise IntervalSegmentationError("GitHub compare commit must be an object")
                sha = raw.get("sha")
                if not self._is_git_sha(sha):
                    raise IntervalSegmentationError("GitHub compare commit has invalid SHA")
                assert isinstance(sha, str)
                page_shas.append(sha)
            commits.extend(page_shas)
            if len(commits) >= total:
                break
            if not page_shas:
                raise IntervalSegmentationError(
                    "GitHub compare pagination ended before total_commits"
                )
            page += 1

        assert expected_total is not None and expected_status is not None
        if len(commits) != expected_total:
            raise IntervalSegmentationError(
                "GitHub compare returned a commit count different from total_commits"
            )
        if len(commits) != len(set(commits)):
            raise IntervalSegmentationError("GitHub compare returned duplicate commits")
        if expected_status is CommitRangeStatus.IDENTICAL:
            if base_sha != head_sha or commits:
                raise IntervalSegmentationError("identical compare frontier is inconsistent")
        elif not commits or commits[-1] != head_sha:
            raise IntervalSegmentationError(
                "GitHub compare frontier does not terminate at current revision"
            )
        return expected_status, tuple(commits)

    def _commit_snapshot(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        *,
        ordinal: int,
        run_id: str,
        source_id: str,
        previous_source_revision_id: str,
        current_source_revision_id: str,
    ) -> CommitPathSnapshot:
        touched_paths: set[str] = set()
        parent_shas: tuple[str, ...] | None = None
        page = 1
        raw_file_count = 0
        while True:
            payload = self.reader.get_commit_page(
                owner,
                repo,
                commit_sha,
                page=page,
                per_page=COMMIT_FILES_PAGE_SIZE,
            )
            if payload.get("sha") != commit_sha:
                raise IntervalSegmentationError("GitHub commit page disagrees on commit SHA")
            raw_parents = payload.get("parents")
            if not isinstance(raw_parents, list):
                raise IntervalSegmentationError("GitHub commit page omitted parents")
            current_parents: list[str] = []
            for raw_parent in raw_parents:
                if not isinstance(raw_parent, Mapping) or not self._is_git_sha(raw_parent.get("sha")):
                    raise IntervalSegmentationError("GitHub commit parent has invalid SHA")
                current_parents.append(str(raw_parent["sha"]))
            if parent_shas is None:
                parent_shas = tuple(current_parents)
            elif tuple(current_parents) != parent_shas:
                raise IntervalSegmentationError("GitHub commit pagination changed parent metadata")

            raw_files = payload.get("files")
            if not isinstance(raw_files, list):
                raise IntervalSegmentationError("GitHub commit page omitted files")
            raw_file_count += len(raw_files)
            for raw_file in raw_files:
                if not isinstance(raw_file, Mapping):
                    raise IntervalSegmentationError("GitHub commit file must be an object")
                filename = raw_file.get("filename")
                self._validate_git_path(filename)
                assert isinstance(filename, str)
                touched_paths.add(filename)
                previous_filename = raw_file.get("previous_filename")
                if previous_filename is not None:
                    self._validate_git_path(previous_filename)
                    assert isinstance(previous_filename, str)
                    touched_paths.add(previous_filename)

            if len(raw_files) < COMMIT_FILES_PAGE_SIZE:
                break
            if raw_file_count >= MAX_GITHUB_FILES_PER_COMMIT:
                raise IntervalSegmentationError(
                    "GitHub commit file projection reached the 3,000-file completeness limit"
                )
            page += 1

        assert parent_shas is not None
        return CommitPathSnapshot(
            commit_path_snapshot_id=self._stable_id(
                "commit-path-snapshot", run_id, commit_sha
            ),
            source_id=source_id,
            previous_source_revision_id=previous_source_revision_id,
            current_source_revision_id=current_source_revision_id,
            commit_sha=commit_sha,
            ordinal=ordinal,
            parent_shas=parent_shas,
            touched_paths=tuple(sorted(touched_paths)),
            segmentation_run_id=run_id,
        )

    @staticmethod
    def _validate_linear_commit_chain(
        base_sha: str,
        head_sha: str,
        snapshots: tuple[CommitPathSnapshot, ...],
    ) -> None:
        if not snapshots:
            if base_sha != head_sha:
                raise IntervalSegmentationError(
                    "commit interval has no commits between distinct revisions"
                )
            return

        expected_parent = base_sha
        for snapshot in snapshots:
            if snapshot.parent_shas != (expected_parent,):
                raise IntervalSegmentationError(
                    "commit interval is not a single-parent linear chain"
                )
            expected_parent = snapshot.commit_sha
        if expected_parent != head_sha:
            raise IntervalSegmentationError(
                "linear commit chain does not terminate at current revision"
            )

    @staticmethod
    def _assign_latest_touch(
        deltas: tuple[GitPathDelta, ...],
        snapshots: tuple[CommitPathSnapshot, ...],
    ) -> dict[str, CommitPathSnapshot]:
        wanted = {item.path for item in deltas}
        latest: dict[str, CommitPathSnapshot] = {}
        for snapshot in snapshots:
            for path in snapshot.touched_paths:
                if path in wanted:
                    latest[path] = snapshot
        missing = tuple(sorted(wanted - set(latest)))
        if missing:
            preview = ", ".join(repr(path) for path in missing[:5])
            suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
            raise IntervalSegmentationError(
                f"net GitPathDelta paths are absent from complete commit touch sets: {preview}{suffix}"
            )
        return latest

    def _build_candidates(
        self,
        deltas: tuple[GitPathDelta, ...],
        latest_touch: dict[str, CommitPathSnapshot],
        *,
        run_id: str,
        source_id: str,
        previous_source_revision_id: str,
        current_source_revision_id: str,
    ) -> tuple[IntervalCandidateSegment, ...]:
        grouped: dict[tuple[int, str], list[GitPathDelta]] = {}
        snapshot_by_ordinal: dict[int, CommitPathSnapshot] = {}
        for delta in deltas:
            snapshot = latest_touch[delta.path]
            snapshot_by_ordinal[snapshot.ordinal] = snapshot
            key = (snapshot.ordinal, self._path_group(delta.path))
            grouped.setdefault(key, []).append(delta)

        candidates: list[IntervalCandidateSegment] = []
        for (commit_ordinal, path_group), items in sorted(grouped.items()):
            snapshot = snapshot_by_ordinal[commit_ordinal]
            ordered = sorted(items, key=lambda item: item.path)
            for offset in range(0, len(ordered), self.max_paths_per_candidate):
                chunk = ordered[offset : offset + self.max_paths_per_candidate]
                chunk_ordinal = offset // self.max_paths_per_candidate + 1
                candidates.append(
                    IntervalCandidateSegment(
                        interval_candidate_segment_id=self._stable_id(
                            "interval-candidate-segment",
                            run_id,
                            snapshot.commit_sha,
                            path_group,
                            str(chunk_ordinal),
                        ),
                        source_id=source_id,
                        previous_source_revision_id=previous_source_revision_id,
                        current_source_revision_id=current_source_revision_id,
                        commit_path_snapshot_id=snapshot.commit_path_snapshot_id,
                        commit_sha=snapshot.commit_sha,
                        commit_ordinal=commit_ordinal,
                        path_group=path_group,
                        chunk_ordinal=chunk_ordinal,
                        git_path_delta_ids=tuple(item.git_path_delta_id for item in chunk),
                        paths=tuple(item.path for item in chunk),
                        segmentation_run_id=run_id,
                    )
                )
        return tuple(candidates)

    @staticmethod
    def _path_group(path: str) -> str:
        parts = path.split("/")
        if len(parts) == 1:
            return "root"
        if len(parts) >= 2 and parts[0] == ".github" and parts[1] == "workflows":
            return "path-prefix:" + json.dumps(
                ".github/workflows", ensure_ascii=False, separators=(",", ":")
            )
        return "top-level:" + json.dumps(
            parts[0], ensure_ascii=False, separators=(",", ":")
        )

    def _revision(self, revision_id: str) -> SourceRevision:
        revision = self.store.get(SourceRevision, revision_id)
        if revision is None:
            raise IntervalSegmentationError(
                f"GitPathDiffSummary references missing SourceRevision: {revision_id}"
            )
        return revision

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("interval segmentation clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _validate_git_path(path: object) -> None:
        if (
            not isinstance(path, str)
            or not path
            or "\x00" in path
            or path.startswith("/")
            or path.endswith("/")
        ):
            raise IntervalSegmentationError(f"GitHub commit contains invalid path: {path!r}")
        if any(part in {"", ".", ".."} for part in path.split("/")):
            raise IntervalSegmentationError(f"GitHub commit contains unsafe path: {path!r}")

    @staticmethod
    def _is_git_sha(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 40
            and all(character in "0123456789abcdef" for character in value)
        )

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        material = "\0".join((prefix, *parts)).encode("utf-8")
        return f"{prefix}:{hashlib.sha256(material).hexdigest()}"

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
