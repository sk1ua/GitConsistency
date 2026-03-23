"""代码审查命令.

提供交互式代码审查功能，支持增量审查和快速模式.

Examples:
    >>> from consistency.commands.review import ReviewCommand
    >>> cmd = ReviewCommand()
    >>> await cmd.review_file("main.py")
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from consistency.agents import ReviewSupervisor
from consistency.core import GitNexusClient
from consistency.tools.diff_tools import DiffParser, IncrementalReviewer

logger = logging.getLogger(__name__)
console = Console()


class ReviewCommand:
    """审查命令处理器.

    处理各种审查场景：
    - 单文件审查
    - 增量审查（git diff）
    - 快速模式（只检查关键问题）
    - 完整模式（全量分析）

    Attributes:
        quick_mode: 是否启用快速模式
        use_gitnexus: 是否使用 GitNexus 上下文
    """

    def __init__(
        self,
        quick_mode: bool = False,
        use_gitnexus: bool = True,
        max_workers: int = 3,
    ) -> None:
        """初始化审查命令.

        Args:
            quick_mode: 启用快速模式（只运行 SecurityAgent）
            use_gitnexus: 是否使用 GitNexus 获取代码上下文
            max_workers: 最大并发数
        """
        self.quick_mode = quick_mode
        self.use_gitnexus = use_gitnexus
        self.max_workers = max_workers
        self.supervisor = ReviewSupervisor(quick_mode=quick_mode)
        self.diff_parser = DiffParser()
        self.incremental_reviewer = IncrementalReviewer()
        self._gitnexus: GitNexusClient | None = None

    async def _get_gitnexus(self) -> GitNexusClient | None:
        """获取或创建 GitNexus 客户端.

        Returns:
            GitNexusClient 实例，如果不可用则返回 None
        """
        if not self.use_gitnexus:
            return None

        if self._gitnexus is None:
            try:
                client = GitNexusClient()
                if await client.ensure_available():
                    self._gitnexus = client
                else:
                    console.print("[yellow]⚠ GitNexus 不可用，将不使用代码知识图谱[/yellow]")
            except Exception as e:
                logger.warning(f"GitNexus 初始化失败: {e}")
                console.print("[yellow]⚠ GitNexus 初始化失败，将不使用代码知识图谱[/yellow]")

        return self._gitnexus

    async def review_file(
        self,
        file_path: Path | str,
        show_code: bool = False,
    ) -> dict[str, Any]:
        """审查单个文件.

        Args:
            file_path: 文件路径
            show_code: 是否显示代码片段

        Returns:
            审查结果字典
        """
        file_path = Path(file_path)

        if not file_path.exists():
            console.print(f"[red]✗ 文件不存在: {file_path}[/red]")
            return {"success": False, "error": "文件不存在"}

        try:
            code = file_path.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"[red]✗ 读取文件失败: {e}[/red]")
            return {"success": False, "error": str(e)}

        mode_text = "快速模式" if self.quick_mode else "完整模式"
        console.print(f"[blue]🔍 正在审查 {file_path.name} ({mode_text})...[/blue]")

        # 确保 GitNexus 已初始化
        await self._get_gitnexus()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("分析中...", total=None)

            try:
                result = await self.supervisor.review(file_path, code)
            except Exception as e:
                console.print(f"[red]✗ 审查失败: {e}[/red]")
                return {"success": False, "error": str(e)}

        # 显示结果
        self._display_result(result, file_path, code if show_code else None)

        return {
            "success": True,
            "file": str(file_path),
            "summary": result.summary,
            "comments_count": len(result.comments),
            "severity": result.overall_severity.value,
        }

    async def review_diff(
        self,
        repo_path: Path | str,
        target: str | None = None,
        cached: bool = False,
    ) -> dict[str, Any]:
        """审查变更（git diff）.

        Args:
            repo_path: Git 仓库路径
            target: 目标分支/提交（默认对比 HEAD）
            cached: 是否审查暂存区

        Returns:
            审查结果字典
        """
        repo_path = Path(repo_path)

        if not (repo_path / ".git").exists():
            console.print(f"[red]✗ 不是 Git 仓库: {repo_path}[/red]")
            return {"success": False, "error": "不是 Git 仓库"}

        # 构建 git diff 命令
        cmd = ["git", "-C", str(repo_path), "diff"]

        if cached:
            cmd.append("--cached")

        if target:
            cmd.append(target)

        cmd.extend(["--no-color", "-U3"])  # 3 行上下文

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            diff_text = result.stdout
        except Exception as e:
            console.print(f"[red]✗ 获取 diff 失败: {e}[/red]")
            return {"success": False, "error": str(e)}

        if not diff_text.strip():
            console.print("[yellow]⚠ 没有检测到变更[/yellow]")
            return {"success": True, "summary": "没有检测到变更"}

        mode_text = "快速模式" if self.quick_mode else "完整模式"
        console.print(f"[blue]🔍 正在审查变更 ({mode_text})...[/blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("分析变更...", total=None)

            review_result = await self.incremental_reviewer.review_diff(
                diff_text,
                repo_path,
                supervisor=self.supervisor,
            )

        # 显示结果
        self._display_diff_result(review_result)

        return {
            "success": True,
            "summary": review_result["summary"],
            "files_count": review_result["files_count"],
            "issues_count": review_result["issues_count"],
        }

    async def review_batch(
        self,
        files: list[Path | str],
    ) -> dict[str, Any]:
        """批量审查文件.

        Args:
            files: 文件路径列表

        Returns:
            审查结果字典
        """
        if not files:
            console.print("[yellow]⚠ 没有指定文件[/yellow]")
            return {"success": True, "summary": "没有指定文件"}

        console.print(f"[blue]🔍 正在审查 {len(files)} 个文件...[/blue]")

        # 准备任务
        tasks = []
        valid_files = []

        for f in files:
            path = Path(f)
            if path.exists():
                try:
                    code = path.read_text(encoding="utf-8")
                    tasks.append((path, code))
                    valid_files.append(path)
                except Exception as e:
                    console.print(f"[yellow]⚠ 跳过 {path}: {e}[/yellow]")

        if not tasks:
            console.print("[yellow]⚠ 没有可审查的文件[/yellow]")
            return {"success": True, "summary": "没有可审查的文件"}

        # 执行批量审查
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(f"审查 {len(tasks)} 个文件...", total=None)

            results = await self.supervisor.review_batch(
                tasks,
                max_concurrency=self.max_workers,
            )

        # 汇总结果
        total_issues = sum(len(r.comments) for r in results)
        critical_count = sum(1 for r in results for c in r.comments if c.severity.value in ("CRITICAL", "HIGH"))

        # 显示汇总表
        self._display_batch_summary(valid_files, results, total_issues, critical_count)

        return {
            "success": True,
            "files_count": len(valid_files),
            "issues_count": total_issues,
            "critical_count": critical_count,
        }

    def _display_result(
        self,
        result: Any,
        file_path: Path,
        code: str | None = None,
    ) -> None:
        """显示单个文件审查结果."""
        # 摘要
        summary_color = {
            "CRITICAL": "red",
            "HIGH": "red",
            "MEDIUM": "yellow",
            "LOW": "blue",
            "INFO": "green",
        }.get(result.overall_severity.value, "white")

        console.print(
            Panel(
                result.summary,
                title=f"[bold]{file_path.name} 审查结果[/bold]",
                border_style=summary_color,
            )
        )

        # 问题列表
        if result.comments:
            table = Table(title=f"发现 {len(result.comments)} 个问题")
            table.add_column("严重级别", style="cyan", width=10)
            table.add_column("类别", style="magenta", width=12)
            table.add_column("行号", style="green", width=6)
            table.add_column("描述", style="white")

            for comment in result.comments:
                sev_color = {
                    "CRITICAL": "red",
                    "HIGH": "red",
                    "MEDIUM": "yellow",
                    "LOW": "blue",
                    "INFO": "green",
                }.get(comment.severity.value, "white")

                table.add_row(
                    f"[{sev_color}]{comment.severity.value}[/{sev_color}]",
                    comment.category.value,
                    str(comment.line) if comment.line else "-",
                    comment.message,
                )

            console.print(table)
        else:
            console.print("[green]✓ 未发现明显问题[/green]")

        # 显示代码（如果请求）
        if code and result.comments:
            console.print("\n[bold]相关代码片段:[/bold]")
            for comment in result.comments[:3]:  # 只显示前 3 个的上下文
                if comment.line:
                    lines = code.split("\n")
                    start = max(0, comment.line - 3)
                    end = min(len(lines), comment.line + 2)
                    snippet = "\n".join(lines[start:end])

                    syntax = Syntax(
                        snippet,
                        file_path.suffix.lstrip(".") or "python",
                        theme="monokai",
                        line_numbers=True,
                        start_line=start + 1,
                    )
                    console.print(syntax)

    def _display_diff_result(self, result: dict[str, Any]) -> None:
        """显示 diff 审查结果."""
        console.print(
            Panel(
                result["summary"],
                title="[bold]增量审查结果[/bold]",
                border_style="blue",
            )
        )

        if not result["results"]:
            return

        # 每个文件的结果
        for item in result["results"]:
            changes = item["changes"]
            review = item["review"]

            file_summary = f"{changes['path']} (+{changes['added_lines']}/-{changes['removed_lines']})"

            if review.comments:
                sev = review.overall_severity.value
                color = {
                    "CRITICAL": "red",
                    "HIGH": "red",
                    "MEDIUM": "yellow",
                }.get(sev, "green")

                console.print(f"\n[{color}]● {file_summary}[/{color}]")

                for c in review.comments[:3]:  # 最多显示 3 个
                    sev_color = {
                        "CRITICAL": "red",
                        "HIGH": "red",
                        "MEDIUM": "yellow",
                        "LOW": "blue",
                    }.get(c.severity.value, "white")

                    console.print(f"  [{sev_color}]{c.severity.value}[/{sev_color}] {c.message}")
            else:
                console.print(f"[green]✓ {file_summary}[/green]")

    def _display_batch_summary(
        self,
        files: list[Path],
        results: list[Any],
        total_issues: int,
        critical_count: int,
    ) -> None:
        """显示批量审查汇总."""
        # 汇总面板
        status = "✓ 通过" if critical_count == 0 else "✗ 发现问题"
        color = "green" if critical_count == 0 else "red"

        summary = f"""
审查完成: {status}
文件数: {len(files)}
问题数: {total_issues}
关键问题: {critical_count}
"""

        console.print(
            Panel(
                summary.strip(),
                title="[bold]批量审查汇总[/bold]",
                border_style=color,
            )
        )

        # 详细结果表
        if total_issues > 0:
            table = Table(title="问题分布")
            table.add_column("文件", style="cyan")
            table.add_column("问题数", style="magenta")
            table.add_column("严重程度", style="red")

            for f, r in zip(files, results):
                if r.comments:
                    sev = r.overall_severity.value
                    table.add_row(
                        f.name,
                        str(len(r.comments)),
                        sev,
                    )

            console.print(table)


# 便捷函数
async def review_file(
    file_path: Path | str,
    quick: bool = False,
    show_code: bool = False,
) -> dict[str, Any]:
    """便捷函数：审查文件.

    Args:
        file_path: 文件路径
        quick: 启用快速模式
        show_code: 显示代码片段

    Returns:
        审查结果
    """
    cmd = ReviewCommand(quick_mode=quick)
    return await cmd.review_file(file_path, show_code)


async def review_diff(
    repo_path: Path | str,
    target: str | None = None,
    cached: bool = False,
    quick: bool = False,
) -> dict[str, Any]:
    """便捷函数：审查变更.

    Args:
        repo_path: 仓库路径
        target: 目标分支/提交
        cached: 审查暂存区
        quick: 启用快速模式

    Returns:
        审查结果
    """
    cmd = ReviewCommand(quick_mode=quick)
    return await cmd.review_diff(repo_path, target, cached)
