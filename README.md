# LemmaMind

**LemmaMind** is a personal technical-intelligence system for turning reproducible technical evidence into reviewed, decision-relevant knowledge.

GitHub is the first source ecosystem, not the boundary of the project. LemmaMind studies high-value technical sources, preserves the exact evidence used for analysis, separates observed facts from inference, detects meaningful changes, and progressively synthesizes cross-source patterns, tensions, insights, and reviewed knowledge.

Repository repair is not a core requirement. LemmaMind's mandatory job is to understand and substantiate; operational action is optional and depends on ownership, authority, risk, and user intent.

## Governing principle

> Useful evidence first. Evidence-bound inference second. Reviewed knowledge third. Real decisions are the measure of success.

## Current phase

**M−1 — Manual Intelligence Pilot: PASS.**

The completed pilot contains a controlled ElephantRock corpus plus four real external read-only repositories. It demonstrates useful single-source observations, cross-repository reasoning, negative intelligence, belief revision, correct no-action behavior, source-role classification, and decision-relevant intelligence without requiring source modification.

**V1 foundation — M1 Curated Discovery and the V1 M2 Repository Registry core are implemented, including canonical identity/evolution and governed tracking-level history/policy.**

The executable foundation includes strict versioned contracts, append-only SQLite persistence, formal `DiscoveryChannel → DiscoveryRun → DiscoveryHit` lineage, stable GitHub provider-ID repository resolution, immutable repository-locator history, immutable governed repository tracking assignments, latest-effective tracking policy, tracking-aware capture/reasoning gates, registry-aware capture, a SHA-256 content-addressed artifact store, deterministic read-only GitHub file capture, exact Git root-tree capture, durable Git commit metadata, deterministic artifact extraction, Python AST structural evidence, TypeScript/TSX syntax and comment evidence, explicit candidate `Observation` construction with typed support edges, revision-aware same-source supersession, durable current GitHub issue/pull-request snapshots, durable issue-event history, workflow-run/job/step evidence, repository-metadata visibility evidence, evidence-bound action-policy evaluation, temporal frontier reconciliation, and a narrow M8-lite cross-repository Pattern layer.

M1 records raw discovery provenance without requiring identity to exist in advance. A `DiscoveryHit` may remain unresolved (`source_id=null`) until M2 resolves it; the historical hit is never rewritten merely because identity becomes known later. The frozen 13-repository manual watchlist is covered in unresolved, partially resolved, and fully resolved states.

The first M2 registry slice uses GitHub's provider repository ID as the stable identity anchor. Owner/name, canonical URL, default branch, archive state, fork state, and optional fork-parent provider ID are append-only `RepositoryLocator` observations. A rename, transfer, or default-branch/archive change therefore creates a later locator for the same Source instead of mutating the original discovery hit or seed identity. Registry-aware capture accepts mutable repository-state evolution only when the latest validated M2 locator matches the incoming provider state.

The M2 tracking slice records immutable `RepositoryTrackingAssignment` history over the roadmap's levels `0 — Ignore` through `5 — Continuous`. An unassigned Source fails closed operationally as level `0` without fabricating a persisted assignment. V1 accepts only immediately effective new assignments; future scheduling and backdating are deferred until explicit cancellation/correction semantics exist. Tracking level controls operational eligibility, not truth or authorization: metadata requires level `1+`, explicit files and commit metadata `2+`, root-tree structure and source-local reasoning `3+`, and process/history/workflow evidence `4+`; level `5` adds continuous-monitoring eligibility without inventing a fixed scheduler cadence.

The first M8-lite vertical slice adds `Pattern`, `PatternOccurrence`, and `PatternOccurrenceSupport` above source-local Observations. It supports explicit supporting cases, negative controls, and contradicting occurrences; prevents repeated revisions of one Source from becoming pseudo-replication; and always constructs a candidate `SYNTHESIS` result rather than self-validating a cross-source claim.

The evidence layer preserves artifact path facts, selected `pyproject.toml` / `package.json` facts, ordinary Markdown prose, Markdown list items, exact Git root-tree structure, exact commit metadata, Python syntax, TypeScript/TSX syntax, current GitHub repository/issue/PR process metadata, GitHub issue event metadata, GitHub Actions run/job/step metadata, and opt-in scalar JSON Pointer facts for explicitly governed JSON artifacts. Authored prose, commit messages, Python docstrings, TypeScript comments, and issue/PR titles/bodies remain `SourceAssertion`; Git object structure, provider/process/event metadata, workflow metadata, JSON scalar values, repository visibility, and parser-derived syntax remain `EvidenceFact`.

Live external repository evidence coverage progressed against the same 12 frozen requirements:

- initial baseline: **4/12 (33.3%)**
- after Markdown list extraction: **6/12 (50.0%)**
- after exact Git root-tree evidence: **7/12 (58.3%)**
- after durable Git commit evidence: **8/12 (66.7%)**
- after Python AST structural evidence: **10/12 (83.3%)**
- after TypeScript comments + structural evidence: **12/12 (100.0%)**

OpenBot, OpenClaw, Hermes, and the OPD research-index case are all 3/3 at the deterministic repository evidence-recovery layer. Historical reports are preserved rather than overwritten.

The first live `Evidence → ObservationSupport → Observation` probe replayed the two frozen OpenBot golden observations against freshly captured evidence. Workflow run `32851722987` passed **66 offline tests** and constructed both golden statements with matching epistemic types, exact runtime support edges, and one pinned OpenBot `SourceRevision`. Fresh runtime records correctly remained **`candidate`** even though the golden evaluation targets are `validated` and `reviewed`.

Hard-case evaluation corrected supersession semantics: one source-level Observation remains bound to one revision, but a later candidate may supersede an earlier observation from another revision of the **same Source**. Cross-source/mixed-revision support inside one Observation remains rejected.

The first durable GitHub process-state slice was live-validated against CSD-Foundry. Workflow run `32862376557` passed **75 offline tests** and captured issue #37, merged PR #115, and open/draft PR #117 as immutable current snapshots, emitting **73 metadata facts** and **6 authored assertions**.

Durable GitHub Actions evidence was live-validated against frozen Resonance-World workflow run `31895957256`. LemmaMind run `32864264454` passed **79 offline tests** and recovered **139 deterministic workflow facts**, including the cancelled provider step, skipped upload step, two zero-step dependent jobs, zero artifacts, and safe job-log availability without reading log contents. Workflow status remains evidence rather than a causal diagnosis or rerun decision.

Action-policy validation then used the same frozen Resonance-World source context plus the request plan's `confirmatory_rerun_allowed=false` and PR #177's explicit classifier/Acceptance-plane boundaries. Live run `32865837892` passed **92 offline tests** and demonstrated that `OWNED + can_write=true` does not override governance: rerun was rejected, provider self-classification rejected, separate evaluator classification recommendable, promotion left recommendation-only with independent authorization required, and preservation recommendable. No policy output was authorized.

GitHub process event history was then live-validated against CSD issue #37. Run `32869669389` passed **97 offline tests**, recovered **9 provider events / 54 deterministic event facts**, and directly observed the `closed` event at `2026-08-24T21:31:54Z` followed by `reopened` at `2026-08-24T21:36:12Z`.

Temporal frontier reconciliation completed the CSD belief-revision path. Live run `32870568177` passed **101 offline tests**, verified that open/draft PR #117 is based on D5 merge revision `aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7` with head `2d910f3ff83f061409ca9d8f2e3709fde7c13f6e`, preserved the prior “#37 can close” Observation unchanged, and created a candidate superseding Evaluation that narrows the conclusion to implementation landed while qualification/closure remains open. The runtime did not self-promote either new candidate to reviewed/validated state.

The private-Actions provider signature was rechecked across ExpertOS, ExpertForge, ERLab, and Resonance-ContextGraph. The two private repositories retain the frozen pre-step/zero-step failure signatures, while the two public controls retain normal successful step execution. M8-lite represents those as two supporting `PatternOccurrence` records plus two negative controls. The shared private-repository provisioning/entitlement/billing explanation remains a **candidate inference**, not a confirmed account-level cause.

The hard-case readiness matrix is now **4 ready / 0 blocked / 0 deferred**:

- OPD source-role case: ready;
- Resonance-World confirmatory case: ready;
- CSD-Foundry frontier/belief-revision case: ready;
- private-Actions cross-repository Pattern case: ready in the M8-lite Pattern layer.

This means the four selected hard golden cases are representable in their correct semantic layers. It does **not** mean the roadmap or full M8 is complete.

M2 identity/evolution validation is deliberately non-destructive. `ElephantRock/LemmaMind` currently resolves to GitHub provider repository ID `1345295505`, owner/name `ElephantRock/LemmaMind`, default branch `main`, `archived=false`, and `fork=false`. Rename/transfer/default-branch/archive evolution is tested deterministically rather than by mutating a real repository solely for demonstration. The corrected identity/evolution suite reached **131 passed** after a regression test exposed and closed a stale-locator capture-authorization hole.

M2 tracking-policy validation is also deterministic and non-destructive; no production tracking assignment was fabricated merely to demonstrate the feature. The first policy implementation passed **147 tests**. Review exposed a future-scheduling ambiguity, so V1 was narrowed to immediate-only new assignments and reached **148 passed**. A final audit then gated the remaining current capture entry points—repository metadata, commit metadata, root-tree capture, and workflow runs—and permanent PR workflow run `32912533399` reached **152 passed**.

The implementation remains deliberately below scheduler cadence/budget policy, pre-revision metadata scheduling, authenticated tracking-policy writers, provider-independent registry adapters, an explicit M3 Revision Capture gate closeout, general M5 delta machinery, M6 ArchitectureProfile/triage, M6.5 embeddings/representation, autonomous model-generated reasoning, the real M7.5 attention-budgeted review queue, full M8 automatic pattern discovery/cohorts/tensions, M9 Insight/Knowledge promotion, action execution, authorization issuance, and UI.

The next roadmap move is **M3 Revision Capture reconciliation**: audit the already-existing `SourceRevision`, `CaptureManifest`, content-addressed artifact, Git tree, and Git commit machinery against the formal M3 gate; preserve what already satisfies it and implement only missing reconstruction/materiality capabilities rather than duplicating the M0 work.

## Start here

- [`docs/PRODUCT.md`](docs/PRODUCT.md) — authoritative product definition, user, outputs, UX, and action boundary
- [`eval/pilot/M-1-CLOSEOUT.md`](eval/pilot/M-1-CLOSEOUT.md) — M−1 result, evidence, design changes, and exit decision
- [`docs/M0-CONTRACTS.md`](docs/M0-CONTRACTS.md) — minimum contracts selected from actual pilot cases
- [`docs/M0-IMPLEMENTATION.md`](docs/M0-IMPLEMENTATION.md) — rationale for executable M0 contracts and persistence
- [`docs/M1-DISCOVERY.md`](docs/M1-DISCOVERY.md) — formal curated-discovery lineage and M1/M2 boundary
- [`docs/M2-REPOSITORY-REGISTRY.md`](docs/M2-REPOSITORY-REGISTRY.md) — stable provider identity, locator evolution, governed tracking history, and tracking-aware policy gates
- [`docs/M0-CAPTURE.md`](docs/M0-CAPTURE.md) — deterministic GitHub capture semantics and trust boundary
- [`docs/M0-EXTRACTION.md`](docs/M0-EXTRACTION.md) — deterministic facts/assertions, provenance, and epistemic boundary
- [`docs/M0-TYPESCRIPT-EVIDENCE.md`](docs/M0-TYPESCRIPT-EVIDENCE.md) — pinned TypeScript parser trust surface and compatibility evidence
- [`docs/M0-OBSERVATIONS.md`](docs/M0-OBSERVATIONS.md) — supported Observation construction, support/provenance rules, and validation-state boundary
- [`docs/M0-OBSERVATION-READINESS.md`](docs/M0-OBSERVATION-READINESS.md) — executable hard-case readiness and semantic-layer boundaries
- [`docs/M0-GITHUB-PROCESS-EVIDENCE.md`](docs/M0-GITHUB-PROCESS-EVIDENCE.md) — durable current issue/PR process snapshots
- [`docs/M0-GITHUB-PROCESS-EVENTS.md`](docs/M0-GITHUB-PROCESS-EVENTS.md) — durable provider issue-event history and close/reopen boundary
- [`docs/M0-GITHUB-WORKFLOW-EVIDENCE.md`](docs/M0-GITHUB-WORKFLOW-EVIDENCE.md) — durable workflow-run/job/step evidence and safe log-availability boundary
- [`docs/M0-ACTION-POLICY.md`](docs/M0-ACTION-POLICY.md) — evidence-bound operational policy and authorization separation
- [`docs/M0-TEMPORAL-RECONCILIATION.md`](docs/M0-TEMPORAL-RECONCILIATION.md) — source-local temporal frontier reconciliation and immutable belief revision
- [`docs/M8-PATTERN-INTELLIGENCE-LITE.md`](docs/M8-PATTERN-INTELLIGENCE-LITE.md) — first cross-repository Pattern/negative-control boundary
- [`eval/pilot/discovery-reports/manual-watchlist-v1.md`](eval/pilot/discovery-reports/manual-watchlist-v1.md) — frozen 13-entry M1 manual-watchlist checkpoint
- [`eval/pilot/registry-reports/lemmamind-provider-identity-v1.md`](eval/pilot/registry-reports/lemmamind-provider-identity-v1.md) — M2 live provider-ID checkpoint and evolution boundary
- [`eval/pilot/registry-reports/tracking-level-policy-v1.md`](eval/pilot/registry-reports/tracking-level-policy-v1.md) — M2 governed tracking-policy checkpoint and effective-time correction
- [`eval/pilot/coverage/external-v1.yaml`](eval/pilot/coverage/external-v1.yaml) — machine-readable external evidence-recovery checks
- [`eval/pilot/coverage/reports/external-v1-typescript.md`](eval/pilot/coverage/reports/external-v1-typescript.md) — complete deterministic repository-evidence checkpoint (12/12)
- [`eval/pilot/observation-reports/external-openbot-v1.md`](eval/pilot/observation-reports/external-openbot-v1.md) — first live evidence-supported Observation probe
- [`eval/pilot/observation-readiness-v1.yaml`](eval/pilot/observation-readiness-v1.yaml) — executable hard-case readiness state
- [`eval/pilot/process-reports/csd-issue-pr-v1.md`](eval/pilot/process-reports/csd-issue-pr-v1.md) — live current issue/PR process-evidence checkpoint
- [`eval/pilot/process-event-reports/csd-issue-37-events-v1.md`](eval/pilot/process-event-reports/csd-issue-37-events-v1.md) — live issue event-history checkpoint
- [`eval/pilot/workflow-reports/resonance-world-confirmatory-v1.md`](eval/pilot/workflow-reports/resonance-world-confirmatory-v1.md) — live workflow evidence checkpoint
- [`eval/pilot/action-policy-reports/resonance-world-confirmatory-v1.md`](eval/pilot/action-policy-reports/resonance-world-confirmatory-v1.md) — live operational policy checkpoint
- [`eval/pilot/temporal-reports/csd-frontier-reconciliation-v1.md`](eval/pilot/temporal-reports/csd-frontier-reconciliation-v1.md) — live temporal belief-revision checkpoint
- [`eval/pilot/pattern-reports/private-actions-v1.md`](eval/pilot/pattern-reports/private-actions-v1.md) — first cross-repository Pattern checkpoint
- [`src/lemmamind/contracts.py`](src/lemmamind/contracts.py) — executable versioned contracts
- [`src/lemmamind/discovery.py`](src/lemmamind/discovery.py) — generic M1 discovery lineage service
- [`src/lemmamind/manual_watchlist.py`](src/lemmamind/manual_watchlist.py) — manual-watchlist M1 adapter
- [`src/lemmamind/repository_registry.py`](src/lemmamind/repository_registry.py) — M2 GitHub provider-ID resolution and locator history
- [`src/lemmamind/registry_aware_capture.py`](src/lemmamind/registry_aware_capture.py) — capture path requiring latest validated M2 locator once registry history exists
- [`src/lemmamind/tracking_contracts.py`](src/lemmamind/tracking_contracts.py) — immutable M2 tracking-level assignment contract
- [`src/lemmamind/tracking.py`](src/lemmamind/tracking.py) — latest-effective tracking history and deterministic level policy
- [`src/lemmamind/tracking_adapters.py`](src/lemmamind/tracking_adapters.py) — tracking-aware capture/process/workflow/reasoning gates
- [`src/lemmamind/storage.py`](src/lemmamind/storage.py) — atomic append-only SQLite contract persistence
- [`src/lemmamind/objects.py`](src/lemmamind/objects.py) — SHA-256 content-addressed captured bytes
- [`src/lemmamind/github.py`](src/lemmamind/github.py) — read-only GitHub repository/file capture path
- [`src/lemmamind/git_tree.py`](src/lemmamind/git_tree.py) — exact Git root-tree capture and deterministic tree facts
- [`src/lemmamind/git_commit.py`](src/lemmamind/git_commit.py) — exact Git commit metadata and message assertions
- [`src/lemmamind/github_repository_metadata.py`](src/lemmamind/github_repository_metadata.py) — content-addressed mutable repository metadata such as visibility
- [`src/lemmamind/github_process.py`](src/lemmamind/github_process.py) — current GitHub issue/PR snapshot capture and deterministic process evidence
- [`src/lemmamind/github_process_events.py`](src/lemmamind/github_process_events.py) — paginated durable GitHub issue-event history evidence
- [`src/lemmamind/github_workflow.py`](src/lemmamind/github_workflow.py) — workflow-run/job/step snapshot capture and deterministic evidence
- [`src/lemmamind/github_workflow_http.py`](src/lemmamind/github_workflow_http.py) — no-redirect job-log availability transport
- [`src/lemmamind/json_evidence.py`](src/lemmamind/json_evidence.py) — opt-in deterministic JSON Pointer scalar facts
- [`src/lemmamind/action_policy.py`](src/lemmamind/action_policy.py) — evidence-bound action-policy validation without execution/authorization
- [`src/lemmamind/temporal_reconciliation.py`](src/lemmamind/temporal_reconciliation.py) — source-local temporal reconciliation and superseding candidate construction
- [`src/lemmamind/python_ast.py`](src/lemmamind/python_ast.py) — deterministic Python AST facts and docstring assertions
- [`src/lemmamind/typescript_ast.py`](src/lemmamind/typescript_ast.py) — deterministic TypeScript/TSX syntax facts and comment assertions
- [`src/lemmamind/observations.py`](src/lemmamind/observations.py) — candidate Observation construction with validated support provenance
- [`src/lemmamind/observations_v2.py`](src/lemmamind/observations_v2.py) — revision-aware same-source supersession while preserving one-revision Observation support
- [`src/lemmamind/pattern_intelligence.py`](src/lemmamind/pattern_intelligence.py) — candidate cross-source Pattern construction over source-local Observations
- [`src/lemmamind/observation_readiness.py`](src/lemmamind/observation_readiness.py) — deterministic hard-case readiness evaluator
- [`tests/`](tests/) — contract, persistence, discovery, registry/tracking, capture, extraction, observation, process/event/workflow/policy/temporal/pattern, coverage, object-integrity, and golden-corpus regression tests
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — comprehensive project roadmap
- [`docs/PILOT.md`](docs/PILOT.md) — M−1 protocol and completed corpus
- [`pilot/watchlist.yaml`](pilot/watchlist.yaml) — pinned internal + external validation corpus
- [`eval/pilot/`](eval/pilot/) — golden intelligence cases and evaluation contract

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

## Current executable vertical path

```text
DiscoveryChannel
      ↓
DiscoveryRun
      ↓
DiscoveryHit
      ↓
DiscoveryResolution
      ↓
stable Source + latest RepositoryLocator
      ↓
latest effective RepositoryTrackingAssignment / TrackingPolicy
      ↓
tracking-aware registry capture
      ↓
exact commit + tree analysis anchor
      ↓
content-addressed artifacts
      ↓
deterministic EvidenceFact / SourceAssertion
      ↓
revision-bound Observation + ObservationSupport
      ↓
same-Source revision-aware supersession
      ↓
Temporal frontier reconciliation
      ↓
PatternOccurrence across distinct Sources
      ↓
candidate cross-repository Pattern
```

Operational reasoning remains separate:

```text
RepositoryRelationship + evidence-bound governance
      ↓
Action-policy evaluation
(reject / recommend / require authorization; never authorize)
```

The next implementation priority is **M3 Revision Capture reconciliation**. Model-proposed observations, broad automatic Pattern discovery, knowledge promotion, and action execution remain deferred.

## Canonical home

https://github.com/ElephantRock/LemmaMind