"""Final fail-closed public surface for full-M5 candidate evidence packets.

This layer authenticates the complete deterministic lineage that feeds semantic
change interpretation.  The previous review-hardened implementation is retained
in ``candidate_evidence_packets_v1``; this module tightens upstream generation
authentication and persists the exact ordered extractor profile needed for later
semantic replay.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .affected_file_planning import (
    MAX_CAPTURE_BLOB_BYTES_V1,
    _SUPPRESSED_SURFACES_V1,
    AffectedFileCapturePlanner,
)
from .candidate_evidence_packet_contracts import AssertionSnapshotSide
from .candidate_evidence_packet_generation_contracts import (
    CandidateEvidencePacketGeneration,
    PacketExtractorDescriptor,
)
from .candidate_evidence_packets_base import (
    CandidateEvidencePacketService as _BaseCandidateEvidencePacketService,
)
from .candidate_evidence_packets_v1 import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketResult,
    CandidateEvidencePacketService as _PreviousCandidateEvidencePacketService,
    ContractStore,
)
from .candidate_reduction import CandidateFactualReductionService
from .candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
)
from .capture_planning_contracts import AffectedFileCapturePlan
from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureManifest,
    PipelineRun,
    RunType,
    SourceRevision,
)
from .interval_segmentation import (
    IntervalCandidateSegmentationService,
    IntervalSegmentationError,
)
from .interval_segmentation_contracts import (
    CommitPathSnapshot,
    CommitRangeSummary,
    IntervalSegmentationGeneration,
    IntervalCandidateSegment,
)
from .path_change_contracts import GitPathDelta, GitPathDiffSummary
from .recursive_tree import RecursiveGitTreeDiffService, classify_change_surface
from .tracking import CaptureDepth, RepositoryTrackingService, TrackingPolicyError


class CandidateEvidencePacketService(_PreviousCandidateEvidencePacketService):
    """Build bounded packets only from a fully authenticated deterministic lineage."""

    _PATH_DIFF_POLICY = "recursive-git-path-diff.v1"

    def __init__(
        self,
        *args,
        artifact_extractors: Iterable[object] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.artifact_extractors = self._normalize_extractor_profile(artifact_extractors)

    @staticmethod
    def _normalize_extractor_profile(
        artifact_extractors: Iterable[object] | None,
    ) -> tuple[PacketExtractorDescriptor, ...]:
        if artifact_extractors is None:
            return ()
        descriptors: list[PacketExtractorDescriptor] = []
        for item in artifact_extractors:
            if isinstance(item, PacketExtractorDescriptor):
                descriptor = item
            elif isinstance(item, Mapping):
                descriptor = PacketExtractorDescriptor(
                    name=str(item.get("name", "")),
                    version=str(item.get("version", "")),
                )
            else:
                descriptor = PacketExtractorDescriptor(
                    name=str(getattr(item, "name", "")),
                    version=str(getattr(item, "version", "")),
                )
            descriptors.append(descriptor)
        return tuple(descriptors)

    def _profile_payload(self) -> tuple[dict[str, str], ...]:
        if not self.artifact_extractors:
            raise CandidateEvidencePacketError(
                "candidate evidence packet generation requires the exact ordered artifact extractor profile"
            )
        return tuple(
            {"name": item.name, "version": item.version}
            for item in self.artifact_extractors
        )

    def build_reduction(self, reduction_run_id: str) -> CandidateEvidencePacketResult:
        """Persist packets and the exact authenticated profile used to reconstruct them."""

        profile = self._profile_payload()
        started_at = self._aware_now()
        reduction_run, pairs = self._authenticated_reduction_generation(reduction_run_id)
        packet_run_id = f"run:candidate-evidence-packet:{self.id_factory()}"
        packets = tuple(
            self._build_packet(reduction, candidate, packet_run_id)
            for candidate, reduction in pairs
            if reduction.disposition is CandidateReductionDisposition.RETAIN
        )

        inputs_hash = self._digest_json(
            {
                "reduction_run": reduction_run.model_dump(mode="json", by_alias=True),
                "artifact_extractors": list(profile),
                "policy_version": self.policy_version,
                "max_structural_previews": self.max_structural_previews,
                "max_assertion_previews": self.max_assertion_previews,
                "preview_chars": self.preview_chars,
            }
        )
        outputs_hash = self._digest_json(
            [self._stable_packet_payload(item) for item in packets]
        )
        run = PipelineRun(
            run_id=packet_run_id,
            run_type=RunType.OTHER,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=self._aware_now(),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        generation = CandidateEvidencePacketGeneration(
            candidate_evidence_packet_generation_id=(
                f"candidate-evidence-packet-generation:{packet_run_id}"
            ),
            packet_run_id=packet_run_id,
            reduction_run_id=reduction_run_id,
            policy_version=self.policy_version,
            max_structural_previews=self.max_structural_previews,
            max_assertion_previews=self.max_assertion_previews,
            preview_chars=self.preview_chars,
            artifact_extractors=self.artifact_extractors,
            candidate_evidence_packet_ids=tuple(
                sorted(item.candidate_evidence_packet_id for item in packets)
            ),
        )
        result = CandidateEvidencePacketResult(reduction_run_id, packets, run)
        self.store.put_many((*packets, run, generation))
        return result

    def _authenticated_reduction_generation(self, reduction_run_id: str):
        """Authenticate path diff -> segmentation -> planner -> factual reduction."""

        profile = self._profile_payload()
        run, pairs = _BaseCandidateEvidencePacketService._authenticated_reduction_generation(
            self, reduction_run_id
        )
        if not pairs:
            raise CandidateEvidencePacketError(
                "candidate factual-reduction generation is empty"
            )
        if any(
            len(candidate.paths) > self._MAX_CANDIDATE_PATHS
            for candidate, _ in pairs
        ):
            raise CandidateEvidencePacketError(
                "candidate factual-reduction generation exceeds the 50-path packet boundary"
            )

        first = pairs[0][1]
        lineage = self._reduction_lineage(first)
        for _, reduction in pairs[1:]:
            if self._reduction_lineage(reduction) != lineage:
                raise CandidateEvidencePacketError(
                    "candidate factual reductions do not share one input generation"
                )

        expected_change_policy = self._REDUCTION_CHANGE_POLICIES.get(run.policy_version)
        expected_extraction_policy = self._REDUCTION_EXTRACTION_POLICIES.get(
            run.policy_version
        )
        if expected_change_policy is None or expected_extraction_policy is None:
            raise CandidateEvidencePacketError(
                "candidate evidence packets require a known factual-reduction policy"
            )

        diff_run, diff_summary, deltas = self._authenticate_path_diff_generation(
            first.diff_run_id
        )
        expected_interval = (
            first.source_id,
            first.previous_source_revision_id,
            first.current_source_revision_id,
        )
        observed_interval = (
            diff_summary.source_id,
            diff_summary.previous_source_revision_id,
            diff_summary.current_source_revision_id,
        )
        if observed_interval != expected_interval:
            raise CandidateEvidencePacketError(
                "candidate factual reduction disagrees with authenticated path-diff interval"
            )

        segmentation_run = self._completed_run(
            first.segmentation_run_id, RunType.DIFF, "interval segmentation"
        )
        if segmentation_run.policy_version != self._SEGMENTATION_POLICY:
            raise CandidateEvidencePacketError(
                "candidate factual reduction references an unrecognized segmentation policy"
            )
        candidates = tuple(candidate for candidate, _ in pairs)
        self._authenticate_segmentation_generation(
            segmentation_run,
            diff_summary,
            deltas,
            candidates,
        )

        planner_run = self._completed_run(
            first.planner_run_id, RunType.OTHER, "affected-file planner"
        )
        if planner_run.policy_version != self._PLANNER_POLICY:
            raise CandidateEvidencePacketError(
                "candidate factual reduction references an unrecognized planner policy"
            )
        plans = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(AffectedFileCapturePlan)
                    if item.planner_run_id == first.planner_run_id
                ),
                key=lambda item: item.path,
            )
        )

        previous_manifest = self._manifest(
            first.previous_capture_id, first.previous_source_revision_id
        )
        current_manifest = self._manifest(
            first.current_capture_id, first.current_source_revision_id
        )
        self._authenticate_plan_generation(
            planner_run,
            diff_summary,
            deltas,
            plans,
            previous_manifest,
            current_manifest,
        )

        change_run = self._completed_run(
            first.change_run_id, RunType.DIFF, "candidate factual change"
        )
        if change_run.policy_version != expected_change_policy:
            raise CandidateEvidencePacketError(
                "candidate factual reduction references an incompatible change policy"
            )
        previous_extraction = self._completed_run(
            first.previous_extraction_run_id, RunType.EXTRACTION, "previous extraction"
        )
        current_extraction = self._completed_run(
            first.current_extraction_run_id, RunType.EXTRACTION, "current extraction"
        )
        if (
            previous_extraction.policy_version != expected_extraction_policy
            or current_extraction.policy_version != expected_extraction_policy
        ):
            raise CandidateEvidencePacketError(
                "candidate factual reduction references incompatible extraction policies"
            )
        self._authenticate_extraction_run(previous_extraction.run_id)
        self._authenticate_extraction_run(current_extraction.run_id)

        gap_paths = self._gap_paths_for_reduction(
            run.policy_version,
            previous_extraction.run_id,
            current_extraction.run_id,
        )
        if not self._profile_matches_input_envelopes(
            descriptors=profile,
            run=run,
            change_run=change_run,
            previous_extraction=previous_extraction,
            current_extraction=current_extraction,
            previous_manifest=previous_manifest,
            current_manifest=current_manifest,
            candidates=candidates,
            plans=plans,
            gap_paths=gap_paths,
        ):
            raise CandidateEvidencePacketError(
                "supplied artifact extractor profile does not authenticate factual lineage"
            )

        artifact_deltas, structural_deltas = self._authenticate_change_outputs(
            change_run, candidates
        )
        self._reconstruct_candidate_reductions(
            run=run,
            pairs=pairs,
            plans=plans,
            previous_manifest=previous_manifest,
            current_manifest=current_manifest,
            artifact_deltas=artifact_deltas,
            structural_deltas=structural_deltas,
            gap_paths=gap_paths,
        )
        # Keep the diff run live in this scope to make the authenticated root explicit.
        if diff_run.run_id != first.diff_run_id:
            raise CandidateEvidencePacketError("authenticated path-diff run identity changed")
        return run, pairs

    def _authenticate_path_diff_generation(
        self,
        diff_run_id: str,
    ) -> tuple[PipelineRun, GitPathDiffSummary, tuple[GitPathDelta, ...]]:
        run = self._completed_run(diff_run_id, RunType.DIFF, "recursive path diff")
        if run.policy_version != self._PATH_DIFF_POLICY:
            raise CandidateEvidencePacketError(
                "candidate factual reduction references an unrecognized path-diff policy"
            )
        summaries = tuple(
            item
            for item in self.store.list(GitPathDiffSummary)
            if item.diff_run_id == diff_run_id
        )
        if len(summaries) != 1:
            raise CandidateEvidencePacketError(
                "recursive path diff requires exactly one GitPathDiffSummary"
            )
        summary = summaries[0]
        deltas = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(GitPathDelta)
                    if item.diff_run_id == diff_run_id
                ),
                key=lambda item: item.path,
            )
        )
        if len(deltas) != summary.delta_count:
            raise CandidateEvidencePacketError(
                "authenticated path-diff delta_count disagrees with persisted deltas"
            )
        try:
            IntervalCandidateSegmentationService._validate_delta_generation(
                summary, deltas
            )
        except IntervalSegmentationError as exc:
            raise CandidateEvidencePacketError(
                "recursive path-diff delta provenance does not authenticate"
            ) from exc
        if len({item.path for item in deltas}) != len(deltas):
            raise CandidateEvidencePacketError(
                "recursive path-diff generation contains duplicate Git paths"
            )

        if summary.git_path_diff_summary_id != RecursiveGitTreeDiffService._summary_id(
            diff_run_id
        ):
            raise CandidateEvidencePacketError(
                "recursive path-diff summary identity does not authenticate"
            )
        for delta in deltas:
            expected_id = RecursiveGitTreeDiffService._delta_id(
                diff_run_id,
                summary.previous_source_revision_id,
                summary.current_source_revision_id,
                delta.path,
                delta.change_type,
            )
            if delta.git_path_delta_id != expected_id:
                raise CandidateEvidencePacketError(
                    "recursive path-diff delta identity does not authenticate"
                )
            if delta.surface is not classify_change_surface(delta.path):
                raise CandidateEvidencePacketError(
                    "recursive path-diff surface classification does not authenticate"
                )

        previous_revision = self.store.get(
            SourceRevision, summary.previous_source_revision_id
        )
        current_revision = self.store.get(
            SourceRevision, summary.current_source_revision_id
        )
        if previous_revision is None or current_revision is None:
            raise CandidateEvidencePacketError(
                "recursive path diff references missing SourceRevision"
            )
        if (
            previous_revision.source_id != summary.source_id
            or current_revision.source_id != summary.source_id
            or previous_revision.observed_at > current_revision.observed_at
        ):
            raise CandidateEvidencePacketError(
                "recursive path-diff revision provenance does not authenticate"
            )

        expected_inputs = self._digest_json(
            {
                "previous_capture_id": summary.previous_capture_id,
                "current_capture_id": summary.current_capture_id,
                "previous_source_revision_id": summary.previous_source_revision_id,
                "current_source_revision_id": summary.current_source_revision_id,
                "policy_version": run.policy_version,
            }
        )
        if run.inputs_hash != expected_inputs:
            raise CandidateEvidencePacketError(
                "recursive path-diff input envelope does not authenticate"
            )
        expected_outputs = self._digest_json(
            {
                "summary": summary.model_dump(mode="json", by_alias=True),
                "deltas": [
                    {
                        "path": delta.path,
                        "change_type": delta.change_type.value,
                        "surface": delta.surface.value,
                        "previous_entry_type": delta.previous_entry_type,
                        "current_entry_type": delta.current_entry_type,
                        "previous_mode": delta.previous_mode,
                        "current_mode": delta.current_mode,
                        "previous_object_sha": delta.previous_object_sha,
                        "current_object_sha": delta.current_object_sha,
                        "previous_size": delta.previous_size,
                        "current_size": delta.current_size,
                    }
                    for delta in deltas
                ],
            }
        )
        if run.outputs_hash != expected_outputs:
            raise CandidateEvidencePacketError(
                "recursive path-diff output envelope does not authenticate"
            )
        return run, summary, deltas

    def _tracking_policy(
        self,
        source_id: str,
        minimum: CaptureDepth,
        run: PipelineRun,
    ):
        tracking = RepositoryTrackingService(
            self.store,
            clock=lambda: run.started_at,
        )
        try:
            return tracking.require_capture_depth(
                source_id,
                minimum,
                as_of=run.started_at,
            )
        except TrackingPolicyError as exc:
            raise CandidateEvidencePacketError(
                "persisted tracking history cannot authenticate upstream generation"
            ) from exc

    def _authenticate_segmentation_generation(
        self,
        run: PipelineRun,
        diff_summary: GitPathDiffSummary,
        deltas: tuple[GitPathDelta, ...],
        candidates: tuple[IntervalCandidateSegment, ...],
    ) -> None:
        ranges = tuple(
            item
            for item in self.store.list(CommitRangeSummary)
            if item.segmentation_run_id == run.run_id
        )
        if len(ranges) != 1:
            raise CandidateEvidencePacketError(
                "interval segmentation requires exactly one CommitRangeSummary"
            )
        commit_range = ranges[0]
        snapshots = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(CommitPathSnapshot)
                    if item.segmentation_run_id == run.run_id
                ),
                key=lambda item: item.ordinal,
            )
        )
        expected_lineage = (
            diff_summary.source_id,
            diff_summary.previous_source_revision_id,
            diff_summary.current_source_revision_id,
            run.run_id,
        )
        if (
            commit_range.source_id,
            commit_range.previous_source_revision_id,
            commit_range.current_source_revision_id,
            commit_range.segmentation_run_id,
        ) != expected_lineage:
            raise CandidateEvidencePacketError(
                "commit-range lineage disagrees with authenticated path diff"
            )
        for ordinal, snapshot in enumerate(snapshots, start=1):
            if (
                snapshot.source_id,
                snapshot.previous_source_revision_id,
                snapshot.current_source_revision_id,
                snapshot.segmentation_run_id,
            ) != expected_lineage or snapshot.ordinal != ordinal:
                raise CandidateEvidencePacketError(
                    "commit snapshot lineage disagrees with authenticated segmentation"
                )
        if tuple(item.commit_sha for item in snapshots) != commit_range.commit_shas:
            raise CandidateEvidencePacketError(
                "commit snapshots do not exactly cover the authenticated commit frontier"
            )

        previous_revision = self.store.get(
            SourceRevision, diff_summary.previous_source_revision_id
        )
        current_revision = self.store.get(
            SourceRevision, diff_summary.current_source_revision_id
        )
        if previous_revision is None or current_revision is None:
            raise CandidateEvidencePacketError(
                "interval segmentation references missing SourceRevision"
            )
        tracking_policy = self._tracking_policy(
            diff_summary.source_id,
            CaptureDepth.STRUCTURAL,
            run,
        )
        if tracking_policy.assignment_id is None:
            raise CandidateEvidencePacketError(
                "interval segmentation requires a persisted tracking assignment"
            )

        generations = tuple(
            item
            for item in self.store.list(IntervalSegmentationGeneration)
            if item.segmentation_run_id == run.run_id
        )
        if len(generations) != 1:
            raise CandidateEvidencePacketError(
                "interval segmentation requires exactly one durable profile envelope"
            )
        generation = generations[0]
        if (
            generation.interval_segmentation_generation_id
            != IntervalCandidateSegmentationService._stable_id(
                "interval-segmentation-generation", run.run_id
            )
            or generation.diff_run_id != diff_summary.diff_run_id
            or generation.policy_version != run.policy_version
        ):
            raise CandidateEvidencePacketError(
                "interval segmentation durable profile disagrees with authenticated lineage"
            )
        max_paths = generation.max_paths_per_candidate
        expected_inputs = self._digest_json(
            {
                "diff_run_id": diff_summary.diff_run_id,
                "diff_summary": diff_summary.model_dump(mode="json", by_alias=True),
                "path_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in deltas
                ],
                "tracking_assignment_id": tracking_policy.assignment_id,
                "tracking_level": tracking_policy.level.value,
                "max_paths_per_candidate": max_paths,
                "policy_version": run.policy_version,
            }
        )
        if run.inputs_hash != expected_inputs:
            raise CandidateEvidencePacketError(
                "interval segmentation input envelope does not authenticate against its durable profile"
            )

        service = IntervalCandidateSegmentationService(
            None,
            self.store,
            None,
            max_paths_per_candidate=max_paths,
            policy_version=run.policy_version,
        )
        try:
            integration = service._first_parent_integration_chain(
                previous_revision.commit_sha,
                current_revision.commit_sha,
                snapshots,
            )
            latest_touch = service._assign_latest_touch(deltas, integration)
            reconstructed = service._build_candidates(
                deltas,
                latest_touch,
                run_id=run.run_id,
                source_id=diff_summary.source_id,
                previous_source_revision_id=diff_summary.previous_source_revision_id,
                current_source_revision_id=diff_summary.current_source_revision_id,
            )
        except IntervalSegmentationError as exc:
            raise CandidateEvidencePacketError(
                "interval segmentation cannot be reconstructed from authenticated inputs"
            ) from exc
        if reconstructed != candidates:
            raise CandidateEvidencePacketError(
                "persisted interval candidates disagree with deterministic segmentation reconstruction"
            )

        expected_outputs = self._digest_json(
            {
                "commit_range": commit_range.model_dump(mode="json", by_alias=True),
                "commit_snapshots": [
                    item.model_dump(mode="json", by_alias=True) for item in snapshots
                ],
                "integration_commit_shas": [item.commit_sha for item in integration],
                "candidates": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in reconstructed
                ],
            }
        )
        if run.outputs_hash != expected_outputs:
            raise CandidateEvidencePacketError(
                "interval segmentation output envelope does not authenticate"
            )

    def _authenticate_plan_generation(
        self,
        run: PipelineRun,
        diff_summary: GitPathDiffSummary,
        deltas: tuple[GitPathDelta, ...],
        plans: tuple[AffectedFileCapturePlan, ...],
        previous_manifest: CaptureManifest,
        current_manifest: CaptureManifest,
    ) -> None:
        tracking_policy = self._tracking_policy(
            diff_summary.source_id,
            CaptureDepth.SHALLOW,
            run,
        )
        if tracking_policy.assignment_id is None:
            raise CandidateEvidencePacketError(
                "affected-file planning requires a persisted tracking assignment"
            )
        expected_inputs = self._digest_json(
            {
                "diff_run_id": diff_summary.diff_run_id,
                "diff_summary": diff_summary.model_dump(mode="json", by_alias=True),
                "path_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in deltas
                ],
                "tracking_assignment_id": tracking_policy.assignment_id,
                "tracking_level": tracking_policy.level.value,
                "max_capture_blob_bytes": MAX_CAPTURE_BLOB_BYTES_V1,
                "suppressed_surfaces": sorted(
                    surface.value for surface in _SUPPRESSED_SURFACES_V1
                ),
                "policy_version": run.policy_version,
            }
        )
        if run.inputs_hash != expected_inputs:
            raise CandidateEvidencePacketError(
                "affected-file planner input envelope does not authenticate against path diff and tracking policy"
            )

        planner = AffectedFileCapturePlanner(
            self.store,
            None,
            policy_version=run.policy_version,
        )
        reconstructed = tuple(
            planner._plan_delta(
                delta,
                run_id=run.run_id,
                tracking_assignment_id=tracking_policy.assignment_id,
                tracking_level=tracking_policy.level.value,
            )
            for delta in deltas
        )
        if reconstructed != plans:
            raise CandidateEvidencePacketError(
                "persisted affected-file plans disagree with deterministic path-diff reconstruction"
            )
        expected_outputs = self._digest_json(
            [item.model_dump(mode="json", by_alias=True) for item in reconstructed]
        )
        if run.outputs_hash != expected_outputs:
            raise CandidateEvidencePacketError(
                "affected-file planner output envelope does not authenticate"
            )

        validator = CandidateFactualReductionService(self.store, None)
        try:
            validator._validate_capture_scope(previous_manifest, plans, previous=True)
            validator._validate_capture_scope(current_manifest, plans, previous=False)
        except Exception as exc:
            raise CandidateEvidencePacketError(
                "candidate capture scope does not authenticate against affected-file plans"
            ) from exc

    @staticmethod
    def _plain_round_robin_by_path(
        items: tuple,
        *,
        path_of,
        item_key,
    ) -> tuple:
        groups: dict[str, list] = {}
        for item in items:
            groups.setdefault(path_of(item), []).append(item)
        for values in groups.values():
            values.sort(key=item_key)
        selected: list = []
        depth = 0
        paths = sorted(groups)
        while True:
            added = False
            for path in paths:
                values = groups[path]
                if depth < len(values):
                    selected.append(values[depth])
                    added = True
            if not added:
                break
            depth += 1
        return tuple(selected)

    @staticmethod
    def _round_robin_by_path(
        items: tuple,
        limit: int,
        *,
        path_of,
        item_key,
    ) -> tuple:
        """Round-robin paths and alternate previous/current assertion sides."""

        is_assertion_snapshot = bool(items) and all(
            isinstance(item, tuple)
            and len(item) == 3
            and isinstance(item[0], AssertionSnapshotSide)
            for item in items
        )
        if not is_assertion_snapshot:
            return CandidateEvidencePacketService._plain_round_robin_by_path(
                items,
                path_of=path_of,
                item_key=item_key,
            )[:limit]

        by_side = {
            side: CandidateEvidencePacketService._plain_round_robin_by_path(
                tuple(item for item in items if item[0] is side),
                path_of=path_of,
                item_key=item_key,
            )
            for side in (
                AssertionSnapshotSide.PREVIOUS,
                AssertionSnapshotSide.CURRENT,
            )
        }
        selected: list = []
        depth = 0
        while len(selected) < limit:
            added = False
            for side in (
                AssertionSnapshotSide.PREVIOUS,
                AssertionSnapshotSide.CURRENT,
            ):
                values = by_side[side]
                if depth < len(values):
                    selected.append(values[depth])
                    added = True
                    if len(selected) == limit:
                        break
            if not added:
                break
            depth += 1
        return tuple(selected)


__all__ = [
    "CandidateEvidencePacketError",
    "CandidateEvidencePacketResult",
    "CandidateEvidencePacketService",
    "ContractStore",
]
