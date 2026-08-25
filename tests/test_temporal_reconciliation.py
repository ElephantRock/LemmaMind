from datetime import datetime, timezone

import pytest

from lemmamind.contracts import (
    Observation,
    ObservationEpistemicType,
    RepositoryIdentity,
    Source,
    SourceKind,
    SourceRevision,
    SourceRole,
    SupportType,
    ValidationState,
)
from lemmamind.github_process import (
    GitHubProcessCaptureService,
    GitHubProcessEvidenceService,
    ProcessKind,
    ProcessRef,
)
from lemmamind.github_process_events import (
    GitHubProcessEventCaptureService,
    GitHubProcessEventEvidenceService,
)
from lemmamind.objects import ContentAddressedFileStore
from lemmamind.observations import SupportRef
from lemmamind.observations_v2 import ObservationConstructionServiceV2
from lemmamind.storage import SQLiteContractStore
from lemmamind.temporal_reconciliation import (
    FactExpectation,
    OrderedEventTransition,
    TemporalFrontierReconciliationService,
    TemporalReconciliationError,
)

NOW = datetime(2026, 8, 25, 16, 15, tzinfo=timezone.utc)


class FakeProcessReader:
    def get_issue(self, owner, repo, number):
        assert (owner, repo, number) == ("ElephantRock", "CSD-Foundry", 37)
        return {
            "id": 3700,
            "node_id": "I_37",
            "number": 37,
            "html_url": "https://github.com/ElephantRock/CSD-Foundry/issues/37",
            "state": "open",
            "state_reason": None,
            "title": "Implement v0.5-D governed registries",
            "body": "Umbrella issue.",
            "user": {"login": "Alajmah"},
            "author_association": "OWNER",
            "locked": False,
            "comments": 10,
            "labels": [],
            "assignees": [],
            "created_at": "2026-08-02T00:00:00Z",
            "updated_at": "2026-08-24T21:36:20Z",
            "closed_at": None,
        }

    def get_pull(self, owner, repo, number):
        assert (owner, repo) == ("ElephantRock", "CSD-Foundry")
        if number == 115:
            return self._pull(
                number=115,
                state="closed",
                draft=False,
                merged=True,
                head_sha="955e1991cad1c74ddf15ea385c375a3d814d9cc3",
                base_sha="02d585c0f8d663b9e154aa7a0e3a88477f1cc44b",
                merge_sha="aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7",
                title="P3.6: D5 atomic multi-registry temporal integration",
                body="Completes D5 and references #37.",
            )
        if number == 117:
            return self._pull(
                number=117,
                state="open",
                draft=True,
                merged=False,
                head_sha="2d910f3ff83f061409ca9d8f2e3709fde7c13f6e",
                base_sha="aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7",
                merge_sha=None,
                title="P3.7: Phase-3 integrated qualification and closure",
                body="Independent validator, five-generation canary, mutation and determinism checks.",
            )
        raise AssertionError(number)

    @staticmethod
    def _pull(*, number, state, draft, merged, head_sha, base_sha, merge_sha, title, body):
        return {
            "id": number * 100,
            "node_id": f"PR_{number}",
            "number": number,
            "html_url": f"https://github.com/ElephantRock/CSD-Foundry/pull/{number}",
            "state": state,
            "draft": draft,
            "merged": merged,
            "merge_commit_sha": merge_sha,
            "title": title,
            "body": body,
            "user": {"login": "Alajmah"},
            "author_association": "OWNER",
            "labels": [],
            "requested_reviewers": [],
            "head": {"ref": f"pr-{number}", "sha": head_sha, "repo": {"full_name": "ElephantRock/CSD-Foundry"}},
            "base": {"ref": "main", "sha": base_sha, "repo": {"full_name": "ElephantRock/CSD-Foundry"}},
            "commits": 3,
            "changed_files": 5,
            "additions": 100,
            "deletions": 10,
            "created_at": "2026-08-15T00:00:00Z",
            "updated_at": "2026-08-24T21:36:20Z",
            "closed_at": "2026-08-15T17:57:27Z" if merged else None,
            "merged_at": "2026-08-15T17:57:27Z" if merged else None,
        }


class FakeEventReader:
    def get_issue_events(self, owner, repo, number):
        assert (owner, repo, number) == ("ElephantRock", "CSD-Foundry", 37)
        return (
            {
                "id": 29940854834,
                "node_id": "CE_37",
                "event": "closed",
                "actor": {"login": "Alajmah"},
                "commit_id": None,
                "commit_url": None,
                "created_at": "2026-08-24T21:31:54Z",
            },
            {
                "id": 29941032785,
                "node_id": "RE_37",
                "event": "reopened",
                "actor": {"login": "Alajmah"},
                "commit_id": None,
                "commit_url": None,
                "created_at": "2026-08-24T21:36:12Z",
            },
        )


def build_context(tmp_path):
    store = SQLiteContractStore(tmp_path / "lemmamind.db")
    objects = ContentAddressedFileStore(tmp_path / "objects")
    source = Source(
        source_id="github:1318635781",
        source_kind=SourceKind.GITHUB_REPOSITORY,
        source_role=SourceRole.IMPLEMENTATION,
        canonical_locator="https://github.com/ElephantRock/CSD-Foundry",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    repository = RepositoryIdentity(
        source_id=source.source_id,
        provider_repository_id="1318635781",
        owner="ElephantRock",
        name="CSD-Foundry",
        default_branch="main",
        aliases=(),
        archived=False,
    )
    revision = SourceRevision(
        source_revision_id="github:1318635781@aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7",
        source_id=source.source_id,
        commit_sha="aa2f1a79c7dfe57a0107a8ffe971e3f6affb96c7",
        tree_sha="843b049ed77b3d4393f944e252651c0c7deb8c31",
        observed_at=NOW,
    )
    store.put_many((source, repository, revision))

    process_capture = GitHubProcessCaptureService(
        FakeProcessReader(), store, objects, clock=lambda: NOW
    ).capture_process(
        revision.source_revision_id,
        (
            ProcessRef(ProcessKind.ISSUE, 37),
            ProcessRef(ProcessKind.PULL_REQUEST, 115),
            ProcessRef(ProcessKind.PULL_REQUEST, 117),
        ),
    )
    process = GitHubProcessEvidenceService(store, objects, clock=lambda: NOW).extract_process(
        process_capture.manifest.capture_id
    )
    event_capture = GitHubProcessEventCaptureService(
        FakeEventReader(), store, objects, clock=lambda: NOW
    ).capture_issue_events(revision.source_revision_id, (37,))
    events = GitHubProcessEventEvidenceService(store, objects, clock=lambda: NOW).extract_issue_events(
        event_capture.manifest.capture_id
    )
    return store, revision, process, events


def fact_by_locator(facts, locator):
    return next(fact for fact in facts if fact.locator == locator)


def reconciliation_inputs(process, events):
    merged = fact_by_locator(process.facts, "$github/pull/115#/merged")
    qualification_open = fact_by_locator(process.facts, "$github/pull/117#/state")
    issue_open = fact_by_locator(process.facts, "$github/issue/37#/state")
    closed_event = fact_by_locator(events.facts, "$github/issue/37/events#/events/0/event")
    closed_at = fact_by_locator(events.facts, "$github/issue/37/events#/events/0/created_at")
    reopened_event = fact_by_locator(events.facts, "$github/issue/37/events#/events/1/event")
    reopened_at = fact_by_locator(events.facts, "$github/issue/37/events#/events/1/created_at")
    supports = tuple(
        SupportRef(SupportType.EVIDENCE_FACT, fact.evidence_id)
        for fact in (merged, qualification_open, issue_open, closed_event, closed_at, reopened_event, reopened_at)
    )
    expectations = (
        FactExpectation(merged.evidence_id, True),
        FactExpectation(qualification_open.evidence_id, "open"),
        FactExpectation(issue_open.evidence_id, "open"),
    )
    transition = OrderedEventTransition(
        from_event_fact_id=closed_event.evidence_id,
        from_event="closed",
        from_timestamp_fact_id=closed_at.evidence_id,
        to_event_fact_id=reopened_event.evidence_id,
        to_event="reopened",
        to_timestamp_fact_id=reopened_at.evidence_id,
    )
    return merged, supports, expectations, transition


def test_reconciliation_supersedes_prior_without_rewriting_history(tmp_path) -> None:
    store, _, process, events = build_context(tmp_path)
    merged, supports, expectations, transition = reconciliation_inputs(process, events)
    observations = ObservationConstructionServiceV2(store, clock=lambda: NOW)
    prior = observations.create_candidate(
        logical_claim_id="csd:issue-37-closure-frontier",
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement="Issue #37 can close because the D1-D5 implementation frontier is complete.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, merged.evidence_id),),
    ).observation

    reconciled = TemporalFrontierReconciliationService(
        store, observation_service=observations
    ).reconcile(
        logical_claim_id=prior.logical_claim_id,
        prior_observation_id=prior.observation_id,
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement=(
            "The earlier conclusion that #37 could close was too strong; implementation is landed "
            "but qualification and evidentiary closure remain open."
        ),
        supports=supports,
        expectations=expectations,
        transition=transition,
    )

    assert reconciled.observation.supersedes_observation_id == prior.observation_id
    assert reconciled.observation.validation_state is ValidationState.CANDIDATE
    assert reconciled.from_timestamp == "2026-08-24T21:31:54Z"
    assert reconciled.to_timestamp == "2026-08-24T21:36:12Z"
    assert store.get(Observation, prior.observation_id) == prior
    assert len(store.list(Observation)) == 2


def test_reconciliation_fails_when_expected_current_state_disagrees(tmp_path) -> None:
    store, _, process, events = build_context(tmp_path)
    merged, supports, expectations, transition = reconciliation_inputs(process, events)
    observations = ObservationConstructionServiceV2(store, clock=lambda: NOW)
    prior = observations.create_candidate(
        logical_claim_id="csd:issue-37-closure-frontier",
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement="Issue #37 can close.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, merged.evidence_id),),
    ).observation
    wrong = tuple(
        FactExpectation(item.evidence_id, "closed") if item.expected_normalized_value == "open" else item
        for item in expectations
    )

    with pytest.raises(TemporalReconciliationError, match="expected"):
        TemporalFrontierReconciliationService(store, observation_service=observations).reconcile(
            logical_claim_id=prior.logical_claim_id,
            prior_observation_id=prior.observation_id,
            epistemic_type=ObservationEpistemicType.EVALUATION,
            statement="Narrower frontier conclusion.",
            supports=supports,
            expectations=wrong,
            transition=transition,
        )


def test_reconciliation_requires_transition_facts_as_explicit_support(tmp_path) -> None:
    store, _, process, events = build_context(tmp_path)
    merged, supports, expectations, transition = reconciliation_inputs(process, events)
    observations = ObservationConstructionServiceV2(store, clock=lambda: NOW)
    prior = observations.create_candidate(
        logical_claim_id="csd:issue-37-closure-frontier",
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement="Issue #37 can close.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, merged.evidence_id),),
    ).observation

    with pytest.raises(TemporalReconciliationError, match="not an explicit Observation support"):
        TemporalFrontierReconciliationService(store, observation_service=observations).reconcile(
            logical_claim_id=prior.logical_claim_id,
            prior_observation_id=prior.observation_id,
            epistemic_type=ObservationEpistemicType.EVALUATION,
            statement="Narrower frontier conclusion.",
            supports=supports[:-1],
            expectations=expectations,
            transition=transition,
        )


def test_reconciliation_refuses_second_branch_from_same_prior(tmp_path) -> None:
    store, _, process, events = build_context(tmp_path)
    merged, supports, expectations, transition = reconciliation_inputs(process, events)
    observations = ObservationConstructionServiceV2(store, clock=lambda: NOW)
    prior = observations.create_candidate(
        logical_claim_id="csd:issue-37-closure-frontier",
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement="Issue #37 can close.",
        supports=(SupportRef(SupportType.EVIDENCE_FACT, merged.evidence_id),),
    ).observation
    service = TemporalFrontierReconciliationService(store, observation_service=observations)
    kwargs = dict(
        logical_claim_id=prior.logical_claim_id,
        prior_observation_id=prior.observation_id,
        epistemic_type=ObservationEpistemicType.EVALUATION,
        statement="Narrower frontier conclusion.",
        supports=supports,
        expectations=expectations,
        transition=transition,
    )
    service.reconcile(**kwargs)

    with pytest.raises(TemporalReconciliationError, match="already has a superseding candidate"):
        service.reconcile(**kwargs)
