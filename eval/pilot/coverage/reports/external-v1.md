# External pilot deterministic-evidence coverage

Coverage ID: `external-golden-evidence-v1`

This report measures deterministic evidence recovery only. It does **not** claim that golden observations can be generated without reasoning or review.

## Live execution provenance

- One-time live workflow run: `32811460037`
- Branch head executed: `97a9c9933bf5ee853e56ce074823476343a950ad`
- Offline suite before live capture: **32 passed**
- Live pinned capture/extraction step: **success**
- GitHub token permissions: read-only `contents: read`, `metadata: read`
- All external repository revisions came from `pilot/watchlist.yaml`.

The committed JSON companion is the transient-ID-free report emitted by the live runner.

## Summary

- Cases: **4**
- Evidence requirements: **12**
- Recovered: **4**
- Gaps: **8**
- Coverage fraction: **0.333**

| Case | Recovered | Total | Fraction |
| --- | ---: | ---: | ---: |
| `external-openbot-capability-authority` | 0 | 3 | 0.000 |
| `external-openclaw-sandbox-posture` | 2 | 3 | 0.667 |
| `external-hermes-process-containment` | 0 | 3 | 0.000 |
| `external-opd-source-type` | 2 | 3 | 0.667 |

## What was recovered

### OpenClaw

The existing Markdown prose extractor recovered both core sandbox-posture assertions from the same exact source paragraph:

- `openclaw-sandbox-1` → `docs/gateway/sandboxing.md:L9-L9`
- `openclaw-sandbox-2` → `docs/gateway/sandboxing.md:L9-L9`

This demonstrates that current M0 extraction can already preserve useful architecture claims as `SourceAssertion` when they appear in ordinary prose.

### Awesome On-Policy Distillation

The existing Markdown prose extractor recovered the source-role evidence needed for two requirements:

- `opd-source-1` → `README.md:L14-L14`
- `opd-source-2` → `README.md:L18-L18`, `README.md:L20-L20`

This is enough deterministic source material to support a later reviewed interpretation that the repository is a curated research/discovery source rather than primary implementation evidence.

## Missing deterministic capabilities

- `markdown-list-source-assertions`: **2** requirements
- `source-code-semantic-facts`: **3** requirements
- `test-code-semantic-facts`: **1** requirement
- `commit-metadata-and-change-facts`: **1** requirement
- `complete-repository-tree-facts`: **1** requirement

### Markdown list assertions

Two source claims are visible in Markdown but are intentionally dropped by the current v1 extractor because list items are excluded:

- OpenBot: `Skills are instructions, not capabilities`
- OpenClaw: `Elevated exec bypasses sandboxing ...`

This is a high-confidence, low-risk extraction gap: the source is already explicit and no semantic inference is required.

### Repository tree facts

The OPD case requires evidence about the repository root. Explicit-path capture cannot truthfully establish a complete root listing, so `opd-source-3` remains a gap. The correct fix is deterministic Git tree capture, not inference from a hand-picked file list.

### Commit/change facts

Hermes `hermes-containment-1` depends on the pinned commit/change record. The current capture service resolves commit metadata transiently but does not persist it as evidence. Change intelligence therefore needs a durable, content-addressed representation of commit metadata before this requirement can be recovered.

### Source and test code facts

The current extractor intentionally emits only artifact path facts for `.py` and `.ts` source. It does not claim code semantics. This leaves the Hermes implementation/test evidence and OpenBot implementation evidence uncovered.

A future implementation should **not** add a generic “semantic code fact” extractor. Prefer deterministic language-specific structural extraction (for example Python AST facts and TypeScript syntax/AST facts) and let later reasoning interpret those facts.

## Requirement detail

### `external-openbot-capability-authority`

- `openbot-authority-1`: **gap** — needs `markdown-list-source-assertions`
- `openbot-authority-2`: **gap** — needs `source-code-semantic-facts`
- `openbot-authority-3`: **gap** — needs `source-code-semantic-facts`

### `external-openclaw-sandbox-posture`

- `openclaw-sandbox-1`: **recovered** at `docs/gateway/sandboxing.md:L9-L9`
- `openclaw-sandbox-2`: **recovered** at `docs/gateway/sandboxing.md:L9-L9`
- `openclaw-sandbox-3`: **gap** — needs `markdown-list-source-assertions`

### `external-hermes-process-containment`

- `hermes-containment-1`: **gap** — needs `commit-metadata-and-change-facts`
- `hermes-containment-2`: **gap** — needs `source-code-semantic-facts`
- `hermes-containment-3`: **gap** — needs `test-code-semantic-facts`

### `external-opd-source-type`

- `opd-source-1`: **recovered** at `README.md:L14-L14`
- `opd-source-2`: **recovered** at `README.md:L18-L18` and `README.md:L20-L20`
- `opd-source-3`: **gap** — needs `complete-repository-tree-facts`

## Interpretation boundary

A recovered requirement means only:

```text
pinned source
    ↓
real capture
    ↓
content-addressed artifact
    ↓
deterministic extractor
    ↓
explicit coverage check matched
```

It does not mean:

```text
matched text/fact
    ↓
automatically true interpretation
    ↓
automatically promoted knowledge
```

That distinction remains the central M0 epistemic boundary.
