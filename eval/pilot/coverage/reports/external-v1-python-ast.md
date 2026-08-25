# External pilot deterministic-evidence coverage — after Python AST extraction

Coverage ID: `external-golden-evidence-v1`

This is the fifth live execution of the same external coverage corpus. Historical 4/12, 6/12, 7/12, and 8/12 reports remain preserved.

## Live execution provenance

- One-time live workflow run: `32848352853`
- Branch head executed: `917ce40f2b885af1e21a0831cab0f4e1eab429cf`
- Offline suite before live capture: **53 passed**
- Live pinned capture/extraction step: **success**
- GitHub token permissions: read-only `contents: read`, `metadata: read`
- Coverage specification: `eval/pilot/coverage/external-v1.yaml`
- Prior post-commit baseline: **8/12 (66.7%)**

## Result

- Cases: **4**
- Evidence requirements: **12**
- Recovered: **10**
- Gaps: **2**
- Coverage fraction: **0.833**
- Absolute improvement over prior run: **+2 requirements**
- Coverage progression: **33.3% → 50.0% → 58.3% → 66.7% → 83.3%**

| Case | Before Python AST | After | Change |
| --- | ---: | ---: | ---: |
| `external-openbot-capability-authority` | 1/3 | **1/3** | 0 |
| `external-openclaw-sandbox-posture` | 3/3 | **3/3** | 0 |
| `external-hermes-process-containment` | 1/3 | **3/3** | +2 |
| `external-opd-source-type` | 3/3 | **3/3** | 0 |

## Newly recovered evidence

### Hermes implementation structure

`hermes-containment-2` is now recovered from exact Python AST facts in `tools/environments/local.py`:

- `LocalEnvironment._kill_process` function range: `L1858:C4-L1980:C20`
- nested `LocalEnvironment._kill_process._sweep_escaped_descendants`: `L1927:C16-L1949:C36`
- descendant snapshot assignment using `psutil.Process(proc.pid).children(recursive=True)`: `L1923:C20-L1923:C83`
- escaped-survivor `child.kill()` call: `L1947:C28-L1947:C40`
- process-group SIGTERM call: `L1952:C20-L1952:C51`
- process-group SIGKILL call: `L1966:C20-L1966:C51`

These are syntax facts. LemmaMind does not convert them into a claim that descendant containment is complete or correct.

### Hermes regression-test structure

`hermes-containment-3` is now recovered from exact AST facts in `tests/tools/test_local_setsid_descendant_sweep.py`:

- `test_timeout_kill_reaps_setsid_grandchild`: `L49:C0-L104:C16`
- `test_kill_process_survives_psutil_snapshot_failure`: `L113:C0-L148:C37`
- calls to `env.execute`, `_wait_for_pid_exit`, `env._kill_process`, and the relevant `monkeypatch.setattr` sites
- assertion syntax covering grandchild exit and SIGTERM / `killpg_calls` expectations

The test module's authored docstrings are preserved separately as `python-docstring.v1` `SourceAssertion` records. Test syntax is evidence about what the test asserts, not proof that the runtime property holds in every environment.

## Extraction volume

For the two pinned Hermes Python artifacts, the AST-enabled extraction emitted:

- **769** `python-ast.v1` `EvidenceFact` records
- **53** `python-docstring.v1` `SourceAssertion` records
- **777** total deterministic file facts including the pre-existing artifact-path facts

The volume is intentionally source-structural rather than semantic. Future profiling should select relevant subsets rather than treating every AST record as equally important.

## Remaining gaps

Only two golden-evidence requirements remain, both in the OpenBot TypeScript implementation case:

- `openbot-authority-2`
- `openbot-authority-3`

They are still labeled `source-code-semantic-facts` in the historical coverage taxonomy, but the implementation direction remains narrower: preserve TypeScript comments/doc comments as `SourceAssertion`, then add version-pinned syntax/AST facts only for the exact capability-grant and gateway-control structures required by the golden case.

## Trust boundary

`python-ast.v1`:

- decodes captured `.py` artifacts as UTF-8;
- parses with Python's standard-library `ast` module;
- never imports, executes, or evaluates captured source;
- emits exact line/column ranges;
- records functions/classes, calls, assignments, assertions, and `try` structure;
- keeps authored docstrings in `SourceAssertion` rather than `EvidenceFact`;
- fails closed on invalid Python syntax.

## Interpretation boundary

The 10/12 result means current deterministic acquisition/extraction can recover the selected source-addressed evidence for ten requirements. It does **not** mean LemmaMind can automatically generate or validate all four golden `Observation` objects without reasoning and review.

## Next measured slice

TypeScript comments + deterministic syntax structure for the two OpenBot requirements. This introduces a new parser dependency/trust surface, so it should be version-pinned and evaluated narrowly against the existing golden case rather than generalized into a broad semantic analyzer.
