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

    def generate_github_annotations(
        self,
        scan_results: list[ScanResult],
        max_annotations: int = 50,
    ) -> list[dict[str, Any]]:
        """生成 GitHub PR Annotations（行级评论）.

        GitHub Actions 每个步骤支持最多 10 个警告注解和 10 个错误注解。

        Args:
            scan_results: 扫描结果列表
            max_annotations: 最大注解数量

        Returns:
            注解字典列表
        """
        annotations: list[dict[str, Any]] = []

        all_findings: list[Finding] = []
        for result in scan_results:
            all_findings.extend(result.findings)

        # 按严重级别排序（critical/high 优先）
        severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
        sorted_findings = sorted(all_findings, key=lambda f: severity_order.get(f.severity, 5))

        for finding in sorted_findings[:max_annotations]:
            if not finding.file_path:
                continue

            line = finding.line or 0
            if line <= 0:
                continue

            # 映射严重级别到 GitHub annotation level
            level = self._severity_to_annotation_level(finding.severity)

            annotation = {
                "path": str(finding.file_path),
                "start_line": finding.line,
                "end_line": finding.line,
                "annotation_level": level,
                "message": f"[{finding.rule_id}] {finding.message}",
                "title": finding.rule_id,
            }

            # 添加代码片段
            if finding.code_snippet:
                annotation["raw_details"] = finding.code_snippet[:500]

            annotations.append(annotation)

        return annotations

    def generate_checks_output(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
    ) -> dict[str, Any]:
        """生成 GitHub Checks API 输出格式.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果
            project_name: 项目名称

        Returns:
            Checks API 输出字典
        """
        all_findings: list[Finding] = []
        for result in scan_results:
            all_findings.extend(result.findings)

        severity_counts: dict[Severity, int] = dict.fromkeys(Severity, 0)
        for finding in all_findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

        # 构建摘要
        summary_lines = [
            f"## GitConsistency Security Scan - {project_name}",
            "",
            "### Summary",
            f"- **Critical**: {severity_counts.get(Severity.CRITICAL, 0)}",
            f"- **High**: {severity_counts.get(Severity.HIGH, 0)}",
            f"- **Medium**: {severity_counts.get(Severity.MEDIUM, 0)}",
            f"- **Low**: {severity_counts.get(Severity.LOW, 0)}",
            f"- **Info**: {severity_counts.get(Severity.INFO, 0)}",
            "",
        ]

        # 添加发现的问题详情
        if all_findings:
            summary_lines.append("### Findings")
            summary_lines.append("")
            for finding in all_findings[:30]:  # Checks 输出限制为 30 个
                emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}.get(
                    finding.severity.value, "⚪"
                )
                location = f"`{finding.file_path}:{finding.line}`" if finding.file_path else ""
                summary_lines.append(f"{emoji} **{finding.severity.value}** [{finding.rule_id}] {finding.message[:80]}")
                if location:
                    summary_lines.append(f"   Location: {location}")

        # 确定结论
        critical = severity_counts.get(Severity.CRITICAL, 0)
        high = severity_counts.get(Severity.HIGH, 0)

        if critical > 0:
            title = f"❌ {critical} critical issues found"
        elif high > 0:
            title = f"⚠️ {high} high severity issues found"
        else:
            title = "✅ No critical issues found"

        return {
            "title": title,
            "summary": "\n".join(summary_lines),
            "annotations": self.generate_github_annotations(scan_results),
        }

    def generate_actions_summary(
        self,
        scan_results: list[ScanResult],
        duration_ms: float,
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
    ) -> str:
        """生成 GitHub Actions Job Summary（用于 $GITHUB_STEP_SUMMARY）。

        Args:
            scan_results: 扫描结果列表
            duration_ms: 扫描耗时（毫秒）
            ai_review: AI 审查结果
            project_name: 项目名称

        Returns:
            Markdown 摘要内容
        """
        all_findings: list[Finding] = []
        for result in scan_results:
            all_findings.extend(result.findings)

        severity_counts: dict[Severity, int] = dict.fromkeys(Severity, 0)
        for finding in all_findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

        critical = severity_counts.get(Severity.CRITICAL, 0)
        high = severity_counts.get(Severity.HIGH, 0)
        medium = severity_counts.get(Severity.MEDIUM, 0)
        low = severity_counts.get(Severity.LOW, 0)

        # 确定整体状态
        if critical > 0:
            status_emoji = "❌"
            status_text = "Failed"
        elif high > 0:
            status_emoji = "⚠️"
            status_text = "Warning"
        else:
            status_emoji = "✅"
            status_text = "Passed"

        lines = [
            f"# {status_emoji} GitConsistency Code Review",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| **Project** | {project_name} |",
            f"| **Status** | {status_text} |",
            f"| **Duration** | {duration_ms:.0f}ms |",
            "",
            "## 📊 Results Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| 🔴 Critical | {critical} |",
            f"| 🟠 High | {high} |",
            f"| 🟡 Medium | {medium} |",
            f"| 🟢 Low | {low} |",
            f"| 🔵 Info | {severity_counts.get(Severity.INFO, 0)} |",
            "",
        ]

        # 添加发现的问题表格
        if all_findings:
            lines.extend([
                "## 🔍 Findings",
                "",
                "| File | Line | Severity | Rule | Message |",
                "|------|------|----------|------|---------|",
            ])

            for finding in all_findings[:20]:  # 摘要限制为 20 个
                file_str = str(finding.file_path) if finding.file_path else "-"
                line_val = finding.line or 0
                line_str = str(line_val) if line_val > 0 else "-"
                emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}.get(
                    finding.severity.value, "⚪"
                )
                msg = finding.message[:50] + "..." if len(finding.message) > 50 else finding.message
                lines.append(
                    f"| {file_str} | {line_str} | {emoji} {finding.severity.value} | "
                    f"{finding.rule_id} | {msg} |"
                )

            if len(all_findings) > 20:
                lines.append(f"\n*... and {len(all_findings) - 20} more findings*")

            lines.append("")

        # 添加 AI 审查部分
        if ai_review:
            lines.extend([
                "## 🤖 AI Review",
                "",
                ai_review.summary,
                "",
            ])

        return "\n".join(lines)

    def _severity_to_annotation_level(self, severity: Severity) -> str:
        """转换严重级别到 GitHub annotation level。"""
        mapping = {
            Severity.CRITICAL: "failure",
            Severity.HIGH: "failure",
            Severity.MEDIUM: "warning",
            Severity.LOW: "notice",
            Severity.INFO: "notice",
        }
        return mapping.get(severity, "notice")

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
