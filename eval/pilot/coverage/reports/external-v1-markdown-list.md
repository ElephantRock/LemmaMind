# External pilot deterministic-evidence coverage — after Markdown list extraction

Coverage ID: `external-golden-evidence-v1`

This report is the second live execution of the same frozen external coverage specification. It preserves the original 4/12 report rather than overwriting it.

## Live execution provenance

- One-time live workflow run: `32812194683`
- Branch head executed: `1d92f90af10b60361d14a7fabffd88772f701967`
- Offline suite before live capture: **36 passed**
- Live pinned capture/extraction step: **success**
- GitHub token permissions: read-only `contents: read`, `metadata: read`
- Coverage specification: `eval/pilot/coverage/external-v1.yaml`
- Prior baseline: `eval/pilot/coverage/reports/external-v1.md` (**4/12, 33.3%**)

## Result

- Cases: **4**
- Evidence requirements: **12**
- Recovered: **6**
- Gaps: **6**
- Coverage fraction: **0.500**
- Absolute improvement: **+2 requirements**
- Relative coverage increase: **33.3% → 50.0%**

| Case | Before | After | Change |
| --- | ---: | ---: | ---: |
| `external-openbot-capability-authority` | 0/3 | **1/3** | +1 |
| `external-openclaw-sandbox-posture` | 2/3 | **3/3** | +1 |
| `external-hermes-process-containment` | 0/3 | **0/3** | 0 |
| `external-opd-source-type` | 2/3 | **2/3** | 0 |

## Newly recovered evidence

### OpenBot — skill instructions versus capabilities

`openbot-authority-1` is now recovered from:

- `README.md:L151-L151`

The source list item states that skills are instructions rather than capabilities. The new `markdown-list.v1` extractor preserves that authored statement as `SourceAssertion`; it does not convert the security claim into an observed implementation fact.

### OpenClaw — elevated execution outside the sandbox

`openclaw-sandbox-3` is now recovered from:

- `docs/gateway/sandboxing.md:L23-L23`

This completes all three source-assertion requirements for the OpenClaw sandbox-posture case. The resulting **3/3** means the current deterministic Markdown layer now preserves the complete documentation evidence selected for that golden case. It does not mean the later architectural `Observation` is automatically generated or validated.

## Remaining gaps

The Markdown-list gap is eliminated from this coverage specification. The six remaining requirements are:

- `source-code-semantic-facts`: **3**
- `test-code-semantic-facts`: **1**
- `commit-metadata-and-change-facts`: **1**
- `complete-repository-tree-facts`: **1**

These labels describe missing evidence capability classes. They are **not** permission to emit semantic conclusions directly as `EvidenceFact`.

## Parser behavior validated

`markdown-list.v1`:

- recognizes unordered list markers (`-`, `+`, `*`);
- recognizes ordered list markers (`1.`, `1)` and analogous numeric markers);
- removes only the structural list marker from the assertion text;
- joins indented continuation lines into the same assertion;
- assigns exact first/last content line provenance;
- treats nested list items as separate assertions;
- excludes fenced-code contents;
- refuses table/block-quote lines as list continuations;
- remains separate from `markdown-prose.v1`, preserving reproducibility of the older extractor contract.

Combined source assertions are ordered by source path and numeric line range so multiple Markdown extractors do not scramble evidence order.

## Interpretation boundary

A recovered requirement still means only:

```text
pinned source
    ↓
real read-only capture
    ↓
content-addressed Artifact
    ↓
deterministic source extraction
    ↓
source-addressed EvidenceFact / SourceAssertion
```

It does **not** mean:

```text
source text
    ↓
automatically true claim
    ↓
automatically validated Observation
```

## Next selected slice

The next deterministic capability remains **exact Git tree capture and tree facts**. It directly targets `opd-source-3`, removes a structural blind spot created by explicit-path capture, and is lower epistemic risk than source-code interpretation.
