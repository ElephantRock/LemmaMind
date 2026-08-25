# External pilot deterministic-evidence coverage — after Git root-tree evidence

Coverage ID: `external-golden-evidence-v1`

This is the third live execution of the same external coverage corpus. Historical 4/12 and 6/12 reports remain preserved.

## Live execution provenance

- One-time live workflow run: `32831275075`
- Branch head executed: `e52cf51d6220a64a3c80b69608a658ffd5457c3e`
- Offline suite before live capture: **42 passed**
- Live pinned capture/extraction step: **success**
- GitHub token permissions: read-only `contents: read`, `metadata: read`
- Coverage specification: `eval/pilot/coverage/external-v1.yaml`
- Prior post-Markdown baseline: **6/12 (50.0%)**

## Result

- Cases: **4**
- Evidence requirements: **12**
- Recovered: **7**
- Gaps: **5**
- Coverage fraction: **0.583**
- Absolute improvement over prior run: **+1 requirement**
- Coverage progression: **33.3% → 50.0% → 58.3%**

| Case | Before tree evidence | After | Change |
| --- | ---: | ---: | ---: |
| `external-openbot-capability-authority` | 1/3 | **1/3** | 0 |
| `external-openclaw-sandbox-posture` | 3/3 | **3/3** | 0 |
| `external-hermes-process-containment` | 0/3 | **0/3** | 0 |
| `external-opd-source-type` | 2/3 | **3/3** | +1 |

## Newly recovered evidence

### OPD source role — complete root membership

`opd-source-3` is now recovered from an exact, non-recursive Git tree artifact tied to the pinned `SourceRevision.tree_sha`:

- commit revision: `e4b5e7334ccd3437ccab8d4eef770ed02c4f9934`
- root tree SHA: `c159887c873d5003aec7dabb0ee579f22a18e82b`
- response truncated: `false`
- exact root entries:
  - `.claude`
  - `CITATION.cff`
  - `CONTRIBUTING.md`
  - `LICENSE`
  - `README.md`

The coverage check requires exact membership and a non-truncated response. Merely finding the four curation files would not pass if an additional root implementation entry such as `src/` were present.

Matched deterministic facts:

- `$git/tree/root#/entry_paths`
- `$git/tree/root#/truncated`

The captured root tree produced **24** deterministic `EvidenceFact` records covering tree identity, truncation state, entry count/path set, and per-entry Git type/mode/SHA/size where supplied.

## Provenance model

The Git tree path is deliberately independent from hand-picked repository files:

```text
SourceRevision.tree_sha
        ↓
GitHub Git Trees endpoint (non-recursive)
        ↓
canonical root-tree JSON bytes
        ↓
SHA-256 content-addressed Artifact
        ↓
CaptureManifest
        ↓
git-root-tree.v1 EvidenceFact
```

A tree SHA mismatch fails before capture persistence. An exact-root coverage requirement fails if the response is truncated, any expected entry is missing, or any unexpected entry appears.

## Remaining gaps

The complete-repository-tree gap is eliminated for the current corpus. Five requirements remain:

- `commit-metadata-and-change-facts`: **1**
- `source-code-semantic-facts`: **3**
- `test-code-semantic-facts`: **1**

As before, the code-related labels identify missing evidence classes. They are not permission to store architectural or behavioral conclusions as deterministic facts.

## Interpretation boundary

The tree proves exact Git root membership at the pinned revision. It does not itself prove that the repository is a research index; that classification remains a reviewed interpretation supported jointly by tree facts and README `SourceAssertion` records.

## Next measured slice

The next P1 capability is durable commit metadata/change evidence for the Hermes case. The current GitHub capture already retrieves the commit to resolve `commit_sha` and `tree_sha`; the missing work is to preserve a canonical source artifact and split it into deterministic metadata facts plus commit-message `SourceAssertion` evidence.
