# LemmaMind M0 — Deterministic GitHub Capture

## Scope

This slice implements the first real read-only source path:

```text
GitHub repository metadata
        ↓
Source + RepositoryIdentity
        ↓
exact commit + tree
        ↓
SourceRevision
        ↓
explicit file capture at commit SHA
        ↓
content-addressed bytes
        ↓
CaptureManifest + Artifact
        ↓
PipelineRun
```

It does **not** extract evidence, interpret code, execute repository content, recurse through repository trees, or synthesize observations.

## Components

### `GitHubRESTReader`

A minimal read-only GitHub REST client using Python's standard library.

It supports only:

- repository metadata reads;
- commit resolution;
- file reads at an explicit ref/commit;
- blob fallback when the Contents response does not inline file bytes.

The adapter exposes no GitHub write operation.

### `GitHubCaptureService`

The deterministic capture orchestrator.

For one `owner/name` repository and an explicit set of paths it:

1. reads repository metadata;
2. binds the source to GitHub's stable numeric repository ID;
3. resolves the requested ref (or default branch) once;
4. records the exact commit SHA and tree SHA;
5. uses that immutable commit SHA for every subsequent file read;
6. stores captured bytes by SHA-256;
7. emits `Artifact` and `CaptureManifest` records;
8. records a versioned `PipelineRun` with canonical input/output digests;
9. persists the contract batch atomically.

A branch name is therefore never used as the artifact read boundary after the revision has been resolved.

### `ContentAddressedFileStore`

Captured bytes are stored under a digest-derived path:

```text
objects/
└── sha256/
    └── <first two hex chars>/
        └── <remaining digest>
```

Remote repository paths never participate in the local filesystem path. This prevents untrusted source filenames from controlling local write locations.

Existing objects are re-hashed on read and idempotent write. Digest disagreement raises `ObjectCorruption`.

## Stable identity and repeat capture

The first implementation exposed an important consequence of the M0 immutable-record model.

`Source`, `RepositoryIdentity`, and `SourceRevision` are stable identities. Reconstructing them with a new observation timestamp on every capture would create a false immutable-record conflict.

The capture service therefore follows these rules:

- if a `Source` already exists, reuse it rather than advancing its timestamps;
- if the same `SourceRevision` already exists, reuse the original record;
- each actual capture receives a new `CaptureManifest` and `PipelineRun` identity;
- captured artifacts are scoped to that capture;
- a changed owner/name/default branch/archive state raises `RepositoryIdentityDrift` rather than silently rewriting history;
- a changed source role or canonical locator raises `SourceMetadataDrift` rather than silently reclassifying the source.

Repository rename/transfer/archive evolution belongs to M2. M0 fails explicitly when it encounters that boundary.

`Source.last_seen_at` is therefore **not yet maintained as a mutable registry field** by the M0 capture service. That behavior remains deferred until the registry evolution model exists.

## Source role

GitHub metadata does not determine evidentiary role.

The caller supplies `SourceRole`, for example:

```text
implementation
research_index
research_program
mixed
unknown
```

The default is `unknown`.

LemmaMind does not infer that a repository is implementation evidence merely because it contains code, nor that a repository is a research index merely because its README contains citations.

## Missing files

A 404 at the pinned revision is represented in the capture manifest as:

```text
retrieval_status = missing
content_hash = null
media_type = null
```

No `Artifact` record is created for that path.

Other GitHub API failures abort the capture rather than being silently normalized into a partial-success result.

## Transaction boundary

`SQLiteContractStore.put_many()` is transactional in this slice.

If any immutable identity conflicts with an existing record, the entire contract batch is rolled back. This prevents a capture from leaving a new artifact or manifest committed while its source/revision envelope failed validation.

Captured object bytes are content-addressed and may exist before the database transaction commits. A failed database transaction can therefore leave an unreferenced object, but never a falsely referenced or mutable object. Garbage collection is deferred.

## Trust boundary

The capture path treats repository content as untrusted bytes.

It does not:

- execute captured scripts;
- import captured Python modules;
- invoke repository build tools;
- resolve or run package-manager hooks;
- follow repository-provided instructions;
- run submodules;
- materialize remote paths directly on disk.

The next deterministic evidence-extraction slice must consume captured bytes through sanitized parsers, not execute the source repository.

## Deliberate M0 limitations

This slice intentionally does not implement:

- repository discovery or crawling;
- recursive directory capture;
- LFS object resolution;
- submodule traversal;
- releases, PRs, issues, or commit-message capture;
- rename/transfer/archive history;
- mutable source-registry timestamps;
- evidence extraction;
- diff/change intelligence;
- architecture profiling;
- embeddings or model calls;
- patterns, insights, ranking, or UI.

Those capabilities remain behind their roadmap gates.

## Example

```python
import os

from lemmamind.contracts import SourceRole
from lemmamind.github import GitHubCaptureService, GitHubRESTReader
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.storage import SQLiteContractStore

store = SQLiteContractStore("data/lemmamind.db")
objects = ContentAddressedFileStore("data/objects")
reader = GitHubRESTReader(token=os.getenv("GITHUB_TOKEN"))

capture = GitHubCaptureService(reader, store, objects)
result = capture.capture_repository(
    "CopilotKit/OpenBot",
    ["README.md", "server/src/tenant-package.ts"],
    source_role=SourceRole.IMPLEMENTATION,
    ref="d293f2331bd5ff9ba4ad17af6ac94570a157d26d",
)

print(result.revision.commit_sha)
print(result.manifest.capture_id)
```

The token is optional for public repositories but recommended when normal GitHub API rate limits would otherwise be restrictive.

## Acceptance gate

This slice is acceptable only when tests prove:

1. all artifact reads use the resolved commit SHA;
2. captured bytes round-trip through SHA-256-addressed storage;
3. repeated capture reuses stable source/revision identities without mutation;
4. each repeat capture receives a new manifest/run;
5. missing files remain explicit manifest facts;
6. identity drift fails loudly rather than overwriting M0 history;
7. parent-traversal source paths are rejected;
8. multi-record persistence rolls back atomically on conflict;
9. the existing M−1 golden corpus remains green.

After this gate, the next slice is deterministic evidence extraction from captured artifacts, beginning with small, inspectable parsers rather than LLM inference.
