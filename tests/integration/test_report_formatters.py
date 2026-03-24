"""Report Formatters 集成测试.

测试各种报告格式化器的集成。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from consistency.report.formatters.base import BaseFormatter
from consistency.report.formatters.html import HtmlFormatter
from consistency.report.formatters.json import JsonFormatter
from consistency.report.formatters.markdown import MarkdownFormatter
from consistency.report.generator import ReportGenerator
from consistency.report.templates import ReportFormat, ReportTheme
from consistency.reviewer.models import ReviewComment, ReviewResult
from consistency.reviewer.models import Severity as ReviewSeverity
from consistency.scanners.base import Finding, ScanResult, Severity


class TestBaseFormatter:
    """Base Formatter 测试."""

    def test_base_formatter_abstract(self) -> None:
        """测试 BaseFormatter 是抽象类."""

        class TestFormatter(BaseFormatter):
            def generate(self, scan_results, ai_review, project_name, **kwargs):
                return "test report"

        formatter = TestFormatter()
        assert isinstance(formatter.theme, ReportTheme)

    def test_formatter_with_custom_theme(self) -> None:
        """测试自定义主题."""

        class TestFormatter(BaseFormatter):
            def generate(self, scan_results, ai_review, project_name, **kwargs):
                return "test"

        theme = ReportTheme(primary_color="#ff0000")
        formatter = TestFormatter(theme=theme)
        assert formatter.theme.primary_color == "#ff0000"


class TestMarkdownFormatterIntegration:
    """Markdown Formatter 集成测试."""

    @pytest.fixture
    def formatter(self) -> MarkdownFormatter:
        """创建 Markdown Formatter."""
        return MarkdownFormatter()

    def test_generate_empty_report(self, formatter: MarkdownFormatter) -> None:
        """测试生成空报告."""
        report = formatter.generate(
            scan_results=[],
            ai_review=None,
            project_name="test-project",
            duration=1.5,
        )

        assert "# " in report
        assert "GitConsistency" in report
        assert "test-project" in report
        assert "1.50s" in report or "1.5s" in report

    def test_generate_with_findings(self, formatter: MarkdownFormatter) -> None:
        """测试生成带发现的报告."""
        scan_result = ScanResult(
            scanner_name="Bandit",
            findings=[
                Finding(
                    rule_id="B101",
                    message="Security issue",
                    severity=Severity.HIGH,
                    file_path=Path("test.py"),
                    line=10,
                ),
            ],
        )

        report = formatter.generate(
            scan_results=[scan_result],
            ai_review=None,
            project_name="test-project",
            duration=2.0,
        )

        assert "Security issue" in report
        assert "test.py" in report

    def test_generate_with_ai_review(self, formatter: MarkdownFormatter) -> None:
        """测试生成带 AI 审查的报告."""
        ai_review = ReviewResult(
            summary="AI found some issues",
            severity=ReviewSeverity.MEDIUM,
            comments=[
                ReviewComment(
                    file="main.py",
                    line=5,
                    message="Consider refactoring",
                    severity=ReviewSeverity.MEDIUM,
                    suggestion="Use list comprehension",
                ),
            ],
        )

        report = formatter.generate(
            scan_results=[],
            ai_review=ai_review,
            project_name="test-project",
            duration=1.0,
        )

        assert "AI" in report or "AI Code Review" in report
        assert "AI found some issues" in report
        assert "Consider refactoring" in report
        assert "list comprehension" in report


class TestHtmlFormatterIntegration:
    """HTML Formatter 集成测试."""

    @pytest.fixture
    def formatter(self) -> HtmlFormatter:
        """创建 HTML Formatter."""
        return HtmlFormatter()

    def test_generate_empty_report(self, formatter: HtmlFormatter) -> None:
        """测试生成空报告."""
        report = formatter.generate(
            scan_results=[],
            ai_review=None,
            project_name="test-project",
            duration=1.5,
        )

        assert "<!DOCTYPE html>" in report or "<html" in report
        assert "GitConsistency" in report
        assert "test-project" in report

    def test_generate_with_findings(self, formatter: HtmlFormatter) -> None:
        """测试生成带发现的报告."""
        scan_result = ScanResult(
            scanner_name="Bandit",
            findings=[
                Finding(
                    rule_id="B101",
                    message="Security issue",
                    severity=Severity.HIGH,
                    file_path=Path("test.py"),
                    line=10,
                ),
            ],
        )

        report = formatter.generate(
            scan_results=[scan_result],
            ai_review=None,
            project_name="test-project",
            duration=1.0,
        )

        assert "Security issue" in report
        assert "test.py" in report

    def test_custom_theme(self) -> None:
        """测试自定义主题."""
        theme = ReportTheme(primary_color="#ff0000")
        formatter = HtmlFormatter(theme=theme)
        report = formatter.generate(
            scan_results=[],
            ai_review=None,
            project_name="test",
        )

        assert isinstance(report, str)
        assert len(report) > 0


class TestJsonFormatterIntegration:
    """JSON Formatter 集成测试."""

    @pytest.fixture
    def formatter(self) -> JsonFormatter:
        """创建 JSON Formatter."""
        return JsonFormatter()

    def test_generate_empty_report(self, formatter: JsonFormatter) -> None:
        """测试生成空报告."""
        report = formatter.generate(
            scan_results=[],
            ai_review=None,
            project_name="test-project",
            duration_ms=1500,
        )

        assert isinstance(report, dict)
        assert report["project_name"] == "test-project"
        assert "summary" in report
        assert report["summary"]["duration_ms"] == 1500
        assert "scanners" in report

    def test_generate_with_findings(self, formatter: JsonFormatter) -> None:
        """测试生成带发现的报告."""
        scan_result = ScanResult(
            scanner_name="Bandit",
            findings=[
                Finding(
                    rule_id="B101",
                    message="Security issue",
                    severity=Severity.HIGH,
                    file_path=Path("test.py"),
                    line=10,
                ),
            ],
        )

        report = formatter.generate(
            scan_results=[scan_result],
            ai_review=None,
            project_name="test-project",
        )

        assert len(report["scanners"]) == 1
        assert report["scanners"][0]["finding_count"] == 1
        assert report["scanners"][0]["findings"][0]["message"] == "Security issue"

    def test_generate_with_ai_review(self, formatter: JsonFormatter) -> None:
        """测试生成带 AI 审查的报告."""
        ai_review = ReviewResult(
            summary="AI review",
            severity=ReviewSeverity.LOW,
            comments=[
                ReviewComment(
                    file="main.py",
                    line=1,
                    message="Test comment",
                    severity=ReviewSeverity.LOW,
                ),
            ],
        )

        report = formatter.generate(
            scan_results=[],
            ai_review=ai_review,
            project_name="test",
        )

        assert report["ai_review"]["summary"] == "AI review"
        assert report["ai_review"]["comment_count"] == 1


class TestReportGeneratorIntegration:
    """Report Generator 集成测试."""

    @pytest.fixture
    def generator(self) -> ReportGenerator:
        """创建 Report Generator."""
        return ReportGenerator()

    def test_generator_initialization(self, generator: ReportGenerator) -> None:
        """测试生成器初始化."""
        assert isinstance(generator.theme, ReportTheme)
        # 检查格式器是否存在
        assert ReportFormat.MARKDOWN in generator._formatters
        assert ReportFormat.HTML in generator._formatters
        assert ReportFormat.JSON in generator._formatters

    def test_generate_markdown(self, generator: ReportGenerator) -> None:
        """测试生成 Markdown 报告."""
        report = generator.generate(
            scan_results=[],
            ai_review=None,
            project_name="test",
            format=ReportFormat.MARKDOWN,
        )

        assert isinstance(report, str)
        assert "# " in report

    def test_generate_html(self, generator: ReportGenerator) -> None:
        """测试生成 HTML 报告."""
        report = generator.generate(
            scan_results=[],
            ai_review=None,
            project_name="test",
            format=ReportFormat.HTML,
        )

        assert isinstance(report, str)
        assert "<" in report

    def test_generate_json(self, generator: ReportGenerator) -> None:
        """测试生成 JSON 报告."""
        report = generator.generate(
            scan_results=[],
            ai_review=None,
            project_name="test",
            format=ReportFormat.JSON,
        )

        assert isinstance(report, dict)
        assert report["project_name"] == "test"

    def test_generate_github_comment(self, generator: ReportGenerator) -> None:
        """测试生成 GitHub 评论."""
        comment = generator.generate_github_comment(
            scan_results=[],
            ai_review=None,
            project_name="test-project",
        )

        assert isinstance(comment, str)
        assert "GitConsistency" in comment
        assert "test-project" in comment

    def test_invalid_format(self, generator: ReportGenerator) -> None:
        """测试无效格式."""
        with pytest.raises(ValueError, match="不支持的格式"):
            generator.generate(
                scan_results=[],
                ai_review=None,
                project_name="test",
                format="invalid",  # type: ignore
            )


class TestFindingDataClass:
    """Finding 数据类测试."""

    def test_finding_creation(self) -> None:
        """测试创建 Finding."""
        finding = Finding(
            rule_id="B101",
            message="Test message",
            severity=Severity.HIGH,
            file_path=Path("test.py"),
            line=10,
            column=5,
        )

        assert finding.rule_id == "B101"
        assert finding.message == "Test message"
        assert finding.severity == Severity.HIGH
        assert finding.file_path == Path("test.py")
        assert finding.line == 10
        assert finding.column == 5

    def test_finding_defaults(self) -> None:
        """测试 Finding 默认值."""
        finding = Finding(
            rule_id="B101",
            message="Test",
            severity=Severity.LOW,
        )

        assert finding.file_path is None
        assert finding.line is None
        assert finding.column is None
        assert finding.confidence == 1.0
        assert finding.metadata == {}


class TestScanResult:
    """ScanResult 数据类测试."""

    def test_scan_result_summary(self) -> None:
        """测试 ScanResult 摘要."""
        result = ScanResult(
            scanner_name="TestScanner",
            findings=[
                Finding(rule_id="R1", message="High", severity=Severity.HIGH),
                Finding(rule_id="R2", message="Low", severity=Severity.LOW),
                Finding(rule_id="R3", message="Medium", severity=Severity.MEDIUM),
            ],
        )

        summary = result.summary
        assert summary["high"] == 1
        assert summary["low"] == 1
        assert summary["medium"] == 1
        assert summary["critical"] == 0

    def test_scan_result_empty(self) -> None:
        """测试空的 ScanResult."""
        result = ScanResult(scanner_name="Test")

        assert result.findings == []
        assert result.summary == {"info": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
