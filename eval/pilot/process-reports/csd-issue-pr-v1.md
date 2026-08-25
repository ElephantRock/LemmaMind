# CSD-Foundry GitHub issue/PR process evidence checkpoint

This checkpoint validates LemmaMind's first durable GitHub **process-state** acquisition path against real issue and pull-request payloads.

## Live execution

- Workflow run: `32862376557`
- Branch head: `6c271e9f95ba198cac4defb65cb059668e6eea8b`
- Offline regression suite: **75 passed**
- Live CSD issue/PR capture: **success**
- Permissions: read-only `contents`, `issues`, `metadata`, and `pull-requests`
- Repository analysis anchor: `aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7`
- Stable source revision ID: `github:1318635781@aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7`

## Captured process resources

- `$github/issue/37`
- `$github/pull/115`
- `$github/pull/117`

The capture emitted **73** deterministic metadata `EvidenceFact` records and **6** authored title/body `SourceAssertion` records.

## Current snapshot evidence

### Issue #37

- state: `open`
- title: `Implement v0.5-D governed registries`
- provider `updated_at`: `2026-08-24T21:36:20Z`

### PR #115

- state: `closed`
- merged: `true`
- merge commit: `aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7`
- head SHA: `955e1991cad1c74ddf15ea385c375a3d814d9cc3`
- title: `P3.6: D5 atomic multi-registry temporal integration`
- authored body explicitly references issue `#37`

### PR #117

- state: `open`
- draft: `true`
- head SHA: `2d910f3ff83f061409ca9d8f2e3709fde7c13f6e`
- base SHA: `aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7`
- provider `updated_at`: `2026-08-15T22:06:50Z`
- title: `P3.7: Phase-3 integrated qualification and closure`

## Mutable-state model

Issue and pull-request state is **not** modeled as a property of a Git commit.

`SourceRevision` is the repository analysis anchor used to attach this process snapshot to a reproducible analysis generation. The snapshot independently records provider IDs, timestamps, state, and PR head/base/merge SHAs. A later capture creates another immutable content-addressed snapshot rather than overwriting this one.

This distinction is necessary because an issue can close or reopen while repository HEAD remains unchanged, and a PR can change draft/review/process state independently of the base commit.

## Epistemic boundary

This checkpoint proves that LemmaMind can durably capture and deterministically extract the **current observed** issue/PR snapshot needed for CSD frontier reasoning.

It does **not** prove the historical statement that issue #37 was closed and later reopened. That requires process event/timeline history. It also does not itself infer that implementation completion and evidentiary closure are different frontiers; that remains temporal/change-intelligence reasoning over evidence.

Accordingly:

- `github_issue_pr_evidence` can move to **implemented**;
- `github_process_event_history` remains **missing**;
- `temporal_change_reconciliation` remains **missing**.
