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
ADAPTER_VERSION = "zai-glm-5.3.packet-v13"

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

BASE.ADAPTER_VERSION = ADAPTER_VERSION
BASE.SYSTEM_RULES = BASE.SYSTEM_RULES.rstrip() + "\n\n" + ATTENTION_V13_RULES.strip() + "\n"

SYSTEM_RULES = BASE.SYSTEM_RULES
REVIEW_WORTHINESS_PROVENANCE = BASE.REVIEW_WORTHINESS_PROVENANCE
INVOKE_TIMEOUT_SECONDS = BASE.INVOKE_TIMEOUT_SECONDS
MAX_TIMEOUT_RETRIES = BASE.MAX_TIMEOUT_RETRIES
MAX_SEMANTIC_REPAIRS = BASE.MAX_SEMANTIC_REPAIRS
MAX_INFERENCE_WORKERS = BASE.MAX_INFERENCE_WORKERS
packet_prompt = BASE.packet_prompt
repair_prompt = BASE.repair_prompt
normalize = BASE.normalize
semantic_reference_fields = BASE.semantic_reference_fields
support_repair_reference = BASE.support_repair_reference
infer_packet = BASE.infer_packet
infer_packets = BASE.infer_packets
main = BASE.main


if __name__ == "__main__":
    raise SystemExit(main())
