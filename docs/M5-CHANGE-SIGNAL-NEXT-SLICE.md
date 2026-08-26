# LemmaMind — First Full-M5 Change-Signal Slice

## Status

**Authorized by V2-P0 FAIL / `CHANGE_SIGNAL` bottleneck.**

The authoritative product-value closeout is [`eval/v2/product-value-probe/V2-P0-CLOSEOUT.md`](../eval/v2/product-value-probe/V2-P0-CLOSEOUT.md).

V1 remains PASS. This document narrows the next implementation slice; it does not redefine the V1 release boundary or authorize later V2 capabilities.

## Problem

V1 can prove that an exact repository revision changed, retain exact root-tree evidence, compare governed explicit files, and route an evidence-rich Deep-tracked source to review. The first prospective V2-P0 intervals showed that this is still too coarse for attention-saving intelligence:

```text
exact root tree changed
        ↓
top-level areas changed
        ↓
REVIEW
```

The missing deterministic bridge is:

```text
exact root tree changed
        ↓
recursive changed paths
        ↓
affected eligible artifacts
        ↓
normalized factual change
        ↓
low-value churn suppressed/classified
        ↓
small candidate set for interpretation/review
```

## Slice objective

Implement the smallest full-M5 capability that can turn exact Git revision differences into a bounded, reproducible changed-artifact set without executing untrusted repository code and without introducing model-generated interpretation.

## Required capabilities

### 1. Recursive changed-path localization

Given two exact `SourceRevision` records for the same Source:

- compare Git trees recursively or through an equivalent exact Git object/API path;
- emit deterministic path-level additions, removals, type changes, and content-object changes;
- preserve old/new blob or tree object identities where available;
- distinguish directory movement from authored semantic interpretation;
- fail closed on truncated/incomplete provider tree responses rather than claiming completeness.

The output is factual change localization, not `ChangeInterpretation`.

### 2. Affected-file capture planning

Use the path-level factual change set to determine which changed artifacts are eligible for capture under the active tracking policy and trust boundary.

The planner must:

- preserve tracking-level authorization;
- never execute changed source code;
- avoid broad repository checkout merely to discover paths when exact provider/Git evidence is sufficient;
- retain explicit missing/unavailable states;
- keep capture scope distinct from repository-authored add/remove claims.

### 3. Deterministic surface/churn classification

Where classification can be made from path, media type, retained bytes, or normalized deterministic evidence, tag factual change surfaces such as:

```text
SOURCE
TEST
DOCS
CONFIG
WORKFLOW
MANIFEST
LOCKFILE
GENERATED
VENDORED
UNKNOWN
```

Formatting-only or equivalent-normalized churn may be suppressed only when the equivalence is deterministic and reproducible. Unknown cases remain unknown rather than being guessed away.

### 4. Candidate-set production

Produce a small factual candidate set suitable for later review or `ChangeInterpretation`.

A candidate must retain:

- exact previous/current SourceRevision IDs;
- changed paths and old/new object identities;
- capture/evidence provenance;
- deterministic surface/churn tags;
- suppression reason when suppressed;
- producer/run/schema/policy versions.

The candidate is not yet a claim about architectural importance, causality, adoption, reversal, or failure.

## Explicitly deferred inside this slice

Do not add yet:

- embeddings or vector search;
- learned ranking;
- autonomous model-generated change summaries;
- semantic importance scores without a reviewed evaluation basis;
- automatic Pattern discovery;
- knowledge promotion;
- action authorization or execution.

`ChangeInterpretation` should begin only after recursive localization and deterministic suppression are proven against the frozen V2-P0 failures.

## Evaluation target

Replay the three failed prospective intervals:

- `CopilotKit/OpenBot` — `43ea5c1… → e8aa344…`
- `openclaw/openclaw` — `20eef85… → aec260b…`
- `NousResearch/hermes-agent` — `b2bd1ac… → a6d6060…`

The slice passes only if it materially reduces each interval from broad top-level tree movement to an auditable changed-path/candidate set that includes the locations containing the important misses recorded in V2-P0, without using those misses as hard-coded path exceptions.

## Next decision

After this deterministic localization/suppression slice passes, reassess whether the remaining bottleneck is:

- semantic `ChangeInterpretation` within full M5;
- richer deterministic profiling in full M6;
- or another measured issue.

M6.5 remains deferred until cross-repository comparison, rather than source-local change signal, is the demonstrated bottleneck.
