"""分析命令.

提供代码仓库的安全分析功能，集成安全扫描和 AI 审查.

Examples:
    >>> from consistency.commands.analyze import AnalyzeCommand
    >>> cmd = AnalyzeCommand()
    >>> await cmd.analyze(Path("./my-project"))
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from consistency.config import Settings, get_settings
from consistency.exceptions import GitConsistencyError
from consistency.report.generator import ReportGenerator
from consistency.report.templates import ReportFormat
from consistency.scanners.orchestrator import ScannerOrchestrator

console = Console()


class AnalyzeCommand:
    """分析命令处理器.

    处理代码仓库的安全分析和 AI 审查，支持多种输出格式.

    Attributes:
        settings: 应用配置
        skip_security: 是否跳过安全扫描
        skip_ai: 是否跳过 AI 审查
    """

    def __init__(
        self,
        settings: Settings | None = None,
        skip_security: bool = False,
        skip_ai: bool = False,
    ) -> None:
        """初始化分析命令.

        Args:
            settings: 应用配置（默认从全局获取）
            skip_security: 跳过安全扫描
            skip_ai: 跳过 AI 审查
        """
        self.settings = settings or get_settings()
        self.skip_security = skip_security
        self.skip_ai = skip_ai

    async def analyze(
        self,
        path: Path,
        output: Path | None = None,
        format: str = "markdown",
    ) -> dict[str, Any]:
        """执行代码分析.

        Args:
            path: 要分析的代码路径
            output: 输出文件路径（None 则输出到控制台）
            format: 输出格式 (markdown, json, html)

        Returns:
            分析结果字典

        Raises:
            GitConsistencyError: 分析过程中发生错误
        """
        console.print(
            Panel.fit(
                f"[bold]分析目标:[/bold] {path.absolute()}\n"
                f"[bold]输出格式:[/bold] {format}\n"
                f"[dim]安全扫描: {'✓' if not self.skip_security else '✗'} | "
                f"AI 审查: {'✓' if not self.skip_ai else '✗'}[/dim]",
                title="📋 分析配置",
                border_style="green",
            )
        )

        try:
            result = await self._run_analysis(path)

            report = self._generate_report(result, path, format)

            if output:
                output_path = self._save_report(report, output, format)
                console.print(f"\n[green]✓[/green] 报告已保存: [cyan]{output_path}[/cyan]")
            elif isinstance(report, dict):
                console.print_json(json.dumps(report, indent=2))
            else:
                console.print(report)

            self._print_summary(result)

            return {
                "success": True,
                "results": result["results"],
                "duration_ms": result["duration_ms"],
                "commit_sha": result.get("commit_sha", "unknown"),
            }

        except GitConsistencyError as e:
            console.print(f"\n[red]✗ 分析失败: {e.message}[/red]")
            if self.settings.debug:
                import traceback

                console.print(traceback.format_exc())
                console.print(f"[dim]Error Code: {e.error_code}[/dim]")
            raise

    async def _run_analysis(self, path: Path) -> dict[str, Any]:
        """运行分析.

        Args:
            path: 扫描目标路径

        Returns:
            分析结果字典
        """
        orchestrator = ScannerOrchestrator(self.settings)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("正在分析代码...", total=None)

            report = await orchestrator.scan(path, skip_security=self.skip_security)

            progress.update(task, description="扫描完成，正在生成报告...")

            ai_review = None
            if not self.skip_ai and self.settings.is_litellm_configured:
                ai_review = await self._run_ai_review(report)
                progress.update(task, description="AI 审查完成")

        return {
            "results": report.results,
            "duration_ms": report.duration_ms,
            "ai_review": ai_review,
            "errors": report.errors,
            "commit_sha": self._get_git_commit_sha(path),
        }

    async def _run_ai_review(self, report: Any) -> Any:
        """运行 AI 审查.

        Args:
            report: 扫描报告

        Returns:
            AI 审查结果
        """
        from consistency.reviewer import AIReviewer, ReviewContext

        reviewer = AIReviewer()

        all_findings = []
        for r in report.results.values():
            all_findings.extend(r.findings)

        context = ReviewContext(
            diff="",
            files_changed=[str(f.file_path) for f in all_findings if f.file_path],
            security_findings=[
                {"severity": f.severity.value, "message": f.message}
                for f in all_findings[:20]
            ],
        )

        return await reviewer.review(context)

    def _generate_report(
        self,
        result: dict[str, Any],
        path: Path,
        format: str,
    ) -> str | dict[str, Any]:
        """生成报告.

        Args:
            result: 分析结果
            path: 目标路径
            format: 输出格式

        Returns:
            报告内容（字符串或字典）
        """
        generator = ReportGenerator()
        format_map = {
            "markdown": ReportFormat.MARKDOWN,
            "json": ReportFormat.JSON,
            "html": ReportFormat.HTML,
        }
        report_format = format_map.get(format, ReportFormat.MARKDOWN)

        return generator.generate(
            scan_results=list(result["results"].values()),
            ai_review=result.get("ai_review"),
            project_name=path.resolve().name or "Unknown",
            format=report_format,
            commit_sha=result.get("commit_sha", "unknown"),
            duration=result["duration_ms"] / 1000,
        )

    def _save_report(
        self,
        report: str | dict[str, Any],
        output: Path,
        format: str,
    ) -> Path:
        """保存报告到文件.

        Args:
            report: 报告内容
            output: 输出路径
            format: 格式

        Returns:
            实际保存的路径
        """
        generator = ReportGenerator()
        format_map = {
            "markdown": ReportFormat.MARKDOWN,
            "json": ReportFormat.JSON,
            "html": ReportFormat.HTML,
        }
        report_format = format_map.get(format, ReportFormat.MARKDOWN)
        return generator.save_report(report, output, report_format)

    def _print_summary(self, result: dict[str, Any]) -> None:
        """打印分析摘要.

        Args:
            result: 分析结果
        """
        scan_errors = list(result.get("errors", []))
        for scan_result in result.get("results", {}).values():
            scan_errors.extend(getattr(scan_result, "errors", []))

        if scan_errors:
            console.print("\n[red]⚠ 扫描过程中发生错误，结果可能不完整：[/red]")
            for err in scan_errors:
                console.print(f"[red]- {err}[/red]")

        all_findings = []
        for r in result["results"].values():
            all_findings.extend(r.findings)

        if not all_findings:
            if scan_errors:
                console.print(
                    "\n[yellow]⚠ 当前未发现问题，但扫描器存在错误，请先修复环境后重跑。[/yellow]"
                )
            else:
                console.print("\n[green]🎉 未发现安全问题！[/green]")
            return

        table = Table(title="安全扫描结果摘要")
        table.add_column("严重程度", style="bold")
        table.add_column("数量", justify="right")

        severity_counts: dict[str, int] = {}
        for f in all_findings:
            severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1

        for sev, count in sorted(severity_counts.items(), key=lambda x: x[1], reverse=True):
            color = {
                "critical": "red",
                "high": "orange3",
                "medium": "yellow",
                "low": "green",
                "info": "blue",
            }.get(sev, "white")
            table.add_row(f"[{color}]{sev.upper()}[/{color}]", str(count))

        console.print(table)

    @staticmethod
    def _get_git_commit_sha(path: Path) -> str:
        """获取 Git 提交 SHA.

        Args:
            path: Git 仓库路径

        Returns:
            提交 SHA 或 "unknown"
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                check=True,
            )
            sha = result.stdout.strip()
            return sha if sha else "unknown"
        except Exception:
            return "unknown"
