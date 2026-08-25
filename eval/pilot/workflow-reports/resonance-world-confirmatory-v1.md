# Resonance-World confirmatory workflow evidence checkpoint

## Scope

This checkpoint records the first successful live use of LemmaMind's durable GitHub Actions run/job/step evidence path against the frozen Resonance-World confirmatory case.

It is an evidence checkpoint, not an experiment conclusion or rerun authorization.

## Source

- repository: `ElephantRock/Resonance-World`
- analysis anchor commit: `65d739736070bbebe7941bebfbee785d33499c46`
- workflow path: `.github/workflows/d2-confirmatory.yml`
- GitHub workflow run: `31895957256`
- live LemmaMind validation run: `32864264454`

## Live result

The validation run passed the offline suite and then captured/extracted the real frozen workflow run.

Recovered deterministic facts included:

```text
workflow run
  conclusion = cancelled
  job_count = 3
  artifact_count = 0

provider-confirmatory-campaign
  conclusion = cancelled
  step_count = 11
  job log = available

step 6
  name = Execute frozen provider campaign
  conclusion = cancelled
  started_at = 2026-08-15T16:36:24Z
  completed_at = 2026-08-15T21:36:25Z

step 8
  conclusion = skipped

registry-promotion-disabled
  conclusion = skipped
  step_count = 0

frozen-output-evaluator
  conclusion = skipped
  step_count = 0
```

The deterministic report projection from step timestamps is `18001` seconds. That duration is not stored as a causal interpretation.

Total emitted metadata facts: **139**.

## Log-security boundary

The GitHub job-log endpoint redirects to a signed blob URL when logs exist. The accepted live path uses `SafeGitHubWorkflowRESTReader`, which refuses to follow that redirect and records only:

- availability;
- HTTP status;
- whether GitHub issued a redirect.

Authorization is never forwarded to the blob host and log bytes are not retained or parsed.

An earlier live attempt followed the redirect and received HTTP 401. That failure is preserved in Actions history; the corrected no-redirect run succeeded.

## Epistemic boundary

This evidence supports statements such as:

- the workflow run concluded `cancelled`;
- the provider execution step concluded `cancelled`;
- the upload step was skipped;
- no workflow artifacts were present in the captured run metadata;
- downstream jobs had zero recorded steps.

It does **not** by itself establish:

- why the provider step was cancelled;
- that the configured timeout caused the cancellation;
- whether a rerun is scientifically permitted;
- whether any mechanism claim should be accepted or rejected.

Those conclusions require later Observation and action/governance layers.

## Readiness effect

This checkpoint moves:

```text
github_workflow_run_evidence
```

from `missing` to `implemented` in the hard-case readiness matrix.

The Resonance-World case remains blocked only on authority/governance-aware action-policy validation. The private-Actions case remains deferred to the cross-repository Pattern layer rather than blocked on workflow evidence acquisition.
