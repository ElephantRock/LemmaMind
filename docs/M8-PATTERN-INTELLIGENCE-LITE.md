# M8-lite — Pattern Intelligence

## Purpose

This slice introduces the smallest cross-repository semantic layer justified by the frozen `private-actions-pattern` case.

It does **not** broaden `Observation`. A source-level Observation remains revision-bound. Cross-source synthesis begins only at `Pattern`.

## Durable path

```text
Pattern
   ↓
PatternOccurrence
   ↓
PatternOccurrenceSupport
   ↓
source-local Observation
   ↓
ObservationSupport
   ↓
EvidenceFact / SourceAssertion
   ↓
Artifact
   ↓
SourceRevision
```

## Contracts

The additive contracts are:

- `Pattern`
- `PatternOccurrence`
- `PatternOccurrenceSupport`
- `PatternOccurrenceRole`

Occurrence roles are:

- `supporting`
- `negative_control`
- `contradicting`

`Pattern` remains a derived candidate with an epistemic type and validation state. Construction produces a `SYNTHESIS` `PipelineRun`.

## Construction policy

`PatternConstructionService` is proposal-driven. It does not discover clusters or generate claims. The caller supplies the candidate statement and source-local occurrence proposals.

The service validates:

1. at least two distinct supporting Sources for a cross-repository Pattern;
2. any configured minimum number of negative-control Sources;
3. each Source counts once, preventing repeated revisions from becoming pseudo-replication;
4. each occurrence points to one exact `SourceRevision`;
5. every supporting Observation resolves exactly to that occurrence revision;
6. rejected Observations cannot support an occurrence;
7. support runs and artifact provenance are complete.

The resulting Pattern is always `candidate` in this slice. Construction does not review, validate, promote, authorize, or execute anything.

## Repository visibility evidence

The private-Actions case also requires observed repository visibility. `github_repository_metadata.py` therefore adds a content-addressed repository-metadata snapshot and deterministic facts such as:

```text
$github/repository#/visibility
$github/repository#/private
$github/repository#/full_name
```

Repository metadata is mutable provider state. `SourceRevision` is the analysis-generation anchor, not a claim that visibility is historical state at that Git commit.

## Frozen private-Actions topology

The golden case uses:

```text
ExpertOS                  private  supporting
ExpertForge               private  supporting
ERLab                     public   negative_control
Resonance-ContextGraph    public   negative_control
```

The supporting signature is a GitHub Actions failure before useful job-step execution. The negative controls are public repositories in the same portfolio whose frozen runs executed normal workflow steps successfully.

The cross-repository explanation remains an inference/hypothesis, not a fact:

> a shared private-repository Actions provisioning, entitlement, or billing problem is better supported than two independent code-test failures.

No account-level evidence has confirmed that explanation, so Pattern construction must not promote it beyond candidate inference strength.

## Credential boundary

The reusable product code is network-independent under normal CI. LemmaMind's repository-scoped `GITHUB_TOKEN` is not assumed to have read authority over sibling private repositories. Cross-repository credentials are not broadened merely to make a live demonstration run.

The frozen provider signatures are rechecked through the authorized GitHub connection, while the durable Pattern/provenance implementation is exercised in offline CI fixtures.

## Explicitly deferred

This M8-lite slice does not implement:

- automatic cluster discovery;
- embeddings or nearest-neighbor search;
- `Cohort` or prevalence denominators;
- Rare/Emerging/Growing/Established/Declining labels;
- `ArchitecturalTension`;
- autonomous Pattern generation;
- human review queue behavior;
- Insight or Knowledge promotion.

Those remain subject to their roadmap gates.
