# LemmaMind M−1 — Manual Intelligence Pilot

## Purpose

Validate the core LemmaMind product hypothesis **before** implementing the ingestion and intelligence platform.

The hypothesis is:

> Cross-repository technical analysis, when grounded in reproducible evidence and explicit epistemic boundaries, can produce insights that materially influence engineering or research decisions.

M−1 is a falsification exercise. A negative result is useful because it prevents months of infrastructure work around an intelligence loop that does not create enough value.

## Pilot question

Initial proposed question:

> **How do modern coding/agent runtimes separate model-authored reasoning from privileged execution, state, and capability authority?**

The question may be refined before corpus lock, but the pilot must stay within one tightly related domain.

## Scope

Target corpus:

- 10–20 repositories
- architecturally related but intentionally diverse
- fixed to full commit SHAs before analysis
- manually curated; no broad discovery

Prefer a mix of established and unconventional implementations, especially projects with enough architecture/design material to support source-addressed reasoning.

## Required outputs

The pilot must produce at least:

1. **3 cross-repository patterns**
2. **1 architectural tension**
3. **1 negative/reversal observation**, if supported by available history
4. **1 synthesized insight**
5. **1 decision record** describing whether any result changed what should be investigated, designed, implemented, avoided, or reconsidered

## Epistemic rules

### ObservedFact

A directly inspectable property of captured repository material.

### SourceAssertion

A claim made by the repository or its maintainers. It is not automatically a system fact.

### Interpretation

A structural interpretation explicitly supported by evidence.

### Inference / Hypothesis

A higher-order conclusion whose support is indirect or incomplete.

No stage may erase the distinction between these classes.

## Evidence requirements

Every durable pilot claim must identify:

- repository
- full commit SHA
- artifact path
- smallest practical source locator
- evidence class
- capture date

Preferred source locators include line ranges, JSON pointers, YAML/TOML keys, AST symbols, directory paths, and dependency entries.

## Pilot workflow

```text
Repository selection
        ↓
Pin full commit SHA
        ↓
Capture relevant source material
        ↓
Record ObservedFacts / SourceAssertions
        ↓
Write explicit Interpretations / Inferences
        ↓
Compare repositories
        ↓
Identify recurring mechanisms
        ↓
Identify ArchitecturalTensions
        ↓
Look for reversals / negative evidence
        ↓
Synthesize one or more insights
        ↓
Human decision review
```

## Suggested evidence focus

Prioritize high-signal material rather than exhaustive coverage:

- README and architecture/design documentation
- top-level repository structure
- runtime / executor / sandbox / tool directories
- dependency manifests
- capability, provider, plugin, adapter, tool, or runtime interfaces
- CI/deployment definitions where they reveal runtime boundaries
- release notes, RFCs, PR descriptions, or design issues when needed to explain *why*

Do not execute repository code during M−1.

## Pattern template

```yaml
id: pattern_<slug>
name: <human-readable name>
status: candidate
question: <what recurring mechanism does this answer?>
occurrences:
  - repository: owner/repo
    commit_sha: <full sha>
    evidence:
      - <evidence id or file reference>
notes: |
  What is common across the implementations?
  What materially differs?
```

## Architectural tension template

```yaml
id: tension_<slug>
question: <architectural question>
positions:
  - <position A>
  - <position B>
  - <position C if needed>
differentiating_assumptions:
  - <assumption>
evidence:
  - <supporting repository observations>
```

## Insight template

Every synthesized insight should answer:

- What mechanism exists?
- What problem does it solve?
- Under what assumptions?
- What trade-offs does it introduce?
- What competing approaches exist?
- Where has it been observed?
- Where has it failed, been reversed, or contradicted?
- How general is the conclusion?
- What decision could this affect?

## Measurements

Record at minimum:

- repositories considered
- repositories rejected and why
- repositories analyzed
- evidence items inspected
- hours spent
- patterns produced
- patterns judged generic/low-signal
- tensions produced
- unsupported interpretations caught during review
- useful insights produced
- review friction / time

## Success gate

M−1 passes only if at least one result satisfies:

> **I would investigate, design, implement, avoid, or reconsider something differently because of this insight.**

A useful but non-decisive result may justify a second pilot, but it does not automatically justify platform implementation.

## Failure outcomes

If the pilot produces mostly generic architectural observations, determine whether failure came from corpus selection, weak evidence capture, an overly broad question, insufficient process/history evidence, synthesis methodology, or the core product hypothesis itself.

Do not respond to failure by adding infrastructure.

## Exit from M−1

If the pilot passes:

1. freeze the pilot artifacts as the first golden evaluation corpus
2. document the successful intelligence workflow
3. implement only the M0 contracts required by actual pilot data
4. begin V1 with the reproducible evidence spine

```text
Repository
  ↓
RepositoryRevision
  ↓
CaptureManifest
  ↓
Artifact
  ↓
EvidenceFact
```

No autonomous insight synthesis is required for V1.
