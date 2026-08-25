"""Deterministic JSON scalar evidence for explicitly selected artifacts.

This extractor is intentionally not part of the default broad artifact policy yet.
Callers opt into it when a captured JSON document is itself a governed source of
machine-readable facts. Scalar leaves become EvidenceFact candidates addressed by
RFC 6901-style JSON Pointer locators; no interpretation is performed.
"""
from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any

from .contracts import Artifact
from .extraction import ExtractionError, FactSpec


class JsonPointerExtractor:
    """Emit deterministic scalar JSON leaves with exact pointer provenance."""

    name = "json-pointer"
    version = "1"

    def supports(self, artifact: Artifact) -> bool:
        return PurePosixPath(artifact.source_locator).suffix.lower() == ".json"

    def extract(self, artifact: Artifact, data: bytes) -> tuple[FactSpec, ...]:
        try:
            text = data.decode("utf-8")
            document = json.loads(text, parse_constant=self._reject_nonfinite)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ExtractionError(f"invalid JSON: {artifact.source_locator}") from exc

        facts: list[FactSpec] = []
        self._walk(artifact, document, pointer="", facts=facts)
        return tuple(facts)

    def _walk(
        self,
        artifact: Artifact,
        value: Any,
        *,
        pointer: str,
        facts: list[FactSpec],
    ) -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                escaped = self._escape_pointer_token(str(key))
                self._walk(
                    artifact,
                    value[key],
                    pointer=f"{pointer}/{escaped}",
                    facts=facts,
                )
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._walk(
                    artifact,
                    item,
                    pointer=f"{pointer}/{index}",
                    facts=facts,
                )
            return
        if value is None or isinstance(value, (str, int, float, bool)):
            facts.append(
                FactSpec(
                    locator=f"{artifact.source_locator}#{pointer}",
                    raw_value=value,
                    normalized_value=value,
                    extractor_name=self.name,
                    extractor_version=self.version,
                )
            )
            return
        raise ExtractionError(
            f"unsupported JSON scalar type at {artifact.source_locator}#{pointer}"
        )

    @staticmethod
    def _escape_pointer_token(value: str) -> str:
        return value.replace("~", "~0").replace("/", "~1")

    @staticmethod
    def _reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON number is not accepted: {value}")
