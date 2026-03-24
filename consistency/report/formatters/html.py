"""HTML 报告格式化器."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from consistency.report.formatters.base import BaseFormatter
from consistency.report.templates import HTMLTemplates
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import ScanResult


class HtmlFormatter(BaseFormatter):
    """HTML 报告格式化器."""

    def __init__(self, **kwargs: Any) -> None:
        """初始化 HTML 格式化器."""
        super().__init__(**kwargs)
        self.html = HTMLTemplates()

    def generate(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None,
        project_name: str,
        **kwargs: Any,
    ) -> str:
        """生成 HTML 报告."""
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
                table = self._generate_scanner_table(result)
                content_parts.append(table)

        content = "\n".join(content_parts)

        # 完整页面
        return self.html.FULL_PAGE.format(
            project_name=project_name,
            css=self.html.CSS,
            content=content,
        )

    def _generate_scanner_table(self, result: ScanResult) -> str:
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
