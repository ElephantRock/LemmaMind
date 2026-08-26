# LemmaMind V2-P0 — Product-Value Probe Closeout

## Result

**FAIL**

This is a failure of the **post-V1 prospective product-value gate**, not a regression of the V1 Evidence Engine release result.

V1 remains PASS for its release contract: deterministic capture, reconstructable evidence, exact source inspection, factual change records, revision-bound profiling/triage, and append-only review provenance. V2-P0 asks a different product question: whether that machinery, on ordinary fresh activity selected without hindsight, is already sufficient to save attention and surface the mechanisms worth investigating.

It is not yet sufficient.

## Product question

> Does the V1 Evidence Engine make fresh technical-change investigation materially better than manually inspecting GitHub?

For the first three eligible prospective intervals, the answer is **no**. LemmaMind reliably proved that repository state changed and provided exact top-level Git-tree localization, but it did not surface a genuinely useful mechanism-level finding before bounded manual review. Manual review then found multiple directly relevant architecture, governance, evidence-integrity, and temporal-correctness changes in every active interval.

## Prospective sample

The V2-P0 corpus was frozen at five repositories. Three advanced beyond the baseline and became eligible before this gate was stopped. ERLab and Resonance-World had not advanced beyond their frozen baselines at the time of the check and therefore did not produce revision intervals.

| Repository | Previous revision | Fresh revision | Deterministic triage | Useful surfaced findings | Important misses |
| --- | --- | --- | --- | ---: | ---: |
| CopilotKit/OpenBot | `43ea5c1…` | `e8aa344…` | `review` | 0 | 3 |
| openclaw/openclaw | `20eef85…` | `aec260b…` | `review` | 0 | 4 |
| NousResearch/hermes-agent | `b2bd1ac…` | `a6d6060…` | `review` | 0 | 3 |
| ElephantRock/ERLab | `6f13f80…` | no later revision observed | — | — | — |
| ElephantRock/Resonance-World | `0f38ba4…` | no later revision observed | — | — | — |

Stopping after three changed external intervals is intentional. The protocol defines repeated important misses as a FAIL condition. Once the same defect appeared independently across all three eligible intervals, spending additional review attention on inactive sources was not required to establish the gate failure.

## Deterministic execution provenance

The corrected first-interval probe exercised existing V1 capability rather than a narrower synthetic substitute:

```text
exact SourceRevision
      ↓
prospectively selected explicit-file capture
      +
tracking-aware exact non-recursive Git root-tree capture
      ↓
deterministic evidence extraction
      ↓
ArtifactDelta / StructuralDelta
      ↓
revision-bound ArchitectureProfile
      ↓
deterministic TriageAssessment
```

Workflow run `33017750243`, job `98340261443`, at probe commit `8acbf021672dcbc1f4d3d2e3bd2d7bb6ec6f71b0` completed successfully and ran the permanent suite at **202 passed** before executing the three intervals.

The deterministic probe path used **0 LLM tokens** and **0 embedding operations**.

## Measurement summary

- useful fresh findings surfaced prospectively: **0**
- decision-relevant findings surfaced prospectively: **0**
- cases where exact evidence was materially useful enough to satisfy the gate: **0**
- eligible changed intervals evaluated: **3**
- provider requests measured by the probe: **30**
- retained unique artifact bytes measured by the probe: **375,696 bytes**
- measured deterministic pipeline runtime across the three intervals: **8.752 seconds**
- persistent SQLite bytes added: `not_measured`
- human review minutes: `not_measured`
- weekly attention-budget compatibility: **not established**
- LLM tokens: **0**
- embedding operations: **0**

The retained-byte figure is the probe's unique retained object bytes for the selected explicit files plus root-tree artifacts; it is not a claim about total upstream interval size.

## What V1 surfaced

### OpenBot

V1 correctly proved a new root tree and localized top-level changes to `.github`, `CHANGELOG.md`, `app`, `charts`, and `server`. The two prospectively selected explicit files were unchanged, so their comparison produced no ArtifactDelta and no StructuralDelta. Triage routed the revision to `review` because tracking was Deep, domain match was true, and the profile was evidence-rich.

This was directionally correct but low-signal. It did not identify a mechanism worth attention.

### OpenClaw

V1 proved a new root tree with changes across fifteen top-level entries and identified `docs/gateway/sandboxing.md` as `content_changed`. The selected explicit-file evidence still produced zero StructuralDelta records. Triage again returned `review`.

The interval contained roughly 150 commits. A generic `review` route plus broad top-level tree movement does not reduce the inspection problem enough at this activity rate.

### Hermes Agent

V1 proved a new root tree with changes across twelve top-level entries. The selected local-process files were unchanged and produced zero StructuralDelta records. Triage returned `review`.

Again, this correctly answered “something changed” but did not answer “what mechanism should I care about?”

## Important misses found by bounded manual review

Manual review was performed only after the deterministic probe output was captured.

### OpenBot misses

1. `e8aa34451f73ef2719c22cc557be369d9ea70afb` — an **attention inbox for refusals and stalls** derived from existing append-only audit events, with separate attributed resolution state. This is directly relevant to LemmaMind's future attention-budgeted review loop.
2. `3c1a067ef2371298135ed4a879c670368022ec5f` — a **policy dry-run against historical judged actions before saving a boundary rule**, without writing audit decisions during the dry run. This is directly relevant to evidence-bound governance.
3. `50949d6eda31b34f2cbf56f81d127750c47c7291` — named **undecided routing causes** such as unreachable, unparsed, off-roster, unconfident, and one-candidate. This is useful failure taxonomy and observability intelligence.

### OpenClaw misses

1. `ce4a680544a3502f98d3c9dc49ab9b9e77e7c43b` — **configurable model-selection scopes** with session/agent/global persistence while deliberately not broadening configuration-write authority.
2. `e0a4915bcf162a1175877d4f741474b41ca3f9e0` — **validate a capture batch before publishing files**, avoiding partial publication after a malformed later response.
3. `fa87acd0b87aaa374c61cd0fa4c1610c9a364db4` — **recheck idle and node readiness after waits**, a temporal/stale-state correctness mechanism.
4. `aec260b7002cf56232add300f3dd3454c81a10cf` — **preserve worker timeouts across clock changes**, another concrete temporal-correctness mechanism.

### Hermes Agent misses

1. `4860978115a018913fe51efd61b2319e9273d0a4` — a shared **update-admission gate** that refuses in-place mutation for image/package-managed installs, honors authoritative provenance, fails closed on corrupted markers, and distinguishes refusal from execution errors.
2. `07200e9cd67f777de79497cc807a644861b2c87b` — **project completed agent-as-provider tool work into the durable turn** without turning already-completed calls back into pending actions.
3. `19f9d1badbb5748611807e84538527b8826567da` — **fail closed on a headless model guard** instead of hanging on a confirmation surface nobody can answer.

These are not marginal misses. They map directly onto LemmaMind's own product concerns: authority boundaries, evidence integrity, temporal reconciliation, attention management, durable provenance, and fail-closed operation.

## Triage and attention judgment

Triage was not wrong in the narrow sense: all three changed repositories were routed to `review`. The problem is that `review` remained too coarse.

The deterministic profile and root-tree signal can say that a source deserves inspection, but they cannot yet isolate the changed mechanism or suppress enough irrelevant surface to make review cheap. At high source velocity, especially the OpenClaw interval, this creates the exact attention burden V2-P0 was designed to detect.

Human review time was not measured, so this closeout does **not** claim a numerical productivity loss or weekly-minute total. Because the protocol requires explicit measurement rather than estimates, attention-budget compatibility remains unproven.

## Evidence-usefulness judgment

Exact evidence was **helpful** but not **material enough to pass the gate**.

The retained root-tree artifacts provided reproducible proof that the repository changed and correctly localized broad top-level areas. That is valuable auditability. However, bounded manual review still had to inspect revision history/change details to discover the mechanisms that mattered. The evidence trail therefore did not materially reduce verification effort for a prospectively surfaced useful finding, because no such useful finding was surfaced.

## Decision effects

No V1-surfaced candidate from these intervals changed or materially focused an investigation, design, adoption/avoidance, monitoring, or belief-revalidation decision before manual review.

The manually discovered misses do influence what LemmaMind should build next: they show that representation/embeddings are not the immediate bottleneck. The immediate product deficit is **change localization and significance**.

## Gate check

- [ ] At least two genuinely useful fresh findings were surfaced prospectively.
- [ ] At least one surfaced finding changed or materially focused a decision/investigation.
- [ ] Exact evidence was materially useful in at least one surfaced useful case.
- [ ] Review burden is demonstrated compatible with the attention budget.
- [ ] Noise is low enough that corpus growth appears plausible under the current change surface.
- [ ] Important misses do not show systematic hiding of the most valuable changes.

The last condition fails positively: all three eligible changed intervals contained high-value misses that were not isolated by the V1 surfaced change signal.

## Bottleneck judgment

**`CHANGE_SIGNAL`**

The dominant issue is not evidence correctness, profile storage, cross-repository similarity, or semantic embeddings. It is the gap between:

```text
root tree changed
```

and:

```text
these exact changed mechanisms are worth your attention
```

The current root-tree evidence is intentionally non-recursive, and explicit-file capture only produces useful deltas when the changed mechanism happens to intersect the governed selected files. That is insufficient for prospective technical-change intelligence.

A secondary operational issue is **cadence**. Very active repositories can accumulate tens or hundreds of commits between observations. Scheduler cadence should eventually be measured against source velocity and attention budget, but cadence does not remove the primary need for better change localization and suppression.

## Next authorized slice

**`full M5`**

The first full-M5 implementation slice should remain narrow and deterministic before adding broader semantic interpretation:

1. **Recursive changed-path localization** from exact Git revision/tree evidence, without cloning or executing untrusted source code.
2. **Affected-file capture planning** so the evidence engine captures changed eligible files rather than relying only on a fixed explicit-file set.
3. **Deterministic churn suppression/classification** where possible: generated, vendored, lockfile-only, formatting-only, docs-only, config, source, test, workflow, and similar surface classes.
4. Only then introduce explicit provenance-bound **`ChangeInterpretation`** for meaningful adoption, removal, reversal, deprecation, failure, authority/governance, and project-state changes.

The next full-M5 gate should ask whether these changes convert the three frozen V2-P0 failures into a small, auditable set of mechanism-level candidates without manufacturing causal claims.

## Explicit deferrals

V2-P0 does **not** authorize:

- M6.5 semantic embeddings;
- vector infrastructure;
- learned ranking;
- autonomous observation generation;
- automatic pattern discovery;
- knowledge promotion;
- action authorization or execution.

M6.5 remains deferred until source-local change intelligence is useful and cross-repository comparison is the measured bottleneck.

## Final verdict

> **V2-P0: FAIL — V1 evidence is reproducible and trustworthy, but the prospective product bottleneck is change signal. Proceed to full M5, beginning with recursive changed-path localization and deterministic suppression before semantic interpretation.**
