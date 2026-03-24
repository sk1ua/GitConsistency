"""GitHub API 客户端基类.

提供底层的 GitHub API 客户端管理和配置验证.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from consistency.config import get_settings
from consistency.exceptions import GitHubError

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API 客户端.

    管理 GitHub API 连接、并发控制和基础配置.

    Examples:
        >>> client = GitHubClient(token="ghp_xxx")
        >>> gh = client.get_client()
        >>> repo = gh.get_repo("owner/repo")
    """

    def __init__(
        self,
        token: str | None = None,
        max_concurrent: int = 5,
        api_base: str | None = None,
    ) -> None:
        """初始化客户端.

        Args:
            token: GitHub Personal Access Token
            max_concurrent: 最大并发请求数
            api_base: GitHub Enterprise API 地址
        """
        settings = get_settings()

        self.token = token or settings.github_token
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
                details={"original_error": str(e)},
            ) from e

        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    def get_client(self) -> Any:
        """获取或创建 GitHub 客户端."""
        if self._client is None:
            from github import Github

            kwargs: dict[str, Any] = {}
            if self.api_base:
                kwargs["base_url"] = self.api_base

            self._client = Github(self.token, **kwargs)

        return self._client

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """获取并发控制信号量."""
        if self._semaphore is None:
            raise GitHubError("GitHub 未配置", details={"hint": "请检查 GITHUB_TOKEN 是否设置"})
        return self._semaphore

    async def close(self) -> None:
        """关闭连接."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("GitHub 连接已关闭")

    def __enter__(self) -> GitHubClient:
        """上下文管理器入口."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """上下文管理器退出."""
        asyncio.get_event_loop().run_until_complete(self.close())
