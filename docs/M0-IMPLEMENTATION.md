# LemmaMind M0 — Implementation Status

## Scope

M0 implements only the contracts and deterministic evidence spine justified by the completed M−1 corpus. It does not add broad discovery automation, embeddings, autonomous reasoning, pattern mining, synthesis, or a user interface.

Three executable slices are now defined:

1. **Core contracts + persistence**
2. **Deterministic read-only GitHub capture**
3. **Deterministic artifact evidence extraction**

## Executable contracts

`src/lemmamind/contracts.py` implements the M0 contract set selected in `docs/M0-CONTRACTS.md`:

- `Source`
- `RepositoryIdentity`
- `SourceRevision`
- `CaptureManifest`
- `Artifact`
- `EvidenceFact`
- `SourceAssertion`
- `Observation`
- `ObservationSupport`
- `PipelineRun`
- `RepositoryRelationship`
- `ActionRecommendation`
- `ReviewDecision`

All persisted contracts share the schema identifier `lemmamind.m0.v1` and use strict, immutable Pydantic models (`extra=forbid`, `frozen=true`).

## Concrete v1 identity additions

The conceptual contract document describes the minimum information content. The executable representation adds a few persistence identities needed to store records independently:

- `ObservationSupport.support_edge_id`
- `RepositoryRelationship.relationship_id`
- `EvidenceFact.run_id`
- `SourceAssertion.run_id`
- `ActionRecommendation.created_at`

These additions do not create new ontology layers; they make provenance edges and operational records durable and independently addressable.

## Persistence decision

M0 uses a single append-only SQLite table for validated contract payloads:

```text
(contract_type, record_id)
        ↓
schema_version
canonical JSON payload
payload SHA-256
stored_at
```

The choice is deliberate. M−1 justifies durable typed records, immutability, reproducibility, and versioning, but it does not yet justify a heavily normalized relational schema or graph database.

Insertion semantics are:

1. a new typed identity is inserted;
2. an identical re-insert is idempotent;
3. reusing the same typed identity with different content raises `RecordConflict`;
4. `put_many()` is transactional, so a conflict rolls back the entire batch.

## Deterministic GitHub capture

`src/lemmamind/github.py` and `src/lemmamind/objects.py` implement the first real source path:

```text
GitHub repository metadata
        ↓
Source + RepositoryIdentity
        ↓
resolved commit + tree SHA
        ↓
SourceRevision
        ↓
explicit files read at commit SHA
        ↓
SHA-256 content-addressed object store
        ↓
CaptureManifest + Artifact
        ↓
PipelineRun
```

Important constraints:

- only read operations are exposed;
- a branch/tag/ref is resolved once, then all file reads use the exact commit SHA;
- captured bytes are stored by digest, never by remote source path;
- repository content is never executed;
- missing paths are represented explicitly in the manifest;
- source role is caller-supplied and is never inferred from repository content;
- stable `Source`, `RepositoryIdentity`, and `SourceRevision` records are reused across repeat captures;
- repository metadata drift is rejected until M2 provides rename/transfer/archive history.

See `docs/M0-CAPTURE.md` for the detailed trust and identity boundary.

## Deterministic evidence extraction

`src/lemmamind/extraction.py` consumes persisted captures and emits only source-addressed `EvidenceFact` and `SourceAssertion` records plus an extraction `PipelineRun`.

The initial extractor set is intentionally small:

- artifact-path facts: basename, suffix, depth, top-level segment;
- selected `pyproject.toml` structural fields;
- selected `package.json` structural fields;
- Markdown prose paragraphs preserved as explicit `SourceAssertion` records with line ranges.

The path extractor describes each captured artifact only. It does **not** claim complete repository structure because the capture policy still acquires explicit paths rather than a recursive tree.

Before parsing, extraction verifies that an `Artifact` agrees with its `CaptureManifest` reference on capture ID, locator, content hash, and media type. Content bytes are reverified by the content-addressed store on read.

Malformed `pyproject.toml` / `package.json` input fails closed. A source assertion remains a source assertion; extraction does not promote source prose to observed fact.

See `docs/M0-EXTRACTION.md` for detailed extractor semantics and the epistemic boundary.

## Contract invariants enforced now

The implementation rejects states that would violate pilot conclusions, including:

- `last_seen_at` before `first_seen_at`;
- captured artifacts without content hash + media type;
- `READ_ONLY` relationships claiming direct write authority;
- `OWNED` relationships without write authority;
- `no_action` recommendations that require repository modification;
- source evidence classes represented as derived observation types;
- malformed Git commit/tree identities and SHA-256 content digests;
- capture paths containing parent traversal;
- silent repository identity/source-role drift across captures;
- manifest/artifact metadata mismatches during extraction;
- captured manifest entries without corresponding `Artifact` records;
- malformed structured manifests producing partial persisted evidence.

## Golden-corpus regression contract

`tests/test_golden_corpus.py` binds M0 to the M−1 evaluation corpus rather than to synthetic examples alone. It requires:

- the five external validation cases to remain present;
- repository relationship types to remain representable;
- expected observation epistemic/validation values to remain representable;
- evidence classes to remain separated into `ObservedFact` or `SourceAssertion`;
- source revisions and repository identities to retain explicit source addressing.

The golden cases remain evaluation fixtures, not production database rows.

Capture-specific tests require exact revision pinning, repeat-capture identity stability, explicit missing-file records, byte integrity, drift rejection, deterministic media typing, and atomic persistence.

Extraction-specific tests require exact artifact provenance, manifest parsing, Markdown line provenance, source-assertion separation, fail-closed malformed input, and equal semantic output hashes across repeat runs.

## CI

`.github/workflows/test.yml` runs the package and regression tests on pull requests and pushes to `main` using Python 3.11.

## Deferred by design

Still out of scope:

- broad repository discovery/crawling;
- recursive repository tree capture;
- releases, PRs, issues, or commit-message ingestion;
- LFS and submodule traversal;
- repository rename/transfer/archive history;
- lockfile resolution and package installation;
- language AST/semantic source-code extraction;
- change intelligence;
- architecture profiles;
- vector or embedding representations;
- model calls;
- observations generated by model reasoning;
- patterns, tensions, insights, or promoted knowledge;
- ranking/recommendation;
- graph databases;
- distributed workers.

## Current gate

The deterministic extraction slice is acceptable when:

1. package installation and all existing tests remain green;
2. evidence records bind to the exact captured artifact;
3. machine-readable manifest facts are deterministic;
4. Markdown prose remains a `SourceAssertion`, not an `EvidenceFact`;
5. line locators remain exact and stable;
6. malformed structured input fails before evidence persistence;
7. repeat extraction produces equal semantic outputs/`outputs_hash` under the same policy;
8. missing capture entries are not fabricated into artifact evidence;
9. the complete M−1 golden corpus remains green;
10. no captured source content is executed.

After that, the next M0 validation step should run **capture + extraction against selected pinned pilot artifacts** and measure whether the deterministic evidence is sufficient to reconstruct the expected golden observations manually. That evaluation should identify the smallest additional deterministic extractors actually required before any reasoning layer is introduced.
