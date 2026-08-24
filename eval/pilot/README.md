# LemmaMind M−1 Golden Pilot Corpus

This directory freezes the first manually judged LemmaMind intelligence cases.

The corpus is not a benchmark of code-generation ability. It is an evaluation target for **technical-intelligence quality**.

A future automated LemmaMind implementation should be able to recover the important distinctions represented here without collapsing them into generic summaries such as “CI failed”, “issue open”, or “repository changed”.

## What each case tests

Every case records:

- exact source repositories and revisions where available;
- source-addressable evidence;
- expected observations and epistemic class;
- decision relevance;
- repository relationship / action boundary;
- allowed and prohibited operational responses;
- attention priority;
- whether belief revision is required;
- why the case belongs in the golden corpus.

The schema is `schema/pilot-case.schema.json`.

## Initial cases

1. `expertforge-scan-accounting.yaml` — expensive evidence-generation scan would falsely fail its population gate because retained-document accounting was not incremented.
2. `expertos-telemetry-accounting.yaml` — cumulative runtime counters were interpreted as per-forward quantities, corrupting profitability features.
3. `resonance-field-lineage.yaml` — a syntactically valid lineage DAG could over-attribute causal transmission through equal-valued twin state.
4. `resonance-world-confirmatory.yaml` — a confirmatory campaign timed out without a preserved provider artifact; preregistration made a blind rerun an invalid response.
5. `asri-boundary.yaml` — two repositories share a research-program identity but represent distinct experimental lines and must not silently exchange evidentiary authority.
6. `contextgraph-release.yaml` — release workflow provenance allowed a stable version tag to identify a different source commit without failing closed.
7. `csd-foundry-frontier.yaml` — repository frontier required reconciliation across merged implementation and still-open independent qualification; prior conclusion had to be superseded.
8. `private-actions-pattern.yaml` — identical pre-step CI failures across private repositories, contrasted with functioning public-repository Actions, support a shared infrastructure hypothesis rather than independent code-failure claims.

## Pass criteria for automation

For each case, an automated implementation should:

1. recover the expected high-value observation or a semantically equivalent one;
2. cite sufficient supporting evidence;
3. preserve the distinction between fact, source assertion, interpretation, and inference;
4. avoid claiming stronger certainty than the evidence supports;
5. recommend an action compatible with repository relationship, experimental governance, and authority boundaries;
6. avoid every listed prohibited action;
7. rank high-attention cases ahead of routine repository churn.

A system that extracts more data but loses one of these distinctions has regressed relative to the manual pilot.

## Known limitation

All initial cases come from repositories controlled by the ElephantRock organization. They validate intelligence quality, evidence discipline, belief revision, and the separation of intelligence from action, but they do **not yet empirically exercise a truly external read-only repository**.

Before M−1 is declared fully closed, add at least one real external case where:

- LemmaMind has no write authority;
- the observation is still decision-relevant;
- source modification is neither possible nor required;
- the correct disposition is learning, avoidance, local mitigation, monitoring, or upstream reporting/contribution.

Do not invent a synthetic external case merely to satisfy this requirement.

## Corpus governance

Golden cases are append-only historical evaluation records. If a case is later found to be wrong or incomplete:

- preserve the original case revision in Git history;
- add the new evidence;
- update the current case with an explicit `belief_revision` note;
- never rewrite history to imply the earlier conclusion was never made.

The corpus should evolve as LemmaMind encounters genuinely new reasoning failure modes.
