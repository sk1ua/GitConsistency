"""GitHub Check Run 管理.

提供 GitHub Check Run 和 PR 状态检查功能.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from consistency.github.client import GitHubClient

logger = logging.getLogger(__name__)


@dataclass
class PRInfo:
    """PR 信息."""

    number: int
    title: str
    body: str
    head_sha: str
    base_sha: str
    state: str
    is_draft: bool


class CheckManager:
    """Check Run 管理器.

    管理 GitHub Check Run 创建和 PR 信息获取.

    Examples:
        >>> client = GitHubClient(token="ghp_xxx")
        >>> checks = CheckManager(client)
        >>> await checks.create_check_run("owner/repo", "Security Scan", "abc123")
    """

    def __init__(self, client: GitHubClient) -> None:
        """初始化 Check 管理器.

        Args:
            client: GitHub 客户端
        """
        self.client = client

    async def get_pr_info(self, repo: str, pr_number: int) -> PRInfo | None:
        """获取 PR 信息.

        Args:
            repo: 仓库名（格式：owner/repo）
            pr_number: PR 编号

        Returns:
            PR 信息或 None
        """
        async with self.client.semaphore:
            try:
                gh = self.client.get_client()
                repository = gh.get_repo(repo)
                pr = repository.get_pull(pr_number)

                return PRInfo(
                    number=pr.number,
                    title=pr.title,
                    body=pr.body or "",
                    head_sha=pr.head.sha,
                    base_sha=pr.base.sha,
                    state=pr.state,
                    is_draft=pr.draft,
                )
            except Exception as e:
                logger.error(f"获取 PR 信息失败: {e}")
                return None

    async def create_check_run(
        self,
        repo: str,
        name: str,
        head_sha: str,
        status: str = "completed",
        conclusion: str | None = None,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建 Check Run（需要 GitHub App）.

        Args:
            repo: 仓库名
            name: Check 名称
            head_sha: HEAD commit SHA
            status: 状态（queued, in_progress, completed）
            conclusion: 结论（success, failure, neutral, cancelled, skipped,
                timed_out, action_required）
            output: 输出信息

        Returns:
            Check Run 信息
        """
        from consistency.exceptions import GitHubError

        async with self.client.semaphore:
            try:
                gh = self.client.get_client()
                repository = gh.get_repo(repo)

                check_run = repository.create_check_run(
                    name=name,
                    head_sha=head_sha,
                    status=status,
                    conclusion=conclusion,
                    output=output,
                )

                return {
                    "id": check_run.id,
                    "url": check_run.url,
                }

            except Exception as e:
                logger.error(f"创建 Check Run 失败: {e}")
                raise GitHubError(
                    f"创建 Check Run 失败: {e}",
                    details={"repo": repo, "name": name},
                ) from e
