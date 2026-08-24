# LemmaMind M0 — Implementation Slice 1

## Scope

This slice implements only the contracts justified by the completed M−1 corpus. It does not add discovery automation, repository crawling, embeddings, autonomous reasoning, pattern mining, synthesis, or a user interface.

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
3. reusing the same typed identity with different content raises `RecordConflict`.

This protects immutable evidence/provenance identities while keeping the physical schema easy to migrate as the ontology develops.

## Contract invariants enforced now

The first implementation rejects several states that would violate pilot conclusions:

- `last_seen_at` before `first_seen_at`;
- captured artifacts without a content hash and media type;
- `READ_ONLY` repository relationships that claim direct write authority;
- `OWNED` relationships without write authority;
- `no_action` recommendations that claim repository modification is required;
- source evidence classes (`ObservedFact`, `SourceAssertion`) represented as derived `Observation` epistemic types;
- malformed Git commit/tree identities and SHA-256 content digests.

## Golden-corpus regression contract

`tests/test_golden_corpus.py` binds M0 to the M−1 evaluation corpus rather than to synthetic examples alone. It requires:

- the five external validation cases to remain present;
- every repository relationship type in the corpus to be representable by the M0 relationship enum;
- every expected observation epistemic type and validation state to be representable by M0;
- evidence classes to remain separated into `ObservedFact` or `SourceAssertion`;
- source revisions and repository identities to retain explicit source addressing.

The golden cases remain evaluation fixtures, not production database rows.

## CI

`.github/workflows/test.yml` runs the package and regression tests on pull requests and pushes to `main` using Python 3.11.

## Deferred by design

Still out of scope:

- source acquisition and GitHub API clients;
- capture execution;
- deterministic extractors;
- change intelligence;
- architecture profiles;
- vector or embedding representations;
- model calls;
- patterns, tensions, insights, or promoted knowledge;
- ranking/recommendation;
- graph databases;
- distributed workers.

## Next gate

This slice is acceptable when:

1. package installation succeeds in CI;
2. contract invariant tests pass;
3. SQLite append-only round trips pass;
4. the complete M−1 golden corpus passes compatibility tests;
5. no deferred platform capability is introduced accidentally.

After that, the next M0 slice should implement the first real deterministic path:

```text
GitHub repository metadata
        ↓
Source + RepositoryIdentity
        ↓
SourceRevision
        ↓
CaptureManifest + Artifact
```

That path should remain read-only and reproducible before deterministic evidence extractors are added.
