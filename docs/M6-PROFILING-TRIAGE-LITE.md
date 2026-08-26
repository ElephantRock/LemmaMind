# LemmaMind M6-lite — Deterministic Profiling & Triage

## Objective

M6-lite closes the V1 profiling/triage boundary without introducing embeddings, learned ranking, or model-generated architecture claims.

The executable path is:

```text
revision-bound deterministic evidence
        ↓
ArchitectureProfile
        ↓
M2 tracking policy
+ explicit domain match
+ explicit governance/experiment sensitivity
+ factual M5 StructuralDelta
        ↓
TriageAssessment
```

The governing rule is:

> **A profile records which deterministic evidence features are present at one exact revision. Triage routes attention using explicit policy inputs and factual change provenance. Neither step decides what the architecture means.**

## Roadmap alignment

The formal M6 roadmap asks for:

- immutable, revision-bound `ArchitectureProfile` objects;
- profile schema and extractor versions;
- simple deterministic triage using manual tracking level, domain match, evidence richness, recent change, source/process richness, and governance/experiment sensitivity;
- no sophisticated numerical weighting before review data exists.

M6-lite implements that boundary conservatively.

One wording is intentionally narrower than the roadmap prose: this V1 slice uses **recent factual structural change**, represented by M5 `StructuralDelta`, rather than claiming a **meaningful recent change** classifier. Semantic significance remains outside M5-lite/M6-lite.

## Durable contracts

### `ArchitectureProfile`

One immutable profile is bound to exactly one canonical `Source` and one `SourceRevision`.

It records exact provenance:

- profile schema version;
- producing `PipelineRun(run_type=profiling)`;
- explicit evidence extraction run IDs;
- exact Artifact IDs;
- exact EvidenceFact IDs;
- exact SourceAssertion IDs;
- fact/assertion/artifact counts;
- extractor families;
- extractor profiles as `name@version`;
- artifact media types;
- deterministic feature-presence keys.

An ArchitectureProfile does not contain a prose architecture summary, inferred component graph, inferred mechanism description, or model confidence score.

### `TriageAssessment`

One immutable assessment records:

- ArchitectureProfile identity;
- Source and SourceRevision;
- producing profiling run;
- triage policy version;
- effective M2 tracking level and assignment ID, if any;
- explicit caller-supplied domain match;
- explicit governance / experiment sensitivity flags;
- exact supporting M5 StructuralDelta IDs;
- deterministic triage band;
- complete reason-code set.

Triage is attention-routing metadata. It does not alter validation state, repository relationship, knowledge status, or action authority.

## Profile evidence boundary

Callers explicitly supply one or more completed extraction PipelineRun IDs.

Every supplied run must be:

- present;
- `run_type=extraction`;
- complete (`finished_at` and `outputs_hash` present).

Every EvidenceFact and SourceAssertion from those runs is traced through:

```text
EvidenceFact / SourceAssertion
        ↓
Artifact
        ↓
CaptureManifest
        ↓
exact SourceRevision
```

Evidence from any other revision is rejected.

The Artifact must also agree with its CaptureManifest on Artifact ID, source locator, content hash, and media type.

An extraction generation may be complete yet contain zero facts/assertions. M6-lite permits an empty ArchitectureProfile in that case. The empty profile is a truthful deterministic state, not fabricated architecture information.

## Feature-presence policy

Feature keys are deterministic presence indicators over already-established evidence families. Current examples include:

```text
language:python
language:typescript
manifest:python-project
manifest:node-package
surface:workflow
surface:process-current
surface:process-history
surface:repository-metadata
surface:git-tree
surface:git-commit
extractor:<name>
media:<media-type>
```

Feature presence means only that the corresponding deterministic evidence family is present in the supplied revision-bound generation.

For example:

```text
language:python
```

means Python AST evidence was extracted. It does **not** mean Python is the repository's dominant language, runtime architecture, or implementation strategy.

README prose and other SourceAssertions do not become architecture claims merely because they are present in the profile provenance.

## Extractor-version provenance

M6 requires profile schema and extractor versions to remain explicit.

ArchitectureProfile therefore records both:

```text
extractor_families
extractor_profiles = name@version
```

Versions are provenance, not weights. A future extractor revision can therefore produce a distinct inspectable profile generation without pretending the feature ontology stayed identical.

## Triage policy

M6-lite deliberately uses rule precedence, not a numerical score.

Current bands are:

```text
ignore
watch
review
deep_dive
```

Current precedence:

1. effective tracking level `0` → `ignore`;
2. domain match + tracking level `4/5` + at least one supplied StructuralDelta + at least one governance/experiment sensitivity flag → `deep_dive`;
3. domain match + any of recent structural change, sensitivity, process richness, workflow richness, or evidence richness → `review`;
4. otherwise → `watch`.

Every contributing condition is preserved as a reason code.

### V1 evidence-rich heuristic

For this slice:

```text
evidence_rich =
  evidence_fact_count > 0
  AND at least two extractor families are present
```

This is an operational heuristic, not a learned measure of repository quality or epistemic confidence.

### Process/workflow richness

These are feature-presence signals:

```text
surface:process-current
surface:process-history
surface:workflow
```

They indicate richer captured evidence surfaces, not that a process/workflow state is healthy, failing, important, or causally explanatory.

### Domain and sensitivity inputs

`domain_match` and governance/experiment sensitivity are explicit caller inputs. M6-lite does not infer them from README prose or source code.

They are persisted on TriageAssessment and included in the producing run's inputs hash so the routing decision is reproducible.

This slice does not yet add authenticated/manual-signal author identity as a separate durable contract. If later feedback workflows require governed authorship/correction semantics, that should be introduced explicitly rather than inferred from the triage result.

## M5 provenance boundary

A supplied recent-change signal must be an existing M5 `StructuralDelta` that:

- belongs to the same Source as the profile;
- terminates at the profile's exact SourceRevision;
- references an existing ArtifactDelta;
- agrees with that ArtifactDelta on Source, current revision, and DIFF run;
- is produced by a complete `PipelineRun(run_type=diff)`.

Thus the chain remains:

```text
TriageAssessment
      ↓
StructuralDelta
      ↓
ArtifactDelta
      ↓
DIFF PipelineRun
      ↓
revision-bound deterministic evidence
```

A StructuralDelta is factual structural change. Its presence does **not** establish semantic significance.

## Tracking boundary

Triage consumes the existing M2 latest-effective tracking policy at assessment time.

Tracking controls operational attention eligibility only. It does not change profile truth or evidence truth.

An unassigned Source resolves operationally to level `0`, so M6-lite routes it to `ignore` without fabricating a tracking assignment.

## Pipeline provenance

Both profile construction and triage use `RunType.PROFILING`, but their run IDs are namespaced:

```text
run:profiling:<id>
run:triage:<id>
```

This naming correction was introduced after the first integration CI run exposed an append-only `PipelineRun` identity collision when deterministic test ID factories were reused across the two services.

## Validation history

### First integration run — informative failure

PR workflow:

```text
run: 32949026813
head: a355f9b5628c900a49a6035185c89ed12739f21c
result: 189 passed, 5 failed
```

All five failures were `RecordConflict` on `PipelineRun:run:m6-1`. The profile and triage services had generated the same un-namespaced run ID under reset deterministic test factories.

The fix was to namespace the two PipelineRun identities. No triage rule was weakened.

### Corrected permanent CI

PR workflow:

```text
run: 32949167132
head: 0f769dabaa68b4d9313b8270987aaf695c0ef4a1
pytest: 194 passed
conclusion: success
```

### Live immutable-revision probe

Temporary read-only workflow:

```text
run: 32949263303
head: 14a2da7cc9f88ae2a74ac0e4af0cfa7a264eab99
permissions: contents=read, metadata=read
pytest: 194 passed
conclusion: success
```

The probe compared immutable LemmaMind revisions:

```text
previous M4:
c83c95488c85c2130b198b08161b9fa6fcd5209f

current M5:
4fa67cfa6c3fafa235d0d2c74215cff2b2988b9c
```

Using the same requested paths:

```text
README.md
pyproject.toml
src/lemmamind/change_intelligence.py
```

Current revision profile:

```text
Artifacts:        3
EvidenceFacts:    209
SourceAssertions: 122
```

Extractor profiles:

```text
artifact-path@1
markdown-list@1
markdown-prose@1
pyproject@1
python-ast@1
python-docstring@1
```

Selected feature keys included:

```text
language:python
manifest:python-project
media:application/toml
media:text/markdown
media:text/x-python
```

M5 produced **193 StructuralDelta records** terminating at the current revision.

The probe then created an **ephemeral tracking assignment inside the temporary SQLite database only**:

```text
level: 4 (Deep)
assigned_by: m6-live-probe
reason: ephemeral live triage validation
```

No production GitHub or LemmaMind governance/tracking state was changed.

With explicit:

```text
domain_match = true
governance sensitivity = true
193 factual StructuralDelta IDs
```

M6-lite produced:

```text
band: deep_dive
reasons:
  deep_tracking
  domain_match
  evidence_rich
  governance_sensitive
  recent_structural_change
  tracking_active
```

This validates deterministic routing under a fully satisfied synthetic policy context. It is not a claim that the M5 implementation itself deserves a real-world deep dive.

The temporary workflow is removed before final PR closeout.

## M6-lite closeout boundary

For V1, this slice is complete when permanent CI proves:

- immutable revision-bound ArchitectureProfile persistence;
- exact extractor-family and extractor-version provenance;
- exact evidence/artifact provenance;
- deterministic feature-presence extraction without architecture interpretation;
- deterministic triage bands and reason codes;
- M2 tracking consumption;
- M5 StructuralDelta/ArtifactDelta provenance checks;
- no numeric weighting or learned ranker;
- unassigned Sources fail closed to ignore;
- existing M0–M5 and golden regressions remain green.

Still deferred are:

- semantic ArchitectureProfile fields inferred by a model;
- `ChangeInterpretation` / meaningful-change classification;
- learned or weighted relevance ranking;
- embeddings / M6.5 representation;
- nearest-neighbor search;
- autonomous mechanism classification;
- human-attention queue UI;
- automatic tracking changes;
- autonomous reasoning volume increases.

## Release boundary after M6-lite

The roadmap defines V1 — Evidence Engine as:

```text
M0 + M1 + M2 + M3 + M4 + M5-lite + M6-lite + basic review/feedback capture
```

M6.5 belongs to V2.

Therefore the next justified step after this slice is **V1 release-gate reconciliation**, including verification that basic review/feedback capture is sufficient and that the V1 success criterion is actually demonstrated. Do not proceed directly into embeddings merely because M6-lite exists.
