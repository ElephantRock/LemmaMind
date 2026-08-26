# LemmaMind M5-lite — Deterministic Change Intelligence

## Objective

M5-lite implements the factual portion of the roadmap's change-intelligence stack:

```text
ArtifactDelta
      ↓
StructuralDelta
      ↓
ChangeInterpretation
```

Only `ArtifactDelta` and `StructuralDelta` are implemented in this V1 slice.
`ChangeInterpretation` remains inferred work for later M5/V2 reasoning.

The governing boundary is:

> **First establish exactly what retained source state changed and which deterministic facts changed. Only later ask what the change means or whether it matters.**

M5-lite composes the existing M3 and M4 guarantees rather than introducing a new acquisition path:

```text
previous CaptureManifest     current CaptureManifest
          │                           │
          └──── M3 local reconstruction ────┘
                         ↓
                    ArtifactDelta
                         ↓
compatible M4 EvidenceFact generations
                         ↓
                    StructuralDelta
```

No provider refetch is required by the comparison service.

## Durable contracts

`src/lemmamind/change_contracts.py` adds two milestone-local immutable contracts to the generic append-only persistence registry.

### `ArtifactDelta`

One factual difference for a source locator between two exact capture manifests.

Current change types are:

```text
capture_scope_added
capture_scope_removed
became_captured
became_missing
content_changed
metadata_changed
```

Each record retains the Source, previous/current SourceRevision and CaptureManifest IDs, source locator, previous/current retrieval state, artifact IDs, content hashes, media types, and the producing `DIFF` PipelineRun.

### `StructuralDelta`

One normalized `EvidenceFact` difference associated with a non-scope `ArtifactDelta`.

Current change types are:

```text
added
removed
modified
```

Each record preserves:

- the supporting `ArtifactDelta`;
- Source and revision pair;
- source locator;
- extractor name/version;
- stable structural key;
- previous/current EvidenceFact IDs;
- previous/current evidence locators;
- previous/current normalized values;
- producing `DIFF` PipelineRun.

`StructuralDelta` is factual normalization, not an architectural or significance judgment.

## Capture-scope boundary

M3 file capture is intentionally explicit-path capture. Therefore a path present in one `CaptureManifest` but absent from the other does **not** prove that the file was added to or removed from the repository.

M5-lite records this only as:

```text
capture_scope_added
capture_scope_removed
```

and does not emit source-structure deltas for evidence that exists only because capture scope changed.

By contrast, if the **same requested path** appears in both manifests and its retrieval state changes, M5 can make the narrower factual claim:

```text
MISSING  → CAPTURED = became_captured
CAPTURED → MISSING  = became_missing
```

This distinction prevents an acquisition-policy change from masquerading as source change.

## Artifact delta semantics

For a locator present in both reconstructable manifests:

- two `MISSING` states are unchanged;
- `MISSING → CAPTURED` is `became_captured`;
- `CAPTURED → MISSING` is `became_missing`;
- two captured unequal content hashes are `content_changed`;
- equal content hashes with changed media type are `metadata_changed`;
- equal captured content and media type produce no `ArtifactDelta`.

M5-lite does not label `content_changed` as important, semantic, functional, formatting-only, generated, vendored, or noisy. It records only the exact byte-level fact.

## Structural delta semantics

`StructuralDelta` compares `EvidenceFact.normalized_value`, not authored prose and not model output.

A structural comparison is allowed only when the previous and current extraction `PipelineRun` records have the same:

```text
code_version
contract schema version
policy_version
```

The structural identity key is:

```text
source locator
+ extractor name
+ extractor version
+ locator relative to the Artifact root
```

For matching keys:

- same normalized value → no structural delta;
- unequal normalized value → `modified`.

A key present only in the current compatible generation is `added`; a key present only in the previous generation is `removed`.

This preserves exact evidence lineage while preventing extractor-version drift from being silently reported as source change.

## Determinism invariant

If two compared manifests have identical state for a source locator but compatible deterministic extraction generations yield different facts, M5-lite raises `DeterminismViolation`.

It does **not** construct a change record.

That case indicates a broken deterministic-evidence assumption, incomplete generation identity, or corrupted persisted state and must be investigated at the evidence layer.

## Conservative churn behavior

M5-lite can already suppress one useful class of structural noise without pretending to understand it.

For example, two `package.json` artifacts with byte-different whitespace formatting produce:

```text
ArtifactDelta: content_changed
StructuralDelta: none
```

because the selected package facts normalize to the same values.

The correct conclusion is only:

> the retained bytes changed, but the current deterministic package-structure extractors detected no normalized fact change.

This is **not** a generic formatting-only classifier. Syntax extractors whose facts include source coordinates or source text may still produce structural deltas for formatting edits. Generated-file, vendored-code, lockfile-noise, and broader churn policy remain future work.

## SourceAssertion boundary

M5-lite does not diff `SourceAssertion` records into `StructuralDelta`.

Authored README prose, Markdown list statements, commit messages, Python docstrings, TypeScript comments, and issue/PR title/body text remain evidence that can later support change reasoning, but their textual evolution is not silently reclassified as machine-structural fact.

This means a README byte change may yield `ArtifactDelta(content_changed)` with no `StructuralDelta` if the current deterministic fact layer did not change.

## Temporal boundary

Comparisons require:

- the same canonical Source;
- previous `SourceRevision.observed_at <= current SourceRevision.observed_at`;
- previous `CaptureManifest.captured_at <= current CaptureManifest.captured_at`.

The capture-time guard matters when repeated snapshots are taken under the same SourceRevision, including mutable provider/process evidence tied to one analysis anchor.

M5-lite does not infer causal ordering between independent provider surfaces from timestamps alone.

## Live M3 → M4 probe

A temporary branch-only, read-only workflow validated M5-lite against real immutable LemmaMind history.

Workflow run:

```text
32919230925
```

Exact branch head:

```text
409c7694e61a6d9463f27606ad2318a21dc13a83
```

GitHub token permissions were read-only (`contents: read`, `metadata: read`). The temporary workflow was removed before PR closeout.

The probe captured the **same two requested paths** at:

```text
previous M3 commit:
055d67f1ae0ebd5174114d8982bcef92609e5733

current M4 commit:
c83c95488c85c2130b198b08161b9fa6fcd5209f
```

Requested paths:

```text
README.md
src/lemmamind/evidence_inspection.py
```

Observed retrieval state:

```text
previous:
  README.md                              captured
  src/lemmamind/evidence_inspection.py missing

current:
  README.md                              captured
  src/lemmamind/evidence_inspection.py captured
```

M5-lite produced:

```text
README.md                              content_changed
src/lemmamind/evidence_inspection.py became_captured
```

The extraction generations contained 4 previous facts and 241 current facts. The structural comparison produced **237 `added` StructuralDelta records**, all for `src/lemmamind/evidence_inspection.py`.

The README change did not produce a `StructuralDelta` in this probe because its changed material was authored prose rather than a changed current `EvidenceFact`. That is an epistemic boundary, not a claim that the README change was insignificant.

The live workflow also ran the full offline suite and reached **182 passed** before executing the exact-revision probe.

## Failure semantics

M5-lite fails closed when:

- either CaptureManifest cannot be reconstructed locally under M3;
- captures belong to different Sources;
- revision or capture temporal ordering is reversed;
- only one extraction run ID is supplied;
- an extraction run is missing, incomplete, or not `run_type=extraction`;
- extraction evidence refers outside the expected capture;
- extraction code/schema/policy generations differ;
- a fact locator is not anchored to its Artifact;
- one extraction generation contains duplicate structural keys;
- compatible deterministic evidence changes while Artifact state is identical.

It does not fall back to current provider state, heuristic text diffing, generated summaries, or model judgment.

## M5-lite closeout boundary

For V1, this slice is complete when permanent CI proves:

- durable `ArtifactDelta` and `StructuralDelta` persistence;
- exact capture-scope versus retrieval-state distinctions;
- deterministic normalized add/remove/modify structural comparison;
- formatting-byte churn can remain below StructuralDelta when normalized facts are unchanged;
- extractor generation drift fails closed;
- deterministic fact drift without artifact change fails closed;
- same-Source and temporal comparison guards hold;
- existing M0–M4 and golden regressions remain green.

This does **not** claim full M5.

Still deferred are:

- `ChangeInterpretation`;
- semantic significance / impact ranking;
- generic formatting-only detection;
- generated/vendored/lockfile noise classification;
- negative-intelligence event classification such as adoption/reversal/deprecation/removal/failure/cancellation;
- project-state reconciliation across issue, PR, commit, CI, and experiment surfaces;
- model-generated change narratives.

## Next roadmap move

After M5-lite closes, the next V1 gap is **M6-lite Profiling & Triage reconciliation**: a small immutable revision-bound `ArchitectureProfile` over demonstrated deterministic evidence, plus simple deterministic triage signals. Embeddings, learned ranking, autonomous architectural interpretation, and broad profiling taxonomies remain later work.
