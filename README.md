# LemmaMind

**LemmaMind** is a personal technical-intelligence system for turning reproducible technical evidence into reviewed, decision-relevant knowledge.

GitHub is the first source ecosystem, not the boundary of the project. LemmaMind studies high-value technical sources, preserves the exact evidence used for analysis, separates observed facts from inference, detects meaningful changes, and progressively synthesizes cross-source patterns, tensions, insights, and reviewed knowledge.

Repository repair is not a core requirement. LemmaMind's mandatory job is to understand and substantiate; operational action is optional and depends on ownership, authority, risk, and user intent.

## Governing principle

> Useful evidence first. Evidence-bound inference second. Reviewed knowledge third. Real decisions are the measure of success.

## Current phase

**M−1 — Manual Intelligence Pilot: PASS.**

The completed pilot contains a controlled ElephantRock corpus plus four real external read-only repositories. It demonstrates useful single-source observations, cross-repository reasoning, negative intelligence, belief revision, correct no-action behavior, source-role classification, and decision-relevant intelligence without requiring source modification.

**M0 — Minimum System Contracts: implementation active; deterministic evidence spine complete for the frozen external corpus, first evidence-supported Observation transition live-validated.**

The executable M0 now includes strict versioned contracts, append-only SQLite persistence, a SHA-256 content-addressed artifact store, deterministic read-only GitHub file capture, exact Git root-tree capture, durable Git commit-metadata capture, deterministic artifact extraction, Python AST structural evidence, TypeScript/TSX syntax and comment evidence, an executable pilot evidence-coverage harness, and explicit candidate `Observation` construction with typed support edges.

The evidence layer preserves artifact path facts, selected `pyproject.toml` / `package.json` facts, ordinary Markdown prose, Markdown list items, exact Git root-tree structure, exact commit metadata, Python syntax, and TypeScript/TSX syntax with line/column provenance. Authored prose, commit messages, Python docstrings, and TypeScript comments remain `SourceAssertion`; Git object structure, metadata, and parser-derived syntax remain `EvidenceFact`.

Live external evidence coverage has progressed against the same 12 frozen requirements:

- initial baseline: **4/12 (33.3%)**
- after Markdown list extraction: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**
- after durable Git commit evidence: **8/12 (66.7%)**
- after Python AST structural evidence: **10/12 (83.3%)**
- after TypeScript comments + structural evidence: **12/12 (100.0%)**

OpenBot, OpenClaw, Hermes, and the OPD research-index case are all 3/3 at the deterministic evidence-recovery layer. Historical reports are preserved rather than overwritten.

The first live `Evidence → ObservationSupport → Observation` probe then replayed the two frozen OpenBot golden observations against freshly captured evidence. Workflow run `32851722987` passed **66 offline tests** and constructed both golden statements with matching epistemic types, exact runtime support edges, and one pinned OpenBot `SourceRevision`. The fresh runtime records correctly remained **`candidate`** even though the golden evaluation targets are `validated` and `reviewed`.

That result is deliberately narrow: LemmaMind can now preserve a correct evidence-supported candidate claim graph for this case. It still does **not** generate the claim, choose the support set autonomously, independently validate the claim, or promote it to knowledge.

The implementation remains deliberately below autonomous architecture profiling, pattern/insight synthesis, embeddings, autonomous reasoning, and UI. The next measured boundary is to exercise the same Observation contract against the hardest M−1 distinctions—belief revision, correct no-action behavior, CI-state interpretation, and source-role constraints—before introducing model-generated claims.

## Start here

- [`docs/PRODUCT.md`](docs/PRODUCT.md) — authoritative product definition, user, outputs, UX, and action boundary
- [`eval/pilot/M-1-CLOSEOUT.md`](eval/pilot/M-1-CLOSEOUT.md) — M−1 result, evidence, design changes, and exit decision
- [`docs/M0-CONTRACTS.md`](docs/M0-CONTRACTS.md) — minimum contracts selected from actual pilot cases
- [`docs/M0-IMPLEMENTATION.md`](docs/M0-IMPLEMENTATION.md) — rationale for executable M0 contracts and persistence
- [`docs/M0-CAPTURE.md`](docs/M0-CAPTURE.md) — deterministic GitHub capture semantics and trust boundary
- [`docs/M0-EXTRACTION.md`](docs/M0-EXTRACTION.md) — deterministic facts/assertions, provenance, and epistemic boundary
- [`docs/M0-TYPESCRIPT-EVIDENCE.md`](docs/M0-TYPESCRIPT-EVIDENCE.md) — pinned TypeScript parser trust surface and compatibility evidence
- [`docs/M0-OBSERVATIONS.md`](docs/M0-OBSERVATIONS.md) — supported Observation construction, support/provenance rules, and validation-state boundary
- [`eval/pilot/coverage/external-v1.yaml`](eval/pilot/coverage/external-v1.yaml) — machine-readable external evidence-recovery checks
- [`eval/pilot/coverage/reports/external-v1.md`](eval/pilot/coverage/reports/external-v1.md) — first live external baseline (4/12)
- [`eval/pilot/coverage/reports/external-v1-markdown-list.md`](eval/pilot/coverage/reports/external-v1-markdown-list.md) — post-P0 baseline (6/12)
- [`eval/pilot/coverage/reports/external-v1-git-tree.md`](eval/pilot/coverage/reports/external-v1-git-tree.md) — post-tree baseline (7/12)
- [`eval/pilot/coverage/reports/external-v1-commit-evidence.md`](eval/pilot/coverage/reports/external-v1-commit-evidence.md) — post-commit baseline (8/12)
- [`eval/pilot/coverage/reports/external-v1-python-ast.md`](eval/pilot/coverage/reports/external-v1-python-ast.md) — post-Python-AST baseline (10/12)
- [`eval/pilot/coverage/reports/external-v1-typescript.md`](eval/pilot/coverage/reports/external-v1-typescript.md) — complete deterministic evidence checkpoint (12/12)
- [`eval/pilot/observation-reports/external-openbot-v1.md`](eval/pilot/observation-reports/external-openbot-v1.md) — first live evidence-supported Observation probe
- [`docs/M0-NEXT-EXTRACTORS.md`](docs/M0-NEXT-EXTRACTORS.md) — measured extractor progression and exit condition
- [`src/lemmamind/contracts.py`](src/lemmamind/contracts.py) — executable versioned M0 contract models
- [`src/lemmamind/storage.py`](src/lemmamind/storage.py) — atomic append-only SQLite contract persistence
- [`src/lemmamind/objects.py`](src/lemmamind/objects.py) — SHA-256 content-addressed captured bytes
- [`src/lemmamind/github.py`](src/lemmamind/github.py) — read-only GitHub file capture path
- [`src/lemmamind/git_tree.py`](src/lemmamind/git_tree.py) — exact Git root-tree capture and deterministic tree facts
- [`src/lemmamind/git_commit.py`](src/lemmamind/git_commit.py) — exact Git commit-metadata capture, metadata facts, and commit-message assertions
- [`src/lemmamind/python_ast.py`](src/lemmamind/python_ast.py) — deterministic Python AST facts and docstring assertions
- [`src/lemmamind/typescript_ast.py`](src/lemmamind/typescript_ast.py) — deterministic TypeScript/TSX syntax facts and comment assertions
- [`src/lemmamind/observations.py`](src/lemmamind/observations.py) — candidate Observation construction with validated support provenance
- [`src/lemmamind/pilot_observations.py`](src/lemmamind/pilot_observations.py) — golden-driven live OpenBot Observation probe
- [`src/lemmamind/extraction.py`](src/lemmamind/extraction.py) — deterministic artifact extractors and extraction service
- [`src/lemmamind/pilot_coverage.py`](src/lemmamind/pilot_coverage.py) — base evidence-coverage evaluator
- [`src/lemmamind/pilot_coverage_v2.py`](src/lemmamind/pilot_coverage_v2.py) — historical Git-object + Python AST coverage policy
- [`src/lemmamind/pilot_coverage_v3.py`](src/lemmamind/pilot_coverage_v3.py) — TypeScript-aware deterministic coverage policy
- [`tests/`](tests/) — contract, persistence, capture, extraction, observation, coverage, object-integrity, and golden-corpus regression tests
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — comprehensive project roadmap
- [`docs/PILOT.md`](docs/PILOT.md) — M−1 protocol and completed corpus
- [`pilot/watchlist.yaml`](pilot/watchlist.yaml) — pinned internal + external validation corpus
- [`eval/pilot/`](eval/pilot/) — golden intelligence cases and evaluation contract
- [`eval/pilot/schema/pilot-case.schema.json`](eval/pilot/schema/pilot-case.schema.json) — machine-readable case schema
- [`config/domains.yaml`](config/domains.yaml) — configurable technical domains

## Core product loop

```text
What should I pay attention to?
            ↓
     DISCOVER / CHANGE
            ↓
         EVIDENCE
            ↓
        UNDERSTAND
            ↓
         COMPARE
            ↓
        SYNTHESIZE
            ↓
          REVIEW
            ↓
     ┌──────┴──────┐
     ↓             ↓
 KNOWLEDGE      DECISION
     │             │
     └──────┬──────┘
            ↓
       REVALIDATE
```

## M0 rule

The implementation target remains deliberately small:

```text
Source
  ↓
SourceRevision
  ↓
CaptureManifest
  ↓
Artifact
  ↓
EvidenceFact / SourceAssertion
  ↓
Observation + explicit support
```

Cross-cutting from the start: `PipelineRun`, `RepositoryRelationship`, `ActionRecommendation`, and `ReviewDecision`.

Current implemented boundary:

```text
GitHub metadata
      ↓
exact commit + tree revision
      ↓
content-addressed file / Git-tree / commit artifacts
      ↓
deterministic text / metadata / Python / TypeScript syntax evidence
      ↓
EvidenceFact / SourceAssertion
      ↓
12/12 frozen deterministic evidence recovery
      ↓
Observation + ObservationSupport
(manual / golden-driven candidate construction)
```

The next measured implementation slice is **hard-case Observation validation**, not autonomous claim generation: exercise belief revision/supersession, no-action outcomes, CI-state interpretation, and source-role constraints while preserving exact support provenance and independent review state. Model-proposed observations come only after these support-graph invariants survive the golden corpus.

## Canonical home

https://github.com/ElephantRock/LemmaMind
