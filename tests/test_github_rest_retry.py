import io
import json
from email.message import Message
from urllib.error import HTTPError

import pytest

import lemmamind.github as github_module
from lemmamind.github import GitHubAPIError, GitHubNotFound, GitHubRESTReader


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def make_http_error(
    code: int,
    message: str,
    *,
    headers: dict[str, str] | None = None,
) -> HTTPError:
    response_headers = Message()
    for key, value in (headers or {}).items():
        response_headers[key] = value
    body = io.BytesIO(json.dumps({"message": message}).encode("utf-8"))
    return HTTPError(
        "https://api.github.com/example",
        code,
        message,
        response_headers,
        body,
    )


def install_outcomes(monkeypatch, outcomes: list[object]) -> list[str]:
    calls: list[str] = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(github_module, "urlopen", fake_urlopen)
    return calls


def test_rate_limit_without_headers_waits_at_least_one_minute(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(429, "secondary rate limit"),
        FakeResponse({"ok": True}),
    ]
    calls = install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append, wall_clock=lambda: 1000.0)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [60.0]
    assert len(calls) == 2


def test_rate_limit_honors_retry_after_header(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(429, "secondary rate limit", headers={"Retry-After": "17"}),
        FakeResponse({"ok": True}),
    ]
    install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [17.0]


def test_rate_limit_honors_retry_after_http_date(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(
            429,
            "secondary rate limit",
            headers={"Retry-After": "Thu, 01 Jan 1970 00:18:20 GMT"},
        ),
        FakeResponse({"ok": True}),
    ]
    install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append, wall_clock=lambda: 1000.0)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [100.0]


def test_negative_retry_after_falls_through_to_primary_reset(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(
            429,
            "API rate limit exceeded",
            headers={
                "Retry-After": "-5",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1100",
            },
        ),
        FakeResponse({"ok": True}),
    ]
    install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append, wall_clock=lambda: 1000.0)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [101.0]


@pytest.mark.parametrize("retry_after", ["nan", "inf", "-inf"])
def test_non_finite_retry_after_falls_through_to_one_minute_backoff(
    monkeypatch,
    retry_after: str,
) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(
            429,
            "secondary rate limit",
            headers={"Retry-After": retry_after},
        ),
        FakeResponse({"ok": True}),
    ]
    install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append, wall_clock=lambda: 1000.0)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [60.0]


def test_primary_rate_limit_waits_until_reset(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(
            429,
            "API rate limit exceeded",
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1100",
            },
        ),
        FakeResponse({"ok": True}),
    ]
    install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append, wall_clock=lambda: 1000.0)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [101.0]


def test_repeated_rate_limit_exhausts_bounded_retry_budget(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(429, "secondary rate limit"),
        make_http_error(429, "secondary rate limit"),
        make_http_error(429, "secondary rate limit"),
    ]
    calls = install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(
        max_retries=2,
        sleep=sleeps.append,
        wall_clock=lambda: 1000.0,
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        reader._get_json("/example")

    assert exc_info.value.status_code == 429
    assert sleeps == [60.0, 120.0]
    assert len(calls) == 3


def test_not_found_is_never_retried(monkeypatch) -> None:
    sleeps: list[float] = []
    calls = install_outcomes(monkeypatch, [make_http_error(404, "Not Found")])
    reader = GitHubRESTReader(sleep=sleeps.append)

    with pytest.raises(GitHubNotFound) as exc_info:
        reader._get_json("/example")

    assert exc_info.value.status_code == 404
    assert sleeps == []
    assert len(calls) == 1


def test_ordinary_forbidden_response_is_never_retried(monkeypatch) -> None:
    sleeps: list[float] = []
    calls = install_outcomes(
        monkeypatch,
        [make_http_error(403, "Access denied by policy settings")],
    )
    reader = GitHubRESTReader(sleep=sleeps.append)

    with pytest.raises(GitHubAPIError) as exc_info:
        reader._get_json("/example")

    assert exc_info.value.status_code == 403
    assert sleeps == []
    assert len(calls) == 1


def test_rate_limited_forbidden_response_is_retried(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(403, "secondary rate limit exceeded"),
        FakeResponse({"ok": True}),
    ]
    install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [60.0]


def test_transient_server_failure_uses_short_bounded_backoff(monkeypatch) -> None:
    sleeps: list[float] = []
    outcomes = [
        make_http_error(503, "Service Unavailable"),
        FakeResponse({"ok": True}),
    ]
    install_outcomes(monkeypatch, outcomes)
    reader = GitHubRESTReader(sleep=sleeps.append)

    assert reader._get_json("/example") == {"ok": True}
    assert sleeps == [1.0]


def test_negative_retry_budget_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        GitHubRESTReader(max_retries=-1)
