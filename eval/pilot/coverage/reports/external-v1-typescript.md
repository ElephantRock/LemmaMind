# External pilot deterministic-evidence coverage — after TypeScript evidence

Coverage ID: `external-golden-evidence-v1`

This is the sixth live execution of the same frozen external coverage corpus. Historical 4/12, 6/12, 7/12, 8/12, and 10/12 checkpoints remain preserved.

## Live execution provenance

- Successful one-time live workflow run: `32850490426`
- Branch head executed: `2430be25d0aa0a6ac8087dcb19b5d21a79e148e6`
- Offline suite before live capture: **60 passed**
- Live pinned capture/extraction step: **success**
- GitHub token permissions: read-only `contents: read`, `metadata: read`
- Coverage specification: `eval/pilot/coverage/external-v1.yaml`
- Prior Python-AST baseline: **10/12 (83.3%)**

## Result

- Cases: **4**
- Evidence requirements: **12**
- Recovered: **12**
- Gaps: **0**
- Coverage fraction: **1.000**
- Absolute improvement over prior run: **+2 requirements**
- Coverage progression: **33.3% → 50.0% → 58.3% → 66.7% → 83.3% → 100.0%**

| Case | Before TypeScript evidence | After | Change |
| --- | ---: | ---: | ---: |
| `external-openbot-capability-authority` | 1/3 | **3/3** | +2 |
| `external-openclaw-sandbox-posture` | 3/3 | **3/3** | 0 |
| `external-hermes-process-containment` | 3/3 | **3/3** | 0 |
| `external-opd-source-type` | 3/3 | **3/3** | 0 |

## Newly recovered evidence

### OpenBot authority separation

`openbot-authority-2` now requires both authored TypeScript comments and parser-derived syntax. The live run recovered:

- the authored `TenantAgent.skills` explanation at `server/src/tenant-package.ts:L145-L156`, including that a skill is instructional rather than authoritative and that runtime offering is constrained by grants;
- syntax facts showing the package code separately operates on declared skill tools and plugin grants.

The comments remain `SourceAssertion`; the call structure remains `EvidenceFact`. Neither is silently converted into a higher-level architectural conclusion.

### OpenBot fail-closed package validation

`openbot-authority-3` now recovers:

- the authored `TenantSkill.tools` explanation at `L116-L125`, including that unknown tool references remain inert under runtime intersection;
- the authored package-skill validation rationale at `L399-L407`;
- the actual `if (!skillSlugs.has(slug))` branch at `L408:C6-L412:C7`;
- the corresponding refusal `throw` at `L409:C8-L411:C10`.

This supports the golden distinction between a declared tool requirement and actual grant authority while preserving the source's authored semantics separately from parser facts.

## Extraction volume

For the pinned OpenBot TypeScript artifact, the TypeScript-enabled extraction emitted:

- **307** `typescript-ast.v1` `EvidenceFact` records
- **28** `typescript-comment.v1` `SourceAssertion` records
- **315** total deterministic file facts including the pre-existing artifact-path facts
- **133** total source assertions including pre-existing README/Markdown assertions

The corpus is now fully covered at the deterministic evidence-recovery layer. This does not imply every emitted syntax node is equally useful; downstream observation/profile logic should select evidence relevant to a claim.

## Parser trust surface and rejected pairing

The first live parser pairing was deliberately not accepted:

- `tree-sitter==0.26.0`
- `tree-sitter-typescript==0.23.2`
- offline fixtures passed, but real pinned coverage crashed with a native **segmentation fault (exit 139)** in workflow run `32850400232`.

A blind rerun would not have been evidence of correctness. The runtime was instead pinned to the grammar project's compatible 0.24 generation:

- `tree-sitter==0.24.0`
- `tree-sitter-typescript==0.23.2`

That exact pair passed 60 offline tests and the complete live frozen corpus in run `32850490426`.

This is an M0 evidence lesson: native/parser dependency compatibility is part of the evidence-producing trust surface. A deterministic extractor is not reproducible merely because its own Python wrapper is versioned.

## Trust boundary

`typescript-ast.v1`:

- operates only on already-captured `.ts` / `.tsx` bytes;
- parses with the pinned Tree-sitter runtime and TypeScript/TSX grammar;
- never executes source, resolves imports, runs a type checker, or evaluates expressions;
- emits exact line/column syntax locations;
- preserves authored comments separately as `typescript-comment.v1` `SourceAssertion`;
- fails closed on parse errors.

## Interpretation boundary

The **12/12** result means the current deterministic acquisition/extraction spine can recover all selected source-addressed evidence required by this frozen external validation corpus. It does **not** mean LemmaMind can automatically generate, validate, or promote the corpus's higher-level `Observation`, pattern, tension, or knowledge objects without reasoning and review.

## Milestone implication

There are now **no measured deterministic extractor gaps in the frozen external M−1 corpus**. The next move should not be adding parsers speculatively. The project should reassess the M0 exit boundary and begin testing the next epistemic link—evidence-supported observations and explicit support graphs—against the same golden cases.
