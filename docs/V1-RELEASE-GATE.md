# LemmaMind V1 — Evidence Engine Release Gate

## Release definition

The roadmap defines V1 as:

```text
M0
+ M1 Curated Discovery
+ M2 Repository Registry
+ M3 Revision Capture
+ M4 Deterministic Evidence
+ M5-lite Change Intelligence
+ M6-lite Profiling & Triage
+ basic review/feedback capture
```

V1 explicitly excludes autonomous insight synthesis.

The release success question is:

> **Can LemmaMind reliably know what changed and prove every extracted fact while preserving the M−1 evidence and action boundaries?**

This document evaluates that exact boundary. It does not reinterpret V1 as full M5/M6, M6.5, M7, or the complete human review queue.

## Gate result

**V1 Evidence Engine: PASS, conditional only on final unchanged-head CI and merge of the release-gate branch.**

The release has executable gates for the required layers and retains the critical M−1 epistemic/action invariants.

## Capability matrix

| V1 requirement | Executable state | Gate judgment |
| --- | --- | --- |
| M0 contracts/persistence | strict versioned contracts + append-only SQLite + typed provenance | PASS |
| M1 curated discovery | `DiscoveryChannel → DiscoveryRun → DiscoveryHit`, including unresolved hits | PASS |
| M2 registry | stable provider-ID identity, locator evolution, tracking history/policy gates | PASS (V1 core) |
| M3 revision capture | exact commit/tree, manifest/CAS, local-only historical reconstruction | PASS |
| M4 deterministic evidence | deterministic evidence extraction + exact local inspection | PASS |
| M5-lite change intelligence | factual `ArtifactDelta → StructuralDelta` with generation binding | PASS |
| M6-lite profiling/triage | revision-bound ArchitectureProfile + deterministic triage reasons | PASS |
| basic review/feedback capture | append-only ReviewDecision + reviewer/subject/run provenance | PASS after this branch |
| M−1 evidence/action boundaries | golden/hard cases retained; action evaluation never self-authorizes | PASS |

## End-to-end V1 evidence path

```text
DiscoveryChannel
      ↓
DiscoveryRun
      ↓
DiscoveryHit
      ↓
DiscoveryResolution
      ↓
stable Source + RepositoryLocator
      ↓
RepositoryTrackingAssignment / TrackingPolicy
      ↓
tracking-aware capture
      ↓
SourceRevision
      ↓
CaptureManifest + content-addressed Artifacts
      ↓
M3 local reconstruction
      ↓
EvidenceFact / SourceAssertion
      ↓
M4 exact evidence inspection
      ↓
ArtifactDelta → StructuralDelta
      ↓
ArchitectureProfile
      ↓
TriageAssessment
      ↓
ReviewDecision + ReviewFeedback
```

This is the V1 evidence engine. Later Observation/Pattern vertical proofs already exist, but V1 does not depend on autonomous reasoning or cross-repository synthesis.

## What "know what changed" means in V1

V1 establishes factual change at two deterministic layers:

1. **ArtifactDelta** — capture-scope, retrieval-state, retained-byte, and media-type changes.
2. **StructuralDelta** — normalized deterministic `EvidenceFact` add/remove/modify changes under exactly bound compatible extraction generations.

This is intentionally narrower than semantic significance.

V1 does **not** claim that every StructuralDelta is meaningful, important, architectural, causal, or decision-relevant. Those classifications remain full-M5/V2 work.

## What "prove every extracted fact" means in V1

For current deterministic evidence families, `EvidenceInspectionService` traces an EvidenceFact or SourceAssertion through its producing extraction run, Artifact, CaptureManifest, SourceRevision, and retained content-addressed material.

Supported locator families resolve either to:

- the exact retained source value/span; or
- an explicitly identified deterministic derivation substrate when the fact is an aggregate or immutable Artifact metadata fact.

The M4 extractor-surface regression requires every record emitted by the current Markdown/manifest/Python/TypeScript source-file extraction stack to resolve through `audit_all()`.

No provider refetch is required to inspect historical retained evidence.

## Basic review/feedback capture

The original M0 `ReviewDecision` contract existed before V1 but was not itself an executable review path.

The V1 release-gate slice adds `ReviewFeedbackService` plus immutable `ReviewFeedback` provenance.

One review action now atomically persists:

```text
PipelineRun(run_type=evaluation)
ReviewDecision
ReviewFeedback
```

`ReviewFeedback` records:

- ReviewDecision ID;
- exact subject contract type and ID;
- supplied reviewer identity;
- producing review PipelineRun;
- recorded timestamp.

The default V1 reviewable high-level subject types are:

```text
ArchitectureProfile
TriageAssessment
Observation
Pattern
ActionRecommendation
```

Low-level EvidenceFact is not reviewable by default; evidence is inspected rather than "voted true" through this service.

### Governance boundary

The supplied `reviewer_id` is provenance, not authenticated authority.

A review action does not:

- mutate candidate/reviewed/validated state;
- automatically promote an Observation or Pattern;
- authorize an ActionRecommendation;
- alter repository relationship;
- create source-write authority.

Thus a `PROMOTE` review decision remains feedback unless a later explicit promotion authority/process consumes it.

Multiple review decisions for one subject remain append-only history.

## M−1 boundary preservation

V1 retains the pilot distinctions that drove the architecture:

- `red CI != test failure`;
- write access != rerun authority;
- authored instructions != runtime capability grants;
- sandboxing is layered, not binary;
- a research index is not automatically an implementation;
- missing qualification evidence can narrow/supersede an earlier conclusion;
- cross-repository infrastructure hypotheses require supporting cases and negative controls;
- correct no-action is a valid outcome.

The hard-case readiness matrix reached `4 ready / 0 blocked / 0 deferred` in their correct semantic layers before V1 closeout.

## Evidence from milestone checkpoints

The evidence engine has been exercised incrementally rather than only by unit fixtures:

- deterministic external repository evidence recovery reached **12/12** on the frozen OpenBot/OpenClaw/Hermes/OPD requirements;
- M3 local reconstruction reached **163 tests** and proved a captured revision could replay with zero provider reads;
- M4 exact evidence inspection reached **174 tests**;
- M5-lite final branch reached **184 tests**, plus a read-only immutable M3→M4 live comparison;
- M6-lite final branch reached **194 tests**, plus a read-only immutable M4→M5 profile/triage probe;
- V1 basic review implementation first reached **201 tests** before the final closeout additions.

The final V1 release branch must pass the ordinary permanent PR workflow unchanged before merge.

## Cost and scale disclosure for V1

The roadmap requires a scale/cost estimate before a major release. V1 is still a manually invoked evidence engine, not an autonomous monitoring service, so the honest current operating estimate is intentionally sparse.

### Current curated inventory

The frozen manual watchlist contains **13 repositories**.

No production tracking-assignment database is committed with the repository. Under the executable policy, an unassigned Source resolves operationally to tracking level `0 — Ignore` until an explicit assignment is made.

### Autonomous workload at V1 default

Because V1 does not ship a scheduler:

```text
autonomous snapshots/month:     0
autonomous GitHub API requests:  0/day
embedding operations/month:      0
LLM tokens/month for V1 engine:   0
scheduled review queue minutes:   0/week
```

Manual and CI-triggered runs consume GitHub API calls, temporary storage, and Actions compute only when explicitly invoked.

### Persistent storage growth

CI/live validation uses temporary databases/object stores, so it does not provide a defensible production storage/month measurement.

Production storage growth is therefore **not yet measured**. Before a scheduler or continuous tracking level is enabled in a real deployment, LemmaMind must measure bytes per capture/artifact and derive a storage budget from actual assigned tracking levels.

### Monetary cost

V1 introduces no embeddings and no LLM inference into the evidence engine, so incremental model/embedding API cost is **$0 by design**.

GitHub Actions/provider-plan and local storage costs are environment-dependent and are not asserted as zero.

## Explicit release limitations

A V1 PASS does not imply:

- a scheduler or continuous monitoring daemon;
- full M5 ChangeInterpretation;
- semantic/LLM ArchitectureProfile generation;
- learned relevance ranking;
- M6.5 embeddings or nearest-neighbor search;
- autonomous Observation generation;
- the M7.5 attention-budgeted review queue;
- automatic Pattern discovery;
- Insight/Knowledge promotion;
- action execution or authorization issuance;
- a user interface.

## V1 → V2 boundary

The roadmap places full M5, full M6, M6.5, M7, M7.5, and M8-lite in V2.

The next decision after V1 is therefore a **product-value reassessment**, followed by M6.5 only if representation/similarity is actually justified. The existing early Observation/Pattern vertical proofs should be treated as evidence for later design, not as permission to skip the release reassessment.
