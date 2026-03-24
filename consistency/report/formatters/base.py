"""报告格式化器基类."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from consistency import __version__
from consistency.report.templates import ReportFormat, ReportTheme
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import Finding, ScanResult, Severity

logger = logging.getLogger(__name__)


class BaseFormatter(ABC):
    """报告格式化器基类."""

    def __init__(
        self,
        theme: ReportTheme | None = None,
        version: str | None = None,
    ) -> None:
        """初始化格式化器.

        Args:
            theme: 报告主题配置
            version: GitConsistency 版本号
        """
        self.theme = theme or ReportTheme()
        self.version = version or __version__

    @abstractmethod
    def generate(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None,
        project_name: str,
        **kwargs: Any,
    ) -> str | dict[str, Any]:
        """生成报告.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果（可选）
            project_name: 项目名称
            **kwargs: 额外参数

        Returns:
            报告内容
        """
        ...

    def save(
        self,
        report: str | dict[str, Any],
        output_path: Path,
    ) -> Path:
        """保存报告到文件.

        Args:
            report: 报告内容
            output_path: 输出路径

        Returns:
            实际保存的路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(report, dict):
            output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        else:
            output_path.write_text(str(report), encoding="utf-8")

        logger.info(f"报告已保存: {output_path}")
        return output_path

    def _collect_findings(self, scan_results: list[ScanResult]) -> list[Finding]:
        """收集所有发现."""
        findings: list[Finding] = []
        for result in scan_results:
            findings.extend(result.findings)
        return findings

    def _count_by_severity(self, findings: list[Finding]) -> dict[Severity, int]:
        """按严重程度统计."""
        counts: dict[Severity, int] = dict.fromkeys(Severity, 0)
        for finding in findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def _get_worst_severity(self, counts: dict[Severity, int]) -> Severity:
        """获取最严重的严重程度."""
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
            if counts.get(severity, 0) > 0:
                return severity
        return Severity.INFO

    def _get_status_emoji(self, counts: dict[Severity, int]) -> str:
        """获取状态图标."""
        if counts.get(Severity.CRITICAL, 0) > 0:
            return "❌ Critical issues found"
        elif counts.get(Severity.HIGH, 0) > 0:
            return "❌ Issues found"
        elif counts.get(Severity.MEDIUM, 0) > 0:
            return "⚠️ Warnings found"
        else:
            return "✅ All clear"

    def _generate_summary_text(
        self,
        severity_counts: dict[Severity, int],
        findings: list[Finding],
        scanner_error_count: int = 0,
    ) -> str:
        """生成摘要文本."""
        total = len(findings)
        critical = severity_counts.get(Severity.CRITICAL, 0)
        high = severity_counts.get(Severity.HIGH, 0)

        if critical > 0:
            return (
                f"🚨 Found **{total}** issues including **{critical}** critical "
                "vulnerabilities that require immediate attention."
            )
        elif high > 0:
            return (
                f"⚠️ Found **{total}** issues including **{high}** high severity "
                "problems. Review recommended before merging."
            )
        elif total > 0:
            return f"✅ Found **{total}** minor issues. Consider addressing them for code quality improvement."
        elif scanner_error_count > 0:
            return (
                "⚠️ Scan finished with errors. "
                f"**{scanner_error_count}** scanner error(s) occurred, so results may be incomplete."
            )
        else:
            return "🎉 No issues found! Code looks great."
