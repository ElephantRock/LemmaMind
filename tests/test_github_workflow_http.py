from urllib.error import HTTPError

import pytest

import lemmamind.github_workflow_http as workflow_http
from lemmamind.github import GitHubAPIError
from lemmamind.github_workflow_http import SafeGitHubWorkflowRESTReader


class FailingOpener:
    def __init__(self, status: int) -> None:
        self.status = status

    def open(self, request, timeout=None):
        raise HTTPError(
            request.full_url,
            self.status,
            "synthetic",
            hdrs={},
            fp=None,
        )


def test_log_probe_treats_redirect_as_available_without_following(monkeypatch) -> None:
    monkeypatch.setattr(workflow_http, "build_opener", lambda *_: FailingOpener(302))
    reader = SafeGitHubWorkflowRESTReader(token="secret")

    result = reader.probe_job_log("ElephantRock", "Repo", 123)

    assert result == {
        "availability": "available",
        "http_status": 302,
        "redirected": True,
    }


def test_log_probe_treats_404_as_missing(monkeypatch) -> None:
    monkeypatch.setattr(workflow_http, "build_opener", lambda *_: FailingOpener(404))
    reader = SafeGitHubWorkflowRESTReader(token="secret")

    result = reader.probe_job_log("ElephantRock", "Repo", 123)

    assert result == {
        "availability": "missing",
        "http_status": 404,
        "redirected": False,
    }


def test_log_probe_does_not_hide_authentication_failure(monkeypatch) -> None:
    monkeypatch.setattr(workflow_http, "build_opener", lambda *_: FailingOpener(401))
    reader = SafeGitHubWorkflowRESTReader(token="secret")

    with pytest.raises(GitHubAPIError, match="HTTP 401"):
        reader.probe_job_log("ElephantRock", "Repo", 123)
