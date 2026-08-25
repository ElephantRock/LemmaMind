# M2 — Repository registry resolution and evolution

## Status

This slice implements the **identity/evolution half** of roadmap M2.

It does not complete all of M2: governed tracking levels `0–5` remain a separate M2 slice because they control capture depth, polling frequency, artifact classes, process/history evidence, and reasoning eligibility.

The implemented boundary is:

```text
DiscoveryChannel
       ↓
DiscoveryRun
       ↓
DiscoveryHit                    immutable M1 history
       ↓
DiscoveryResolution             immutable M2 resolution edge
       ↓
Source                          stable canonical identity
       ↓
RepositoryLocator*              append-only mutable provider state
```

For GitHub repositories, the stable identity key is GitHub's provider repository ID. Owner/name, canonical URL, default branch, archive state, and fork state are observations that may evolve without changing the canonical Source.

## Why M2 is a separate layer

M1 records what a discovery channel surfaced. It deliberately permits unresolved hits:

```text
DiscoveryHit(
    discovered_locator="owner/new-repo",
    source_id=None,
)
```

M1 cannot require a canonical Source before the hit exists, because that would make discovery circular with identity resolution.

M2 therefore resolves a historical hit without rewriting it:

```text
DiscoveryHit ──→ DiscoveryResolution ──→ Source
                        │
                        └──→ RepositoryLocator
```

A hit that was unresolved at discovery time remains unresolved **inside that historical M1 record**. The later resolution is represented by a new immutable edge.

## Stable identity versus mutable locator state

`RepositoryIdentity` remains the initial stable identity snapshot associated with a Source. M2 adds `RepositoryLocator` for mutable provider state.

Example rename/transfer:

```text
hit A: old-owner/repo
        ↓
RepositoryLocator A
  provider_id = 42
  owner = old-owner
  name = repo
        ↓
Source github:42

hit B: new-owner/renamed
        ↓
RepositoryLocator B
  provider_id = 42
  owner = new-owner
  name = renamed
        ↓
same Source github:42
```

The old hit, resolution, locator, Source, and seed `RepositoryIdentity` are not rewritten. Current provider state is obtained from the latest valid `RepositoryLocator` once locator history exists.

This also applies to:

- default-branch changes;
- archive/unarchive state;
- owner transfer;
- repository rename;
- repeated discovery through different channels or later runs.

## Fork boundary

A fork is not a rename or alternate locator for its parent.

GitHub gives the fork a distinct provider repository ID, therefore it receives a distinct Source:

```text
parent provider id 42  → Source github:42
fork   provider id 84  → Source github:84
```

When GitHub exposes a parent repository ID, M2 records it as `RepositoryLocator.parent_provider_repository_id`. That relation does not collapse the two identities.

## Durable contracts

### `RepositoryLocator`

One immutable observation of mutable GitHub repository state:

- `repository_locator_id`
- `source_id`
- `provider_repository_id`
- `owner`
- `name`
- `canonical_locator`
- `default_branch`
- `archived`
- `fork`
- `parent_provider_repository_id`
- `observed_at`
- `pipeline_run_id`

### `DiscoveryResolution`

One immutable resolution of one M1 hit:

- `discovery_resolution_id`
- `discovery_hit_id`
- `source_id`
- `repository_locator_id`
- `resolution_method`
- `resolver_version`
- `resolved_at`
- `pipeline_run_id`

Current GitHub resolution method:

```text
github_provider_repository_id
```

### Registry run provenance

M2 adds `PipelineRun(run_type=registry)`.

Every new locator/resolution generation is tied to a registry run with canonical input/output hashes, resolver policy version, code version, contract schema version, and timestamps.

## Required M1 provenance

Resolution fails closed unless the historical M1 chain is complete:

```text
DiscoveryChannel
       ↓
DiscoveryRun
       ↓
PipelineRun(run_type=discovery)
       ↓
DiscoveryHit
```

A manually inserted `DiscoveryHit` without its channel/run/pipeline lineage cannot enter the registry.

## Resolution semantics

### First unresolved hit

For a hit with `source_id=null`, GitHub metadata supplies the stable provider ID.

If provider ID `42` has never been registered, M2 creates:

```text
Source.source_id = github:42
RepositoryIdentity.provider_repository_id = 42
RepositoryLocator.provider_repository_id = 42
DiscoveryResolution.source_id = github:42
```

The Source's `first_seen_at` comes from the M1 `DiscoveryRun.observed_at`, not from the later registry execution time.

### Hit already linked to a Source

If M1 already knew a Source, M2 validates that Source and binds its `RepositoryIdentity` to the provider ID when needed.

If the same provider ID is already bound to another Source, resolution fails closed.

### Exact replay

Resolving the same historical hit again with the identical provider ID and mutable state is idempotent. M2 returns the existing resolution, locator, and registry run rather than creating a duplicate generation.

### Changed state on the same hit

The same historical hit may not be re-resolved with changed owner/name/default-branch/archive/fork state.

That attempt is rejected. A new provider observation requires a new discovery hit so chronology remains explicit.

### Changed state on a later hit

A later hit with the same provider ID creates a new locator/resolution generation that points to the same Source.

This is the supported rename/transfer/evolution path.

## Registry-aware capture

The original M0 `GitHubCaptureService` remains deliberately fail-closed on repository metadata drift.

M2 adds `RegistryAwareGitHubCaptureService` rather than weakening that original contract.

Its rule is:

> Once a Source has M2 locator history, a registry-aware capture must match the latest validated RepositoryLocator.

A locator can authorize capture only when:

1. it is the latest locator for that Source;
2. its incoming provider/owner/name/default-branch/archive state matches the GitHub metadata being captured;
3. its `pipeline_run_id` resolves to `PipelineRun(run_type=registry)`;
4. exactly one `DiscoveryResolution` binds that locator, Source, and registry run.

An older locator cannot become authoritative again merely because incoming metadata happens to equal the original immutable `Source` or `RepositoryIdentity` snapshot.

This was caught by regression testing: the first registry-aware implementation incorrectly accepted stale seed state after a newer locator existed. The rule above closes that hole.

## Provider-ID invariants

The registry fails closed when:

- one provider repository ID maps to multiple Sources;
- a known Source is already bound to a different provider repository ID;
- a historical hit has already been resolved to another provider ID;
- an existing resolution is missing its locator, Source, identity, or registry run;
- a resolution points to a non-registry `PipelineRun`;
- GitHub metadata omits stable identity fields;
- the discovery locator is not a single GitHub `owner/name` repository.

The provider repository ID itself is not treated as mutable identity state.

## Validation

The branch-local full suite reached **131 passed** after the registry-aware capture freshness correction.

The test matrix covers:

- unresolved hit → canonical Source creation;
- complete M1 lineage requirement;
- typed registry persistence and producing-run provenance;
- exact replay idempotence;
- same-hit state rewrite rejection;
- rename/transfer/default-branch/archive evolution via later hits;
- known-Source reuse;
- provider-ID collision rejection;
- fork identity separation and parent-provider relation;
- M0 capture remaining fail-closed without M2 history;
- capture succeeding after matching M2 history exists;
- stale older locator rejection once a newer locator exists.

Live validation is intentionally non-destructive. Through the authorized GitHub connection, `ElephantRock/LemmaMind` currently resolves to provider repository ID `1345295505`, owner/name `ElephantRock/LemmaMind`, default branch `main`, `archived=false`, and `fork=false`.

No repository was renamed, transferred, archived, or forked solely to demonstrate this feature. Those evolution semantics are covered by deterministic tests rather than by unnecessary source mutation.

See `eval/pilot/registry-reports/lemmamind-provider-identity-v1.md`.

## Deferred within M2

This slice does not yet implement:

- governed tracking-level history (`0` through `5`);
- tracking-level policy effects on capture depth or polling;
- automatic resolution of every discovery channel in one scheduler;
- webhook-driven rename/transfer observation;
- mutable repository relationship reconciliation as part of the registry loop;
- provider-independent identity adapters beyond GitHub.

The next justified V1 slice is therefore the remaining M2 **tracking-level contract and history**, not M3 reimplementation and not additional M8/M9 synthesis.
