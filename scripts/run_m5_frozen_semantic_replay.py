#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path

PR34_SHA = os.environ.get("M5_PR34_SHA", "")
if re.fullmatch(r"[0-9a-f]{40}", PR34_SHA) is None:
    raise RuntimeError("M5_PR34_SHA must be an exact 40-character lowercase Git SHA")
SCHEMA_VERSION = "m5-frozen-semantic-replay.v1"

SPECS = {
    "openbot": {
        "repository": "CopilotKit/OpenBot",
        "baseline": "43ea5c11210c485551c25b41a4270c56a58591f1",
        "current": "e8aa34451f73ef2719c22cc557be369d9ea70afb",
        "anchor": "app/src/lib/attention/queries.ts",
        "max_review_items": 5,
        "expected": {
            "interval_candidates": 9,
            "artifact_deltas": 41,
            "structural_deltas": 3612,
            "extraction_gap_paths": 0,
        },
    },
    "openclaw": {
        "repository": "openclaw/openclaw",
        "baseline": "20eef858aafbf6a3c45b0f20366a08192996f91b",
        "current": "aec260b7002cf56232add300f3dd3454c81a10cf",
        "anchor": "src/agents/sticky-model-selection.ts",
        "max_review_items": 35,
        "expected": {
            "interval_candidates": 229,
            "artifact_deltas": 1269,
            "structural_deltas": 356123,
            "extraction_gap_paths": 69,
        },
    },
    "hermes": {
        "repository": "NousResearch/hermes-agent",
        "baseline": "b2bd1ac63ff137a6287ce989d65dccee6b9155e2",
        "current": "a6d6060d6128260d8536d0b92ae0324fff028ffd",
        "anchor": "hermes_cli/update_contract.py",
        "max_review_items": 10,
        "expected": {
            "interval_candidates": 65,
            "artifact_deltas": 146,
            "structural_deltas": 120864,
            "extraction_gap_paths": 0,
        },
    },
}

KNOWN_MECHANISMS = {
    "openbot": [
        "Attention inbox for refusals and stalls derived from append-only audit events, with separate attributed resolution state.",
        "Policy dry-run against historical judged actions before saving a boundary rule, without writing audit decisions during the dry run.",
        "Named undecided routing causes such as unreachable, unparsed, off-roster, unconfident, and one-candidate.",
    ],
    "openclaw": [
        "Configurable model-selection scopes with session/agent/global persistence without broadening configuration-write authority.",
        "Validate a capture batch before publishing files, preventing partial publication after a malformed later response.",
        "Recheck idle/node readiness after waits rather than trusting stale state.",
        "Preserve worker timeouts across clock changes.",
    ],
    "hermes": [
        "Provenance-aware update admission that refuses inappropriate in-place mutation, honors authoritative installation provenance, and fails closed on corrupted markers.",
        "Project completed agent-as-provider tool work into the durable turn without resurrecting completed calls as pending work.",
        "Fail closed on a headless model guard instead of waiting on an unavailable confirmation surface.",
    ],
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(repo_key: str, state_dir: Path) -> int:
    from lemmamind.affected_file_planning import AffectedFileCapturePlanner
    from lemmamind.candidate_evidence_packets import CandidateEvidencePacketService
    from lemmamind.candidate_extraction_gaps import CandidateExtractionGapService
    from lemmamind.candidate_reduction_contracts import CandidateReductionDisposition
    from lemmamind.contracts import SourceRole
    from lemmamind.extraction_diagnostics import GapTolerantExtractionPairService
    from lemmamind.gap_aware_candidate_reduction import GapAwareCandidateFactualReductionService
    from lemmamind.github import GitHubCaptureService
    from lemmamind.interval_segmentation import GitHubIntervalRESTReader, IntervalCandidateSegmentationService
    from lemmamind.objects import ContentAddressedFileStore
    from lemmamind.recursive_tree import RecursiveGitTreeDiffService, TrackingAwareGitHubRecursiveTreeCaptureService
    from lemmamind.storage import SQLiteContractStore
    from lemmamind.tracking import RepositoryTrackingService
    from lemmamind.tracking_adapters import TrackingAwareGitHubCaptureService
    from lemmamind.tracking_contracts import TrackingLevel
    from lemmamind.typescript_ast import typescript_aware_extractors

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required for frozen source capture")

    spec = SPECS[repo_key]
    state_dir = state_dir.resolve()
    if state_dir.exists():
        shutil.rmtree(state_dir)
    state_dir.mkdir(parents=True)

    store = SQLiteContractStore(state_dir / "lemmamind.db")
    objects = ContentAddressedFileStore(state_dir / "objects")
    reader = GitHubIntervalRESTReader(token=token)

    seed_capture = GitHubCaptureService(reader, store, objects)
    previous_seed = seed_capture.capture_repository(
        spec["repository"], ["README.md"], source_role=SourceRole.IMPLEMENTATION, ref=spec["baseline"]
    )
    current_seed = seed_capture.capture_repository(
        spec["repository"], ["README.md"], source_role=SourceRole.IMPLEMENTATION, ref=spec["current"]
    )

    tracking = RepositoryTrackingService(store)
    tracking.assign_level(
        current_seed.source.source_id,
        TrackingLevel.DEEP,
        assigned_by="m5-frozen-semantic-replay",
        reason="ephemeral frozen V2-P0 semantic replay",
    )

    recursive = TrackingAwareGitHubRecursiveTreeCaptureService(reader, store, objects, tracking=tracking)
    previous_tree = recursive.capture_recursive_tree(previous_seed.revision.source_revision_id)
    current_tree = recursive.capture_recursive_tree(current_seed.revision.source_revision_id)
    diff = RecursiveGitTreeDiffService(store, objects).compare_captures(
        previous_tree.manifest.capture_id, current_tree.manifest.capture_id
    )

    planning = AffectedFileCapturePlanner(store, tracking).plan_diff(diff.run.run_id)
    segmented = IntervalCandidateSegmentationService(reader, store, tracking).segment_diff(diff.run.run_id)
    if not planning.previous_capture_paths or not planning.current_capture_paths:
        raise RuntimeError("frozen replay requires non-empty explicit capture plans")

    explicit_capture = TrackingAwareGitHubCaptureService(reader, store, objects, tracking=tracking)
    previous_files = explicit_capture.capture_repository(
        spec["repository"], list(planning.previous_capture_paths), source_role=SourceRole.IMPLEMENTATION, ref=spec["baseline"]
    )
    current_files = explicit_capture.capture_repository(
        spec["repository"], list(planning.current_capture_paths), source_role=SourceRole.IMPLEMENTATION, ref=spec["current"]
    )

    extractors = typescript_aware_extractors()
    extraction_pair = GapTolerantExtractionPairService(
        store, objects, artifact_extractors=extractors
    ).extract_pair(previous_files.manifest.capture_id, current_files.manifest.capture_id)
    previous_extraction = extraction_pair.previous.extraction
    current_extraction = extraction_pair.current.extraction

    reduced = GapAwareCandidateFactualReductionService(store, objects).reduce_segmentation(
        diff_run_id=diff.run.run_id,
        segmentation_run_id=segmented.run.run_id,
        planner_run_id=planning.run.run_id,
        previous_capture_id=previous_files.manifest.capture_id,
        current_capture_id=current_files.manifest.capture_id,
        previous_extraction_run_id=previous_extraction.run.run_id,
        current_extraction_run_id=current_extraction.run.run_id,
        artifact_extractors=extractors,
    )
    gap_signals = CandidateExtractionGapService(store).record_signals(
        segmentation_run_id=segmented.run.run_id,
        previous_extraction_run_id=previous_extraction.run.run_id,
        current_extraction_run_id=current_extraction.run.run_id,
        reduction_run_id=reduced.run.run_id,
    )
    packet_result = CandidateEvidencePacketService(
        store, artifact_extractors=extractors
    ).build_reduction(reduced.run.run_id)

    if len(reduced.reductions) != len(segmented.candidates):
        raise AssertionError("factual reduction does not exactly cover interval candidates")
    if reduced.retained_count != len(segmented.candidates) or reduced.suppressed_count != 0:
        raise AssertionError("frozen candidate retention changed")
    if len(packet_result.packets) != len(segmented.candidates):
        raise AssertionError("packet generation does not exactly cover retained candidates")

    anchor_reductions = [item for item in reduced.reductions if spec["anchor"] in item.paths]
    if len(anchor_reductions) != 1 or anchor_reductions[0].disposition is not CandidateReductionDisposition.RETAIN:
        raise AssertionError("primary anchor must occur in exactly one retained candidate")

    observed = {
        "interval_candidates": len(segmented.candidates),
        "artifact_deltas": len(reduced.change.artifact_deltas),
        "structural_deltas": len(reduced.change.structural_deltas),
        "extraction_gap_paths": len(extraction_pair.gap_paths),
    }
    if observed != spec["expected"]:
        raise AssertionError(
            f"frozen factual baseline drifted for {repo_key}: expected={spec['expected']} observed={observed}"
        )

    signal_counts = Counter()
    for item in reduced.reductions:
        for signal in item.signal_kinds:
            signal_counts[signal.value] += 1
    if gap_signals.candidate_count:
        signal_counts["extraction_gap"] = gap_signals.candidate_count

    write_json(
        state_dir / "packets.json",
        [item.model_dump(mode="json", by_alias=True) for item in packet_result.packets],
    )
    meta = {
        "schema_version": SCHEMA_VERSION,
        "runtime_sha": PR34_SHA,
        "repo_key": repo_key,
        "repository": spec["repository"],
        "baseline_revision": spec["baseline"],
        "current_revision": spec["current"],
        "primary_anchor_path": spec["anchor"],
        "max_review_items": spec["max_review_items"],
        "source_id": current_seed.source.source_id,
        "previous_source_revision_id": previous_seed.revision.source_revision_id,
        "current_source_revision_id": current_seed.revision.source_revision_id,
        "diff_run_id": diff.run.run_id,
        "planner_run_id": planning.run.run_id,
        "segmentation_run_id": segmented.run.run_id,
        "reduction_run_id": reduced.run.run_id,
        "packet_run_id": packet_result.run.run_id,
        "packet_count": len(packet_result.packets),
        "retained_candidates": reduced.retained_count,
        "suppressed_candidates": reduced.suppressed_count,
        "artifact_deltas": len(reduced.change.artifact_deltas),
        "structural_deltas": len(reduced.change.structural_deltas),
        "extraction_gap_paths": len(extraction_pair.gap_paths),
        "extraction_gap_candidates": gap_signals.candidate_count,
        "signal_counts": dict(sorted(signal_counts.items())),
    }
    write_json(state_dir / "build_meta.json", meta)
    print("M5_FROZEN_BUILD=" + json.dumps(meta, sort_keys=True), flush=True)
    return 0


def validate(repo_key: str, state_dir: Path, inference_file: Path, output_dir: Path) -> int:
    from lemmamind.change_interpretation import ChangeInterpretationService, InterpretationProposal
    from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
    from lemmamind.mechanism_review import MechanismReviewGroupingService
    from lemmamind.storage import SQLiteContractStore

    spec = SPECS[repo_key]
    build_meta = read_json(state_dir / "build_meta.json")
    inference = read_json(inference_file)
    output_dir.mkdir(parents=True, exist_ok=True)

    if build_meta["runtime_sha"] != PR34_SHA:
        raise AssertionError("validation state was not built with the exact reviewed PR #34 runtime")
    if inference.get("schema_version") != SCHEMA_VERSION:
        raise AssertionError("inference artifact schema is not the frozen replay schema")
    if inference.get("repo_key") != repo_key:
        raise AssertionError("inference artifact repository key mismatch")
    if inference.get("packet_count") != build_meta["packet_count"]:
        raise AssertionError("inference did not cover the exact packet generation")

    errors = inference.get("errors", [])
    if errors:
        meta = {
            "schema_version": SCHEMA_VERSION,
            "repo_key": repo_key,
            "runtime_sha": PR34_SHA,
            "status": "INCONCLUSIVE_PROVIDER_OUTPUT",
            "provider_error_count": len(errors),
            "packet_count": build_meta["packet_count"],
            "review_item_count": None,
            "max_review_items": spec["max_review_items"],
            "primary_anchor_visible": None,
        }
        write_json(output_dir / "validation_meta.json", meta)
        write_json(output_dir / "provider_errors.json", errors)
        write_json(output_dir / "review_items.json", [])
        print("M5_FROZEN_VALIDATE=" + json.dumps(meta, sort_keys=True), flush=True)
        return 0

    by_packet = inference.get("results", {})
    if len(by_packet) != build_meta["packet_count"]:
        raise AssertionError("inference result cardinality does not equal packet count")

    class FrozenInterpreter:
        name = "zai-openai-compatible"
        version = "GLM-5.3.m5-frozen-v1"

        def interpret(self, packet):
            record = by_packet.get(packet.candidate_evidence_packet_id)
            if record is None:
                raise RuntimeError("inference artifact omitted an authenticated packet")
            if record["status"] == "decline":
                return None
            if record["status"] != "interpret":
                raise RuntimeError("unexpected inference status")
            return InterpretationProposal.model_validate(record["proposal"])

    store = SQLiteContractStore(state_dir / "lemmamind.db")
    interpretation_result = ChangeInterpretationService(store).produce_packet_run(
        build_meta["packet_run_id"], FrozenInterpreter()
    )
    grouping = MechanismReviewGroupingService(store).group_interpretation_run(
        interpretation_result.run.run_id
    )
    authenticated_run, authenticated_items = MechanismReviewGroupingService(store).authenticate_grouping_run(
        grouping.run.run_id
    )
    if authenticated_run.run_id != grouping.run.run_id or authenticated_items != grouping.items:
        raise AssertionError("mechanism review grouping did not reconstruct exactly")

    candidate_by_id = {
        item.interval_candidate_segment_id: item
        for item in store.list(IntervalCandidateSegment)
    }
    review_payloads = []
    primary_anchor_visible = False
    for item in grouping.items:
        paths = sorted(
            {
                path
                for candidate_id in item.interval_candidate_segment_ids
                for path in candidate_by_id[candidate_id].paths
            }
        )
        if spec["anchor"] in paths:
            primary_anchor_visible = True
        payload = item.model_dump(mode="json", by_alias=True)
        payload["candidate_paths"] = paths
        review_payloads.append(payload)

    meta = {
        "schema_version": SCHEMA_VERSION,
        "repo_key": repo_key,
        "repository": spec["repository"],
        "runtime_sha": PR34_SHA,
        "provider_type": inference["provider_type"],
        "provider_base_url": inference["provider_base_url"],
        "model": inference["model"],
        "adapter_version": inference["adapter_version"],
        "packet_count": build_meta["packet_count"],
        "interpretation_count": len(interpretation_result.interpretations),
        "declined_count": inference["declined_count"],
        "review_item_count": len(grouping.items),
        "max_review_items": spec["max_review_items"],
        "attention_pass": len(grouping.items) <= spec["max_review_items"],
        "primary_anchor_path": spec["anchor"],
        "primary_anchor_visible": primary_anchor_visible,
        "interpretation_run_id": interpretation_result.run.run_id,
        "grouping_run_id": grouping.run.run_id,
        "status": "READY_FOR_AUDIT",
    }
    write_json(output_dir / "validation_meta.json", meta)
    write_json(output_dir / "review_items.json", review_payloads)
    write_json(
        output_dir / "interpretations.json",
        [item.model_dump(mode="json", by_alias=True) for item in interpretation_result.interpretations],
    )
    print("M5_FROZEN_VALIDATE=" + json.dumps(meta, sort_keys=True), flush=True)
    return 0


def aggregate(inputs_dir: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    metas = {}
    review_items = {}
    for key in SPECS:
        root = inputs_dir / key
        metas[key] = read_json(root / "validation_meta.json")
        review_items[key] = read_json(root / "review_items.json")

    for key, meta in metas.items():
        if meta.get("runtime_sha") != PR34_SHA:
            raise AssertionError(f"aggregate validation runtime mismatch for {key}")

    if any(meta["status"] == "INCONCLUSIVE_PROVIDER_OUTPUT" for meta in metas.values()):
        status = "INCONCLUSIVE"
        total_review_items = None
        attention_pass = False
        anchors_pass = False
    else:
        total_review_items = sum(meta["review_item_count"] for meta in metas.values())
        attention_pass = total_review_items <= 50 and all(meta["attention_pass"] for meta in metas.values())
        anchors_pass = all(meta["primary_anchor_visible"] for meta in metas.values())
        if not attention_pass:
            status = "FAIL_ATTENTION"
        elif not anchors_pass:
            status = "FAIL_RECALL"
        else:
            status = "READY_FOR_HUMAN_SEMANTIC_AUDIT"

    report = {
        "schema_version": SCHEMA_VERSION,
        "runtime_sha": PR34_SHA,
        "status": status,
        "repositories": metas,
        "total_machine_candidates": 303,
        "total_review_items": total_review_items,
        "total_review_item_limit": 50,
        "attention_pass": attention_pass,
        "primary_anchors_pass": anchors_pass,
        "human_audit_required": True,
        "known_mechanism_recall_required": "at least 8 of 10",
        "known_mechanisms": KNOWN_MECHANISMS,
        "semantic_grounding_requirement": "zero unsupported central mechanism claims",
        "gap_requirement": "zero silent extraction-gap claims",
        "provenance_requirement": "zero provenance failures",
        "note": "Known-mechanism recall and central semantic grounding remain bounded human-audit gates; they are not inferred from string matching.",
    }
    write_json(output_dir / "m5-frozen-replay-report.json", report)
    for key, items in review_items.items():
        write_json(output_dir / f"review-items-{key}.json", items)
    print("M5_FROZEN_REPORT=" + json.dumps(report, sort_keys=True), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build")
    build_parser.add_argument("--repo-key", choices=tuple(SPECS), required=True)
    build_parser.add_argument("--state-dir", type=Path, required=True)

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--repo-key", choices=tuple(SPECS), required=True)
    validate_parser.add_argument("--state-dir", type=Path, required=True)
    validate_parser.add_argument("--inference-file", type=Path, required=True)
    validate_parser.add_argument("--output-dir", type=Path, required=True)

    aggregate_parser = sub.add_parser("aggregate")
    aggregate_parser.add_argument("--inputs-dir", type=Path, required=True)
    aggregate_parser.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "build":
        return build(args.repo_key, args.state_dir)
    if args.command == "validate":
        return validate(args.repo_key, args.state_dir, args.inference_file, args.output_dir)
    if args.command == "aggregate":
        return aggregate(args.inputs_dir, args.output_dir)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
