# M0 — Next deterministic extractors selected from live pilot coverage

## Decision basis

LemmaMind now has five preserved live external coverage checkpoints against the same four pinned read-only repositories and 12 explicit golden-evidence requirements:

- initial deterministic baseline: **4/12 (33.3%)**
- after `markdown-list.v1`: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**
- after durable Git commit evidence: **8/12 (66.7%)**
- after Python AST structural evidence: **10/12 (83.3%)**

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

Live effect: overall `4/12 → 6/12`; OpenBot `0/3 → 1/3`; OpenClaw `2/3 → 3/3`.

## Priority 1 — Exact Git root-tree capture and facts: COMPLETE

The root-tree path follows the pinned `SourceRevision.tree_sha`, captures the exact non-recursive Git tree as content-addressed JSON, and emits deterministic facts for tree identity, truncation, path membership, object type, mode, SHA, and size where supplied.

Live effect: OPD `2/3 → 3/3`; overall `6/12 → 7/12`.

## Priority 1 — Durable commit metadata/change evidence: COMPLETE

The commit path follows `SourceRevision.commit_sha`, rejects commit/tree disagreement, stores canonical content-addressed metadata, emits commit/tree/parent/timestamp/verification structure as `EvidenceFact`, and preserves the authored commit message as `SourceAssertion`.

Live effect: Hermes `0/3 → 1/3`; overall `7/12 → 8/12`.

## Priority 2 — Python AST structural facts: COMPLETE

**Gaps closed:**

- `hermes-containment-2`
- `hermes-containment-3`

`python-ast.v1` uses Python's standard-library `ast` parser and never imports or executes captured code. It emits exact source ranges and deterministic syntax facts for:

- function/class definitions and qualified scopes;
- call expressions and syntactically resolvable call names;
- positional/keyword syntax;
- assignments and call-valued assignments;
- assertion statements;
- `try` / `except` structure;
- nested function structure.

Authored module/class/function docstrings are preserved separately as `python-docstring.v1` `SourceAssertion` records.

For the pinned Hermes implementation, deterministic facts recover:

- `LocalEnvironment._kill_process`;
- nested `_sweep_escaped_descendants`;
- `descendants = psutil.Process(proc.pid).children(recursive=True)`;
- `child.kill()` in the survivor sweep;
- process-group SIGTERM and SIGKILL calls.

For the pinned Hermes regression test, deterministic facts recover both target test functions, calls into `env.execute`, `_wait_for_pid_exit`, `env._kill_process`, monkeypatch setup, and the selected assertion syntax.

Live run `32848352853` passed **53** offline tests before the read-only capture and moved Hermes `1/3 → 3/3`, overall `8/12 → 10/12`.

The AST facts do **not** state that containment is correct or that the tests prove the property. Those conclusions remain later reviewed `Observation` reasoning.

## Priority 2 — TypeScript comments + structural facts: NEXT

**Remaining measured gaps:**

- `openbot-authority-2`
- `openbot-authority-3`

The historical coverage label `source-code-semantic-facts` is a capability category, not an implementation contract. The implementation should remain syntax-first.

### Required approach

1. Inspect the exact pinned OpenBot TypeScript artifact and define the minimum structural selectors required by the two golden requirements.
2. Preserve explicit line/block/doc comments as exact-range `SourceAssertion` records where they contain authored claims.
3. Introduce a TypeScript parser only if comments alone are insufficient.
4. Pin the parser dependency/version and expose it through an explicit extractor version/policy.
5. Emit syntax facts for the exact relevant structures—e.g. function/method definitions, call expressions, property access, object/array literals, and control-flow constructs—without labeling them with architectural conclusions.
6. Rerun the same 12-requirement corpus and require that any move to 12/12 comes from explicit source-addressed evidence rather than a weaker check.

### Trust-surface constraint

Unlike Python AST, TypeScript parsing introduces a non-stdlib parser dependency. That dependency must be treated as part of the evidence-producing implementation: pinned, tested, versioned, and visible in `PipelineRun` inputs/policy. Do not add a broad compiler/runtime toolchain merely to satisfy the two cases.

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
P2  TypeScript comments + structure      NEXT — 2 requirements remain
```

## Explicitly deferred

Still not justified by the measured corpus:

- LLM-based code interpretation;
- embeddings;
- automatic `Observation` generation;
- architecture-profile synthesis;
- generic semantic program analysis;
- autonomous knowledge promotion.
