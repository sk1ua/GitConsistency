"""配置命令.

提供配置查看和验证功能.

Examples:
    >>> from consistency.commands.config import ConfigCommand
    >>> cmd = ConfigCommand()
    >>> cmd.show_config()
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from consistency.config import get_settings

console = Console()


class ConfigCommand:
    """配置命令处理器.

    查看和验证 GitConsistency 配置.
    """

    def show_config(self) -> dict[str, Any]:
        """显示当前配置.

        Returns:
            配置信息
        """
        settings = get_settings()

        table = Table(title="当前配置")
        table.add_column("配置项", style="cyan")
        table.add_column("值")

        for key, value in settings.model_dump().items():
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
                value = "***" if value else "未设置"
            table.add_row(key, str(value))

        console.print(table)

        return {
            "success": True,
            "config": settings.model_dump(),
        }

    def validate_config(self) -> dict[str, Any]:
        """验证配置有效性.

        Returns:
            验证结果
        """
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

        return {
            "success": True,
            "checks": {name: {"configured": ok, "description": desc} for name, ok, desc in checks},
        }
