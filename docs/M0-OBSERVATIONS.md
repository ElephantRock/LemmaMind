# M0 — Evidence-supported Observation boundary

## Purpose

Deterministic evidence recovery is complete for the frozen 12-requirement external corpus. The next M0 question is not whether LemmaMind can parse more source material, but whether a durable derived claim can preserve its exact evidence lineage without collapsing facts, source assertions, and interpretation into one object.

`ObservationConstructionService` is the first executable boundary for that question.

## What v1 does

The service accepts a caller-supplied candidate claim plus explicit typed support references. It does **not** generate, paraphrase, score, or validate the truth of the statement.

Inputs:

```text
logical_claim_id
epistemic_type
statement
supports[]
supersedes_observation_id?
```

Each support is exactly one of:

```text
EvidenceFact
SourceAssertion
Observation
```

A successful construction atomically persists:

```text
PipelineRun(run_type = reasoning)
Observation(validation_state = candidate)
ObservationSupport[]
```

## Support validation

A support reference is valid only when its provenance is complete.

For `EvidenceFact` / `SourceAssertion`:

```text
support
  ↓
Artifact
  ↓
CaptureManifest
  ↓
SourceRevision
```

The producing extraction `PipelineRun` must exist and be complete (`finished_at` and `outputs_hash` present).

For an Observation support:

```text
Observation
  ↓
ObservationSupport[]
  ↓
leaf evidence/assertions/observations
  ↓
SourceRevision
```

The reasoning producer must exist and be complete. Recursive support cycles fail closed.

## Single-revision rule

`supported-observation.v1` requires every support leaf to resolve to one `SourceRevision`.

This is intentional. An Observation is currently a source/revision-level derived claim. Cross-repository or cross-revision synthesis should later use explicit Pattern/Tension/Insight contracts rather than hiding multi-source reasoning inside a source-level Observation.

A future version can relax this only when the corpus demonstrates a concrete need and the provenance semantics are specified.

## Epistemic type

The M0 Observation contract is reserved for derived classes:

```text
Interpretation
Inference
Hypothesis
Evaluation
Opinion
Unknown
```

`EvidenceFact` and `SourceAssertion` remain evidence-layer objects rather than being re-labeled as Observations.

## Validation state

The construction service always creates:

```text
validation_state = candidate
```

It does not self-validate a claim. Review/validation authority belongs to a later explicit review transition/policy using `ReviewDecision`; constructing a well-supported candidate is not equivalent to accepting it.

## Supersession / belief revision

A new candidate may set `supersedes_observation_id` only when:

1. the prior Observation exists;
2. `logical_claim_id` is unchanged;
3. both old and new support resolve to the same source revision under v1.

This preserves historical claims while making revision explicit. It does not mutate or erase the superseded record.

Cross-revision belief revision is deliberately not smuggled into this first slice; that requires an explicit policy for whether the logical claim is revision-bound or source-level and how new upstream evidence changes applicability.

## Atomicity

Run, Observation, and support edges are written in one append-only batch. A missing support, incomplete producer run, provenance break, cross-revision support set, duplicate support, or invalid supersession causes the construction to fail before any candidate records are persisted.

## Reasoning boundary

The producer run type is `reasoning`, but `supported-observation.v1` is still manual/golden-driven. A caller supplies the statement and support references.

No model is required and no model output is trusted implicitly.

This separation is important for the next evaluation step:

```text
Can LemmaMind preserve a correct evidence → Observation graph?
```

before asking:

```text
Can a model propose the Observation and support set correctly?
```

## Next validation target

Exercise this service against the frozen external golden cases by:

1. running the existing deterministic capture/extraction policy;
2. selecting exact support records from golden evidence locators;
3. constructing the golden candidate Observation without rewriting it;
4. verifying every support edge resolves to the pinned source revision;
5. rejecting deliberately incomplete, mistyped, or cross-revision support sets;
6. comparing the resulting candidate to the golden expected observation independently of source modification authority.

That will test the first actual epistemic transition in LemmaMind rather than another ingestion capability.
