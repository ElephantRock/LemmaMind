# M6-lite Profiling & Triage Checkpoint v1

## Result

**Status: PASS for the V1 M6-lite deterministic profiling/triage slice, pending final unchanged-head PR CI and merge.**

This checkpoint validates:

```text
revision-bound deterministic evidence
        ↓
ArchitectureProfile
        ↓
M2 tracking + explicit triage context + M5 StructuralDelta
        ↓
TriageAssessment
```

It does not validate embeddings, learned relevance, semantic architecture interpretation, or full M6.

## Deterministic contract

ArchitectureProfile must:

1. bind to exactly one SourceRevision;
2. reference explicit completed extraction PipelineRuns;
3. retain exact fact/assertion/artifact IDs;
4. retain extractor family and `name@version` identity;
5. expose only deterministic feature-presence keys;
6. reject evidence resolving to another revision;
7. permit an empty profile for a valid empty extraction generation.

TriageAssessment must:

1. consume the latest-effective M2 tracking policy;
2. retain explicit caller-supplied domain and sensitivity inputs;
3. retain exact M5 StructuralDelta IDs;
4. verify each StructuralDelta through ArtifactDelta and its complete DIFF run;
5. use rule precedence, not numeric weights;
6. preserve all contributing reason codes;
7. fail closed to `ignore` for an unassigned Source.

## Integration failure that changed the implementation

First PR workflow:

```text
run: 32949026813
head: a355f9b5628c900a49a6035185c89ed12739f21c
result: 189 passed, 5 failed
```

All failures were append-only `PipelineRun` ID conflicts. `ArchitectureProfilingService` and `DeterministicTriageService` both generated `run:<id>`; resetting the deterministic test ID factory caused a real identity collision.

The fix namespaced durable run IDs:

```text
run:profiling:<id>
run:triage:<id>
```

No triage threshold or provenance check was weakened.

Corrected permanent PR workflow:

```text
run: 32949167132
head: 0f769dabaa68b4d9313b8270987aaf695c0ef4a1
pytest: 194 passed in 3.01s
conclusion: success
```

## Live immutable-revision checkpoint

Temporary branch-only read-only workflow:

```text
run: 32949263303
head: 14a2da7cc9f88ae2a74ac0e4af0cfa7a264eab99
permissions: contents=read, metadata=read
pytest: 194 passed in 2.83s
conclusion: success
```

Repository:

```text
ElephantRock/LemmaMind
```

Immutable revisions:

```text
previous M4:
c83c95488c85c2130b198b08161b9fa6fcd5209f

current M5:
4fa67cfa6c3fafa235d0d2c74215cff2b2988b9c
```

Requested identically at both revisions:

```text
README.md
pyproject.toml
src/lemmamind/change_intelligence.py
```

Current ArchitectureProfile:

```text
artifact_count:          3
evidence_fact_count:    209
source_assertion_count: 122
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

Feature-presence keys included:

```text
language:python
manifest:python-project
media:application/toml
media:text/markdown
media:text/x-python
```

M5 comparison produced:

```text
StructuralDelta count: 193
```

Every supplied triage StructuralDelta terminates at the current profile revision and retains its M5 factual provenance.

## Triage probe

The live workflow created an ephemeral local-only M2 tracking assignment inside its temporary SQLite database:

```text
tracking level: 4 (Deep)
assigned_by: m6-live-probe
reason: ephemeral live triage validation
```

This did not mutate repository state, production tracking state, or governance authority.

Explicit triage inputs:

```text
domain_match: true
sensitivity: governance
recent structural change: 193 M5 StructuralDelta IDs
```

Result:

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

The result establishes that deterministic policy routing is reproducible when all `deep_dive` prerequisites are supplied. It does not assert that these manual inputs should be assigned in production.

## Important semantic boundary

The roadmap refers to "meaningful recent change" as a future triage signal. M5-lite does not yet classify meaningfulness.

This checkpoint therefore uses only:

> **recent factual structural change**

represented by supplied `StructuralDelta` records.

No semantic-significance claim is made.

Similarly:

- extractor presence is not architecture interpretation;
- evidence richness is a V1 operational heuristic, not confidence;
- process/workflow richness means captured evidence-surface presence, not health/failure/importance;
- domain match and sensitivity are explicit caller inputs, not inferred facts.

## Exit decision

M6-lite is eligible to close after:

1. the temporary live workflow is removed;
2. code/docs/report/README reach a final branch head;
3. the ordinary permanent PR workflow passes that unchanged head;
4. the exact head is squash-merged under an expected-head guard.

After M6-lite, the roadmap says to evaluate the **V1 Evidence Engine release gate** before M6.5 representation. V1 also requires basic review/feedback capture; that capability must be audited explicitly rather than assumed from the existence of a `ReviewDecision` contract.
