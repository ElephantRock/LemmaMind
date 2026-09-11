# M5 ChangeInterpretation — Frozen Evaluation Specification

## Purpose

This evaluation freezes the product gate for the next full-M5 slice before any
semantic interpreter is implemented.

The factual substrate is already considered sufficient for this experiment:
recursive changed-path localization, affected-file planning, interval
segmentation, candidate-scoped capture, deterministic extraction,
`ArtifactDelta`, `StructuralDelta`, authored-assertion change, and explicit
extraction-gap signals have all been replayed successfully on the frozen V2-P0
intervals.

The remaining question is:

> Can provenance-bound interpretation convert machine-sized factual candidates
> into a materially smaller set of mechanism-level review items without
> inventing unsupported significance?

This specification is intentionally frozen before interpreter implementation so
the implementation cannot redefine success after seeing its own outputs.

## Inputs

Use the same three V2-P0 revision intervals and the same deterministic
candidate-generation policies used by the M5 candidate factual-reduction replay.

| Repository | Previous revision | Current revision | Machine candidates |
| --- | --- | --- | ---: |
| CopilotKit/OpenBot | `43ea5c11210c485551c25b41a4270c56a58591f1` | `e8aa34451f73ef2719c22cc557be369d9ea70afb` | 9 |
| openclaw/openclaw | `20eef858aafbf6a3c45b0f20366a08192996f91b` | `aec260b7002cf56232add300f3dd3454c81a10cf` | 229 |
| NousResearch/hermes-agent | `b2bd1ac63ff137a6287ce989d65dccee6b9155e2` | `a6d6060d6128260d8536d0b92ae0324fff028ffd` | 65 |

Frozen factual baseline:

```text
OpenBot:      9 candidates,   41 ArtifactDelta,   3,612 StructuralDelta
OpenClaw:   229 candidates, 1,269 ArtifactDelta, 356,123 StructuralDelta
Hermes:      65 candidates,  146 ArtifactDelta, 120,864 StructuralDelta
```

Extraction uncertainty is part of the frozen substrate. In particular,
OpenClaw has a 69-path extraction-gap union across 41 candidates. Those gaps are
not evidence of low value and must not be silently suppressed.

## Known high-value mechanisms

The V2-P0 manual review identified ten mechanism-level misses. They are frozen
evaluation targets, not training labels that may be hard-coded into routing.

### OpenBot

1. Attention inbox for refusals and stalls derived from append-only audit events,
   with separate attributed resolution state.
2. Policy dry-run against historical judged actions before saving a boundary rule,
   without writing audit decisions during the dry run.
3. Named undecided routing causes such as unreachable, unparsed, off-roster,
   unconfident, and one-candidate.

Primary anchor path:

```text
app/src/lib/attention/queries.ts
```

### OpenClaw

1. Configurable model-selection scopes with session/agent/global persistence
   without broadening configuration-write authority.
2. Validate a capture batch before publishing files, preventing partial
   publication after a malformed later response.
3. Recheck idle/node readiness after waits rather than trusting stale state.
4. Preserve worker timeouts across clock changes.

Primary anchor path:

```text
src/agents/sticky-model-selection.ts
```

### Hermes Agent

1. Provenance-aware update admission that refuses inappropriate in-place
   mutation, honors authoritative installation provenance, and fails closed on
   corrupted markers.
2. Project completed agent-as-provider tool work into the durable turn without
   resurrecting completed calls as pending work.
3. Fail closed on a headless model guard instead of waiting on an unavailable
   confirmation surface.

Primary anchor path:

```text
hermes_cli/update_contract.py
```

## Contract boundary

`ChangeInterpretation` is inferred M5 output. It is not deterministic evidence.

Every interpretation must:

- bind exact source and previous/current `SourceRevision` IDs;
- bind one or more exact `IntervalCandidateSegment` IDs;
- bind one factual reduction for every interpreted candidate;
- carry typed support references to factual records and/or explicit extraction
  uncertainty;
- remain in `candidate` validation state when created;
- carry explicit uncertainty when an extraction-gap signal is part of its support;
- preserve model/policy/run provenance in the producing `PipelineRun`.

A generated interpretation must not:

- create new `EvidenceFact` or `SourceAssertion` records;
- treat absence of extracted structure as evidence of irrelevance;
- convert extraction failure into a factual add/remove claim;
- claim causal importance merely from file count or churn;
- authorize action, promotion, repository writes, or knowledge validation;
- use repository relationship/write authority as evidence that a technical claim
  is true.

## Attention-surface gate

The interpreter may decline to produce an interpretation when evidence is
insufficient. It must not produce one prose item per machine candidate merely to
satisfy coverage.

For the frozen replay, PASS requires all of the following:

1. **Primary-anchor recall:** all three primary anchor mechanisms are visible in
   the resulting human review surface.
2. **Known-mechanism recall:** at least 8 of the 10 frozen V2-P0 high-value
   mechanisms are represented by a reviewable mechanism-level interpretation.
3. **Material attention reduction:** the human-facing review surface contains no
   more than:

   ```text
   OpenBot:    5 review items
   OpenClaw:  35 review items
   Hermes:    10 review items
   total:     50 review items
   ```

   This reduces the frozen 303 machine candidates by at least ~83% at the total
   review-surface level.
4. **No provenance failures:** every support reference resolves to the exact
   frozen generation and agrees with source/revision/candidate lineage.
5. **No silent gap claims:** any interpretation materially relying on a candidate
   with extraction gaps must expose that uncertainty when the gap could affect
   the interpretation.
6. **No unsupported semantic claims:** bounded human audit finds no interpretation
   whose central mechanism statement is unsupported by the supplied evidence
   packet and referenced source material.
7. **No diff paraphrase pass:** an output that mainly restates changed filenames,
   structural keys, or commit messages without isolating a mechanism is LOW_SIGNAL
   and does not count toward known-mechanism recall.
8. **Verification remains cheap:** a reviewer can navigate from a review item to
   exact supporting evidence without unrestricted repository-wide manual search.

Failure of any provenance/epistemic boundary is a slice failure even if the item
count target is met.

## Anti-overfitting gate

Passing the frozen replay is necessary but not sufficient.

After the frozen gate passes, run at least one **new prospectively selected**
revision interval using the ordinary tracking/capture path. The interval must be
selected before detailed manual inspection of its changes.

Record:

- machine candidate count;
- interpretation/review-item count;
- useful vs low-signal/noise review items;
- important manual-review misses;
- verification time where measured;
- whether any finding materially focuses a decision or deeper investigation.

Do not authorize M6.5, learned ranking, or broader M7 reasoning solely from the
frozen replay.

## Implementation sequence

The first implementation increment is:

```text
ChangeInterpretation contract
        ↓
deterministic bounded CandidateEvidencePacket
        ↓
constrained interpretation producer
        ↓
deterministic provenance/support validation
        ↓
mechanism grouping / review-surface collapse
        ↓
frozen replay
        ↓
prospective replay
```

The evidence-packet layer must be deterministic and hashable before any model
call is introduced.

## Exit decision

The slice exits with one of:

```text
PASS
FAIL_ATTENTION
FAIL_RECALL
FAIL_PROVENANCE
FAIL_SEMANTIC_GROUNDING
INCONCLUSIVE
```

Only `PASS` authorizes the next roadmap decision. A PASS does not automatically
authorize embeddings; it establishes that source-local semantic change
intelligence has become useful enough to reassess whether the next bottleneck is
full M6, M6.5 representation, M7 reasoning, or review-product work.
