"""PR 标签管理.

提供 PR 标签的添加、移除和状态管理功能.
"""

from __future__ import annotations

import logging
from typing import Any

from consistency.exceptions import GitHubError
from consistency.github.client import GitHubClient

logger = logging.getLogger(__name__)


class LabelManager:
    """PR 标签管理器.

    管理 PR 标签的添加、移除和状态同步.

    Examples:
        >>> client = GitHubClient(token="ghp_xxx")
        >>> labels = LabelManager(client)
        >>> await labels.update_pr_status("owner/repo", 42, has_issues=True)
    """

    LABEL_ISSUES_FOUND = "gitconsistency:issues-found"
    LABEL_PASSED = "gitconsistency:passed"

    def __init__(self, client: GitHubClient) -> None:
        """初始化标签管理器.

        Args:
            client: GitHub 客户端
        """
        self.client = client

    async def update_pr_status(
        self,
        repo: str,
        pr_number: int,
        has_issues: bool,
        summary: str = "",
    ) -> dict[str, Any]:
        """更新 PR 状态标签.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            has_issues: 是否有问题
            summary: 状态摘要（保留参数，暂未使用）

        Returns:
            状态信息
        """
        labels_to_add = []
        labels_to_remove = []

        if has_issues:
            labels_to_add.append(self.LABEL_ISSUES_FOUND)
            labels_to_remove.append(self.LABEL_PASSED)
        else:
            labels_to_add.append(self.LABEL_PASSED)
            labels_to_remove.append(self.LABEL_ISSUES_FOUND)

        await self._manage_labels(repo, pr_number, labels_to_add, labels_to_remove)

        return {"success": True, "labels_updated": True}

    async def _manage_labels(
        self,
        repo: str,
        pr_number: int,
        add: list[str],
        remove: list[str],
    ) -> None:
        """管理 PR 标签.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            add: 要添加的标签列表
            remove: 要移除的标签列表
        """
        async with self.client.semaphore:
            try:
                gh = self.client.get_client()
                repository = gh.get_repo(repo)
                pr = repository.get_pull(pr_number)

                current_labels = {label.name for label in pr.labels}

                # 添加标签
                for label in add:
                    if label not in current_labels:
                        pr.add_to_labels(label)

                # 移除标签
                for label in remove:
                    if label in current_labels:
                        pr.remove_from_labels(label)

            except Exception as e:
                logger.warning(f"标签管理失败: {e}")
                raise GitHubError(
                    f"标签管理失败: {e}",
                    details={"repo": repo, "pr_number": pr_number},
                ) from e

    async def add_labels(self, repo: str, pr_number: int, labels: list[str]) -> None:
        """添加标签.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            labels: 标签列表
        """
        await self._manage_labels(repo, pr_number, labels, [])

    async def remove_labels(self, repo: str, pr_number: int, labels: list[str]) -> None:
        """移除标签.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            labels: 标签列表
        """
        await self._manage_labels(repo, pr_number, [], labels)
