"""Minimal GitHub REST client (stdlib). Errors never include the token."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request


class GitHubError(Exception):
    pass


class GitHub:
    def __init__(self, repo: str, token: str, api: str = "https://api.github.com"):
        self.repo, self._token, self.api = repo, token, api.rstrip("/")

    def _call(self, method: str, path: str, body: dict | None = None, query: dict | None = None):
        url = f"{self.api}/repos/{self.repo}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "faceless-homelab-ops"})
        last = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                last = GitHubError(f"{method} {path}: HTTP {e.code}")
                if e.code < 500 and e.code != 429:
                    raise last from None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = GitHubError(f"{method} {path}: {type(e).__name__}")
            time.sleep(2 * (attempt + 1))
        raise last

    def runs(self, workflow: str, since_iso: str | None = None, status: str | None = None) -> list[dict]:
        query = {"per_page": 100}
        if since_iso:
            query["created"] = f">={since_iso}"
        if status:
            query["status"] = status
        out = []
        for page in range(1, 6):
            query["page"] = page
            batch = self._call("GET", f"/actions/workflows/{workflow}/runs", query=query)["workflow_runs"]
            out += batch
            if len(batch) < 100:
                break
        return out

    def jobs(self, run_id: int) -> list[dict]:
        return self._call("GET", f"/actions/runs/{run_id}/jobs", query={"per_page": 100})["jobs"]

    def dispatch(self, workflow: str, inputs: dict, ref: str = "main") -> None:
        self._call("POST", f"/actions/workflows/{workflow}/dispatches", {"ref": ref, "inputs": inputs})

    def rerun_failed(self, run_id: int) -> None:
        self._call("POST", f"/actions/runs/{run_id}/rerun-failed-jobs", {})

    def cancel(self, run_id: int, force: bool = False) -> None:
        self._call("POST", f"/actions/runs/{run_id}/{'force-cancel' if force else 'cancel'}")
