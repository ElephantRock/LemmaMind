# V2-P0 Product-Value Probe Evaluation Records

This directory stores immutable prospective evaluation records for the LemmaMind V2-P0 product-value gate defined in [`docs/V2-P0-PRODUCT-VALUE-PROBE.md`](../../../docs/V2-P0-PRODUCT-VALUE-PROBE.md).

## Result

**V2-P0: FAIL — `CHANGE_SIGNAL` bottleneck.**

The authoritative closeout is [`V2-P0-CLOSEOUT.md`](V2-P0-CLOSEOUT.md). V1 remains PASS; this result means the V1 evidence machinery is not yet sufficient as a prospective attention-saving product. The next authorized slice is **full M5**, beginning with recursive changed-path localization and deterministic churn suppression before broader semantic `ChangeInterpretation`.

Semantic embeddings and M6.5 remain deferred.

## Prospective rule

A sampled interval is valid only when the prior revision is recorded before unrestricted inspection of the later change. Do not choose a revision pair because a known interesting outcome has already been identified.

Silence and low-value intervals remain valid samples.

## Frozen baseline

The five-repository frontier is recorded in [`baseline-2026-08-26.yaml`](baseline-2026-08-26.yaml). Three repositories advanced and produced eligible intervals before the gate was stopped; ERLab and Resonance-World remained at baseline.

## Evaluated intervals

- [`2026-08-26-openbot-43ea5c-e8aa344.yaml`](2026-08-26-openbot-43ea5c-e8aa344.yaml)
- [`2026-08-26-openclaw-20eef85-aec260b.yaml`](2026-08-26-openclaw-20eef85-aec260b.yaml)
- [`2026-08-26-hermes-b2bd1ac-a6d6060.yaml`](2026-08-26-hermes-b2bd1ac-a6d6060.yaml)

The corrected deterministic probe used exact non-recursive Git root-tree evidence plus prospectively selected explicit files and completed on workflow run `33017750243` with **202 tests passed**. Bounded manual review was performed only after the deterministic output was captured.

## One record per sampled interval

Create one YAML record from `record-template.yaml` for each repository/revision interval.

Records are append-only evaluation artifacts. If later evidence changes a judgment, add a later record and reference the earlier record through `supersedes` or explanatory notes. Do not rewrite the historical evaluation merely to match the current belief.

## Human judgment is not evidence mutation

Labels such as `HIGH_VALUE`, `LOW_SIGNAL`, `RIGHT_PRIORITY`, or `MATERIAL` are evaluation judgments. They do not alter deterministic `EvidenceFact`, `StructuralDelta`, `ArchitectureProfile`, or `TriageAssessment` state.

## Closeout discipline

A closeout must identify the measured bottleneck and choose exactly one next narrow direction:

- full M5;
- full M6;
- M6.5a structured representation;
- minimal representation required for M7.

The first V2-P0 closeout selected **full M5**. Future representation work remains contingent on a later measured bottleneck rather than roadmap sequence alone.
