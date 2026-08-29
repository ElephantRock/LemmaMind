# M5 interval/candidate segmentation — V2-P0 replay

## Result

**PASS for deterministic interval segmentation correctness. The full-M5 attention-sized candidate objective remains OPEN.**

This slice addresses the next measured defect after recursive localization and affected-file planning: high-velocity baseline-to-current intervals remained monolithic. It converts one complete net `GitPathDelta` generation into deterministic temporal/path units while preserving every factual path delta.

It does not rank architectural importance, discard `UNKNOWN` surfaces, introduce `ChangeInterpretation`, use embeddings, or invoke model inference.

## Topology model

An initial implementation treated the GitHub compare list as a linear commit chain and failed closed when any commit had multiple parents. The first frozen replay showed that this rule rejected a real target interval:

```text
run: 33138131861
unit suite: 242 passed
replay: FAIL
reason: commit interval is not a single-parent linear chain
```

Rejecting every merge history would make interval segmentation unusable on ordinary repositories. The hardened model therefore separates **complete frontier evidence** from **deterministic temporal routing**:

1. retain the complete paginated GitHub compare frontier;
2. retain a complete changed-path projection and parent list for every intervening commit;
3. derive the current revision's **first-parent integration chain** back to the frozen baseline;
4. fail closed if the baseline is not first-parent reachable from the current revision;
5. assign each net `GitPathDelta` to its latest touching commit on that first-parent integration chain;
6. group assignments by typed deterministic path structure and chunk at the fixed 50-path v1 bound.

This avoids inventing an ordering between sibling branch commits while still supporting real merge histories. Side-branch commit snapshots remain retained evidence; they are not treated as a causal total order for candidate routing.

## Correctness hardening

The slice also:

- validates every `GitPathDelta` against the complete `GitPathDiffSummary` generation tuple before provider reads or persistence;
- preserves exact Git path identity, including significant whitespace;
- includes rename `previous_filename` aliases in complete touch sets;
- validates compare pagination, exact current SHA termination, and the GitHub 3,000-file per-commit completeness boundary;
- uses collision-resistant typed path-group keys so root-level files cannot collide with a real top-level directory such as `$root`;
- requires every net path delta to be assigned exactly once;
- keeps all deterministic path surfaces represented.

## Test and replay provenance

Permanent pull-request CI on implementation head `639584bc20f0319d371210e82e4920ef38541788`:

```text
workflow run: 33138426147
pytest: 243 passed
conclusion: success
```

The temporary read-only frozen replay used the same code head:

```text
workflow run: 33138423901
job: 98743595152
pytest: 243 passed
replay: success
```

The replay asserted complete net-path coverage and required each frozen high-value miss location to appear in exactly one candidate. The target paths are evaluation checks, not routing exceptions.

## Frozen replay results

| Repository | Net changed paths | Intervening commits | Candidate count | Median paths/candidate | P95 | Max | Known miss retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CopilotKit/OpenBot | 41 | 5 | 9 | 4 | 13 | 13 | yes |
| openclaw/openclaw | 1,291 | 150 | 229 | 2 | 21 | 50 | yes |
| NousResearch/hermes-agent | 147 | 71 | 65 | 1 | 6 | 17 | yes |

All net paths remained represented:

```text
OpenBot:      41 / 41
OpenClaw:  1,291 / 1,291
Hermes:      147 / 147
```

### Frozen miss localization inside candidates

OpenBot:

```text
target: app/src/lib/attention/queries.ts
candidate size: 5
path group: top-level:"app"
assigned integration commit: e8aa34451f73ef2719c22cc557be369d9ea70afb
```

OpenClaw:

```text
target: src/agents/sticky-model-selection.ts
candidate size: 28
path group: top-level:"src"
assigned integration commit: ce4a680544a3502f98d3c9dc49ab9b9e77e7c43b
```

Hermes Agent:

```text
target: hermes_cli/update_contract.py
candidate size: 5
path group: top-level:"hermes_cli"
assigned integration commit: 4860978115a018913fe51efd61b2319e9273d0a4
```

For OpenClaw and Hermes, the deterministic integration commit selected for the target path is the same commit identified during the bounded V2-P0 manual review. That is useful temporal localization, but it is not itself semantic interpretation.

## Product judgment

The segmentation is a meaningful structural improvement, but **it does not yet satisfy the roadmap's final “small candidate set” attention objective**.

The strongest counterexample is OpenClaw:

```text
1,291 changed leaf paths
        ↓
229 deterministic candidates
median candidate size: 2 paths
p95 candidate size: 21 paths
max candidate size: 50 paths
```

The monolithic interval has been decomposed into bounded, auditable units, and the known mechanism remains represented. However, 229 candidate units are still too many to treat as a human review queue under LemmaMind's attention contract. Hermes at 65 candidates also remains above a comfortable direct-review surface.

Therefore this slice should be retained as deterministic routing infrastructure, but it does **not** authorize semantic ranking, M6.5, embeddings, or direct exposure of every candidate to a reviewer.

## Next measured bottleneck

The remaining deterministic M5 work is **candidate-scoped factual reduction**.

The next slice should use the bounded candidates as machine-processing units rather than human-review items:

1. derive exact candidate-scoped affected-file capture plans from the already persisted `GitPathDelta` and planning evidence;
2. capture eligible before/after bytes under the existing tracking and trust policy;
3. run deterministic extraction and `ArtifactDelta` / `StructuralDelta` over each candidate scope;
4. deterministically suppress or classify candidates whose retained bytes/evidence normalize to no meaningful factual structural change, while preserving explicit suppression provenance;
5. measure the remaining candidate count and frozen miss retention before introducing `ChangeInterpretation`.

Only after this deterministic evidence-aware reduction is measured should full M5 decide whether the remaining bottleneck is semantic `ChangeInterpretation` or another factual reduction step.

M6.5 and embeddings remain deferred.

## Governance

The temporary replay workflow is execution provenance only and is removed from the branch before merge. No repository source code from tracked external repositories was executed.
