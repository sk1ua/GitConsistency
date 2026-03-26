"""CLI 欢迎横幅工具."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.text import Text

# 使用 stderr 以避免与标准输出冲突
console = Console(stderr=True)


def print_banner() -> None:
    """打印欢迎横幅."""
    # 检测 Windows 环境，避免 Unicode 问题
    is_windows = sys.platform == "win32"

    banner = Text()
    banner.append("+-------------------------------------------+\n", style="cyan")
    banner.append("|   ", style="cyan")
    if is_windows:
        banner.append("GitConsistency", style="bold cyan")
        banner.append("                      |\n", style="cyan")
        banner.append("|   ", style="cyan")
        banner.append("Code Security Scan & AI Review", style="dim")
    else:
        banner.append("GitConsistency", style="bold cyan")
        banner.append("                   |\n", style="cyan")
        banner.append("|   ", style="cyan")
        banner.append("代码安全扫描与 AI 审查", style="dim")
    banner.append("           |\n", style="cyan")
    banner.append("+-------------------------------------------+")
    console.print(banner)
    console.print()
