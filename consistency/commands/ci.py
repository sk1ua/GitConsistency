"""CI 命令.

提供 CI/CD 环境（GitHub Actions 等）中的代码审查功能.

Examples:
    >>> from consistency.commands.ci import CICommand
    >>> cmd = CICommand()
    >>> await cmd.run_ci()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from consistency.config import Settings, get_settings
from consistency.exceptions import GitConsistencyError, GitHubError
from consistency.github import GitHubIntegration
from consistency.report.generator import ReportGenerator

from consistency.commands.analyze import AnalyzeCommand

console = Console()


class CICommand:
    """CI 命令处理器.

    在 CI/CD 环境中运行代码审查，自动发布 PR 评论.

    Attributes:
        settings: 应用配置
        dry_run: 干运行模式
        skip_ai: 是否跳过 AI 审查
    """

    def __init__(
        self,
        settings: Settings | None = None,
        dry_run: bool = False,
        skip_ai: bool = False,
    ) -> None:
        """初始化 CI 命令.

        Args:
            settings: 应用配置（默认从全局获取）
            dry_run: 干运行模式（不实际发布评论）
            skip_ai: 跳过 AI 审查
        """
        self.settings = settings or get_settings()
        self.dry_run = dry_run
        self.skip_ai = skip_ai

    async def run_ci(
        self,
        event: str = "pull_request",
        pr_number: int | None = None,
    ) -> dict[str, Any]:
        """在 CI 环境中运行分析.

        Args:
            event: CI 事件类型
            pr_number: PR 编号（覆盖自动检测）

        Returns:
            CI 运行结果

        Raises:
            GitConsistencyError: 分析过程中发生错误
        """
        if not GitHubIntegration.is_github_actions():
            console.print("[yellow]⚠[/yellow] 未检测到 CI 环境，请在 GitHub Actions 中运行")
            return {"success": False, "error": "Not in CI environment"}

        env_info = GitHubIntegration.detect_from_env()
        if not env_info:
            console.print("[red]✗[/red] 无法获取 CI 环境信息")
            return {"success": False, "error": "Cannot detect CI environment"}

        repo = env_info.get("repository")
        actual_pr_number = pr_number or env_info.get("pr_number")

        if not repo or not actual_pr_number:
            console.print("[red]✗[/red] 无法获取仓库或 PR 信息")
            return {"success": False, "error": "Missing repo or PR number"}

        console.print(
            Panel.fit(
                f"[bold]仓库:[/bold] {repo}\n"
                f"[bold]PR:[/bold] #{actual_pr_number}\n"
                f"[bold]事件:[/bold] {event}\n"
                f"[bold]干运行:[/bold] {'是' if self.dry_run else '否'}",
                title="🔧 CI 模式",
                border_style="blue",
            )
        )

        try:
            # 使用 AnalyzeCommand 执行分析
            analyze_cmd = AnalyzeCommand(
                settings=self.settings,
                skip_security=False,
                skip_ai=self.skip_ai,
            )
            result = await analyze_cmd._run_analysis(Path("."))

            # 生成 GitHub 评论
            generator = ReportGenerator()
            comment = generator.generate_github_comment(
                scan_results=list(result["results"].values()),
                ai_review=result.get("ai_review"),
                project_name=repo.split("/")[-1],
            )

            if self.dry_run:
                console.print("\n[yellow]干运行模式，以下是将要发布的评论:[/yellow]")
                console.print(Panel(comment, title="评论预览"))
            else:
                await self._post_comment(repo, actual_pr_number, comment)

            self._print_summary(result)

            return {
                "success": True,
                "repo": repo,
                "pr_number": actual_pr_number,
                "findings_count": sum(
                    len(r.findings) for r in result["results"].values()
                ),
            }

        except GitConsistencyError as e:
            console.print(f"\n[red]✗ CI 分析失败: {e.message}[/red]")
            if self.settings.debug:
                console.print(f"[dim]Error Code: {e.error_code}[/dim]")
            raise

    async def _post_comment(
        self,
        repo: str,
        pr_number: int,
        comment: str,
    ) -> None:
        """发布 PR 评论.

        Args:
            repo: 仓库名
            pr_number: PR 编号
            comment: 评论内容

        Raises:
            GitHubError: 发布失败
        """
        github = GitHubIntegration()
        try:
            post_result = await github.post_comment(repo, pr_number, comment)
            console.print(f"\n[green]✓[/green] 评论已发布: {post_result.get('url', '')}")
        except GitHubError as e:
            console.print(f"\n[red]✗ 评论发布失败: {e.message}[/red]")
            console.print(f"[dim]Error Code: {e.error_code}[/dim]")
            raise

    def _print_summary(self, result: dict[str, Any]) -> None:
        """打印分析摘要.

        Args:
            result: 分析结果
        """
        from rich.table import Table

        scan_errors = list(result.get("errors", []))
        for scan_result in result.get("results", {}).values():
            scan_errors.extend(getattr(scan_result, "errors", []))

        if scan_errors:
            console.print("\n[red]⚠ 扫描过程中发生错误：[/red]")
            for err in scan_errors:
                console.print(f"[red]- {err}[/red]")

        all_findings = []
        for r in result["results"].values():
            all_findings.extend(r.findings)

        if not all_findings:
            if scan_errors:
                console.print(
                    "\n[yellow]⚠ 当前未发现问题，但扫描器存在错误。[/yellow]"
                )
            else:
                console.print("\n[green]🎉 未发现安全问题！[/green]")
            return

        table = Table(title="CI 扫描结果摘要")
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
