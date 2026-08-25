# M0 TypeScript evidence trust surface

## Purpose

The frozen external pilot left two OpenBot evidence requirements that could not be recovered from Markdown, Git objects, commit metadata, or Python AST structure. This slice adds the minimum TypeScript evidence surface needed to close those measured gaps without introducing a TypeScript runtime, compiler pipeline, type checker, or generic semantic analyzer.

## Epistemic split

TypeScript source contains two distinct evidence classes:

- authored comments/doc comments → `SourceAssertion` via `typescript-comment.v1`;
- parser-derived syntax → `EvidenceFact` via `typescript-ast.v1`.

A source comment that says a runtime behaves a certain way remains an authored claim. A parsed `if`, `throw`, call, declaration, or function node is a syntactic fact. Higher-level architectural meaning remains an `Observation`/interpretation built over explicit support.

## Parser implementation

The accepted parser pair is pinned exactly:

```text
tree-sitter==0.24.0
tree-sitter-typescript==0.23.2
```

The extractor:

1. consumes only bytes already captured at a pinned `SourceRevision`;
2. selects the TypeScript or TSX grammar from the pinned grammar package;
3. parses without executing or importing the target source;
4. fails closed if the parse tree contains syntax errors;
5. emits exact one-based line / zero-based column ranges;
6. records a deliberately small syntax surface;
7. stores source comments separately from syntax facts.

Current syntax kinds:

- function/method/function-expression/arrow-function nodes;
- call expressions;
- `if` statements;
- `throw` statements;
- variable declarations;
- type aliases;
- interfaces.

This is not a claim that those node kinds are sufficient for TypeScript generally. They are the minimum justified by the current golden corpus.

## Rejected parser pairing

The first live attempt pinned:

```text
tree-sitter==0.26.0
tree-sitter-typescript==0.23.2
```

Small offline fixtures succeeded, but the full pinned external coverage process crashed with a native segmentation fault (exit `139`) in workflow run `32850400232`.

That failure matters epistemically. A native parser crash means the evidence-producing implementation is not reliably reproducible even if its Python-level unit tests pass. The run was therefore not retried blindly and was not accepted as evidence.

The Tree-sitter runtime was aligned to the TypeScript grammar project's 0.24 generation, then the complete gate was rerun.

## Accepted live validation

Workflow run `32850490426` executed branch head:

`2430be25d0aa0a6ac8087dcb19b5d21a79e148e6`

Results:

- dependency installation: success;
- offline regression suite: **60 passed**;
- live pinned capture/extraction: success;
- GitHub permission boundary: `contents: read`, `metadata: read`;
- OpenBot: `1/3 → 3/3`;
- complete external corpus: `10/12 → 12/12`.

For the pinned OpenBot TypeScript artifact the live run emitted:

- 307 `typescript-ast.v1` facts;
- 28 `typescript-comment.v1` assertions.

## Golden requirement behavior

### `openbot-authority-2`

Recovery requires both:

- authored comments that state a skill is instructional and that actual runtime offering is constrained by grants/intersection;
- syntax facts showing separate operations involving skill-tool declarations and plugin grants.

This prevents source prose alone from satisfying the structural component.

### `openbot-authority-3`

Recovery requires both:

- authored comments explaining that unknown tool refs are not load-time grant checks and remain inert under runtime intersection;
- syntax facts for the package-skill slug refusal branch and its `throw`.

This preserves the distinction between an unknown tool declaration that is inert and an unknown package skill slug that is rejected.

## Reproducibility rule

For native/parser-backed evidence extraction, reproducibility includes the runtime/grammar pair, not only LemmaMind's extractor code version. The parser versions therefore belong in the evidence policy/trust surface and must remain pinned until deliberately revalidated.

An upgrade must repeat the real frozen-corpus gate. Passing small parser fixtures alone is insufficient.

## What this milestone does not prove

The 12/12 external result proves deterministic recovery of the selected evidence requirements in the frozen corpus. It does not prove:

- that every source comment is true;
- that parsed syntax has the architectural meaning later assigned to it;
- that OpenBot's runtime always enforces the documented authority model;
- that LemmaMind can automatically generate or promote the golden observations;
- that the current TypeScript syntax surface generalizes to arbitrary repositories.

Those questions belong to later evidence-supported observation, validation, and cross-source reasoning stages.
