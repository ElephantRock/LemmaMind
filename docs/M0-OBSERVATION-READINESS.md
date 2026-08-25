# M0 — Hard-case Observation readiness

## Status

The first executable `Evidence → Observation` slice and revision-aware supersession are merged. The current branch also live-validates durable GitHub issue/PR **current snapshot** evidence.

The key result remains that not every golden case should be made to pass by broadening `Observation` until it can hold arbitrary synthesis. The hard cases separate source-local observation, process/event evidence, temporal belief revision, action/governance policy, and cross-repository pattern synthesis.

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

## GitHub process-snapshot correction

Issue and pull-request state is mutable independently of Git state. `SourceRevision` is therefore an analysis-generation anchor, not a claim that issue/PR state is historically determined by the anchor commit.

The new process evidence path preserves current observed state in immutable content-addressed snapshots with provider timestamps and PR head/base/merge SHAs. Authored title/body text remains `SourceAssertion`; deterministic process metadata becomes `EvidenceFact`.

Live CSD validation captured issue #37, merged PR #115, and open/draft PR #117. See `docs/M0-GITHUB-PROCESS-EVIDENCE.md` and `eval/pilot/process-reports/csd-issue-pr-v1.*`.

## Hard-case readiness result

Current deterministic result remains:

| Case | Outcome | Current blocker boundary |
| --- | --- | --- |
| `external-opd-source-type` | **ready** | None at the source-level Observation layer. |
| `csd-foundry-frontier` | **blocked** | Current issue/PR snapshots now exist; close→reopen event history and temporal multi-revision reconciliation are still missing. |
| `resonance-world-confirmatory` | **blocked** | Issue/PR snapshots now exist; durable workflow-run evidence and authority/governance-aware action validation remain missing. |
| `private-actions-pattern` | **deferred** | Workflow evidence is missing, and the useful claim intentionally belongs to the later cross-repository Pattern layer. |

Summary: **1 ready / 2 blocked / 1 deferred**.

## Why CSD is still blocked

Current snapshots now recover important frontier evidence:

```text
issue #37: open
PR #115: closed + merged
PR #117: open + draft
```

and PR #117's base SHA is the D5 merge commit while its head is the separate qualification revision.

But the frozen golden case also says issue #37 was previously closed and later reopened. A current snapshot cannot prove that transition. The acquisition gap is now explicitly:

```text
github_process_event_history
```

Even after event history exists, the higher-level conclusion:

```text
implementation frontier complete
!=
evidentiary closure frontier complete
```

still belongs to:

```text
temporal_change_reconciliation
```

Forcing historical events or multi-revision reconciliation into one source-level Observation would weaken provenance.

## Why private Actions remains outside Observation

The private-Actions conclusion depends on matching pre-step failure signatures in ExpertOS and ExpertForge, repository privacy metadata, and functioning public-repository Actions as negative controls.

That is a cross-repository inference. The one-revision Observation rule should continue rejecting it. LemmaMind should add the later Pattern layer when justified rather than turn `Observation` into a generic container for every synthesis level.

## Resonance-World implication

The Resonance-World case demonstrates that epistemic support and operational action are separate problems.

Current issue/PR snapshot evidence is no longer the blocker. The remaining acquisition gap is durable workflow-run/job/step evidence for the cancelled confirmatory execution. After that, the conclusion `do not blindly rerun` still requires an action-policy service that can reason over repository relationship, prospective no-rerun rules, experiment governance, and separate evaluation/acceptance authority.

`ActionRecommendation` already exists as a contract, but M0 does not yet have a validation service that can prove such a recommendation respects those constraints.

## Next priorities selected by the corpus

Do not add autonomous observation generation yet.

The next justified capabilities are:

1. **durable workflow-run / job / step evidence capture** — shared prerequisite for Resonance-World and private-Actions;
2. GitHub issue/PR event-history capture — required for the CSD close→reopen history;
3. temporal change/frontier reconciliation over revision-bound observations;
4. authority-aware action-policy validation;
5. later, cross-repository Pattern semantics.

The readiness evaluator should be rerun whenever one of those capability states changes. A case may move from `blocked` to `ready`, but `deferred` cases should move only when the correct later semantic layer exists—not because Observation constraints were weakened.

## Interpretation boundary

The readiness matrix is not a claim that the blocked cases are invalid. It records whether the current executable LemmaMind layers can represent their frozen golden intelligence with the required provenance and authority boundaries.
