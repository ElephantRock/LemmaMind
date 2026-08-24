# LemmaMind M0 — Minimum System Contracts

## Status

Selected from the completed M−1 manual pilot. This document defines the **minimum contracts justified by observed pilot cases**. It is not a final ontology and does not authorize broad platform construction.

## Why these contracts exist

The M−1 corpus demonstrated that LemmaMind must preserve several distinctions that a repository-summary system would lose:

- technical source identity is not the same as source role;
- a curated research index is not implementation evidence;
- upstream revision and analyzed material must be reproducible;
- observed facts and source assertions are different evidence classes;
- derived observations require explicit support edges and validation state;
- current state can supersede an earlier conclusion without erasing history;
- repository ownership affects operational action but not epistemic validity;
- an action recommendation is separate from the knowledge claim that motivated it;
- agent-runtime authority is multi-dimensional rather than a single tools/sandbox flag;
- every derived object must identify the run/version that produced it.

## Minimal contracts

### 1. Source

Stable identity for anything LemmaMind studies.

Minimum fields:

```text
source_id
source_kind
source_role
canonical_locator
first_seen_at
last_seen_at
```

Initial `source_kind` may be `github_repository`; future kinds can be added without changing the evidence model.

Initial `source_role` should stay deliberately small:

```text
implementation
research_index
research_program
mixed
unknown
```

The OPD external case is the reason `source_role` exists in M0 rather than being deferred.

### 2. RepositoryIdentity

GitHub-specific stable identity attached to a `Source` when the source is a repository.

Minimum fields:

```text
source_id
provider_repository_id
owner
name
default_branch
aliases
archived
```

Use stable provider identity where available so renames/transfers do not create a new conceptual source.

### 3. SourceRevision

Exact upstream state observed.

For GitHub:

```text
source_revision_id
source_id
commit_sha
tree_sha
observed_at
```

A source revision is upstream state, not the local capture itself.

### 4. CaptureManifest

Exact material retained for one analysis generation.

```text
capture_id
source_revision_id
capture_policy_version
captured_at
artifacts[]
```

Each artifact entry binds path/locator, content hash, media type, and retrieval status.

### 5. Artifact

Addressable captured material.

```text
artifact_id
capture_id
source_locator
content_hash
media_type
```

Artifacts are immutable for a given capture.

### 6. EvidenceFact

Deterministically inspectable fact derived from an artifact.

```text
evidence_id
artifact_id
locator
raw_value
normalized_value
extractor_name
extractor_version
```

Only directly inspectable properties belong here.

### 7. SourceAssertion

A claim made by the source, maintainer, documentation, issue, paper index, or other captured material.

```text
assertion_id
artifact_id
locator
statement
extractor_name
extractor_version
```

A SourceAssertion is evidence that the source **said** something; it is not automatically evidence that the claimed property is true.

### 8. Observation

A durable interpretation, inference, hypothesis, or evaluation supported by evidence/assertions.

```text
observation_id
logical_claim_id
epistemic_type
statement
validation_state
reasoning_run_id
created_at
supersedes_observation_id?
```

Support is represented explicitly, not embedded only in prose.

### 9. ObservationSupport

Many-to-many provenance edge between an observation and supporting evidence.

```text
observation_id
support_id
support_type
```

`support_type` initially identifies `EvidenceFact`, `SourceAssertion`, or another reviewed observation when higher-order reasoning is permitted.

### 10. PipelineRun

Generic producer identity for discovery, capture, extraction, diffing, profiling, reasoning, synthesis, or evaluation.

```text
run_id
run_type
code_version
schema_version
policy_version
started_at
finished_at
inputs_hash
outputs_hash
```

Model/prompt identity is added when a run actually uses a model; it is not mandatory for deterministic runs.

### 11. RepositoryRelationship

Operational relationship between the user/system and a repository source.

```text
source_id
relationship_type
can_write
can_contribute
observed_at
```

Initial relationship types:

```text
OWNED
CONTRIBUTABLE
EXTERNAL
READ_ONLY
UNKNOWN
```

This contract must never alter the truth value or support status of evidence/observations.

### 12. ActionRecommendation

Optional operational consequence of an observation or insight.

```text
action_id
subject_id
action_type
target
rationale
repository_modification_required
authorization_required
status
```

Possible action types include learn, investigate, adopt, avoid, mitigate, pin, monitor, report_upstream, contribute_upstream, fork_vendor, revalidate, and no_action.

### 13. ReviewDecision

Human governance and evaluation label.

```text
review_id
subject_id
decision
decided_at
notes
```

Initial decisions may include:

```text
ACCEPT
REJECT
LOW_SIGNAL
DUPLICATE
MERGE
PROMOTE
SNOOZE
DEEP_DIVE
CONTRADICT
```

## Deferred contracts

M−1 does **not** justify implementing these as M0 core entities yet:

- Pattern / PatternOccurrence
- Cohort / prevalence measurement
- ArchitecturalTension
- Insight / KnowledgeItem
- embedding/vector representations
- learned recommendation ranker
- graph database objects
- dynamic execution/sandbox results

They remain roadmap concepts and should be introduced only when the preceding data exists.

## Architecture-profile implication from the external corpus

The OpenBot/OpenClaw/Hermes comparison changes the planned M6 representation. A future agent-runtime profile should not contain a single `sandboxed` or `tools_available` flag. At minimum, candidate dimensions should distinguish:

```text
instruction_source / skill loading
capability_authority
declared tool requirements
execution location
control-plane location
isolation default
isolation scope / backend
elevation or escape paths
process-tree / descendant containment
```

These are **M6 profile fields**, not M0 entities. They are recorded here because M−1 supplied the evidence that they will be needed.

## M0 gate

M0 implementation is complete only when every durable derived record can answer:

1. What source and exact revision did this come from?
2. What exact captured artifact and locator support it?
3. Is it a direct fact, a source assertion, or a derived observation?
4. Which versioned run produced it?
5. Has a later observation superseded it?
6. What repository relationship applies to any proposed action?
7. Can the knowledge remain valid even when no source modification is possible?

No autonomous synthesis is required for M0.
