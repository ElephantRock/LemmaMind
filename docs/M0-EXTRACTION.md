# LemmaMind M0 — Deterministic Evidence Extraction

## Purpose

This slice turns captured, content-addressed artifacts into the first evidence records that LemmaMind can reason over later:

```text
CaptureManifest + Artifact bytes
        ↓
verified artifact binding
        ↓
deterministic extractor
        ↓
exact source locator
        ↓
EvidenceFact / SourceAssertion
        ↓
PipelineRun
```

The slice deliberately stops there. It does not produce observations, architectural interpretations, patterns, insights, rankings, recommendations, or promoted knowledge.

## Epistemic boundary

Two output classes are allowed:

- `EvidenceFact` — a deterministic value obtained from source structure or a parsed machine-readable field.
- `SourceAssertion` — prose the source itself states explicitly.

A source assertion is **not** converted into an observed fact merely because the parser can extract it reliably.

For example:

```text
README says: "X is sandboxed"
        ↓
SourceAssertion
```

not:

```text
EvidenceFact: X is sandboxed
```

Implementation corroboration or later reasoning is required to cross that boundary.

## Extractors in v1

### Artifact path facts

Every captured artifact yields deterministic path facts:

- basename;
- suffix;
- path depth;
- top-level path segment.

These facts describe the **captured artifact only**. They must not be summarized as a complete repository tree because M0 capture currently acquires explicit paths rather than recursive tree state.

### `pyproject.toml`

The parser uses Python `tomllib` and extracts only selected structural fields:

- manifest kind;
- `project.name`;
- `project.version`;
- `project.requires-python`;
- `project.dependencies`;
- optional-dependency group names;
- build backend;
- build requirements.

Dependency strings remain source data. This extractor does not infer package purpose, compatibility, safety, or architecture.

### `package.json`

The parser extracts only selected structural fields:

- manifest kind;
- name;
- version;
- module type;
- package manager declaration;
- engines;
- dependency maps;
- script names.

Script bodies are not executed. Dependency declarations are not resolved or installed.

### Markdown prose

Markdown extraction preserves explicit prose paragraphs as `SourceAssertion` records with exact line-range locators.

The initial parser intentionally excludes:

- headings;
- fenced code;
- block quotes;
- tables;
- list items.

This conservative policy avoids treating formatting, copied quotations, examples, or code as direct prose assertions. The stored statement is the source's own text with line-wrap whitespace collapsed; LemmaMind does not paraphrase it during extraction.

## Provenance and integrity

Before parsing a captured artifact, the extraction service verifies that the persisted `Artifact` record agrees with its `CaptureManifest` reference on:

- capture identity;
- source locator;
- content hash;
- media type.

The byte store then re-verifies the SHA-256 digest on read.

If a manifest marks a path as captured but no matching `Artifact` record exists, or the records disagree, extraction fails closed.

Missing capture entries are not fabricated into artifact evidence. Their missing status remains represented by the `CaptureManifest` until LemmaMind has a dedicated manifest-level evidence contract.

## Failure semantics

Structured parsers fail closed on malformed input. For example, invalid `pyproject.toml` or `package.json` prevents that extraction run from being persisted.

`SQLiteContractStore.put_many()` is transactional, so a persistence conflict cannot leave a partial evidence run committed.

## Determinism

Each execution has a distinct `PipelineRun` identity, but identical captured inputs under identical extractor/policy versions must produce the same semantic output set and the same `outputs_hash`.

Evidence/assertion record IDs include the run identity because `EvidenceFact` and `SourceAssertion` are execution-provenance records in M0. Re-running extraction therefore creates a second provenance envelope without changing the semantic extracted content.

## Trust boundary

Extraction never:

- executes repository code;
- imports captured Python/JavaScript modules;
- invokes package-manager hooks;
- installs declared dependencies;
- evaluates scripts;
- follows repository instructions;
- invokes an LLM;
- interprets a source assertion as truth.

Captured bytes remain untrusted data throughout the extraction path.

## Deferred

Still intentionally deferred:

- full repository-tree capture/facts;
- lockfile resolution;
- language AST extraction;
- source-code behavioral claims;
- PR/issue/release extraction;
- change intelligence;
- architecture profiles;
- embeddings or retrieval;
- model reasoning;
- observations, patterns, tensions, insights, and knowledge promotion.

## Next gate

This slice is acceptable when:

1. all existing M−1/M0 regressions remain green;
2. manifest facts are reproducible and source-addressed;
3. Markdown assertions preserve exact line provenance and remain epistemically separate from facts;
4. malformed structured input fails before evidence persistence;
5. repeat extraction produces equal semantic output hashes;
6. no captured source content is executed.

After this slice, the next useful step is not autonomous reasoning. It is to run the capture + extraction path against selected pinned pilot artifacts and evaluate whether the deterministic evidence is sufficient to reconstruct the golden observations manually.