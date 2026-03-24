"""ci 命令实现."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel

from consistency.cli.banner import print_banner
from consistency.cli.utils import get_git_commit_sha
from consistency.exceptions import GitConsistencyError, GitHubError
from consistency.github import GitHubIntegration
from consistency.report.generator import ReportGenerator
from consistency.scanners.orchestrator import ScannerOrchestrator

if TYPE_CHECKING:
    import typer
    from rich.console import Console

    from consistency.config import Settings


def register_ci_command(app: "typer.Typer", console: "Console") -> None:
    """注册 ci 命令到主 CLI."""

    @app.command(name="ci")
    def ci_command(
        event: str = "pull_request",
        pr_number: int | None = None,
        dry_run: bool = False,
        skip_ai: bool = False,
    ) -> None:
        """在 CI/CD 环境中运行（GitHub Actions 等）."""
        print_banner()
        _run_ci_command(event, pr_number, dry_run, skip_ai, console)


def _run_ci_command(
    event: str,
    pr_number: int | None,
    dry_run: bool,
    skip_ai: bool,
    console: "Console",
) -> None:
    """执行 CI 命令的核心逻辑."""
    from consistency import get_settings

    settings = get_settings()

    if not GitHubIntegration.is_github_actions():
        console.print("[yellow]⚠[/yellow] 未检测到 CI 环境，请在 GitHub Actions 中运行")
        raise Exception("Exit 1")

    env_info = GitHubIntegration.detect_from_env()
    if not env_info:
        console.print("[red]✗[/red] 无法获取 CI 环境信息")
        raise Exception("Exit 1")

    repo = env_info.get("repository")
    actual_pr_number = pr_number or env_info.get("pr_number")

    if not repo or not actual_pr_number:
        console.print("[red]✗[/red] 无法获取仓库或 PR 信息")
        raise Exception("Exit 1")

    console.print(
        Panel.fit(
            f"[bold]仓库:[/bold] {repo}\n"
            f"[bold]PR:[/bold] #{actual_pr_number}\n"
            f"[bold]事件:[/bold] {event}\n"
            f"[bold]干运行:[/bold] {'是' if dry_run else '否'}",
            title="🔧 CI 模式",
            border_style="blue",
        )
    )

    try:
        result = asyncio.run(
            _run_analysis(
                path=Path("."),
                skip_security=False,
                skip_ai=skip_ai,
                settings=settings,
            )
        )

        generator = ReportGenerator()
        comment = generator.generate_github_comment(
            scan_results=list(result["results"].values()),
            ai_review=result.get("ai_review"),
            project_name=repo.split("/")[-1],
        )

        if dry_run:
            console.print("\n[yellow]干运行模式，以下是将要发布的评论:[/yellow]")
            console.print(Panel(comment, title="评论预览"))
        else:
            github = GitHubIntegration()
            try:
                post_result = asyncio.run(github.post_comment(repo, actual_pr_number, comment))
                console.print(f"\n[green]✓[/green] 评论已发布: {post_result.get('url', '')}")
            except GitHubError as e:
                console.print(f"\n[red]✗ 评论发布失败: {e.message}[/red]")
                console.print(f"[dim]Error Code: {e.error_code}[/dim]")
                raise Exception("Exit 1")

        _print_summary(result, console)

    except GitConsistencyError as e:
        console.print(f"\n[red]✗ CI 分析失败: {e.message}[/red]")
        if settings.debug:
            console.print(f"[dim]Error Code: {e.error_code}[/dim]")
        raise Exception("Exit 1")
    except Exception as e:
        console.print(f"\n[red]✗ CI 分析失败: {e}[/red]")
        raise Exception("Exit 1")


async def _run_analysis(
    path: Path,
    skip_security: bool,
    skip_ai: bool,
    settings: "Settings",
) -> dict:
    """运行分析."""
    orchestrator = ScannerOrchestrator(settings)

    report = await orchestrator.scan(path, skip_security=skip_security)

    ai_review = None
    if not skip_ai and settings.is_litellm_configured:
        from consistency.reviewer import AIReviewer, ReviewContext

        reviewer = AIReviewer()

        all_findings = []
        for r in report.results.values():
            all_findings.extend(r.findings)

        context = ReviewContext(
            diff="",
            files_changed=[str(f.file_path) for f in all_findings if f.file_path],
            security_findings=[{"severity": f.severity.value, "message": f.message} for f in all_findings[:20]],
        )

        ai_review = await reviewer.review(context)

    return {
        "results": report.results,
        "duration_ms": report.duration_ms,
        "ai_review": ai_review,
        "errors": report.errors,
        "commit_sha": get_git_commit_sha(path),
    }


def _print_summary(result: dict, console: "Console") -> None:
    """打印分析摘要."""
    from rich.table import Table

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
            console.print("\n[yellow]⚠ 当前未发现问题，但扫描器存在错误，请先修复环境后重跑。[/yellow]")
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
