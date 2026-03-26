"""scan 子命令实现."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Windows 编码修复
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if TYPE_CHECKING:
    import typer
    from rich.console import Console


def register_scan_commands(scan_app: typer.Typer, console: Console) -> None:
    """注册 scan 子命令."""

    @scan_app.command(name="security")
    def scan_security(
        path: Path = Path("."),
        rules: list[str] | None = None,
        fmt: str = "console",
        output: Path | None = None,
    ) -> None:
        """运行安全扫描（Semgrep + Bandit）.

        Args:
            path: 扫描路径
            rules: 自定义 Semgrep 规则
            fmt: 输出格式 (console, sarif)
            output: 输出文件路径（仅 sarif 格式）
        """
        console.print(f"[blue]扫描:[/blue] {path}")

        async def run() -> None:
            from consistency.scanners.security_scanner import SecurityScanner

            scanner = SecurityScanner(semgrep_rules=rules)
            result = await scanner.scan(path)

            # SARIF 格式输出
            if fmt.lower() == "sarif":
                from consistency.report.formatters.sarif import SARIFFormatter

                formatter = SARIFFormatter()
                sarif_report = formatter.generate(
                    scan_results=[result],
                    ai_review=None,
                    project_name=path.name or "project",
                )

                if output:
                    formatter.save(sarif_report, output)
                    console.print(f"[green]SARIF 报告已保存:[/green] {output}")
                else:
                    import json

                    console.print(json.dumps(sarif_report, indent=2))
                return

            # Console 格式输出
            console.print(f"扫描文件: {result.scanned_files}")
            console.print(f"发现问题: {len(result.findings)}")

            if result.errors:
                console.print("[red]扫描错误：[/red]")
                for err in result.errors:
                    console.print(f"  [red]- {err}[/red]")

            for finding in result.findings:
                console.print(f"  [{finding.severity.value}] {finding.rule_id}: {finding.message[:80]}")

        asyncio.run(run())
