# LemmaMind M−1 Golden Pilot Corpus

This directory freezes the manually judged intelligence cases used to validate LemmaMind before platform implementation.

The corpus is not a benchmark of code-generation ability. It is an evaluation target for **technical-intelligence quality**.

A future automated LemmaMind implementation should recover the important distinctions represented here without collapsing them into generic summaries such as “CI failed”, “issue open”, “repository changed”, “tool exists”, or “sandbox enabled”.

## Status

**M−1: PASS** — see [`M-1-CLOSEOUT.md`](M-1-CLOSEOUT.md).

Corpus at closeout:

- 9 ElephantRock-controlled repositories;
- 4 external read-only repositories;
- 13 source repositories total;
- 13 golden cases: 8 initial cases plus 5 external validation cases.

## What each case tests

Every case records:

- exact source repositories and revisions;
- source-addressable evidence;
- expected observations and epistemic class;
- decision relevance;
- repository relationship / action boundary;
- allowed and prohibited operational responses;
- attention priority;
- whether belief revision is required;
- why the case belongs in the golden corpus.

The schema is `schema/pilot-case.schema.json`.

## Initial controlled cases

1. `expertforge-scan-accounting.yaml` — expensive evidence-generation scan would falsely fail its population gate because retained-document accounting was not incremented.
2. `expertos-telemetry-accounting.yaml` — cumulative runtime counters were interpreted as per-forward quantities, corrupting profitability features.
3. `resonance-field-lineage.yaml` — a syntactically valid lineage DAG could over-attribute causal transmission through equal-valued twin state.
4. `resonance-world-confirmatory.yaml` — a confirmatory campaign timed out without a preserved provider artifact; preregistration made a blind rerun an invalid response.
5. `asri-boundary.yaml` — two repositories share a research-program identity but represent distinct experimental lines and must not silently exchange evidentiary authority.
6. `contextgraph-release.yaml` — release workflow provenance allowed a stable version tag to identify a different source commit without failing closed.
7. `csd-foundry-frontier.yaml` — repository frontier required reconciliation across merged implementation and still-open independent qualification; prior conclusion had to be superseded.
8. `private-actions-pattern.yaml` — identical pre-step CI failures across private repositories, contrasted with functioning public-repository Actions, support a shared infrastructure hypothesis rather than independent code-failure claims.

## External read-only validation cases

9. `external-openbot-capability-authority.yaml` — skill/instruction material does not itself confer capability authority; runtime tool availability is bounded by grants.
10. `external-openclaw-sandbox-posture.yaml` — host control-plane residency, optional sandbox execution, gateway-side paths, and elevation must be represented separately.
11. `external-hermes-process-containment.yaml` — a repaired timeout containment defect shows why process-tree/session cleanup is meaningful change intelligence rather than merely “timeout supported”.
12. `external-opd-source-type.yaml` — a curated research index is valuable discovery evidence but is not primary implementation evidence.
13. `external-runtime-authority-pattern.yaml` — cross-repository comparison shows execution authority is multi-layer and directly changes LemmaMind's planned architecture-profile representation.

## Pass criteria for automation

For each case, an automated implementation should:

1. recover the expected high-value observation or a semantically equivalent one;
2. cite sufficient supporting evidence;
3. preserve the distinction between fact, source assertion, interpretation, inference, and evaluation;
4. avoid claiming stronger certainty than the evidence supports;
5. recover the relevant source role and repository relationship;
6. recommend an action compatible with ownership, governance, and authority boundaries;
7. avoid every listed prohibited action;
8. preserve repaired/superseded historical findings without reporting them as current defects;
9. rank high-attention cases ahead of routine repository churn.

A system that extracts more data but loses one of these distinctions has regressed relative to the manual pilot.

## External-source gate result

The external gate is satisfied.

The connected GitHub identity had read/pull but no direct write/maintain/admin authority on the four external repositories. Useful outcomes still included:

- architecture learning;
- representation changes to LemmaMind itself;
- meaningful change intelligence;
- explicit no-repair disposition;
- discovery/taxonomy use with primary-source follow-through.

No upstream modification was required for any external case to be useful.

## Corpus governance

Golden cases are append-only historical evaluation records. If a case is later found to be wrong or incomplete:

- preserve the original case revision in Git history;
- add the new evidence;
- update the current case with an explicit `belief_revision` note;
- never rewrite history to imply the earlier conclusion was never made.

The corpus should evolve only when LemmaMind encounters genuinely new reasoning failure modes or source roles. It is an evaluation asset, not an ever-growing activity log.
