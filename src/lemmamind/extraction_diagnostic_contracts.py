"""Durable contracts for source-local deterministic extraction gaps."""
from __future__ import annotations

from .contracts import (
    CONTRACT_TYPES,
    ContractModel,
    Identifier,
    SourceLocator,
)


class ExtractionDiagnostic(ContractModel):
    """One recoverable extractor failure bound to one captured source revision."""

    record_id_field = "extraction_diagnostic_id"

    extraction_diagnostic_id: Identifier
    capture_id: Identifier
    source_revision_id: Identifier
    artifact_id: Identifier
    source_locator: SourceLocator
    extractor_name: Identifier
    extractor_version: Identifier
    error_type: Identifier
    error_message: str
    run_id: Identifier


CONTRACT_TYPES[ExtractionDiagnostic.__name__] = ExtractionDiagnostic

EXTRACTION_DIAGNOSTIC_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    ExtractionDiagnostic.__name__: ExtractionDiagnostic,
}
