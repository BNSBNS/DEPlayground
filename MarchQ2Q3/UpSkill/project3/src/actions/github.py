import base64

import httpx
import structlog

from src.config import get_settings
from src.models.fixes import FixProposal

log = structlog.get_logger(__name__)


class GitHubClient:
    """GitHub API client for creating branches, committing files, and opening PRs."""

    def __init__(self) -> None:
        settings = get_settings()
        self.owner = settings.github_owner
        self.repo = settings.github_repo
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_default_branch_sha(self) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/git/ref/heads/main",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()["object"]["sha"]

    async def create_branch(self, branch_name: str, sha: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/git/refs",
                headers=self.headers,
                json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            )
            resp.raise_for_status()
            await log.ainfo("branch_created", branch=branch_name)

    async def commit_file(
        self,
        branch: str,
        path: str,
        content: str,
        message: str,
    ) -> None:
        encoded = base64.b64encode(content.encode()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{path}",
                headers=self.headers,
                json={
                    "message": message,
                    "content": encoded,
                    "branch": branch,
                },
            )
            resp.raise_for_status()

    async def open_pr(self, branch: str, title: str, body: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls",
                headers=self.headers,
                json={
                    "title": title,
                    "body": body,
                    "head": branch,
                    "base": "main",
                },
            )
            resp.raise_for_status()
            pr_url = resp.json()["html_url"]
            await log.ainfo("pr_created", url=pr_url)
            return pr_url


async def create_pull_request(proposal: FixProposal) -> str:
    """Create a PR with all fix files. In simulation mode, logs instead."""
    settings = get_settings()

    if settings.simulation_mode:
        await log.ainfo(
            "pr_simulated",
            title=proposal.pr_title,
            fix_count=len(proposal.fixes),
        )
        return "https://github.com/simulated/repo/pull/1"

    client = GitHubClient()
    sha = await client.get_default_branch_sha()
    branch = f"auto-fix/{proposal.proposal_id}"

    await client.create_branch(branch, sha)

    for fix in proposal.fixes:
        await client.commit_file(
            branch=branch,
            path=fix.file_path,
            content=fix.content,
            message=f"fix: {fix.description}",
        )

    return await client.open_pr(branch, proposal.pr_title, proposal.pr_body)
