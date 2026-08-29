from lemmamind.change_contracts import ArtifactDelta, ArtifactDeltaType, StructuralDelta, StructuralDeltaType
from lemmamind.contracts import EvidenceFact, RetrievalStatus, SourceAssertion


def test_evidence_and_change_contracts_preserve_exact_whitespace_bearing_locators() -> None:
    path = " src/core.py "
    fact_locator = f"{path}#content"
    assertion_locator = f"{path}:L1-L1"

    fact = EvidenceFact(
        evidence_id="fact:test",
        artifact_id="artifact:test",
        locator=fact_locator,
        raw_value="new",
        normalized_value="new",
        extractor_name="content-fact",
        extractor_version="1",
        run_id="run:extract",
    )
    assertion = SourceAssertion(
        assertion_id="assertion:test",
        artifact_id="artifact:test",
        locator=assertion_locator,
        statement="claim",
        extractor_name="content-assertion",
        extractor_version="1",
        run_id="run:extract",
    )
    artifact_delta = ArtifactDelta(
        artifact_delta_id="artifact-delta:test",
        source_id="github:test",
        previous_source_revision_id="github:test@" + "a" * 40,
        current_source_revision_id="github:test@" + "b" * 40,
        previous_capture_id="capture:previous",
        current_capture_id="capture:current",
        source_locator=path,
        change_type=ArtifactDeltaType.CONTENT_CHANGED,
        previous_artifact_id="artifact:previous",
        current_artifact_id="artifact:current",
        previous_retrieval_status=RetrievalStatus.CAPTURED,
        current_retrieval_status=RetrievalStatus.CAPTURED,
        previous_content_hash="sha256:" + "1" * 64,
        current_content_hash="sha256:" + "2" * 64,
        previous_media_type="text/plain",
        current_media_type="text/plain",
        diff_run_id="run:diff",
    )
    structural_delta = StructuralDelta(
        structural_delta_id="structural-delta:test",
        artifact_delta_id=artifact_delta.artifact_delta_id,
        source_id="github:test",
        previous_source_revision_id=artifact_delta.previous_source_revision_id,
        current_source_revision_id=artifact_delta.current_source_revision_id,
        source_locator=path,
        structural_key="content-fact@1:#content",
        change_type=StructuralDeltaType.MODIFIED,
        extractor_name="content-fact",
        extractor_version="1",
        previous_evidence_id="fact:previous",
        current_evidence_id="fact:current",
        previous_locator=fact_locator,
        current_locator=fact_locator,
        previous_value="old",
        current_value="new",
        diff_run_id="run:diff",
    )

    assert fact.locator == fact_locator
    assert assertion.locator == assertion_locator
    assert artifact_delta.source_locator == path
    assert structural_delta.source_locator == path
    assert structural_delta.previous_locator == fact_locator
    assert structural_delta.current_locator == fact_locator
