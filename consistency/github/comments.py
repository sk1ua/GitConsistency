"""PR 评论管理.

提供 PR 评论的发布、删除和批量操作功能.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from consistency.exceptions import (
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from consistency.github.client import GitHubClient

logger = logging.getLogger(__name__)


@dataclass
class PRComment:
    """PR 评论."""

    body: str
    path: str | None = None
    line: int | None = None
    commit_id: str | None = None


class CommentManager:
    """PR 评论管理器.

    管理 PR 评论的创建、更新和删除，支持签名和自动清理旧评论.

    Examples:
        >>> client = GitHubClient(token="ghp_xxx")
        >>> comments = CommentManager(client, comment_signature="<!-- Bot -->")
        >>> await comments.post_comment("owner/repo", 42, "Review results...")
    """

    COMMENT_SIGNATURE = "<!-- GitConsistency Code Review -->"
    MAX_COMMENT_LENGTH = 65536

    def __init__(
        self,
        client: GitHubClient,
        delete_old_comments: bool = True,
        comment_signature: str | None = None,
    ) -> None:
        """初始化评论管理器.

        Args:
            client: GitHub 客户端
            delete_old_comments: 是否删除旧评论
            comment_signature: 评论签名
        """
        self.client = client
        self.delete_old_comments = delete_old_comments
        self.comment_signature = comment_signature or self.COMMENT_SIGNATURE

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
            delete_previous: 是否删除之前的评论

        Returns:
            评论信息
        """
        if delete_previous is None:
            delete_previous = self.delete_old_comments

        async with self.client.semaphore:
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
                gh = self.client.get_client()
                repository = gh.get_repo(repo)
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
                self._handle_error(error_msg, repo, pr_number, e)

    def _handle_error(self, error_msg: str, repo: str, pr_number: int, original: Exception) -> None:
        """分类处理错误."""
        if "401" in error_msg or "Bad credentials" in error_msg:
            raise GitHubAuthError(
                "GitHub 认证失败，请检查 GITHUB_TOKEN",
                details={"original_error": error_msg},
            ) from original
        elif "403" in error_msg and "rate limit" in error_msg.lower():
            raise GitHubRateLimitError(
                "GitHub API 速率限制，请稍后重试",
                details={"original_error": error_msg},
            ) from original
        elif "404" in error_msg:
            raise GitHubNotFoundError(
                f"PR 或仓库未找到: {repo}#{pr_number}",
                details={"original_error": error_msg},
            ) from original
        raise GitHubError(
            f"发布评论失败: {error_msg}",
            details={"repo": repo, "pr_number": pr_number},
        ) from original

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
        async with self.client.semaphore:
            try:
                gh = self.client.get_client()
                repository = gh.get_repo(repo)
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
                raise GitHubError(
                    f"发布文件评论失败: {e}",
                    details={"repo": repo, "path": path, "line": line},
                ) from e

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

    async def _delete_previous_comments(self, repo: str, pr_number: int) -> int:
        """删除之前的 GitConsistency 评论.

        Args:
            repo: 仓库名
            pr_number: PR 编号

        Returns:
            删除的评论数
        """
        deleted = 0

        try:
            gh = self.client.get_client()
            repository = gh.get_repo(repo)
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
