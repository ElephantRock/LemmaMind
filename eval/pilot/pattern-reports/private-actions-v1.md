# Private Actions cross-repository Pattern checkpoint

## Case

`private-actions-pattern`

This checkpoint exercises the first M8-lite cross-repository Pattern boundary without relaxing source-local Observation provenance.

## Provider signature recheck

The frozen repositories and workflow runs were rechecked through the authorized GitHub connection on 2026-08-25.

| Repository | Visibility | Frozen run | Role | Rechecked signature |
| --- | --- | ---: | --- | --- |
| `ElephantRock/ExpertOS` | private | `32779830513` | supporting | Four jobs remain `failure` with no recorded job steps; a failed-job log probe returned unavailable/missing rather than test output. |
| `ElephantRock/ExpertForge` | private | `32778642199` | supporting | First job remains `failure` with no recorded steps; downstream jobs remain `skipped`. |
| `ElephantRock/ERLab` | public | `32334661409` | negative control | Workflow jobs remain successful and contain normal checkout/setup/install/test/lint/build steps. |
| `ElephantRock/Resonance-ContextGraph` | public | `32780247570` | negative control | Workflow job remains successful and contains normal checkout/setup/install/architecture/ruff/pytest steps. |

The comparison still supports the original portfolio-level hypothesis more strongly than treating the two private failures as independent code-test failures. It does **not** confirm billing, entitlement, runner provisioning, or any other account-level cause.

## Runtime representation

Each repository is represented first as one source-local candidate Observation supported by its own repository-visibility and workflow evidence. Those Observations remain revision-bound.

The cross-source layer then constructs four `PatternOccurrence` records:

```text
ExpertOS                supporting
ExpertForge             supporting
ERLab                   negative_control
Resonance-ContextGraph  negative_control
```

Two candidate Patterns are replayed from the golden case:

### Inference

> The matched pre-step failure signature across two private repositories, contrasted with functioning public-repository Actions, supports a shared private-repository Actions provisioning, entitlement, or billing hypothesis more strongly than two independent code-test failures.

### Evaluation

> The affected PRs should be described as CI not executed rather than code tests failed until runner/provisioning state is resolved.

Both remain `candidate`. The golden corpus may contain reviewed/validated targets, but construction itself does not self-ratify them.

## Provenance invariant

```text
Pattern
  → PatternOccurrence
    → source-local Observation
      → exact EvidenceFact / SourceAssertion
        → Artifact
          → SourceRevision
```

A PatternOccurrence is rejected if its Observation resolves to a different revision than the occurrence declares. Repeated revisions of one Source cannot be counted as independent supporting cases.

## Credential boundary

Normal LemmaMind CI remains network-independent. The repository-scoped `GITHUB_TOKEN` is not assumed to have authority to read sibling private repositories, and this validation did not broaden credentials merely to run an integration demo.

Provider state was rechecked through the authorized GitHub connection; the reusable contracts, metadata-evidence path, occurrence provenance, negative-control counting, pseudo-replication guard, and candidate Pattern construction are exercised by the offline test suite.

## Readiness effect

`cross_repository_pattern_layer` moves from `deferred` to `implemented` for the frozen hard-case matrix.

The measured hard-case state becomes:

```text
4 ready / 0 blocked / 0 deferred
```

This closes **representability of the four selected hard golden cases**. It does not mean full M8 is complete. Automatic pattern discovery, cohorts/prevalence, architectural tensions, representation/embeddings, human review, and knowledge promotion remain later roadmap work.
