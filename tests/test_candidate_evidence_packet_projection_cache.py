from lemmamind.candidate_evidence_packets import CandidateEvidencePacketService
from lemmamind.candidate_reduction_contracts import CandidateFactualReduction
from lemmamind.change_contracts import StructuralDelta
from tests.test_candidate_evidence_packets import (
    EXTRACTOR_PROFILE,
    REDUCTION_RUN_ID,
    STRUCTURAL_DELTA_ID,
    prepare,
)


class ManifestCountingPacketService(CandidateEvidencePacketService):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.manifest_calls = 0

    def _manifest(self, capture_id: str, source_revision_id: str):
        self.manifest_calls += 1
        return super()._manifest(capture_id, source_revision_id)


def test_structural_projection_reuses_maps_only_after_full_authentication(tmp_path) -> None:
    store = prepare(tmp_path)
    reduction = store.list(CandidateFactualReduction)[0]
    structural = store.get(StructuralDelta, STRUCTURAL_DELTA_ID)
    assert structural is not None

    direct = ManifestCountingPacketService(store, artifact_extractors=EXTRACTOR_PROFILE)
    direct._validate_structural_evidence(structural, reduction)
    assert direct.manifest_calls == 2

    service = ManifestCountingPacketService(store, artifact_extractors=EXTRACTOR_PROFILE)
    service._authenticated_reduction_generation(REDUCTION_RUN_ID)
    authenticated_manifest_calls = service.manifest_calls

    service._validate_structural_evidence(structural, reduction)
    service._validate_structural_evidence(structural, reduction)

    assert service.manifest_calls == authenticated_manifest_calls
    assert service._projection_ready is True


def test_cached_projection_preserves_packet_payload(tmp_path) -> None:
    store = prepare(tmp_path)
    service = CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE)
    reduction_run, pairs = service._authenticated_reduction_generation(REDUCTION_RUN_ID)
    assert reduction_run.run_id == REDUCTION_RUN_ID
    candidate, reduction = pairs[0]

    cached = service._build_packet(reduction, candidate, "run:packet:cached")

    service._reset_projection_cache()
    uncached = service._build_packet(reduction, candidate, "run:packet:cached")

    assert service._stable_packet_payload(cached) == service._stable_packet_payload(uncached)
