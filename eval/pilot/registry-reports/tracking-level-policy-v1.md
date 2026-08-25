# M2 tracking-level policy checkpoint — v1

## Scope

This checkpoint validates the remaining V1 M2 tracking-level contract without fabricating a production policy assignment or mutating any upstream repository.

Tracking is operational metadata only. It does not alter evidence truth, validation state, repository relationship, or authorization.

## Implemented policy levels

| Level | Name | Capture | Polling | Process current/history | Reasoning |
| --- | --- | --- | --- | --- | --- |
| `0` | Ignore | none | never | no / no | no |
| `1` | Metadata only | metadata | metadata | no / no | no |
| `2` | Shallow | shallow | revision | no / no | no |
| `3` | Structural | structural | revision | no / no | yes |
| `4` | Deep | deep | revision | yes / yes | yes |
| `5` | Continuous | deep | continuous | yes / yes | yes |

Polling mode is deliberately qualitative. No fixed polling interval is invented by this slice.

## Durable history contract

`RepositoryTrackingAssignment` is immutable and records:

- canonical `source_id`;
- tracking level;
- effective and recorded timestamps;
- caller-supplied governance identity;
- reason;
- policy version;
- explicit supersession link to the preceding assignment.

An unassigned Source fails closed as effective level `0`, but no fake assignment is persisted. Explicit `0` and unassigned therefore remain distinguishable.

## Effective-time correction during validation

The first implementation allowed future-effective assignments while enforcing monotonic effective history.

Review identified a governance ambiguity: once a future promotion was recorded, a later attempt to cancel it before activation could require inserting an earlier future timestamp, which the monotonic rule would reject. Allowing that insertion without explicit cancellation/correction semantics would make the append-only timeline ambiguous.

V1 was therefore narrowed:

- new assignments are immediate only;
- future scheduling is rejected;
- backdating is rejected;
- exact replay of an existing assignment remains idempotent;
- historical `as_of` lookup remains supported.

## Enforcement points

Tracking-aware adapters gate existing services before expensive or durable work:

1. repository file capture requires level `2+`;
2. current issue/PR snapshots require level `4+`;
3. issue-event history requires level `4+`;
4. source-local candidate Observation construction requires level `3+` before persistence.

The original non-tracking-aware services are left unchanged so M2 policy is additive and explicit.

## CI evidence

Initial tracking implementation:

- permanent PR workflow: passed;
- suite size: **147 tests**.

After immediate-only effective-time correction:

- exact tracking/adapters head: `7e877f2728699bc95146cd9b55ddfcda4918ad58`;
- permanent PR workflow run: `32912196984`;
- result: **148 passed in 1.94s**.

Documentation commits follow that tested implementation and are subject to the final PR workflow before merge.

## What this checkpoint does not claim

It does not claim:

- that a production scheduler exists;
- that `continuous` has a fixed cadence;
- that `assigned_by` is authenticated by the tracking service;
- that tracking level authorizes repository modification;
- that reasoning eligibility validates or promotes a claim;
- that any live LemmaMind Source has been assigned a production tracking level.

The next roadmap step after M2 is M3 Revision Capture, reconciling the already-existing M0 revision/capture machinery against the formal M3 gate rather than duplicating it.
