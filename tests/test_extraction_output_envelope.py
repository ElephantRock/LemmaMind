from datetime import datetime, timezone

import pytest

from lemmamind.change_intelligence import (
    ChangeIntelligenceError,
    DeterministicChangeService,
)
from lemmamind.contracts import (
    CONTRACT_SCHEMA_VERSION,
    PipelineRun,
    RunType,
)
from lemmamind.extraction_diagnostic_contracts import ExtractionDiagnostic


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)
DIGEST = "sha256:" + "0" * 64


class Store:
    def __init__(self, records=()):
        self.records = list(records)

    def get(self, model, record_id):
        for item in self.records:
            if isinstance(item, model) and getattr(item, item.record_id_field) == record_id:
                return item
        return None

    def list(self, model):
        return [item for item in self.records if isinstance(item, model)]

    def put_many(self, records):
        self.records.extend(records)


def _service(store):
    return DeterministicChangeService(store, None)


def _run(outputs_hash, *, policy_version="org.partial.v1"):
    return PipelineRun(
        run_id="run:extraction:test",
        run_type=RunType.EXTRACTION,
        code_version="lemmamind-0.1.0",
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        policy_version=policy_version,
        started_at=NOW,
        finished_at=NOW,
        inputs_hash=DIGEST,
        outputs_hash=outputs_hash,
    )


def _diagnostic():
    return ExtractionDiagnostic(
        extraction_diagnostic_id="extraction-diagnostic:test",
        capture_id="capture:test",
        source_revision_id="github:test@" + "a" * 40,
        artifact_id="artifact:test",
        source_locator="src/bad.ts",
        extractor_name="typescript-ast",
        extractor_version="1",
        error_type="TypeScriptAstExtractionError",
        error_message="syntactic parse failure",
        run_id="run:extraction:test",
    )


def test_strict_comparison_rejects_clean_gap_mode_with_custom_policy_name() -> None:
    store = Store()
    service = _service(store)
    gap_hash = service._digest_json(
        {"facts": [], "assertions": [], "diagnostics": []}
    )
    run = _run(gap_hash, policy_version="org.partial.v1")
    store.records.append(run)

    service._authenticate_gap_tolerant_extraction_run(run)
    with pytest.raises(
        ChangeIntelligenceError,
        match="gap-tolerant extraction runs",
    ):
        service._require_strict_extraction_run(run)


def test_appended_diagnostic_invalidates_committed_gap_output_envelope() -> None:
    diagnostic = _diagnostic()
    store = Store((diagnostic,))
    service = _service(store)
    committed_hash = service._digest_json(
        {"facts": [], "assertions": [], "diagnostics": []}
    )
    run = _run(committed_hash)

    with pytest.raises(
        ChangeIntelligenceError,
        match="output envelope does not authenticate",
    ):
        service._authenticate_gap_tolerant_extraction_run(run)


def test_authenticated_diagnostic_envelope_is_accepted_by_gap_authenticator() -> None:
    diagnostic = _diagnostic()
    store = Store((diagnostic,))
    service = _service(store)
    committed_hash = service._digest_json(
        {
            "facts": [],
            "assertions": [],
            "diagnostics": [service._diagnostic_payload(diagnostic)],
        }
    )
    run = _run(committed_hash)

    service._authenticate_gap_tolerant_extraction_run(run)
