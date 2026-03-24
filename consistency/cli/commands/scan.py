"""scan 子命令实现."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer
    from rich.console import Console


def register_scan_commands(scan_app: typer.Typer, console: Console) -> None:
    """注册 scan 子命令."""

    @scan_app.command(name="security")
    def scan_security(
        path: Path = Path("."),
        rules: list[str] | None = None,
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
