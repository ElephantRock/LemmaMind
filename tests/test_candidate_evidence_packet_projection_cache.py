from contextlib import contextmanager

import pytest

from lemmamind.candidate_evidence_packet_generation_contracts import (
    CandidateEvidencePacketGeneration,
)
from lemmamind.candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
    _AuthenticatedCandidateEvidencePacketService,
)
from lemmamind.candidate_reduction_contracts import (
    CandidateFactualReduction,
    CandidateReductionDisposition,
    CandidateSignalKind,
)
from lemmamind.change_contracts import StructuralDelta
from lemmamind.contracts import PipelineRun, SourceAssertion
from lemmamind.interval_segmentation_contracts import IntervalCandidateSegment
from lemmamind.storage import SQLiteContractStore
from tests.test_candidate_evidence_packets import (
    CURRENT_ARTIFACT_ID,
    CURRENT_EXTRACTION_RUN_ID,
    EXTRACTOR_PROFILE,
    PATH,
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


class TamperBeforeTransactionStore(SQLiteContractStore):
    def __init__(self, path) -> None:
        super().__init__(path)
        self.pending_record = None

    @contextmanager
    def transaction(self):
        if self.pending_record is not None:
            record = self.pending_record
            self.pending_record = None
            self.put(record)
        with super().transaction() as transaction:
            yield transaction


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


def test_cached_projection_preserves_packet_payload_and_discards_cache(tmp_path) -> None:
    store = prepare(tmp_path)
    service = CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE)
    reduction_run, pairs = service._authenticated_reduction_generation(REDUCTION_RUN_ID)
    assert reduction_run.run_id == REDUCTION_RUN_ID
    candidate, reduction = pairs[0]

    cached = service._build_packet(reduction, candidate, "run:packet:cached")

    assert service._projection_ready is False
    uncached = service._build_packet(reduction, candidate, "run:packet:cached")

    assert service._stable_packet_payload(cached) == service._stable_packet_payload(uncached)


def test_final_projection_reauth_rejects_post_auth_extraction_tampering(tmp_path) -> None:
    store = prepare(tmp_path)
    service = CandidateEvidencePacketService(store, artifact_extractors=EXTRACTOR_PROFILE)
    _, pairs = service._authenticated_reduction_generation(REDUCTION_RUN_ID)
    candidate, reduction = pairs[0]

    store.put(
        SourceAssertion(
            assertion_id="assertion:projection:post-auth-tamper",
            artifact_id=CURRENT_ARTIFACT_ID,
            locator=f"{PATH}:L9-L9",
            statement="appended after packet lineage authentication",
            extractor_name="authored",
            extractor_version="1",
            run_id=CURRENT_EXTRACTION_RUN_ID,
        )
    )

    with pytest.raises(
        CandidateEvidencePacketError,
        match="output envelope does not authenticate",
    ):
        service._build_packet(
            reduction,
            candidate,
            "run:packet:post-auth-tamper",
        )
    assert service._projection_ready is False


def test_atomic_persistence_reauth_rejects_extraction_tamper_after_projection(tmp_path) -> None:
    prepared = prepare(tmp_path)
    store = TamperBeforeTransactionStore(prepared.path)
    tamper = SourceAssertion(
        assertion_id="assertion:projection:pre-transaction-tamper",
        artifact_id=CURRENT_ARTIFACT_ID,
        locator=f"{PATH}:L10-L10",
        statement="appended after final packet projection",
        extractor_name="authored",
        extractor_version="1",
        run_id=CURRENT_EXTRACTION_RUN_ID,
    )
    store.pending_record = tamper
    service = CandidateEvidencePacketService(
        store,
        artifact_extractors=EXTRACTOR_PROFILE,
        id_factory=lambda: "atomic-persistence",
    )

    with pytest.raises(
        CandidateEvidencePacketError,
        match="output envelope does not authenticate",
    ):
        service.build_reduction(REDUCTION_RUN_ID)

    assert store.get(SourceAssertion, tamper.assertion_id) == tamper
    assert store.list(CandidateEvidencePacketGeneration) == []


def test_atomic_persistence_reauth_rejects_non_extraction_lineage_tamper(tmp_path) -> None:
    prepared = prepare(tmp_path)
    store = TamperBeforeTransactionStore(prepared.path)
    original = store.list(CandidateFactualReduction)[0]
    tamper = original.model_copy(
        update={
            "candidate_factual_reduction_id": "reduction:projection:pre-transaction-tamper",
        }
    )
    store.pending_record = tamper
    service = CandidateEvidencePacketService(
        store,
        artifact_extractors=EXTRACTOR_PROFILE,
        id_factory=lambda: "atomic-full-lineage",
    )

    with pytest.raises(
        CandidateEvidencePacketError,
        match="duplicate candidates",
    ):
        service.build_reduction(REDUCTION_RUN_ID)

    assert (
        store.get(
            CandidateFactualReduction,
            tamper.candidate_factual_reduction_id,
        )
        == tamper
    )
    assert store.list(CandidateEvidencePacketGeneration) == []


def test_zero_retained_generation_discards_projection_cache(tmp_path, monkeypatch) -> None:
    store = prepare(tmp_path)
    candidate = store.list(IntervalCandidateSegment)[0]
    reduction = store.list(CandidateFactualReduction)[0].model_copy(
        update={
            "policy_suppressed_paths": (PATH,),
            "signal_kinds": (CandidateSignalKind.POLICY_SUPPRESSED,),
            "disposition": CandidateReductionDisposition.SUPPRESS,
        }
    )
    reduction_run = store.get(PipelineRun, REDUCTION_RUN_ID)
    assert reduction_run is not None

    def authenticated_zero_retained(_service, reduction_run_id):
        assert reduction_run_id == REDUCTION_RUN_ID
        return reduction_run, ((candidate, reduction),)

    monkeypatch.setattr(
        _AuthenticatedCandidateEvidencePacketService,
        "_authenticated_reduction_generation",
        authenticated_zero_retained,
    )
    service = CandidateEvidencePacketService(
        store,
        artifact_extractors=EXTRACTOR_PROFILE,
        id_factory=lambda: "zero-retained",
    )

    result = service.build_reduction(REDUCTION_RUN_ID)

    assert result.packets == ()
    assert service._projection_ready is False
