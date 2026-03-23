"""GitHub 集成模块.

提供 PR 评论、状态检查、多 PR 并发处理等功能.
使用 PyGithub 进行异步封装.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from consistency.config import get_settings
from consistency.exceptions import (
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)

logger = logging.getLogger(__name__)


@dataclass
class PRComment:
    """PR 评论."""

    body: str
    path: str | None = None
    line: int | None = None
    commit_id: str | None = None


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


class GitHubIntegration:
    """GitHub 集成客户端.

    提供 PR 评论、状态检查、文件评论等功能，
    支持多 PR 并发处理和优雅的限流.

    Examples:
        >>> github = GitHubIntegration(token="ghp_xxx")
        >>> await github.post_comment(
        ...     repo="owner/repo",
        ...     pr_number=42,
        ...     body="Code review results...",
        ... )
    """

    COMMENT_SIGNATURE = "<!-- GitConsistency Code Review -->"
    MAX_COMMENT_LENGTH = 65536

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
        settings = get_settings()

        self.token = token or settings.github_token
        self.delete_old_comments = delete_old_comments
        self.comment_signature = comment_signature or self.COMMENT_SIGNATURE
        self.max_concurrent = max_concurrent
        self.api_base = api_base

        self._client: Any | None = None
        self._semaphore: asyncio.Semaphore | None = None

        self._validate_setup()

    def _validate_setup(self) -> None:
        """验证配置."""
        if not self.token:
            logger.warning("未配置 GitHub Token，集成功能将不可用")
            return

        try:
            from github import Github  # noqa: F401
        except ImportError as e:
            raise GitHubError(
                "PyGithub 未安装，请运行: pip install pygithub",
                details={"original_error": str(e)}
            ) from e

        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    def _get_client(self) -> Any:
        """获取或创建 GitHub 客户端."""
        if self._client is None:
            from github import Github

            kwargs: dict[str, Any] = {}
            if self.api_base:
                kwargs["base_url"] = self.api_base

            self._client = Github(self.token, **kwargs)

        return self._client

    async def get_pr_info(self, repo: str, pr_number: int) -> PRInfo | None:
        """获取 PR 信息.

        Args:
            repo: 仓库名（格式：owner/repo）
            pr_number: PR 编号

        Returns:
            PR 信息或 None
        """
        if not self._semaphore:
            return None

        async with self._semaphore:
            try:
                client = self._get_client()
                repository = client.get_repo(repo)
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

    async def post_comment(
        self,
        repo: str,
        pr_number: int,
        body: str,
        delete_previous: bool | None = None,
    ) -> dict[str, Any]:
        """发布 PR 评论.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            body: 评论内容
            delete_previous: 是否删除之前的评论（默认使用初始化设置）

        Returns:
            评论信息
        """
        if not self._semaphore:
            raise GitHubError("GitHub 未配置", details={"hint": "请检查 GITHUB_TOKEN 是否设置"})

        if delete_previous is None:
            delete_previous = self.delete_old_comments

        async with self._semaphore:
            try:
                # 删除旧评论
                if delete_previous:
                    deleted = await self._delete_previous_comments(repo, pr_number)
                    logger.info(f"删除了 {deleted} 条旧评论")

                # 添加签名
                full_body = f"{body}\n\n{self.comment_signature}"

                # 截断如果太长
                if len(full_body) > self.MAX_COMMENT_LENGTH:
                    full_body = full_body[: self.MAX_COMMENT_LENGTH - 100]
                    full_body += "\n\n... (评论过长已截断)"
                    full_body += f"\n\n{self.comment_signature}"

                # 发布评论
                client = self._get_client()
                repository = client.get_repo(repo)
                pr = repository.get_pull(pr_number)

                comment = pr.create_issue_comment(full_body)

                logger.info(f"已发布评论: {comment.html_url}")

                return {
                    "id": comment.id,
                    "url": comment.html_url,
                    "body_length": len(full_body),
                }

            except Exception as e:
                error_msg = str(e)
                logger.error(f"发布评论失败: {error_msg}")
                # 分类处理常见错误并抛出具体异常
                if "401" in error_msg or "Bad credentials" in error_msg:
                    raise GitHubAuthError(
                        "GitHub 认证失败，请检查 GITHUB_TOKEN",
                        details={"original_error": error_msg}
                    ) from e
                elif "403" in error_msg and "rate limit" in error_msg.lower():
                    raise GitHubRateLimitError(
                        "GitHub API 速率限制，请稍后重试",
                        details={"original_error": error_msg}
                    ) from e
                elif "404" in error_msg:
                    raise GitHubNotFoundError(
                        f"PR 或仓库未找到: {repo}#{pr_number}",
                        details={"original_error": error_msg}
                    ) from e
                raise GitHubError(
                    f"发布评论失败: {error_msg}",
                    details={"repo": repo, "pr_number": pr_number}
                ) from e

    async def post_file_comment(
        self,
        repo: str,
        pr_number: int,
        path: str,
        line: int,
        body: str,
        commit_id: str | None = None,
    ) -> dict[str, Any]:
        """发布文件行级评论.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            path: 文件路径
            line: 行号
            body: 评论内容
            commit_id: 提交 ID（可选）

        Returns:
            评论信息
        """
        if not self._semaphore:
            raise GitHubError("GitHub 未配置", details={"hint": "请检查 GITHUB_TOKEN 是否设置"})

        async with self._semaphore:
            try:
                client = self._get_client()
                repository = client.get_repo(repo)
                pr = repository.get_pull(pr_number)

                # 获取最新 commit 如果没有提供
                if not commit_id:
                    commit_id = pr.head.sha

                # 创建 review comment
                comment = pr.create_review_comment(
                    body=f"{body}\n\n{self.comment_signature}",
                    commit=repository.get_commit(commit_id),
                    path=path,
                    line=line,
                )

                return {
                    "id": comment.id,
                    "url": comment.html_url,
                }

            except Exception as e:
                logger.error(f"发布文件评论失败: {e}")
                raise GitHubError(f"发布文件评论失败: {e}", details={"repo": repo, "path": path, "line": line}) from e

    async def post_comments_batch(
        self,
        repo: str,
        pr_number: int,
        comments: list[PRComment],
        max_concurrent: int = 3,
    ) -> list[dict[str, Any]]:
        """批量发布评论.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            comments: 评论列表
            max_concurrent: 最大并发数

        Returns:
            结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def post_single(comment: PRComment) -> dict[str, Any]:
            async with semaphore:
                if comment.path and comment.line:
                    return await self.post_file_comment(repo, pr_number, comment.path, comment.line, comment.body)
                else:
                    return await self.post_comment(repo, pr_number, comment.body)

        tasks = [post_single(c) for c in comments]
        return await asyncio.gather(*tasks)

    async def _delete_previous_comments(
        self,
        repo: str,
        pr_number: int,
    ) -> int:
        """删除之前的 GitConsistency 评论.

        Args:
            repo: 仓库名
            pr_number: PR 编号

        Returns:
            删除的评论数
        """
        deleted = 0

        try:
            client = self._get_client()
            repository = client.get_repo(repo)
            pr = repository.get_pull(pr_number)

            # 获取所有评论
            comments = pr.get_issue_comments()

            for comment in comments:
                if self.comment_signature in comment.body:
                    comment.delete()
                    deleted += 1
                    logger.debug(f"删除旧评论: {comment.id}")

        except Exception as e:
            logger.warning(f"删除旧评论失败: {e}")

        return deleted

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
            conclusion: 结论（success, failure, neutral, cancelled, skipped, timed_out, action_required）
            output: 输出信息

        Returns:
            Check Run 信息
        """
        if not self._semaphore:
            raise GitHubError("GitHub 未配置", details={"hint": "请检查 GITHUB_TOKEN 是否设置"})

        async with self._semaphore:
            try:
                client = self._get_client()
                repository = client.get_repo(repo)

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
                raise GitHubError(f"创建 Check Run 失败: {e}", details={"repo": repo, "name": name}) from e

    async def update_pr_status(
        self,
        repo: str,
        pr_number: int,
        has_issues: bool,
        summary: str = "",
    ) -> dict[str, Any]:
        """更新 PR 状态.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            has_issues: 是否有问题
            summary: 状态摘要

        Returns:
            状态信息
        """
        # 添加 PR 标签
        try:
            labels_to_add = []
            labels_to_remove = []

            if has_issues:
                labels_to_add.append("gitconsistency:issues-found")
                labels_to_remove.append("gitconsistency:passed")
            else:
                labels_to_add.append("gitconsistency:passed")
                labels_to_remove.append("gitconsistency:issues-found")

            await self._manage_labels(repo, pr_number, labels_to_add, labels_to_remove)

            return {"success": True, "labels_updated": True}

        except Exception as e:
            logger.warning(f"更新 PR 标签失败: {e}")
            raise GitHubError(f"更新 PR 标签失败: {e}", details={"repo": repo, "pr_number": pr_number}) from e

    async def _manage_labels(
        self,
        repo: str,
        pr_number: int,
        add: list[str],
        remove: list[str],
    ) -> None:
        """管理 PR 标签."""
        if not self._semaphore:
            return

        async with self._semaphore:
            try:
                client = self._get_client()
                repository = client.get_repo(repo)
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

    @staticmethod
    def parse_pr_url(url: str) -> tuple[str, int] | None:
        """从 PR URL 解析信息.

        Args:
            url: PR URL

        Returns:
            (repo, pr_number) 或 None
        """
        import re

        patterns = [
            r"github\.com/([^/]+/[^/]+)/pull/(\d+)",
            r"github\.com/([^/]+/[^/]+)/pulls/(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), int(match.group(2))

        return None

    @staticmethod
    def detect_from_env() -> dict[str, Any] | None:
        """从环境变量检测 GitHub 信息.

        Returns:
            检测到的信息或 None
        """
        event_name = os.environ.get("GITHUB_EVENT_NAME")

        if not event_name:
            return None

        info = {
            "event_name": event_name,
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
            "head_ref": os.environ.get("GITHUB_HEAD_REF"),
            "base_ref": os.environ.get("GITHUB_BASE_REF"),
            "actor": os.environ.get("GITHUB_ACTOR"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "action": os.environ.get("GITHUB_ACTION"),
            "event_path": os.environ.get("GITHUB_EVENT_PATH"),
        }

        # 尝试从 event payload 获取 PR 编号
        if event_name == "pull_request" and info["event_path"]:
            try:
                import json

                with open(info["event_path"]) as f:
                    event_data = json.load(f)
                info["pr_number"] = event_data.get("pull_request", {}).get("number")
            except Exception:
                pass

        return info

    @staticmethod
    def is_github_actions() -> bool:
        """检查是否在 GitHub Actions 环境中运行."""
        return os.environ.get("GITHUB_ACTIONS") == "true"

    async def close(self) -> None:
        """关闭连接."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("GitHub 连接已关闭")
