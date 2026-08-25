"""Safe HTTP transport for GitHub workflow log-availability probes.

The GitHub job-log endpoint returns a redirect to a signed blob URL when logs
exist. LemmaMind v1 needs only the availability signal, not log contents. This
reader therefore refuses redirects and interprets GitHub's redirect response as
``available``. Authorization headers are never forwarded to the blob host.
"""
from __future__ import annotations

from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .github import GitHubAPIError
from .github_workflow import GitHubWorkflowRESTReader


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> None:
        return None


class SafeGitHubWorkflowRESTReader(GitHubWorkflowRESTReader):
    """Workflow reader whose log probe never follows GitHub's signed redirect."""

    def probe_job_log(self, owner: str, repo: str, job_id: int) -> Mapping[str, Any]:
        path = (
            f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
            f"/actions/jobs/{job_id}/logs"
        )
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        opener = build_opener(_NoRedirect())
        try:
            response = opener.open(request, timeout=self.timeout)
            try:
                status = int(getattr(response, "status", 200))
            finally:
                response.close()
            return {
                "availability": "available",
                "http_status": status,
                "redirected": False,
            }
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                return {
                    "availability": "available",
                    "http_status": exc.code,
                    "redirected": True,
                }
            if exc.code == 404:
                return {
                    "availability": "missing",
                    "http_status": 404,
                    "redirected": False,
                }
            raise GitHubAPIError(
                f"GitHub job-log probe failed with HTTP {exc.code}",
                status_code=exc.code,
            ) from exc
