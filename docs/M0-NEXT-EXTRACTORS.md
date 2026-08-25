# M0 — Next deterministic extractors selected from live pilot coverage

## Decision basis

LemmaMind now has three preserved live external coverage checkpoints against the same four pinned read-only repositories and 12 explicit golden-evidence requirements:

- initial deterministic baseline: **4/12 (33.3%)**
- after `markdown-list.v1`: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**

Reports are preserved under `eval/pilot/coverage/reports/`; new capabilities never rewrite historical evidence.

## Selection principles

1. Prefer deterministic source preservation and syntax/structure before interpretation.
2. Prefer capabilities tied to measured golden-case gaps.
3. Never encode architectural meaning directly as `EvidenceFact` merely to improve coverage.
4. Keep source claims as `SourceAssertion`.
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

Implemented behavior:

- follows the already pinned `SourceRevision.tree_sha`;
- calls the non-recursive Git Trees endpoint read-only;
- rejects a returned SHA that differs from the pinned tree SHA;
- canonicalizes the root tree into UTF-8 JSON;
- stores those bytes as a SHA-256 content-addressed `Artifact` in a dedicated `CaptureManifest`;
- emits deterministic facts for tree SHA, recursive/truncated state, root entry count and path set, and per-entry type/mode/SHA/size where supplied;
- fails an exact-root coverage check if the tree is truncated, any expected entry is missing, or any unexpected entry appears.

For the pinned OPD revision `e4b5e7334ccd3437ccab8d4eef770ed02c4f9934`, the commit resolves to root tree `c159887c873d5003aec7dabb0ee579f22a18e82b`. The live run observed an exact non-truncated root of:

- `.claude`
- `CITATION.cff`
- `CONTRIBUTING.md`
- `LICENSE`
- `README.md`

Live effect:

- OPD index: `2/3 → 3/3`
- overall: `6/12 → 7/12`

The tree facts support the existing source-role interpretation; they do not themselves classify the repository.

## Priority 1 — Durable commit metadata/change artifact: NEXT

**Gap addressed directly:** 1 requirement

- `hermes-containment-1`

### Required behavior

The GitHub file capture path already retrieves the pinned commit to resolve `commit_sha` and `tree_sha`. The next slice should preserve a canonical immutable commit artifact rather than discarding that metadata after resolution.

At minimum preserve:

- commit SHA;
- tree SHA;
- parent SHAs;
- author timestamp;
- committer timestamp;
- commit message;
- source-supplied verification state.

### Epistemic output

- commit identity, parent structure, tree identity, timestamps, verification metadata → `EvidenceFact`
- commit-message text → `SourceAssertion`

The commit message must not be promoted to an observed behavioral fact merely because it describes a fix.

### Why next

Hermes `hermes-containment-1` is specifically a change-intelligence requirement. File snapshots alone cannot establish what changed or why a revision exists. Durable commit evidence is also prerequisite infrastructure for M5 meaningful-change analysis.

## Priority 2 — Python AST structural facts

**Gaps informed:** 2 Hermes requirements

- `hermes-containment-2`
- `hermes-containment-3`

Use Python's standard-library `ast` to emit deterministic source ranges and syntax facts such as function/class definitions, call expressions, keyword/literal arguments, try/except structure, assertions, test function names, and statement ordering.

Do not emit conclusions such as “descendants are fully contained”; that remains later reviewed reasoning.

## Priority 2 — TypeScript comments + structural facts

**Gaps informed:** 2 OpenBot requirements

- `openbot-authority-2`
- `openbot-authority-3`

Preserve explicit TypeScript comments/doc comments first as `SourceAssertion`. Add version-pinned syntax/AST extraction only where needed to recover deterministic control-flow or grant-intersection structure.

The existing `source-code-semantic-facts` gap label is a coverage category, not an implementation contract.

## Current sequence

```text
P0  Markdown structural assertions       COMPLETE — 6/12
        ↓
P1  Git root-tree capture/facts          COMPLETE — 7/12
        ↓
P1  Commit metadata/change artifact      NEXT
        ↓
P2  Python AST structural facts
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
