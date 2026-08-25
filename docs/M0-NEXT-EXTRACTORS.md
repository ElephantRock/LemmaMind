# M0 — Next deterministic extractors selected from live pilot coverage

## Decision basis

The first live external coverage run recovered 4 of 12 golden-evidence requirements from four pinned read-only repositories. The baseline is recorded in:

- `eval/pilot/coverage/external-v1.yaml`
- `eval/pilot/coverage/reports/external-v1.json`
- `eval/pilot/coverage/reports/external-v1.md`

The purpose of this document is to select the next deterministic capabilities from observed coverage gaps rather than from speculative platform design.

## Selection principles

1. Prefer extractors that preserve source material or deterministic structure without interpretation.
2. Prefer capabilities that unlock multiple current golden requirements.
3. Do not introduce a generic “code semantics” extractor that silently embeds reasoning into `EvidenceFact`.
4. Keep `SourceAssertion` distinct from facts about source structure or execution behavior.
5. Do not claim complete repository structure from explicit-path capture.
6. Prefer language-native parsers or Git object structure over regex when structural correctness matters.

## Priority 0 — Markdown structural source assertions

**Gap addressed:** 2 requirements

- `openbot-authority-1`
- `openclaw-sandbox-3`

### Required behavior

Extend Markdown extraction to preserve explicit source text from structural constructs that v1 currently drops:

- list items;
- optionally block quotes where the source itself is making the assertion;
- continuation lines belonging to the same list item;
- exact line ranges and original text content.

### Epistemic output

`SourceAssertion`, never `EvidenceFact` merely because the text appears in a list.

### Why first

This is the smallest low-risk improvement and should directly recover two existing gaps without inference. It also improves README/documentation coverage generally.

## Priority 1 — Exact Git tree capture and tree facts

**Gap addressed directly:** 1 requirement

- `opd-source-3`

### Required behavior

Persist an exact Git tree artifact tied to the already pinned `SourceRevision.tree_sha`, then emit deterministic facts such as:

- root entry path;
- entry type (`blob`, `tree`, `commit`/submodule when applicable);
- Git object SHA;
- executable/file mode;
- root entry count;
- whether a requested recursive tree response was truncated.

For the OPD case, a non-recursive root tree is sufficient and preferable to inferring repository structure from selected files.

### Epistemic output

Tree membership and Git object identities are `EvidenceFact`.

### Why early

Repository structure is foundational for later change intelligence and architecture profiling. It also closes a current source-role evidence gap with very little semantic risk.

## Priority 1 — Durable commit metadata/change artifact

**Gap addressed directly:** 1 requirement

- `hermes-containment-1`

### Required behavior

The GitHub capture adapter already resolves commit metadata to pin a revision. Preserve a canonical immutable subset as content-addressed source evidence rather than discarding it after resolution. At minimum:

- commit SHA;
- tree SHA;
- parent SHAs;
- author/committer timestamps;
- commit message;
- verification state if supplied by the source API.

The commit message itself remains a source statement. Facts such as parent identities and timestamps are deterministic metadata facts.

### Epistemic output

- commit structure/timestamps → `EvidenceFact`
- commit-message prose → `SourceAssertion`

### Why early

Change-intelligence cases cannot be reconstructed from file snapshots alone. Persisting commit evidence is a prerequisite for later M5 meaningful-change analysis.

## Priority 2 — Python AST structural facts

**Gaps informed:** 2 Hermes requirements

- `hermes-containment-2`
- `hermes-containment-3`

### Required behavior

Use Python's standard-library `ast` parser to emit source-addressed structural facts such as:

- function/class definitions;
- call expressions and qualified call names when deterministically resolvable from syntax;
- keyword arguments and literal values;
- `try`/`except` structure;
- assertion statements;
- test function names;
- source line/column ranges;
- statement ordering by source position.

Do not emit claims such as “this fully contains descendants” from AST structure. A later reviewed interpretation can combine calls, ordering, tests, and commit evidence.

### Epistemic output

Syntactic structure is `EvidenceFact`; comments/docstrings remain `SourceAssertion` when preserved as source claims.

### Why before broad code analysis

Hermes provides a concrete Python case with known expected evidence. Built-in `ast` keeps the extractor deterministic and inspectable without introducing a general semantic-analysis engine.

## Priority 2 — TypeScript source structure, not generic semantics

**Gaps informed:** 2 OpenBot requirements

- `openbot-authority-2`
- `openbot-authority-3`

### Required behavior

First preserve explicit TypeScript comments/doc comments as `SourceAssertion` with exact line ranges. Then add syntax/AST facts only if needed to corroborate the relevant control flow and grant-intersection behavior.

Any parser dependency must be pinned and treated as an extractor implementation detail with explicit versioning.

### Epistemic output

- comments/doc comments → `SourceAssertion`
- syntax/AST structure → `EvidenceFact`
- architectural meaning → later `Observation`

### Why not a “source-code-semantic-facts” extractor

That gap label is a coverage category, not an implementation design. Encoding semantic conclusions directly as deterministic facts would collapse the Evidence → Observation boundary established by M−1.

## Expected sequence

```text
P0  Markdown structural assertions
        ↓
P1  Git tree capture/facts
        ↓
P1  Commit metadata/change artifact
        ↓
P2  Python AST structural facts
        ↓
P2  TypeScript comments + structural facts
        ↓
rerun external coverage baseline
```

After each slice, rerun `external-golden-evidence-v1` and compare the new transient-ID-free report to the committed baseline. The goal is not to maximize a percentage mechanically; the goal is to recover the evidence necessary for the golden cases **without weakening epistemic typing**.

## Explicitly deferred

Still not justified by this coverage run:

- LLM-based code interpretation;
- embeddings;
- automatic `Observation` generation;
- architecture-profile synthesis;
- generic semantic program analysis;
- autonomous knowledge promotion.
