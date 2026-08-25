# LemmaMind

**LemmaMind** is a personal technical-intelligence system for turning reproducible technical evidence into reviewed, decision-relevant knowledge.

GitHub is the first source ecosystem, not the boundary of the project. LemmaMind studies high-value technical sources, preserves the exact evidence used for analysis, separates observed facts from inference, detects meaningful changes, and progressively synthesizes cross-source patterns, tensions, insights, and reviewed knowledge.

Repository repair is not a core requirement. LemmaMind's mandatory job is to understand and substantiate; operational action is optional and depends on ownership, authority, risk, and user intent.

## Governing principle

> Useful evidence first. Evidence-bound inference second. Reviewed knowledge third. Real decisions are the measure of success.

## Current phase

**M−1 — Manual Intelligence Pilot: PASS.**

The completed pilot contains a controlled ElephantRock corpus plus four real external read-only repositories. It demonstrates useful single-source observations, cross-repository reasoning, negative intelligence, belief revision, correct no-action behavior, source-role classification, and decision-relevant intelligence without requiring source modification.

**M0 — Minimum System Contracts: implementation active.**

The executable M0 now includes strict versioned contracts, append-only SQLite persistence, a SHA-256 content-addressed artifact store, deterministic read-only GitHub file capture, exact Git root-tree capture, durable Git commit-metadata capture, deterministic evidence extraction, and an executable pilot evidence-coverage harness.

The evidence layer currently preserves artifact path facts, selected `pyproject.toml` / `package.json` facts, ordinary Markdown prose, Markdown list items, exact Git root-tree structure, and exact commit metadata. Authored prose and commit messages remain `SourceAssertion`; Git object structure and metadata remain `EvidenceFact`.

Live external evidence coverage has progressed against the same 12 frozen requirements:

- initial baseline: **4/12 (33.3%)**
- after Markdown list extraction: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**
- after durable Git commit evidence: **8/12 (66.7%)**

OpenClaw and the OPD research-index case are 3/3 at the deterministic evidence layer; Hermes is now 1/3. Historical reports are preserved rather than overwritten.

The four remaining measured gaps are language-specific source/test structure: three source-code requirements and one test-code requirement. The implementation remains deliberately below autonomous observations, architecture profiling, pattern/insight synthesis, embeddings, autonomous reasoning, and UI.

## Start here

- [`docs/PRODUCT.md`](docs/PRODUCT.md) — authoritative product definition, user, outputs, UX, and action boundary
- [`eval/pilot/M-1-CLOSEOUT.md`](eval/pilot/M-1-CLOSEOUT.md) — M−1 result, evidence, design changes, and exit decision
- [`docs/M0-CONTRACTS.md`](docs/M0-CONTRACTS.md) — minimum contracts selected from actual pilot cases
- [`docs/M0-IMPLEMENTATION.md`](docs/M0-IMPLEMENTATION.md) — rationale for executable M0 contracts and persistence
- [`docs/M0-CAPTURE.md`](docs/M0-CAPTURE.md) — deterministic GitHub capture semantics and trust boundary
- [`docs/M0-EXTRACTION.md`](docs/M0-EXTRACTION.md) — deterministic facts/assertions, provenance, and epistemic boundary
- [`eval/pilot/coverage/external-v1.yaml`](eval/pilot/coverage/external-v1.yaml) — machine-readable external evidence-recovery checks
- [`eval/pilot/coverage/reports/external-v1.md`](eval/pilot/coverage/reports/external-v1.md) — first live external baseline (4/12)
- [`eval/pilot/coverage/reports/external-v1-markdown-list.md`](eval/pilot/coverage/reports/external-v1-markdown-list.md) — post-P0 baseline (6/12)
- [`eval/pilot/coverage/reports/external-v1-git-tree.md`](eval/pilot/coverage/reports/external-v1-git-tree.md) — post-tree baseline (7/12)
- [`eval/pilot/coverage/reports/external-v1-commit-evidence.md`](eval/pilot/coverage/reports/external-v1-commit-evidence.md) — post-commit baseline (8/12)
- [`docs/M0-NEXT-EXTRACTORS.md`](docs/M0-NEXT-EXTRACTORS.md) — extractor priorities selected from measured gaps
- [`src/lemmamind/contracts.py`](src/lemmamind/contracts.py) — executable versioned M0 contract models
- [`src/lemmamind/storage.py`](src/lemmamind/storage.py) — atomic append-only SQLite contract persistence
- [`src/lemmamind/objects.py`](src/lemmamind/objects.py) — SHA-256 content-addressed captured bytes
- [`src/lemmamind/github.py`](src/lemmamind/github.py) — read-only GitHub file capture path
- [`src/lemmamind/git_tree.py`](src/lemmamind/git_tree.py) — exact Git root-tree capture and deterministic tree facts
- [`src/lemmamind/git_commit.py`](src/lemmamind/git_commit.py) — exact Git commit-metadata capture, metadata facts, and commit-message assertions
- [`src/lemmamind/extraction.py`](src/lemmamind/extraction.py) — deterministic artifact extractors and extraction service
- [`src/lemmamind/pilot_coverage.py`](src/lemmamind/pilot_coverage.py) — base evidence-coverage evaluator
- [`src/lemmamind/pilot_coverage_v2.py`](src/lemmamind/pilot_coverage_v2.py) — live coverage with Git-tree and commit evidence
- [`tests/`](tests/) — contract, persistence, capture, extraction, coverage, object-integrity, and golden-corpus regression tests
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
deterministic EvidenceFact / SourceAssertion
      ↓
pilot evidence-coverage measurement
```

The next implementation slice is **Python AST structural facts**, selected because the two remaining Hermes source/test requirements can be approached using Python's standard-library parser without introducing generic semantic program analysis. TypeScript source structure follows for OpenBot. No autonomous insight synthesis is required for M0/V1.

## Canonical home

https://github.com/ElephantRock/LemmaMind
