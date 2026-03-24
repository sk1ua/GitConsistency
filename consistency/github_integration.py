"""GitHub 集成模块（已迁移）.

此模块已拆分为 `consistency.github` 包。保留此文件用于向后兼容。

请使用新的导入路径:
    >>> from consistency.github import GitHubIntegration

替代旧路径:
    >>> from consistency.github_integration import GitHubIntegration  # 仍可用
"""

from __future__ import annotations

import warnings

# 重新导出所有组件以保持向后兼容
from consistency.github import (  # noqa: F401
    CommentManager,
    GitHubClient,
    GitHubIntegration,
    PRComment,
    PRInfo,
    detect_from_env,
    is_github_actions,
    parse_pr_url,
)

warnings.warn(
    "consistency.github_integration 已弃用，请使用 consistency.github",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "GitHubIntegration",
    "GitHubClient",
    "CommentManager",
    "PRComment",
    "PRInfo",
    "detect_from_env",
    "is_github_actions",
    "parse_pr_url",
]
