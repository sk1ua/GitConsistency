"""GitConsistency CLI 入口.

使用 Typer 构建的现代化命令行界面，支持 Rich 富文本输出.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from consistency import __version__
from consistency.cli.commands.analyze import register_analyze_command
from consistency.cli.commands.ci import register_ci_command
from consistency.cli.commands.config_cmd import register_config_commands
from consistency.cli.commands.init import register_init_command
from consistency.cli.commands.review import register_review_commands
from consistency.cli.commands.scan import register_scan_commands
from consistency.config import get_settings

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


def register_all_commands() -> None:
    """注册所有 CLI 命令."""
    register_analyze_command(app, console)
    register_ci_command(app, console)
    register_init_command(app, console)
    register_scan_commands(scan_app, console)
    register_config_commands(config_app, console)
    register_review_commands(review_app, console)


register_all_commands()

if __name__ == "__main__":
    app()
