# LemmaMind
## Comprehensive Technical Intelligence Roadmap

**Canonical home:** https://github.com/ElephantRock/LemmaMind  
**Initial source ecosystem:** GitHub  
**Product contract:** [`docs/PRODUCT.md`](PRODUCT.md)

## Mission

Build **LemmaMind**, a personal technical-intelligence system that converts reproducible technical evidence into useful engineering and research intelligence.

The desired transformation is:

```text
High-value technical sources
        ↓
reproducible evidence
        ↓
structural understanding
        ↓
meaningful changes
        ↓
evidence-grounded observations
        ↓
cross-source patterns
        ↓
architectural tensions
        ↓
validated insights
        ↓
reviewed knowledge
        ↓
engineering / research decisions
```

The governing principle is:

> **Useful evidence first. Evidence-bound inference second. Reviewed knowledge third. Real decisions are the measure of success.**

## Product contract

LemmaMind should answer questions such as:

- What materially changed in repositories I care about?
- Why might the change matter?
- Which repositories implement a particular mechanism?
- Which mechanisms recur across unrelated projects?
- Which implementations diverge from the common approach?
- Which patterns are emerging, declining, or being reversed?
- What assumptions explain competing architectural approaches?
- Which repository deserves a deep dive?
- Which discovery challenges something I currently believe?
- Which past design decisions were later reverted?
- What evidence supports this insight?
- What should I investigate, adopt, avoid, monitor, or reconsider?

Primary outputs, in priority order:

1. review queue
2. weekly technical-intelligence brief
3. repository/change deep dives
4. pattern dossiers
5. architectural-tension dossiers
6. promoted knowledge
7. action recommendations
8. interactive ask/compare/search interface

Human attention is a scarce system resource. The system should degrade by showing **less**, not by accumulating backlog.

## Knowledge path and action path

Understanding is mandatory; intervention is optional.

```text
                         Observation
                             │
                  ┌──────────┴──────────┐
                  ↓                     ↓
          KNOWLEDGE PATH          ACTION PATH
                  │                     │
               Pattern           Impact assessment
                  ↓                     ↓
               Tension        Ownership / authority
                  ↓                     ↓
               Insight        Action recommendation
                  ↓                     ↓
          Reviewed Knowledge      Optional action
```

Repository write access never makes an observation more true, and lack of write access never makes an observation less useful.

Repository modification is an explicitly authorized downstream action, not a LemmaMind success requirement.

## Governing invariants

1. **Evidence and inference are separate.** No generated interpretation may silently become source evidence.
2. **Every durable derived object has provenance.** It must identify source revision, artifacts, evidence, producer/run, and schema/model/policy version.
3. **Historical evidence is immutable.** New extractor/reasoner versions create new generations rather than rewriting history.
4. **Analysis must be reproducible.** LemmaMind retains the exact material used for analysis.
5. **External repository content is untrusted.** It may be retrieved, parsed, normalized, and statically inspected, but not granted privileged execution authority.
6. **LLM output is never authoritative evidence.** Before reasoning milestones, model output is advisory only.
7. **Repositories are sources, not knowledge.** Durable knowledge concerns mechanisms, patterns, trade-offs, tensions, failures, and reusable principles.
8. **Human attention is budgeted.** Processing volume is not a success metric.
9. **Negative evidence is first-class.** Reversals, deprecations, abandoned designs, and failed experiments matter.
10. **Personalization must retain exploration.** LemmaMind should not become a confirmation filter.
11. **Intelligence is mandatory; action is optional.** A useful finding does not require source modification.
12. **Technical capability is not authority.** Ability to merge, rerun, approve, or modify does not imply epistemic or operational authorization.
13. **Beliefs are revisable without rewriting history.** New evidence may supersede prior observations or conclusions while preserving their lineage.
14. **Repository relationship is operational metadata, not epistemic evidence.** `OWNED`, `CONTRIBUTABLE`, `EXTERNAL`, `READ_ONLY`, and `UNKNOWN` affect action policy, not truth value.

## Permanent foundation planes

These apply from M0 onward rather than appearing as late milestones:

- Provenance & reproducibility
- Security & trust isolation
- Evaluation & quality
- Observability & cost
- Schema & version management
- Human review & feedback
- Ownership / authority boundaries

## Roadmap topology

```text
M−1  Validation Pilot
M0   System Contracts
M1   Curated Discovery
M2   Repository Registry
M3   Revision Capture
M4   Deterministic Evidence
M5   Change Intelligence
M6   Profiling & Triage
M6.5 Representation
M7   Evidence-Grounded Reasoning
M7.5 Human Review Loop
M8   Pattern Intelligence
M9   Insight & Knowledge Promotion
M10  Intelligence Interface
```

Everything beyond M10 is an expansion track rather than critical-path scope.

---

## M−1 — Manual Intelligence Pilot

**Objective:** test the highest-risk assumption before building the platform: can disciplined evidence-grounded analysis produce technical intelligence worth acting on or deliberately not acting on?

The first controlled corpus is the nine-repository ElephantRock portfolio pinned in `pilot/watchlist.yaml`. Eight manually judged cases are frozen under `eval/pilot/cases/`.

The cases exercise:

- evidence-generation integrity;
- measurement validity;
- scientific instrumentation;
- confirmatory-governance boundaries;
- repository/research-line identity;
- release provenance;
- repository-frontier reconciliation;
- belief revision;
- cross-repository infrastructure inference;
- correct no-action behavior.

Before M−1 closes, add at least one **real external repository case** where LemmaMind lacks source modification authority but still produces useful intelligence.

**Gate:** at least one result changes what should be investigated, designed, implemented, adopted, avoided, monitored, or believed; the golden corpus is reviewed; and the external-source action boundary is exercised with real evidence.

Repository repair is not required.

The pilot becomes LemmaMind's first manually judged evaluation corpus and the quality floor for later automation.

## M0 — System Contracts

Define only the contracts required for safe evolution and for the cases observed in M−1:

- stable source/repository identity
- provenance
- trust boundaries
- schema/version policy
- generic `PipelineRun`
- budget policy
- review/feedback events
- `RepositoryRelationship`
- `ActionRecommendation`
- explicit supersession / belief-revision lineage

Start with a small physical schema and evolve it under real data rather than speculative ontology design.

The first physical schema should remain small. Candidate core objects:

```text
Repository
RepositoryRevision
Artifact
EvidenceFact
SourceAssertion
Observation
PipelineRun
ReviewDecision
RepositoryRelationship
ActionRecommendation
```

`RepositoryRelationship` and `ActionRecommendation` must remain separate from evidence truth and knowledge promotion.

**Gate:** every durable derived record can answer what produced it, from which source material, under which versioned contracts; every action recommendation can explain what authority/relationship constraints apply.

## M1 — Curated Discovery

Start narrow:

1. manual watchlist
2. personal stars
3. a small number of saved searches
4. later, topics / organizations / developers / ecosystem expansion

Core lineage:

```text
DiscoveryChannel
       ↓
DiscoveryRun
       ↓
DiscoveryHit
       ↓
Repository
```

**Gate:** every repository can explain why, when, and through which discovery run it entered the system.

## M2 — Repository Registry

Maintain one canonical repository identity across renames, transfers, forks, and repeated discovery.

Track repository relationship separately from identity:

```text
OWNED
CONTRIBUTABLE
EXTERNAL
READ_ONLY
UNKNOWN
```

Relationship may change over time and affects only operational policy.

Tracking levels:

```text
0 — Ignore
1 — Metadata only
2 — Shallow
3 — Structural
4 — Deep
5 — Continuous
```

Tracking level controls capture depth, polling frequency, artifact classes, process/history evidence, and reasoning eligibility.

## M3 — Revision Capture

Separate upstream state from local analysis inputs:

```text
RepositoryRevision = exact upstream Git revision
CaptureManifest     = exact inputs retained for analysis
```

Support API-based shallow capture and deeper Git-based capture where justified.

A materiality gate prevents expensive analysis for every changed HEAD.

**Gate:** historical analysis inputs can be reconstructed locally.

## M4 — Deterministic Evidence

Convert captured artifacts into machine-readable, source-addressable facts.

Initial scope:

- README assertions
- repository tree structure
- Python / JS / TS / Rust / Go dependency manifests
- workflow / release configuration needed by the golden corpus
- issue / PR / run metadata when needed to reconstruct project state

Evidence should carry precise source locators such as line ranges, JSON pointers, TOML keys, AST symbols, directory paths, dependency entries, workflow/job IDs, and immutable GitHub object identities.

At this layer use only:

- `ObservedFact`
- `SourceAssertion`

No architectural interpretation belongs inside deterministic evidence.

**Gate:** any fact can be inspected at its exact source location without trusting generated prose.

## M5 — Change Intelligence

Use three explicit layers:

```text
ArtifactDelta
      ↓
StructuralDelta
      ↓
ChangeInterpretation
```

The first two are factual/normalized. `ChangeInterpretation` is inferred.

Suppress low-value churn such as formatting-only changes, generated files, vendored code, and irrelevant lockfile noise.

Begin negative intelligence here with adoption, reversal, deprecation, removal, failure, cancellation, and supersession events.

Project-state change intelligence must reconcile issue, PR, commit, CI, and experiment state rather than trusting one surface in isolation.

## M6 — Profiling & Triage

Create immutable, revision-bound `ArchitectureProfile` objects with schema and extractor versions.

V1 triage should stay simple and deterministic:

- manual tracking level
- domain match
- evidence richness
- meaningful recent change
- source/process richness
- governance / experiment sensitivity

Do not invent sophisticated numeric weights before enough feedback data exists.

## M6.5 — Representation Layer

Create a measurable similarity space from:

- structured architecture feature vectors
- semantic embeddings of normalized representations

Use them for nearest-neighbor retrieval, deduplication, clustering, novelty, and redundancy detection.

The model later interprets candidate clusters; it should not perform O(N²) pairwise comparisons across the corpus.

## M7 — Evidence-Grounded Reasoning

Introduce durable model-generated observations while preserving authority boundaries.

Inputs may include:

- EvidenceFacts
- SourceAssertions
- ArchitectureProfiles
- StructuralDeltas
- selected untrusted source excerpts
- repository relationship metadata for action reasoning only

Every observation carries support edges, reasoning-run provenance, epistemic classification, and validation state.

Use explicit epistemic classes such as:

```text
ObservedFact
SourceAssertion
Interpretation
Inference
Hypothesis
Evaluation
Opinion
Unknown
```

Avoid arbitrary confidence probabilities until they can be empirically calibrated.

Reasoning quality is evaluated against the M−1 golden cases. A system that produces more prose but loses a critical distinction such as `red CI != test failure` or `write access != rerun authority` has regressed.

## M7.5 — Human Review Loop

The review queue is a product capability, not an afterthought.

Possible actions:

```text
ACCEPT
REJECT
LOW_SIGNAL
DUPLICATE
MERGE
PROMOTE
SNOOZE
DEEP_DIVE
CONTRADICT
SUPERSEDE
```

Every action creates a `ReviewDecision` and later becomes evaluation/personalization data.

Queue size must respect the configured attention budget. Overflow is ranked, collapsed, suppressed, or deferred rather than accumulated indefinitely.

## M8 — Pattern Intelligence

Use architecture profiles, observations, and representation neighborhoods to propose candidate groups.

Core objects include:

- `PatternOccurrence`
- `Pattern`
- `Cohort`
- `ArchitecturalTension`

Prevalence claims require defined cohorts and observation windows. Labels such as Rare, Emerging, Growing, Established, and Declining must have measurable denominators.

`ArchitecturalTension` is preferred over simplistic contradiction because different designs may be valid under different assumptions.

Cross-repository infrastructure patterns are legitimate intelligence when supported by multiple positive cases and meaningful counterexamples, as demonstrated by the M−1 private-Actions case.

## M9 — Insight & Knowledge Promotion

Convert supported patterns into reusable engineering knowledge.

Every insight should address:

- mechanism
- problem
- assumptions
- trade-offs
- competing approaches
- observed implementations
- failures/reversals
- generality
- decision relevance

Promotion is an explicit authority boundary. Evidence does not decay, but current applicability and freshness can become stale and require revalidation.

Action recommendations remain separate from knowledge promotion. A promoted insight may have no operational action, or different actions for `OWNED` versus `EXTERNAL` repositories.

**Traceability invariant:**

```text
KnowledgeItem
    ↓
Insight
    ↓
Pattern
    ↓
PatternOccurrences
    ↓
Observations
    ↓
EvidenceFacts
    ↓
Artifacts
    ↓
RepositoryRevision
```

## M10 — Intelligence Interface

Expose intelligence rather than ingestion output.

Core modes:

- Search
- Ask
- Compare
- Changes
- Deep dive
- Review

The weekly technical-intelligence brief is the primary product output and should emphasize high-value deltas, new mechanisms, significant changes, emerging/reversing patterns, architectural tensions, negative intelligence, deep-dive recommendations, stale knowledge requiring revalidation, and high-value action recommendations.

Answers expose evidence, provenance, uncertainty, alternatives, historical state, and action/authority boundaries rather than hiding them behind fluent prose.

---

## Release boundaries

### V0 — Validation

Contains M−1.

**Success:** the reviewed golden corpus contains decision-relevant intelligence, demonstrates belief revision and correct no-action behavior, and includes at least one real external-source case where useful intelligence does not depend on source modification.

### V1 — Evidence Engine

Contains M0, M1, M2, M3, M4, M5-lite, M6-lite, and basic review/feedback capture.

```text
Curated repositories
       ↓
canonical identity + relationship
       ↓
revision capture
       ↓
structured evidence
       ↓
basic structural deltas
       ↓
basic architecture profile
```

No autonomous insight synthesis.

**Success:** can LemmaMind reliably know what changed and prove every extracted fact while preserving the M−1 evidence and action boundaries?

### V2 — Repository Intelligence

Contains full M5, full M6, M6.5, M7, M7.5, and M8-lite.

**Success:** can the system discover meaningful mechanisms shared or contested across repositories without manufacturing unsupported conclusions or unauthorized actions?

### V3 — Personal Technical Intelligence

Contains full M8, M9, and M10.

**Success:** does LemmaMind repeatedly surface ideas that influence real engineering or research decisions?

---

## Expansion track

- **X1 — Research-source integration:** arXiv, OpenReview, official docs, benchmarks, technical blogs, release notes.
- **X2 — Architecture genealogy:** trace ideas from paper to reference implementation to framework to production adaptation.
- **X3 — Novelty & anomaly intelligence:** measure architectural distance from peer clusters.
- **X4 — Personalized ranking:** learn relevance while preserving deliberate exploration.
- **X5 — Dynamic sandboxed analysis:** only when static evidence proves insufficient; disposable, secret-free, non-privileged, network-restricted.
- **X6 — Knowledge graph optimization:** add specialized graph infrastructure only when demonstrated query requirements justify it.

## Explicit “Not Building Yet” policy

Do not build:

- broad GitHub discovery until the curated/watchlist pipeline has acceptable signal-to-noise and review load
- a graph database until relational/query traversal is demonstrably inadequate
- genealogy until enough validated/promoted patterns exist
- a recommendation model until enough meaningful review decisions exist
- external research-source integration until GitHub-derived intelligence has already affected real work
- autonomous promotion until observation/pattern quality is measured and policy precision is acceptable
- autonomous repository repair as a core LemmaMind requirement
- distributed workers until single-node execution becomes a measured bottleneck
- sophisticated numerical confidence until evaluation data supports calibration

## Storage architecture

Use three tiers:

1. **Curated durable knowledge — Git-tracked:** curated knowledge, configuration, human decisions.
2. **Machine state and evidence — backed up:** `lemmamind.db`, objects, capture manifests, indexes, evaluation corpus.
3. **Regenerable projections — disposable:** generated Markdown, cached summaries, search indexes, temporary embeddings, daily render output.

Generated projections are never manually edited. Human-edited artifacts receive a durable curated identity.

## Evaluation

Evaluation starts in M−1 and grows with the platform.

The M−1 golden corpus is the first regression suite for intelligence behavior.

Operational questions:

- Was deterministic evidence extracted correctly?
- Did change intelligence isolate meaningful change without flooding the user?
- Are observations supported, partially supported, unsupported, or contradicted?
- Did the system distinguish source facts from its own interpretation?
- Did the system revise a prior conclusion when newer evidence required it?
- Did it preserve experiment/governance boundaries?
- Did it choose an allowed action or correct no-action disposition?
- Do claimed pattern occurrences really instantiate the pattern?
- Which discoveries are opened and deep-dived?
- Which insights are actually promoted and used?

Ultimate objective:

```text
promoted useful insights
─────────────────────────
human attention + compute cost
```

## Security

External repository content remains untrusted throughout capture and reasoning.

Never execute external code in a workflow containing repository-write credentials, cloud credentials, personal secrets, or knowledge-writing authority.

Separate source-reading authority from knowledge-writing authority.

Promotion improves epistemic status; it does not make upstream bytes security-trusted.

## Cost and scale contract

Before every major release estimate:

- repositories per tracking level
- snapshots per month
- artifacts per snapshot
- API requests/day
- storage/month
- embedding operations/month
- LLM tokens/month
- estimated cost/month
- human review minutes/week

Architecture choices should respond to measured scale rather than hypothetical future scale.

## Final execution order

```text
1. Freeze and review the M−1 golden corpus.
2. Add one real external-source case and explicitly judge M−1 PASS/FAIL.
3. Implement M0 contracts only as needed by real pilot data.
4. Build M1–M4 as the reproducible evidence spine.
5. Add M5–M6 and prove useful change detection against golden cases.
6. Reassess product value.
7. Add M6.5 representation.
8. Introduce M7 reasoning with strict provenance and golden-case regression.
9. Build the human review loop before increasing generation volume.
10. Add M8 only after enough observations exist.
11. Promote M9 knowledge only after patterns survive review.
12. Build M10 around demonstrated workflows.
13. Unlock expansion capabilities only when their trigger conditions are met.
```

LemmaMind succeeds not when every milestone is implemented, but when the smallest necessary subset consistently produces **decision-relevant, evidence-backed technical intelligence**.
