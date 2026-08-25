# LemmaMind M0 — Implementation Status

## Scope

M0 implements only the contracts and deterministic evidence spine justified by the completed M−1 corpus. It does not add broad discovery automation, embeddings, autonomous reasoning, pattern mining, synthesis, or a user interface.

Two executable slices are now defined:

1. **Core contracts + persistence**
2. **Deterministic read-only GitHub capture**

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
4. `put_many()` is transactional, so a conflict rolls back the entire capture batch.

This protects immutable evidence/provenance identities while keeping the physical schema easy to migrate as the ontology develops.

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

## Contract invariants enforced now

The implementation rejects several states that would violate pilot conclusions:

- `last_seen_at` before `first_seen_at`;
- captured artifacts without a content hash and media type;
- `READ_ONLY` repository relationships that claim direct write authority;
- `OWNED` relationships without write authority;
- `no_action` recommendations that claim repository modification is required;
- source evidence classes (`ObservedFact`, `SourceAssertion`) represented as derived `Observation` epistemic types;
- malformed Git commit/tree identities and SHA-256 content digests;
- capture paths containing parent traversal;
- silent repository identity changes across captures;
- silent source-role or canonical-locator changes across captures.

## Golden-corpus regression contract

`tests/test_golden_corpus.py` binds M0 to the M−1 evaluation corpus rather than to synthetic examples alone. It requires:

- the five external validation cases to remain present;
- every repository relationship type in the corpus to be representable by the M0 relationship enum;
- every expected observation epistemic type and validation state to be representable by M0;
- evidence classes to remain separated into `ObservedFact` or `SourceAssertion`;
- source revisions and repository identities to retain explicit source addressing.

The golden cases remain evaluation fixtures, not production database rows.

Capture-specific tests additionally require exact revision pinning, repeat-capture identity stability, explicit missing-file records, content-addressed byte integrity, metadata-drift rejection, and atomic persistence.

## CI

`.github/workflows/test.yml` runs the package and regression tests on pull requests and pushes to `main` using Python 3.11.

## Deferred by design

Still out of scope:

- broad repository discovery/crawling;
- recursive repository tree capture;
- releases, PRs, issues, or commit-message ingestion;
- LFS and submodule traversal;
- repository rename/transfer/archive history;
- deterministic evidence extractors;
- change intelligence;
- architecture profiles;
- vector or embedding representations;
- model calls;
- patterns, tensions, insights, or promoted knowledge;
- ranking/recommendation;
- graph databases;
- distributed workers.

## Current gate

The deterministic capture slice is acceptable when:

1. package installation succeeds in CI;
2. contract and storage tests remain green;
3. every artifact read is pinned to the resolved commit SHA;
4. captured bytes round-trip through the content-addressed object store;
5. repeat captures reuse stable identities but create new capture/run identities;
6. missing paths remain explicit in `CaptureManifest`;
7. metadata/source-role drift fails loudly;
8. batch conflicts roll back atomically;
9. the complete M−1 golden corpus remains green;
10. no deferred platform capability is introduced accidentally.

After that, the next M0 slice should implement **deterministic evidence extraction from captured artifacts**. It should begin with a small number of inspectable parsers (for example repository tree/manifests/README assertions) and produce only `EvidenceFact` or `SourceAssertion` records with exact locators and extractor/run versions.
