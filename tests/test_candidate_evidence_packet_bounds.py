import pytest

from lemmamind.candidate_evidence_packet_contracts import AssertionSnapshotSide
from lemmamind.candidate_evidence_packets import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketService,
)
from lemmamind.candidate_reduction_contracts import CandidateFactualReduction
from lemmamind.change_contracts import StructuralDelta
from lemmamind.contracts import SourceAssertion
from lemmamind.storage import SQLiteContractStore
from tests.test_candidate_evidence_packets import (
    PATH,
    PREVIOUS_ARTIFACT_ID,
    PREVIOUS_EXTRACTION_RUN_ID,
    STRUCTURAL_DELTA_ID,
    prepare as prepare_packet_store,
)


def test_long_assertion_locator_is_bounded_with_explicit_truncation(tmp_path) -> None:
    service = CandidateEvidencePacketService(
        SQLiteContractStore(tmp_path / "lemmamind.db")
    )
    assertion = SourceAssertion(
        assertion_id="assertion:long-locator",
        artifact_id="artifact:long-locator",
        locator=PATH + ":" + "x" * 2000,
        statement="bounded statement",
        extractor_name="authored",
        extractor_version="1",
        run_id="run:long-locator",
    )

    preview = service._assertion_preview(
        AssertionSnapshotSide.CURRENT,
        PATH,
        assertion,
    )

    assert len(preview.locator) <= 512
    assert preview.locator_truncated is True
    assert preview.statement_truncated is False


def test_long_structural_key_is_bounded_with_explicit_truncation(tmp_path) -> None:
    store = prepare_packet_store(tmp_path)
    delta = store.get(StructuralDelta, STRUCTURAL_DELTA_ID)
    assert delta is not None
    long_delta = delta.model_copy(update={"structural_key": "k" * 2000})

    preview = CandidateEvidencePacketService(store)._structural_preview(long_delta)

    assert len(preview.structural_key) <= 512
    assert preview.structural_key_truncated is True


def test_bounded_packet_policy_rejects_context_expanding_configuration(tmp_path) -> None:
    store = SQLiteContractStore(tmp_path / "lemmamind.db")

    with pytest.raises(ValueError, match="max_structural_previews exceeds"):
        CandidateEvidencePacketService(store, max_structural_previews=257)
    with pytest.raises(ValueError, match="max_assertion_previews exceeds"):
        CandidateEvidencePacketService(store, max_assertion_previews=129)
    with pytest.raises(ValueError, match="preview_chars exceeds"):
        CandidateEvidencePacketService(store, preview_chars=513)


def test_assertion_locator_requires_exact_artifact_namespace_boundary(tmp_path) -> None:
    store = prepare_packet_store(tmp_path)
    reduction = store.list(CandidateFactualReduction)[0]
    store.put(
        SourceAssertion(
            assertion_id="assertion:packet:malformed-boundary",
            artifact_id=PREVIOUS_ARTIFACT_ID,
            locator=PATH + ".bak:L1-L1",
            statement="malformed locator namespace",
            extractor_name="authored",
            extractor_version="1",
            run_id=PREVIOUS_EXTRACTION_RUN_ID,
        )
    )

    with pytest.raises(
        CandidateEvidencePacketError,
        match="exact artifact-path namespace boundary",
    ):
        CandidateEvidencePacketService(store)._assertion_snapshots(reduction)
