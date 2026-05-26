from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    html_url: str


class GitHubClient:
    def __init__(self, token: str):
        self._token = token
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=API_BASE,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_repo(self, owner: str, repo: str) -> dict:
        resp = await self._get_client().get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        return resp.json()

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str | None = None,
        per_page: int = 30,
    ) -> list[GitHubIssue]:
        params: dict = {"state": state, "per_page": per_page}
        if labels:
            params["labels"] = labels
        resp = await self._get_client().get(f"/repos/{owner}/{repo}/issues", params=params)
        resp.raise_for_status()
        return [
            GitHubIssue(
                number=i["number"],
                title=i["title"],
                body=i.get("body") or "",
                state=i["state"],
                labels=[lb["name"] for lb in i.get("labels", [])],
                html_url=i["html_url"],
            )
            for i in resp.json()
            if "pull_request" not in i
        ]

    async def create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict:
        resp = await self._get_client().post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        return resp.json()

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict:
        resp = await self._get_client().post(
            f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
        )
        resp.raise_for_status()
        return resp.json()
