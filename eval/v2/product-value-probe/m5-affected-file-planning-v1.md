# M5 affected-file capture planning — V2-P0 replay

## Result

**PASS for the affected-file planning sub-slice. Full M5 remains open.**

The recursive-localization slice established exact changed leaf paths. This
sub-slice converts those factual `GitPathDelta` records into a governed,
auditable exact-file byte-capture plan without provider reads, repository
checkout, source execution, semantic ranking, embeddings, or model inference.

## Planning policy v1

The planner:

- requires Shallow-or-deeper tracking and `EXPLICIT_FILES` authorization;
- binds every plan to the effective tracking assignment and level;
- preserves both sides for modified blobs;
- requests the absent side of add/remove transitions so later capture can retain
  an explicit `MISSING` retrieval state rather than silently changing scope;
- does not request directory or submodule-pointer sides;
- preserves exact Git path whitespace;
- suppresses only deterministic byte-capture cases in v1:
  - paths already classified `GENERATED`;
  - paths already classified `VENDORED`;
  - blobs larger than 1,000,000 bytes;
- leaves `UNKNOWN` surfaces capture eligible rather than guessing them away;
- retains old/new object SHA, type, size, revision, diff-run, planner-run, and
  tracking provenance.

Planning runs use `RunType.OTHER` because no bytes are captured in this stage.

## Test and live replay provenance

Temporary read-only workflow run `33022098111` executed the full repository test
suite and replayed all three frozen V2-P0 failure intervals.

```text
229 passed
```

The replay also asserted that the known high-value miss location from each
frozen interval remained capture eligible. These paths are evaluation checks,
not planner exceptions.

| Repository | Changed leaf paths | Previous capture paths | Current capture paths | Suppressed paths | Known miss retained |
| --- | ---: | ---: | ---: | ---: | --- |
| CopilotKit/OpenBot | 41 | 41 | 41 | 0 | yes |
| openclaw/openclaw | 1,291 | 1,269 | 1,269 | 22 | yes |
| NousResearch/hermes-agent | 147 | 146 | 146 | 1 | yes |

The suppressed OpenClaw and Hermes paths were large blobs. In the replay, each
suppressed modified path produced a large-blob decision on both revision sides,
so the side-level reason counts were 44 and 2 respectively.

## Interpretation boundary

The planner now answers a reproducible operational question:

```text
which exact changed Git path/revision sides should be fetched as files,
which absent sides should be requested to retain MISSING state,
and which deterministic non-file/low-value sides should not be fetched?
```

It does **not** answer which remaining changed files are architecturally
important.

The live numbers are the next measurement: byte-capture planning reduces
OpenClaw only from 1,291 changed paths to 1,269 requested paths per revision.
That is useful for storage/trust-boundary correctness, but it is nowhere near an
attention-sized candidate set. Broad suppression by TEST, DOCS, CONFIG, or
UNKNOWN would be unjustified because the frozen misses demonstrate that
mechanism-level value can live outside ordinary source files.

## Next measured bottleneck

Proceed with **deterministic candidate reduction / interval segmentation** before
semantic `ChangeInterpretation`.

The next slice should preserve every factual path delta while producing smaller
review units using evidence that does not guess semantic importance. Candidate
approaches to evaluate include:

1. segment high-velocity baseline-to-current spans by exact intervening Git
   commits rather than treating 1,291 paths as one monolithic interval;
2. group paths within each segment by deterministic repository/path structure;
3. retain explicit suppression/grouping provenance and never discard UNKNOWN;
4. verify that the frozen high-value miss locations remain represented without
   hard-coded exceptions;
5. only after candidate volume is materially reduced, capture eligible bytes and
   feed deterministic extraction/StructuralDelta into later interpretation.

M6.5/embeddings remain deferred.

## Governance

The temporary replay workflow is removed before merge. Workflow run
`33022098111` remains immutable execution provenance.
