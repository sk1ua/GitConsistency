"""review 子命令实现.

注意：当前 review 命令使用 Agent 方式进行代码审查。
GitNexus 为可选依赖，不可用时自动降级为基础模式。
"""

from __future__ import annotations

import asyncio
import os
import subprocess
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
            # GitNexus 可选检查
            gitnexus = None
            try:
                if GitNexusClient.is_available():
                    gitnexus = GitNexusClient()
                else:
                    console.print("[yellow]⚠ GitNexus 不可用，使用基础模式[/yellow]")
            except Exception:
                console.print("[yellow]⚠ GitNexus 连接失败，使用基础模式[/yellow]")

            from consistency.agents import ReviewSupervisor

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
        async def run() -> None:
            # 1. 获取 git diff
            diff_cmd = ["git", "diff"]
            if cached:
                diff_cmd.append("--cached")
            if target:
                diff_cmd.append(target)

            try:
                # 确定工作目录（如果是文件则使用其父目录）
                cwd = path if path.is_dir() else path.parent
                # 设置环境变量避免编码问题
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"

                result = subprocess.run(
                    diff_cmd,
                    capture_output=True,
                    text=False,  # 以字节方式读取
                    cwd=str(cwd),
                    check=True,
                    shell=False,
                    env=env,
                )
                # 手动解码，使用 UTF-8 并忽略错误
                diff_text = result.stdout.decode("utf-8", errors="ignore")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]✗ 获取 git diff 失败: {e}[/red]")
                raise typer.Exit(1)
            except FileNotFoundError:
                console.print("[red]✗ 未找到 git 命令[/red]")
                raise typer.Exit(1)

            if not diff_text.strip():
                console.print("[yellow]⚠ 没有检测到变更[/yellow]")
                return

            console.print(f"[blue]📝 审查 {path} 的变更...[/blue]")

            # 2. 解析 diff
            from consistency.tools.diff_tools import DiffParser

            parser = DiffParser()
            file_diffs = parser.parse(diff_text)

            if not file_diffs:
                console.print("[yellow]⚠ 未能解析 diff 内容[/yellow]")
                return

            console.print(f"检测到 {len(file_diffs)} 个文件变更")

            # 3. GitNexus 可选检查
            from consistency.core.gitnexus_client import GitNexusClient

            gitnexus = None
            try:
                if GitNexusClient.is_available():
                    gitnexus = GitNexusClient()
                else:
                    console.print("[yellow]⚠ GitNexus 不可用，使用基础模式[/yellow]")
            except Exception:
                console.print("[yellow]⚠ GitNexus 连接失败，使用基础模式[/yellow]")

            # 4. 审查每个变更文件
            from consistency.agents import ReviewSupervisor

            supervisor = ReviewSupervisor(gitnexus_client=gitnexus, quick_mode=quick)

            total_issues = 0
            for file_diff in file_diffs:
                if file_diff.is_deleted:
                    continue

                # 提取变更的代码
                changed_code = "\n".join(
                    content for _, content in [
                        line for hunk in file_diff.hunks for line in hunk.added_lines
                    ]
                )

                if not changed_code:
                    continue

                file_path = path / file_diff.new_path
                if not file_path.exists():
                    continue

                try:
                    review_result = await supervisor.review(file_path, changed_code)

                    if review_result.comments:
                        console.print(f"\n[{file_diff.new_path}]: [red]{len(review_result.comments)} 个问题[/red]")
                        for comment in review_result.comments:
                            console.print(f"  - [{comment.severity.value}] {comment.message}")
                        total_issues += len(review_result.comments)
                    else:
                        console.print(f"[{file_diff.new_path}]: [green]✓ 通过[/green]")

                except Exception as e:
                    console.print(f"\n[{file_diff.new_path}]: [red]✗ 审查失败: {e}[/red]")

            # 5. 汇总结果
            if total_issues > 0:
                console.print(f"\n[red]共发现 {total_issues} 个问题[/red]")
                raise typer.Exit(1)
            else:
                console.print("\n[green]✓ 所有变更审查通过[/green]")

        asyncio.run(run())

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
            # GitNexus 可选检查
            gitnexus = None
            try:
                if GitNexusClient.is_available():
                    gitnexus = GitNexusClient()
                else:
                    console.print("[yellow]⚠ GitNexus 不可用，使用基础模式[/yellow]")
            except Exception:
                console.print("[yellow]⚠ GitNexus 连接失败，使用基础模式[/yellow]")

            from consistency.agents import ReviewSupervisor

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
                        console.print("[path.name]: [green]✓ 通过[/green]")
                except Exception as e:
                    console.print(f"\n[path.name]: [red]✗ 审查失败: {e}[/red]")

            if all_issues > 0:
                console.print(f"\n[red]共发现 {all_issues} 个问题[/red]")
                raise typer.Exit(1)
            else:
                console.print("\n[green]✓ 所有文件审查通过[/green]")

        asyncio.run(run())
