# M0 — Temporal frontier reconciliation

## Purpose

Evidence acquisition can prove current process state and historical transitions, but it does not decide how a prior belief should change.

Temporal reconciliation is the source-local semantic layer that answers:

```text
What did we believe?
      +
What newer source evidence now exists?
      +
What changed over time?
      ↓
What narrower or revised conclusion is now supportable?
```

It preserves prior history rather than silently replacing it.

## Service boundary

`TemporalFrontierReconciliationService` does not generate arbitrary claims. A caller supplies:

- the prior `Observation`;
- the same `logical_claim_id`;
- the proposed superseding statement and epistemic type;
- explicit typed Observation supports;
- exact current-state `EvidenceFact` expectations;
- an ordered provider event transition.

The service validates those constraints, then delegates candidate persistence to `ObservationConstructionServiceV2`.

## Invariants

### Prior history is immutable

The prior Observation is never edited or deleted.

Belief revision is represented as:

```text
old Observation
      ↑
supersedes_observation_id
      │
new candidate Observation
```

### Current evidence stays explicit

Every fact used to validate the temporal/frontier precondition must also be an explicit support edge for the resulting Observation. The service cannot use hidden reconciliation inputs that disappear from provenance.

### Provider chronology is evidence, not prose inference

An ordered transition requires event/type and timestamp facts from the same provider event records and one event-history artifact. Timestamps must be timezone-aware and strictly increasing.

### Same-Source boundary remains

`ObservationConstructionServiceV2` still requires the current candidate's supports to resolve to one `SourceRevision` and requires the prior/current revisions to belong to the same `Source`.

Cross-repository synthesis remains outside this layer.

### Reconciliation does not review itself

New runtime Observations remain `candidate`. A live match to golden semantics does not grant `reviewed` or `validated` state.

## Live CSD-Foundry validation

Workflow run `32870568177` passed **101 offline tests** and then reconciled the frozen CSD case using live GitHub evidence.

It verified:

```text
PR #115 merged = true
issue #37 = open
PR #117 = open + draft
PR #117 base = aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7
PR #117 head = 2d910f3ff83f061409ca9d8f2e3709fde7c13f6e
issue #37 closed at 2026-08-24T21:31:54Z
issue #37 reopened at 2026-08-24T21:36:12Z
```

The live Interpretation candidate preserved the distinction:

```text
implementation frontier complete
!=
evidentiary closure frontier complete
```

The live Evaluation candidate superseded the earlier stronger closure conclusion while preserving that prior Observation unchanged.

See `eval/pilot/temporal-reports/csd-frontier-reconciliation-v1.*`.

## What remains outside this layer

Temporal reconciliation does not implement:

- cross-repository Pattern/PatternOccurrence semantics;
- prevalence measurement;
- autonomous claim generation;
- human review or promotion;
- action authorization or execution.

The remaining hard golden case (`private-actions-pattern`) therefore stays deferred until a real cross-repository Pattern layer exists.
