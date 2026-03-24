"""review 子命令实现."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer
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
        from consistency.commands import ReviewCommand

        async def run() -> None:
            cmd = ReviewCommand(quick_mode=quick)
            result = await cmd.review_file(path, show_code=show_code)

            if not result.get("success"):
                raise Exception("Exit 1")

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
        from consistency.commands import ReviewCommand

        async def run() -> None:
            cmd = ReviewCommand(quick_mode=quick)
            result = await cmd.review_diff(path, target=target, cached=cached)

            if not result.get("success"):
                raise Exception("Exit 1")

            # 有关键问题时返回非零状态码
            if result.get("issues_count", 0) > 0 and not quick:
                console.print("\n[yellow]⚠ 发现潜在问题，请检查[/yellow]")

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
        from consistency.commands import ReviewCommand

        async def run() -> None:
            cmd = ReviewCommand(quick_mode=quick, max_workers=5)
            result = await cmd.review_batch(paths)

            if not result.get("success"):
                raise Exception("Exit 1")

        asyncio.run(run())
