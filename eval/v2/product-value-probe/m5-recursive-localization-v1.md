# M5 recursive changed-path localization — V2-P0 replay

## Result

**PASS for the recursive-localization sub-slice. Full M5 remains open.**

This replay addresses the first deterministic defect exposed by the V2-P0 `CHANGE_SIGNAL` failure: V1 could prove that a root tree changed but could not enumerate the exact changed leaf paths beneath that root.

The new slice adds:

- complete recursive Git-tree capture bound to one exact `SourceRevision`;
- fail-closed rejection of provider responses marked `truncated`;
- immutable content-addressed recursive-tree artifacts and capture provenance;
- deterministic leaf-level `GitPathDelta` records (`added`, `removed`, `modified`, `type_changed`);
- suppression of parent directory-tree hash churn as carrier metadata rather than candidate changes;
- deterministic path-surface labels (`SOURCE`, `TEST`, `DOCS`, `CONFIG`, `WORKFLOW`, `MANIFEST`, `LOCKFILE`, `GENERATED`, `VENDORED`, `UNKNOWN`);
- Structural-or-deeper tracking enforcement for recursive tree acquisition.

No repository code is executed. No model output, embeddings, learned ranking, semantic importance, or `ChangeInterpretation` is introduced.

## Test gate

Temporary read-only workflow run `33018898144` executed the permanent test suite plus a live replay against the three frozen V2-P0 failure intervals.

The repository's permanent pull-request CI (`.github/workflows/test.yml`) remains the merge gate for PR #30; the live replay is additional execution provenance rather than a substitute for final-head CI.

The test suite reached:

```text
220 passed
```

The live replay used GitHub read authority only and asserted that one known high-value miss location from each frozen interval appeared in the recursively localized path set. Those target paths are evaluation checks, not hard-coded localization exceptions.

## Live replay

| Repository | Frozen interval | Changed leaf paths | Frozen miss location checked | Localized |
| --- | --- | ---: | --- | --- |
| CopilotKit/OpenBot | `43ea5c1… → e8aa344…` | 41 | `app/src/lib/attention/queries.ts` | yes |
| openclaw/openclaw | `20eef85… → aec260b…` | 1,291 | `src/agents/sticky-model-selection.ts` | yes |
| NousResearch/hermes-agent | `b2bd1ac… → a6d6060…` | 147 | `hermes_cli/update_contract.py` | yes |

### Surface distribution

OpenBot:

```text
CONFIG    4
DOCS      2
SOURCE   24
TEST      9
UNKNOWN   1
WORKFLOW  1
```

OpenClaw:

```text
CONFIG    61
DOCS      69
LOCKFILE   1
MANIFEST   2
SOURCE    679
TEST      396
UNKNOWN    82
WORKFLOW    1
```

Hermes Agent:

```text
CONFIG   18
DOCS      3
SOURCE   68
TEST     53
UNKNOWN   5
```

## Interpretation boundary

The replay proves a narrower claim than “change intelligence is solved.”

It establishes that LemmaMind can now deterministically transform:

```text
root tree changed
```

into:

```text
these exact leaf Git paths changed
```

while retaining exact old/new object identity and source-revision provenance.

It does **not** establish that the resulting set is small enough for human review.

The OpenClaw interval is the critical counterexample: localization reduced an opaque repository-level change to an exact set, but **1,291 changed leaf paths is still not an attention product**. This confirms that the next full-M5 sub-slice must perform affected-file planning and deterministic candidate reduction rather than moving into M6.5 representation or semantic embeddings.

## Next sub-slice

Proceed with deterministic affected-file/candidate planning over `GitPathDelta`:

1. distinguish capture-worthy blobs from directory/submodule/type-carrier changes;
2. preserve both sides for modified files and the existing side for add/remove transitions;
3. deterministically identify generated/vendored/large or otherwise low-value capture surfaces without silently discarding unknowns;
4. group or segment high-velocity intervals so a repository such as OpenClaw does not become one 1,291-path review item;
5. then capture eligible changed artifacts and run the existing evidence/StructuralDelta machinery over the affected set.

Semantic `ChangeInterpretation` remains downstream of this deterministic reduction gate.

## Governance

The temporary workflow is not part of the permanent product surface and is removed before merge. Workflow run `33018898144` remains immutable execution provenance.
