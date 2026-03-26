"""review 子命令实现.

注意：当前 review 命令使用 Agent 方式进行代码审查。
需要 GitNexus 支持。如果 GitNexus 不可用，这些命令将返回降级提示。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from rich.console import Console


def register_review_commands(review_app: typer.Typer, console: Console) -> None:
    """注册 review 子命令."""

    @review_app.command(name="file")
    def review_file_command(
        path: Path,
        quick: bool = False,
        show_code: bool = False,
    ) -> None:
        """审查单个文件.

        Examples:
            $ gitconsistency review file main.py
            $ gitconsistency review file main.py --quick
            $ gitconsistency review file main.py --show-code
        """
        from consistency.core.gitnexus_client import GitNexusClient

        async def run() -> None:
            # 检查 GitNexus 是否可用
            if not GitNexusClient.is_available():
                console.print("[yellow]⚠ GitNexus 未安装，review 命令需要 GitNexus 支持[/yellow]")
                console.print("[dim]请安装 GitNexus: npm install -g gitnexus[/dim]")
                raise typer.Exit(1)

            from consistency.agents import ReviewSupervisor

            gitnexus = GitNexusClient()
            supervisor = ReviewSupervisor(gitnexus_client=gitnexus, quick_mode=quick)

            try:
                result = await supervisor.review(path, path.read_text(encoding="utf-8"))

                # 显示结果
                if result.comments:
                    console.print(f"\n[red]发现 {len(result.comments)} 个问题:[/red]")
                    for comment in result.comments:
                        console.print(f"  - [{comment.severity.value}] {comment.message}")
                    raise typer.Exit(1)
                else:
                    console.print("\n[green]✓ 未发现明显问题[/green]")

            except Exception as e:
                console.print(f"\n[red]✗ 审查失败: {e}[/red]")
                raise typer.Exit(1)

        asyncio.run(run())

    @review_app.command(name="diff")
    def review_diff_command(
        path: Path = Path("."),
        target: str | None = None,
        cached: bool = False,
        quick: bool = False,
    ) -> None:
        """审查变更代码（git diff）.

        Examples:
            $ gitconsistency review diff
            $ gitconsistency review diff --cached
            $ gitconsistency review diff --target main
            $ gitconsistency review diff --quick
        """
        console.print("[yellow]⚠ review diff 命令暂未实现[/yellow]")
        console.print("[dim]请使用 'gitconsistency review file <path>' 审查单个文件[/dim]")
        raise typer.Exit(1)

    @review_app.command(name="batch")
    def review_batch_command(
        paths: list[Path],
        quick: bool = False,
    ) -> None:
        """批量审查多个文件.

        Examples:
            $ gitconsistency review batch main.py utils.py
            $ gitconsistency review batch *.py --quick
        """
        from consistency.core.gitnexus_client import GitNexusClient

        async def run() -> None:
            # 检查 GitNexus 是否可用
            if not GitNexusClient.is_available():
                console.print("[yellow]⚠ GitNexus 未安装，review 命令需要 GitNexus 支持[/yellow]")
                console.print("[dim]请安装 GitNexus: npm install -g gitnexus[/dim]")
                raise typer.Exit(1)

            from consistency.agents import ReviewSupervisor

            gitnexus = GitNexusClient()
            supervisor = ReviewSupervisor(gitnexus_client=gitnexus, quick_mode=quick)

            all_issues = 0
            for path in paths:
                if not path.exists():
                    console.print(f"[yellow]⚠ 文件不存在: {path}[/yellow]")
                    continue

                try:
                    result = await supervisor.review(path, path.read_text(encoding="utf-8"))
                    if result.comments:
                        console.print(f"\n[path.name]: [red]{len(result.comments)} 个问题[/red]")
                        for comment in result.comments:
                            console.print(f"  - [{comment.severity.value}] {comment.message}")
                        all_issues += len(result.comments)
                    else:
                        console.print(f"[path.name]: [green]✓ 通过[/green]")
                except Exception as e:
                    console.print(f"\n[path.name]: [red]✗ 审查失败: {e}[/red]")

            if all_issues > 0:
                console.print(f"\n[red]共发现 {all_issues} 个问题[/red]")
                raise typer.Exit(1)
            else:
                console.print("\n[green]✓ 所有文件审查通过[/green]")

        asyncio.run(run())
