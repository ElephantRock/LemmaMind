# M5 — Provenance-Bound ChangeInterpretation

## Status

**Authorized next full-M5 slice after candidate factual reduction.**

The prior replay established that LemmaMind now has abundant trustworthy
candidate-local evidence, but deterministic evidence does not itself create a
human-sized attention surface. All 303 frozen machine candidates remained
retained.

This slice introduces the first semantic layer in M5:

```text
ArtifactDelta
      ↓
StructuralDelta
      ↓
CandidateFactualReduction
      ↓
ChangeInterpretation
```

`ChangeInterpretation` is inferred. It must remain distinguishable from
`EvidenceFact` and `SourceAssertion` at the contract, persistence, review, and UI
boundaries.

## Governing objective

Produce a small number of auditable mechanism-level change interpretations from
retained factual candidates while preserving exact support, explicit uncertainty,
and human review authority.

The implementation is successful only if it reduces attention. Generating more
correct prose is not success.

## Initial contract

One `ChangeInterpretation` binds:

- exact source identity;
- exact previous/current revisions;
- one or more `IntervalCandidateSegment` records;
- exactly one `CandidateFactualReduction` for each interpreted candidate;
- one or more interpretation types;
- a mechanism label and bounded summary;
- typed support references;
- explicit uncertainty notes when extraction-gap support is present;
- one interpretation-producing pipeline run;
- `candidate` validation state only.

Supported interpretation types begin conservatively with:

```text
introduction
modification
removal
reversal
deprecation
failure
repair
authority_governance
project_state
temporal_correctness
unknown
```

These are semantic classifications, not deterministic facts.

## Support types

The first contract permits support edges to:

```text
CandidateFactualReduction
ArtifactDelta
StructuralDelta
SourceAssertion
CandidateExtractionGapSignal
```

Support membership alone does not prove the natural-language mechanism statement.
The future producer/validator must verify lineage and semantic grounding against a
bounded evidence packet.

## Human authority boundary

A generated interpretation starts as:

```text
validation_state = candidate
```

It cannot self-promote to reviewed/validated state and cannot authorize any action.

Existing `ReviewDecision` / `ReviewFeedback` remain the human feedback boundary.
Future promotion remains separate.

## Evidence packet before model inference

No model call should consume the raw unbounded change generation.

The next implementation increment after this contract is a deterministic,
hashable `CandidateEvidencePacket` that:

- closes lineage through candidate factual reductions;
- includes exact candidate paths and factual signal kinds;
- carries bounded deterministic references/previews for structural changes and
  authored assertions;
- carries explicit extraction-gap signals;
- records total vs included evidence counts so truncation is visible;
- is reproducible for identical source-local inputs.

The packet must never discard the existence of omitted evidence merely because a
preview budget is reached.

## Grouping boundary

Machine candidates and human review items are intentionally different objects.

A future interpretation producer may:

- interpret one candidate as one mechanism;
- decline a candidate for insufficient evidence;
- combine multiple candidates into one mechanism when evidence supports a common
  change.

It must not group merely because files are adjacent or descriptions look
linguistically similar. Grouping requires support that the candidates belong to
the same mechanism/change.

## Frozen gate

The immutable evaluation contract is:

```text
eval/v2/product-value-probe/m5-change-interpretation-evaluation-spec.md
```

The gate requires primary-anchor recall, at least 8/10 known-mechanism recall,
no more than 50 total human review items across the frozen 303 candidates, zero
provenance failures, explicit gap uncertainty, and no unsupported central
mechanism claims.

A fresh prospective interval is required after the frozen replay before the
roadmap can advance.

## Explicit deferrals

This slice does not authorize:

- embeddings or vector infrastructure;
- learned ranking;
- autonomous pattern discovery;
- knowledge promotion;
- action execution;
- broad M7 reasoning over arbitrary sources;
- numerical confidence probabilities.

The next roadmap decision is made only after measured interpretation quality and
attention reduction.
