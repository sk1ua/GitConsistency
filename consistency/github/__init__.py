"""GitHub 集成模块.

提供统一的 GitHub API 集成接口，包括 PR 评论、状态检查和标签管理.

Examples:
    >>> from consistency.github import GitHubIntegration
    >>> github = GitHubIntegration(token="ghp_xxx")
    >>> await github.post_comment("owner/repo", 42, "Code review results...")
"""

from __future__ import annotations

from typing import Any

from consistency.github.checks import CheckManager, PRInfo
from consistency.github.ci_utils import (
    debug_print_context,
    get_workflow_context,
    is_github_actions,
    set_actions_output,
    set_actions_outputs_from_results,
    write_actions_summary,
    write_annotations_from_findings,
    write_workflow_annotation,
)
from consistency.github.client import GitHubClient
from consistency.github.comments import CommentManager, PRComment
from consistency.github.labels import LabelManager
from consistency.github.utils import detect_from_env, parse_pr_url
from consistency.github.utils import is_github_actions as _is_github_actions


class GitHubIntegration:
    """GitHub 集成客户端（兼容性包装器）.

    提供与原有 github_integration.GitHubIntegration 相同的 API，
    内部使用拆分后的模块化组件.

    Examples:
        >>> github = GitHubIntegration(token="ghp_xxx")
        >>> await github.post_comment(
        ...     repo="owner/repo",
        ...     pr_number=42,
        ...     body="Code review results...",
        ... )
    """

    COMMENT_SIGNATURE = CommentManager.COMMENT_SIGNATURE
    MAX_COMMENT_LENGTH = CommentManager.MAX_COMMENT_LENGTH

    def __init__(
        self,
        token: str | None = None,
        delete_old_comments: bool = True,
        comment_signature: str | None = None,
        max_concurrent: int = 5,
        api_base: str | None = None,
    ) -> None:
        """初始化 GitHub 集成.

        Args:
            token: GitHub Personal Access Token
            delete_old_comments: 是否删除旧评论
            comment_signature: 评论签名
            max_concurrent: 最大并发请求数
            api_base: GitHub Enterprise API 地址
        """
        self.client = GitHubClient(
            token=token,
            max_concurrent=max_concurrent,
            api_base=api_base,
        )
        self.comments = CommentManager(
            client=self.client,
            delete_old_comments=delete_old_comments,
            comment_signature=comment_signature,
        )
        self.checks = CheckManager(client=self.client)
        self.labels = LabelManager(client=self.client)

    async def get_pr_info(self, repo: str, pr_number: int) -> PRInfo | None:
        """获取 PR 信息."""
        return await self.checks.get_pr_info(repo, pr_number)

    async def post_comment(
        self,
        repo: str,
        pr_number: int,
        body: str,
        delete_previous: bool | None = None,
    ) -> dict[str, Any]:
        """发布 PR 评论."""
        return await self.comments.post_comment(repo, pr_number, body, delete_previous)

    async def post_file_comment(
        self,
        repo: str,
        pr_number: int,
        path: str,
        line: int,
        body: str,
        commit_id: str | None = None,
    ) -> dict[str, Any]:
        """发布文件行级评论."""
        return await self.comments.post_file_comment(repo, pr_number, path, line, body, commit_id)

    async def post_comments_batch(
        self,
        repo: str,
        pr_number: int,
        comments: list[PRComment],
        max_concurrent: int = 3,
    ) -> list[dict[str, Any]]:
        """批量发布评论."""
        return await self.comments.post_comments_batch(repo, pr_number, comments, max_concurrent)

    async def create_check_run(
        self,
        repo: str,
        name: str,
        head_sha: str,
        status: str = "completed",
        conclusion: str | None = None,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建 Check Run."""
        return await self.checks.create_check_run(repo, name, head_sha, status, conclusion, output)

    async def update_pr_status(
        self,
        repo: str,
        pr_number: int,
        has_issues: bool,
        summary: str = "",
    ) -> dict[str, Any]:
        """更新 PR 状态."""
        return await self.labels.update_pr_status(repo, pr_number, has_issues, summary)

    async def close(self) -> None:
        """关闭连接."""
        await self.client.close()

    @staticmethod
    def parse_pr_url(url: str) -> tuple[str, int] | None:
        """从 PR URL 解析信息."""
        return parse_pr_url(url)

    @staticmethod
    def detect_from_env() -> dict[str, Any] | None:
        """从环境变量检测 GitHub 信息."""
        return detect_from_env()

    @staticmethod
    def is_github_actions() -> bool:
        """检查是否在 GitHub Actions 环境中运行."""
        return _is_github_actions()


# 导出子模块组件（供高级用户使用）
__all__ = [
    # Core components
    "CheckManager",
    "CommentManager",
    "GitHubClient",
    "GitHubIntegration",
    "LabelManager",
    "PRComment",
    "PRInfo",
    # CI utilities
    "debug_print_context",
    "get_workflow_context",
    "is_github_actions",
    "set_actions_output",
    "set_actions_outputs_from_results",
    "write_actions_summary",
    "write_annotations_from_findings",
    "write_workflow_annotation",
    # Utils
    "detect_from_env",
    "parse_pr_url",
]
