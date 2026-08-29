# LemmaMind — First Full-M5 Change-Signal Slice

## Status

**COMPLETED and evaluated against the frozen V2-P0 `CHANGE_SIGNAL` failures.**

The authoritative product-value closeout remains [`eval/v2/product-value-probe/V2-P0-CLOSEOUT.md`](../eval/v2/product-value-probe/V2-P0-CLOSEOUT.md). The staged corrective evaluations are recorded under [`eval/v2/product-value-probe/`](../eval/v2/product-value-probe/), culminating in `m5-candidate-factual-reduction-v1.md`.

V1 remains PASS. This full-M5 slice did not redefine the V1 release boundary or authorize embeddings, learned ranking, promotion, or action execution.

## Problem

V1 could prove that an exact repository revision changed, retain exact root-tree evidence, compare governed explicit files, and route an evidence-rich Deep-tracked source to review. The first prospective V2-P0 intervals showed that this was still too coarse for attention-saving intelligence:

```text
exact root tree changed
        ↓
top-level areas changed
        ↓
REVIEW
```

The deterministic bridge evaluated in this slice was:

```text
exact root tree changed
        ↓
recursive changed paths
        ↓
affected eligible artifacts
        ↓
first-parent temporal/path candidates
        ↓
candidate-scoped deterministic evidence
        ↓
explicit factual signals + extraction gaps
```

## Implemented capabilities

### 1. Recursive changed-path localization

Given two exact `SourceRevision` records for the same Source, LemmaMind now:

- compares Git trees recursively;
- emits deterministic path-level additions, removals, type changes, and content-object changes;
- preserves old/new Git object identities where available;
- suppresses parent-directory hash churn without suppressing changed leaf paths;
- fails closed on incomplete/truncated provider tree evidence.

The output remains factual `GitPathDelta`, not `ChangeInterpretation`.

### 2. Affected-file capture planning

The planner now maps the complete path-level factual generation into explicit before/after capture scope under the active tracking policy and trust boundary. It:

- preserves tracking-level authorization;
- never executes changed repository source code;
- uses exact provider/Git evidence rather than broad checkout for path discovery;
- retains add/remove missing-side state;
- handles directories/submodules distinctly from ordinary file capture;
- suppresses only explicitly governed generated, vendored, or oversized surfaces;
- preserves `UNKNOWN` rather than guessing it away.

### 3. Deterministic interval/candidate segmentation

High-velocity intervals are decomposed through a first-parent integration model while preserving the full compare frontier as evidence. Every net `GitPathDelta` is assigned exactly once to a bounded deterministic candidate, with typed path grouping and fixed chunking.

This produced:

```text
OpenBot:      41 changed paths ->   9 candidates
OpenClaw:  1,291 changed paths -> 229 candidates
Hermes:      147 changed paths ->  65 candidates
```

The candidates are machine-processing units, not semantic claims or direct-review items.

### 4. Candidate-scoped factual reduction

Each candidate can now be reduced through exact explicit-file captures and deterministic evidence. The full-M5 factual layer distinguishes:

```text
structural_delta
authored_assertion_change
artifact_delta_without_extracted_signal
git_only_change
policy_suppressed
```

`EvidenceFact` / `StructuralDelta` remain separate from authored `SourceAssertion` changes. Exact Git path identity is preserved through capture, evidence, and change contracts.

A candidate is automatically suppressed only when all of its paths were already explicitly policy-suppressed. Changed bytes without selected extracted structure remain retained fail-closed.

### 5. Explicit extraction-gap isolation

Broad candidate captures exposed a real scaling boundary: one parser-incompatible artifact could previously abort an otherwise useful large extraction generation. The full-M5 path now isolates that uncertainty without weakening strict V1 behavior:

- strict deterministic extraction remains fail-closed;
- gap-tolerant extraction is explicitly versioned and opt-in;
- recoverable parser/extractor failures become source-local `ExtractionDiagnostic` records;
- gap paths are excluded symmetrically from `StructuralDelta` comparison;
- candidate-level gap signals close exact capture/revision/artifact/path/run lineage;
- strict deterministic change rejects gap-tolerant or diagnostic-bearing extraction generations.

An extraction gap is explicit incomplete coverage, not semantic evidence and not a suppression reason.

## Frozen evaluation

The same three prospective failure intervals were replayed without target-path routing exceptions:

- `CopilotKit/OpenBot` — `43ea5c1… → e8aa344…`
- `openclaw/openclaw` — `20eef85… → aec260b…`
- `NousResearch/hermes-agent` — `b2bd1ac… → a6d6060…`

The final candidate factual-reduction replay succeeded and retained every known high-value miss location:

| Repository | Interval candidates | Retained | Suppressed | StructuralDelta | Extraction-gap paths |
| --- | ---: | ---: | ---: | ---: | ---: |
| CopilotKit/OpenBot | 9 | 9 | 0 | 3,612 | 0 |
| openclaw/openclaw | 229 | 229 | 0 | 356,123 | 69 |
| NousResearch/hermes-agent | 65 | 65 | 0 | 120,864 | 0 |

The OpenClaw gaps span 41 candidates and are preserved as explicit uncertainty. They do not erase deterministic evidence from independent paths.

The detailed replay, target retention, signal distribution, and provenance are recorded in `eval/v2/product-value-probe/m5-candidate-factual-reduction-v1.md`.

## Product conclusion

The deterministic change-signal foundation is now substantially stronger, but **deterministic factual reduction did not produce an attention-sized human review set**.

The final counts remained:

```text
OpenBot:     9 ->   9 retained
OpenClaw:  229 -> 229 retained
Hermes:     65 ->  65 retained
```

This result is informative rather than a reason to add broader suppression. The current evidence does not justify discarding tests, docs, configuration, `UNKNOWN`, parser-incompatible artifacts, or changed bytes without extracted structure merely to reduce counts. Doing so would violate the evidence-first contract and risks removing exactly the mechanisms LemmaMind is intended to surface.

At the same time, source-local factual evidence is now abundant: OpenClaw alone produces 356,123 deterministic `StructuralDelta` records. The remaining attention problem is therefore not primarily “where did change occur?” or “can we extract facts from it?” It is “which evidenced mechanism-level changes matter, and why?”

## Next authorized full-M5 slice

The measured next bottleneck is **provenance-bound `ChangeInterpretation`**.

The next slice is authorized to consume retained candidate paths, `ArtifactDelta`, `StructuralDelta`, authored assertions, and extraction-gap signals and produce bounded mechanism-level interpretations that:

- cite exact retained evidence;
- preserve the distinction between fact, source assertion, and interpretation;
- state uncertainty when extraction coverage is incomplete;
- avoid unsupported causality or importance claims;
- reduce the machine-candidate surface to a genuinely smaller review set;
- replay the same frozen V2-P0 intervals and recover the known mechanism-level findings without hard-coded path exceptions.

A ChangeInterpretation slice fails the product gate if it merely paraphrases diffs or emits one summary per deterministic candidate without reducing attention.

Extractor coverage should expand only when a measured miss is attributable to an extraction gap. Broad extractor expansion is not the current primary bottleneck.

## Still deferred

Do not add yet:

- embeddings or vector search / M6.5;
- learned ranking;
- automatic Pattern discovery;
- autonomous knowledge promotion;
- semantic importance scores without a reviewed evaluation basis;
- action authorization or execution.

M6.5 remains deferred until cross-repository comparison, rather than source-local change interpretation, is the demonstrated bottleneck.
