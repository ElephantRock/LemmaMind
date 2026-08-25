# External OpenBot Observation probe — v1

Case: `external-openbot-capability-authority`

This is LemmaMind's first live execution of the explicit `Evidence → ObservationSupport → Observation` boundary against a frozen external golden case.

## Live execution provenance

- One-time workflow run: `32851722987`
- Branch head executed: `82e004808740291b0ad0a758317dab76103fd461`
- Offline suite before live probe: **66 passed**
- Live pinned OpenBot capture/extraction/observation step: **success**
- GitHub permissions: read-only `contents: read`, `metadata: read`
- Repository: `CopilotKit/OpenBot`
- Pinned revision: `d293f2331bd5ff9ba4ad17af6ac94570a157d26d`
- Runtime `SourceRevision`: `github:1336502227@d293f2331bd5ff9ba4ad17af6ac94570a157d26d`

## Result

Two frozen golden observation statements were replayed as new runtime candidates.

All four probe invariants passed:

- statements matched the frozen golden statements exactly;
- epistemic types matched exactly;
- every runtime Observation remained `candidate`;
- every leaf support edge resolved to the one pinned OpenBot `SourceRevision`.

The probe does not generate or independently validate the statements. Its purpose is to prove the durable support graph and authority boundary first.

## Observation 1 — instruction versus execution authority

Golden epistemic type: `Interpretation`  
Golden validation target: `validated`  
Fresh runtime validation state: **`candidate`**

Golden statement:

> OpenBot treats instructional content and execution authority as separate control planes; loading a skill does not itself grant the ability to invoke the tools that skill names.

Runtime support: **8 explicit edges** flattened from two golden evidence groups.

### `openbot-authority-1`

One `SourceAssertion`:

- `README.md:L151-L151`

### `openbot-authority-2`

Seven runtime support records spanning `SourceAssertion` and `EvidenceFact`:

- `server/src/tenant-package.ts:L145-L156`
- `server/src/tenant-package.ts:L586:C9-L851:C4#typescript/call`
- `server/src/tenant-package.ts:L812:C14-L812:C44#typescript/call`
- `server/src/tenant-package.ts:L812:C14-L818:C9#typescript/call`
- `server/src/tenant-package.ts:L831:C14-L832:C31#typescript/call`
- `server/src/tenant-package.ts:L831:C14-L840:C11#typescript/call`
- `server/src/tenant-package.ts:L831:C14-L846:C12#typescript/call`

The runtime does not persist the golden evidence-group ID as if it were source evidence; it persists the actual leaf records that support the Observation.

## Observation 2 — profiling consequence

Golden epistemic type: `Evaluation`  
Golden validation target: `reviewed`  
Fresh runtime validation state: **`candidate`**

Golden statement:

> Agent-runtime profiling should represent instruction or skill loading separately from capability authorization rather than inferring authority from the presence of a skill or tool declaration.

Runtime support: **11 explicit edges** flattened from `openbot-authority-2` and `openbot-authority-3`.

`openbot-authority-3` contributes:

- `server/src/tenant-package.ts:L116-L125`
- `server/src/tenant-package.ts:L399-L407`
- `server/src/tenant-package.ts:L408:C6-L412:C7#typescript/if`
- `server/src/tenant-package.ts:L409:C8-L411:C10#typescript/throw`

## Validation-state boundary

The most important negative result is intentional:

```text
golden corpus says: validated / reviewed
fresh construction says: candidate
```

A new runtime object does not inherit acceptance authority merely because its text matches a previously reviewed golden statement. The golden state is an evaluation target; runtime acceptance must come through an explicit review/validation pathway.

## Provenance boundary

Every leaf support was validated through:

```text
EvidenceFact / SourceAssertion
        ↓
Artifact
        ↓
CaptureManifest
        ↓
SourceRevision
```

The producing extraction run had to exist and be complete before the Observation could be created. The Observation, its support edges, and its reasoning `PipelineRun` were persisted atomically.

## What this proves

The current M0 implementation can represent a real external golden observation as a durable candidate whose support is exact, typed, source-addressed, revision-bound, and producer-versioned.

## What this does not prove

It does not prove that LemmaMind can yet:

- generate the statement from evidence;
- select the correct support set without golden guidance;
- independently validate the claim;
- decide whether the observation is high-signal;
- compare it to other repositories;
- promote it into a Pattern, Insight, or KnowledgeItem.

Those are later reasoning/review capabilities and should be evaluated separately.

## Next measured step

Expand the golden-driven Observation probe to cases that exercise different failure modes before introducing autonomous reasoning:

1. belief revision / supersession;
2. correct no-action behavior;
3. CI-state interpretation where `red CI != code failure`;
4. source-role constraints such as research-index versus implementation evidence.

This tests whether the support graph preserves the hardest M−1 distinctions before asking a model to propose observations itself.
