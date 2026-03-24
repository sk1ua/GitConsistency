"""analyze 命令实现."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from consistency.cli.banner import print_banner
from consistency.cli.utils import get_git_commit_sha
from consistency.config import Settings
from consistency.exceptions import GitConsistencyError
from consistency.report.generator import ReportGenerator
from consistency.report.templates import ReportFormat
from consistency.scanners.orchestrator import ScannerOrchestrator

if TYPE_CHECKING:
    import typer

def register_analyze_command(app: "typer.Typer", console: Console) -> None:
    """注册 analyze 命令到主 CLI."""

    @app.command(name="analyze")
    def analyze_command(
        path: Path = Path("."),
        output: Path | None = None,
        format: str = "markdown",
        skip_security: bool = False,
        skip_ai: bool = False,
    ) -> None:
        """分析代码仓库的安全状况."""
        print_banner()
        _run_analyze_command(path, output, format, skip_security, skip_ai, console)


def _run_analyze_command(
    path: Path,
    output: Path | None,
    format: str,
    skip_security: bool,
    skip_ai: bool,
    console: Console,
) -> None:
    """执行分析命令的核心逻辑."""
    from consistency import get_settings

    settings = get_settings()

    console.print(
        Panel.fit(
            f"[bold]分析目标:[/bold] {path.absolute()}\n"
            f"[bold]输出格式:[/bold] {format}\n"
            f"[dim]安全扫描: {'✓' if not skip_security else '✗'} | "
            f"AI 审查: {'✓' if not skip_ai else '✗'}[/dim]",
            title="📋 分析配置",
            border_style="green",
        )
    )

    try:
        result = asyncio.run(
            _run_analysis(
                path=path,
                skip_security=skip_security,
                skip_ai=skip_ai,
                settings=settings,
                console=console,
            )
        )

        generator = ReportGenerator()
        format_map = {
            "markdown": ReportFormat.MARKDOWN,
            "json": ReportFormat.JSON,
            "html": ReportFormat.HTML,
        }
        report_format = format_map.get(format, ReportFormat.MARKDOWN)

        report = generator.generate(
            scan_results=list(result["results"].values()),
            ai_review=result.get("ai_review"),
            project_name=path.resolve().name or "Unknown",
            format=report_format,
            commit_sha=result.get("commit_sha", "unknown"),
            duration=result["duration_ms"] / 1000,
        )

        if output:
            output_path = generator.save_report(report, output, report_format)
            console.print(f"\n[green]✓[/green] 报告已保存: [cyan]{output_path}[/cyan]")
        elif isinstance(report, dict):
            console.print_json(json.dumps(report, indent=2))
        else:
            console.print(report)

        _print_summary(result, console)

    except GitConsistencyError as e:
        console.print(f"\n[red]✗ 分析失败: {e.message}[/red]")
        if settings.debug:
            import traceback

            console.print(traceback.format_exc())
            console.print(f"[dim]Error Code: {e.error_code}[/dim]")
        raise Exception("Exit 1")
    except Exception as e:
        console.print(f"\n[red]✗ 未知错误: {e}[/red]")
        if settings.debug:
            import traceback

            console.print(traceback.format_exc())
        raise Exception("Exit 1")


async def _run_analysis(
    path: Path,
    skip_security: bool,
    skip_ai: bool,
    settings: Settings,
    console: Console,
) -> dict[str, Any]:
    """运行分析."""
    orchestrator = ScannerOrchestrator(settings)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在分析代码...", total=None)

        report = await orchestrator.scan(path, skip_security=skip_security)

        progress.update(task, description="扫描完成，正在生成报告...")

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
            progress.update(task, description="AI 审查完成")

    return {
        "results": report.results,
        "duration_ms": report.duration_ms,
        "ai_review": ai_review,
        "errors": report.errors,
        "commit_sha": get_git_commit_sha(path),
    }


def _print_summary(result: dict[str, Any], console: Console) -> None:
    """打印分析摘要."""
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
