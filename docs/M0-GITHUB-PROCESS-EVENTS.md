# M0 — GitHub process event history

## Purpose

Current issue and pull-request snapshots answer **what GitHub reports now**. They cannot prove a historical transition such as:

```text
open → closed → reopened
```

`github_process_events.py` adds a separate durable evidence path for provider issue events. The distinction is intentional: mutable current state and historical event records are different evidence classes and must not be conflated.

## Capture model

For a selected issue, LemmaMind reads the GitHub issue-events endpoint and stores a content-addressed canonical artifact at:

```text
$github/issue/<number>/events
```

The artifact is attached to a `CaptureManifest` whose `source_revision_id` is the repository analysis anchor. That anchor identifies the analysis generation; it does **not** claim that GitHub process events are determined by the Git commit.

Canonical event metadata includes:

```text
provider_id
node_id
event
created_at
actor_login
commit_id?
commit_url?
```

Events are sorted deterministically by provider timestamp and provider ID before storage.

## Pagination

The REST reader uses `per_page=100` and requests additional pages until GitHub returns a short page. If the configured page ceiling is exhausted, capture fails closed instead of silently preserving a truncated history.

## Epistemic classification

Provider event metadata is emitted as `EvidenceFact`.

For example:

```text
$github/issue/37/events#/events/7/event = "closed"
$github/issue/37/events#/events/8/event = "reopened"
```

The evidence layer does not convert those facts into a higher-level frontier conclusion.

## Live CSD validation

One-time read-only workflow run `32869669389` validated the accepted path against `ElephantRock/CSD-Foundry` issue #37 at analysis anchor:

```text
aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7
```

The run passed **97 offline tests** and recovered **9 provider events / 54 deterministic facts**.

The state events were:

```text
closed
  provider event: 29940854834
  timestamp:      2026-08-24T21:31:54Z

reopened
  provider event: 29941032785
  timestamp:      2026-08-24T21:36:12Z
```

This directly proves the close→reopen history required by the frozen CSD golden case.

## Boundary to temporal reconciliation

Observed event history is an input to change intelligence, not change intelligence itself.

The remaining CSD question is:

```text
D5 implementation landed
+ issue was prematurely closed then reopened
+ P3.7 qualification remains open
        ↓
what should now be believed about the frontier?
```

That answer belongs to `temporal_change_reconciliation`. It must preserve the historical stronger conclusion and create explicit supersession/belief-revision lineage rather than rewrite old evidence or observations.
