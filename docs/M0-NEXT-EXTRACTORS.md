# M0 — Deterministic extractor progression selected from live pilot coverage

## Decision basis

LemmaMind now has six preserved live external coverage checkpoints against the same four pinned read-only repositories and 12 explicit golden-evidence requirements:

- initial deterministic baseline: **4/12 (33.3%)**
- after `markdown-list.v1`: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**
- after durable Git commit evidence: **8/12 (66.7%)**
- after Python AST structural evidence: **10/12 (83.3%)**
- after TypeScript comments + structural evidence: **12/12 (100.0%)**

Reports are preserved under `eval/pilot/coverage/reports/`; new capabilities never rewrite historical evidence.

## Selection principles

1. Prefer deterministic source preservation and syntax/structure before interpretation.
2. Prefer capabilities tied to measured golden-case gaps.
3. Never encode architectural meaning directly as `EvidenceFact` merely to improve coverage.
4. Keep authored source claims as `SourceAssertion`.
5. Do not infer complete repository structure from selected files.
6. Prefer Git object structure and language-native/version-pinned parsers over regex when structural correctness matters.
7. Treat parser/runtime compatibility as part of the evidence-producing trust surface.
8. Treat coverage as evidence-recovery measurement, not automatic observation validity.
9. Stop adding extractors when the frozen corpus no longer demonstrates an evidence gap.

## Priority 0 — Markdown structural source assertions: COMPLETE

`markdown-list.v1` preserves ordered/unordered list items, nested items, and indented continuation lines with exact line provenance while excluding fenced code. It remains separate from `markdown-prose.v1`.

Live effect: overall `4/12 → 6/12`; OpenBot `0/3 → 1/3`; OpenClaw `2/3 → 3/3`.

## Priority 1 — Exact Git root-tree capture and facts: COMPLETE

The root-tree path follows the pinned `SourceRevision.tree_sha`, captures the exact non-recursive Git tree as content-addressed JSON, and emits deterministic facts for tree identity, truncation, path membership, object type, mode, SHA, and size where supplied.

Live effect: OPD `2/3 → 3/3`; overall `6/12 → 7/12`.

## Priority 1 — Durable commit metadata/change evidence: COMPLETE

The commit path follows `SourceRevision.commit_sha`, rejects commit/tree disagreement, stores canonical content-addressed metadata, emits commit/tree/parent/timestamp/verification structure as `EvidenceFact`, and preserves the authored commit message as `SourceAssertion`.

Live effect: Hermes `0/3 → 1/3`; overall `7/12 → 8/12`.

## Priority 2 — Python AST structural facts: COMPLETE

`python-ast.v1` uses Python's standard-library `ast` parser and never imports or executes captured code. It emits exact source ranges and deterministic syntax facts for functions/classes, calls, arguments, assignments, assertions, `try` structure, and nested scopes. Authored docstrings remain `python-docstring.v1` `SourceAssertion` records.

Live run `32848352853` passed **53** offline tests before read-only capture and moved Hermes `1/3 → 3/3`, overall `8/12 → 10/12`.

The AST facts do **not** state that containment is correct or that tests prove the property. Those conclusions remain later reviewed `Observation` reasoning.

## Priority 2 — TypeScript comments + structural facts: COMPLETE

**Gaps closed:**

- `openbot-authority-2`
- `openbot-authority-3`

`typescript-ast.v1` parses already-captured `.ts` / `.tsx` bytes only. It emits exact-range syntax facts for the selected structural surface—functions, calls, declarations, `if`, `throw`, type aliases, and interfaces—without type checking, import resolution, evaluation, or execution.

Authored TypeScript comments are extracted separately as `typescript-comment.v1` `SourceAssertion` records.

The OpenBot coverage checks intentionally require mixed evidence rather than allowing comments to masquerade as facts:

- `openbot-authority-2` requires authored comments describing skill/grant intersection plus parser-derived syntax showing separate `skillTools` and `pluginGrants` operations;
- `openbot-authority-3` requires authored comments describing inert unknown tool references plus parser-derived `!skillSlugs.has(slug)` refusal and its `throw`.

Live run `32850490426` passed **60** offline tests and the complete read-only pinned external corpus. OpenBot moved `1/3 → 3/3`; overall coverage moved `10/12 → 12/12`.

### Parser trust surface

The accepted evidence-producing parser pair is pinned exactly:

- `tree-sitter==0.24.0`
- `tree-sitter-typescript==0.23.2`

A newer runtime was explicitly rejected during validation:

- `tree-sitter==0.26.0`
- `tree-sitter-typescript==0.23.2`
- small offline fixtures passed, but the real pinned coverage process segfaulted with exit code `139` in workflow run `32850400232`.

That result was not treated as a reason to weaken the golden checks or blindly retry. The runtime was aligned with the grammar's compatible Tree-sitter generation and then revalidated end-to-end. See `docs/M0-TYPESCRIPT-EVIDENCE.md`.

## Current sequence

```text
P0  Markdown structural assertions       COMPLETE — 6/12
        ↓
P1  Git root-tree capture/facts          COMPLETE — 7/12
        ↓
P1  Commit metadata/change evidence      COMPLETE — 8/12
        ↓
P2  Python AST structural facts          COMPLETE — 10/12
        ↓
P2  TypeScript comments + structure      COMPLETE — 12/12
```

## Deterministic-extractor exit condition

The frozen external corpus now has **no measured deterministic evidence-recovery gaps**. Therefore the next M0/V1 work should not add language parsers, semantic analyzers, or extraction breadth speculatively.

The next evidence-driven question is whether LemmaMind can construct and validate the golden `Observation` layer while preserving:

- explicit evidence support links;
- epistemic type (`ObservedFact`, `SourceAssertion`, `Interpretation`, `Evaluation`);
- validation/review state;
- source-revision provenance;
- belief revision/supersession;
- the distinction between epistemic disposition and operational action.

Any new extractor should be introduced only when a new golden case demonstrates a specific deterministic evidence gap.

## Still deferred

Not justified merely by reaching 12/12 evidence recovery:

- LLM-based generic code interpretation;
- embeddings;
- autonomous `Observation` generation without review constraints;
- architecture-profile synthesis without evidence support;
- generic semantic program analysis;
- autonomous knowledge promotion.
