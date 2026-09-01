"""Read-only GitHub acquisition into the M0 evidence spine."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .contracts import (
    CONTRACT_SCHEMA_VERSION, Artifact, CaptureArtifactRef, CaptureManifest,
    PipelineRun, RepositoryIdentity, RetrievalStatus, RunType, Source,
    SourceKind, SourceRevision, SourceRole,
)
from .objects import ContentAddressedFileStore

_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".py": "text/x-python",
    ".json": "application/json",
    ".toml": "application/toml",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".xml": "application/xml",
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".rs": "text/x-rust",
    ".go": "text/x-go",
}

_HTTP_DAY_SHORT = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
_HTTP_DAY_LONG = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_HTTP_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
_IMF_FIXDATE_RE = re.compile(
    rf"{_HTTP_DAY_SHORT}, [0-9]{{2}} {_HTTP_MONTH} [0-9]{{4}} "
    r"[0-9]{2}:[0-9]{2}:[0-9]{2} GMT"
)
_RFC850_DATE_RE = re.compile(
    rf"{_HTTP_DAY_LONG}, [0-9]{{2}}-{_HTTP_MONTH}-(?P<year>[0-9]{{2}}) "
    r"[0-9]{2}:[0-9]{2}:[0-9]{2} GMT"
)
_ASCTIME_DATE_RE = re.compile(
    rf"{_HTTP_DAY_SHORT} {_HTTP_MONTH} (?:[0-9]{{2}}| [0-9]) "
    r"[0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}"
)


class GitHubAPIError(RuntimeError):
    """GitHub REST request failed."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubNotFound(GitHubAPIError):
    """Requested GitHub resource does not exist at the pinned revision."""


class RepositoryIdentityDrift(RuntimeError):
    """Stable repository metadata changed and requires M2 identity handling."""


class SourceMetadataDrift(RuntimeError):
    """An existing source would be silently reclassified or relocated."""


class GitHubReader(Protocol):
    """Read-only GitHub interface used by the deterministic capture service."""

    def get_repository(self, owner: str, repo: str) -> Mapping[str, Any]: ...

    def get_commit(self, owner: str, repo: str, ref: str) -> Mapping[str, Any]: ...

    def get_file(self, owner: str, repo: str, path: str, ref: str) -> bytes: ...


class ContractStore(Protocol):
    def get(self, model: type, record_id: str): ...

    def put_many(self, records): ...


class GitHubRESTReader:
    """Minimal read-only GitHub REST client using Python's standard library."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = "https://api.github.com",
        user_agent: str = "LemmaMind/0.1",
        timeout: float = 30.0,
        max_retries: int = 3,
        sleep: Callable[[float], None] | None = None,
        wall_clock: Callable[[], float] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep or time.sleep
        self.wall_clock = wall_clock or time.time

    def _get_json(self, path: str, query: Mapping[str, str] | None = None) -> Any:
        url = f"{self.base_url}{path}" + (f"?{urlencode(query)}" if query else "")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        retry_index = 0
        while True:
            request = Request(url, headers=headers, method="GET")
            try:
                with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                try:
                    payload = json.loads(exc.read().decode("utf-8"))
                    detail = str(payload.get("message", exc.reason))
                except Exception:
                    detail = str(exc.reason)

                delay = self._retry_delay(exc, detail, retry_index)
                if delay is not None and retry_index < self.max_retries:
                    self.sleep(delay)
                    retry_index += 1
                    continue

                error_type = GitHubNotFound if exc.code == 404 else GitHubAPIError
                raise error_type(
                    f"GitHub API {exc.code}: {detail}",
                    status_code=exc.code,
                ) from exc

    def _retry_delay(self, exc: HTTPError, detail: str, retry_index: int) -> float | None:
        headers = exc.headers
        retry_after = headers.get("Retry-After") if headers is not None else None
        rate_remaining = headers.get("X-RateLimit-Remaining") if headers is not None else None
        rate_reset = headers.get("X-RateLimit-Reset") if headers is not None else None
        detail_lower = detail.lower()
        is_rate_limited = (
            exc.code == 429
            or (
                exc.code == 403
                and (
                    rate_remaining == "0"
                    or "rate limit" in detail_lower
                )
            )
        )
        if is_rate_limited:
            if retry_after is not None:
                retry_after_delay = self._parse_retry_after(retry_after)
                if retry_after_delay is not None:
                    return retry_after_delay
            if rate_remaining == "0" and rate_reset is not None:
                reset = rate_reset.strip()
                if reset.isascii() and reset.isdigit():
                    reset_at = float(reset)
                    if math.isfinite(reset_at):
                        reset_delay = reset_at - self.wall_clock() + 1.0
                        if math.isfinite(reset_delay):
                            return max(1.0, reset_delay)
            return 60.0 * (2 ** retry_index)

        if exc.code == 503 and retry_after is not None:
            retry_after_delay = self._parse_retry_after(retry_after)
            if retry_after_delay is not None:
                return retry_after_delay

        if exc.code in {500, 502, 503, 504}:
            return 1.0 * (2 ** retry_index)
        return None

    def _parse_retry_after(self, value: str) -> float | None:
        numeric = value.strip()
        if numeric.isascii() and numeric.isdigit():
            delay = float(numeric)
            if math.isfinite(delay):
                return delay
            return None

        http_date = value.strip()
        rfc850_match = _RFC850_DATE_RE.fullmatch(http_date)
        is_asctime = _ASCTIME_DATE_RE.fullmatch(http_date) is not None
        if not (
            _IMF_FIXDATE_RE.fullmatch(http_date)
            or rfc850_match
            or is_asctime
        ):
            return None
        try:
            retry_at = parsedate_to_datetime(http_date)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            if not is_asctime:
                return None
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        elif retry_at.utcoffset().total_seconds() != 0.0:
            return None

        if rfc850_match is not None:
            try:
                now = datetime.fromtimestamp(self.wall_clock(), tz=timezone.utc)
                year_suffix = int(rfc850_match.group("year"))
                candidate_year = (now.year // 100) * 100 + year_suffix
                candidate_fields = (
                    retry_at.month,
                    retry_at.day,
                    retry_at.hour,
                    retry_at.minute,
                    retry_at.second,
                )
                now_fields = (
                    now.month,
                    now.day,
                    now.hour,
                    now.minute,
                    now.second,
                )
                if candidate_year < now.year - 50 or (
                    candidate_year == now.year - 50
                    and candidate_fields < now_fields
                ):
                    candidate_year += 100
                if candidate_year > now.year + 50 or (
                    candidate_year == now.year + 50
                    and candidate_fields > now_fields
                ):
                    candidate_year -= 100
                retry_at = retry_at.replace(year=candidate_year)
            except (OSError, OverflowError, ValueError):
                return None

        try:
            delay = retry_at.timestamp() - self.wall_clock()
        except (OSError, OverflowError, ValueError):
            return None
        if not math.isfinite(delay):
            return None
        return max(0.0, delay)

    def get_repository(self, owner: str, repo: str) -> Mapping[str, Any]:
        return self._get_json(f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}")

    def get_commit(self, owner: str, repo: str, ref: str) -> Mapping[str, Any]:
        return self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/commits/{quote(ref, safe='')}"
        )

    def get_file(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        prefix = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
        payload = self._get_json(
            f"{prefix}/contents/{quote(path, safe='/')}",
            {"ref": ref},
        )
        if not isinstance(payload, Mapping) or payload.get("type") != "file":
            raise GitHubAPIError(f"GitHub path is not a file: {path}")
        content = payload.get("content")
        if payload.get("encoding") == "base64" and isinstance(content, str):
            return base64.b64decode(content, validate=False)
        blob_sha = payload.get("sha")
        if not isinstance(blob_sha, str):
            raise GitHubAPIError(f"GitHub file payload omitted content and blob SHA: {path}")
        blob = self._get_json(f"{prefix}/git/blobs/{quote(blob_sha, safe='')}")
        blob_content = blob.get("content") if isinstance(blob, Mapping) else None
        if not isinstance(blob_content, str) or blob.get("encoding") != "base64":
            raise GitHubAPIError(f"GitHub blob could not be decoded: {path}")
        return base64.b64decode(blob_content, validate=False)


@dataclass(frozen=True)
class GitHubCaptureResult:
    source: Source
    repository: RepositoryIdentity
    revision: SourceRevision
    manifest: CaptureManifest
    artifacts: tuple[Artifact, ...]
    run: PipelineRun

    def records(self) -> tuple:
        return (
            self.source,
            self.repository,
            self.revision,
            *self.artifacts,
            self.manifest,
            self.run,
        )


class GitHubCaptureService:
    """Capture explicit files without executing source or performing GitHub writes."""

    def __init__(
        self,
        reader: GitHubReader,
        store: ContractStore,
        object_store: ContentAddressedFileStore,
        *,
        capture_policy_version: str = "github.explicit-paths.v1",
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

    def capture_repository(
        self,
        repository: str,
        paths: list[str] | tuple[str, ...],
        *,
        source_role: SourceRole = SourceRole.UNKNOWN,
        ref: str | None = None,
    ) -> GitHubCaptureResult:
        owner, repo = self._split_repository(repository)
        normalized_paths = self._normalize_paths(paths)
        started_at = self._aware_now()
        metadata = self.reader.get_repository(owner, repo)
        provider_id = str(metadata["id"])
        current_owner = str(metadata["owner"]["login"])
        current_name = str(metadata["name"])
        default_branch = str(metadata["default_branch"])
        archived = bool(metadata.get("archived", False))
        source_id = f"github:{provider_id}"

        source = self._stable_source(
            source_id,
            f"https://github.com/{current_owner}/{current_name}",
            source_role,
            started_at,
        )
        repository_identity = self._stable_repository(
            source_id,
            provider_id,
            current_owner,
            current_name,
            default_branch,
            archived,
        )
        commit = self.reader.get_commit(current_owner, current_name, ref or default_branch)
        commit_sha = str(commit["sha"])
        tree_sha = str(commit["commit"]["tree"]["sha"])
        revision = self._stable_revision(source_id, commit_sha, tree_sha, started_at)

        capture_id = f"capture:{self.id_factory()}"
        artifact_records: list[Artifact] = []
        artifact_refs: list[CaptureArtifactRef] = []
        for path in normalized_paths:
            artifact_id = self._artifact_id(capture_id, path)
            try:
                data = self.reader.get_file(current_owner, current_name, path, commit_sha)
            except GitHubNotFound:
                artifact_refs.append(
                    CaptureArtifactRef(
                        artifact_id=artifact_id,
                        source_locator=path,
                        retrieval_status=RetrievalStatus.MISSING,
                    )
                )
                continue
            content_hash = self.object_store.put(data)
            media_type = self._media_type(path)
            artifact = Artifact(
                artifact_id=artifact_id,
                capture_id=capture_id,
                source_locator=path,
                content_hash=content_hash,
                media_type=media_type,
            )
            artifact_records.append(artifact)
            artifact_refs.append(
                CaptureArtifactRef(
                    artifact_id=artifact_id,
                    source_locator=path,
                    content_hash=content_hash,
                    media_type=media_type,
                    retrieval_status=RetrievalStatus.CAPTURED,
                )
            )

        manifest = CaptureManifest(
            capture_id=capture_id,
            source_revision_id=revision.source_revision_id,
            capture_policy_version=self.capture_policy_version,
            captured_at=self._aware_now(),
            artifacts=tuple(artifact_refs),
        )
        inputs_hash = self._digest_json(
            {
                "repository": f"{current_owner}/{current_name}",
                "provider_repository_id": provider_id,
                "commit_sha": commit_sha,
                "tree_sha": tree_sha,
                "paths": normalized_paths,
                "source_role": source_role.value,
                "capture_policy_version": self.capture_policy_version,
            }
        )
        outputs_hash = self._digest_json(
            [
                source.model_dump(mode="json", by_alias=True),
                repository_identity.model_dump(mode="json", by_alias=True),
                revision.model_dump(mode="json", by_alias=True),
                *[
                    artifact.model_dump(mode="json", by_alias=True)
                    for artifact in artifact_records
                ],
                manifest.model_dump(mode="json", by_alias=True),
            ]
        )
        run = PipelineRun(
            run_id=f"run:{self.id_factory()}",
            run_type=RunType.CAPTURE,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.capture_policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = GitHubCaptureResult(
            source,
            repository_identity,
            revision,
            manifest,
            tuple(artifact_records),
            run,
        )
        self.store.put_many(result.records())
        return result

    def _stable_source(
        self,
        source_id: str,
        canonical_locator: str,
        source_role: SourceRole,
        observed_at: datetime,
    ) -> Source:
        existing = self.store.get(Source, source_id)
        if existing is not None:
            if existing.source_kind != SourceKind.GITHUB_REPOSITORY:
                raise SourceMetadataDrift(f"{source_id} changed source kind")
            if existing.source_role != source_role:
                raise SourceMetadataDrift(
                    f"{source_id} is already classified as {existing.source_role.value}; "
                    f"requested {source_role.value}"
                )
            if existing.canonical_locator != canonical_locator:
                raise SourceMetadataDrift(
                    f"{source_id} canonical locator changed; M2 identity evolution is required"
                )
            return existing
        return Source(
            source_id=source_id,
            source_kind=SourceKind.GITHUB_REPOSITORY,
            source_role=source_role,
            canonical_locator=canonical_locator,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
        )

    def _stable_repository(
        self,
        source_id: str,
        provider_id: str,
        owner: str,
        name: str,
        default_branch: str,
        archived: bool,
    ) -> RepositoryIdentity:
        existing = self.store.get(RepositoryIdentity, source_id)
        if existing is not None:
            current = (
                existing.provider_repository_id,
                existing.owner,
                existing.name,
                existing.default_branch,
                existing.archived,
            )
            incoming = (provider_id, owner, name, default_branch, archived)
            if current != incoming:
                raise RepositoryIdentityDrift(
                    f"{source_id} repository metadata changed; "
                    "M2 rename/archive handling is required"
                )
            return existing
        return RepositoryIdentity(
            source_id=source_id,
            provider_repository_id=provider_id,
            owner=owner,
            name=name,
            default_branch=default_branch,
            aliases=(),
            archived=archived,
        )

    def _stable_revision(
        self,
        source_id: str,
        commit_sha: str,
        tree_sha: str,
        observed_at: datetime,
    ) -> SourceRevision:
        revision_id = f"{source_id}@{commit_sha}"
        existing = self.store.get(SourceRevision, revision_id)
        if existing is not None:
            if (
                existing.source_id,
                existing.commit_sha,
                existing.tree_sha,
            ) != (source_id, commit_sha, tree_sha):
                raise RepositoryIdentityDrift(f"revision identity collision: {revision_id}")
            return existing
        return SourceRevision(
            source_revision_id=revision_id,
            source_id=source_id,
            commit_sha=commit_sha,
            tree_sha=tree_sha,
            observed_at=observed_at,
        )

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("capture clock must return timezone-aware datetimes")
        return value

    @staticmethod
    def _split_repository(repository: str) -> tuple[str, str]:
        parts = repository.strip().split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("repository must be in owner/name form")
        return parts[0], parts[1]

    @staticmethod
    def _normalize_paths(paths: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        normalized: set[str] = set()
        for raw in paths:
            path = raw
            if (
                not path
                or "\x00" in path
                or path.startswith("/")
                or path.endswith("/")
                or any(part in {"", ".", ".."} for part in path.split("/"))
            ):
                raise ValueError(f"invalid repository path: {raw!r}")
            normalized.add(path)
        if not normalized:
            raise ValueError("at least one repository file path is required")
        return tuple(sorted(normalized))

    @staticmethod
    def _artifact_id(capture_id: str, path: str) -> str:
        digest = hashlib.sha256(f"{capture_id}\0{path}".encode("utf-8")).hexdigest()
        return f"artifact:{digest}"

    @staticmethod
    def _media_type(path: str) -> str:
        return _MEDIA_TYPES.get(
            PurePosixPath(path).suffix.lower(),
            "application/octet-stream",
        )

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
