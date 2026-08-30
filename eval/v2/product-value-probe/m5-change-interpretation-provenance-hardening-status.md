# M5 ChangeInterpretation Provenance Hardening — Status

Status: **provenance hardening validated; semantic product gate remains OPEN**.

This note records implementation-validation status only. It does **not** close the frozen M5 ChangeInterpretation product evaluation, change its criteria, or authorize later roadmap stages.

## Validated runtime head

The provenance-hardening runtime/test implementation was committed at:

- `fae18faf47c09475b985048deb6790f36062912d` — `Harden packet upstream provenance authentication`

The hardening closes the deterministic lineage boundary used before semantic interpretation by requiring packet construction/authentication to preserve and reauthenticate the exact upstream generation context, including:

- recursive Git path-diff provenance;
- interval segmentation provenance reconstructed against the authenticated path-diff generation;
- affected-file planning provenance reconstructed against the authenticated path diff, tracking policy, and exact capture scope;
- completed extraction/change/reduction lineage;
- the exact ordered artifact-extractor profile as durable packet-generation provenance rather than a profile inferred from outputs;
- bounded assertion preview selection that preserves previous/current snapshot visibility under constrained preview budgets.

The temporary validation harness intentionally failed closed: it applied the staged hardening, compiled the modified modules/tests, ran the complete pytest suite, and only then committed the validated runtime/test state while removing all temporary staging files.

## Validation evidence

Temporary one-shot hardening workflow:

- workflow run: `33290492830`
- job: `99201154945`
- result: **success**
- complete pytest execution: **302 tests completed green**

The workflow then deleted its temporary payload/workflow machinery and pushed the validated commit `fae18faf47c09475b985048deb6790f36062912d`.

The normal pull-request workflow generated for that bot-authored push was run `33290507028`, but GitHub concluded it as `action_required` without creating test jobs. This is workflow-trigger behavior for the bot-authored push, not a LemmaMind test failure. This user-authored status commit exists in part to trigger permanent PR CI on an otherwise unchanged runtime head.

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
