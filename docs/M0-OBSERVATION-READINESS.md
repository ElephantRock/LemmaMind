# M0 — Hard-case Observation readiness

## Status

The first executable `Evidence → Observation` slice is merged. This document records what the harder frozen cases show about the next boundary.

The key result is that not every golden case should be made to pass by broadening `Observation` until it can hold arbitrary synthesis. The hard cases separate four distinct needs: source-local observation, temporal belief revision, action/governance policy, and cross-repository pattern synthesis.

The machine-readable readiness contract is `eval/pilot/observation-readiness-v1.yaml` and is evaluated by `lemmamind.observation_readiness`.

## Observation v2 correction

`ObservationConstructionService` v1 correctly required one resolved `SourceRevision` for one source-level Observation, but it also required a superseding Observation to resolve to the exact same revision as the observation it replaced.

That second constraint was too strict. Genuine belief revision often occurs because a later revision changes what should be believed.

`ObservationConstructionServiceV2` therefore preserves:

```text
one Observation
    ↓
one resolved SourceRevision
```

while changing supersession to:

```text
same logical_claim_id
+ same Source identity
+ previous revision may differ from current revision
```

Cross-source support remains rejected.

This lets LemmaMind preserve a belief history without pretending that a later claim came from the earlier source state.

## Hard-case readiness result

Current deterministic result:

| Case | Outcome | Why |
| --- | --- | --- |
| `external-opd-source-type` | **ready** | Single-source/single-revision evidence exists, including root-tree facts and explicit `research_index` source role. |
| `csd-foundry-frontier` | **blocked** | Requires durable issue/PR evidence and temporal multi-revision frontier reconciliation. |
| `resonance-world-confirmatory` | **blocked** | Requires durable PR/workflow-run evidence and authority/governance-aware action validation. |
| `private-actions-pattern` | **deferred** | The useful claim is intentionally cross-repository and belongs to Pattern/Inference semantics rather than source-level Observation. |

Summary: **1 ready / 2 blocked / 1 deferred**.

## Why CSD is not solved by supersession alone

The CSD golden case is the canonical belief-revision example, but its frozen observations reconcile evidence from two revisions. That is more than a later source-local Observation replacing an earlier one.

The correct decomposition is:

```text
earlier source-revision Observation
        ↓
newer source-revision Observation
        ↓
explicit supersession lineage
```

plus a later temporal/change-intelligence object that can say:

```text
implementation frontier complete
!=
evidentiary closure frontier complete
```

without erasing either historical state.

Forcing both revisions into one source-level Observation would weaken provenance rather than improve coverage.

## Why private Actions remains outside Observation

The private-Actions conclusion depends on:

- matching pre-step failure signatures in ExpertOS and ExpertForge;
- repository privacy metadata;
- functioning public-repository Actions as negative controls.

That is a cross-repository inference. The existing one-revision Observation rule should reject it.

This is a positive boundary result: LemmaMind should add the later Pattern layer when justified, not turn `Observation` into a generic container for every synthesis level.

## Resonance-World implication

The Resonance-World case demonstrates that epistemic support and operational action are separate problems.

Even after the cancelled run and frozen plan are captured as evidence, the conclusion `do not blindly rerun` requires an action-policy service that can reason over:

- repository relationship;
- explicit prospective no-rerun rules;
- experiment-governance boundaries;
- separate evaluation/acceptance authority.

`ActionRecommendation` already exists as a contract, but M0 does not yet have a validation service that can prove such a recommendation respects those constraints.

## Next priorities selected by the corpus

Do not add autonomous observation generation yet.

The next justified capabilities are:

1. durable GitHub issue / pull-request evidence capture;
2. durable workflow-run / job / step evidence capture;
3. temporal change/frontier reconciliation over revision-bound observations;
4. authority-aware action-policy validation;
5. later, a cross-repository Pattern layer for cases such as private Actions.

The readiness evaluator should be rerun whenever one of those capability states changes. A case may move from `blocked` to `ready`, but `deferred` cases should move only when the correct later semantic layer exists—not because Observation constraints were weakened.

## Interpretation boundary

The readiness matrix is not a claim that the blocked cases are invalid. It records whether the current executable LemmaMind layers can represent their frozen golden intelligence with the required provenance and authority boundaries.
