"""GitConsistency CLI 入口.

使用 Typer 构建的现代化命令行界面，支持 Rich 富文本输出.
提供 analyze、ci、scan 等主要命令.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from consistency import __version__
from consistency.config import Settings, get_settings
from consistency.exceptions import (
    GitConsistencyError,
    GitHubError,
)
from consistency.github_integration import GitHubIntegration
from consistency.report.generator import ReportGenerator
from consistency.report.templates import ReportFormat
from consistency.scanners.orchestrator import ScannerOrchestrator

console = Console()

app = typer.Typer(
    name="gitconsistency",
    help="GitConsistency - 代码安全扫描与 AI 审查",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

scan_app = typer.Typer(help="安全扫描命令")
config_app = typer.Typer(help="配置相关命令")
review_app = typer.Typer(help="AI 代码审查命令")
app.add_typer(scan_app, name="scan")
app.add_typer(config_app, name="config")
app.add_typer(review_app, name="review")


def version_callback(value: bool) -> None:
    """显示版本信息并退出."""
    if value:
        console.print(
            Panel.fit(
                f"[bold blue]GitConsistency[/bold blue] [green]v{__version__}[/green]\n"
                f"[dim]代码安全扫描与 AI 审查[/dim]",
                title="版本信息",
                border_style="blue",
            )
        )
        raise typer.Exit()


def _print_banner() -> None:
    """打印欢迎横幅."""
    banner = Text()
    banner.append("╔═══════════════════════════════════════════╗\n", style="cyan")
    banner.append("║   ", style="cyan")
    banner.append("🔍 GitConsistency", style="bold cyan")
    banner.append("", style="dim")
    banner.append("                    ║\n", style="cyan")
    banner.append("║   ", style="cyan")
    banner.append("代码安全扫描与 AI 审查", style="dim")
    banner.append("           ║\n", style="cyan")
    banner.append("╚═══════════════════════════════════════════╝", style="cyan")
    console.print(banner)
    console.print()


def _get_git_commit_sha(path: Path) -> str:
    """获取目标路径下的 Git 提交 SHA，失败时返回 unknown."""
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


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="显示版本信息",
        ),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            "-d",
            help="启用调试模式",
        ),
    ] = False,
) -> None:
    """GitConsistency - 代码安全扫描与 AI 审查.

    为项目提供：
    - 安全扫描（Semgrep + Bandit）
    - AI 代码审查
    - GitHub PR 自动评论
    """
    settings = get_settings()
    if debug:
        settings.debug = True
        console.print("[dim]🐛 调试模式已启用[/dim]")


@app.command(name="analyze")
def analyze_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="要分析的代码路径",
            exists=True,
        ),
    ] = Path("."),
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="输出文件路径",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="输出格式 (markdown, json, html)",
        ),
    ] = "markdown",
    skip_security: Annotated[
        bool,
        typer.Option(
            "--skip-security",
            help="跳过安全扫描",
        ),
    ] = False,
    skip_ai: Annotated[
        bool,
        typer.Option(
            "--skip-ai",
            help="跳过 AI 审查",
        ),
    ] = False,
) -> None:
    """分析代码仓库的安全状况.

    运行安全扫描和 AI 审查.

    Examples:
        $ gitconsistency analyze ./my-project
        $ gitconsistency analyze . -o report.md --format markdown
        $ gitconsistency analyze . --skip-ai
    """
    _print_banner()

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

        _print_summary(result)

    except GitConsistencyError as e:
        console.print(f"\n[red]✗ 分析失败: {e.message}[/red]")
        if settings.debug:
            import traceback

            console.print(traceback.format_exc())
            console.print(f"[dim]Error Code: {e.error_code}[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ 未知错误: {e}[/red]")
        if settings.debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)


async def _run_analysis(
    path: Path,
    skip_security: bool,
    skip_ai: bool,
    settings: Settings,
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
        "commit_sha": _get_git_commit_sha(path),
    }


def _print_summary(result: dict[str, Any]) -> None:
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


@app.command(name="ci")
def ci_command(
    event: Annotated[
        str,
        typer.Option(
            "--event",
            "-e",
            help="CI 事件类型",
        ),
    ] = "pull_request",
    pr_number: Annotated[
        int | None,
        typer.Option(
            "--pr",
            help="PR 编号（覆盖自动检测）",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="干运行模式（不实际发布评论）",
        ),
    ] = False,
    skip_ai: Annotated[
        bool,
        typer.Option(
            "--skip-ai",
            help="跳过 AI 审查",
        ),
    ] = False,
) -> None:
    """在 CI/CD 环境中运行（GitHub Actions 等）.

    自动检测 GitHub Actions 环境变量，分析 PR 并发布评论.

    Examples:
        $ gitconsistency ci
        $ gitconsistency ci --event pull_request --dry-run
    """
    settings = get_settings()

    _print_banner()

    if not GitHubIntegration.is_github_actions():
        console.print("[yellow]⚠[/yellow] 未检测到 CI 环境，请在 GitHub Actions 中运行")
        raise typer.Exit(1)

    env_info = GitHubIntegration.detect_from_env()
    if not env_info:
        console.print("[red]✗[/red] 无法获取 CI 环境信息")
        raise typer.Exit(1)

    repo = env_info.get("repository")
    actual_pr_number = pr_number or env_info.get("pr_number")

    if not repo or not actual_pr_number:
        console.print("[red]✗[/red] 无法获取仓库或 PR 信息")
        raise typer.Exit(1)

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
                raise typer.Exit(1)

        _print_summary(result)

    except GitConsistencyError as e:
        console.print(f"\n[red]✗ CI 分析失败: {e.message}[/red]")
        if settings.debug:
            console.print(f"[dim]Error Code: {e.error_code}[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ CI 分析失败: {e}[/red]")
        raise typer.Exit(1)


@scan_app.command(name="security")
def scan_security(
    path: Annotated[
        Path,
        typer.Argument(help="扫描路径"),
    ] = Path("."),
    rules: Annotated[
        list[str] | None,
        typer.Option(
            "--rules",
            "-r",
            help="Semgrep 规则",
        ),
    ] = None,
) -> None:
    """运行安全扫描（Semgrep + Bandit）."""
    console.print(f"[blue]🔒 安全扫描:[/blue] {path}")

    async def run() -> None:
        from consistency.scanners.security_scanner import SecurityScanner

        scanner = SecurityScanner(semgrep_rules=rules)
        result = await scanner.scan(path)

        console.print(f"扫描文件: {result.scanned_files}")
        console.print(f"发现问题: {len(result.findings)}")

        if result.errors:
            console.print("[red]扫描错误：[/red]")
            for err in result.errors:
                console.print(f"  [red]- {err}[/red]")

        for finding in result.findings:
            console.print(f"  [{finding.severity.value}] {finding.rule_id}: {finding.message[:80]}")

    asyncio.run(run())


@config_app.command(name="show")
def config_show() -> None:
    """显示当前配置."""
    settings = get_settings()

    table = Table(title="当前配置")
    table.add_column("配置项", style="cyan")
    table.add_column("值")

    for key, value in settings.model_dump().items():
        if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
            value = "***" if value else "未设置"
        table.add_row(key, str(value))

    console.print(table)


@config_app.command(name="validate")
def config_validate() -> None:
    """验证配置有效性."""
    settings = get_settings()

    table = Table(title="配置验证")
    table.add_column("组件", style="bold")
    table.add_column("状态")
    table.add_column("说明")

    checks = [
        ("LLM", settings.is_litellm_configured, "AI 代码审查"),
        ("GitHub", settings.is_github_configured, "PR 评论"),
        ("GitNexus", settings.is_gitnexus_configured, "代码图谱分析"),
    ]

    for name, ok, desc in checks:
        status = "[green]✓ 已配置[/green]" if ok else "[yellow]○ 未配置[/yellow]"
        table.add_row(name, status, desc)

    console.print(table)
    console.print("\n[dim]注意: 未配置项将跳过对应功能，不影响其他功能运行[/dim]")


# ========== Review 命令 ==========


@review_app.command(name="file")
def review_file_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="要审查的文件路径",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    quick: Annotated[
        bool,
        typer.Option(
            "--quick",
            "-q",
            help="快速模式（只检查关键问题）",
        ),
    ] = False,
    show_code: Annotated[
        bool,
        typer.Option(
            "--show-code",
            "-c",
            help="显示代码片段",
        ),
    ] = False,
) -> None:
    """审查单个文件.

    使用多 Agent 架构进行 AI 代码审查.

    Examples:
        $ gitconsistency review file main.py
        $ gitconsistency review file main.py --quick
        $ gitconsistency review file main.py --show-code
    """
    from consistency.commands import ReviewCommand

    async def run() -> None:
        cmd = ReviewCommand(quick_mode=quick)
        result = await cmd.review_file(path, show_code=show_code)

        if not result.get("success"):
            raise typer.Exit(1)

    asyncio.run(run())


@review_app.command(name="diff")
def review_diff_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Git 仓库路径",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("."),
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            "-t",
            help="目标分支/提交（默认对比 HEAD）",
        ),
    ] = None,
    cached: Annotated[
        bool,
        typer.Option(
            "--cached",
            "-s",
            help="审查暂存区（staged changes）",
        ),
    ] = False,
    quick: Annotated[
        bool,
        typer.Option(
            "--quick",
            "-q",
            help="快速模式",
        ),
    ] = False,
) -> None:
    """审查变更代码（git diff）.

    只审查变更的部分，适合 pre-commit 或保存时触发.

    Examples:
        $ gitconsistency review diff
        $ gitconsistency review diff --cached
        $ gitconsistency review diff --target main
        $ gitconsistency review diff --quick
    """
    from consistency.commands import ReviewCommand

    async def run() -> None:
        cmd = ReviewCommand(quick_mode=quick)
        result = await cmd.review_diff(path, target=target, cached=cached)

        if not result.get("success"):
            raise typer.Exit(1)

        # 有关键问题时返回非零状态码
        if result.get("issues_count", 0) > 0 and not quick:
            console.print("\n[yellow]⚠ 发现潜在问题，请检查[/yellow]")

    asyncio.run(run())


@review_app.command(name="batch")
def review_batch_command(
    paths: Annotated[
        list[Path],
        typer.Argument(
            help="要审查的文件路径列表",
            exists=True,
        ),
    ],
    quick: Annotated[
        bool,
        typer.Option(
            "--quick",
            "-q",
            help="快速模式",
        ),
    ] = False,
) -> None:
    """批量审查多个文件.

    Examples:
        $ gitconsistency review batch main.py utils.py
        $ gitconsistency review batch *.py --quick
    """
    from consistency.commands import ReviewCommand

    async def run() -> None:
        cmd = ReviewCommand(quick_mode=quick, max_workers=5)
        result = await cmd.review_batch(paths)

        if not result.get("success"):
            raise typer.Exit(1)

    asyncio.run(run())


@app.command(name="init")
def init_command(
    path: Annotated[
        Path,
        typer.Argument(help="初始化路径"),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="覆盖现有文件",
        ),
    ] = False,
) -> None:
    """在新项目中初始化 GitConsistency 配置.

    创建 .env 文件、GitHub Actions 工作流等.

    Examples:
        $ gitconsistency init ./my-project
        $ gitconsistency init . --force
    """
    _print_banner()

    console.print(f"[blue]📁 初始化路径:[/blue] {path.absolute()}")

    env_file = path / ".env"
    if env_file.exists() and not force:
        console.print(f"[yellow]⚠[/yellow] {env_file} 已存在，使用 --force 覆盖")
    else:
        env_content = """# GitConsistency 配置
LITELLM_API_KEY=your_api_key_here
GITHUB_TOKEN=your_github_token_here
"""
        env_file.write_text(env_content, encoding="utf-8")
        console.print(f"[green]✓[/green] 创建: {env_file}")

    github_dir = path / ".github" / "workflows"
    github_dir.mkdir(parents=True, exist_ok=True)

    workflow_file = github_dir / "consistency.yml"
    workflow_content = """name: 🔍 GitConsistency Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install GitConsistency
        run: pip install "git-consistency[full]"
      - name: Run Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          LITELLM_API_KEY: ${{ secrets.LITELLM_API_KEY }}
        run: gitconsistency ci
"""
    workflow_file.write_text(workflow_content, encoding="utf-8")
    console.print(f"[green]✓[/green] 创建: {workflow_file}")

    console.print("\n[green]🎉 初始化完成！[/green]")
    console.print("[dim]下一步: 编辑 .env 文件，配置 API 密钥[/dim]")


if __name__ == "__main__":
    app()
