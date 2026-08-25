# M0 — Durable GitHub workflow-run evidence

## Status

**Implemented and live-validated for workflow run/job/step snapshots.**

This slice adds read-only, content-addressed evidence for selected GitHub Actions workflow runs. It preserves provider run metadata, jobs, steps, artifact metadata, and job-log availability without retaining or interpreting log contents.

## Why workflow state is its own evidence surface

A red GitHub Actions badge does not identify the failure class. Useful distinctions include:

```text
run conclusion
job conclusion
step count
step conclusions
runner assignment
artifact count
job-log availability
```

These are process facts, not code-test conclusions.

The private-Actions golden case depends on exactly this distinction: `failure + zero steps + missing logs` must not be represented as `tests failed`.

## Capture model

The workflow capture is anchored to a persisted `SourceRevision` whose commit SHA must equal the workflow run's explicit `head_sha`:

```text
SourceRevision
    ↓
workflow run head_sha check
    ↓
immutable workflow snapshot artifact
    ↓
EvidenceFact
```

The canonical snapshot contains:

- run identity, path, event, status/conclusion, attempt, head SHA, timestamps, and linked PR numbers;
- complete job list for the captured page contract;
- each job's status/conclusion, runner metadata, step count, and ordered steps;
- each step's number, name, status/conclusion, and timestamps;
- workflow artifact metadata and count;
- job-log availability metadata only.

The capture fails closed if job or artifact pagination indicates an incomplete snapshot.

## Log-security boundary

GitHub's job-log endpoint may redirect to a signed blob URL. LemmaMind does not need log bytes for the v1 evidence contract.

`SafeGitHubWorkflowRESTReader` therefore:

1. sends the authenticated request only to GitHub;
2. refuses redirects;
3. interprets GitHub's redirect response as `available`;
4. records 404 as `missing`;
5. treats other HTTP failures as hard API errors;
6. never forwards authorization to the signed blob host;
7. never stores or parses log contents.

A live attempt using the default redirect-following transport received HTTP 401 after the signed redirect. The corrected no-redirect reader passed live validation. This failure remains useful trust-surface evidence.

## Evidence locators

Examples:

```text
$github/actions/run/31895957256#/run/conclusion
$github/actions/run/31895957256#/artifact_count
$github/actions/run/31895957256#/jobs/95039193643/conclusion
$github/actions/run/31895957256#/jobs/95039193643/step_count
$github/actions/run/31895957256#/jobs/95039193643/log/availability
$github/actions/run/31895957256#/jobs/95039193643/steps/6/name
$github/actions/run/31895957256#/jobs/95039193643/steps/6/conclusion
```

All emitted workflow records are `EvidenceFact`. No workflow status string is converted into an interpretation such as “code failed,” “timeout caused cancellation,” or “rerun allowed.”

## Live Resonance-World validation

Live LemmaMind workflow run `32864264454` validated the path against frozen Resonance-World workflow run `31895957256`.

The live checkpoint recovered:

- run conclusion `cancelled`;
- three jobs;
- zero workflow artifacts;
- provider job conclusion `cancelled`;
- provider execution step conclusion `cancelled`;
- execution step timestamps spanning 18,001 seconds;
- upload-artifact step conclusion `skipped`;
- two dependent jobs with zero steps;
- provider job log availability without reading log bytes.

The extraction emitted **139 deterministic metadata facts**.

Stable report: `eval/pilot/workflow-reports/resonance-world-confirmatory-v1.{json,md}`.

## What this closes

The hard-case capability:

```text
github_workflow_run_evidence
```

moves from `missing` to `implemented`.

This changes the readiness matrix in two ways:

- Resonance-World is now blocked only on `action_policy_validation`;
- private Actions is no longer blocked on acquisition and remains deliberately deferred to `cross_repository_pattern_layer`.

## What remains outside this layer

Workflow evidence does not determine:

- causal explanation for a failure/cancellation;
- whether a retry/rerun is allowed;
- whether separate acceptance/governance authority is satisfied;
- whether matched signatures across repositories support a Pattern.

Those belong to later Observation, action-policy, and Pattern semantics.

## Next measured capability

The next decision-relevant slice should be **authority/governance-aware action-policy validation**, because workflow + issue/PR evidence now make the Resonance-World source-local state representable while the scientifically important `do not rerun` decision remains intentionally unvalidated.
