# Hard-case epistemic readiness

## Status

The frozen hard-case matrix is now representable in the correct semantic layers without weakening source-local provenance.

Source-level `Observation` remains bound to one resolved `SourceRevision`. Revision-aware supersession may cross revisions of the same Source. Cross-repository synthesis is now represented separately by the M8-lite `Pattern / PatternOccurrence` layer.

The machine-readable readiness contract is `eval/pilot/observation-readiness-v1.yaml` and is evaluated by `lemmamind.observation_readiness`.

## Source-local boundary

```text
EvidenceFact / SourceAssertion
          ↓
ObservationSupport
          ↓
Observation
(one resolved SourceRevision)
```

A later Observation may supersede an earlier Observation from another revision of the same Source when the logical claim identity is unchanged. Prior records remain immutable.

## Cross-source boundary

```text
Pattern
   ↓
PatternOccurrence
   ↓
source-local Observation
   ↓
exact evidence provenance
```

Pattern construction does not turn multiple Sources into one Observation. Each occurrence declares one `SourceRevision`, and its supporting Observations must resolve exactly to that revision.

The M8-lite constructor also prevents pseudo-replication by counting each Source once and supports explicit `negative_control` occurrences.

## Hard-case readiness result

| Case | Outcome | Executable boundary |
| --- | --- | --- |
| `external-opd-source-type` | **ready** | Source-role and deterministic evidence boundaries. |
| `csd-foundry-frontier` | **ready** | Current process state, provider event history, exact PR revision relation, and immutable temporal belief revision. |
| `resonance-world-confirmatory` | **ready** | Workflow evidence plus evidence-bound action policy preserving no-rerun, classifier, and independent-authority constraints. |
| `private-actions-pattern` | **ready** | Two private supporting occurrences plus two healthy public negative controls above source-local Observations. |

Summary: **4 ready / 0 blocked / 0 deferred**.

## Private Actions Pattern

The frozen topology is:

```text
ExpertOS                private  supporting
ExpertForge             private  supporting
ERLab                   public   negative_control
Resonance-ContextGraph  public   negative_control
```

Current provider signatures were rechecked through the authorized GitHub connection. The private runs still exhibit the pre-step/zero-step failure signatures, while the public controls show normal successful step execution.

The resulting candidate inference remains deliberately weaker than confirmation:

> A shared private-repository Actions provisioning, entitlement, or billing hypothesis is better supported than two independent code-test failures.

No account-level evidence confirms that cause. Pattern construction therefore remains `candidate` and does not convert the hypothesis into fact.

See `docs/M8-PATTERN-INTELLIGENCE-LITE.md` and `eval/pilot/pattern-reports/private-actions-v1.md`.

## What this readiness result does not mean

`4/4 ready` means the selected hard golden cases can now be represented correctly. It does **not** mean the roadmap is complete.

Still missing or intentionally partial are:

- formal M1 discovery lineage;
- mature M2 repository-registry evolution and tracking levels;
- general M5 ArtifactDelta / StructuralDelta machinery;
- M6 ArchitectureProfile and triage;
- M6.5 representation/embeddings;
- autonomous/model-generated M7 observations;
- the real M7.5 attention-budgeted review queue;
- full M8 automatic discovery, Cohort/prevalence, and ArchitecturalTension;
- M9 Insight/Knowledge promotion;
- M10 intelligence interface.

After this M8-lite proof, implementation should return to the missing V1 foundation rather than advancing directly into M9.
