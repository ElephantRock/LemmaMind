# LemmaMind M4 — Deterministic Evidence Reconciliation

## Objective

M4 closes the deterministic-evidence source-addressability gate without replacing the extractor stack that was already built and validated during M0 and the pilot vertical slices.

The roadmap gate is:

> **Any deterministic fact can be inspected at its exact source location without trusting generated prose.**

The executable path is now:

```text
SourceRevision
      ↓
CaptureManifest
      ↓
Artifact + content-addressed bytes
      ↓
deterministic extractor
      ↓
EvidenceFact / SourceAssertion
      ↓
EvidenceInspectionService
      ↓
exact retained source span / structured value / derivation substrate
```

M4 does not add interpretation. It makes deterministic evidence inspectable.

## Reused evidence surface

The current deterministic surface already includes:

- artifact-path facts;
- selected `pyproject.toml` and `package.json` structure;
- Markdown prose and list assertions;
- exact Git root-tree structure;
- Git commit metadata and authored commit messages;
- Python AST facts and docstrings;
- TypeScript/TSX syntax facts and authored comments;
- opt-in JSON scalar facts addressed by JSON Pointer;
- GitHub repository metadata;
- current issue/pull-request snapshots;
- issue event history;
- GitHub Actions run/job/step/artifact metadata.

The external golden coverage for this deterministic repository evidence surface was already 12/12 before M4 reconciliation. M4 therefore focuses on the missing executable inspection contract rather than adding speculative extractors.

## `EvidenceInspectionService`

`src/lemmamind/evidence_inspection.py` provides three entry points:

```text
inspect_fact(evidence_id)
inspect_assertion(assertion_id)
audit_all()
```

For one record the service verifies:

1. the producing `PipelineRun` exists and is `run_type=extraction`;
2. the referenced `Artifact` exists;
3. M3 can reconstruct the artifact's `CaptureManifest` and `SourceRevision` entirely from local durable state;
4. the retained content-addressed bytes are available and digest-valid;
5. the evidence locator is anchored to `Artifact.source_locator`;
6. the locator resolves deterministically against the retained source or against an explicitly identified immutable derivation substrate.

There is no provider fallback. A locator that only works by refetching GitHub does not satisfy M4.

`audit_all()` applies the same contract to every persisted `EvidenceFact` and `SourceAssertion` and fails closed on the first unresolvable record.

## Inspection result

`EvidenceInspection` preserves both the evidence record's own value and the material against which it can be inspected:

- `requested_locator` — locator originally emitted by the extractor;
- `resolved_locator` — concrete retained-source address after semantic locator resolution;
- `location_kind` — what kind of source address was resolved;
- `evidence_value` — `EvidenceFact.raw_value` or `SourceAssertion.statement`;
- `source_value` — exact structured value/container or immutable metadata substrate when applicable;
- `source_text` — exact retained text span for line/range locators.

This separation is deliberate. A derived fact such as `entry_count=4` is not falsely presented as a literal JSON leaf. Its inspection resolves to the exact retained `entries` container from which the count was deterministically computed.

## Locator families

### Text line ranges

Markdown prose, Markdown lists, Python docstrings, and TypeScript comments use line-range locators such as:

```text
README.md:L14-L14
sample.py:L1-L1
```

Inspection returns the exact retained UTF-8 lines.

### AST byte-coordinate ranges

Python and TypeScript syntax records use source ranges such as:

```text
sample.py:L3:C4-L3:C12#python/call
sample.ts:L2:C0-L2:C44#typescript/function
```

The columns are treated as byte offsets, matching Python AST/tree-sitter source-coordinate semantics rather than assuming Unicode character indexes. The returned text is sliced from retained bytes before UTF-8 decoding.

### TOML keys

Selected `pyproject.toml` facts use dotted key locators, for example:

```text
pyproject.toml#project.name
pyproject.toml#project.requires-python
```

Inspection reparses the retained TOML and resolves the exact structured value.

### JSON Pointer and JSON resource fields

Ordinary JSON evidence resolves against retained JSON, including the RFC 6901 scalar-root case:

```text
value.json#
package.json#/name
```

Provider snapshots also use resource-root locators. For example repository metadata emits:

```text
$github/repository#/visibility
```

while the canonical retained snapshot stores the provider field under:

```text
$github/repository#/repository/visibility
```

Inspection records the requested semantic locator and the concrete canonical pointer separately.

### Stable semantic keys over canonical arrays

Some evidence intentionally addresses stable provider/source identities rather than brittle array positions.

Git root-tree facts use entry paths:

```text
$git/tree/root#/entries/src/type
```

The retained canonical JSON stores `entries` as an array. Inspection finds the entry whose `path == "src"` and returns the concrete pointer, for example:

```text
$git/tree/root#/entries/1/type
```

Workflow facts use provider job IDs, artifact IDs, and step numbers:

```text
$github/actions/run/77#/jobs/9001/name
$github/actions/run/77#/jobs/9001/steps/2/conclusion
$github/actions/run/77#/artifacts/501/name
```

Inspection resolves those stable keys to the corresponding canonical array indexes. The evidence locator remains stable even if canonical ordering changes; the resolved locator explains where that value lives in the retained snapshot.

### Immutable artifact metadata

Artifact-path facts such as:

```text
README.md#$path.basename
README.md#$path.suffix
README.md#$path.path_depth
```

and manifest-kind facts are deterministic derivations of immutable `Artifact.source_locator`, not claims about a byte range inside the file. Inspection therefore reports `location_kind=artifact_metadata` and resolves to the exact Artifact metadata field rather than inventing source bytes.

### Deterministic aggregate structure

Current aggregate examples include:

- Git tree `entry_count` / `entry_paths`;
- Git commit `parent_count`;
- issue-history `event_count`.

These facts resolve to the exact retained container (`entries`, `parents`, or `events`) and are marked `location_kind=derived_structure`.

The inspection contract does not imply that `evidence_value == source_value` for a deterministic transformation. It requires the transformation to point to an exact, locally retained substrate.

## Epistemic boundary

M4 preserves the existing distinction:

```text
machine-readable source structure
        ↓
EvidenceFact

source-authored prose
        ↓
SourceAssertion
```

Inspection does not promote a `SourceAssertion` to a fact and does not infer architecture, causality, importance, correctness, or intent from syntax.

For example:

```text
SourceAssertion: "Sandboxing is off by default"
```

remains an assertion made by the source even when the exact line is locally inspectable.

## Failure semantics

Inspection fails closed when:

- a producing extraction run is missing or has the wrong run type;
- an Artifact is missing;
- M3 reconstruction cannot close the manifest/artifact/object set;
- retained bytes are missing or corrupt;
- a locator is not anchored to the evidence Artifact;
- a line/column range is invalid;
- a TOML/JSON path does not resolve;
- a semantic Git-tree/workflow key is absent;
- an unsupported locator/media-type combination is encountered.

The service never silently falls back to a broader source region, a current provider state, generated prose, or heuristic string search.

## Validation

The M4 regression suite covers representative locator families and an end-to-end extractor audit.

The integration test constructs one real multi-artifact capture containing Markdown, `pyproject.toml`, `package.json`, Python, and TypeScript, runs the actual `DeterministicExtractionService` with the current TypeScript-aware extractor stack, then requires `EvidenceInspectionService.audit_all()` to resolve every emitted fact and assertion.

The branch also directly tests:

- multibyte UTF-8 byte-coordinate slicing;
- scalar JSON-root pointers;
- Git-tree path keys;
- workflow provider IDs and step numbers;
- repository-metadata relative resource locators;
- deterministic aggregate substrates;
- fail-closed unanchored locators.

Permanent PR run `32916123573` reached **172 passed** on the first inspection implementation. After adding the JSON-root edge case and real extractor-surface audit, run `32916244385` reached **174 passed**.

The final exact-head merge run is preserved in PR #24 and GitHub Actions history so the tested head/run association remains immutable without making the tracked checkpoint self-referential.

## M4 closeout boundary

For the current V1 deterministic evidence surface, M4 is complete when the final exact branch head passes permanent CI with:

- local reconstruction required for inspection;
- representative locator-family tests green;
- the actual default/Python/TypeScript source-file extractor stack fully inspectable under `audit_all()`;
- existing golden and external deterministic evidence regressions unchanged.

This does **not** claim:

- every possible programming language is parsed;
- every GitHub surface has an extractor;
- lockfiles are fully resolved;
- release/config formats beyond demonstrated requirements are covered;
- syntax implies behavior;
- semantic change has been classified;
- model output is evidence.

New deterministic extractors remain additive when future V1/V2 cases demonstrate a need.

## Next roadmap move

After M4 closes, the next V1 gap is **M5-lite Change Intelligence reconciliation**. The appropriate first slice is deterministic delta structure over reconstructable revision/capture evidence—`ArtifactDelta` followed by `StructuralDelta`—while keeping inferred `ChangeInterpretation`, significance judgments, and sophisticated churn suppression behind explicit later boundaries.
