"""一致性检查 CLI 命令.

提供交互式代码审查功能.

Examples:
    >>> from consistency.commands import ReviewCommand, AnalyzeCommand
    >>> cmd = ReviewCommand()
"""

from __future__ import annotations

from consistency.commands.analyze import AnalyzeCommand
from consistency.commands.ci import CICommand
from consistency.commands.config_cmd import ConfigCommand
from consistency.commands.init import InitCommand
from consistency.commands.review import ReviewCommand, review_diff, review_file
from consistency.commands.scan import ScanCommand

__all__ = [
    # 主要命令类
    "AnalyzeCommand",
    "CICommand",
    "ConfigCommand",
    "InitCommand",
    "ReviewCommand",
    "ScanCommand",
    # 便捷函数
    "review_diff",
    "review_file",
]
