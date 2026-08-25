# CSD-Foundry temporal frontier reconciliation checkpoint

## Result

The first live `temporal_change_reconciliation` probe succeeded against the frozen CSD-Foundry frontier case.

- LemmaMind workflow run: `32870568177`
- live branch head: `f8134bf5718b861c952fbe4fa74090be03a47227`
- offline regression suite: **101 passed**
- live reconciliation step: **success**
- D5 analysis anchor: `aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7`
- qualification revision: `2d910f3ff83f061409ca9d8f2e3709fde7c13f6e`

## Reconciled source state

The live probe recovered and checked:

```text
PR #115 merged = true
issue #37 state = open
PR #117 state = open
PR #117 draft = true
PR #117 base SHA = aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7
PR #117 head SHA = 2d910f3ff83f061409ca9d8f2e3709fde7c13f6e
```

The base/head relationship matters: the still-open qualification work is explicitly layered on the D5 merge revision rather than being unrelated repository churn.

Provider event history independently established:

```text
closed   2026-08-24T21:31:54Z
reopened 2026-08-24T21:36:12Z
```

## Interpretation candidate

The live service constructed the golden semantic equivalent:

> The implementation frontier and the evidentiary closure frontier are distinct; D1-D5 production implementation can be complete while independent integrated qualification remains pending.

The runtime record remains `candidate`. The golden case's reviewed/validated labels are evaluation targets, not permissions for the runtime to self-promote.

## Belief revision

The probe first persisted the historical stronger conclusion:

> Issue #37 can close because the D1-D5 implementation frontier is complete.

It then created the narrower superseding candidate:

> The earlier conclusion that #37 could close was too strong and should be superseded by the narrower conclusion that implementation is landed but qualification and closure remain open.

The prior Observation remained byte-for-byte unchanged in persistence. The new Observation records `supersedes_observation_id`; it does not mutate or delete the prior record.

```text
prior conclusion
      │
      │ preserved
      ↓
newer process + revision + event evidence
      │
      ↓
superseding candidate Observation
```

## Fail-closed semantics

Temporal reconciliation requires:

- explicit current-state `EvidenceFact` expectations;
- every validated temporal fact to also be an explicit Observation support;
- event and timestamp facts to describe the same provider event;
- one ordered event-history artifact for the declared transition;
- strictly increasing provider timestamps;
- same logical claim identity for supersession;
- same Source identity through `ObservationConstructionServiceV2`;
- no second competing superseding branch from the same prior Observation in this M0 policy.

## Readiness effect

`temporal_change_reconciliation` moves from `missing` to `implemented`.

The hard-case matrix is now:

```text
3 ready / 0 blocked / 1 deferred
```

`csd-foundry-frontier` is now **ready**. The remaining deferred `private-actions-pattern` case is intentionally cross-repository and should advance only through a proper Pattern layer, not by weakening source-level Observation constraints.
