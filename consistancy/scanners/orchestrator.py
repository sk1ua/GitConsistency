"""扫描器协调器.

并行执行多个扫描器，统一结果输出.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from consistancy.config import Settings
from consistancy.scanners.base import Finding, ScanResult
from consistancy.scanners.drift_detector import DriftDetector
from consistancy.scanners.hotspot_analyzer import HotspotAnalyzer
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
            gitnexus_client: GitNexus MCP 客户端
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
        """创建默认扫描器集合."""
        if self.settings:
            # 安全扫描器
            security = SecurityScanner(
                semgrep_rules=self.settings.semgrep_rules,
                bandit_severity=self.settings.bandit_severity,
                use_gitnexus=self.settings.is_gitnexus_configured,
                gitnexus_client=self.gitnexus_client,
            )
            self.register_scanner("security", security)

            # 漂移检测器
            drift = DriftDetector(
                threshold=self.settings.drift_threshold,
                zscore_threshold=self.settings.drift_zscore_threshold,
                gitnexus_client=self.gitnexus_client,
            )
            self.register_scanner("drift", drift)

            # 热点分析器
            hotspot = HotspotAnalyzer(
                complexity_threshold=self.settings.hotspot_complexity_threshold,
                lookback_days=self.settings.hotspot_lookback_days,
            )
            self.register_scanner("hotspot", hotspot)
        else:
            # 使用默认配置
            self.register_scanner("security", SecurityScanner())
            self.register_scanner("drift", DriftDetector())
            self.register_scanner("hotspot", HotspotAnalyzer())

    async def scan(
        self,
        path: Path,
        scanners: list[str] | None = None,
        skip_scanners: list[str] | None = None,
    ) -> ScanReport:
        """执行扫描.

        Args:
            path: 扫描目标路径
            scanners: 指定扫描器列表（None 表示全部）
            skip_scanners: 跳过的扫描器列表

        Returns:
            统一扫描报告
        """
        import time

        start_time = time.perf_counter()
        report = ScanReport(target_path=str(path))

        # 如果没有注册扫描器，创建默认的
        if not self._scanners:
            self.create_default_scanners()

        # 确定要运行的扫描器
        to_run = list(self._scanners.keys())
        if scanners:
            to_run = [s for s in to_run if s in scanners]
        if skip_scanners:
            to_run = [s for s in to_run if s not in skip_scanners]

        logger.info(f"开始扫描: {path}, 扫描器: {to_run}")

        # 并行执行扫描
        tasks = []
        for name in to_run:
            scanner = self._scanners[name]
            task = asyncio.create_task(
                self._run_scanner(scanner, path, name),
                name=f"scan_{name}",
            )
            tasks.append((name, task))

        # 收集结果
        for name, task in tasks:
            try:
                result = await task
                report.results[name] = result
                logger.info(f"扫描器 {name} 完成: {len(result.findings)} 个问题")
            except Exception as e:
                logger.error(f"扫描器 {name} 失败: {e}")
                report.errors.append(f"{name}: {e}")

        report.duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"扫描完成: {len(report.all_findings)} 个问题, {report.duration_ms:.0f}ms")

        return report

    async def _run_scanner(
        self,
        scanner: Any,
        path: Path,
        name: str,
    ) -> ScanResult:
        """运行单个扫描器."""
        logger.debug(f"启动扫描器: {name}")
        result: ScanResult = await scanner.scan(path)
        return result

    def get_scanner_info(self) -> dict[str, dict[str, Any]]:
        """获取扫描器信息."""
        info = {}
        for name, scanner in self._scanners.items():
            info[name] = {
                "name": scanner.name,
                "config": getattr(scanner, "config", {}),
            }
        return info
