"""报告生成器.

生成漂亮的 Markdown、HTML、JSON 等格式的分析报告.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from consistency import __version__
from consistency.report.templates import (
    HTMLTemplates,
    MarkdownTemplates,
    ReportFormat,
    ReportTheme,
)
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import Finding, ScanResult, Severity

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报告生成器.

    生成多种格式的代码健康分析报告，支持自定义模板和主题.

    Examples:
        >>> generator = ReportGenerator(theme=ReportTheme())
        >>> report = generator.generate_markdown(
        ...     scan_results=[security_result, drift_result],
        ...     ai_review=ai_result,
        ...     title="My Project Analysis",
        ... )
        >>> Path("report.md").write_text(report)
    """

    def __init__(
        self,
        theme: ReportTheme | None = None,
        version: str | None = None,
    ) -> None:
        """初始化报告生成器.

        Args:
            theme: 报告主题配置
            version: GitConsistency 版本号
        """
        self.theme = theme or ReportTheme()
        self.version = version or __version__
        self.md = MarkdownTemplates()
        self.html = HTMLTemplates()

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
        if format == ReportFormat.MARKDOWN:
            return self.generate_markdown(scan_results, ai_review, project_name, **kwargs)
        elif format == ReportFormat.HTML:
            return self.generate_html(scan_results, ai_review, project_name, **kwargs)
        elif format == ReportFormat.JSON:
            return self.generate_json(scan_results, ai_review, project_name, **kwargs)
        else:
            raise ValueError(f"不支持的格式: {format}")

    def generate_markdown(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
        commit_sha: str = "unknown",
        duration: float = 0.0,
        include_details: bool = True,
    ) -> str:
        """生成 Markdown 报告.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果
            project_name: 项目名称
            commit_sha: Git commit SHA
            duration: 扫描耗时（秒）
            include_details: 是否包含详细信息

        Returns:
            Markdown 格式报告
        """
        parts: list[str] = []

        # 计算统计
        all_findings = self._collect_findings(scan_results)
        severity_counts = self._count_by_severity(all_findings)

        # 头部
        header = self.md.HEADER.format(
            project_name=project_name,
            scan_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration=duration,
            commit_sha=commit_sha[:8] if commit_sha else "unknown",
            summary=self._generate_summary_text(severity_counts, all_findings),
            critical_count=severity_counts.get(Severity.CRITICAL, 0),
            high_count=severity_counts.get(Severity.HIGH, 0),
            medium_count=severity_counts.get(Severity.MEDIUM, 0),
            low_count=severity_counts.get(Severity.LOW, 0),
            info_count=severity_counts.get(Severity.INFO, 0),
            total_issues=len(all_findings),
            icon_critical=self.theme.icon_danger,
            icon_high=self.theme.icon_danger,
            icon_medium=self.theme.icon_warning,
            icon_low=self.theme.icon_success,
            icon_info=self.theme.icon_info,
        )
        parts.append(header)

        # 扫描器结果
        for result in scan_results:
            section = self._generate_scanner_section(result, include_details)
            parts.append(section)

        # AI 审查结果
        if ai_review:
            ai_section = self._generate_ai_section(ai_review, include_details)
            parts.append(ai_section)

        # 页脚
        footer = self.md.FOOTER.format(version=self.version)
        parts.append(footer)

        return "\n".join(parts)

    def generate_html(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
        **kwargs: Any,
    ) -> str:
        """生成 HTML 报告.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果
            project_name: 项目名称
            **kwargs: 额外参数

        Returns:
            HTML 格式报告
        """
        all_findings = self._collect_findings(scan_results)
        severity_counts = self._count_by_severity(all_findings)

        # 构建内容
        content_parts: list[str] = []

        # 头部
        worst_severity = self._get_worst_severity(severity_counts)
        header = self.html.HEADER.format(
            project_name=project_name,
            scan_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration=kwargs.get("duration", 0.0),
            summary=self._generate_summary_text(severity_counts, all_findings),
            total_issues=len(all_findings),
            worst_severity=worst_severity.value,
        )
        content_parts.append(header)

        # 扫描器结果表格
        for result in scan_results:
            if result.findings:
                table = self._generate_html_scanner_table(result)
                content_parts.append(table)

        content = "\n".join(content_parts)

        # 完整页面
        return self.html.FULL_PAGE.format(
            project_name=project_name,
            css=self.html.CSS,
            content=content,
        )

    def generate_json(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成 JSON 报告.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果
            project_name: 项目名称
            **kwargs: 额外参数

        Returns:
            JSON 格式报告（字典）
        """
        all_findings = self._collect_findings(scan_results)
        severity_counts = self._count_by_severity(all_findings)

        report = {
            "version": self.version,
            "scan_date": datetime.now().isoformat(),
            "project_name": project_name,
            "summary": {
                "total_issues": len(all_findings),
                "severity_counts": {k.value: v for k, v in severity_counts.items()},
                "duration_ms": kwargs.get("duration_ms", 0),
            },
            "scanners": [
                {
                    "name": r.scanner_name,
                    "scanned_files": r.scanned_files,
                    "finding_count": len(r.findings),
                    "error_count": len(r.errors),
                    "findings": [
                        {
                            "rule_id": f.rule_id,
                            "severity": f.severity.value,
                            "file": str(f.file_path) if f.file_path else None,
                            "line": f.line,
                            "message": f.message,
                            "confidence": f.confidence,
                        }
                        for f in r.findings
                    ],
                }
                for r in scan_results
            ],
        }

        if ai_review:
            report["ai_review"] = {
                "summary": ai_review.summary,
                "severity": ai_review.severity.value,
                "comment_count": len(ai_review.comments),
                "critical_count": ai_review.critical_count,
                "high_count": ai_review.high_count,
                "has_blocking_issues": ai_review.has_blocking_issues,
                "comments": [
                    {
                        "file": c.file,
                        "line": c.line,
                        "message": c.message,
                        "suggestion": c.suggestion,
                        "severity": c.severity.value,
                        "category": c.category.value,
                        "confidence": c.confidence,
                    }
                    for c in ai_review.comments
                ],
                "action_items": ai_review.action_items,
            }

        return report

    def generate_github_comment(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
        max_length: int = 65536,
    ) -> str:
        """生成 GitHub PR 评论.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果
            project_name: 项目名称
            max_length: 最大长度限制

        Returns:
            评论内容
        """
        all_findings = self._collect_findings(scan_results)
        severity_counts = self._count_by_severity(all_findings)

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

        # 添加关键问题
        critical_and_high = [f for f in all_findings if f.severity in (Severity.CRITICAL, Severity.HIGH)][
            :10
        ]  # 最多显示 10 个

        if critical_and_high:
            lines.append("### 🚨 Critical Issues")
            lines.append("")
            for finding in critical_and_high:
                location = f"`{finding.file_path}:{finding.line}`" if finding.file_path else ""
                lines.append(f"- **{finding.severity.value.upper()}** [{finding.rule_id}] {finding.message[:100]}")
                if location:
                    lines.append(f"  - {location}")
            lines.append("")

        # 添加 AI 审查摘要
        if ai_review:
            lines.append("### 🤖 AI Review")
            lines.append(f"{ai_review.summary[:200]}...")
            lines.append("")

            if ai_review.has_blocking_issues:
                lines.append("⚠️ **Blocking issues detected. Please address before merging.**")
                lines.append("")

        # 添加签名
        lines.append("---")
        lines.append(f"*Report generated by GitConsistency v{self.version}*")

        comment = "\n".join(lines)

        # 截断如果超过限制
        if len(comment) > max_length:
            comment = comment[: max_length - 100] + "\n\n... (truncated)"

        return comment

    def _collect_findings(self, scan_results: list[ScanResult]) -> list[Finding]:
        """收集所有发现."""
        findings: list[Finding] = []
        for result in scan_results:
            findings.extend(result.findings)
        return findings

    def _count_by_severity(self, findings: list[Finding]) -> dict[Severity, int]:
        """按严重程度统计."""
        counts: dict[Severity, int] = {s: 0 for s in Severity}
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
        else:
            return "🎉 No issues found! Code looks great."

    def _generate_scanner_section(
        self,
        result: ScanResult,
        include_details: bool,
    ) -> str:
        """生成扫描器部分."""
        status = "✅ Passed" if not result.findings else f"⚠️ {len(result.findings)} issues"

        if not include_details or not result.findings:
            return self.md.SCANNER_SECTION.format(
                scanner_name=result.scanner_name.upper(),
                status=status,
                scanned_files=result.scanned_files,
                issue_count=len(result.findings),
                findings_table="",
            )

        # 生成表格
        rows = []
        for finding in result.findings[:50]:  # 限制行数
            row = self.md.TABLE_ROW.format(
                severity=finding.severity.value.upper(),
                file=finding.file_path.name if finding.file_path else "-",
                line=finding.line or "-",
                rule=finding.rule_id,
                message=finding.message[:80] + "..." if len(finding.message) > 80 else finding.message,
            )
            rows.append(row)

        table = self.md.FINDINGS_TABLE.format(rows="\n".join(rows))

        return self.md.SCANNER_SECTION.format(
            scanner_name=result.scanner_name.upper(),
            status=status,
            scanned_files=result.scanned_files,
            issue_count=len(result.findings),
            findings_table=table,
        )

    def _generate_ai_section(
        self,
        ai_review: ReviewResult,
        include_details: bool,
    ) -> str:
        """生成 AI 审查部分."""
        # 清理 summary，移除 JSON 标记和多余空白
        summary = self._clean_text_for_markdown(ai_review.summary)

        if not include_details:
            return self.md.AI_REVIEW_SECTION.format(
                summary=summary,
                severity=ai_review.severity.value.upper(),
                comments="",
                action_items="",
            )

        # 生成评论
        comment_lines = []
        for comment in ai_review.comments[:20]:  # 限制数量
            if comment.file and comment.line:
                location = f"{comment.file}:{comment.line}"
            else:
                location = comment.file or "general"
            suggestion = f"\n**💡 Suggestion**: {comment.suggestion}" if comment.suggestion else ""

            comment_text = self.md.AI_COMMENT.format(
                category=comment.category.value.upper(),
                severity=comment.severity.value.upper(),
                location=location,
                message=self._clean_text_for_markdown(comment.message),
                suggestion=suggestion,
            )
            comment_lines.append(comment_text)

        # 行动项
        action_lines = [f"- [ ] {item}" for item in ai_review.action_items[:10]]

        return self.md.AI_REVIEW_SECTION.format(
            summary=summary,
            severity=ai_review.severity.value.upper(),
            comments="\n".join(comment_lines) if comment_lines else "_No comments_",
            action_items="\n".join(action_lines) if action_lines else "_No action items_",
        )

    def _clean_text_for_markdown(self, text: str) -> str:
        """清理文本，使其适合 Markdown 格式.

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return ""

        # 移除 JSON 代码块标记
        import re

        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)

        # 将多行合并为单行（用于 summary 等简短文本）
        lines = text.split("\n")
        lines = [line.strip() for line in lines if line.strip()]

        # 如果是单行，直接返回
        if len(lines) <= 1:
            return lines[0] if lines else ""

        # 如果是多行，检查是否看起来像 JSON
        joined = " ".join(lines)
        if joined.startswith("{") and joined.endswith("}"):
            # 尝试提取其中的 summary 字段
            try:
                data = json.loads(joined)
                if isinstance(data, dict) and "summary" in data:
                    return str(data["summary"])
            except json.JSONDecodeError:
                pass

        # 返回前3行，用空格连接（避免 Markdown 格式混乱）
        return " ".join(lines[:3])

    def _generate_html_scanner_table(self, result: ScanResult) -> str:
        """生成 HTML 扫描器表格."""
        headers = ["Severity", "File", "Line", "Rule", "Message"]
        header_html = "".join(self.html.TABLE_HEADER.format(text=h) for h in headers)

        rows = []
        for finding in result.findings[:30]:
            cells = [
                f'<span class="severity-{finding.severity.value}">{finding.severity.value.upper()}</span>',
                f"<code>{finding.file_path.name if finding.file_path else '-'}</code>",
                str(finding.line or "-"),
                f"<code>{finding.rule_id}</code>",
                finding.message[:100],
            ]
            row_html = "".join(self.html.TABLE_CELL.format(text=c) for c in cells)
            rows.append(self.html.TABLE_ROW.format(cells=row_html))

        return self.html.TABLE.format(
            title=f"{result.scanner_name.upper()} ({len(result.findings)} issues)",
            headers=header_html,
            rows="\n".join(rows),
        )

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
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == ReportFormat.JSON:
            if isinstance(report, dict):
                output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            else:
                output_path.write_text(str(report), encoding="utf-8")
        else:
            output_path.write_text(str(report), encoding="utf-8")

        logger.info(f"报告已保存: {output_path}")
        return output_path
