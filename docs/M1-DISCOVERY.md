# M1 — Curated Discovery Lineage

## Purpose

M1 records **why and when a candidate entered LemmaMind** before repository-registry policy, capture depth, evidence extraction, or reasoning are applied.

The durable lineage is:

```text
DiscoveryChannel
       ↓
DiscoveryRun
       ↓
DiscoveryHit
       ↓
raw discovered locator
       └── optional Source link when already resolved
```

A domain `DiscoveryRun` is bound to the existing generic `PipelineRun(run_type=discovery)` for execution provenance, policy version, timestamps, and input/output hashes.

## Contracts

### `DiscoveryChannel`

A stable configured entry point such as:

- manual watchlist;
- GitHub stars;
- saved search.

Only the **manual watchlist adapter** is implemented in this slice. The enum reserves the roadmap channel classes without claiming their adapters exist.

### `DiscoveryRun`

One immutable execution of one channel. It records:

- channel identity;
- associated `PipelineRun`;
- observation time;
- hit count.

Zero-hit runs are valid. A future saved search may execute successfully and find nothing.

### `DiscoveryHit`

One ordered raw result from a channel. It always preserves:

- the exact channel-local locator;
- the run that produced it;
- its ordinal position.

`source_id` is optional by design.

## M1 / M2 boundary

The first implementation briefly required every discovery candidate to already map to a `Source`. That made M1 circular with M2: a system cannot discover something new if canonical identity must already exist.

The corrected boundary is:

```text
M1
raw DiscoveryHit
(owner/name, URL, provider result, ...)
        ↓
M2
canonical identity resolution / rename / transfer / fork policy
        ↓
Source / RepositoryIdentity
```

When a Source is already known, a `DiscoveryHit` may carry its `source_id` immediately. The service validates that any supplied Source link actually exists. When identity is not yet known, the hit remains durable with `source_id=null`; later M2 work should add the explicit resolution/evolution relation rather than rewriting the historical hit.

This preserves historical discovery evidence and roadmap ordering.

## Duplicate policy

Within one discovery run:

- the same raw locator may occur only once;
- the same already-resolved Source may occur only once;
- different unresolved locators remain distinct because M1 does not guess whether they are aliases.

Alias/rename reconciliation belongs to M2.

## Manual watchlist adapter

`manual_watchlist.py` parses the configured YAML without contacting GitHub. It records:

- watchlist path;
- SHA-256 of the exact watchlist bytes;
- watchlist version;
- pilot ID when present;
- ordered repository count;
- one `DiscoveryHit` per repository entry.

The adapter rejects malformed YAML, invalid `owner/name` locators, and duplicate repository entries.

The frozen `pilot/watchlist.yaml` currently contains **13 ordered repositories**. The regression suite verifies both modes:

```text
watchlist → 13 unresolved raw hits
```

and, when M2-resolved Source mappings are supplied:

```text
watchlist → 13 hits linked to 13 existing Sources
```

Partial resolution is also valid; unresolved hits are preserved instead of dropped.

## Epistemic boundary

Discovery is not evidence that a repository is good, relevant, correct, owned, or safe.

A `DiscoveryHit` does **not** establish:

- source role;
- repository relationship;
- current revision;
- architecture;
- materiality;
- trust;
- evidence truth;
- reasoning eligibility.

It only establishes that a configured channel surfaced a locator during a specific versioned run.

## Validation

Temporary branch run `32877853029` exercised the corrected M1/M2 boundary and complete repository regression suite:

```text
121 passed
```

The temporary branch workflow is removed before merge; normal PR CI remains the authoritative final gate.

## Scope still deferred

This slice does not implement:

- GitHub stars ingestion;
- saved-search execution;
- broad GitHub discovery;
- M2 rename/transfer/fork resolution;
- tracking levels;
- discovery ranking;
- materiality or triage;
- automatic capture scheduling.

The next V1 foundation step after this slice should be the minimal M2 repository-registry resolution/evolution contract needed to connect unresolved discovery hits to stable Sources without mutating discovery history.
