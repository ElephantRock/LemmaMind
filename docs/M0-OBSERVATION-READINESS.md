# M0 — Hard-case Observation readiness

## Status

The executable `Evidence → Observation` slice, revision-aware supersession, durable GitHub issue/PR snapshots, issue-event history, durable workflow-run evidence, and evidence-bound action-policy validation are now implemented and live-validated.

The hard cases continue to separate source-local observation, process/event evidence, temporal belief revision, action/governance policy, and cross-repository pattern synthesis rather than broadening `Observation` into a generic synthesis container.

The machine-readable readiness contract is `eval/pilot/observation-readiness-v1.yaml` and is evaluated by `lemmamind.observation_readiness`.

## Observation boundary

One source-level Observation remains bound to one resolved `SourceRevision`, while supersession may cross revisions of the same Source:

```text
same logical_claim_id
+ same Source identity
+ previous revision may differ from current revision
```

Cross-source support remains rejected.

## Process, event, and workflow evidence

Current issue/PR snapshots preserve what GitHub reports now. Issue-event history separately preserves provider event IDs, event kinds, actors, timestamps, and optional commit links. `SourceRevision` remains the analysis-generation anchor, not the time authority for mutable process state.

Live CSD event-history validation recovered issue #37's provider `closed` event at `2026-08-24T21:31:54Z` and later `reopened` event at `2026-08-24T21:36:12Z`. The historical close→reopen transition is therefore directly observed rather than inferred from the current `state=open` snapshot.

Workflow evidence likewise preserves run/job/step/artifact metadata without turning workflow conclusions into causal diagnoses.

See `docs/M0-GITHUB-PROCESS-EVIDENCE.md`, `docs/M0-GITHUB-PROCESS-EVENTS.md`, and `docs/M0-GITHUB-WORKFLOW-EVIDENCE.md`.

## Action-policy boundary

Repository capability is not operational authority. The Resonance-World validator uses explicit captured governance to block a blind rerun and provider self-classification even when the relationship is `OWNED` with `can_write=true`. Promotion remains recommendation-only with independent authorization still external to the evaluator.

## Hard-case readiness result

| Case | Outcome | Current blocker boundary |
| --- | --- | --- |
| `external-opd-source-type` | **ready** | None at the source-level Observation layer. |
| `csd-foundry-frontier` | **blocked** | Historical close→reopen evidence now exists; only temporal multi-revision/frontier reconciliation remains missing. |
| `resonance-world-confirmatory` | **ready** | Source-local evidence and action-policy validation preserve the no-rerun/classifier/independent-authority boundaries. |
| `private-actions-pattern` | **deferred** | The useful conclusion intentionally belongs to the later cross-repository Pattern layer. |

Summary: **2 ready / 1 blocked / 1 deferred**.

## Why CSD is still blocked

The source-local evidence now includes:

```text
issue #37: currently open
PR #115: merged
PR #117: open + draft
issue #37 event history: closed → reopened
```

The missing capability is no longer acquisition. It is the higher-level reconciliation:

```text
D5 implementation landed
+ umbrella issue was closed
+ issue was later reopened
+ qualification PR remains open
        ↓
implementation frontier complete
!=
evidentiary closure frontier complete
```

That conclusion belongs to `temporal_change_reconciliation`. It must preserve the earlier stronger conclusion as historical state and produce explicit supersession/belief-revision lineage rather than rewriting it.

## Why private Actions remains deferred

Workflow evidence can represent each repository-local signature correctly, including zero-step failures and missing logs, without labeling them test failures. The useful private-Actions conclusion still depends on matched signatures and negative controls across several Sources. That is later Pattern semantics, not a reason to weaken the one-revision Observation invariant.

## Next priorities selected by the corpus

Do not add autonomous observation generation yet.

The next justified source-local capability is:

1. **temporal change/frontier reconciliation** over revision-bound observations plus current process snapshots and provider event history;
2. after that, later cross-repository Pattern semantics for cases such as private Actions.

A case may move from `blocked` to `ready` only when the correct semantic layer exists—not because source-level Observation constraints were weakened.
