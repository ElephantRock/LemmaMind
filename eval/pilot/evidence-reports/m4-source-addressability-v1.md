# M4 deterministic evidence source-addressability checkpoint

## Scope

This checkpoint records the M4 reconciliation of LemmaMind's already-existing deterministic evidence surface against the roadmap gate:

> Any fact can be inspected at its exact source location without trusting generated prose.

Base `main` before the M4 branch:

```text
055d67f1ae0ebd5174114d8982bcef92609e5733
```

Branch:

```text
m4/deterministic-evidence-reconciliation
```

PR:

```text
#24 — Reconcile M4 deterministic evidence inspection
```

## Reconciliation result

M4 did not introduce another extractor framework. It added an executable inspection layer over the current deterministic evidence records and the M3 local reconstruction boundary.

The inspection chain is:

```text
EvidenceFact / SourceAssertion
        ↓
producing EXTRACTION PipelineRun
        ↓
Artifact
        ↓
CaptureManifest + SourceRevision
        ↓
M3 local reconstruction
        ↓
retained content-addressed bytes / immutable artifact metadata
        ↓
resolved exact location or deterministic derivation substrate
```

No provider fallback is permitted.

## Locator families covered

The M4 tests exercise:

- Markdown/source line ranges;
- Python and TypeScript byte-column ranges;
- TOML key paths;
- JSON and scalar-root JSON Pointer locations;
- artifact path and manifest-kind metadata derivations;
- Git-tree stable entry-path keys resolved to canonical array indexes;
- Git commit direct fields and deterministic parent-count substrate;
- GitHub repository-metadata resource-relative locations;
- issue-event direct fields and event-count substrate;
- workflow provider job IDs, artifact IDs, and step numbers resolved to canonical array indexes;
- fail-closed unanchored/unresolvable locator behavior.

The real extractor integration regression captures Markdown, `pyproject.toml`, `package.json`, Python, and TypeScript artifacts, runs the current `DeterministicExtractionService` with the TypeScript-aware extractor stack, and requires `EvidenceInspectionService.audit_all()` to resolve every emitted `EvidenceFact` and `SourceAssertion`.

## CI progression

First permanent PR run after the inspection implementation:

```text
run: 32916123573
head: 3f1c24b5672b9e4b28363daf2a13cf415bcf2925
result: success
pytest: 172 passed in 2.26s
```

After adding the scalar JSON-root edge case and the real extractor-surface audit:

```text
run: 32916244385
head: b52c7f193330f5e62c71dab36fa70684c2d5ac8c
result: success
pytest: 174 passed in 2.48s
```

The authoritative final exact-head CI run is added to the PR description before merge; Git history and the PR retain the immutable run/head association.

## Epistemic boundary

Source-addressability does not change epistemic class.

- parser/provider structure remains `EvidenceFact`;
- source-authored prose remains `SourceAssertion`;
- deterministic aggregates identify their exact retained container substrate rather than pretending to be literal source leaves;
- no M4 inspection result is an `Observation`, interpretation, causal diagnosis, or importance judgment.

## Exit decision

Subject to final exact-head permanent CI on the code + documentation state, the current V1 M4 deterministic-evidence gate is satisfied.

The next V1 reconciliation target is M5-lite: deterministic `ArtifactDelta` / `StructuralDelta` over historical reconstructable inputs, without treating a changed structure as an inferred `ChangeInterpretation`.
