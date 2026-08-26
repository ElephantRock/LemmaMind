"""Executable V1 basic review/feedback capture.

The service records feedback; it does not mutate the reviewed subject, promote
validation state, authenticate the supplied reviewer identity, or authorize actions.
Those remain explicit later-stage product/governance concerns.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .contracts import (
    CONTRACT_SCHEMA_VERSION,
    CONTRACT_TYPES,
    PipelineRun,
    ReviewDecision,
    ReviewDecisionType,
    RunType,
)
from .review_contracts import ReviewFeedback


class ReviewCaptureError(RuntimeError):
    """Review input or subject provenance is invalid."""


class ReviewStore(Protocol):
    def get_untyped(self, contract_type: str, record_id: str): ...

    def put_many(self, records): ...


DEFAULT_REVIEWABLE_SUBJECT_TYPES = frozenset(
    {
        "ArchitectureProfile",
        "TriageAssessment",
        "Observation",
        "Pattern",
        "ActionRecommendation",
    }
)


@dataclass(frozen=True)
class ReviewCaptureResult:
    decision: ReviewDecision
    feedback: ReviewFeedback
    run: PipelineRun

    def records(self) -> tuple:
        return (self.run, self.decision, self.feedback)


class ReviewFeedbackService:
    """Atomically record one explicit review decision and its provenance."""

    def __init__(
        self,
        store: ReviewStore,
        *,
        reviewable_subject_types: frozenset[str] = DEFAULT_REVIEWABLE_SUBJECT_TYPES,
        policy_version: str = "basic-review-feedback.v1",
        code_version: str = "lemmamind-0.1.0",
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self.reviewable_subject_types = reviewable_subject_types
        self.policy_version = policy_version
        self.code_version = code_version
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def record(
        self,
        *,
        subject_type: str,
        subject_id: str,
        decision: ReviewDecisionType,
        reviewer_id: str,
        notes: str = "",
    ) -> ReviewCaptureResult:
        subject_type = subject_type.strip()
        subject_id = subject_id.strip()
        reviewer_id = reviewer_id.strip()
        if not subject_type or not subject_id or not reviewer_id:
            raise ReviewCaptureError("subject_type, subject_id, and reviewer_id are required")
        if subject_type not in CONTRACT_TYPES:
            raise ReviewCaptureError(f"unknown review subject contract type: {subject_type}")
        if subject_type not in self.reviewable_subject_types:
            raise ReviewCaptureError(f"contract type is not reviewable in V1: {subject_type}")

        subject = self.store.get_untyped(subject_type, subject_id)
        if subject is None:
            raise ReviewCaptureError(f"review subject does not exist: {subject_type}:{subject_id}")
        if subject.record_id != subject_id:
            raise ReviewCaptureError("review subject identity does not match requested subject_id")

        decided_at = self._aware_now()
        token = self.id_factory()
        run_id = f"run:review:{token}"
        review_id = f"review:{self.id_factory()}"
        feedback_id = f"review-feedback:{self.id_factory()}"

        review = ReviewDecision(
            review_id=review_id,
            subject_id=subject_id,
            decision=decision,
            decided_at=decided_at,
            notes=notes,
        )
        feedback = ReviewFeedback(
            review_feedback_id=feedback_id,
            review_id=review_id,
            subject_type=subject_type,
            subject_id=subject_id,
            reviewer_id=reviewer_id,
            review_run_id=run_id,
            recorded_at=decided_at,
        )
        inputs = {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "decision": decision.value,
            "reviewer_id": reviewer_id,
            "notes": notes,
            "policy_version": self.policy_version,
        }
        outputs = {
            "review": review.model_dump(mode="json"),
            "feedback": feedback.model_dump(mode="json"),
        }
        run = PipelineRun(
            run_id=run_id,
            run_type=RunType.EVALUATION,
            code_version=self.code_version,
            contract_schema_version=CONTRACT_SCHEMA_VERSION,
            policy_version=self.policy_version,
            started_at=decided_at,
            finished_at=decided_at,
            inputs_hash=self._digest_json(inputs),
            outputs_hash=self._digest_json(outputs),
        )
        self.store.put_many((run, review, feedback))
        return ReviewCaptureResult(decision=review, feedback=feedback, run=run)

    def _aware_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewCaptureError("review clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _digest_json(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
