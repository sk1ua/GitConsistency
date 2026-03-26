"""报告生成器.

基于 LLM 的智能报告生成，所有报告内容均由 AI 生成，不再是硬编码模板。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from consistency.report.formatters.sarif import SARIFFormatter
from consistency.report.llm_generator import LLMReportGenerator
from consistency.report.templates import ReportFormat, ReportTheme
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import Finding, ScanResult, Severity

logger = logging.getLogger(__name__)

# 报告生成常量
MAX_CHECKS_FINDINGS_DISPLAY = 30  # Checks API 输出中最多显示的发现数量
MAX_MESSAGE_LENGTH_DISPLAY = 80  # 消息显示的最大长度


class ReportGenerator:
    """LLM 驱动的报告生成器.

    所有报告内容由 LLM 生成，提供自然语言、上下文感知的分析报告。

    Examples:
        >>> generator = ReportGenerator()
        >>> report = await generator.generate(
        ...     scan_results=[security_result, drift_result],
        ...     project_name="My Project",
        ... )
        >>> Path("report.md").write_text(report)
    """

    def __init__(self, theme: ReportTheme | None = None) -> None:
        """初始化报告生成器.

        Args:
            theme: 报告主题配置（保留用于兼容性）
        """
        self.theme = theme or ReportTheme()
        self._llm_generator = LLMReportGenerator()

    async def generate(
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
            ai_review: AI 审查结果（可选，将合并到报告中）
            project_name: 项目名称
            format: 输出格式
            **kwargs: 额外参数
                - commit_sha: 提交 SHA
                - duration: 扫描耗时

        Returns:
            报告内容（字符串或字典）

        Raises:
            ValueError: 如果格式不受支持
        """
        # 验证格式
        if format not in (ReportFormat.MARKDOWN, ReportFormat.HTML, ReportFormat.JSON, ReportFormat.SARIF):
            raise ValueError(f"不支持的格式: {format}")

        # 如果有 ai_review，合并到 scan_results
        all_results = list(scan_results)
        if ai_review and ai_review.comments:
            # 将 AI review 转换为 ScanResult
            ai_findings = self._convert_ai_review_to_findings(ai_review)
            all_results.append(
                ScanResult(
                    scanner_name="AI Review",
                    findings=ai_findings,
                    scanned_files=0,
                )
            )

        commit_sha = kwargs.get("commit_sha", "unknown")
        duration = kwargs.get("duration", 0.0)

        if format == ReportFormat.JSON:
            return self._generate_json(all_results, project_name, commit_sha, duration)

        if format == ReportFormat.SARIF:
            formatter = SARIFFormatter()
            return formatter.generate(
                scan_results=all_results,
                ai_review=ai_review,
                project_name=project_name,
                commit_sha=commit_sha,
                repository_uri=kwargs.get("repository_uri", ""),
            )

        if format == ReportFormat.HTML:
            markdown = await self._llm_generator.generate(
                scan_results=all_results,
                project_name=project_name,
                commit_sha=commit_sha,
                duration=duration,
            )
            return self._markdown_to_html(markdown)

        # Markdown 格式
        return await self._llm_generator.generate(
            scan_results=all_results,
            project_name=project_name,
            commit_sha=commit_sha,
            duration=duration,
        )

    async def generate_github_comment(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None = None,
        agent_reviews: list[ReviewResult] | None = None,
        project_name: str = "Unknown",
        max_length: int = 65536,
        commit_sha: str = "HEAD",
        duration: float = 0.0,
    ) -> str:
        """生成 GitHub PR 评论.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果（已弃用，直接传入 agent_reviews）
            agent_reviews: 多 Agent 审查结果列表
            project_name: 项目名称
            max_length: 最大长度限制
            commit_sha: 提交 SHA
            duration: 扫描耗时

        Returns:
            评论内容
        """
        # 合并所有结果
        all_results = list(scan_results)

        if agent_reviews:
            for review in agent_reviews:
                findings = self._convert_ai_review_to_findings(review)
                all_results.append(
                    ScanResult(
                        scanner_name=review.metadata.get("agent_name", "AI Agent"),
                        findings=findings,
                        scanned_files=0,
                    )
                )

        return await self._llm_generator.generate_github_comment(
            scan_results=all_results,
            project_name=project_name,
            commit_sha=commit_sha,
            duration=duration,
            max_length=max_length,
        )

    async def generate_actions_summary(
        self,
        scan_results: list[ScanResult],
        duration_ms: float,
        ai_review: ReviewResult | None = None,
        project_name: str = "Unknown",
    ) -> str:
        """生成 GitHub Actions Job Summary.

        Args:
            scan_results: 扫描结果列表
            duration_ms: 扫描耗时（毫秒）
            ai_review: AI 审查结果（可选）
            project_name: 项目名称

        Returns:
            Markdown 摘要内容
        """
        all_results = list(scan_results)
        if ai_review and ai_review.comments:
            findings = self._convert_ai_review_to_findings(ai_review)
            all_results.append(
                ScanResult(
                    scanner_name="AI Review",
                    findings=findings,
                    scanned_files=0,
                )
            )

        return await self._llm_generator.generate_actions_summary(
            scan_results=all_results,
            project_name=project_name,
            duration_ms=duration_ms,
        )

    def generate_github_annotations(
        self,
        scan_results: list[ScanResult],
        max_annotations: int = 50,
    ) -> list[dict[str, Any]]:
        """生成 GitHub PR Annotations（行级评论）.

        此功能不需要 LLM，直接基于扫描结果生成。

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

            annotation: dict[str, Any] = {
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

        此功能使用模板生成，不依赖 LLM。

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
            for finding in all_findings[:MAX_CHECKS_FINDINGS_DISPLAY]:  # Checks 输出限制数量
                emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}.get(
                    finding.severity.value, "⚪"
                )
                location = f"`{finding.file_path}:{finding.line}`" if finding.file_path else ""
                message_display = finding.message[:MAX_MESSAGE_LENGTH_DISPLAY]
                summary_lines.append(f"{emoji} **{finding.severity.value}** [{finding.rule_id}] {message_display}")
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

    def _convert_ai_review_to_findings(self, review: ReviewResult) -> list[Finding]:
        """将 AI Review 转换为 Finding 列表."""
        # 类型映射： reviewer.models.Severity -> scanners.base.Severity
        severity_map = {
            "info": Severity.INFO,
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }

        findings = []
        for comment in review.comments:
            base_severity = severity_map.get(comment.severity.value, Severity.LOW)
            findings.append(
                Finding(
                    rule_id=comment.category.value,
                    message=comment.message,
                    severity=base_severity,
                    file_path=Path(comment.file) if comment.file else None,
                    line=comment.line,
                    confidence=comment.confidence,
                    code_snippet=None,
                    metadata={"suggestion": comment.suggestion} if comment.suggestion else {},
                )
            )
        return findings

    def _generate_json(
        self,
        scan_results: list[ScanResult],
        project_name: str,
        commit_sha: str,
        duration: float,
    ) -> dict[str, Any]:
        """生成 JSON 格式报告."""
        all_findings: list[Finding] = []
        for result in scan_results:
            all_findings.extend(result.findings)

        severity_counts: dict[Severity, int] = dict.fromkeys(Severity, 0)
        for finding in all_findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

        return {
            "version": "2.0.0",
            "project_name": project_name,
            "scan_date": "",  # Could be added if needed
            "commit_sha": commit_sha,
            "duration_seconds": duration,
            "summary": {
                "total_issues": len(all_findings),
                "severity_counts": {sev.value.lower(): count for sev, count in severity_counts.items()},
            },
            "scanners": [
                {
                    "name": result.scanner_name,
                    "findings_count": len(result.findings),
                    "findings": [
                        {
                            "rule_id": f.rule_id,
                            "message": f.message,
                            "severity": f.severity.value,
                            "file": str(f.file_path) if f.file_path else None,
                            "line": f.line,
                        }
                        for f in result.findings
                    ],
                    "errors": result.errors,
                }
                for result in scan_results
            ],
        }

    def _markdown_to_html(self, markdown: str) -> str:
        """将 Markdown 转换为 HTML（简化版）."""
        html = markdown
        # 基本转换
        html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # 代码块
        html = html.replace("```python", '<pre><code class="language-python">')
        html = html.replace("```", "</code></pre>")
        # 行内代码
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
        # 标题
        for i in range(6, 0, -1):
            pattern = "^" + "#" * i + " (.+)$"
            replacement = "<h" + str(i) + ">\\1</h" + str(i) + ">"
            html = re.sub(pattern, replacement, html, flags=re.MULTILINE)
        # 粗体
        html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
        # 斜体
        html = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html)
        # 列表
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        # 段落
        html = re.sub(r"\n\n", "</p><p>", html)
        # 包裹
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>GitConsistency Code Health Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        pre {{ background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        code {{
            background: #f1f2f6;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
        }}
        li {{ margin: 5px 0; }}
        .severity-critical {{ color: #e74c3c; }}
        .severity-high {{ color: #e67e22; }}
        .severity-medium {{ color: #f39c12; }}
        .severity-low {{ color: #27ae60; }}
        .severity-info {{ color: #3498db; }}
    </style>
</head>
<body>
    <p>{html}</p>
</body>
</html>"""
        return html

    def _severity_to_annotation_level(self, severity: Severity) -> str:
        """转换严重级别到 GitHub annotation level."""
        mapping = {
            Severity.CRITICAL: "failure",
            Severity.HIGH: "failure",
            Severity.MEDIUM: "warning",
            Severity.LOW: "notice",
            Severity.INFO: "notice",
        }
        return mapping.get(severity, "notice")

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
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(report, dict):
            output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            output_path.write_text(report, encoding="utf-8")

        return output_path

    async def generate_sync(
        self,
        scan_results: list[ScanResult],
        **kwargs: Any,
    ) -> str | dict[str, Any]:
        """同步方式生成报告（方便调用）."""
        return await self.generate(scan_results, **kwargs)
