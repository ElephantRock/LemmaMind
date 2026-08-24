# LemmaMind

**LemmaMind** is a personal technical-intelligence system for turning reproducible technical evidence into reviewed, decision-relevant knowledge.

GitHub is the first source ecosystem, not the boundary of the project. LemmaMind studies high-value technical sources, preserves the exact evidence used for analysis, separates observed facts from inference, detects meaningful changes, and progressively synthesizes cross-source patterns, tensions, insights, and reviewed knowledge.

Repository repair is not a core requirement. LemmaMind's mandatory job is to understand and substantiate; operational action is optional and depends on ownership, authority, risk, and user intent.

## Governing principle

> Useful evidence first. Evidence-bound inference second. Reviewed knowledge third. Real decisions are the measure of success.

## Current phase

LemmaMind is in **M−1 — Manual Intelligence Pilot**.

The first controlled pilot used the broader ElephantRock repository portfolio to test whether disciplined evidence-grounded analysis can recover high-value technical findings while preserving epistemic status, governance boundaries, belief revision, and correct no-action behavior.

Eight manually judged cases are now frozen as the initial golden evaluation corpus. M−1 remains open until at least one real external-source case demonstrates useful intelligence where LemmaMind has no source modification authority.

## Start here

- [`docs/PRODUCT.md`](docs/PRODUCT.md) — authoritative product definition, user, outputs, UX, and action boundary
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — comprehensive project roadmap
- [`docs/PILOT.md`](docs/PILOT.md) — M−1 protocol, current corpus, and exit gate
- [`pilot/watchlist.yaml`](pilot/watchlist.yaml) — pinned ElephantRock pilot corpus
- [`eval/pilot/`](eval/pilot/) — golden intelligence cases and evaluation contract
- [`eval/pilot/schema/pilot-case.schema.json`](eval/pilot/schema/pilot-case.schema.json) — machine-readable case schema
- [`config/domains.yaml`](config/domains.yaml) — configurable technical domains
- [`pilot/evidence/`](pilot/evidence/) — source-addressed pilot evidence conventions
- [`pilot/observations/`](pilot/observations/) — human-authored observation conventions

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

## Canonical home

https://github.com/ElephantRock/LemmaMind
