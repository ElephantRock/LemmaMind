# LemmaMind

**LemmaMind** is a personal technical-intelligence system for turning reproducible technical evidence into reviewed, decision-relevant knowledge.

GitHub is the first source ecosystem, not the boundary of the project. LemmaMind studies high-value technical sources, preserves the exact evidence used for analysis, separates observed facts from inference, detects meaningful changes, and progressively synthesizes cross-source patterns, tensions, insights, and reviewed knowledge.

Repository repair is not a core requirement. LemmaMind's mandatory job is to understand and substantiate; operational action is optional and depends on ownership, authority, risk, and user intent.

## Governing principle

> Useful evidence first. Evidence-bound inference second. Reviewed knowledge third. Real decisions are the measure of success.

## Current phase

**M−1 — Manual Intelligence Pilot: PASS.**

The completed pilot contains a controlled ElephantRock corpus plus four real external read-only repositories. It demonstrates useful single-source observations, cross-repository reasoning, negative intelligence, belief revision, correct no-action behavior, source-role classification, and decision-relevant intelligence without requiring source modification.

**M0 — Minimum System Contracts: implementation active; deterministic repository evidence complete for the frozen external corpus, evidence-supported Observation construction live-validated, and GitHub issue/PR snapshot evidence live-validated.**

The executable M0 now includes strict versioned contracts, append-only SQLite persistence, a SHA-256 content-addressed artifact store, deterministic read-only GitHub file capture, exact Git root-tree capture, durable Git commit-metadata capture, deterministic artifact extraction, Python AST structural evidence, TypeScript/TSX syntax and comment evidence, explicit candidate `Observation` construction with typed support edges, revision-aware same-source supersession, an executable hard-case readiness matrix, and durable current GitHub issue/pull-request process snapshots.

The evidence layer preserves artifact path facts, selected `pyproject.toml` / `package.json` facts, ordinary Markdown prose, Markdown list items, exact Git root-tree structure, exact commit metadata, Python syntax, TypeScript/TSX syntax, and current GitHub issue/PR process metadata. Authored prose, commit messages, Python docstrings, TypeScript comments, and issue/PR titles/bodies remain `SourceAssertion`; Git object structure, provider/process metadata, and parser-derived syntax remain `EvidenceFact`.

Live external repository evidence coverage progressed against the same 12 frozen requirements:

- initial baseline: **4/12 (33.3%)**
- after Markdown list extraction: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**
- after durable Git commit evidence: **8/12 (66.7%)**
- after Python AST structural evidence: **10/12 (83.3%)**
- after TypeScript comments + structural evidence: **12/12 (100.0%)**

OpenBot, OpenClaw, Hermes, and the OPD research-index case are all 3/3 at the deterministic repository evidence-recovery layer. Historical reports are preserved rather than overwritten.

The first live `Evidence → ObservationSupport → Observation` probe replayed the two frozen OpenBot golden observations against freshly captured evidence. Workflow run `32851722987` passed **66 offline tests** and constructed both golden statements with matching epistemic types, exact runtime support edges, and one pinned OpenBot `SourceRevision`. The fresh runtime records correctly remained **`candidate`** even though the golden evaluation targets are `validated` and `reviewed`.

Hard-case evaluation then corrected supersession semantics: one source-level Observation remains bound to one revision, but a later candidate may supersede an earlier observation from another revision of the **same Source**. Cross-source/mixed-revision support inside one Observation remains rejected. The current hard-case readiness matrix is **1 ready / 2 blocked / 1 deferred**.

The first durable GitHub process-state slice was then live-validated against CSD-Foundry. Workflow run `32862376557` passed **75 offline tests** and captured issue #37, merged PR #115, and open/draft PR #117 as immutable current snapshots, emitting **73 metadata facts** and **6 authored assertions**. This closes current `github_issue_pr_evidence`; it does not prove issue close→reopen history or perform temporal frontier reconciliation.

The implementation remains deliberately below autonomous architecture profiling, pattern/insight synthesis, embeddings, autonomous reasoning, and UI. The next measured acquisition boundary is **durable GitHub workflow-run/job/step evidence**, because it is required by both the Resonance-World execution-integrity case and the private-repository Actions pattern.

## Start here

- [`docs/PRODUCT.md`](docs/PRODUCT.md) — authoritative product definition, user, outputs, UX, and action boundary
- [`eval/pilot/M-1-CLOSEOUT.md`](eval/pilot/M-1-CLOSEOUT.md) — M−1 result, evidence, design changes, and exit decision
- [`docs/M0-CONTRACTS.md`](docs/M0-CONTRACTS.md) — minimum contracts selected from actual pilot cases
- [`docs/M0-IMPLEMENTATION.md`](docs/M0-IMPLEMENTATION.md) — rationale for executable M0 contracts and persistence
- [`docs/M0-CAPTURE.md`](docs/M0-CAPTURE.md) — deterministic GitHub capture semantics and trust boundary
- [`docs/M0-EXTRACTION.md`](docs/M0-EXTRACTION.md) — deterministic facts/assertions, provenance, and epistemic boundary
- [`docs/M0-TYPESCRIPT-EVIDENCE.md`](docs/M0-TYPESCRIPT-EVIDENCE.md) — pinned TypeScript parser trust surface and compatibility evidence
- [`docs/M0-OBSERVATIONS.md`](docs/M0-OBSERVATIONS.md) — supported Observation construction, support/provenance rules, and validation-state boundary
- [`docs/M0-OBSERVATION-READINESS.md`](docs/M0-OBSERVATION-READINESS.md) — hard-case readiness, supersession, and semantic-layer boundaries
- [`docs/M0-GITHUB-PROCESS-EVIDENCE.md`](docs/M0-GITHUB-PROCESS-EVIDENCE.md) — durable current issue/PR process snapshots and mutable-state boundary
- [`eval/pilot/coverage/external-v1.yaml`](eval/pilot/coverage/external-v1.yaml) — machine-readable external evidence-recovery checks
- [`eval/pilot/coverage/reports/external-v1.md`](eval/pilot/coverage/reports/external-v1.md) — first live external baseline (4/12)
- [`eval/pilot/coverage/reports/external-v1-markdown-list.md`](eval/pilot/coverage/reports/external-v1-markdown-list.md) — post-P0 baseline (6/12)
- [`eval/pilot/coverage/reports/external-v1-git-tree.md`](eval/pilot/coverage/reports/external-v1-git-tree.md) — post-tree baseline (7/12)
- [`eval/pilot/coverage/reports/external-v1-commit-evidence.md`](eval/pilot/coverage/reports/external-v1-commit-evidence.md) — post-commit baseline (8/12)
- [`eval/pilot/coverage/reports/external-v1-python-ast.md`](eval/pilot/coverage/reports/external-v1-python-ast.md) — post-Python-AST baseline (10/12)
- [`eval/pilot/coverage/reports/external-v1-typescript.md`](eval/pilot/coverage/reports/external-v1-typescript.md) — complete deterministic repository-evidence checkpoint (12/12)
- [`eval/pilot/observation-reports/external-openbot-v1.md`](eval/pilot/observation-reports/external-openbot-v1.md) — first live evidence-supported Observation probe
- [`eval/pilot/observation-readiness-v1.yaml`](eval/pilot/observation-readiness-v1.yaml) — executable hard-case readiness state
- [`eval/pilot/process-reports/csd-issue-pr-v1.md`](eval/pilot/process-reports/csd-issue-pr-v1.md) — live current issue/PR process-evidence checkpoint
- [`docs/M0-NEXT-EXTRACTORS.md`](docs/M0-NEXT-EXTRACTORS.md) — measured repository extractor progression and exit condition
- [`src/lemmamind/contracts.py`](src/lemmamind/contracts.py) — executable versioned M0 contract models
- [`src/lemmamind/storage.py`](src/lemmamind/storage.py) — atomic append-only SQLite contract persistence
- [`src/lemmamind/objects.py`](src/lemmamind/objects.py) — SHA-256 content-addressed captured bytes
- [`src/lemmamind/github.py`](src/lemmamind/github.py) — read-only GitHub repository/file capture path
- [`src/lemmamind/git_tree.py`](src/lemmamind/git_tree.py) — exact Git root-tree capture and deterministic tree facts
- [`src/lemmamind/git_commit.py`](src/lemmamind/git_commit.py) — exact Git commit-metadata capture, metadata facts, and commit-message assertions
- [`src/lemmamind/github_process.py`](src/lemmamind/github_process.py) — current GitHub issue/PR snapshot capture and deterministic process evidence
- [`src/lemmamind/python_ast.py`](src/lemmamind/python_ast.py) — deterministic Python AST facts and docstring assertions
- [`src/lemmamind/typescript_ast.py`](src/lemmamind/typescript_ast.py) — deterministic TypeScript/TSX syntax facts and comment assertions
- [`src/lemmamind/observations.py`](src/lemmamind/observations.py) — v1 candidate Observation construction with validated support provenance
- [`src/lemmamind/observations_v2.py`](src/lemmamind/observations_v2.py) — revision-aware same-source supersession while preserving one-revision Observation support
- [`src/lemmamind/observation_readiness.py`](src/lemmamind/observation_readiness.py) — deterministic hard-case readiness evaluator
- [`src/lemmamind/pilot_observations.py`](src/lemmamind/pilot_observations.py) — golden-driven live OpenBot Observation probe
- [`src/lemmamind/extraction.py`](src/lemmamind/extraction.py) — deterministic artifact extractors and extraction service
- [`src/lemmamind/pilot_coverage.py`](src/lemmamind/pilot_coverage.py) — base evidence-coverage evaluator
- [`src/lemmamind/pilot_coverage_v2.py`](src/lemmamind/pilot_coverage_v2.py) — historical Git-object + Python AST coverage policy
- [`src/lemmamind/pilot_coverage_v3.py`](src/lemmamind/pilot_coverage_v3.py) — TypeScript-aware deterministic coverage policy
- [`tests/`](tests/) — contract, persistence, capture, extraction, observation, process-evidence, coverage, object-integrity, and golden-corpus regression tests
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
GitHub repository/process metadata
      ↓
exact commit + tree analysis anchor
      ↓
content-addressed file / Git-tree / commit / issue / PR artifacts
      ↓
deterministic text / metadata / Python / TypeScript / process evidence
      ↓
EvidenceFact / SourceAssertion
      ↓
12/12 frozen deterministic repository-evidence recovery
      ↓
Observation + ObservationSupport
(manual / golden-driven candidate construction)
      ↓
revision-aware same-source supersession
```

Current process snapshots deliberately stop before issue/PR event history, workflow-run/job/step evidence, temporal frontier reconciliation, action-policy validation, and cross-repository Pattern semantics.

The next measured implementation slice is **durable workflow-run/job/step evidence**. Model-proposed observations remain deferred until the evidence and support-graph invariants survive the hard golden corpus.

## Canonical home

https://github.com/ElephantRock/LemmaMind
