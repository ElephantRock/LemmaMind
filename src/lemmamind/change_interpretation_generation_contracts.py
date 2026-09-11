"""Durable lineage envelope for one ChangeInterpretation generation."""
from __future__ import annotations

from pydantic import model_validator

from .contracts import CONTRACT_TYPES, ContractModel, Identifier


class ChangeInterpretationGeneration(ContractModel):
    """Bind a reasoning run to its packet generation and interpreter identity."""

    record_id_field = "change_interpretation_generation_id"

    change_interpretation_generation_id: Identifier
    interpretation_run_id: Identifier
    packet_run_id: Identifier
    interpreter_name: Identifier
    interpreter_version: Identifier
    policy_version: Identifier
    change_interpretation_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_generation(self) -> "ChangeInterpretationGeneration":
        if self.change_interpretation_ids != tuple(
            sorted(set(self.change_interpretation_ids))
        ):
            raise ValueError("change_interpretation_ids must be sorted and unique")
        return self


CONTRACT_TYPES[ChangeInterpretationGeneration.__name__] = ChangeInterpretationGeneration

CHANGE_INTERPRETATION_GENERATION_CONTRACT_TYPES: dict[str, type[ContractModel]] = {
    ChangeInterpretationGeneration.__name__: ChangeInterpretationGeneration,
}
