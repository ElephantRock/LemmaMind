# M5-lite Deterministic Delta Checkpoint v1

## Result

**Status: PASS for the V1 M5-lite factual delta slice.**

This checkpoint validates the deterministic boundary:

```text
CaptureManifest pair
      ↓
ArtifactDelta
      ↓
exactly bound compatible EvidenceFact generations
      ↓
StructuralDelta
```

It does not validate `ChangeInterpretation` or full M5 semantic change intelligence.

## Contract under test

M5-lite must preserve these distinctions:

1. a different requested capture scope is not automatically a repository add/remove;
2. the same requested path changing `MISSING ↔ CAPTURED` is a factual availability transition;
3. unequal retained bytes are an `ArtifactDelta` even if current normalized structure is unchanged;
4. `StructuralDelta` compares only normalized `EvidenceFact` generations whose persisted run inputs match the exact CaptureManifest and ordered extractor profile and whose code/schema/policy generations match;
5. a valid zero-evidence extraction generation remains bindable through its persisted input hash;
6. authored `SourceAssertion` changes are not silently promoted to structural facts;
7. deterministic evidence drift without artifact-state change is a failure, not a source delta.

## Deterministic regression coverage

The permanent test suite exercises:

- `capture_scope_added` / `capture_scope_removed`;
- `became_captured` / `became_missing`;
- `content_changed`;
- normalized structural `added`, `removed`, and `modified` changes;
- real `DeterministicExtractionService` generations over `package.json`;
- exact extraction-run/CaptureManifest/extractor-profile input-hash verification;
- valid all-missing zero-evidence generation followed by `became_captured` and structural additions;
- wrong extractor-profile rejection;
- byte-different formatting with unchanged normalized package facts;
- capture-scope-only evidence suppression from StructuralDelta;
- extraction code/schema/policy generation mismatch rejection;
- deterministic fact drift with unchanged artifact state rejection;
- cross-Source rejection;
- SourceRevision temporal reversal rejection;
- CaptureManifest temporal reversal rejection for repeated same-revision captures;
- generic append-only persistence registry reconstruction for M5 contracts.

The first permanent implementation run was:

```text
run: 32918939216
head: 829cde3769c70b6327cdc3872cf36d6d1e9006f8
pytest: 182 passed in 2.45s
conclusion: success
```

The stricter extractor-profile implementation was then exercised by the live probe below at **184 passed** before the exact-revision comparison.

## Live exact-revision probe

Temporary read-only workflow:

```text
run: 32919752478
workflow: m5-live-probe
head: 472d6c8b53a80b736c7dcf3a719367b184a0056a
conclusion: success
permissions: contents=read, metadata=read
```

The workflow was branch-only and removed after the probe.

Repository:

```text
ElephantRock/LemmaMind
```

Previous revision:

```text
055d67f1ae0ebd5174114d8982bcef92609e5733
```

Current revision:

```text
c83c95488c85c2130b198b08161b9fa6fcd5209f
```

Both captures requested exactly:

```text
README.md
src/lemmamind/evidence_inspection.py
```

The exact ordered extractor profile verified against both persisted extraction-run input hashes was:

```text
artifact-path@1
pyproject@1
package-json@1
markdown-prose@1
markdown-list@1
python-ast@1
typescript-ast@1
```

### Retrieval states

Previous:

```text
README.md                              captured
src/lemmamind/evidence_inspection.py missing
```

Current:

```text
README.md                              captured
src/lemmamind/evidence_inspection.py captured
```

### ArtifactDelta result

```text
README.md                              content_changed
src/lemmamind/evidence_inspection.py became_captured
```

The second result is specifically **not** `capture_scope_added`: the path was requested in both manifests and was absent at the previous immutable revision.

### StructuralDelta result

```text
previous EvidenceFact count: 4
current EvidenceFact count: 241
StructuralDelta count: 237
StructuralDelta type: added
StructuralDelta source locator:
  src/lemmamind/evidence_inspection.py
```

Every structural delta in the live probe was an added deterministic fact for the newly available M4 implementation file.

README changed at the byte layer but generated no StructuralDelta in this probe because the current changed README material was authored prose / `SourceAssertion` evidence rather than changed deterministic facts.

That result must **not** be read as “README change is unimportant.” It demonstrates the factual/epistemic boundary only.

The live workflow ran the repository suite first:

```text
184 passed in 9.63s
```

and then completed the exact-revision probe successfully.

## Churn boundary demonstrated

A deterministic test also rewrites the same `package.json` document with different whitespace.

Result:

```text
ArtifactDelta: content_changed
StructuralDelta: none
```

This proves only that current normalized package facts can stay stable across formatting-byte churn. It is not a generic formatting classifier and does not imply that AST/source-coordinate extractors will suppress all formatting edits.

## Deferred claims

This checkpoint does not establish:

- semantic significance;
- architecture impact;
- generated/vendored/lockfile noise classification;
- adoption/reversal/deprecation/removal/failure/cancellation classification;
- project-state reconciliation across issue/PR/commit/CI/experiment evidence;
- causal diagnosis;
- model-generated change summaries;
- autonomous review prioritization.

Those remain outside V1 M5-lite.

## Exit decision

M5-lite is eligible to close once the final code/docs branch head passes the permanent PR workflow unchanged.

The next roadmap slice is M6-lite Profiling & Triage reconciliation.
