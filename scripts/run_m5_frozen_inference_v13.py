#!/usr/bin/env python3
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


BASE_PATH = Path(__file__).with_name("run_m5_frozen_inference.py")
SPEC = spec_from_file_location("m5_frozen_inference_v12_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

BASE_ADAPTER_VERSION = BASE.ADAPTER_VERSION
ADAPTER_VERSION = "zai-glm-5.3.packet-v16"

ATTENTION_V13_RULES = """V13 attention-calibration clarification. These rules do not add a new product criterion; they make the existing five conjunctive tests and facet/canonicalization rules harder to satisfy by implication alone.
Evidence-burden rule: interpret only when the packet directly establishes each required element of review-span, review-leverage, durable-knowledge, and boundary-effect. A plausible downstream consequence, a suggestive identifier, a test name, a comment rationale, cross-file breadth, or the fact that state persists is not evidence for a missing element. If any required element depends on extrapolating what another component, later phase, operator, or consumer might do, decline.
Scope-collapse rule: before returning interpret, mentally remove repository-specific nouns, file/function names, transport/storage carriers, UI labels, and implementation technique. If the remaining knowledge is only an allowed-value set, request-shape validation, configuration precedence, local routing choice, helper/callback ownership, plugin or tool registration, cache/baseline selection, pagination/windowing, retry count, timeout tuning, cleanup escalation, local deduplication, local reset behavior, presentation confirmation, or another single-execution implementation rule, decline unless the packet directly proves one of the existing qualifying cross-boundary contracts and its changed consequential outcome.
Authority-governance guard: authority_governance is reserved for a directly evidenced stable rule about which distinct principal, trust domain, or security authority may exercise a capability, or how credentials/secrets are isolated across such a boundary. Do not relabel ordinary validation, enum/allowlist constraints, local owner lookup, routing, configuration source selection, plugin/tool availability, path binding, UI confirmation, or capability dispatch as authority merely because one outcome is admitted and another is denied. If distinct principals or trust domains and the authority boundary are not directly evidenced, use another qualifying type only if all five tests pass; otherwise decline.
Failure guard: failure requires a changed durable terminal disposition or a changed cross-boundary recovery handoff that another independent phase, participant, consumer, or operator must rely on. Local reconnect/retry policy, error wording, cleanup escalation, fallback selection, status mapping, or an implementation repair that restores an already-declared obligation is not enough by itself.
Temporal-correctness guard: temporal_correctness requires a directly evidenced invariant spanning independently progressing participants or independently executed lifecycle phases, with externally or durably consumed state at risk. In-process ordering, adjacent duplicate suppression, pagination/window selection, cache invalidation, local stale-state reset, or sequencing inside one request/session is insufficient unless the packet directly establishes the qualifying non-local invariant and consequential state effect.
Project-state guard: project_state is for an authoritative changed support, compatibility, governance, schema-consumer, or declared project-state contract that external consumers/operators or later lifecycle phases must rely on. Internal schema fold-in, migration scaffolding, generated alignment, plan text, bookkeeping, or documentation of implementation detail is not project_state merely because it is durable or documented.
Facet convergence rule: storage, service, client/UI, documentation, tests, migrations, and generated projections of one governing mechanism must converge on exactly the same short mechanism label and the same canonical interpretation type when the packet directly establishes that governing mechanism. Remove facet-specific adjectives, enforcement technique, phase, carrier, positive/negative wording, and presentation details from the label. If a facet packet cannot directly support the same governing rule-level label without importing facts from another packet, decline that facet instead of emitting a parallel mechanism item.
Canonical-type rule: choose the type that names the governing contract, not the evidence surface or implementation symptom. Do not split one governing mechanism into introduction/modification/failure/authority/project_state variants across facets merely because different packets expose different stages of the same lifecycle. When the packet directly supports only a subordinate facet and not the governing type, decline rather than inventing a second review item.
Human-attention rule: review-worthiness is about reusable governing knowledge a future reviewer must preserve, not whether a change is real, useful, externally visible, security-adjacent, persistent, or well tested. When the packet supports a concrete implementation improvement but does not directly establish independently reusable governing knowledge across a qualifying span, decline.
"""

ATTENTION_V14_RULES = """V14 independent-boundary clarification. Apply these rules after the existing review-worthiness tests; they narrow how evidence may satisfy those tests without changing the tests themselves.
Independent-boundary proof rule: a qualifying review span must be directly evidenced as a rule that crosses at least one genuinely independent boundary: distinct security principals or trust domains, separately executing lifecycle phases, independently scheduled participants, or an authoritative producer and a separate durable/external consumer. Merely touching several files, layers, functions, tests, UI components, callbacks, helpers, routes, or configuration sources does not prove such a span. If the independence of both sides and the changed rule connecting them are not explicit in the packet, decline.
Authority-versus-ownership rule: words such as owner, creator, dispatcher, session, role, profile, workspace, node, plugin, tool, or agent do not by themselves identify a security principal or trust domain. Local object ownership, routing ownership, callback selection, capability registration, path selection, configuration precedence, and same-principal allow/deny validation are not authority_governance. Use authority_governance only when the packet directly establishes that one principal or trust domain gains, loses, delegates, or is prevented from exercising a capability across a distinct authority boundary, or that credentials/secrets are isolated across that boundary.
Authoritative-surface rule: tests, generated files, migration scaffolding, release notes, plans, translations, and documentation are normally evidence about a governing mechanism rather than separate review mechanisms. Decline such a facet when it only verifies, mirrors, migrates, names, or explains a rule whose authoritative behavior lies elsewhere. A consumer/UI surface may qualify only when the packet itself directly establishes an externally consumed read/action contract over durable or cross-phase state; presentation alone is insufficient.
Persistence qualification rule: persisted configuration, a database row, a cache entry, a session record, a registry entry, or state surviving within one process/session is not durable-knowledge evidence by itself. The packet must directly show that the changed rule is authoritative across a later independent invocation, restart, participant, lifecycle phase, or external consumer. Otherwise treat persistence as an implementation carrier and decline unless another qualifying boundary is directly proven.
Recovery novelty rule: retry, reconnect, rewind, cleanup, teardown, fallback, stale-state refresh, status mapping, and timeout handling are implementation recovery techniques unless the packet directly establishes a newly changed durable terminal disposition or a cross-boundary recovery handoff that a separate participant or later phase must consume. Restoring an already-declared behavior, making cleanup more reliable, or changing only local recovery sequencing is not a separate failure mechanism.
Temporal independence rule: temporal_correctness requires independently progressing actors, tasks, processes, devices, or lifecycle epochs whose relative timing can change an externally consumed or durable outcome. UI rerender order, callback order, same-request sequencing, local event ordering, adjacent stream reconciliation, and single-component state reset are insufficient unless the packet directly proves the independent participants and consequential non-local state risk.
Rule-versus-facet test: before interpret, state the mechanism as one short imperative that an independent future implementer would need to preserve without knowing the current file names, UI labels, helper names, storage choice, or test structure. If the imperative collapses to how this implementation performs validation, routing, storage, cleanup, synchronization, presentation, migration, or configuration selection, decline. If the packet shows only a subordinate facet of a broader rule and cannot independently prove that broader governing rule, decline rather than creating another mechanism item.
Self-contained evidence rule: do not import facts from neighboring packets, repository familiarity, likely architecture, naming conventions, test intent, documentation links, or plausible downstream behavior. Every principal, participant, phase, durable consumer, authority transfer, terminal disposition, or consequential state effect needed for interpret must be supported inside the current packet. When one of those elements is only inferred, decline.
"""

ATTENTION_V16_RULES = """V16 evidence-role and conjunct-proof clarification. These rules narrow what counts as direct proof for the existing review-worthiness tests; they do not add a product criterion, change evidence eligibility, or change any frozen gate.
Proof-source rule: authored prose in comments, docstrings, test names, test descriptions, plans, release notes, or documentation may directly establish a contract only to the extent that the source itself is evidence of that contract under the existing five tests. A SourceAssertion remains fully eligible for what its source directly declares, including an authoritative changed project-state declaration or a behavioral contract assertion that itself directly proves the governing rule and boundary effect. It may not substitute for a missing producer, consumer, authority boundary, lifecycle phase, terminal disposition, or consequential state transition that the source merely says exists elsewhere. Do not require runtime implementation bytes solely because an eligible evidence surface is a test or document; decline only when a required conjunct depends on unseen behavior beyond that surface.
Facet-evidence rule: tests, documentation, generated surfaces, translations, migrations, plans, fixtures, and harnesses remain eligible under the existing weak-prior rules and are not hard suppression categories. Such a packet may originate a review item only when its own changed content directly establishes all five tests without importing an authoritative behavior, independent participant, consumer, or boundary effect from outside the packet. An end-to-end behavioral test that directly exercises the qualifying sides and changed outcome may qualify; a changed expectation, fixture, comment, or docstring that merely describes an unseen production path may not. Documentation may qualify when the document itself is the authoritative changed project-state contract; documentation that merely explains unseen runtime behavior does not supply the missing runtime proof.
Uncertainty-conjunct rule: uncertainty may remain only about details that are not required for review-worthiness. If an honest uncertainty note would need to say that the authoritative implementation or consumer is outside the packet, that changed behavior cannot be distinguished from newly added verification, that the independent participant or phase is inferred, or that the consequential effect is not shown, then a required conjunct is unresolved and the decision must be decline.
Two-sided boundary rule: independently reusable cross-boundary knowledge requires direct packet evidence for both sides of the qualifying boundary and for the changed rule connecting them. Words such as later, next launch, another process, remote, operator, external, durable, persistent, owner, authenticated, or consumer are not proof of an independent side when they occur only in rationale prose. A write plus a claim that something later reads it is insufficient unless the packet directly evidences the separate reader/consumer or an authoritative interface whose consumption is itself the changed contract.
Authority-identity rule: admission, approval, ownership, authentication, scoping, or a fail-closed guard is not authority_governance unless the packet directly distinguishes the principals or trust domains on both sides and directly shows the capability or credential that crosses, is delegated across, or is denied across that boundary. A same-principal policy gate, local lifecycle owner, reviewer decision, configuration writer, or authenticated request scope remains implementation policy unless that distinct authority relation is explicit.
Terminal-disposition proof rule: an exit code, refusal, quarantine flag, cleanup escalation, fallback choice, retry outcome, or status mapping is not a failure mechanism merely because another tool could observe it. The packet must directly evidence the changed durable terminal disposition or the separate participant/operator handoff that relies on it; a test expectation or explanatory assertion about an unseen caller is insufficient.
Temporal-conflict proof rule: temporal_correctness requires direct evidence of at least two independently schedulable actors or lifecycle epochs and the conflicting read/write, ownership, or ordering relation that can alter a durable or external outcome. A race regression test, generation counter, reset event, adjacent-message rule, compare-and-delete helper, or the words concurrent/race/restart do not establish that span when the other actor or consequential outcome is absent from the packet.
Mechanism-language neutrality rule: labels and prose such as contract, invariant, lifecycle, admission, authority, trust boundary, durable, fail-closed, externally consumed, or future implementers must preserve carry no evidentiary weight by themselves. Apply the five tests to the underlying packet facts after removing those words. If the qualifying span disappears, decline.
"""

REPAIR_V15_RULES = """V15 provider-output repair reliability clarification. These rules apply only after a provider response has already failed deterministic parsing or validation. They do not change the five review-worthiness tests, evidence eligibility, canonicalization, or any frozen product gate.
Serialization rule: emit exactly one compact single-line JSON object with no markdown, commentary, code fence, trailing text, or literal control characters inside string values. Use normal JSON escaping for quotation marks, backslashes, and embedded control characters. Complete every opened string, array, and object before returning.
Malformed-output reconstruction rule: when the rejected provider response is not parseable JSON, reconstruct a fresh response from the CandidateEvidencePacket and deterministic repair context. Do not continue, splice, quote, or imitate malformed or apparently truncated raw output.
Support-copy rule: every support object must be copied character-for-character from the supplied exact semantic support choices or exact support allowlist. Do not derive, regenerate, shorten, complete, or infer an identifier from evidence prose, hashes, neighboring packets, repository familiarity, or a previous rejected output. Prefer the smallest sufficient support set and exactly one semantic support when one is sufficient.
Semantic-lock serialization rule: when semantic_reference is supplied, preserve every supplied non-support semantic field exactly and perform only JSON serialization plus exact support selection. Do not paraphrase the preserved mechanism, summary, interpretation types, or uncertainty notes.
Repair-economy rule: when no semantic_reference exists, keep repaired prose concise and limited to what is necessary to satisfy the unchanged output contract and evidence-grounding requirements. Do not repeat the packet, narrate the repair process, or add explanatory material outside the JSON fields.
Fail-closed rule: if a valid exact semantic support cannot be selected without changing a preserved interpretation, keep decision=interpret with an empty supports array so deterministic validation rejects the repair. Never convert a supported interpretation to decline merely to make serialization easier.
"""

BASE.ADAPTER_VERSION = ADAPTER_VERSION
BASE.SYSTEM_RULES = (
    BASE.SYSTEM_RULES.rstrip()
    + "\n\n"
    + ATTENTION_V13_RULES.strip()
    + "\n\n"
    + ATTENTION_V14_RULES.strip()
    + "\n\n"
    + ATTENTION_V16_RULES.strip()
    + "\n"
)

SYSTEM_RULES = BASE.SYSTEM_RULES
REVIEW_WORTHINESS_PROVENANCE = BASE.REVIEW_WORTHINESS_PROVENANCE
INVOKE_TIMEOUT_SECONDS = BASE.INVOKE_TIMEOUT_SECONDS
MAX_TIMEOUT_RETRIES = BASE.MAX_TIMEOUT_RETRIES
MAX_SEMANTIC_REPAIRS = BASE.MAX_SEMANTIC_REPAIRS
MAX_INFERENCE_WORKERS = BASE.MAX_INFERENCE_WORKERS
packet_prompt = BASE.packet_prompt
_BASE_REPAIR_PROMPT = BASE.repair_prompt
normalize = BASE.normalize
semantic_reference_fields = BASE.semantic_reference_fields
support_repair_reference = BASE.support_repair_reference

_MALFORMED_OUTPUT_PLACEHOLDER = (
    "<malformed provider output omitted; reconstruct a fresh JSON response from the packet>"
)


def repair_prompt(
    packet: dict,
    *,
    previous_output: str,
    error: Exception,
    repair_attempt: int = 1,
    semantic_reference: dict | None = None,
) -> str:
    malformed_json = semantic_reference is None and isinstance(
        error, BASE.json.JSONDecodeError
    )
    repair_previous_output = (
        _MALFORMED_OUTPUT_PLACEHOLDER if malformed_json else previous_output
    )
    prompt = _BASE_REPAIR_PROMPT(
        packet,
        previous_output=repair_previous_output,
        error=error,
        repair_attempt=repair_attempt,
        semantic_reference=semantic_reference,
    )
    exact_choices = BASE.semantic_support_choices(packet)
    mode_note = (
        "The rejected raw response was malformed JSON and has been deliberately omitted; reconstruct from the packet instead of copying broken text."
        if malformed_json
        else "The rejected response remains available only under the base deterministic repair contract."
    )
    lock_note = (
        "Semantic-lock mode is active: reproduce semantic_reference fields exactly and change only supports plus JSON serialization."
        if semantic_reference is not None
        else "No semantic lock is available because no complete validated semantic reference has been established."
    )
    return (
        prompt.rstrip()
        + "\n\n"
        + REPAIR_V15_RULES.strip()
        + "\n"
        + mode_note
        + "\n"
        + lock_note
        + "\nExact semantic support choices repeated at the final output boundary: "
        + BASE.json.dumps(
            exact_choices,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\nReturn exactly one complete compact single-line JSON object."
    )


BASE.repair_prompt = repair_prompt
infer_packet = BASE.infer_packet
infer_packets = BASE.infer_packets
main = BASE.main


if __name__ == "__main__":
    raise SystemExit(main())
