"""M1 curated-discovery lineage over already-resolved Sources.

Discovery answers why and when a Source entered LemmaMind. It deliberately does
not create canonical Source identities, infer source roles, assign repository
relationships, or capture revisions. Those responsibilities belong to adjacent
layers, especially the M2 repository registry.
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
    """A discovery run violates lineage or source-identity constraints."""


@dataclass(frozen=True)
class DiscoveryCandidate:
    """One channel-local locator already resolved to a canonical Source."""

    source_id: str
    discovered_locator: str


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
        """Record one channel run after Source identities have already been resolved.

        Zero-hit runs are valid: a saved search or other future channel may execute
        successfully without discovering any Sources. Within one run, however, a
        Source may appear only once so repeated aliases cannot inflate discovery
        counts.
        """

        started_at = self._aware_now()
        seen_sources: set[str] = set()
        normalized: list[DiscoveryCandidate] = []
        for candidate in candidates:
            source_id = candidate.source_id.strip()
            locator = candidate.discovered_locator.strip()
            if not source_id:
                raise DiscoveryError("DiscoveryCandidate.source_id must not be empty")
            if not locator:
                raise DiscoveryError("DiscoveryCandidate.discovered_locator must not be empty")
            if source_id in seen_sources:
                raise DiscoveryError(f"duplicate Source in one discovery run: {source_id}")
            if self.store.get(Source, source_id) is None:
                raise DiscoveryError(
                    "discovery requires an already-resolved Source; "
                    f"unknown source_id: {source_id}"
                )
            seen_sources.add(source_id)
            normalized.append(DiscoveryCandidate(source_id, locator))

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
