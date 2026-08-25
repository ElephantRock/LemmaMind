# M2 — Repository registry and governed tracking policy

## Status

The V1 M2 core is implemented in two slices:

1. **identity/evolution** — canonical GitHub repository identity plus immutable locator history;
2. **tracking policy** — immutable tracking-level history plus deterministic operational eligibility.

The executable boundary is now:

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
RepositoryLocator*              append-only provider-state history
       ↓
RepositoryTrackingAssignment*   append-only operational-policy history
       ↓
latest-effective TrackingPolicy
       ↓
capture / polling / process-history / reasoning eligibility
```

Tracking policy is operational metadata. It does not alter evidence truth, validation state, repository relationship, or authorization.

## Stable identity versus mutable provider state

For GitHub repositories, the stable identity key is GitHub's provider repository ID.

Owner/name, canonical URL, default branch, archive state, fork state, and optional fork-parent provider ID are mutable observations represented by `RepositoryLocator`.

A rename or transfer therefore produces a later locator for the same Source:

```text
old-owner/repo      provider id 42
        ↓
RepositoryLocator A
        ↓
Source github:42
        ↑
RepositoryLocator B
        ↑
new-owner/renamed   provider id 42
```

Historical `DiscoveryHit`, `DiscoveryResolution`, `RepositoryLocator`, `Source`, and seed `RepositoryIdentity` records are not rewritten.

## Fork boundary

A fork is not an alternate locator for its parent.

```text
parent provider id 42  → Source github:42
fork   provider id 84  → Source github:84
```

When GitHub exposes the parent repository ID, M2 records it as `RepositoryLocator.parent_provider_repository_id`. The relation does not collapse the identities.

## Identity contracts

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

Each new identity-resolution generation is tied to `PipelineRun(run_type=registry)` provenance.

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

A manually inserted hit without its discovery lineage cannot enter the registry.

## Resolution semantics

### First unresolved hit

For a hit with `source_id=null`, provider metadata supplies the stable repository ID. If provider ID `42` has never been registered, M2 creates canonical Source `github:42`, a seed `RepositoryIdentity`, a `RepositoryLocator`, and a `DiscoveryResolution`.

The Source's `first_seen_at` is inherited from the M1 `DiscoveryRun.observed_at`, not from the later registry execution time.

### Exact replay

Resolving the same historical hit again with identical provider identity and mutable state is idempotent.

### Changed state on the same hit

A historical hit may not be re-resolved with changed mutable repository state. The attempt is rejected.

### Changed state on a later hit

A later hit with the same provider ID creates a later locator/resolution generation for the same Source. This is the supported rename/transfer/default-branch/archive evolution path.

## Registry-aware repository capture

The original M0 `GitHubCaptureService` remains fail-closed on metadata drift.

`RegistryAwareGitHubCaptureService` accepts mutable state only when the latest validated `RepositoryLocator` matches the incoming provider state and is backed by the expected registry provenance.

Once a Source has M2 locator history, an older locator cannot regain authority merely because incoming metadata happens to match the original seed identity.

## Tracking-level contract

M2 adds `RepositoryTrackingAssignment` as an immutable operational-policy history record:

- `tracking_assignment_id`
- `source_id`
- `level`
- `effective_at`
- `recorded_at`
- `assigned_by`
- `reason`
- `policy_version`
- `supersedes_tracking_assignment_id`

`assigned_by` records the governance identity supplied by the caller. The tracking service does **not** authenticate that identity and does not turn it into authorization. Authentication/authorization remains an external responsibility.

Tracking assignments are not evidence and must never be used to make a claim more or less true.

## Tracking levels

The deterministic V1 policy is:

| Level | Name | Capture depth | Polling mode | Process current/history | Reasoning eligible |
| --- | --- | --- | --- | --- | --- |
| `0` | Ignore | none | never | no / no | no |
| `1` | Metadata only | metadata | metadata | no / no | no |
| `2` | Shallow | shallow | revision | no / no | no |
| `3` | Structural | structural | revision | no / no | yes |
| `4` | Deep | deep | revision | yes / yes | yes |
| `5` | Continuous | deep | continuous | yes / yes | yes |

Artifact-class eligibility progresses as follows:

```text
0  none
1  repository metadata
2  + explicit files + commit metadata
3  + Git tree + deterministic structure
4  + current process + process history + workflow runs
5  same deep artifact classes, continuous-monitoring eligibility
```

`continuous` is a polling **mode**, not a fixed time interval. M2 intentionally does not invent polling cadence before a scheduler/budget policy exists.

## Unassigned Source behavior

A Source with no tracking assignment fails closed operationally as level `0`.

That default is **not persisted as a fabricated assignment**. Therefore these states remain distinguishable:

```text
no assignment          → effective level 0, assignment_id = null
explicit level-0 record → effective level 0, assignment_id != null
```

The distinction matters for auditability.

## Effective-time semantics

`repository-tracking.v1` accepts only immediately effective **new** assignments.

Future scheduling and backdating are rejected because they require explicit cancellation/correction semantics. Allowing them without those semantics would make an append-only timeline operationally ambiguous.

Exact replay of an existing assignment remains idempotent even when replayed later.

Historical policy queries remain supported through `latest_effective(source_id, as_of=...)`.

## History invariants

The tracking service fails closed when:

- the Source does not exist;
- a new assignment attempts future scheduling or backdating;
- one effective timestamp is reused with different assignment content;
- the tracking clock moves backward relative to existing history;
- history contains multiple records at the same latest effective timestamp.

Each accepted change links to the previously recorded assignment using `supersedes_tracking_assignment_id` while preserving that prior record unchanged.

## Policy consumers

M2 provides tracking-aware adapters rather than weakening existing services.

### Repository file capture

`TrackingAwareGitHubCaptureService` requires at least level `2` and the `explicit_files` artifact class before the existing registry-aware capture path runs.

### Current issue / pull-request snapshots

`TrackingAwareGitHubProcessCaptureService` requires deep tracking (`4` or `5`) before provider reads occur.

### Issue-event history

`TrackingAwareGitHubProcessEventCaptureService` requires deep tracking (`4` or `5`) before historical provider reads occur.

### Source-local Observation construction

`TrackingAwareObservationConstructionService` resolves support provenance to its SourceRevision and requires structural-or-deeper tracking (`3`, `4`, or `5`) **before** persisting a candidate Observation.

Tracking level makes a reasoning path eligible; it does not validate, promote, or authorize the resulting claim.

### Polling

`RepositoryTrackingService.policy_for()` exposes one deterministic `PollingMode`:

```text
never
metadata
revision
continuous
```

No polling scheduler is implemented in this slice. A future scheduler must consume this policy rather than duplicating tracking semantics.

## Persistence registration

`RepositoryTrackingAssignment` is an additive M2 contract registered with the generic contract-type registry at package import. Typed SQLite persistence therefore supports both normal typed round trips and `get_untyped()` reconstruction without changing the frozen M0 schema version.

## Validation

The first tracking implementation passed the permanent PR suite at **147 tests**.

Review then exposed a future-scheduling governance ambiguity: a scheduled promotion could become difficult to cancel safely while preserving monotonic effective history. V1 was narrowed to immediate-only assignments and the tests were revised accordingly.

The corrected tracking branch reached **148 passed**.

The test matrix covers:

- unassigned fail-closed behavior without fake history;
- all six policy levels;
- immutable append-only history;
- supersession lineage;
- historical `as_of` lookup;
- exact replay idempotence;
- same-effective-time rewrite rejection;
- future scheduling rejection;
- backdating rejection;
- generic untyped persistence reconstruction;
- repository-file capture blocked below level 2 and allowed at level 2;
- process snapshot/history gates before provider reads;
- reasoning blocked below level 3 before candidate persistence;
- reasoning allowed at level 3 while the resulting Observation remains `candidate`.

Identity/evolution validation remains non-destructive. The prior live provider checkpoint for `ElephantRock/LemmaMind` established provider repository ID `1345295505`, owner/name `ElephantRock/LemmaMind`, default branch `main`, `archived=false`, and `fork=false`. No upstream repository was renamed, transferred, archived, or forked solely for validation.

Tracking-level validation is local and deterministic; no production tracking assignment is fabricated merely to demonstrate the feature.

## M2 boundary after this slice

The V1 M2 core now covers:

- canonical provider identity;
- repeated discovery resolution;
- rename/transfer/default-branch/archive evolution;
- fork identity separation;
- current-locator enforcement for registry-aware capture;
- immutable governed tracking-level history;
- deterministic latest-effective tracking policy;
- concrete capture/process/history/reasoning gates;
- polling-mode output for a future scheduler.

Still deferred beyond this core:

- scheduler cadence and budget policy;
- automatic resolution of every discovery channel in one scheduler;
- webhook-driven provider-state observation;
- mutable `RepositoryRelationship` reconciliation inside the registry loop;
- provider-independent identity adapters beyond GitHub;
- tracking-policy UI and authenticated policy writers.

The next roadmap milestone is **M3 Revision Capture**. Existing M0 revision/capture capabilities should be reconciled to the M3 gate rather than reimplemented blindly.
