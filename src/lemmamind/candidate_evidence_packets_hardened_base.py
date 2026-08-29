"""Hardened public surface for deterministic full-M5 candidate evidence packets.

The original packet implementation is retained verbatim in
``candidate_evidence_packets_base`` so this module can apply review-driven
fail-closed hardening without duplicating the full implementation in the active
surface. The subclass tightens three boundaries: authenticated extraction policy
allowlisting, exact diagnostic-to-gap-signal coverage, and assertion preview
balancing across snapshot sides.
"""
from __future__ import annotations

from .candidate_evidence_packet_contracts import AssertionSnapshotSide
from .candidate_evidence_packets_base import (
    CandidateEvidencePacketError,
    CandidateEvidencePacketResult,
    CandidateEvidencePacketService as _BaseCandidateEvidencePacketService,
    ContractStore,
)
from .candidate_reduction_contracts import CandidateFactualReduction
from .contracts import RunType
from .extraction_diagnostic_contracts import ExtractionDiagnostic


class CandidateEvidencePacketService(_BaseCandidateEvidencePacketService):
    """Build bounded packets while failing closed on provenance/coverage gaps."""

    _GAP_TOLERANT_EXTRACTION_POLICY = "deterministic-evidence.gap-tolerant.v1"

    def __init__(self, *args, max_assertion_previews: int = 128, **kwargs) -> None:
        if max_assertion_previews < 2:
            raise ValueError(
                "max_assertion_previews must be at least 2 to preserve both snapshot sides"
            )
        super().__init__(
            *args,
            max_assertion_previews=max_assertion_previews,
            **kwargs,
        )

    @staticmethod
    def _round_robin_by_path(
        items: tuple,
        limit: int,
        *,
        path_of,
        item_key,
    ) -> tuple:
        """Round-robin by path, and by side for authored assertion snapshots."""

        groups: dict[object, list] = {}
        for item in items:
            path = path_of(item)
            group_key: object = path
            if (
                isinstance(item, tuple)
                and len(item) == 3
                and isinstance(item[0], AssertionSnapshotSide)
            ):
                group_key = (path, item[0].value)
            groups.setdefault(group_key, []).append(item)
        for values in groups.values():
            values.sort(key=item_key)

        selected: list = []
        depth = 0
        group_keys = sorted(groups, key=lambda value: str(value))
        while len(selected) < limit:
            added = False
            for group_key in group_keys:
                values = groups[group_key]
                if depth < len(values):
                    selected.append(values[depth])
                    added = True
                    if len(selected) == limit:
                        break
            if not added:
                break
            depth += 1
        return tuple(selected)

    def _gap_signals(
        self,
        reduction: CandidateFactualReduction,
    ):
        """Require exact coverage of authenticated candidate-local diagnostics."""

        result = super()._gap_signals(reduction)
        candidate_paths = set(reduction.paths)

        expected_previous = tuple(
            sorted(
                item.extraction_diagnostic_id
                for item in self.store.list(ExtractionDiagnostic)
                if item.run_id == reduction.previous_extraction_run_id
                and item.source_locator in candidate_paths
            )
        )
        expected_current = tuple(
            sorted(
                item.extraction_diagnostic_id
                for item in self.store.list(ExtractionDiagnostic)
                if item.run_id == reduction.current_extraction_run_id
                and item.source_locator in candidate_paths
            )
        )
        expected_paths = tuple(
            sorted(
                {
                    item.source_locator
                    for item in self.store.list(ExtractionDiagnostic)
                    if item.run_id
                    in {
                        reduction.previous_extraction_run_id,
                        reduction.current_extraction_run_id,
                    }
                    and item.source_locator in candidate_paths
                }
            )
        )

        referenced_previous = tuple(
            sorted(
                diagnostic_id
                for signal in result
                for diagnostic_id in signal.previous_diagnostic_ids
            )
        )
        referenced_current = tuple(
            sorted(
                diagnostic_id
                for signal in result
                for diagnostic_id in signal.current_diagnostic_ids
            )
        )
        referenced_paths = tuple(
            sorted({path for signal in result for path in signal.paths})
        )

        if len(referenced_previous) != len(set(referenced_previous)) or len(
            referenced_current
        ) != len(set(referenced_current)):
            raise CandidateEvidencePacketError(
                "candidate extraction-gap signals duplicate diagnostic identities"
            )
        if (
            referenced_previous != expected_previous
            or referenced_current != expected_current
            or referenced_paths != expected_paths
        ):
            raise CandidateEvidencePacketError(
                "candidate extraction-gap signals do not exactly cover authenticated diagnostics"
            )
        return result

    def _authenticate_extraction_run(self, run_id: str) -> None:
        run = self._completed_run(run_id, RunType.EXTRACTION, "extraction")
        if run.policy_version not in {
            self._STRICT_EXTRACTION_POLICY,
            self._GAP_TOLERANT_EXTRACTION_POLICY,
        }:
            raise CandidateEvidencePacketError(
                "candidate evidence packets reject unrecognized extraction policies"
            )
        super()._authenticate_extraction_run(run_id)


__all__ = [
    "CandidateEvidencePacketError",
    "CandidateEvidencePacketResult",
    "CandidateEvidencePacketService",
    "ContractStore",
]
