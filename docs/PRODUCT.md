# LemmaMind Product Contract

## Definition

**LemmaMind is a personal technical-intelligence system that converts reproducible technical evidence into reviewed, decision-relevant knowledge.**

GitHub is the first source ecosystem, not the product boundary. Repositories, releases, pull requests, issues, documentation, experiments, papers, benchmarks, and other technical artifacts may all become evidence sources over time.

LemmaMind is not primarily a repository bookmarker, README summarizer, vector database, crawler, autonomous research agent, or coding bot.

## Primary user

The initial user is one technically sophisticated engineer or researcher who repeatedly needs to understand technical systems, compare implementations, track meaningful changes, and make engineering or research decisions under limited attention.

Typical questions include:

- What materially changed in the projects I care about?
- Why might that change matter?
- Which repositories implement this mechanism?
- Which mechanisms recur across unrelated projects?
- Which approaches differ, and under what assumptions?
- Which designs were later reversed or abandoned?
- Which repository deserves a deep dive?
- What evidence supports this conclusion?
- Does new evidence challenge something I already believe?
- What should I investigate, adopt, avoid, test, or reconsider?

## Core functions

LemmaMind should:

1. discover high-value technical sources;
2. identify and capture exact source revisions;
3. extract source-addressable deterministic evidence;
4. distinguish observed facts from source assertions and inference;
5. build comparable structural and architectural profiles;
6. detect meaningful changes while suppressing routine churn;
7. produce evidence-grounded observations;
8. compare observations across sources;
9. identify recurring mechanisms, reversals, failures, and unusual implementations;
10. identify architectural tensions and the assumptions behind competing positions;
11. synthesize reviewable insights;
12. preserve provenance from knowledge back to exact source material;
13. maintain and revalidate knowledge when underlying evidence changes;
14. prioritize scarce human attention;
15. recommend possible actions without requiring that the source repository be modified.

## Primary outputs

LemmaMind produces intelligence objects, not merely files or summaries:

- reproducible evidence records;
- architecture and mechanism profiles;
- meaningful structural deltas;
- evidence-grounded observations;
- negative/reversal intelligence;
- cross-source patterns;
- architectural tensions;
- synthesized insights;
- promoted knowledge;
- action recommendations;
- review queues;
- daily/weekly intelligence briefs;
- evidence-backed answers, comparisons, and deep dives.

A useful result must support the question:

```text
Why do you believe this?
        ↓
Which observations support it?
        ↓
Which evidence supports those observations?
        ↓
Which exact source revision and artifact produced that evidence?
```

## User experience

The intended experience is closer to a disciplined technical research analyst than a feed reader.

The user should be able to:

- **Review** a small queue of high-value candidate observations and insights;
- **Ask** evidence-backed questions over the tracked corpus;
- **Compare** architectures, mechanisms, and decisions across sources;
- **Inspect changes** that LemmaMind judged materially significant;
- **Deep dive** from an insight down to exact source evidence;
- **Search** across evidence, observations, patterns, tensions, and promoted knowledge;
- **Accept, reject, merge, contradict, snooze, deep-dive, or promote** candidate intelligence.

Silence is a valid output. LemmaMind should show less rather than accumulate a low-value backlog.

## Knowledge path and action path

A core product boundary is the separation between understanding and intervention.

```text
                         Observation
                             │
                  ┌──────────┴──────────┐
                  ↓                     ↓
          KNOWLEDGE PATH          ACTION PATH
                  │                     │
               Pattern           Impact assessment
                  ↓                     ↓
               Tension        Ownership / authority
                  ↓                     ↓
               Insight        Action recommendation
                  ↓                     ↓
          Reviewed Knowledge      Optional action
```

The knowledge path is universal. The action path depends on repository relationship, authority, risk, and user intent.

## Repository relationship

Initial relationship classes:

- `OWNED` — the user or organization controls the repository;
- `CONTRIBUTABLE` — external, but a legitimate contribution path exists;
- `EXTERNAL` — external source; modification is neither assumed nor required;
- `READ_ONLY` — observation only; no operational action is available or appropriate;
- `UNKNOWN` — default to observation and recommendation only.

The ability to repair a source must never determine whether an observation is worth preserving.

## Operational dispositions

A finding may result in any of the following without modifying its source:

- learn / incorporate;
- investigate further;
- adopt;
- avoid;
- pin or version-gate;
- mitigate locally;
- monitor upstream;
- report upstream;
- contribute upstream;
- fork or vendor when justified;
- revalidate existing knowledge;
- take no action.

## Product invariants

1. Evidence and inference remain separate.
2. Every durable derived object has provenance.
3. Historical evidence is immutable.
4. Analysis is reproducible.
5. External source content is untrusted.
6. LLM output is never authoritative source evidence.
7. Technical sources are not themselves knowledge.
8. Human attention is a budgeted system resource.
9. Negative evidence is first-class.
10. Personalization retains deliberate exploration.
11. Intelligence is mandatory; action is optional.
12. Repository modification is an explicitly authorized downstream action, never a success requirement.
13. Technical ability to perform an action does not imply epistemic or operational authority to perform it.
14. New evidence may supersede prior conclusions without rewriting historical observations.

## Success criterion

LemmaMind succeeds when it repeatedly produces evidence-backed technical intelligence that changes what the user investigates, designs, implements, adopts, avoids, or believes.

The system is not judged by repositories processed, summaries generated, embeddings stored, or pull requests opened.
