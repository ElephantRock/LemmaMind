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
- `m5-candidate-factual-reduction-v1.md` — candidate-scoped deterministic evidence, extraction-gap isolation, and the measured boundary where factual reduction stops saving attention.

Templates remain for future prospective evaluations:

- `record-template.yaml`
- `CLOSEOUT-TEMPLATE.md`

## Current product conclusion

The V2-P0 failure was not an evidence-integrity regression. The evidence engine can reproduce and prove factual change, but repository-local change signal was too broad to save human attention.

Full-M5 progress has now established five deterministic layers:

```text
root-tree change
    ↓
exact recursive GitPathDelta
    ↓
governed affected-file capture plan
    ↓
first-parent temporal/path candidate segmentation
    ↓
candidate-scoped factual evidence + explicit extraction gaps
```

The final factual-reduction replay retained every known high-value miss location and safely isolated parser/extractor gaps without weakening the strict V1 extraction contract. It also showed that deterministic evidence does **not** materially reduce the review surface under the current evidence-first rules:

```text
OpenBot:     9 candidates ->   9 retained
OpenClaw:  229 candidates -> 229 retained
Hermes:     65 candidates ->  65 retained
```

OpenClaw produced 356,123 `StructuralDelta` records and explicit extraction gaps on 69 paths across 41 candidates. That is abundant, auditable source-local evidence, but it is not an attention product by itself. Suppressing tests, docs, configuration, `UNKNOWN`, parser-incompatible paths, or changed bytes without extracted structure merely to reduce counts would exceed what the deterministic evidence supports.

The next measured work therefore remains inside full M5 but moves to provenance-bound `ChangeInterpretation`: use the retained factual evidence and explicit uncertainty to surface mechanism-level meaning in a genuinely smaller review set. M6.5/embeddings, learned ranking, autonomous promotion, and action execution remain deferred.
