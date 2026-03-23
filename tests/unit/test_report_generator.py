"""报告生成器单元测试."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from consistency.report.generator import ReportGenerator
from consistency.report.templates import ReportFormat, ReportTheme
from consistency.reviewer.models import CommentCategory, ReviewComment, ReviewResult
from consistency.scanners.base import Finding, ScanResult, Severity


class TestReportGeneratorInit:
    """初始化测试."""

    def test_default_init(self) -> None:
        """测试默认初始化."""
        generator = ReportGenerator()
        assert generator.theme is not None
        assert generator.version == "0.1.0"

    def test_custom_init(self) -> None:
        """测试自定义初始化."""
        theme = ReportTheme(primary_color="#ff0000")
        generator = ReportGenerator(theme=theme, version="1.0.0")
        assert generator.theme.primary_color == "#ff0000"
        assert generator.version == "1.0.0"


class TestGenerateMarkdown:
    """Markdown 生成测试."""

    @pytest.fixture
    def generator(self) -> ReportGenerator:
        return ReportGenerator()

    @pytest.fixture
    def sample_scan_result(self) -> ScanResult:
        return ScanResult(
            scanner_name="security",
            findings=[
                Finding(
                    rule_id="RULE-1",
                    message="Test security issue",
                    severity=Severity.HIGH,
                    file_path=Path("src/main.py"),
                    line=42,
                    confidence=0.9,
                ),
            ],
            scanned_files=10,
        )

    def test_generate_markdown_basic(self, generator: ReportGenerator, sample_scan_result: ScanResult) -> None:
        """测试基本 Markdown 生成."""
        report = generator.generate_markdown(
            scan_results=[sample_scan_result],
            project_name="Test Project",
        )

        assert "# 🔍 GitConsistency Code Health Report" in report
        assert "Test Project" in report
        assert "RULE-1" in report
        assert "Test security issue" in report

    def test_generate_markdown_with_ai_review(self, generator: ReportGenerator, sample_scan_result: ScanResult) -> None:
        """测试带 AI 审查的 Markdown."""
        ai_review = ReviewResult(
            summary="AI review summary",
            severity=Severity.MEDIUM,
            comments=[
                ReviewComment(
                    file="test.py",
                    line=10,
                    message="AI comment",
                    severity=Severity.HIGH,
                    category=CommentCategory.BUG,
                ),
            ],
        )

        report = generator.generate_markdown(
            scan_results=[sample_scan_result],
            ai_review=ai_review,
        )

        assert "## 🤖 AI Code Review" in report
        assert "AI review summary" in report
        assert "AI comment" in report

    def test_generate_markdown_summary(self, generator: ReportGenerator) -> None:
        """测试摘要生成."""
        result = ScanResult(
            scanner_name="test",
            findings=[
                Finding(rule_id="R1", message="Critical", severity=Severity.CRITICAL),
                Finding(rule_id="R2", message="High", severity=Severity.HIGH),
                Finding(rule_id="R3", message="Medium", severity=Severity.MEDIUM),
            ],
        )

        report = generator.generate_markdown([result])

        assert "Critical" in report or "critical" in report.lower()
        assert "🚨" in report or "1" in report

    def test_generate_markdown_no_findings(self, generator: ReportGenerator) -> None:
        """测试无发现时的 Markdown."""
        result = ScanResult(scanner_name="test", findings=[])

        report = generator.generate_markdown([result])

        assert "No issues found" in report or "0" in report


class TestGenerateJSON:
    """JSON 生成测试."""

    def test_generate_json_basic(self) -> None:
        """测试基本 JSON 生成."""
        generator = ReportGenerator()
        result = ScanResult(
            scanner_name="security",
            findings=[
                Finding(
                    rule_id="RULE-1",
                    message="Issue",
                    severity=Severity.HIGH,
                ),
            ],
        )

        report = generator.generate_json([result], project_name="Test")

        assert report["version"] == "0.1.0"
        assert report["project_name"] == "Test"
        assert report["summary"]["total_issues"] == 1
        assert len(report["scanners"]) == 1

    def test_generate_json_severity_counts(self) -> None:
        """测试严重程度计数."""
        generator = ReportGenerator()
        result = ScanResult(
            scanner_name="test",
            findings=[
                Finding(rule_id="R1", message="M1", severity=Severity.HIGH),
                Finding(rule_id="R2", message="M2", severity=Severity.HIGH),
                Finding(rule_id="R3", message="M3", severity=Severity.LOW),
            ],
        )

        report = generator.generate_json([result])

        assert report["summary"]["severity_counts"]["high"] == 2
        assert report["summary"]["severity_counts"]["low"] == 1

    def test_generate_json_with_ai(self) -> None:
        """测试带 AI 的 JSON."""
        generator = ReportGenerator()
        ai_review = ReviewResult(
            summary="AI summary",
            severity=Severity.MEDIUM,
            comments=[
                ReviewComment(message="Comment 1"),
                ReviewComment(message="Comment 2"),
            ],
            action_items=["Fix this"],
        )

        report = generator.generate_json([], ai_review=ai_review)

        assert "ai_review" in report
        assert report["ai_review"]["summary"] == "AI summary"
        assert report["ai_review"]["comment_count"] == 2


class TestGenerateHTML:
    """HTML 生成测试."""

    def test_generate_html_basic(self) -> None:
        """测试基本 HTML 生成."""
        generator = ReportGenerator()
        result = ScanResult(
            scanner_name="security",
            findings=[
                Finding(rule_id="RULE-1", message="Issue", severity=Severity.HIGH),
            ],
        )

        report = generator.generate_html([result], project_name="Test")

        assert "<!DOCTYPE html>" in report
        assert "<html" in report
        assert "GitConsistency Code Health Report" in report
        assert "Test" in report

    def test_generate_html_contains_styling(self) -> None:
        """测试 HTML 包含样式."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = generator.generate_html([result])

        assert "<style>" in report
        assert "</style>" in report
        assert "container" in report


class TestGenerateGitHubComment:
    """GitHub 评论生成测试."""

    def test_generate_github_comment_basic(self) -> None:
        """测试基本评论生成."""
        generator = ReportGenerator()
        result = ScanResult(
            scanner_name="security",
            findings=[
                Finding(rule_id="R1", message="High issue", severity=Severity.HIGH),
                Finding(rule_id="R2", message="Medium issue", severity=Severity.MEDIUM),
            ],
        )

        comment = generator.generate_github_comment([result], project_name="Test")

        assert "GitConsistency Code Review" in comment
        assert "Test" in comment
        assert "🔴 Issues: 1" in comment
        assert "🟡 Warnings: 1" in comment

    def test_generate_github_comment_truncation(self) -> None:
        """测试评论截断."""
        generator = ReportGenerator()
        
        # 创建很多发现
        findings = [
            Finding(rule_id=f"R{i}", message=f"Issue {i}" * 1000, severity=Severity.HIGH)
            for i in range(100)
        ]
        result = ScanResult(scanner_name="security", findings=findings)

        comment = generator.generate_github_comment([result], max_length=5000)

        assert len(comment) <= 5000


class TestHelperMethods:
    """辅助方法测试."""

    def test_collect_findings(self) -> None:
        """测试收集发现."""
        generator = ReportGenerator()
        results = [
            ScanResult(scanner_name="s1", findings=[
                Finding(rule_id="R1", message="M1", severity=Severity.LOW),
            ]),
            ScanResult(scanner_name="s2", findings=[
                Finding(rule_id="R2", message="M2", severity=Severity.MEDIUM),
                Finding(rule_id="R3", message="M3", severity=Severity.HIGH),
            ]),
        ]

        findings = generator._collect_findings(results)

        assert len(findings) == 3

    def test_count_by_severity(self) -> None:
        """测试按严重程度计数."""
        generator = ReportGenerator()
        findings = [
            Finding(rule_id="R1", message="M1", severity=Severity.HIGH),
            Finding(rule_id="R2", message="M2", severity=Severity.HIGH),
            Finding(rule_id="R3", message="M3", severity=Severity.LOW),
        ]

        counts = generator._count_by_severity(findings)

        assert counts[Severity.HIGH] == 2
        assert counts[Severity.LOW] == 1
        assert counts[Severity.MEDIUM] == 0

    def test_get_worst_severity(self) -> None:
        """测试获取最严重级别."""
        generator = ReportGenerator()

        # 有严重问题
        counts1 = {Severity.CRITICAL: 1, Severity.HIGH: 5}
        assert generator._get_worst_severity(counts1) == Severity.CRITICAL

        # 只有中等问题
        counts2 = {Severity.MEDIUM: 3}
        assert generator._get_worst_severity(counts2) == Severity.MEDIUM

        # 没有问题
        counts3 = {}
        assert generator._get_worst_severity(counts3) == Severity.INFO

    def test_get_status_emoji(self) -> None:
        """测试状态图标."""
        generator = ReportGenerator()

        # 有关键问题
        assert "❌" in generator._get_status_emoji({Severity.CRITICAL: 1})

        # 只有警告
        assert "⚠️" in generator._get_status_emoji({Severity.MEDIUM: 1})

        # 全部通过
        assert "✅" in generator._get_status_emoji({Severity.LOW: 1})


class TestSaveReport:
    """保存报告测试."""

    def test_save_markdown(self, tmp_path: Path) -> None:
        """测试保存 Markdown."""
        generator = ReportGenerator()
        report = "# Test Report"
        output_path = tmp_path / "report.md"

        saved_path = generator.save_report(report, output_path, ReportFormat.MARKDOWN)

        assert saved_path == output_path
        assert output_path.read_text() == report

    def test_save_json(self, tmp_path: Path) -> None:
        """测试保存 JSON."""
        generator = ReportGenerator()
        report = {"key": "value", "number": 42}
        output_path = tmp_path / "report.json"

        saved_path = generator.save_report(report, output_path, ReportFormat.JSON)

        content = output_path.read_text()
        assert '"key": "value"' in content
        assert '"number": 42' in content

    def test_save_creates_directories(self, tmp_path: Path) -> None:
        """测试自动创建目录."""
        generator = ReportGenerator()
        output_path = tmp_path / "nested" / "dirs" / "report.md"

        generator.save_report("test", output_path)

        assert output_path.exists()


class TestGenerateDispatch:
    """生成分派测试."""

    def test_generate_markdown_dispatch(self) -> None:
        """测试 Markdown 分派."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = generator.generate([result], format=ReportFormat.MARKDOWN)

        assert isinstance(report, str)
        assert "#" in report

    def test_generate_json_dispatch(self) -> None:
        """测试 JSON 分派."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = generator.generate([result], format=ReportFormat.JSON)

        assert isinstance(report, dict)

    def test_generate_html_dispatch(self) -> None:
        """测试 HTML 分派."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = generator.generate([result], format=ReportFormat.HTML)

        assert isinstance(report, str)
        assert "<html" in report

    def test_generate_invalid_format(self) -> None:
        """测试无效格式."""
        generator = ReportGenerator()
        
        with pytest.raises(ValueError):
            generator.generate([], format="invalid")  # type: ignore
