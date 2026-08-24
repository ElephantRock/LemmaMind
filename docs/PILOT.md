# LemmaMind M−1 — Manual Intelligence Pilot

## Purpose

Validate the core LemmaMind product hypothesis **before** implementing the ingestion and intelligence platform.

The hypothesis is:

> Evidence-grounded cross-source technical analysis can produce decision-relevant knowledge while preserving provenance, epistemic boundaries, governance constraints, and human authority.

M−1 is a falsification exercise. A negative result is useful if it prevents building infrastructure around an intelligence loop that does not create enough value.

## Product boundary under test

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

## Current pilot question

The first manual corpus tests:

> **Can disciplined evidence-grounded analysis across heterogeneous technical repositories surface decision-relevant findings while preserving provenance, epistemic status, governance boundaries, belief revision, and the separation between intelligence and optional action?**

This replaces the earlier assumption that M−1 had to begin with a 10–20 repository agent-runtime architecture survey. That narrower domain remains useful later, but the first risk to validate is the intelligence method itself.

## Corpus

The controlled first corpus is the other repositories under the ElephantRock organization, pinned to exact revisions in `pilot/watchlist.yaml`.

They intentionally span different repository roles:

- executable systems;
- expensive evidence-generation workflows;
- empirical research programs;
- preregistered / confirmatory experiments;
- evidence-heavy governance infrastructure;
- graduated subsystems;
- overlapping research-program identities;
- public and private repository CI surfaces.

The resulting manually judged cases live under `eval/pilot/cases/`.

## Golden cases

The initial corpus contains eight cases:

1. **ExpertForge scan accounting** — an evidence-generation defect that should be caught before an expensive corpus scan.
2. **ExpertOS telemetry accounting** — historical evidence remains immutable while a defective measurement contract invalidates derived profitability features.
3. **Resonance-Field lineage attribution** — graph connectivity is not automatically evidence of intervention-mediated causal transmission.
4. **Resonance-World confirmatory cancellation** — a failed confirmatory campaign cannot be treated like ordinary CI when the prospective design forbids rerun.
5. **ASRI repository boundary** — similarly named repositories can represent distinct experimental lines under one research program.
6. **Resonance-ContextGraph release provenance** — a narrow provenance correction can be appropriate without changing graduated runtime/scientific semantics.
7. **CSD-Foundry frontier reconciliation** — implementation completion and independent qualification closure are distinct; new evidence can supersede a prior conclusion.
8. **Private Actions pattern** — cross-repository comparison can produce a stronger shared-infrastructure hypothesis than independent local interpretations.

The machine-readable schema is `eval/pilot/schema/pilot-case.schema.json`.

## Known limitation

All initial cases come from repositories controlled by ElephantRock.

This validates:

- evidence discipline;
- intelligence quality;
- high-value anomaly detection;
- cross-repository reasoning;
- scientific/governance boundaries;
- belief revision;
- the distinction between technical capability and authority;
- the distinction between intelligence and optional action.

It does **not yet empirically validate** the action model for a truly external repository that LemmaMind cannot modify.

Before M−1 is fully closed, add at least one real external `EXTERNAL`, `READ_ONLY`, or `CONTRIBUTABLE` case. The case must still be useful when the correct outcome is learning, avoidance, local mitigation, monitoring, upstream reporting, upstream contribution, or no action.

Do not invent a synthetic external case merely to satisfy this gate.

## Epistemic rules

### ObservedFact

A directly inspectable property of captured source material.

### SourceAssertion

A claim made by the source or its maintainers. It is not automatically a system fact.

### Interpretation

A structural interpretation explicitly supported by evidence.

### Inference / Hypothesis

A higher-order conclusion whose support is indirect or incomplete.

### Evaluation

A judgment about significance, quality, risk, or actionability that is itself derived rather than source evidence.

No stage may erase the distinction between these classes.

## Evidence requirements

Every durable pilot claim should identify, as applicable:

- repository / technical source;
- exact revision or immutable source identity;
- artifact path, issue, PR, release, workflow run, or experiment record;
- smallest practical source locator;
- evidence class;
- observation support edges;
- review / validation state.

Preferred source locators include line ranges, JSON pointers, YAML/TOML keys, AST symbols, directory paths, dependency entries, workflow/job IDs, PR/issue identities, and content-addressed artifacts.

## Manual intelligence workflow

```text
Select source / event
        ↓
Pin source identity
        ↓
Inspect high-signal artifacts
        ↓
Record ObservedFacts / SourceAssertions
        ↓
Write explicit Interpretations / Inferences
        ↓
Reconcile issue / PR / commit / CI / experiment state
        ↓
Compare related repositories when useful
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

A useful observation may lead to any of these operational dispositions:

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

`fix repository` is only one optional action and is never an M−1 success criterion.

## Correct no-action behavior

M−1 explicitly tests whether LemmaMind can recognize situations where intervention would reduce evidence quality or violate governance.

Examples include:

- do not blindly rerun a preregistered confirmatory experiment;
- do not self-ratify an independent acceptance gate;
- do not modify graduated scientific semantics merely to create activity;
- do not rewrite historical evidence after discovering a measurement defect.

The ability to refrain from action is part of intelligence quality.

## Belief revision

Golden cases may contain superseded conclusions.

Expected lifecycle:

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

CSD-Foundry's implementation-vs-qualification frontier is the first canonical pilot example.

## Required M−1 capabilities

Before exit, the corpus should demonstrate at least:

- one useful single-repository observation;
- one useful cross-repository pattern;
- one architectural or research tension;
- one negative / failure / reversal finding;
- one case where no action is the correct response;
- one case requiring belief revision after new evidence;
- one case where technical ability to act is not sufficient authority to act;
- one real external case where source modification is unavailable or optional;
- one result that changes an actual engineering or research decision.

The current ElephantRock corpus satisfies all except the real external-source requirement and the final explicit M−1 closeout decision.

## Measurements

Record at minimum:

- repositories / sources considered;
- cases accepted into the golden corpus;
- evidence items inspected;
- unsupported interpretations caught during review;
- conclusions superseded after new evidence;
- cross-repository patterns identified;
- actions recommended;
- cases where no action was recommended;
- human review time and friction;
- useful insights / decisions produced;
- false positives and low-signal findings.

## Automation pass criteria

Later automated implementations are evaluated against the manual corpus.

For each golden case they should:

1. recover the high-value observation or a semantically equivalent one;
2. cite sufficient evidence;
3. preserve epistemic class;
4. avoid stronger certainty than the evidence permits;
5. recover the relevant ownership / authority boundary;
6. recommend an allowed action or no-action disposition;
7. avoid every prohibited action;
8. rank the case appropriately relative to routine repository churn.

More extracted data is not an improvement if these distinctions are lost.

## Success gate

M−1 passes only if LemmaMind's manual process demonstrates:

> **I would investigate, design, implement, adopt, avoid, monitor, or believe something differently because of this evidence-grounded intelligence.**

Repository modification is not required.

## Failure outcomes

If the pilot produces mostly generic observations, determine whether failure came from:

- corpus selection;
- weak evidence capture;
- poor source-state reconstruction;
- overly broad questions;
- missing process/history evidence;
- unsupported inference;
- weak cross-source comparison;
- poor attention prioritization;
- or the core product hypothesis itself.

Do not respond to failure by adding infrastructure.

## Exit from M−1

M−1 exits when:

1. the product contract in `docs/PRODUCT.md` is frozen;
2. the initial golden corpus is reviewed;
3. at least one real external-source case is added;
4. the success gate is explicitly judged PASS or FAIL;
5. the successful manual intelligence workflow is documented;
6. only the M0 contracts required by actual pilot cases are selected.

If M−1 passes, begin V1 with the reproducible evidence spine:

```text
Repository / Source
  ↓
SourceRevision
  ↓
CaptureManifest
  ↓
Artifact
  ↓
EvidenceFact / SourceAssertion
```

No autonomous insight synthesis is required for V1.
