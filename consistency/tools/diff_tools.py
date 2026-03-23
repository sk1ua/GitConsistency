"""Diff 分析工具."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from consistency.agents.base import Severity

logger = logging.getLogger(__name__)


@dataclass
class DiffHunk:
    """Diff 片段."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)
    added_lines: list[tuple[int, str]] = field(default_factory=list)  # (行号, 内容)
    removed_lines: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class FileDiff:
    """文件 Diff."""

    old_path: str | None
    new_path: str
    is_new: bool = False
    is_deleted: bool = False
    hunks: list[DiffHunk] = field(default_factory=list)


class DiffParser:
    """Diff 解析器.

    解析 git diff 输出，提取变更信息.

    Examples:
        >>> parser = DiffParser()
        >>> diffs = parser.parse(git_diff_output)
        >>> for diff in diffs:
        ...     print(diff.new_path, len(diff.hunks))
    """

    def parse(self, diff_text: str) -> list[FileDiff]:
        """解析 diff 文本.

        Args:
            diff_text: git diff 输出

        Returns:
            文件变更列表
        """
        if not diff_text or not diff_text.strip():
            return []

        files = []
        lines = diff_text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # 解析文件头
            if line.startswith("diff --git"):
                # 提取文件路径
                match = re.match(r"diff --git a/(.+?) b/(.+)", line)
                if match:
                    old_path = match.group(1)
                    new_path = match.group(2)
                    is_new = False
                    is_deleted = False

                    # 查看后续行确定文件状态
                    j = i + 1
                    while j < len(lines) and not lines[j].startswith("diff --git"):
                        if lines[j].startswith("new file mode"):
                            is_new = True
                        elif lines[j].startswith("deleted file mode"):
                            is_deleted = True
                        elif lines[j].startswith("@@"):
                            break
                        j += 1

                    file_diff = FileDiff(
                        old_path=old_path if old_path != new_path else None,
                        new_path=new_path,
                        is_new=is_new,
                        is_deleted=is_deleted,
                    )

                    # 解析 hunks
                    i, hunks = self._parse_hunks(lines, i + 1)
                    file_diff.hunks = hunks

                    files.append(file_diff)
                    continue

            i += 1

        return files

    def _parse_hunks(
        self,
        lines: list[str],
        start: int,
    ) -> tuple[int, list[DiffHunk]]:
        """解析 hunk 块.

        Args:
            lines: 所有行
            start: 起始索引

        Returns:
            (结束索引, hunks 列表)
        """
        hunks = []
        i = start

        while i < len(lines):
            line = lines[i]

            # 新的文件开始
            if line.startswith("diff --git"):
                break

            # 解析 hunk 头
            if line.startswith("@@"):
                # @@ -old_start,old_count +new_start,new_count @@
                match = re.match(
                    r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
                    line,
                )
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1
                    new_start = int(match.group(3))
                    new_count = int(match.group(4)) if match.group(4) else 1

                    hunk = DiffHunk(
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                    )

                    # 解析 hunk 内容
                    i += 1
                    new_line_num = new_start

                    while i < len(lines):
                        content = lines[i]

                        # 新的 hunk 或文件
                        if content.startswith("@@") or content.startswith("diff --git"):
                            break

                        # 空行或其他
                        if not content:
                            i += 1
                            continue

                        hunk.lines.append(content)

                        if content.startswith("+") and not content.startswith("+++"):
                            hunk.added_lines.append((new_line_num, content[1:]))
                            new_line_num += 1
                        elif content.startswith("-") and not content.startswith("---"):
                            hunk.removed_lines.append((new_line_num, content[1:]))
                        elif not content.startswith("\\"):
                            # 上下文行
                            new_line_num += 1

                        i += 1

                    hunks.append(hunk)
                    continue

            i += 1

        return i, hunks


class IncrementalReviewer:
    """增量审查器.

    只审查变更的代码，但基于完整知识图谱理解上下文.

    Examples:
        >>> reviewer = IncrementalReviewer()
        >>> result = await reviewer.review_diff(diff_text, repo_path)
    """

    def __init__(self) -> None:
        """初始化."""
        self.diff_parser = DiffParser()

    async def review_diff(
        self,
        diff_text: str,
        repo_path: Path | str,
        supervisor: Any | None = None,
    ) -> dict[str, Any]:
        """审查 diff.

        Args:
            diff_text: git diff 输出
            repo_path: 代码库路径
            supervisor: ReviewSupervisor 实例（可选）

        Returns:
            审查结果
        """
        from consistency.agents import ReviewSupervisor

        if supervisor is None:
            supervisor = ReviewSupervisor(quick_mode=True)

        # 1. 解析 diff
        file_diffs = self.diff_parser.parse(diff_text)
        if not file_diffs:
            return {
                "summary": "没有检测到变更",
                "files_count": 0,
                "issues_count": 0,
                "results": [],
            }

        logger.info(f"增量审查: {len(file_diffs)} 个文件")

        # 2. 准备审查任务
        review_tasks = []
        for file_diff in file_diffs:
            if file_diff.is_deleted:
                continue

            # 提取变更的代码
            changed_code = self._extract_changed_code(file_diff)
            if not changed_code:
                continue

            file_path = Path(repo_path) / file_diff.new_path
            review_tasks.append((file_path, changed_code, file_diff))

        # 3. 并行审查
        results = await supervisor.review_batch(
            [(fp, code) for fp, code, _ in review_tasks],
            max_concurrency=3,
        )

        # 4. 汇总结果
        total_issues = sum(len(r.comments) for r in results)

        return {
            "summary": f"审查了 {len(review_tasks)} 个文件，发现 {total_issues} 个问题",
            "files_count": len(review_tasks),
            "issues_count": total_issues,
            "results": [
                {
                    "file": str(fp),
                    "changes": self._summarize_changes(fd),
                    "review": r,
                }
                for (fp, _, fd), r in zip(review_tasks, results)
            ],
        }

    def _extract_changed_code(self, file_diff: FileDiff) -> str:
        """提取变更的代码.

        Args:
            file_diff: 文件 diff

        Returns:
            变更的代码文本
        """
        lines = []

        for hunk in file_diff.hunks:
            # 添加上下文（变更前后各 2 行）
            for _, content in hunk.added_lines:
                lines.append(content)

        return "\n".join(lines)

    def _summarize_changes(self, file_diff: FileDiff) -> dict[str, Any]:
        """汇总变更信息."""
        added = sum(len(h.added_lines) for h in file_diff.hunks)
        removed = sum(len(h.removed_lines) for h in file_diff.hunks)

        return {
            "path": file_diff.new_path,
            "is_new": file_diff.is_new,
            "is_deleted": file_diff.is_deleted,
            "hunks_count": len(file_diff.hunks),
            "added_lines": added,
            "removed_lines": removed,
        }


class QuickReviewTool:
    """快速审查工具.

    Vibe coding 场景：极速反馈，只关注关键问题.

    Examples:
        >>> tool = QuickReviewTool()
        >>> result = await tool.review_code(code, file_path)
    """

    name = "quick_review"
    description = """快速审查代码，只关注关键问题.

适合 vibe coding 场景，在保存时快速反馈.
只运行 SecurityAgent，跳过复杂分析.

Args:
    code: 代码内容
    file_path: 文件路径

Returns:
    关键问题列表（最多 5 个）
"""

    def __init__(self) -> None:
        """初始化."""
        from consistency.agents import ReviewSupervisor

        self.supervisor = ReviewSupervisor(quick_mode=True)

    async def review_code(
        self,
        code: str,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """快速审查代码.

        Args:
            code: 代码内容
            file_path: 文件路径

        Returns:
            审查结果
        """
        import time

        start = time.perf_counter()

        result = await self.supervisor.review(Path(file_path), code)

        # 只保留关键问题
        critical_issues = [c for c in result.comments if c.severity in [Severity.CRITICAL, Severity.HIGH]][
            :5
        ]  # 最多 5 个

        duration = (time.perf_counter() - start) * 1000

        return {
            "file": str(file_path),
            "duration_ms": duration,
            "has_critical_issues": len(critical_issues) > 0,
            "issues": [
                {
                    "message": c.message,
                    "severity": c.severity.value,
                    "line": c.line,
                    "category": c.category.value,
                }
                for c in critical_issues
            ],
            "summary": result.summary if critical_issues else "未发现关键问题",
        }


# 便捷函数
async def review_diff(
    diff_text: str,
    repo_path: Path | str,
) -> dict[str, Any]:
    """便捷函数：审查 diff.

    Args:
        diff_text: git diff 输出
        repo_path: 代码库路径

    Returns:
        审查结果
    """
    reviewer = IncrementalReviewer()
    return await reviewer.review_diff(diff_text, repo_path)


async def quick_review(
    code: str,
    file_path: str | Path,
) -> dict[str, Any]:
    """便捷函数：快速审查.

    Args:
        code: 代码内容
        file_path: 文件路径

    Returns:
        审查结果
    """
    tool = QuickReviewTool()
    return await tool.review_code(code, file_path)
