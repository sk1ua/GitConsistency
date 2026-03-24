"""Markdown 报告格式化器."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from consistency.report.formatters.base import BaseFormatter
from consistency.report.templates import MarkdownTemplates
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import ScanResult, Severity


class MarkdownFormatter(BaseFormatter):
    """Markdown 报告格式化器."""

    def __init__(self, **kwargs: Any) -> None:
        """初始化 Markdown 格式化器."""
        super().__init__(**kwargs)
        self.md = MarkdownTemplates()

    def generate(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None,
        project_name: str,
        **kwargs: Any,
    ) -> str:
        """生成 Markdown 报告."""
        parts: list[str] = []

        # 计算统计
        all_findings = self._collect_findings(scan_results)
        severity_counts = self._count_by_severity(all_findings)
        scanner_error_count = sum(len(result.errors) for result in scan_results)

        # 提取参数
        commit_sha = kwargs.get("commit_sha", "unknown")
        duration = kwargs.get("duration", 0.0)
        include_details = kwargs.get("include_details", True)

        # 头部
        header = self.md.HEADER.format(
            project_name=project_name,
            scan_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration=duration,
            commit_sha=commit_sha[:8] if commit_sha else "unknown",
            summary=self._generate_summary_text(severity_counts, all_findings, scanner_error_count),
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

    def _generate_scanner_section(
        self,
        result: ScanResult,
        include_details: bool,
    ) -> str:
        """生成扫描器部分."""
        if result.errors:
            status = f"❌ Failed ({len(result.errors)} errors)"
        elif result.findings:
            status = f"⚠️ {len(result.findings)} issues"
        else:
            status = "✅ Passed"

        errors_block = ""
        if result.errors:
            rows = [self.md.SCANNER_ERROR_ROW.format(error=error) for error in result.errors]
            errors_block = self.md.SCANNER_ERRORS.format(rows="\n".join(rows))

        if not include_details or not result.findings:
            return self.md.SCANNER_SECTION.format(
                scanner_name=result.scanner_name.upper(),
                status=status,
                scanned_files=result.scanned_files,
                issue_count=len(result.findings),
                errors_block=errors_block,
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
            errors_block=errors_block,
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
        """清理文本，使其适合 Markdown 格式."""
        if not text:
            return ""

        # 移除 JSON 代码块标记
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
