# M0 — Durable GitHub issue / pull-request process evidence

## Status

**Implemented and live-validated for current issue/PR snapshots.**

This slice adds durable deterministic evidence for selected GitHub issues and pull requests without pretending that mutable process state is a property of a Git commit.

## Why process state is different from Git state

A `SourceRevision` answers which repository revision anchored an analysis generation. GitHub issue and pull-request state can change independently of that revision:

- an issue can close or reopen without a repository commit;
- a PR can move between draft/open/closed states independently of the base branch;
- requested reviewers, labels, and provider timestamps can change without changing source files;
- a PR's head/base/merge SHAs are process metadata that must be recorded explicitly.

Therefore the M0 model is:

```text
SourceRevision
    ↓
analysis-generation anchor
    ↓
CaptureManifest
    ↓
immutable process snapshot artifact
    ↓
EvidenceFact / SourceAssertion
```

The arrow does **not** mean “this issue/PR state was historically determined by this commit.”

## Capture contract

`GitHubProcessCaptureService` accepts explicit typed references:

```text
ProcessRef(ISSUE, number)
ProcessRef(PULL_REQUEST, number)
```

and captures one canonical JSON artifact per selected resource.

Stable locators are:

```text
$github/issue/<number>
$github/pull/<number>
```

Each capture is content-addressed and append-only. If mutable provider state changes later, a later capture gets a new immutable artifact/content hash; the previous snapshot remains unchanged.

### Issue snapshot

The v1 canonical issue subset includes provider identity, repository identity, number, URL, state/state-reason, author, association, lock/comment/label/assignee metadata, and provider creation/update/closure timestamps.

### Pull-request snapshot

The v1 canonical PR subset includes provider identity, repository identity, number, URL, state, draft/merged state, merge commit SHA, author, labels/reviewers, head/base refs and SHAs, commit/file/addition/deletion counts, and provider creation/update/closure/merge timestamps.

## Evidence contract

Deterministic provider/process metadata becomes `EvidenceFact` with exact JSON-style locators, for example:

```text
$github/issue/37#/state
$github/issue/37#/updated_at
$github/pull/117#/draft
$github/pull/117#/head/sha
$github/pull/117#/base/sha
```

Authored title/body text remains `SourceAssertion`:

```text
$github/issue/37#title
$github/issue/37#body
$github/pull/117#title
$github/pull/117#body
```

The extractor never promotes authored claims into deterministic facts merely because they appear in a GitHub process object.

## Live CSD-Foundry validation

Workflow run `32862376557` validated the expanded slice against real CSD-Foundry process state using read-only permissions.

- offline suite: **75 passed**
- live process capture/extraction: **success**
- analysis anchor: `aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7`
- captured: issue `#37`, merged PR `#115`, open/draft PR `#117`
- deterministic process metadata facts: **73**
- authored title/body assertions: **6**

Observed snapshot:

```text
issue #37
  state = open

PR #115
  state = closed
  merged = true
  merge_commit_sha = aa2f1a79...
  body mentions #37

PR #117
  state = open
  draft = true
  head_sha = 2d910f3...
  base_sha = aa2f1a79...
```

The stable checkpoint is preserved under `eval/pilot/process-reports/csd-issue-pr-v1.{json,md}`.

## What this closes

The hard-case readiness capability:

```text
github_issue_pr_evidence
```

moves from `missing` to `implemented`.

This means LemmaMind can now preserve current issue/PR state and authored process text as durable evidence rather than relying on a transient GitHub UI read.

## What this does not close

Current snapshots cannot prove process history such as:

```text
issue #37
closed
  ↓
later reopened
```

That requires a distinct capability:

```text
github_process_event_history
```

Likewise, current snapshots do not by themselves produce the CSD temporal conclusion that implementation completion and evidentiary closure are separate frontiers. That remains:

```text
temporal_change_reconciliation
```

And they do not reconstruct cancelled/zero-step GitHub Actions executions. That remains:

```text
github_workflow_run_evidence
```

## Security / authority boundary

This path is read-only. It performs no issue edits, PR edits, reviews, merges, reruns, or repository writes. Captured process text is untrusted source material and is stored/interpreted under the same evidence boundaries as repository content.

## Next measured acquisition slice

The readiness matrix now points next to **durable workflow-run/job/step evidence** because it is required by both the Resonance-World execution-integrity case and the private-repository Actions pattern.
