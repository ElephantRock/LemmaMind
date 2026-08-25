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

The executable M0 now includes strict versioned contracts, append-only SQLite persistence, a SHA-256 content-addressed artifact store, the first real read-only GitHub capture path, and deterministic evidence extraction from captured artifacts.

The initial extractor set emits artifact-scoped path facts, selected `pyproject.toml` / `package.json` facts, and explicit Markdown prose as line-addressed `SourceAssertion` records. It does not execute source content or convert source claims into observed facts.

The implementation remains deliberately below change intelligence, architecture profiling, pattern/insight synthesis, embeddings, autonomous reasoning, and UI.

## Start here

- [`docs/PRODUCT.md`](docs/PRODUCT.md) — authoritative product definition, user, outputs, UX, and action boundary
- [`eval/pilot/M-1-CLOSEOUT.md`](eval/pilot/M-1-CLOSEOUT.md) — M−1 result, evidence, design changes, and exit decision
- [`docs/M0-CONTRACTS.md`](docs/M0-CONTRACTS.md) — minimum contracts selected from actual pilot cases
- [`docs/M0-IMPLEMENTATION.md`](docs/M0-IMPLEMENTATION.md) — rationale for executable M0 contracts and persistence
- [`docs/M0-CAPTURE.md`](docs/M0-CAPTURE.md) — deterministic GitHub capture semantics and trust boundary
- [`docs/M0-EXTRACTION.md`](docs/M0-EXTRACTION.md) — deterministic facts/assertions, provenance, and epistemic boundary
- [`src/lemmamind/contracts.py`](src/lemmamind/contracts.py) — executable versioned M0 contract models
- [`src/lemmamind/storage.py`](src/lemmamind/storage.py) — atomic append-only SQLite contract persistence
- [`src/lemmamind/objects.py`](src/lemmamind/objects.py) — SHA-256 content-addressed captured bytes
- [`src/lemmamind/github.py`](src/lemmamind/github.py) — read-only GitHub REST adapter and capture service
- [`src/lemmamind/extraction.py`](src/lemmamind/extraction.py) — deterministic artifact extractors and extraction service
- [`tests/`](tests/) — contract, persistence, capture, extraction, object-integrity, and golden-corpus regression tests
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
exact revision
      ↓
content-addressed captured artifacts
      ↓
deterministic EvidenceFact / SourceAssertion
```

The next validation step is to run this capture + extraction path against selected pinned pilot artifacts and measure whether the deterministic evidence is sufficient to reconstruct the golden observations without adding inference prematurely. No autonomous insight synthesis is required for M0/V1.

## Canonical home

https://github.com/ElephantRock/LemmaMind
