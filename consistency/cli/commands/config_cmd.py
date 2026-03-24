"""config 子命令实现."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from consistency.config import get_settings

if TYPE_CHECKING:
    import typer
    from rich.console import Console


def register_config_commands(config_app: "typer.Typer", console: "Console") -> None:
    """注册 config 子命令."""

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
