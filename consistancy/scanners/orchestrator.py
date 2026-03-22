"""扫描器协调器.

并行执行安全扫描，统一结果输出.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from consistancy.config import Settings
from consistancy.scanners.base import Finding, ScanResult
from consistancy.scanners.security_scanner import SecurityScanner

logger = logging.getLogger(__name__)


@dataclass
class ScanReport:
    """统一扫描报告."""

    target_path: str
    results: dict[str, ScanResult] = field(default_factory=dict)
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def all_findings(self) -> list[Finding]:
        """获取所有发现的问题."""
        findings: list[Finding] = []
        for result in self.results.values():
            findings.extend(result.findings)
        return findings

    @property
    def summary(self) -> dict[str, Any]:
        """获取汇总信息."""
        severity_counts: dict[str, int] = {}
        scanner_counts: dict[str, int] = {}
        total_findings = 0

        for scanner_name, result in self.results.items():
            count = len(result.findings)
            scanner_counts[scanner_name] = count
            total_findings += count

            for finding in result.findings:
                sev = finding.severity.value
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "total_findings": total_findings,
            "severity_counts": severity_counts,
            "scanner_counts": scanner_counts,
        }


class ScannerOrchestrator:
    """扫描器协调器.

    管理安全扫描器的执行和结果汇总.

    Examples:
        >>> orchestrator = ScannerOrchestrator(settings)
        >>> report = await orchestrator.scan(Path("./my-project"))
        >>> print(f"发现 {report.summary['total_findings']} 个问题")
    """

    def __init__(
        self,
        settings: Settings | None = None,
        gitnexus_client: Any | None = None,
    ) -> None:
        """初始化协调器.

        Args:
            settings: 配置设置
            gitnexus_client: GitNexus MCP 客户端（可选）
        """
        self.settings = settings
        self.gitnexus_client = gitnexus_client
        self._security_scanner: SecurityScanner | None = None

    def _get_security_scanner(self) -> SecurityScanner:
        """获取或创建安全扫描器."""
        if self._security_scanner is None:
            if self.settings:
                self._security_scanner = SecurityScanner(
                    semgrep_rules=self.settings.semgrep_rules,
                    bandit_severity=self.settings.bandit_severity,
                    use_gitnexus=self.settings.is_gitnexus_configured,
                    gitnexus_client=self.gitnexus_client,
                )
            else:
                self._security_scanner = SecurityScanner()
        return self._security_scanner

    async def scan(
        self,
        path: Path,
        skip_security: bool = False,
    ) -> ScanReport:
        """执行扫描.

        Args:
            path: 扫描目标路径
            skip_security: 是否跳过安全扫描

        Returns:
            统一扫描报告
        """
        start_time = time.perf_counter()
        results: dict[str, ScanResult] = {}
        errors: list[str] = []

        # 执行安全扫描
        if not skip_security:
            try:
                scanner = self._get_security_scanner()
                result = await scanner.scan(path)
                results["security"] = result
            except Exception as e:
                logger.error(f"安全扫描失败: {e}")
                errors.append(f"security: {e}")

        duration_ms = (time.perf_counter() - start_time) * 1000

        return ScanReport(
            target_path=str(path),
            results=results,
            duration_ms=duration_ms,
            errors=errors,
        )
