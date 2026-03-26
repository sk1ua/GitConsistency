"""GitConsistency - 代码安全扫描与 AI 审查工具.

一个为 vibe coding / 高频 commit 项目提供的代码安全扫描、
AI 审查和 GitHub PR 自动评论工具。

Examples:
    >>> from consistency import get_settings
    >>> settings = get_settings()
    >>> print(settings.project_name)
    'GitConsistency'

Attributes:
    __version__: 当前版本号
    __author__: 作者信息
"""

__version__ = "0.2.0"
__author__ = "Sk1ua"
__email__ = "sakuaikacn@gmail.com"
__license__ = "MIT"

from consistency.config import Settings, get_settings

__all__ = [
    "Settings",
    "__author__",
    "__version__",
    "get_settings",
]
