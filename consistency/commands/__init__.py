"""一致性检查 CLI 命令.

提供交互式代码审查功能.

Examples:
    >>> from consistency.commands import ReviewCommand
    >>> cmd = ReviewCommand()
"""

from __future__ import annotations

from consistency.commands.review import ReviewCommand, review_diff, review_file

__all__ = [
    "ReviewCommand",
    "review_diff",
    "review_file",
]
