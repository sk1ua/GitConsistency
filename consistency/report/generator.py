"""报告生成器.

生成漂亮的 Markdown、HTML、JSON 等格式的分析报告.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from consistency.report.formatters import HtmlFormatter, JsonFormatter, MarkdownFormatter
from consistency.report.templates import ReportFormat, ReportTheme
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import Finding, ScanResult, Severity

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报告生成器.

    生成多种格式的代码健康分析报告，支持自定义模板和主题.

    Examples:
        >>> generator = ReportGenerator(theme=ReportTheme())
        >>> report = generator.generate(
        ...     scan_results=[security_result, drift_result],
        ...     ai_review=ai_result,
        ...     project_name="My Project",
        ...     format=ReportFormat.MARKDOWN,
        ... )
        >>> Path("report.md").write_text(report)
    """

    def __init__(
        self,
        theme: ReportTheme | None = None,
    ) -> None:
        """初始化报告生成器.

        Args:
            theme: 报告主题配置
        """
        self.theme = theme or ReportTheme()
        self._formatters = {
            ReportFormat.MARKDOWN: MarkdownFormatter(theme=self.theme),
            ReportFormat.HTML: HtmlFormatter(theme=self.theme),
            ReportFormat.JSON: JsonFormatter(theme=self.theme),
        }

    def generate(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
        format: ReportFormat = ReportFormat.MARKDOWN,
        **kwargs: Any,
    ) -> str | dict[str, Any]:
        """生成报告.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果（可选）
            project_name: 项目名称
            format: 输出格式
            **kwargs: 额外参数

        Returns:
            报告内容（字符串或字典）
        """
        formatter = self._formatters.get(format)
        if not formatter:
            raise ValueError(f"不支持的格式: {format}")

        return formatter.generate(
            scan_results=scan_results,
            ai_review=ai_review,
            project_name=project_name,
            **kwargs,
        )

    def generate_github_comment(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        agent_reviews: list[ReviewResult] | None = None,
        project_name: str = "Unknown",
        max_length: int = 65536,
    ) -> str:
        """生成 GitHub PR 评论.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果
            agent_reviews: 多 Agent 审查结果列表
            project_name: 项目名称
            max_length: 最大长度限制

        Returns:
            评论内容
        """
        from consistency import __version__

        # 收集统计数据
        all_findings: list[Finding] = []
        for result in scan_results:
            all_findings.extend(result.findings)

        severity_counts: dict[Severity, int] = dict.fromkeys(Severity, 0)
        for finding in all_findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

        lines = [
            f"## 🔍 GitConsistency Code Review - {project_name}",
            "",
            f"**Overall Status**: {self._get_status_emoji(severity_counts)}",
            "",
            "### Summary",
            f"- 🟢 Passed: {severity_counts.get(Severity.LOW, 0) + severity_counts.get(Severity.INFO, 0)}",
            f"- 🟡 Warnings: {severity_counts.get(Severity.MEDIUM, 0)}",
            f"- 🔴 Issues: {severity_counts.get(Severity.HIGH, 0) + severity_counts.get(Severity.CRITICAL, 0)}",
            "",
        ]

        # 添加多 Agent 审查结果
        if agent_reviews:
            lines.append("### 🤖 Multi-Agent Review")
            lines.append("")

            # 统计各 Agent 的结果
            total_agent_comments = sum(len(r.comments) for r in agent_reviews)
            lines.append("启用 **SecurityAgent**、**LogicAgent**、**StyleAgent** 并行审查")
            lines.append(f"- 审查文件数: {len(agent_reviews)}")
            lines.append(f"- Agent 发现问题: {total_agent_comments}")
            lines.append("")

            # 显示高严重级别的问题
            high_issues: list[tuple[ReviewResult, Any]] = []
            for r in agent_reviews:
                for c in r.comments:
                    if c.severity.value in ("HIGH", "CRITICAL"):
                        high_issues.append((r, c))

            if high_issues:
                lines.append("**Agent 发现的关键问题：**")
                for _, comment in high_issues[:5]:  # 最多 5 个
                    location = f"`{comment.file}:{comment.line}`" if comment.file and comment.line else ""
                    lines.append(f"- **{comment.severity.value}** [{comment.category.value}] {comment.message[:80]}")
                    if location:
                        lines.append(f"  - 📍 {location}")
                lines.append("")

        # 添加关键问题
        critical_and_high = [f for f in all_findings if f.severity in (Severity.CRITICAL, Severity.HIGH)][
            :10
        ]  # 最多显示 10 个

        if critical_and_high:
            lines.append("### 🚨 Security Scan Issues")
            lines.append("")
            for finding in critical_and_high:
                location = f"`{finding.file_path}:{finding.line}`" if finding.file_path else ""
                lines.append(f"- **{finding.severity.value.upper()}** [{finding.rule_id}] {finding.message[:100]}")
                if location:
                    lines.append(f"  - {location}")
            lines.append("")

        # 添加 AI 审查摘要
        if ai_review:
            lines.append("### 📝 AI Review Summary")
            lines.append(f"{ai_review.summary[:200]}...")
            lines.append("")

            if ai_review.has_blocking_issues:
                lines.append("⚠️ **Blocking issues detected. Please address before merging.**")
                lines.append("")

        # 添加签名
        lines.append("---")
        lines.append(f"*Report generated by GitConsistency v{__version__}*")

        comment = "\n".join(lines)

        # 截断如果超过限制
        if len(comment) > max_length:
            comment = comment[: max_length - 100] + "\n\n... (truncated)"

        return comment

    def save_report(
        self,
        report: str | dict[str, Any],
        output_path: Path,
        format: ReportFormat = ReportFormat.MARKDOWN,
    ) -> Path:
        """保存报告到文件.

        Args:
            report: 报告内容
            output_path: 输出路径
            format: 格式

        Returns:
            实际保存的路径
        """
        formatter = self._formatters.get(format)
        if not formatter:
            raise ValueError(f"不支持的格式: {format}")

        return formatter.save(report, output_path)

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
