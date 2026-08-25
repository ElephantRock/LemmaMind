"""M1 curated-discovery lineage over raw channel hits and optional Source links.

Discovery answers why and when a candidate entered LemmaMind. It deliberately
does not create canonical Source identities, infer source roles, assign repository
relationships, or capture revisions. A hit may already be linked to a Source when
identity is known; otherwise the raw locator remains durable for later M2 registry
resolution.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    DiscoveryChannel,
    DiscoveryHit,
    DiscoveryRun,
    PipelineRun,
    RunType,
    Source,
)


class DiscoveryError(RuntimeError):
    """A discovery run violates lineage or identity-link constraints."""


@dataclass(frozen=True)
class DiscoveryCandidate:
    """One channel-local locator, optionally linked to a canonical Source."""

    discovered_locator: str
    source_id: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    channel: DiscoveryChannel
    discovery_run: DiscoveryRun
    hits: tuple[DiscoveryHit, ...]
    pipeline_run: PipelineRun

    def records(self) -> tuple:
        return (self.channel, self.pipeline_run, self.discovery_run, *self.hits)


class DiscoveryService:
    """Persist one immutable DiscoveryChannel → Run → Hit lineage generation."""

    def __init__(
        self,
        store,
        *,
        policy_version: str = "discovery-lineage.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def record_run(
        self,
        *,
        channel: DiscoveryChannel,
        candidates: tuple[DiscoveryCandidate, ...],
        input_snapshot: object,
    ) -> DiscoveryResult:
        """Record one channel run without requiring M2 identity completion.

        Zero-hit runs are valid. Each raw locator may occur only once per run. If
        multiple hits are already linked to Sources, one Source may also occur only
        once so known aliases cannot inflate the run.
        """

        started_at = self._aware_now()
        seen_locators: set[str] = set()
        seen_sources: set[str] = set()
        normalized: list[DiscoveryCandidate] = []
        for candidate in candidates:
            locator = candidate.discovered_locator.strip()
            if not locator:
                raise DiscoveryError("DiscoveryCandidate.discovered_locator must not be empty")
            if locator in seen_locators:
                raise DiscoveryError(f"duplicate locator in one discovery run: {locator}")
            seen_locators.add(locator)

            source_id: str | None = None
            if candidate.source_id is not None:
                source_id = candidate.source_id.strip()
                if not source_id:
                    raise DiscoveryError(
                        "DiscoveryCandidate.source_id must be non-empty when provided"
                    )
                if source_id in seen_sources:
                    raise DiscoveryError(f"duplicate Source in one discovery run: {source_id}")
                if self.store.get(Source, source_id) is None:
                    raise DiscoveryError(
                        "discovery Source link must resolve to an existing Source; "
                        f"unknown source_id: {source_id}"
                    )
                seen_sources.add(source_id)
            normalized.append(DiscoveryCandidate(locator, source_id))

        discovery_run_id = f"discovery-run:{self.id_factory()}"
        pipeline_run_id = f"run:{self.id_factory()}"
        hits = tuple(
            DiscoveryHit(
                discovery_hit_id=f"discovery-hit:{discovery_run_id}:{ordinal}",
                discovery_run_id=discovery_run_id,
                source_id=candidate.source_id,
                ordinal=ordinal,
                discovered_locator=candidate.discovered_locator,
            )
            for ordinal, candidate in enumerate(normalized, start=1)
        )
        observed_at = self._aware_now()
        discovery_run = DiscoveryRun(
            discovery_run_id=discovery_run_id,
            discovery_channel_id=channel.discovery_channel_id,
            pipeline_run_id=pipeline_run_id,
            observed_at=observed_at,
            hit_count=len(hits),
        )

        inputs_hash = self._digest_json(
            {
                "channel": channel.model_dump(mode="json"),
                "input_snapshot": input_snapshot,
                "candidates": [
                    {
                        "source_id": candidate.source_id,
                        "discovered_locator": candidate.discovered_locator,
                    }
                    for candidate in normalized
                ],
                "policy_version": self.policy_version,
            }
        )
        outputs_hash = self._digest_json(
            {
                "discovery_run": discovery_run.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json") for hit in hits],
            }
        )
        pipeline_run = PipelineRun(
            run_id=pipeline_run_id,
            run_type=RunType.DISCOVERY,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=started_at,
            finished_at=observed_at,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
        )
        result = DiscoveryResult(channel, discovery_run, hits, pipeline_run)
        self.store.put_many(result.records())
        return result

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise DiscoveryError("discovery clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _digest_json(value: object) -> str:
        try:
            encoded = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise DiscoveryError("discovery input_snapshot must be canonical JSON data") from exc
        return "sha256:" + hashlib.sha256(encoded).hexdigest()
