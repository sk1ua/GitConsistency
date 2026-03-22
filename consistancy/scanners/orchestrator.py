"""扫描器协调器.

并行执行安全扫描，统一结果输出.
"""

from __future__ import annotations

import asyncio
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

    管理多个扫描器的并行执行和结果汇总.

    Examples:
        >>> orchestrator = ScannerOrchestrator(settings)
        >>> orchestrator.create_default_scanners()
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
        self._scanners: dict[str, Any] = {}

    def register_scanner(self, name: str, scanner: Any) -> None:
        """注册扫描器.

        Args:
            name: 扫描器名称
            scanner: 扫描器实例
        """
        self._scanners[name] = scanner
        logger.debug(f"注册扫描器: {name}")

    def create_default_scanners(self) -> None:
        """创建默认扫描器集合（仅安全扫描器）."""
        if self.settings:
            security = SecurityScanner(
                semgrep_rules=self.settings.semgrep_rules,
                bandit_severity=self.settings.bandit_severity,
                use_gitnexus=self.settings.is_gitnexus_configured,
                gitnexus_client=self.gitnexus_client,
            )
            self.register_scanner("security", security)
        else:
            self.register_scanner("security", SecurityScanner())

    def get_scanner_info(self) -> dict[str, dict[str, Any]]:
        """获取扫描器信息.

        Returns:
            扫描器信息字典
        """
        info: dict[str, dict[str, Any]] = {}
        for name, scanner in self._scanners.items():
            info[name] = {
                "name": getattr(scanner, "name", name),
                "config": getattr(scanner, "config", {}),
            }
        return info

    async def scan(
        self,
        path: Path,
        scanners: list[str] | None = None,
        skip_scanners: list[str] | None = None,
        skip_security: bool = False,
    ) -> ScanReport:
        """执行扫描.

        Args:
            path: 扫描目标路径
            scanners: 指定扫描器列表（None 表示全部）
            skip_scanners: 跳过的扫描器列表
            skip_security: 是否跳过安全扫描（兼容参数）

        Returns:
            统一扫描报告
        """
        start_time = time.perf_counter()
        results: dict[str, ScanResult] = {}
        errors: list[str] = []

        # 确定要运行的扫描器
        if scanners is not None:
            scanner_names = [name for name in scanners if name in self._scanners]
        else:
            scanner_names = list(self._scanners.keys())

        # 应用跳过列表
        if skip_scanners:
            scanner_names = [name for name in scanner_names if name not in skip_scanners]

        # 如果没有注册扫描器且没有跳过安全扫描，使用默认安全扫描
        if not scanner_names and not skip_security:
            try:
                scanner = self._get_security_scanner()
                result = await scanner.scan(path)
                results["security"] = result
            except Exception as e:
                logger.error(f"安全扫描失败: {e}")
                errors.append(f"security: {e}")
        else:
            # 并行运行所有扫描器
            tasks = []
            for name in scanner_names:
                scanner = self._scanners[name]
                tasks.append(self._run_scanner(name, scanner, path))

            if tasks:
                scan_results = await asyncio.gather(*tasks, return_exceptions=True)

                for name, result in zip(scanner_names, scan_results):
                    if isinstance(result, Exception):
                        logger.error(f"扫描器 {name} 失败: {result}")
                        errors.append(f"{name}: {result}")
                    elif isinstance(result, ScanResult):
                        results[name] = result

        duration_ms = (time.perf_counter() - start_time) * 1000

        return ScanReport(
            target_path=str(path),
            results=results,
            duration_ms=duration_ms,
            errors=errors,
        )

    async def _run_scanner(
        self,
        name: str,
        scanner: Any,
        path: Path,
    ) -> ScanResult | Exception:
        """运行单个扫描器.

        Args:
            name: 扫描器名称
            scanner: 扫描器实例
            path: 扫描路径

        Returns:
            扫描结果或异常
        """
        try:
            return await scanner.scan(path)
        except Exception as e:
            return e

    def _get_security_scanner(self) -> SecurityScanner:
        """获取或创建安全扫描器."""
        if "security" in self._scanners:
            scanner = self._scanners["security"]
            if isinstance(scanner, SecurityScanner):
                return scanner

        if self.settings:
            return SecurityScanner(
                semgrep_rules=self.settings.semgrep_rules,
                bandit_severity=self.settings.bandit_severity,
                use_gitnexus=self.settings.is_gitnexus_configured,
                gitnexus_client=self.gitnexus_client,
            )
        return SecurityScanner()
