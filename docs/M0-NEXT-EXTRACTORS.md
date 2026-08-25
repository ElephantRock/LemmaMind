# M0 — Next deterministic extractors selected from live pilot coverage

## Decision basis

LemmaMind now has four preserved live external coverage checkpoints against the same four pinned read-only repositories and 12 explicit golden-evidence requirements:

- initial deterministic baseline: **4/12 (33.3%)**
- after `markdown-list.v1`: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**
- after durable Git commit evidence: **8/12 (66.7%)**

Reports are preserved under `eval/pilot/coverage/reports/`; new capabilities never rewrite historical evidence.

## Selection principles

1. Prefer deterministic source preservation and syntax/structure before interpretation.
2. Prefer capabilities tied to measured golden-case gaps.
3. Never encode architectural meaning directly as `EvidenceFact` merely to improve coverage.
4. Keep authored source claims as `SourceAssertion`.
5. Do not infer complete repository structure from selected files.
6. Prefer Git object structure and language-native parsers over regex when structural correctness matters.
7. Treat coverage as evidence-recovery measurement, not automatic observation validity.

## Priority 0 — Markdown structural source assertions: COMPLETE

`markdown-list.v1` preserves ordered/unordered list items, nested items, and indented continuation lines with exact line provenance while excluding fenced code. It remains separate from `markdown-prose.v1`.

Live effect:

- OpenBot: `0/3 → 1/3`
- OpenClaw: `2/3 → 3/3`
- overall: `4/12 → 6/12`

## Priority 1 — Exact Git root-tree capture and facts: COMPLETE

**Gap closed:** `opd-source-3`

The root-tree path follows the pinned `SourceRevision.tree_sha`, captures the exact non-recursive Git tree as content-addressed JSON, and emits deterministic facts for tree identity, truncation state, path membership, object type, mode, SHA, and size where supplied.

For the pinned OPD revision `e4b5e7334ccd3437ccab8d4eef770ed02c4f9934`, the exact non-truncated root tree is:

- `.claude`
- `CITATION.cff`
- `CONTRIBUTING.md`
- `LICENSE`
- `README.md`

Live effect:

- OPD index: `2/3 → 3/3`
- overall: `6/12 → 7/12`

The tree facts support the source-role interpretation; they do not themselves classify the repository.

## Priority 1 — Durable commit metadata/change evidence: COMPLETE

**Gap closed:** `hermes-containment-1`

Implemented behavior:

- follows the already pinned `SourceRevision.commit_sha`;
- rejects a returned commit SHA or tree SHA that disagrees with the pinned revision;
- stores a canonical immutable commit artifact in the content-addressed object store;
- preserves commit SHA, tree SHA, parent SHAs, author/committer timestamps, and source-supplied verification metadata as deterministic `EvidenceFact` records;
- preserves the authored commit message separately as `SourceAssertion`;
- does not interpret the commit message as proof of runtime behavior.

For Hermes revision `41447a6d7063b2772b0c2f26a5b22d9bd444fb43`, the commit-message assertion records that the terminal fix sweeps `setsid` descendants after the local timeout group-kill. This closes the change-statement requirement while leaving implementation and test behavior to later source-structure evidence.

Live effect:

- Hermes: `0/3 → 1/3`
- overall: `7/12 → 8/12`

## Priority 2 — Python AST structural facts: NEXT

**Measured gaps addressed:** 2 Hermes requirements

- `hermes-containment-2`
- `hermes-containment-3`

Use Python's standard-library `ast` parser. The first implementation should emit only deterministic source structure with exact source ranges, including:

- function and class definitions;
- call expressions and syntactically resolvable qualified call names;
- attribute access;
- literal positional and keyword arguments;
- assignment targets where useful to connect local names to calls/literals;
- `try` / `except` structure;
- assertion statements;
- test function names;
- statement ordering by line/column position;
- docstrings as `SourceAssertion` where they carry authored claims.

The Hermes implementation case should be able to recover structural evidence for descendant snapshotting, process-group signaling, survivor sweeping, and their source order. The test case should recover the `setsid` regression-test function, relevant calls/assertions, and the snapshot-failure regression.

Do **not** emit conclusions such as “descendants are fully contained” or “this test proves containment.” Those remain later reviewed `Observation` reasoning over the AST facts and source assertions.

### Why Python first

It can target two of the four remaining requirements with the standard library and no new parser dependency. That makes it the highest-yield remaining deterministic slice with a small trust surface.

## Priority 2 — TypeScript comments + structural facts

**Measured gaps addressed:** 2 OpenBot requirements

- `openbot-authority-2`
- `openbot-authority-3`

Preserve explicit TypeScript comments/doc comments first as `SourceAssertion`. Add a version-pinned syntax/AST parser only where needed to recover deterministic grant-intersection and gateway-control structure.

The existing `source-code-semantic-facts` coverage label is a missing-capability category, not an implementation contract. Architectural meaning still belongs in a later `Observation`.

## Current sequence

```text
P0  Markdown structural assertions       COMPLETE — 6/12
        ↓
P1  Git root-tree capture/facts          COMPLETE — 7/12
        ↓
P1  Commit metadata/change evidence      COMPLETE — 8/12
        ↓
P2  Python AST structural facts          NEXT
        ↓
P2  TypeScript comments + structural facts
        ↓
rerun external coverage after each slice
```

## Explicitly deferred

Still not justified by the measured corpus:

- LLM-based code interpretation;
- embeddings;
- automatic `Observation` generation;
- architecture-profile synthesis;
- generic semantic program analysis;
- autonomous knowledge promotion.
