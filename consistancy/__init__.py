"""ConsistenCy 2.0 - 现代代码健康智能守护者.

一个为 vibe coding / 高频 commit 项目提供的自动代码一致性漂移检测、
安全扫描、技术债务分析 + AI 审查 + Streamlit Dashboard + GitHub PR 自动评论工具。

Examples:
    >>> from consistancy import ConsistencyAnalyzer
    >>> analyzer = ConsistencyAnalyzer()
    >>> results = analyzer.analyze("./my-project")

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
