"""ci 命令实现."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    from consistency.reviewer.models import ReviewResult


def register_ci_command(app: typer.Typer, console: Console) -> None:
    """注册 ci 命令到主 CLI."""

    @app.command(name="ci")
    def ci_command(
        event: str = "pull_request",
        pr_number: int | None = None,
        dry_run: bool = False,
        skip_ai: bool = False,
        use_agents: bool = True,
        changed_only: bool = False,
        base: str = "main",
    ) -> None:
        """在 CI/CD 环境中运行（GitHub Actions 等）."""
        print_banner()
        _run_ci_command(event, pr_number, dry_run, skip_ai, use_agents, changed_only, base, console)


def _run_ci_command(
    event: str,
    pr_number: int | None,
    dry_run: bool,
    skip_ai: bool,
    use_agents: bool,
    changed_only: bool,
    base: str,
    console: Console,
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

    # 获取变更文件列表（如果启用增量扫描）
    changed_files = None
    if changed_only:
        changed_files = _get_changed_files(base, console)
        if changed_files:
            console.print(f"[blue]📁 增量扫描模式，发现 {len(changed_files)} 个变更文件[/blue]")

    console.print(
        Panel.fit(
            f"[bold]仓库:[/bold] {repo}\n"
            f"[bold]PR:[/bold] #{actual_pr_number}\n"
            f"[bold]事件:[/bold] {event}\n"
            f"[bold]干运行:[/bold] {'是' if dry_run else '否'}\n"
            f"[bold]增量扫描:[/bold] {'是' if changed_only else '否'}",
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
                use_agents=use_agents,
                changed_files=changed_files,
                settings=settings,
                console=console,
            )
        )

        # 生成报告
        generator = ReportGenerator()

        # 1. 输出 PR 评论
        comment = generator.generate_github_comment(
            scan_results=list(result["results"].values()),
            ai_review=result.get("ai_review"),
            agent_reviews=result.get("agent_reviews"),
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

        # 2. 写入 Actions Summary
        _write_actions_summary(result, generator, repo, console)

        # 3. 输出 PR Annotations（行级评论）
        _output_annotations(result, console)

        # 4. 设置 Actions 输出变量
        _set_actions_outputs(result)

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
    use_agents: bool,
    changed_files: list[str] | None,
    settings: Settings,
    console: Console,
) -> dict[str, Any]:
    """运行分析."""
    from consistency.core.metrics import MetricsCollector

    metrics = MetricsCollector()
    metrics.start_scan()

    if changed_files:
        metrics.record_files_scanned(len(changed_files), changed_only=True)

    orchestrator = ScannerOrchestrator(settings)

    report = await orchestrator.scan(path, skip_security=skip_security, files=changed_files)

    # 记录扫描器指标
    for scanner_name, scan_result in report.results.items():
        metrics.record_scanner_used(scanner_name, report.duration_ms / len(report.results))
        if scan_result.errors:
            for _ in scan_result.errors:
                metrics.record_scanner_error()

    # 记录问题统计
    all_findings = []
    for scan_result in report.results.values():
        all_findings.extend(scan_result.findings)

    severity_counts: dict[str, int] = {}
    for f in all_findings:
        severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1

    metrics.record_issues_found(
        critical=severity_counts.get("critical", 0),
        high=severity_counts.get("high", 0),
        medium=severity_counts.get("medium", 0),
        low=severity_counts.get("low", 0),
        info=severity_counts.get("info", 0),
    )

    ai_review = None
    agent_reviews = None

    # 多 Agent 审查（优先使用）
    if use_agents and not skip_ai:
        from consistency.agents import ReviewSupervisor
        from consistency.core.gitnexus_client import GitNexusClient

        import time

        agent_start = time.perf_counter()
        console.print("[blue]🤖 启用多 Agent 智能审查...[/blue]")

        # 初始化 GitNexus
        gitnexus = None
        if GitNexusClient.is_available():
            gitnexus = GitNexusClient()
            console.print("[green]✓[/green] GitNexus 代码知识图谱已启用")
        else:
            console.print("[yellow]! GitNexus 未安装，跳过代码上下文分析[/yellow]")

        # 创建 Supervisor 并运行多 Agent 审查
        supervisor = ReviewSupervisor(
            gitnexus_client=gitnexus,
            quick_mode=False,  # CI 中使用完整模式
        )

        # 对发现的文件进行 Agent 审查
        files_to_review = list(set(str(f.file_path) for f in all_findings if f.file_path))

        if files_to_review:
            console.print(f"[blue]🔍 Agent 正在审查 {len(files_to_review)} 个文件...[/blue]")

            agent_results: list[ReviewResult] = []
            for file_path_str in files_to_review[:10]:  # 最多审查 10 个文件
                file_path = Path(file_path_str)
                if file_path.exists():
                    try:
                        result = await supervisor.review(file_path, file_path.read_text(encoding="utf-8"))
                        agent_results.append(result)
                    except Exception as e:
                        console.print(f"[yellow]! 审查 {file_path.name} 失败: {e}[/yellow]")

            agent_reviews = agent_results

            # 记录 Agent 指标
            agent_duration_ms = (time.perf_counter() - agent_start) * 1000
            agent_names = list(set(r.metadata.get("agent", "unknown") for r in agent_results)) if agent_results else []
            metrics.record_agents_used(agent_names, agent_duration_ms)

            # 汇总 Agent 审查结果作为 AI Review
            if agent_results:
                from consistency.reviewer.models import ReviewResult, Severity

                all_comments = []
                summaries = []
                for ar in agent_results:
                    all_comments.extend(ar.comments)
                    summaries.append(ar.summary)

                # 确定最高严重级别
                max_severity = Severity.LOW
                for ar in agent_results:
                    if ar.severity.value == "CRITICAL":
                        max_severity = Severity.CRITICAL
                    elif ar.severity.value == "HIGH" and max_severity.value != "CRITICAL":
                        max_severity = Severity.HIGH
                    elif ar.severity.value == "MEDIUM" and max_severity.value in ("LOW", "INFO"):
                        max_severity = Severity.MEDIUM

                ai_review = ReviewResult(
                    summary=f"多 Agent 审查完成。审查了 {len(agent_results)} 个文件，发现 {len(all_comments)} 个问题。",
                    severity=max_severity,
                    comments=all_comments[:20],  # 最多 20 条评论
                    action_items=[
                        f"{c.file}:{c.line} - {c.message}"
                        for c in all_comments
                        if c.severity.value in ("HIGH", "CRITICAL")
                    ][:5],
                )

                console.print(f"[green]✓[/green] Agent 审查完成: 发现 {len(all_comments)} 个问题")

    # 回退到传统 AI 审查
    elif not skip_ai and settings.is_litellm_configured:
        import time

        ai_start = time.perf_counter()
        from consistency.reviewer import AIReviewer, ReviewContext

        reviewer = AIReviewer()

        context = ReviewContext(
            diff="",
            files_changed=[str(f.file_path) for f in all_findings if f.file_path],
            security_findings=[{"severity": f.severity.value, "message": f.message} for f in all_findings[:20]],
        )

        ai_review = await reviewer.review(context)

        # 记录 AI 审查指标
        ai_duration_ms = (time.perf_counter() - ai_start) * 1000
        metrics.record_ai_review(
            duration_ms=ai_duration_ms,
            tokens_used=0,  # TODO: 从 LiteLLM 获取实际 token 使用量
            model=str(settings.litellm_model) if settings else "",
        )

    # 完成度量收集
    final_metrics = metrics.finalize()

    return {
        "results": report.results,
        "duration_ms": report.duration_ms,
        "ai_review": ai_review,
        "agent_reviews": agent_reviews,
        "errors": report.errors,
        "commit_sha": get_git_commit_sha(path),
        "metrics": final_metrics,
    }


def _print_summary(result: dict[str, Any], console: Console) -> None:
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
    for scan_r in result["results"].values():
        all_findings.extend(scan_r.findings)

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


def _write_actions_summary(
    result: dict[str, Any],
    generator: ReportGenerator,
    repo: str,
    console: Console,
) -> None:
    """写入 GitHub Actions Job Summary。"""
    try:
        from consistency.core.metrics import format_metrics_for_summary
        from consistency.github import write_actions_summary

        # 1. 写入扫描摘要
        summary = generator.generate_actions_summary(
            scan_results=list(result["results"].values()),
            duration_ms=result.get("duration_ms", 0),
            ai_review=result.get("ai_review"),
            project_name=repo.split("/")[-1],
        )
        write_actions_summary(summary)

        # 2. 写入性能度量
        metrics = result.get("metrics")
        if metrics:
            metrics_summary = format_metrics_for_summary(metrics)
            write_actions_summary(metrics_summary)

        console.print("[dim]✓ Actions Summary 已写入[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠ Actions Summary 写入失败: {e}[/yellow]")


def _output_annotations(result: dict[str, Any], console: Console) -> None:
    """输出 PR Annotations（行级评论）。"""
    try:
        from consistency.github import write_annotations_from_findings
        from consistency.scanners.base import Finding

        all_findings: list[Finding] = []
        for scan_result in result["results"].values():
            all_findings.extend(scan_result.findings)

        if not all_findings:
            return

        # 只输出中高严重级别的问题
        important_findings = [f for f in all_findings if f.severity.value in ("CRITICAL", "HIGH", "MEDIUM")]

        if important_findings:
            count = write_annotations_from_findings(
                important_findings,
                max_errors=10,
                max_warnings=10,
            )
            console.print(f"[dim]✓ 已输出 {count} 个 PR Annotations[/dim]")
    except Exception as e:
        console.print(f"[yellow]⚠ PR Annotations 输出失败: {e}[/yellow]")


def _set_actions_outputs(result: dict[str, Any]) -> None:
    """设置 GitHub Actions 输出变量。"""
    try:
        from consistency.core.metrics import format_metrics_for_github_output
        from consistency.github import set_actions_output

        metrics = result.get("metrics")
        if metrics:
            outputs = format_metrics_for_github_output(metrics)
            for name, value in outputs.items():
                set_actions_output(name, value)

        # 设置额外的扫描结果输出
        all_findings = []
        for scan_result in result["results"].values():
            all_findings.extend(scan_result.findings)

        has_critical = any(f.severity.value == "critical" for f in all_findings)
        has_high = any(f.severity.value == "high" for f in all_findings)

        set_actions_output("has_critical", str(has_critical).lower())
        set_actions_output("has_high", str(has_high).lower())
        set_actions_output("should_block", str(has_critical).lower())

    except Exception:
        # 输出变量失败不应该影响主流程
        pass


def _get_changed_files(base: str, console: Console) -> list[str] | None:
    """获取相对于 base 分支的变更文件列表."""
    import subprocess

    try:
        # 获取当前分支与 base 的差异文件
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        # 只保留 Python 文件
        python_files = [f for f in files if f.endswith(".py")]

        if not python_files:
            console.print("[yellow]⚠ 没有检测到 Python 文件变更[/yellow]")
            return None

        return python_files
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]⚠ 获取变更文件失败: {e}[/yellow]")
        return None
    except Exception as e:
        console.print(f"[yellow]⚠ 获取变更文件时出错: {e}[/yellow]")
        return None
