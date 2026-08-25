# M0 — Evidence-bound action policy validation

## Status

**Implemented and live-validated for the Resonance-World confirmatory governance case.**

This slice validates explicitly proposed operational actions against:

- `RepositoryRelationship`;
- direct captured governance evidence;
- actor-role constraints;
- explicit prohibition rules;
- independent-authorization requirements.

It does not execute actions and does not issue authorization.

## Why this layer exists

Repository capability and operational authority are not the same thing.

The frozen Resonance-World case makes that distinction concrete:

```text
repository relationship = OWNED
can_write = true

but

confirmatory_rerun_allowed = false
```

Therefore:

```text
ability to rerun
!=
authority to rerun
```

The action path must preserve that boundary just as the evidence path preserves the distinction between source ownership and epistemic validity.

## Evidence-driven action vocabulary

The original M0 `ActionType` enum described broad technical-intelligence dispositions. The frozen scientific-governance case requires operational actions that were not representable precisely:

```text
preserve
rerun
classify
promote
```

These are now explicit action types. They are not encoded as free-form target strings because the policy layer needs stable machine-readable action semantics.

## Policy inputs

`ActionPolicyService` accepts an explicit `ActionProposal`, a persisted `RepositoryRelationship`, and versioned `ActionPolicyRule` objects.

A v1 policy rule must be supported by direct captured evidence from the same `Source` as the action:

```text
EvidenceFact
or
SourceAssertion
```

Observation-derived rules are intentionally excluded from v1. Governance constraints should not silently inherit candidate reasoning as if it were direct authority.

Evidence requirements can verify:

- an exact `EvidenceFact.normalized_value`;
- required fragments in a `SourceAssertion`.

The policy evaluation fails closed on missing support, incomplete extraction runs, mismatched fact values, missing assertion text, broken artifact provenance, or support from another Source.

## Policy effects

V1 supports three explicit effects:

```text
PROHIBIT
REQUIRE_ROLE
REQUIRE_INDEPENDENT_AUTHORIZATION
```

Decision precedence is fail-closed:

```text
any blocking condition
        ↓
BLOCKED

else independent authorization required
        ↓
REQUIRES_AUTHORIZATION

else
        ↓
RECOMMENDED
```

Repository permission checks are separate from policy rules. A repository modification proposal is blocked when `can_write=false`; `contribute_upstream` is blocked when `can_contribute=false`. Conversely, `can_write=true` cannot override a matched governance prohibition.

## Authorization boundary

The most important invariant is structural:

> `ActionPolicyService` has no code path that emits `ActionStatus.AUTHORIZED`.

For a policy-compliant action that still requires independent authority, the persisted result remains:

```text
status = recommended
authorization_required = true
```

The service can identify that independent authorization is required; it cannot impersonate or self-ratify that authority.

A future authorization/execution plane must be separate and must prove actor identity/role independently.

## Resonance-World live policy

The live validation used the pinned revision:

`65d739736070bbebe7941bebfbee785d33499c46`

and captured three governance constraints:

1. `research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json#/confirmatory_rerun_allowed = false`;
2. PR #177 says the separate frozen-output evaluator is the only classifier;
3. PR #177 says promotion requires independent Acceptance-plane authority.

The surrounding workflow evidence also verified frozen run `31895957256` is `cancelled` with zero uploaded workflow artifacts.

Live LemmaMind run `32865837892` passed **92 offline tests** and produced:

| Proposal | Decision |
| --- | --- |
| rerun as operator | `blocked` |
| classify as provider runner | `blocked` |
| classify as frozen-output evaluator | `recommended` |
| promote | `requires_authorization` |
| preserve execution record | `recommended` |

All persisted action statuses were non-authorized.

Stable checkpoint: `eval/pilot/action-policy-reports/resonance-world-confirmatory-v1.{json,md}`.

## JSON governance evidence

The request-plan rule required a machine-readable fact from an ordinary JSON document. M0 therefore adds an opt-in `JsonPointerExtractor`.

It emits scalar leaves at deterministic JSON Pointer locators, for example:

```text
research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json#/confirmatory_rerun_allowed
```

It is intentionally not added to the default broad extraction policy yet. Callers opt into it when the JSON document is explicitly selected as a governed source artifact.

## What this closes

The hard-case capability:

```text
action_policy_validation
```

moves from `missing` to `implemented`.

The readiness matrix becomes:

```text
2 ready / 1 blocked / 1 deferred
```

with Resonance-World now `ready` at the current evidence/Observation/action-policy boundary.

## What this does not implement

This slice does not provide:

- action execution;
- credentialed authorization;
- independent actor identity proof;
- automatic policy discovery from arbitrary prose;
- model-generated action proposals;
- issue/PR event history;
- temporal frontier reconciliation;
- cross-repository Pattern semantics.

## Next measured boundary

The remaining source-local blocked golden case is CSD-Foundry. Its next missing evidence is issue #37's close→reopen event history, followed by a temporal reconciliation layer that can compare revision/process evidence without weakening source-revision-bound Observation semantics.
