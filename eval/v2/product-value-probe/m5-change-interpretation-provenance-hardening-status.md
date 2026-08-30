# M5 ChangeInterpretation Provenance Hardening — Status

Status: **provenance hardening validated; semantic product gate remains OPEN**.

This note records implementation-validation status only. It does **not** close the frozen M5 ChangeInterpretation product evaluation, change its criteria, or authorize later roadmap stages.

## Validated runtime head

The current provenance-hardening runtime/test implementation was committed at:

- `35af88f767066bd89167132e23219fac1abe9250` — `Persist exact interval segmentation profiles`

This extends the earlier upstream-lineage hardening at `fae18faf47c09475b985048deb6790f36062912d` and closes the deterministic boundary used before semantic interpretation by requiring packet construction/authentication to preserve and reauthenticate the exact upstream generation context, including:

- recursive Git path-diff provenance;
- interval segmentation provenance reconstructed against the authenticated path-diff generation;
- a durable exact `IntervalSegmentationGeneration` profile containing the configured `max_paths_per_candidate`, so valid packet-safe candidates remain authenticatable even when the upstream segmentation bound is greater than 50;
- affected-file planning provenance reconstructed against the authenticated path diff, tracking policy, and exact capture scope;
- completed extraction/change/reduction lineage;
- the exact ordered artifact-extractor profile as durable packet-generation provenance rather than a profile inferred from outputs;
- repeated extractor descriptors preserved in their original order when upstream extraction legitimately uses them;
- bounded assertion preview selection that preserves previous/current snapshot visibility under constrained preview budgets.

Both temporary validation harnesses intentionally failed closed: each applied staged changes, compiled the modified modules/tests, ran the complete pytest suite, and only then committed validated runtime/test state while removing temporary staging files.

## Validation evidence

Primary upstream-provenance hardening workflow:

- workflow run: `33290492830`
- job: `99201154945`
- result: **success**
- complete pytest execution: **302 tests completed green**
- committed runtime/test state: `fae18faf47c09475b985048deb6790f36062912d`

Exact segmentation-profile / repeated-extractor follow-up workflow:

- workflow run: `33291098525`
- job: `99202748496`
- result: **success**
- complete pytest execution: **305 tests completed green**
- committed runtime/test state: `35af88f767066bd89167132e23219fac1abe9250`

The follow-up added regressions for both fresh exact-head Codex findings: a segmentation configured with `max_paths_per_candidate=100` that produces a one-path packet-safe candidate, and an exact ordered extractor profile containing repeated silent descriptors.

The bot-authored runtime push may not create a normal PR test job because GitHub suppresses recursive workflow execution from `github-actions[bot]`. This user-authored status update exists in part to trigger permanent PR CI on the unchanged runtime head. The permanent exact-head PR CI result should therefore be read from the workflow generated for the commit containing this note, not from any bot-authored push status.

## Product gate remains open

The frozen semantic replay has **not** been completed. The previous bounded GitHub Copilot CLI preflight reached the CLI with `CopilotRequests: write`, but the first inference request was rejected before model execution with `Access denied by policy settings`.

Therefore none of the frozen semantic product thresholds are claimed yet, including the `303 -> <=50` attention-collapse target, anchor visibility, or `>=8/10` known high-value mechanism recall.

The provider-policy failure is an execution-environment blocker, not evidence that the semantic product gate passed or failed.

## Roadmap boundary

Until the frozen semantic replay can run prospectively and its evidence is reviewed:

- PR #34 remains a provenance/semantic implementation candidate rather than a completed product-value gate;
- M6.5 embeddings/representation remain deferred;
- no learned ranking, autonomous promotion, or action execution is authorized;
- the frozen evaluation specification remains unchanged.
