from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    if old not in text:
        raise RuntimeError(f"expected patch anchor not found in {path}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1))


# Persist the exact segmentation profile instead of recovering a bounded hash preimage.
replace_once(
    "src/lemmamind/interval_segmentation_contracts.py",
    "\n\nclass IntervalCandidateSegment(ContractModel):\n",
    '''\n\nclass IntervalSegmentationGeneration(ContractModel):\n    """Durable deterministic profile for one interval-segmentation generation."""\n\n    record_id_field = "interval_segmentation_generation_id"\n\n    interval_segmentation_generation_id: Identifier\n    segmentation_run_id: Identifier\n    diff_run_id: Identifier\n    policy_version: Identifier\n    max_paths_per_candidate: int = Field(ge=1)\n\n\nclass IntervalCandidateSegment(ContractModel):\n''',
)
replace_once(
    "src/lemmamind/interval_segmentation_contracts.py",
    "for _model in (CommitRangeSummary, CommitPathSnapshot, IntervalCandidateSegment):\n",
    "for _model in (\n    CommitRangeSummary,\n    CommitPathSnapshot,\n    IntervalSegmentationGeneration,\n    IntervalCandidateSegment,\n):\n",
)
replace_once(
    "src/lemmamind/interval_segmentation_contracts.py",
    "    for model in (CommitRangeSummary, CommitPathSnapshot, IntervalCandidateSegment)\n",
    "    for model in (\n        CommitRangeSummary,\n        CommitPathSnapshot,\n        IntervalSegmentationGeneration,\n        IntervalCandidateSegment,\n    )\n",
)

replace_once(
    "src/lemmamind/interval_segmentation.py",
    "    CommitRangeSummary,\n    IntervalCandidateSegment,\n",
    "    CommitRangeSummary,\n    IntervalSegmentationGeneration,\n    IntervalCandidateSegment,\n",
)
replace_once(
    "src/lemmamind/interval_segmentation.py",
    '''        result = IntervalSegmentationResult(\n            diff_run_id,\n            commit_range,\n            snapshots,\n            candidates,\n            run,\n        )\n        self.store.put_many(result.records())\n        return result\n''',
    '''        generation = IntervalSegmentationGeneration(\n            interval_segmentation_generation_id=self._stable_id(\n                "interval-segmentation-generation", run_id\n            ),\n            segmentation_run_id=run_id,\n            diff_run_id=diff_run_id,\n            policy_version=self.policy_version,\n            max_paths_per_candidate=self.max_paths_per_candidate,\n        )\n        result = IntervalSegmentationResult(\n            diff_run_id,\n            commit_range,\n            snapshots,\n            candidates,\n            run,\n        )\n        self.store.put_many((*result.records(), generation))\n        return result\n''',
)

# Export/register the additive contract at package load.
replace_once(
    "src/lemmamind/__init__.py",
    "    CommitRangeSummary,\n    IntervalCandidateSegment,\n",
    "    CommitRangeSummary,\n    IntervalSegmentationGeneration,\n    IntervalCandidateSegment,\n",
)
replace_once(
    "src/lemmamind/__init__.py",
    '    "GitPathDeltaType",\n    "IntervalCandidateSegment",\n',
    '    "GitPathDeltaType",\n    "IntervalSegmentationGeneration",\n    "IntervalCandidateSegment",\n',
)

# Packet authentication consumes the persisted exact segmentation profile and
# preserves repeated extractor descriptors exactly as supplied upstream.
replace_once(
    "src/lemmamind/candidate_evidence_packets.py",
    "    CommitRangeSummary,\n    IntervalCandidateSegment,\n",
    "    CommitRangeSummary,\n    IntervalSegmentationGeneration,\n    IntervalCandidateSegment,\n",
)
replace_once(
    "src/lemmamind/candidate_evidence_packets.py",
    '''        identities = tuple((item.name, item.version) for item in descriptors)\n        if len(identities) != len(set(identities)):\n            raise ValueError("artifact_extractors must contain unique ordered descriptors")\n        return tuple(descriptors)\n''',
    '''        return tuple(descriptors)\n''',
)
replace_once(
    "src/lemmamind/candidate_evidence_packets.py",
    '''        matching_bounds: list[int] = []\n        for max_paths in range(1, self._MAX_CANDIDATE_PATHS + 1):\n            expected_inputs = self._digest_json(\n                {\n                    "diff_run_id": diff_summary.diff_run_id,\n                    "diff_summary": diff_summary.model_dump(mode="json", by_alias=True),\n                    "path_deltas": [\n                        item.model_dump(mode="json", by_alias=True) for item in deltas\n                    ],\n                    "tracking_assignment_id": tracking_policy.assignment_id,\n                    "tracking_level": tracking_policy.level.value,\n                    "max_paths_per_candidate": max_paths,\n                    "policy_version": run.policy_version,\n                }\n            )\n            if run.inputs_hash == expected_inputs:\n                matching_bounds.append(max_paths)\n        if len(matching_bounds) != 1:\n            raise CandidateEvidencePacketError(\n                "interval segmentation input envelope cannot be uniquely authenticated within the 50-path boundary"\n            )\n\n        service = IntervalCandidateSegmentationService(\n            None,\n            self.store,\n            None,\n            max_paths_per_candidate=matching_bounds[0],\n            policy_version=run.policy_version,\n        )\n''',
    '''        generations = tuple(\n            item\n            for item in self.store.list(IntervalSegmentationGeneration)\n            if item.segmentation_run_id == run.run_id\n        )\n        if len(generations) != 1:\n            raise CandidateEvidencePacketError(\n                "interval segmentation requires exactly one durable profile envelope"\n            )\n        generation = generations[0]\n        if (\n            generation.interval_segmentation_generation_id\n            != IntervalCandidateSegmentationService._stable_id(\n                "interval-segmentation-generation", run.run_id\n            )\n            or generation.diff_run_id != diff_summary.diff_run_id\n            or generation.policy_version != run.policy_version\n        ):\n            raise CandidateEvidencePacketError(\n                "interval segmentation durable profile disagrees with authenticated lineage"\n            )\n        max_paths = generation.max_paths_per_candidate\n        expected_inputs = self._digest_json(\n            {\n                "diff_run_id": diff_summary.diff_run_id,\n                "diff_summary": diff_summary.model_dump(mode="json", by_alias=True),\n                "path_deltas": [\n                    item.model_dump(mode="json", by_alias=True) for item in deltas\n                ],\n                "tracking_assignment_id": tracking_policy.assignment_id,\n                "tracking_level": tracking_policy.level.value,\n                "max_paths_per_candidate": max_paths,\n                "policy_version": run.policy_version,\n            }\n        )\n        if run.inputs_hash != expected_inputs:\n            raise CandidateEvidencePacketError(\n                "interval segmentation input envelope does not authenticate against its durable profile"\n            )\n\n        service = IntervalCandidateSegmentationService(\n            None,\n            self.store,\n            None,\n            max_paths_per_candidate=max_paths,\n            policy_version=run.policy_version,\n        )\n''',
)

# Authentic fixture lineage now includes the exact segmentation profile envelope.
replace_once(
    "tests/m5_packet_fixture.py",
    "    CommitRangeSummary,\n)",
    "    CommitRangeSummary,\n    IntervalSegmentationGeneration,\n)",
)
replace_once(
    "tests/m5_packet_fixture.py",
    '''    planner = AffectedFileCapturePlanner(\n''',
    '''    segmentation_generation = IntervalSegmentationGeneration(\n        interval_segmentation_generation_id=segmentation_service._stable_id(\n            "interval-segmentation-generation", segmentation_run_id\n        ),\n        segmentation_run_id=segmentation_run_id,\n        diff_run_id=diff_run_id,\n        policy_version="interval-candidate-segmentation.v1",\n        max_paths_per_candidate=max_paths_per_candidate,\n    )\n\n    planner = AffectedFileCapturePlanner(\n''',
)
replace_once(
    "tests/m5_packet_fixture.py",
    '''            *candidates,\n            segmentation_run,\n            *plans,\n''',
    '''            *candidates,\n            segmentation_run,\n            segmentation_generation,\n            *plans,\n''',
)

# Direct segmentation regression: producer preserves the exact configured bound,
# including values above the packet cardinality limit.
replace_once(
    "tests/test_interval_segmentation.py",
    "    CommitRangeSummary,\n    IntervalCandidateSegment,\n",
    "    CommitRangeSummary,\n    IntervalSegmentationGeneration,\n    IntervalCandidateSegment,\n",
)
with Path("tests/test_interval_segmentation.py").open("a") as file:
    file.write('''\n\ndef test_persists_exact_segmentation_bound_above_packet_cardinality_limit(tmp_path) -> None:\n    changes = [delta("src/only.py")]\n    reader = FakeIntervalReader(\n        {1: compare_payload([HEAD_SHA])},\n        {(HEAD_SHA, 1): commit_payload(HEAD_SHA, [{"filename": "src/only.py"}])},\n    )\n    store, service = prepare(\n        tmp_path, changes, reader, max_paths_per_candidate=100\n    )\n\n    result = service.segment_diff(DIFF_RUN_ID)\n\n    assert len(result.candidates) == 1\n    assert result.candidates[0].paths == ("src/only.py",)\n    generations = store.list(IntervalSegmentationGeneration)\n    assert len(generations) == 1\n    assert generations[0].segmentation_run_id == result.run.run_id\n    assert generations[0].max_paths_per_candidate == 100\n''')

# Packet regressions for both fresh Codex findings.
replace_once(
    "tests/test_candidate_evidence_packet_generation_auth.py",
    '''def _seed_retained_git_only_generation(\n    store: SQLiteContractStore,\n    *,\n    extractor_profile=EXTRACTOR_PROFILE,\n) -> None:\n''',
    '''def _seed_retained_git_only_generation(\n    store: SQLiteContractStore,\n    *,\n    extractor_profile=EXTRACTOR_PROFILE,\n    max_paths_per_candidate: int = 50,\n) -> None:\n''',
)
replace_once(
    "tests/test_candidate_evidence_packet_generation_auth.py",
    '''        path_specs=(\n            {\n                "path": PATH,\n''',
    '''        max_paths_per_candidate=max_paths_per_candidate,\n        path_specs=(\n            {\n                "path": PATH,\n''',
)
with Path("tests/test_candidate_evidence_packet_generation_auth.py").open("a") as file:
    file.write('''\n\ndef test_packet_authenticates_safe_candidate_from_segmentation_bound_above_50(tmp_path) -> None:\n    store = SQLiteContractStore(tmp_path / "lemmamind.db")\n    _seed_retained_git_only_generation(store, max_paths_per_candidate=100)\n\n    built = CandidateEvidencePacketService(\n        store,\n        artifact_extractors=EXTRACTOR_PROFILE,\n        clock=lambda: NOW,\n        id_factory=lambda: "segmentation-bound-100",\n    ).build_reduction(REDUCTION_RUN_ID)\n\n    assert len(built.packets) == 1\n    assert built.packets[0].paths == (PATH,)\n    authenticated_run, authenticated_packets = (\n        CandidateEvidencePacketGenerationAuthenticator(store).authenticate(built.run.run_id)\n    )\n    assert authenticated_run == built.run\n    assert authenticated_packets == built.packets\n\n\ndef test_packet_preserves_repeated_extractor_descriptors_in_exact_order(tmp_path) -> None:\n    store = SQLiteContractStore(tmp_path / "lemmamind.db")\n    repeated_profile = (\n        {"name": "silent-duplicate", "version": "1"},\n        {"name": "silent-duplicate", "version": "1"},\n        {"name": "other-silent", "version": "2"},\n    )\n    _seed_retained_git_only_generation(store, extractor_profile=repeated_profile)\n\n    built = CandidateEvidencePacketService(\n        store,\n        artifact_extractors=repeated_profile,\n        clock=lambda: NOW,\n        id_factory=lambda: "repeated-extractor-profile",\n    ).build_reduction(REDUCTION_RUN_ID)\n\n    generation = store.list(CandidateEvidencePacketGeneration)[0]\n    assert tuple((item.name, item.version) for item in generation.artifact_extractors) == (\n        ("silent-duplicate", "1"),\n        ("silent-duplicate", "1"),\n        ("other-silent", "2"),\n    )\n    authenticated_run, authenticated_packets = (\n        CandidateEvidencePacketGenerationAuthenticator(store).authenticate(built.run.run_id)\n    )\n    assert authenticated_run == built.run\n    assert authenticated_packets == built.packets\n''')

print("Applied exact segmentation-profile and repeated-extractor hardening.")
