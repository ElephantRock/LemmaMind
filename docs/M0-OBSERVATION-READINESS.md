# M0 — Hard-case Observation readiness

## Status

The executable M0 source-local path now includes deterministic repository evidence, revision-bound Observation support, revision-aware supersession, GitHub issue/PR current snapshots, issue-event history, workflow-run evidence, evidence-bound action policy, and temporal frontier reconciliation. All of those slices have been live-validated against cases selected by the frozen corpus.

The machine-readable readiness contract is `eval/pilot/observation-readiness-v1.yaml` and is evaluated by `lemmamind.observation_readiness`.

The core boundary remains unchanged: source-level `Observation` is not a generic synthesis container. Cross-source conclusions remain deferred to later Pattern/Insight semantics.

## Source-local provenance boundary

One Observation resolves to one `SourceRevision`. A superseding Observation may use a later revision of the same Source when the logical claim identity is unchanged. The prior Observation remains immutable.

```text
old Observation
      ↑
supersedes_observation_id
      │
new candidate Observation
```

Current process snapshots, provider event history, Git revisions, workflow state, and governance policy remain distinguishable evidence inputs rather than being collapsed into one mutable state record.

## CSD temporal reconciliation

The CSD case now has the full evidence chain required by the frozen golden case:

```text
PR #115 merged = true
issue #37 currently open
PR #117 open + draft
PR #117 base = aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7
PR #117 head = 2d910f3ff83f061409ca9d8f2e3709fde7c13f6e
issue #37 closed at 2026-08-24T21:31:54Z
issue #37 reopened at 2026-08-24T21:36:12Z
```

Live workflow run `32870568177` passed **101 offline tests** and then constructed two candidate runtime Observations:

1. an Interpretation preserving the distinction between implementation completion and evidentiary closure;
2. an Evaluation that supersedes the earlier stronger closure conclusion while leaving that prior Observation unchanged.

Neither runtime candidate self-promotes to the golden case's reviewed/validated target state.

See `docs/M0-TEMPORAL-RECONCILIATION.md` and `eval/pilot/temporal-reports/csd-frontier-reconciliation-v1.*`.

## Hard-case readiness result

| Case | Outcome | Boundary |
| --- | --- | --- |
| `external-opd-source-type` | **ready** | Source-role and deterministic evidence boundaries are executable. |
| `csd-foundry-frontier` | **ready** | Current process state, event history, exact PR revision relation, and explicit belief revision are executable. |
| `resonance-world-confirmatory` | **ready** | Workflow evidence and action policy preserve no-rerun, classifier, and independent-authority boundaries. |
| `private-actions-pattern` | **deferred** | The useful claim requires matched evidence and controls across several Sources and therefore belongs to the later Pattern layer. |

Summary: **3 ready / 0 blocked / 1 deferred**.

## Why private Actions remains deferred

Workflow evidence can represent each repository-local signature correctly, including:

```text
run/job conclusion = failure
step_count = 0
log availability = missing
```

without calling that signature a code-test failure.

The useful conclusion, however, compares ExpertOS and ExpertForge against public negative controls such as ERLab and Resonance-ContextGraph. That is a cross-repository inference. Making it pass by relaxing the one-revision Observation constraint would be an epistemic regression.

The next justified semantic slice is therefore a proper **Pattern / PatternOccurrence** layer with explicit multi-source support and provenance, not autonomous observation generation and not a broader source-level Observation contract.
