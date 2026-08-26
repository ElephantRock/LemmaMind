# LemmaMind M3 — Revision Capture Reconciliation

## Objective

M3 separates immutable upstream Git state from the exact local inputs used for analysis:

```text
Source
  ↓
SourceRevision
(exact commit SHA + root tree SHA)
  ↓
CaptureManifest
(exact capture policy + input set)
  ↓
Artifact
(exact locator + media type + content hash)
  ↓
content-addressed object bytes
```

The roadmap gate is:

> **Historical analysis inputs can be reconstructed locally.**

M3 also requires a cheap materiality gate so every changed HEAD does not automatically trigger expensive downstream analysis.

## Reconciliation result

Most of M3 already existed because the M0 evidence spine implemented it before the roadmap milestone was formally closed.

| M3 requirement | Existing implementation | M3 reconciliation |
| --- | --- | --- |
| exact upstream revision | `SourceRevision.commit_sha` + `tree_sha` | retained unchanged |
| exact retained analysis inputs | `CaptureManifest` | retained unchanged |
| immutable artifact identity | `Artifact` | retained unchanged |
| local content-addressed bytes | `ContentAddressedFileStore` | retained unchanged |
| shallow API capture | `GitHubCaptureService` | retained unchanged |
| Git object evidence | root-tree + commit capture services | retained unchanged |
| historical local reconstruction | implicit only | **added explicitly** |
| cheap revision materiality | absent | **added explicitly** |

No second capture stack was introduced.

## Local reconstruction

`CaptureReconstructionService` reconstructs one historical capture using only durable local state. It performs no GitHub/provider read.

For every manifest entry it verifies:

1. the referenced `SourceRevision` exists;
2. artifact IDs and source locators are unique inside the manifest;
3. a `captured` ref has exactly one matching `Artifact` row;
4. the Artifact agrees with the manifest on capture ID, locator, content hash, and media type;
5. the content-addressed object exists and hashes to the persisted digest;
6. a `missing` ref has no contradictory Artifact row or content metadata;
7. no extra Artifact row exists for the capture outside the manifest.

Only after the closed set is verified are bytes returned.

This makes the manifest an executable reconstruction contract rather than documentation about what was once fetched.

### Retrieval-status boundary

M3 V1 can reconstruct:

- `captured` — exact retained bytes are returned;
- `missing` — exact historical absence at the capture boundary is preserved with no bytes.

`error` and `not_modified` are rejected as non-reconstructable in V1 because the current contract does not provide enough information to identify exact retained bytes for those states.

Failing closed here is deliberate. A later contract may add explicit prior-object linkage for `not_modified`, but M3 does not infer such linkage.

## Materiality gate

`RevisionMaterialityGate` compares two immutable `SourceRevision` records for the same Source:

```text
same commit SHA
    → material = false
    → reason = same_revision

different commit SHA + same root tree SHA
    → material = false
    → reason = tree_unchanged

different root tree SHA
    → material = true
    → reason = tree_changed
```

`material=true` means only:

> repository tree content changed, so later analysis is eligible.

It does **not** mean the change is important, meaningful, architectural, or decision-relevant. Those judgments belong to M5 Change Intelligence and later reasoning layers.

A commit-only change with the same root tree remains valid commit/process evidence, but it does not justify re-running expensive repository-content analysis solely because HEAD changed.

## Why the materiality result is not persisted as a new contract

The M3 result is a deterministic projection over immutable `SourceRevision` records. It can be recomputed exactly and carries no human/model judgment.

Persisting a second durable materiality object would add schema surface without adding information. If later scheduling requires durable skip/execution decisions, those decisions should be captured as scheduler/pipeline provenance rather than converting this pure comparison into epistemic evidence.

## End-to-end proof

The M3 tests include a composition test that:

1. captures explicit repository files through the existing `GitHubCaptureService`;
2. records one missing path;
3. retains bytes in the content-addressed object store;
4. records the provider-read count at the end of capture;
5. reconstructs the capture through `CaptureReconstructionService`;
6. verifies exact bytes and the missing entry;
7. verifies reconstruction caused **zero additional provider reads**.

This is the executable proof for the roadmap gate.

## Failure semantics

Reconstruction fails loudly on:

- unknown manifest;
- missing revision;
- missing captured Artifact;
- manifest/Artifact metadata disagreement;
- unmanifested Artifact rows for the same capture;
- missing or corrupt local object bytes;
- duplicate artifact IDs or source locators;
- non-reconstructable retrieval statuses.

There is no remote fallback. A historical reconstruction that silently refetches current/upstream state would violate the gate.

## Trust boundary

Historical reconstruction reads inert local bytes only. It does not:

- execute repository content;
- follow source-controlled filesystem paths;
- contact GitHub;
- resolve mutable branches;
- update repository state;
- generate evidence or interpretation.

Downstream deterministic extractors continue to consume these bytes under their own parser/version contracts.

## Deliberate M3 limits

This reconciliation does not add:

- a local Git clone transport;
- recursive whole-repository capture;
- LFS/submodule materialization;
- scheduler cadence or polling budget;
- semantic change classification;
- low-value-churn suppression;
- `ArtifactDelta` / `StructuralDelta`;
- model reasoning.

The roadmap says deeper Git-based capture is supported where justified; it does not require a second transport before the reconstruction gate can close. Existing exact Git root-tree and commit-object captures remain sufficient for the current V1 evidence corpus.

## Gate decision

M3 is satisfied for the current V1 GitHub capture surface when permanent CI proves:

1. existing capture still pins all reads to immutable revisions;
2. exact object bytes remain content-addressed and integrity checked;
3. an actual existing capture reconstructs locally with zero provider reads;
4. missing inputs survive reconstruction explicitly;
5. contradictory/incomplete local state fails closed;
6. same-tree revisions suppress repository-content reanalysis eligibility;
7. changed-tree revisions remain eligible without being mislabeled semantically;
8. the full existing regression/golden suite remains green.

After this gate, the next roadmap move is **M4 Deterministic Evidence reconciliation**: audit the substantial existing extractor surface against the formal M4 source-addressability gate and implement only missing deterministic evidence coverage or locator guarantees.
