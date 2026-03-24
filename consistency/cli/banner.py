"""CLI 欢迎横幅工具."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_banner() -> None:
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
