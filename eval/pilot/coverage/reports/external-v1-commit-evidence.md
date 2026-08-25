# External pilot deterministic-evidence coverage — after commit evidence

Coverage ID: `external-golden-evidence-v1`

This is the fourth live execution of the same external coverage corpus. Historical 4/12, 6/12, and 7/12 reports remain preserved.

## Live execution provenance

- One-time live workflow run: `32847234440`
- Branch head executed: `221898e3c7e4c7dc0a6d9a15be64c10f6ec45121`
- Offline suite before live capture: **47 passed**
- Live pinned capture/extraction step: **success**
- GitHub token permissions: read-only `contents: read`, `metadata: read`
- Coverage specification: `eval/pilot/coverage/external-v1.yaml`
- Prior post-tree baseline: **7/12 (58.3%)**

## Result

- Cases: **4**
- Evidence requirements: **12**
- Recovered: **8**
- Gaps: **4**
- Coverage fraction: **0.667**
- Absolute improvement over prior run: **+1 requirement**
- Coverage progression: **33.3% → 50.0% → 58.3% → 66.7%**

| Case | Before commit evidence | After | Change |
| --- | ---: | ---: | ---: |
| `external-openbot-capability-authority` | 1/3 | **1/3** | 0 |
| `external-openclaw-sandbox-posture` | 3/3 | **3/3** | 0 |
| `external-hermes-process-containment` | 0/3 | **1/3** | +1 |
| `external-opd-source-type` | 3/3 | **3/3** | 0 |

## Newly recovered evidence

### Hermes — pinned change statement

`hermes-containment-1` is now recovered from a canonical commit artifact tied to the pinned `SourceRevision.commit_sha`:

- commit SHA: `41447a6d7063b2772b0c2f26a5b22d9bd444fb43`
- tree SHA: `bb6bb716681c12832b3d8e73a59d7a472774d8a2`
- parent count: **2**
- verification state: source reports the commit as verified/valid
- matched source assertion: `$git/commit#message`

The commit message explicitly describes sweeping `setsid` descendants after the local timeout group-kill. LemmaMind preserves that text as `SourceAssertion`; it does **not** treat the message alone as proof that the implementation actually performs the described containment behavior.

The canonical commit artifact produced **9** deterministic `EvidenceFact` records covering commit/tree identity, parent structure, author/committer timestamps, and verification metadata, plus one commit-message `SourceAssertion`.

## Provenance model

```text
SourceRevision.commit_sha
        ↓
GitHub commit endpoint (exact SHA)
        ↓
canonical immutable commit metadata
        ↓
SHA-256 content-addressed Artifact
        ↓
CaptureManifest
        ↓
┌───────────────────────────┬─────────────────────────┐
│ deterministic metadata    │ authored commit message │
│ EvidenceFact              │ SourceAssertion         │
└───────────────────────────┴─────────────────────────┘
```

A returned commit SHA or tree SHA that disagrees with the pinned `SourceRevision` fails before capture persistence.

## Remaining gaps

The commit/change evidence gap is eliminated for the current corpus. Four requirements remain:

- `source-code-semantic-facts`: **3**
- `test-code-semantic-facts`: **1**

Those labels remain coverage categories rather than permission to store semantic conclusions as deterministic facts. The next implementation should use language-specific syntax structure and leave behavioral interpretation to later `Observation` reasoning.

## Interpretation boundary

Commit metadata proves which commit/tree/parents/timestamps the source API reports at the pinned revision. The commit message proves only what the author/merger stated. Hermes containment behavior still requires source- and test-structure evidence before the full golden observation can be reconstructed deterministically.

## Next measured slice

Implement Python AST structural facts first. The Hermes source and test artifacts can potentially close two remaining requirements using Python's standard-library `ast` without introducing a new parser dependency or a generic semantic-analysis layer.
