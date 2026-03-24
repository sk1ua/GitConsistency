"""扫描命令.

提供独立的安全扫描功能（Semgrep + Bandit）.

Examples:
    >>> from consistency.commands.scan import ScanCommand
    >>> cmd = ScanCommand()
    >>> await cmd.scan_security(Path("./my-project"))
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from consistency.scanners.security_scanner import SecurityScanner

console = Console()


class ScanCommand:
    """扫描命令处理器.

    运行安全扫描（Semgrep + Bandit），独立于 AI 审查功能.

    Attributes:
        semgrep_rules: Semgrep 规则集
    """

    def __init__(
        self,
        semgrep_rules: list[str] | None = None,
    ) -> None:
        """初始化扫描命令.

        Args:
            semgrep_rules: Semgrep 规则集
        """
        self.semgrep_rules = semgrep_rules

    async def scan_security(
        self,
        path: Path,
        rules: list[str] | None = None,
    ) -> dict[str, Any]:
        """运行安全扫描.

        Args:
            path: 扫描路径
            rules: 临时指定的规则集（覆盖默认）

        Returns:
            扫描结果
        """
        console.print(f"[blue]🔒 安全扫描:[/blue] {path}")

        scanner = SecurityScanner(semgrep_rules=rules or self.semgrep_rules)
        result = await scanner.scan(path)

        console.print(f"扫描文件: {result.scanned_files}")
        console.print(f"发现问题: {len(result.findings)}")

        if result.errors:
            console.print("[red]扫描错误：[/red]")
            for err in result.errors:
                console.print(f"  [red]- {err}[/red]")

        for finding in result.findings:
            console.print(
                f"  [{finding.severity.value}] {finding.rule_id}: {finding.message[:80]}"
            )

        return {
            "success": len(result.errors) == 0,
            "scanned_files": result.scanned_files,
            "findings_count": len(result.findings),
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "message": f.message,
                    "severity": f.severity.value,
                    "file": str(f.file_path),
                    "line": f.line,
                }
                for f in result.findings
            ],
            "errors": result.errors,
        }
