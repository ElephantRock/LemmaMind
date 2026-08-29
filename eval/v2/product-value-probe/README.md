# V2 Prospective Product-Value Probe

This directory contains the prospective post-V1 product-value evaluation artifacts.

The V1 Evidence Engine remains PASS. V2-P0 asked a different question: whether the deterministic V1 machinery, applied prospectively to ordinary fresh repository changes, already saves enough investigation attention to justify moving downstream into representation or more reasoning.

The first three eligible changed intervals failed that gate with bottleneck `CHANGE_SIGNAL`. The resulting full-M5 corrective work is evaluated here against the same frozen failure intervals.

## Authoritative artifacts

- `baseline-2026-08-26.yaml` — frozen five-repository prospective baseline.
- `2026-08-26-openbot-43ea5c-e8aa344.yaml` — immutable OpenBot interval record.
- `2026-08-26-openclaw-20eef85-aec260b.yaml` — immutable OpenClaw interval record.
- `2026-08-26-hermes-b2bd1ac-a6d6060.yaml` — immutable Hermes Agent interval record.
- `V2-P0-CLOSEOUT.md` — authoritative prospective gate verdict and bottleneck routing.
- `m5-recursive-localization-v1.md` — first full-M5 corrective replay: exact recursive changed-path localization.
- `m5-affected-file-planning-v1.md` — deterministic affected-file capture-planning replay.
- `m5-interval-segmentation-v1.md` — deterministic commit/path candidate segmentation replay, including first-parent integration routing and the remaining attention-size gap.

Templates remain for future prospective evaluations:

- `record-template.yaml`
- `CLOSEOUT-TEMPLATE.md`

## Current product conclusion

The V2-P0 failure was not an evidence-integrity regression. The evidence engine can reproduce and prove factual change, but repository-local change signal was too broad to save human attention.

Full-M5 progress has now established three deterministic layers:

```text
root-tree change
    ↓
exact recursive GitPathDelta
    ↓
governed affected-file capture plan
    ↓
first-parent temporal/path candidate segmentation
```

The frozen segmentation replay retained every net changed path and every known high-value miss location, but OpenClaw still produced 229 deterministic candidate units from 1,291 changed leaf paths. Those are useful machine-processing units, not yet an acceptable human review queue.

The next measured work remains inside full M5: candidate-scoped capture, deterministic evidence/StructuralDelta, and evidence-aware factual suppression/reduction before semantic `ChangeInterpretation` is authorized. M6.5/embeddings remain deferred.
