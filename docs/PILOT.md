# LemmaMind M−1 — Manual Intelligence Pilot

## Status

**PASS — complete.**

See `eval/pilot/M-1-CLOSEOUT.md` for the explicit success-gate judgment and `docs/M0-CONTRACTS.md` for the minimum contracts selected from pilot evidence.

## Purpose

Validate the core LemmaMind product hypothesis **before** implementing the ingestion and intelligence platform.

The hypothesis is:

> Evidence-grounded cross-source technical analysis can produce decision-relevant knowledge while preserving provenance, epistemic boundaries, governance constraints, source role, and human authority.

M−1 was a falsification exercise. The goal was not to maximize harvested repositories; it was to learn whether the intelligence loop itself produces enough value to justify automation.

## Product boundary tested

LemmaMind is responsible for:

```text
Technical source
      ↓
Evidence
      ↓
Observation
      ↓
Assessment
      ↓
Pattern / tension / insight
      ↓
Decision-relevant knowledge
```

Repository repair is **not** part of the mandatory success path.

A separate optional action path may follow an observation:

```text
Observation
    ↓
Impact assessment
    ↓
Repository relationship / authority
    ↓
Action recommendation
    ↓
Optional explicitly authorized action
```

The ability to modify a repository must never determine whether an observation is worth preserving.

## Pilot question

> **Can disciplined evidence-grounded analysis across heterogeneous technical sources surface decision-relevant findings while preserving provenance, epistemic status, source role, governance boundaries, belief revision, and the separation between intelligence and optional action?**

## Corpus

The completed corpus is pinned in `pilot/watchlist.yaml`.

### Controlled corpus

Nine ElephantRock repositories supplied heterogeneous cases involving:

- executable systems;
- expensive evidence-generation workflows;
- empirical research programs;
- preregistered / confirmatory experiments;
- evidence-heavy governance infrastructure;
- graduated subsystems;
- overlapping research-program identities;
- public and private repository CI surfaces.

### External validation corpus

Four real external repositories were then inspected with no direct source write authority:

- `chrisliu298/awesome-on-policy-distillation`
- `CopilotKit/OpenBot`
- `openclaw/openclaw`
- `NousResearch/hermes-agent`

They deliberately add two source classes:

1. a curated research index used for discovery/taxonomy;
2. executable agent/runtime repositories used for architecture and change intelligence.

This external phase validates that useful intelligence does not depend on the ability to repair the source.

## Golden cases

The machine-readable cases live under `eval/pilot/cases/` and conform to `eval/pilot/schema/pilot-case.schema.json`.

Initial controlled cases:

1. ExpertForge scan accounting
2. ExpertOS telemetry accounting
3. Resonance-Field lineage attribution
4. Resonance-World confirmatory cancellation
5. ASRI repository boundary
6. Resonance-ContextGraph release provenance
7. CSD-Foundry frontier reconciliation
8. Private Actions cross-repository pattern

External validation cases:

9. OpenBot capability authority
10. OpenClaw sandbox posture
11. Hermes process containment change
12. OPD source-type boundary
13. External runtime-authority cross-repository pattern

## Epistemic rules

### ObservedFact

A directly inspectable property of captured source material.

### SourceAssertion

A claim made by the source or its maintainers. It is evidence that the source **said** something; it is not automatically a system fact.

### Interpretation

A structural interpretation explicitly supported by evidence.

### Inference / Hypothesis

A higher-order conclusion whose support is indirect or incomplete.

### Evaluation

A judgment about significance, quality, risk, or actionability that is itself derived rather than source evidence.

No stage may erase the distinction between these classes.

## Evidence requirements

Every durable pilot claim should identify, as applicable:

- source / repository;
- exact revision or immutable source identity;
- source role;
- artifact path, issue, PR, release, workflow run, experiment record, or repository tree;
- smallest practical source locator;
- evidence class;
- observation support edges;
- review / validation state.

Preferred locators include line ranges, JSON pointers, YAML/TOML keys, AST symbols, directory paths, dependency entries, workflow/job IDs, PR/issue identities, and content-addressed artifacts.

## Manual intelligence workflow

```text
Select source / event
        ↓
Pin source identity
        ↓
Classify source role
        ↓
Inspect high-signal artifacts
        ↓
Record ObservedFacts / SourceAssertions
        ↓
Write explicit Interpretations / Inferences
        ↓
Reconcile current vs historical state
        ↓
Compare related sources when useful
        ↓
Assess impact and uncertainty
        ↓
Determine repository relationship / authority
        ↓
Recommend action or explicit no-action
        ↓
Human review
        ↓
Freeze useful case into golden corpus
```

## Action boundary

Repository relationships are initially classified as:

```text
OWNED
CONTRIBUTABLE
EXTERNAL
READ_ONLY
UNKNOWN
```

A useful observation may lead to:

- learn / incorporate;
- investigate further;
- adopt;
- avoid;
- pin / version-gate;
- mitigate locally;
- monitor;
- report upstream;
- contribute upstream;
- fork / vendor when justified;
- revalidate existing knowledge;
- take no action.

`fix repository` is only one optional action and was never an M−1 success criterion.

## Correct no-action behavior

M−1 demonstrated several cases where intervention would reduce evidence quality, duplicate already-completed work, or violate governance:

- do not blindly rerun a preregistered confirmatory experiment;
- do not self-ratify an independent acceptance gate;
- do not rewrite historical evidence after discovering a measurement defect;
- do not open an upstream repair for a defect already fixed at the pinned external revision;
- do not modify an external project merely because its design tradeoff differs from ours.

The ability to refrain from action is part of intelligence quality.

## Source-role boundary

The external OPD case showed that repository identity alone is not enough.

A repository may act primarily as:

```text
implementation
research_index
research_program
mixed
unknown
```

A research index can be excellent discovery evidence while still requiring follow-through to linked primary sources before implementation or scientific claims are promoted.

This finding is why `Source` and `source_role` enter M0.

## Belief revision

Golden cases may contain superseded conclusions.

```text
Observation / conclusion v1
        ↓
new evidence
        ↓
review
        ↓
Observation / conclusion v2
        ↓
supersedes v1 without erasing it
```

CSD-Foundry remains the canonical initial example. Hermes adds a related historical/current-state case: a real containment defect is useful negative intelligence, but the pinned current revision already contains the repair and must not be reported as currently unfixed.

## External architecture result

Comparison of OpenBot, OpenClaw, and Hermes changed the planned agent-runtime representation.

Execution authority must be decomposed into at least these candidate M6 dimensions:

```text
instruction / skill loading
capability authority
declared tool requirements
execution location
control-plane location
isolation default
isolation scope / backend
elevation or escape paths
process-tree / descendant containment
```

A single `sandboxed` or `tools_available` field would lose decision-relevant structure.

## Required M−1 capabilities — final result

| Capability | Result |
|---|---|
| Useful single-repository observation | PASS |
| Useful cross-repository pattern | PASS |
| Architectural/research tension | PASS |
| Negative/failure/reversal intelligence | PASS |
| Correct no-action case | PASS |
| Belief revision after new evidence | PASS |
| Ability-to-act != authority-to-act | PASS |
| Real external case with no source modification authority | PASS |
| Result changes an engineering/research decision | PASS |

## Automation pass criteria

Later automated implementations are evaluated against the manual corpus.

For each golden case they should:

1. recover the high-value observation or a semantically equivalent one;
2. cite sufficient evidence;
3. preserve epistemic class;
4. preserve source role and evidence strength;
5. avoid stronger certainty than the evidence permits;
6. recover the relevant ownership / authority boundary;
7. recommend an allowed action or no-action disposition;
8. avoid every prohibited action;
9. preserve repaired/superseded history without confusing it with current state;
10. rank the case appropriately relative to routine repository churn.

More extracted data is not an improvement if these distinctions are lost.

## Success gate

M−1 passes only if the manual process demonstrates:

> **I would investigate, design, implement, adopt, avoid, monitor, or believe something differently because of this evidence-grounded intelligence.**

**Judgment: PASS.**

The external corpus directly changed LemmaMind design before implementation:

- M0 now needs `Source` + `source_role`, not repository identity alone;
- documentation/index claims remain `SourceAssertion` until corroborated;
- repository relationship is separate from knowledge validity;
- M6 runtime authority will be multi-dimensional rather than a sandbox/tools boolean;
- repaired historical defects remain negative/change intelligence without implying current repair work.

## Exit from M−1

All exit conditions are satisfied:

1. product contract frozen — PASS;
2. initial golden corpus reviewed — PASS;
3. real external-source cases added — PASS;
4. success gate explicitly judged — PASS;
5. successful manual intelligence workflow documented — PASS;
6. minimum M0 contracts selected from actual cases — PASS (`docs/M0-CONTRACTS.md`).

Proceed to **M0 — Minimum System Contracts**.

The next implementation rule is:

> **Automate the evidence spine without losing distinctions the manual pilot already demonstrated.**

No autonomous insight synthesis is required for M0/V1.
