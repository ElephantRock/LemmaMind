"""Bounded public surface for full-M5 candidate evidence packets."""
from __future__ import annotations

from itertools import permutations

from .candidate_evidence_packet_contracts import (
    AssertionSnapshotSide,
    SourceAssertionPreview,
    StructuralDeltaPreview,
)
from .candidate_evidence_packet_generation_contracts import (
    CandidateEvidencePacketGeneration,
)
from .candidate_evidence_packets_hardened_base import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketResult,
    CandidateEvidencePacketService as _HardenedCandidateEvidencePacketService,
    ContractStore,
)
from .candidate_reduction import CandidateFactualReductionService
from .candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
)
from .capture_planning_contracts import AffectedFileCapturePlan
from .change_contracts import ArtifactDelta, StructuralDelta
from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    CaptureManifest,
    EvidenceFact,
    PipelineRun,
    RetrievalStatus,
    RunType,
    SourceAssertion,
)
from .extraction_diagnostic_contracts import ExtractionDiagnostic


class CandidateEvidencePacketService(_HardenedCandidateEvidencePacketService):
    """Keep interpreter packets inside fixed context and provenance bounds."""

    _MAX_STRUCTURAL_PREVIEWS = 256
    _MAX_ASSERTION_PREVIEWS = 128
    _MAX_PREVIEW_CHARS = 512
    _MAX_CANDIDATE_PATHS = 50
    _PACKET_POLICY = "candidate-evidence-packet.v1"
    _SEGMENTATION_POLICY = "interval-candidate-segmentation.v1"
    _PLANNER_POLICY = "affected-file-plan.v1"
    _GAP_REDUCTION_POLICY = "candidate-factual-reduction.gap-aware.v1"
    _REDUCTION_CHANGE_POLICIES = {
        "candidate-factual-reduction.v1": "candidate-factual-change.v1",
        _GAP_REDUCTION_POLICY: "candidate-factual-change.gap-aware.v1",
    }
    _REDUCTION_EXTRACTION_POLICIES = {
        "candidate-factual-reduction.v1": "deterministic-evidence.v1",
        _GAP_REDUCTION_POLICY: "deterministic-evidence.gap-tolerant.v1",
    }
    _KNOWN_EXTRACTOR_PROFILES = (
        (
            ("artifact-path", "1"),
            ("pyproject", "1"),
            ("package-json", "1"),
            ("markdown-prose", "1"),
            ("markdown-list", "1"),
        ),
        (
            ("artifact-path", "1"),
            ("pyproject", "1"),
            ("package-json", "1"),
            ("markdown-prose", "1"),
            ("markdown-list", "1"),
            ("python-ast", "1"),
        ),
        (
            ("artifact-path", "1"),
            ("pyproject", "1"),
            ("package-json", "1"),
            ("markdown-prose", "1"),
            ("markdown-list", "1"),
            ("python-ast", "1"),
            ("typescript-ast", "1"),
        ),
    )

    def __init__(
        self,
        *args,
        max_structural_previews: int = 256,
        max_assertion_previews: int = 128,
        preview_chars: int = 512,
        **kwargs,
    ) -> None:
        if max_structural_previews > self._MAX_STRUCTURAL_PREVIEWS:
            raise ValueError("max_structural_previews exceeds bounded packet policy")
        if max_assertion_previews > self._MAX_ASSERTION_PREVIEWS:
            raise ValueError("max_assertion_previews exceeds bounded packet policy")
        if preview_chars > self._MAX_PREVIEW_CHARS:
            raise ValueError("preview_chars exceeds bounded packet policy")
        super().__init__(
            *args,
            max_structural_previews=max_structural_previews,
            max_assertion_previews=max_assertion_previews,
            preview_chars=preview_chars,
            **kwargs,
        )

    def build_reduction(self, reduction_run_id: str) -> CandidateEvidencePacketResult:
        """Persist the exact bounded profile needed to authenticate this generation."""

        started_at = self._aware_now()
        reduction_run, pairs = self._authenticated_reduction_generation(
            reduction_run_id
        )
        packet_run_id = f"run:candidate-evidence-packet:{self.id_factory()}"
        packets = tuple(
            self._build_packet(reduction, candidate, packet_run_id)
            for candidate, reduction in pairs
            if reduction.disposition is CandidateReductionDisposition.RETAIN
        )

        inputs_hash = self._digest_json(
            {
                "reduction_run": reduction_run.model_dump(
                    mode="json", by_alias=True
                ),
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
            candidate_evidence_packet_ids=tuple(
                sorted(item.candidate_evidence_packet_id for item in packets)
            ),
        )
        result = CandidateEvidencePacketResult(reduction_run_id, packets, run)
        self.store.put_many((*packets, run, generation))
        return result

    def _authenticated_reduction_generation(self, reduction_run_id: str):
        """Reconstruct reducer inputs before any packet can expose factual support."""

        run, pairs = super()._authenticated_reduction_generation(reduction_run_id)
        if not pairs:
            raise CandidateEvidencePacketError(
                "candidate factual-reduction generation is empty"
            )
        if any(len(candidate.paths) > self._MAX_CANDIDATE_PATHS for candidate, _ in pairs):
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

        segmentation_run = self._completed_run(
            first.segmentation_run_id, RunType.DIFF, "interval segmentation"
        )
        if segmentation_run.policy_version != self._SEGMENTATION_POLICY:
            raise CandidateEvidencePacketError(
                "candidate factual reduction references an unrecognized segmentation policy"
            )
        planner_run = self._completed_run(
            first.planner_run_id, RunType.OTHER, "affected-file planner"
        )
        if planner_run.policy_version != self._PLANNER_POLICY:
            raise CandidateEvidencePacketError(
                "candidate factual reduction references an unrecognized planner policy"
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

        previous_manifest = self._manifest(
            first.previous_capture_id, first.previous_source_revision_id
        )
        current_manifest = self._manifest(
            first.current_capture_id, first.current_source_revision_id
        )
        candidates = tuple(candidate for candidate, _ in pairs)
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
        self._authenticate_plan_generation(
            planner_run, candidates, plans, previous_manifest, current_manifest
        )

        gap_paths = self._gap_paths_for_reduction(
            run.policy_version,
            previous_extraction.run_id,
            current_extraction.run_id,
        )
        self._recover_authenticated_extractor_profile(
            run=run,
            change_run=change_run,
            previous_extraction=previous_extraction,
            current_extraction=current_extraction,
            previous_manifest=previous_manifest,
            current_manifest=current_manifest,
            candidates=candidates,
            plans=plans,
            gap_paths=gap_paths,
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
        return run, pairs

    @staticmethod
    def _reduction_lineage(reduction: CandidateFactualReduction) -> tuple[str, ...]:
        return (
            reduction.diff_run_id,
            reduction.segmentation_run_id,
            reduction.planner_run_id,
            reduction.previous_capture_id,
            reduction.current_capture_id,
            reduction.previous_extraction_run_id,
            reduction.current_extraction_run_id,
            reduction.change_run_id,
        )

    def _authenticate_plan_generation(
        self,
        planner_run: PipelineRun,
        candidates: tuple,
        plans: tuple[AffectedFileCapturePlan, ...],
        previous_manifest: CaptureManifest,
        current_manifest: CaptureManifest,
    ) -> None:
        if not plans:
            raise CandidateEvidencePacketError(
                "candidate factual reduction requires affected-file plans"
            )
        plan_by_delta = {item.git_path_delta_id: item for item in plans}
        expected_delta_ids = {
            delta_id for candidate in candidates for delta_id in candidate.git_path_delta_ids
        }
        if len(plan_by_delta) != len(plans) or set(plan_by_delta) != expected_delta_ids:
            raise CandidateEvidencePacketError(
                "affected-file plans do not exactly cover candidate GitPathDelta identities"
            )
        validator = CandidateFactualReductionService(self.store, None)
        try:
            validator._validate_capture_scope(previous_manifest, plans, previous=True)
            validator._validate_capture_scope(current_manifest, plans, previous=False)
        except Exception as exc:
            raise CandidateEvidencePacketError(
                "candidate capture scope does not authenticate against affected-file plans"
            ) from exc
        expected_outputs = self._digest_json(
            [item.model_dump(mode="json", by_alias=True) for item in plans]
        )
        if planner_run.outputs_hash != expected_outputs:
            raise CandidateEvidencePacketError(
                "affected-file planner output envelope does not authenticate"
            )

    def _recover_authenticated_extractor_profile(
        self,
        *,
        run: PipelineRun,
        change_run: PipelineRun,
        previous_extraction: PipelineRun,
        current_extraction: PipelineRun,
        previous_manifest: CaptureManifest,
        current_manifest: CaptureManifest,
        candidates: tuple,
        plans: tuple[AffectedFileCapturePlan, ...],
        gap_paths: tuple[str, ...],
    ) -> tuple[dict[str, str], ...]:
        observed = {
            (item.extractor_name, item.extractor_version)
            for model in (EvidenceFact, SourceAssertion, ExtractionDiagnostic)
            for item in self.store.list(model)
            if item.run_id in {previous_extraction.run_id, current_extraction.run_id}
        }
        profiles: list[tuple[tuple[str, str], ...]] = list(
            self._KNOWN_EXTRACTOR_PROFILES
        )
        if 0 < len(observed) <= 6:
            profiles.extend(permutations(tuple(sorted(observed))))

        authenticated: list[tuple[dict[str, str], ...]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for profile in profiles:
            profile = tuple(profile)
            if profile in seen:
                continue
            seen.add(profile)
            descriptors = tuple(
                {"name": name, "version": version} for name, version in profile
            )
            if self._profile_matches_input_envelopes(
                descriptors=descriptors,
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
                authenticated.append(descriptors)

        if len(authenticated) != 1:
            raise CandidateEvidencePacketError(
                "candidate factual-reduction extractor profile cannot be uniquely authenticated"
            )
        return authenticated[0]

    def _profile_matches_input_envelopes(
        self,
        *,
        descriptors: tuple[dict[str, str], ...],
        run: PipelineRun,
        change_run: PipelineRun,
        previous_extraction: PipelineRun,
        current_extraction: PipelineRun,
        previous_manifest: CaptureManifest,
        current_manifest: CaptureManifest,
        candidates: tuple,
        plans: tuple[AffectedFileCapturePlan, ...],
        gap_paths: tuple[str, ...],
    ) -> bool:
        for extraction_run, manifest in (
            (previous_extraction, previous_manifest),
            (current_extraction, current_manifest),
        ):
            expected = self._digest_json(
                {
                    "capture_manifest": manifest.model_dump(
                        mode="json", by_alias=True
                    ),
                    "artifact_extractors": list(descriptors),
                    "policy_version": extraction_run.policy_version,
                }
            )
            if extraction_run.inputs_hash != expected:
                return False

        first = next(
            item
            for item in self.store.list(CandidateFactualReduction)
            if item.reduction_run_id == run.run_id
        )
        reduction_inputs = {
            "diff_run_id": first.diff_run_id,
            "segmentation_run_id": first.segmentation_run_id,
            "planner_run_id": first.planner_run_id,
            "previous_capture": previous_manifest.model_dump(
                mode="json", by_alias=True
            ),
            "current_capture": current_manifest.model_dump(
                mode="json", by_alias=True
            ),
            "previous_extraction_run_id": previous_extraction.run_id,
            "current_extraction_run_id": current_extraction.run_id,
            "artifact_extractors": list(descriptors),
            "change_run_id": change_run.run_id,
            "candidates": [
                item.model_dump(mode="json", by_alias=True) for item in candidates
            ],
            "affected_file_plans": [
                item.model_dump(mode="json", by_alias=True) for item in plans
            ],
            "policy_version": run.policy_version,
        }
        if run.policy_version == self._GAP_REDUCTION_POLICY:
            reduction_inputs["extraction_gap_paths"] = list(gap_paths)
        if run.inputs_hash != self._digest_json(reduction_inputs):
            return False

        change_inputs = {
            "previous_capture_id": previous_manifest.capture_id,
            "current_capture_id": current_manifest.capture_id,
            "previous_source_revision_id": previous_manifest.source_revision_id,
            "current_source_revision_id": current_manifest.source_revision_id,
            "previous_extraction_run_id": previous_extraction.run_id,
            "current_extraction_run_id": current_extraction.run_id,
            "artifact_extractors": list(descriptors),
            "policy_version": change_run.policy_version,
            "artifact_inputs": {
                "previous": [
                    self._capture_reference_state(item)
                    for item in previous_manifest.artifacts
                ],
                "current": [
                    self._capture_reference_state(item)
                    for item in current_manifest.artifacts
                ],
            },
        }
        return change_run.inputs_hash == self._digest_json(change_inputs)

    def _authenticate_change_outputs(
        self,
        change_run: PipelineRun,
        candidates: tuple,
    ) -> tuple[tuple[ArtifactDelta, ...], tuple[StructuralDelta, ...]]:
        candidate_paths = {
            path for candidate in candidates for path in candidate.paths
        }
        artifacts = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(ArtifactDelta)
                    if item.diff_run_id == change_run.run_id
                ),
                key=lambda item: item.source_locator,
            )
        )
        structural = tuple(
            sorted(
                (
                    item
                    for item in self.store.list(StructuralDelta)
                    if item.diff_run_id == change_run.run_id
                ),
                key=lambda item: (
                    item.source_locator,
                    item.structural_key,
                    item.structural_delta_id,
                ),
            )
        )
        if any(item.source_locator not in candidate_paths for item in (*artifacts, *structural)):
            raise CandidateEvidencePacketError(
                "candidate factual change contains evidence outside segmentation paths"
            )
        expected_outputs = self._digest_json(
            {
                "artifact_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in artifacts
                ],
                "structural_deltas": [
                    item.model_dump(mode="json", by_alias=True) for item in structural
                ],
            }
        )
        if change_run.outputs_hash != expected_outputs:
            raise CandidateEvidencePacketError(
                "candidate factual change output envelope does not authenticate"
            )
        return artifacts, structural

    def _reconstruct_candidate_reductions(
        self,
        *,
        run: PipelineRun,
        pairs: tuple,
        plans: tuple[AffectedFileCapturePlan, ...],
        previous_manifest: CaptureManifest,
        current_manifest: CaptureManifest,
        artifact_deltas: tuple[ArtifactDelta, ...],
        structural_deltas: tuple[StructuralDelta, ...],
        gap_paths: tuple[str, ...],
    ) -> None:
        validator = CandidateFactualReductionService(self.store, None)
        previous_assertions = validator._assertion_signatures(
            previous_manifest, pairs[0][1].previous_extraction_run_id
        )
        current_assertions = validator._assertion_signatures(
            current_manifest, pairs[0][1].current_extraction_run_id
        )
        if run.policy_version == self._GAP_REDUCTION_POLICY:
            gap = set(gap_paths)
            previous_assertions = {
                path: value for path, value in previous_assertions.items() if path not in gap
            }
            current_assertions = {
                path: value for path, value in current_assertions.items() if path not in gap
            }

        plan_by_delta = {item.git_path_delta_id: item for item in plans}
        artifact_by_path = {item.source_locator: item for item in artifact_deltas}
        structural_by_path: dict[str, list[StructuralDelta]] = {}
        for item in structural_deltas:
            structural_by_path.setdefault(item.source_locator, []).append(item)
        previous_required = set(validator._required_paths(plans, previous=True))
        current_required = set(validator._required_paths(plans, previous=False))

        referenced_artifacts: set[str] = set()
        referenced_structural: set[str] = set()
        for candidate, actual in pairs:
            expected = validator._reduce_candidate(
                candidate,
                plan_by_delta,
                artifact_by_path,
                structural_by_path,
                previous_assertions,
                current_assertions,
                previous_required=previous_required,
                current_required=current_required,
                diff_run_id=actual.diff_run_id,
                planner_run_id=actual.planner_run_id,
                previous_capture_id=actual.previous_capture_id,
                current_capture_id=actual.current_capture_id,
                previous_extraction_run_id=actual.previous_extraction_run_id,
                current_extraction_run_id=actual.current_extraction_run_id,
                change_run_id=actual.change_run_id,
                reduction_run_id=run.run_id,
            ).model_copy(
                update={
                    "candidate_factual_reduction_id": (
                        actual.candidate_factual_reduction_id
                    )
                }
            )
            if actual != expected:
                raise CandidateEvidencePacketError(
                    "candidate factual reduction disagrees with reconstructed upstream evidence"
                )
            referenced_artifacts.update(actual.artifact_delta_ids)
            referenced_structural.update(actual.structural_delta_ids)

        if referenced_artifacts != {item.artifact_delta_id for item in artifact_deltas}:
            raise CandidateEvidencePacketError(
                "candidate factual reductions do not exactly cover ArtifactDelta evidence"
            )
        if referenced_structural != {
            item.structural_delta_id for item in structural_deltas
        }:
            raise CandidateEvidencePacketError(
                "candidate factual reductions do not exactly cover StructuralDelta evidence"
            )

    def _gap_paths_for_reduction(
        self,
        policy_version: str,
        previous_run_id: str,
        current_run_id: str,
    ) -> tuple[str, ...]:
        diagnostics = tuple(
            item
            for item in self.store.list(ExtractionDiagnostic)
            if item.run_id in {previous_run_id, current_run_id}
        )
        if policy_version != self._GAP_REDUCTION_POLICY and diagnostics:
            raise CandidateEvidencePacketError(
                "strict factual reduction cannot contain extraction diagnostics"
            )
        return tuple(sorted({item.source_locator for item in diagnostics}))

    @staticmethod
    def _capture_reference_state(item) -> dict[str, object]:
        return {
            "artifact_id": item.artifact_id,
            "source_locator": item.source_locator,
            "retrieval_status": item.retrieval_status.value,
            "content_hash": item.content_hash,
            "media_type": item.media_type,
        }

    @staticmethod
    def _round_robin_by_path(
        items: tuple,
        limit: int,
        *,
        path_of,
        item_key,
    ) -> tuple:
        if items and all(
            isinstance(item, tuple)
            and len(item) == 3
            and isinstance(item[0], AssertionSnapshotSide)
            for item in items
        ):
            side_groups: dict[AssertionSnapshotSide, dict[str, list]] = {
                AssertionSnapshotSide.PREVIOUS: {},
                AssertionSnapshotSide.CURRENT: {},
            }
            for item in items:
                side_groups[item[0]].setdefault(path_of(item), []).append(item)
            for groups in side_groups.values():
                for values in groups.values():
                    values.sort(key=item_key)

            selected: list = []
            depth = 0
            while len(selected) < limit:
                added = False
                for side in (
                    AssertionSnapshotSide.PREVIOUS,
                    AssertionSnapshotSide.CURRENT,
                ):
                    for path in sorted(side_groups[side]):
                        values = side_groups[side][path]
                        if depth < len(values):
                            selected.append(values[depth])
                            added = True
                            if len(selected) == limit:
                                break
                    if len(selected) == limit:
                        break
                if not added:
                    break
                depth += 1
            return tuple(selected)
        return _HardenedCandidateEvidencePacketService._round_robin_by_path(
            items,
            limit,
            path_of=path_of,
            item_key=item_key,
        )

    def _assertion_snapshots(
        self,
        reduction: CandidateFactualReduction,
    ) -> tuple[tuple[AssertionSnapshotSide, str, SourceAssertion], ...]:
        result = super()._assertion_snapshots(reduction)
        for _, path, assertion in result:
            if not (
                assertion.locator.startswith(path + ":")
                or assertion.locator.startswith(path + "#")
            ):
                raise CandidateEvidencePacketError(
                    "SourceAssertion locator must use an exact artifact-path namespace boundary"
                )
        return result

    def _structural_preview(self, item: StructuralDelta) -> StructuralDeltaPreview:
        previous, previous_truncated = self._preview_json(item.previous_value)
        current, current_truncated = self._preview_json(item.current_value)
        structural_key, key_truncated = self._preview_text(item.structural_key)
        return StructuralDeltaPreview(
            structural_delta_id=item.structural_delta_id,
            source_locator=item.source_locator,
            structural_key=structural_key,
            structural_key_truncated=key_truncated,
            change_type=item.change_type,
            extractor_name=item.extractor_name,
            extractor_version=item.extractor_version,
            previous_value_preview=previous,
            current_value_preview=current,
            value_preview_truncated=(previous_truncated or current_truncated),
        )

    def _assertion_preview(
        self,
        side: AssertionSnapshotSide,
        path: str,
        item: SourceAssertion,
    ) -> SourceAssertionPreview:
        statement, statement_truncated = self._preview_text(item.statement)
        locator, locator_truncated = self._preview_text(item.locator)
        return SourceAssertionPreview(
            assertion_id=item.assertion_id,
            side=side,
            source_locator=path,
            locator=locator,
            locator_truncated=locator_truncated,
            statement_preview=statement,
            statement_truncated=statement_truncated,
            extractor_name=item.extractor_name,
            extractor_version=item.extractor_version,
        )


__all__ = [
    "CandidateEvidencePacketError",
    "CandidateEvidencePacketResult",
    "CandidateEvidencePacketService",
    "ContractStore",
]
