# M5 candidate factual reduction — V2-P0 replay

## Result

**PASS for provenance-bound factual reduction and extraction-gap isolation. The full-M5 attention-sized candidate objective remains OPEN.**

This slice evaluates the next measured step after deterministic interval segmentation: exact candidate-scoped file capture, deterministic extraction, `ArtifactDelta` / `StructuralDelta`, authored `SourceAssertion` comparison, explicit extraction-gap diagnostics, and fail-closed candidate retention.

The replay shows that this layer materially improves what LemmaMind can *prove about each candidate*, but it does **not** reduce the candidate count. All 303 deterministic interval candidates across the three frozen repositories remain retained.

The product consequence is important: the current bottleneck is no longer missing source-local factual evidence. It is deciding which evidenced changes are semantically meaningful enough to deserve attention without inventing unsupported importance. Broad deterministic suppression is not justified by this replay.

## Factual reduction model

For one complete recursive-path generation, the slice requires:

1. exact `GitPathDelta`, `IntervalCandidateSegment`, and `AffectedFileCapturePlan` generations with matching source/revision provenance;
2. exact explicit-file previous/current captures under the existing tracking and trust policy;
3. deterministic extraction generations over those captures;
4. factual `ArtifactDelta` and `StructuralDelta` comparison;
5. separate authored `SourceAssertion` change detection;
6. one durable `CandidateFactualReduction` for every deterministic interval candidate;
7. explicit `ExtractionDiagnostic` and `CandidateExtractionGapSignal` records when a supported extractor cannot parse one captured artifact.

The reduction signal kinds remain factual:

- `structural_delta`;
- `authored_assertion_change`;
- `artifact_delta_without_extracted_signal`;
- `git_only_change`;
- `policy_suppressed`.

A candidate is automatically suppressed only when every path in that candidate was already explicitly policy-suppressed. Changed bytes that current extractors do not explain remain retained rather than being guessed away as noise.

## Extraction-gap boundary

The first broad replay exposed a scaling defect in the strict extraction contract: one parser-incompatible TypeScript artifact could abort extraction for an otherwise valid ~1,269-file capture generation.

The hardened full-M5 path now isolates that uncertainty without weakening the V1 contract:

- strict `DeterministicExtractionService` remains fail-closed;
- gap-tolerant extraction is an explicit, separately versioned full-M5 policy;
- recoverable parser/extractor failures become durable source-local `ExtractionDiagnostic` records;
- diagnostic output hashes are stable across new run IDs for identical source-local failures;
- `GapAwareDeterministicChangeService` excludes diagnostic paths symmetrically from `StructuralDelta` comparison;
- candidate-level gap signals close lineage through exact captures, revisions, artifacts, paths, extraction runs, and the corresponding factual-reduction generation;
- ordinary `DeterministicChangeService` rejects gap-tolerant policies and independently rejects diagnostic-bearing extraction runs so a strict caller cannot manufacture structural evidence from incomplete extraction.

Extraction gaps therefore mean **known incomplete deterministic coverage**, not a semantic change claim and not permission to suppress the affected path.

## Test and replay provenance

Permanent pull-request CI after the strict/gap-aware boundary hardening:

```text
implementation head: 5ef41f70b5535d891e2b72fd4de5f2f03a7c8e2f
pytest: 258 passed
conclusion: success
```

The final temporary read-only frozen replay ran on the same implementation plus the ephemeral replay workflow:

```text
replay head: 111c1812e9d5df9e79f2a43b2398c3ce34d206f9
workflow run: 33247464022
job: 99087323566
pytest: 258 passed
replay: success
```

The replay executed no tracked repository source code. The workflow only used GitHub API/Git object reads, retained bytes, LemmaMind deterministic extractors, and local contract/object stores. The temporary replay workflow was removed immediately after the successful run.

## Frozen replay results

| Repository | Changed leaf paths | Planned file paths | Interval candidates | Retained | Suppressed | ArtifactDelta | StructuralDelta | Gap paths | Gap candidates | Known miss retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CopilotKit/OpenBot | 41 | 41 | 9 | 9 | 0 | 41 | 3,612 | 0 | 0 | yes |
| openclaw/openclaw | 1,291 | 1,269 | 229 | 229 | 0 | 1,269 | 356,123 | 69 | 41 | yes |
| NousResearch/hermes-agent | 147 | 146 | 65 | 65 | 0 | 146 | 120,864 | 0 | 0 | yes |

Affected-file planning had already suppressed 22 OpenClaw paths and 1 Hermes path. Those policy-suppressed paths appeared inside two OpenClaw candidate units and one Hermes candidate unit, but none of those candidates consisted only of suppressed paths; therefore all candidates correctly remained retained.

### Candidate signal distribution

A candidate can carry more than one signal kind, so the counts below are not mutually exclusive.

| Repository | StructuralDelta candidates | Authored-assertion-change candidates | Artifact-only candidates | Policy-suppressed candidates | Extraction-gap candidates |
| --- | ---: | ---: | ---: | ---: | ---: |
| CopilotKit/OpenBot | 6 | 8 | 3 | 0 | 0 |
| openclaw/openclaw | 169 | 124 | 95 | 2 | 41 |
| NousResearch/hermes-agent | 58 | 49 | 5 | 1 | 0 |

The OpenClaw replay produced 63 previous-side and 68 current-side extraction diagnostics covering a 69-path union across 41 candidates. These paths remain explicit uncertainty rather than false `StructuralDelta` evidence or silent suppression.

## Frozen miss retention

### CopilotKit/OpenBot

```text
target: app/src/lib/attention/queries.ts
candidate size: 5
disposition: retain
signals: authored_assertion_change, structural_delta
artifact-delta paths in candidate: 5
structural-delta paths in candidate: 5
authored-assertion-change paths in candidate: 4
extraction-gap paths in candidate: 0
```

The previously missed attention-inbox mechanism remains fully represented by deterministic structure plus authored-assertion change.

### openclaw/openclaw

```text
target: src/agents/sticky-model-selection.ts
candidate size: 28
disposition: retain
signals: artifact_delta_without_extracted_signal, authored_assertion_change, structural_delta
artifact-delta paths in candidate: 28
structural-delta paths in candidate: 25
authored-assertion-change paths in candidate: 6
artifact-only paths in candidate: 3
```

The target candidate also contains three explicitly surfaced extraction-gap paths:

```text
src/auto-reply/reply/directive-handling.mixed-inline.test.ts
src/auto-reply/reply/directive-handling.model.test.ts
src/gateway/server-methods/sessions-mutations.sticky-model.test.ts
```

Those gaps do not include the target path. The sticky-model mechanism remains supported by deterministic structural and authored-assertion evidence while the candidate simultaneously exposes its incomplete coverage.

### NousResearch/hermes-agent

```text
target: hermes_cli/update_contract.py
candidate size: 5
disposition: retain
signals: authored_assertion_change, structural_delta
artifact-delta paths in candidate: 5
structural-delta paths in candidate: 5
authored-assertion-change paths in candidate: 1
extraction-gap paths in candidate: 0
```

The previously missed provenance-aware update-admission mechanism remains retained with deterministic structure and authored-assertion change.

## Product judgment

The factual layer is a correctness and interpretability improvement, not an attention reduction.

The candidate counts are unchanged from interval segmentation:

```text
OpenBot:     9 ->   9 retained
OpenClaw: 229 -> 229 retained
Hermes:     65 ->  65 retained
```

This is the correct result under the current evidence contract. The replay does not justify suppressing candidates merely because they are tests, docs, configuration, `UNKNOWN`, parser-incompatible, or not explained by the selected extractors. In particular, OpenClaw has 95 candidates containing changed bytes without selected extracted signal and 41 candidates with explicit extraction gaps; absence of extracted structure is not evidence of low value.

At the same time, the factual machinery now produces abundant source-local evidence. OpenClaw alone yields 356,123 `StructuralDelta` records across 229 machine candidates. More deterministic evidence does not by itself identify the handful of mechanisms that deserve human attention.

Therefore the deterministic-suppression hypothesis is **not supported as the primary remaining attention mechanism** on these frozen intervals. Adding broader path/surface suppression merely to force the count down would violate the evidence-first contract.

## Next measured bottleneck

The next full-M5 slice should be **provenance-bound `ChangeInterpretation` over retained machine candidates**, not more broad deterministic suppression and not M6.5.

That slice should:

1. consume exact candidate paths, `ArtifactDelta`, `StructuralDelta`, authored assertions, and extraction-gap signals;
2. produce bounded mechanism-level interpretations with explicit evidence references and explicit uncertainty when extraction coverage is incomplete;
3. distinguish factual evidence from interpretation in the contract;
4. avoid importance claims unsupported by the retained evidence;
5. replay the same frozen intervals and measure whether the known mechanism-level findings become visible in a genuinely smaller review surface;
6. fail the product gate if interpretation merely restates diffs or produces one summary per candidate without reducing attention.

Extractor coverage can be improved later when a measured miss is attributable to a specific deterministic extraction gap. The current replay does not justify expanding extractor coverage indiscriminately: the known high-value targets are retained, and the dominant problem is selecting meaning from abundant evidence.

Learned ranking, embeddings/M6.5, autonomous promotion, and action execution remain deferred.

## Governance

The temporary replay workflow was execution provenance only and was removed from the branch after the successful evaluation. The slice preserves the V1 strict extraction boundary while adding an explicitly versioned, provenance-auditable full-M5 path for broad capture sets.
