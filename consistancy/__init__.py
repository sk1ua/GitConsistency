"""ConsistenCy 2.0 - 代码安全扫描与 AI 审查工具.

一个为 vibe coding / 高频 commit 项目提供的代码安全扫描、
AI 审查和 GitHub PR 自动评论工具。

Examples:
    >>> from consistancy import get_settings
    >>> settings = get_settings()
    >>> print(settings.project_name)
    'ConsistenCy'

Attributes:
    __version__: 当前版本号
    __author__: 作者信息
"""

__version__ = "2.0.0"
__author__ = "ConsistenCy Team"
__email__ = "team@consistancy.dev"
__license__ = "MIT"

from consistancy.config import Settings, get_settings

__all__ = [
    "__version__",
    "__author__",
    "Settings",
    "get_settings",
]
