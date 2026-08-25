# M0 — Hard-case Observation readiness

## Status

The executable `Evidence → Observation` slice, revision-aware supersession, durable GitHub issue/PR snapshots, durable workflow-run evidence, and evidence-bound action-policy validation are now implemented and live-validated.

The key result remains that not every golden case should be made to pass by broadening `Observation` until it can hold arbitrary synthesis. The hard cases separate source-local observation, process/event evidence, temporal belief revision, action/governance policy, and cross-repository pattern synthesis.

The machine-readable readiness contract is `eval/pilot/observation-readiness-v1.yaml` and is evaluated by `lemmamind.observation_readiness`.

## Observation v2 correction

One source-level Observation remains bound to one resolved `SourceRevision`, while supersession may cross revisions of the same Source:

```text
same logical_claim_id
+ same Source identity
+ previous revision may differ from current revision
```

Cross-source support remains rejected.

## Process and workflow evidence

Issue and pull-request state is mutable independently of Git state. `SourceRevision` is an analysis anchor, not a claim that process state is historically determined by the anchor commit. Current issue/PR snapshots preserve provider timestamps and PR head/base/merge SHAs separately.

A workflow conclusion is likewise not a code-test diagnosis. Workflow evidence separately preserves run, job, step, artifact, runner, timestamp, and safe job-log availability metadata.

These boundaries are documented in `docs/M0-GITHUB-PROCESS-EVIDENCE.md` and `docs/M0-GITHUB-WORKFLOW-EVIDENCE.md`.

## Action-policy correction

Repository capability is not operational authority.

The Resonance-World case now has an evidence-bound action policy built from direct captured governance:

```text
confirmatory_rerun_allowed = false
separate frozen-output evaluator = only classifier
promotion requires independent Acceptance-plane authority
```

Even though the repository relationship is `OWNED` with `can_write=true`, the live validator blocks rerun and provider self-classification. Promotion remains recommendation-only with `authorization_required=true`.

The evaluator has no path that emits `AUTHORIZED`. Independent authority remains external to the evaluator.

See `docs/M0-ACTION-POLICY.md` and `eval/pilot/action-policy-reports/resonance-world-confirmatory-v1.*`.

## Hard-case readiness result

| Case | Outcome | Current blocker boundary |
| --- | --- | --- |
| `external-opd-source-type` | **ready** | None at the source-level Observation layer. |
| `csd-foundry-frontier` | **blocked** | Close→reopen event history and temporal multi-revision reconciliation remain missing. |
| `resonance-world-confirmatory` | **ready** | Source-local evidence and action-policy validation now preserve the no-rerun/classifier/independent-authority boundaries. |
| `private-actions-pattern` | **deferred** | The useful conclusion intentionally belongs to the later cross-repository Pattern layer. |

Summary: **2 ready / 1 blocked / 1 deferred**.

## Why CSD is still blocked

Current snapshots recover:

```text
issue #37: open
PR #115: closed + merged
PR #117: open + draft
```

and PR #117's base SHA is the D5 merge commit while its head is the separate qualification revision.

But the frozen golden case also says issue #37 was previously closed and later reopened. A current snapshot cannot prove that transition. The acquisition gap is:

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

Workflow evidence can now represent the local failure signature correctly:

```text
run/job conclusion = failure
step_count = 0
log availability = missing
```

without labeling it `tests failed`.

The useful conclusion, however, depends on matching that signature across private repositories and contrasting healthy public repositories. That is cross-repository synthesis. The one-revision Observation rule should keep rejecting it until a proper Pattern layer exists.

## Resonance-World implication

The source-local state and operational policy are now representable without conflating them:

```text
Evidence
  ↓
Observation / decision context
  ↓
RepositoryRelationship
+ explicit governance rules
  ↓
Action-policy evaluation
```

The policy layer can reject, recommend, or require authorization. It cannot execute or authorize.

## Next priorities selected by the corpus

Do not add autonomous observation generation yet.

The next justified source-local capabilities are:

1. **GitHub issue/PR event-history capture** — required for the CSD close→reopen history;
2. temporal change/frontier reconciliation over revision-bound observations and process events;
3. later, cross-repository Pattern semantics for cases such as private Actions.

The readiness evaluator should be rerun whenever one of those capability states changes. A case may move from `blocked` to `ready`, but `deferred` cases should move only when the correct later semantic layer exists—not because Observation constraints were weakened.

## Interpretation boundary

The readiness matrix is not a claim that blocked/deferred cases are invalid. It records whether the current executable LemmaMind layers can represent their frozen golden intelligence with the required provenance and authority boundaries.
