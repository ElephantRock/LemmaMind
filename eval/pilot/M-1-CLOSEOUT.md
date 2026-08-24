# LemmaMind M−1 Closeout

## Result

**PASS**

M−1 validates the product hypothesis strongly enough to begin M0 contract implementation.

The result does not mean LemmaMind's future automated reasoning is proven. It means the **manual intelligence loop is demonstrably useful**, its failure modes are concrete enough to evaluate, and the minimum contracts can now be derived from observed cases instead of speculation.

## Product hypothesis tested

> Evidence-grounded cross-source technical analysis can produce decision-relevant knowledge while preserving provenance, epistemic boundaries, governance constraints, source role, and human authority.

## Corpus at closeout

- 9 ElephantRock-controlled repositories
- 4 real external read-only repositories
- 13 total source repositories
- 13 golden cases: 8 initial internal cases plus 5 external validation cases

External sources:

- `chrisliu298/awesome-on-policy-distillation` @ `e4b5e7334ccd3437ccab8d4eef770ed02c4f9934`
- `CopilotKit/OpenBot` @ `d293f2331bd5ff9ba4ad17af6ac94570a157d26d`
- `openclaw/openclaw` @ `c50f90251ebf1c420b8b8fbbff65fb39f77558f0`
- `NousResearch/hermes-agent` @ `41447a6d7063b2772b0c2f26a5b22d9bd444fb43`

The connected GitHub identity had no direct write/maintain/admin authority on these four sources during the pilot.

## External validation results

### OpenBot — capability authority

The pilot recovered a useful architectural distinction without finding or requiring a defect: skill/instruction material does not itself confer callable authority; runtime tool availability is bounded by capability grants.

**Decision effect:** LemmaMind's future agent-runtime profile must distinguish instructional content from capability authority.

### OpenClaw — layered sandbox posture

The source documents a host-resident Gateway with optional sandboxing for tool execution plus gateway-side/elevated paths.

**Decision effect:** LemmaMind must represent isolation as multiple dimensions rather than a single sandbox boolean, and must preserve documentation claims as `SourceAssertion` until implementation evidence corroborates them.

### Hermes Agent — repaired process containment

The current head contains a targeted repair for terminal timeout cleanup where a `setsid()` descendant could escape process-group termination.

**Decision effect:** process-tree/session cleanup becomes an explicit runtime-comparison dimension. The correct upstream disposition is **no repair action** because the pinned revision already contains the fix; the historical defect remains valuable negative/change intelligence.

### Awesome On-Policy Distillation — source role

The repository is a curated field index and taxonomy that points to papers, reports, frameworks, and implementations.

**Decision effect:** M0 must distinguish source identity from source role. A research index can drive discovery and preserve field claims as `SourceAssertion`, but primary implementation/scientific claims require follow-through to the linked primary source.

### Cross-repository authority pattern

OpenBot, OpenClaw, and Hermes expose different layers of execution authority:

```text
instruction / requested operation
        ↓
capability authorization
        ↓
execution location / isolation
        ↓
elevation or gateway-side paths
        ↓
process-lifecycle containment
```

**Decision effect:** the planned M6 `ArchitectureProfile` is revised before implementation. Authority will be modeled as orthogonal dimensions, not one `tools` or `sandboxed` property.

## Required M−1 capabilities

| Capability | Result |
|---|---|
| Useful single-repository observation | PASS |
| Useful cross-repository pattern | PASS |
| Architectural/research tension | PASS |
| Negative/failure/reversal intelligence | PASS |
| Correct no-action case | PASS |
| Belief revision after new evidence | PASS |
| Ability-to-act != authority-to-act | PASS |
| Real external source with no modification authority | PASS |
| Result changes an engineering/research decision | PASS |

## Success-gate judgment

The M−1 success statement is:

> **I would investigate, design, implement, adopt, avoid, monitor, or believe something differently because of this evidence-grounded intelligence.**

**Judgment: PASS.**

Concrete design changes caused by the pilot:

1. M0 now needs `Source` + `source_role`, not repository identity alone.
2. `SourceAssertion` remains distinct from deterministic facts because external documentation/indexes are valuable without being implementation proof.
3. `RepositoryRelationship` and `ActionRecommendation` are explicit contracts; knowledge validity is independent of write authority.
4. Supersession/belief revision is required from the start.
5. Agent-runtime authority profiling will be multi-dimensional rather than a single sandbox/tool flag.
6. Historical repaired defects remain valuable change intelligence without implying a current repair obligation.

These are implementation-relevant decisions that were not all present in the original roadmap before the manual pilot.

## What M−1 did not prove

M−1 does not establish:

- automated extractor accuracy;
- automated reasoning quality;
- prevalence of any architectural pattern across GitHub;
- calibrated confidence probabilities;
- broad web/paper ingestion;
- safe execution of external code;
- autonomous knowledge promotion;
- upstream contribution mechanics;
- recommendation-model quality.

Those remain later milestones and evaluation targets.

## Exit decision

M−1 is complete.

Proceed to **M0 — Minimum System Contracts**, using `docs/M0-CONTRACTS.md` as the initial implementation boundary and the golden corpus as the regression target.

The next engineering rule is:

> **Automate the evidence spine without losing distinctions the manual pilot already demonstrated.**
