# LemmaMind V2-P0 — Prospective Product-Value Probe

## Purpose

V1 proved that LemmaMind can preserve a deterministic, reproducible evidence spine from curated discovery through revision capture, source-addressable evidence, factual structural deltas, revision-bound profiling/triage, and append-only human feedback.

V2 must not assume that this machinery is already a useful operating product.

The next gate is therefore a prospective product-value probe:

> **Does the V1 Evidence Engine make fresh technical-change investigation materially better than manually inspecting GitHub?**

This probe is the roadmap's required product-value reassessment between V1 and substantive V2 representation/reasoning work. Passing V1 does not authorize automatic progression into M6.5 embeddings, broader generation volume, or autonomous reasoning.

## Why this gate exists

The M−1 pilot demonstrated decision-relevant intelligence on a deliberately reviewed corpus. V1 then demonstrated correctness, provenance, reproducibility, evidence inspection, deterministic change records, triage, and review capture.

Those results establish that LemmaMind's machinery works under controlled validation. They do not yet establish that, when ordinary fresh repository activity arrives without preselecting an interesting outcome, LemmaMind consistently surfaces the small subset worth a person's attention.

The unresolved product question is therefore prospective signal quality and attention economics, not another deterministic-contract question.

## Authority boundary

V2-P0 is an evaluation gate, not a new inference authority.

It may use the existing V1 path:

```text
Discovery / tracked Source
        ↓
previous observed SourceRevision
        ↓
fresh upstream SourceRevision
        ↓
CaptureManifest + retained Artifacts
        ↓
EvidenceFact / SourceAssertion
        ↓
ArtifactDelta → StructuralDelta
        ↓
ArchitectureProfile
        ↓
TriageAssessment
        ↓
human investigation + ReviewDecision / ReviewFeedback
```

The probe must not silently introduce:

- autonomous `ChangeInterpretation`;
- model-generated observations as authoritative evidence;
- M6.5 embeddings or vector infrastructure;
- learned ranking;
- automatic Pattern discovery;
- knowledge promotion;
- action authorization or execution.

Existing early Observation/Pattern vertical slices may be inspected when useful, but they do not determine the probe result.

## Corpus

Use a deliberately small active subset of the existing curated corpus.

Initial target:

```text
5–8 repositories
```

Selection criteria:

- already known to LemmaMind's registry/watchlist model;
- technically relevant to the product's current domains;
- sufficiently active that fresh revisions are likely to appear;
- collectively diverse enough to exercise different change surfaces;
- no repository is selected because a known interesting change has already been identified for the evaluation window.

The full 13-repository frozen pilot/watchlist remains historical evaluation context. V2-P0 is prospective: the evaluated head/revision pair must be chosen by observation time and tracking policy, not by hindsight about the resulting change.

## Prospective sampling rule

For each included repository:

1. record the previously observed revision before examining the new change in detail;
2. observe a later real revision using the ordinary read-only capture path;
3. run the V1 deterministic evidence/change/profile/triage path;
4. record what LemmaMind surfaced before performing unrestricted manual investigation;
5. perform a bounded human review of the same revision interval;
6. record useful surfaced items, missed important items, noise, investigation time, and decision effect.

Do not discard a repository/revision pair merely because nothing interesting happened. Silence and low-value intervals are part of the product test.

## Required measurements

### 1. Meaningful-change precision

Question:

> Of what LemmaMind surfaced for attention, how much was actually worth inspecting?

Record each surfaced candidate as one of:

```text
HIGH_VALUE
USEFUL
LOW_SIGNAL
NOISE
UNRESOLVED
```

This is a human evaluation label. It does not mutate the underlying deterministic fact.

### 2. Important-change recall

Question:

> What did bounded manual review find that LemmaMind failed to surface or routed too low?

Record missed items with enough source/revision provenance to replay the judgment later.

The probe does not require statistical recall over all repository activity. It requires explicit accounting for important misses in the sampled intervals.

### 3. Investigation time

Measure elapsed focused review time for:

- understanding what changed;
- verifying the supporting evidence;
- deciding whether a deeper investigation is warranted.

Where feasible, distinguish:

```text
LemmalMind-assisted investigation time
manual-baseline estimate or paired manual time
```

Do not claim a precise productivity gain when the comparison was not actually measured.

### 4. Evidence usefulness

Question:

> Did retained exact provenance materially accelerate verification or reduce uncertainty?

Suggested labels:

```text
MATERIAL
HELPFUL
NEUTRAL
BURDENSOME
```

### 5. Triage usefulness

Question:

> Did the deterministic triage route scarce attention sensibly?

Record whether each `deep_dive` / lower-priority route was:

```text
RIGHT_PRIORITY
TOO_HIGH
TOO_LOW
NOT_ENOUGH_CONTEXT
```

### 6. Decision effect

For each genuinely useful finding, record whether it changed or materially focused any of:

```text
INVESTIGATE
DESIGN
IMPLEMENT
ADOPT
AVOID
MONITOR
REVALIDATE_BELIEF
NO_DECISION_EFFECT
```

A correct no-action conclusion remains valid intelligence.

### 7. Review burden

Track total focused human review minutes for the evaluation window.

The product target remains approximately:

```text
30–60 minutes / week
```

The system should degrade by showing less rather than creating an accumulating queue.

### 8. Operational cost

Record at minimum:

```text
repositories sampled
revision intervals
GitHub/provider requests if measured
captured artifact bytes if measured
persistent bytes added if measured
pipeline runtime if measured
human review minutes
LLM tokens: 0 for the V1 deterministic path
embedding operations: 0
```

Unknown quantities must be marked `not_measured`, not treated as zero.

## Evaluation records

Each sampled revision interval should produce one immutable evaluation record under:

```text
eval/v2/product-value-probe/
```

The record should include:

- repository/source identity;
- previous and fresh exact revisions;
- observation timestamps;
- capture/profile/triage run identifiers where available;
- surfaced candidates;
- human judgments;
- important misses;
- investigation time;
- evidence usefulness;
- decision effect;
- unresolved limitations.

Do not rewrite historical probe records when later evidence changes the conclusion. Add a later record or explicit supersession reference.

## Initial PASS gate

V2-P0 passes only if all of the following are true across the prospective sample:

1. **At least two genuinely useful fresh findings** are surfaced without selecting the interval because the outcome was already known.
2. **At least one finding changes or materially focuses an investigation, design, adoption/avoidance, monitoring, or belief-revalidation decision.**
3. **The deterministic evidence trail is materially useful for verification in at least one case.**
4. **Review burden remains compatible with the intended 30–60 minute weekly attention budget for the sampled scope, or the evidence clearly identifies a tractable suppression/ranking correction.**
5. **Noise is low enough that increasing the tracked corpus appears plausible without merely increasing backlog.**
6. **Important misses are explicitly documented and do not demonstrate that the current evidence/triage path systematically hides the most decision-relevant changes.**

The gate is intentionally product-oriented rather than statistically calibrated. Its purpose is to decide what to build next, not to claim general GitHub-wide performance.

## FAIL / inconclusive conditions

The probe does not pass merely because the pipeline ran correctly.

Treat the result as FAIL or INCONCLUSIVE when any of the following dominates:

- surfaced items are mostly routine churn or obvious from ordinary GitHub inspection;
- exact evidence is correct but does not materially reduce investigation effort;
- important changes are repeatedly missed by the current evidence/profile surface;
- triage frequently allocates attention in the wrong direction;
- review burden exceeds the product budget without a credible suppression strategy;
- findings do not affect investigation or decision behavior;
- the sample is too inactive or too small to make a defensible next-step decision.

## Post-probe routing

V2-P0 does not predetermine M6.5.

### Outcome A — change signal is the bottleneck

If the evidence spine is reliable but the surfaced deltas are too noisy or semantically weak, prioritize **full M5**:

- meaningful-change classification;
- semantic churn suppression;
- adoption/reversal/deprecation/removal intelligence;
- project-state reconciliation;
- explicit `ChangeInterpretation` with provenance and epistemic boundaries.

Do not add embeddings to compensate for poor change signal.

### Outcome B — architecture/profile representation is the bottleneck

If fresh changes are useful but the deterministic profile is too shallow for comparison or routing, prioritize **full M6** before semantic retrieval.

### Outcome C — cross-repository comparison is the bottleneck

If source-local intelligence is useful and profiles carry enough signal, begin **M6.5a — Structured Representation**:

```text
ArchitectureProfile
      ↓
canonical structured feature vector
      ↓
interpretable similarity / distance
      ↓
small nearest-repository neighborhood
```

Start with deterministic structured features. At the current curated scale, exhaustive comparison remains computationally trivial; no vector database or approximate-nearest-neighbor infrastructure is justified by scale alone.

### Outcome D — interpretation is the bottleneck

If evidence, change signal, and deterministic comparison are already adequate but human interpretation is the expensive step, implement only the minimum representation contract needed to enter **M7 evidence-grounded reasoning** with strict support/provenance constraints.

### M6.5b — Semantic embeddings

Embeddings are a separate follow-on decision.

Add them only when a measured retrieval/comparison task cannot be served adequately by structured profiles or simple deterministic search. Embeddings must earn their place through retrieval quality or review-effort improvement, not by roadmap sequence alone.

## Exit artifact

Close V2-P0 with one immutable report containing:

```text
PASS | FAIL | INCONCLUSIVE
```

and:

- sampled repositories/revisions;
- measurement summary;
- useful findings;
- important misses;
- attention/cost result;
- product-value judgment;
- selected next bottleneck;
- explicit next milestone (`full M5`, `full M6`, `M6.5a`, or minimal representation → `M7`).

The report must not claim V2 success. It only authorizes the next narrow implementation slice.

## Governing rule

> **After V1, LemmaMind must prove that its deterministic machinery saves attention and produces useful intelligence on prospectively observed changes before representation or reasoning volume is increased.**
