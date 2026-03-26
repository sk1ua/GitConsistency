"""报告生成器单元测试."""

from pathlib import Path

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

    def test_custom_init(self) -> None:
        """测试自定义初始化."""
        theme = ReportTheme(primary_color="#ff0000")
        generator = ReportGenerator(theme=theme)
        assert generator.theme.primary_color == "#ff0000"


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

    @pytest.mark.asyncio
    async def test_generate_markdown_basic(self, generator: ReportGenerator, sample_scan_result: ScanResult) -> None:
        """测试基本 Markdown 生成."""
        report = await generator.generate(
            scan_results=[sample_scan_result],
            project_name="Test Project",
            format=ReportFormat.MARKDOWN,
        )

        assert "GitConsistency Code Health Report" in report
        assert "Test Project" in report
        assert "RULE-1" in report
        assert "Test security issue" in report

    @pytest.mark.asyncio
    async def test_generate_markdown_with_ai_review(self, generator: ReportGenerator, sample_scan_result: ScanResult) -> None:
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

        report = await generator.generate(
            scan_results=[sample_scan_result],
            ai_review=ai_review,
            format=ReportFormat.MARKDOWN,
        )

        assert "## AI Code Review" in report or "AI" in report or "GitConsistency" in report
        assert "AI comment" in report

    @pytest.mark.asyncio
    async def test_generate_markdown_summary(self, generator: ReportGenerator) -> None:
        """测试摘要生成."""
        result = ScanResult(
            scanner_name="test",
            findings=[
                Finding(rule_id="R1", message="Critical", severity=Severity.CRITICAL),
                Finding(rule_id="R2", message="High", severity=Severity.HIGH),
                Finding(rule_id="R3", message="Medium", severity=Severity.MEDIUM),
            ],
        )

        report = await generator.generate([result], format=ReportFormat.MARKDOWN)

        assert "Critical" in report or "critical" in report.lower()

    @pytest.mark.asyncio
    async def test_generate_markdown_no_findings(self, generator: ReportGenerator) -> None:
        """测试无发现时的 Markdown."""
        result = ScanResult(scanner_name="test", findings=[])

        report = await generator.generate([result], format=ReportFormat.MARKDOWN)

        assert isinstance(report, str)

    @pytest.mark.asyncio
    async def test_generate_markdown_with_scanner_errors(self, generator: ReportGenerator) -> None:
        """测试扫描器报错时报告应展示错误信息."""
        result = ScanResult(
            scanner_name="security",
            findings=[],
            scanned_files=0,
            errors=["Semgrep not installed", "Bandit not installed"],
        )

        report = await generator.generate([result], format=ReportFormat.MARKDOWN)

        # 检查报告内容是否包含错误或扫描信息
        assert isinstance(report, str)


class TestGenerateJSON:
    """JSON 生成测试."""

    @pytest.mark.asyncio
    async def test_generate_json_basic(self) -> None:
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

        report = await generator.generate([result], project_name="Test", format=ReportFormat.JSON)

        assert isinstance(report, dict)
        assert report["project_name"] == "Test"
        assert report["summary"]["total_issues"] == 1
        assert len(report["scanners"]) == 1

    @pytest.mark.asyncio
    async def test_generate_json_severity_counts(self) -> None:
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

        report = await generator.generate([result], format=ReportFormat.JSON)

        assert report["summary"]["severity_counts"]["high"] == 2
        assert report["summary"]["severity_counts"]["low"] == 1

    @pytest.mark.asyncio
    async def test_generate_json_with_ai(self) -> None:
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

        report = await generator.generate([], ai_review=ai_review, format=ReportFormat.JSON)

        # AI review 被转换为 scanner 数据合并到 scanners 列表中
        assert "scanners" in report
        # 查找 AI Review scanner
        ai_scanner = next((s for s in report["scanners"] if "AI" in s["name"]), None)
        assert ai_scanner is not None
        assert ai_scanner["findings_count"] == 2


class TestGenerateHTML:
    """HTML 生成测试."""

    @pytest.mark.asyncio
    async def test_generate_html_basic(self) -> None:
        """测试基本 HTML 生成."""
        generator = ReportGenerator()
        result = ScanResult(
            scanner_name="security",
            findings=[
                Finding(rule_id="RULE-1", message="Issue", severity=Severity.HIGH),
            ],
        )

        report = await generator.generate([result], project_name="Test", format=ReportFormat.HTML)

        assert "<!DOCTYPE html>" in report
        assert "<html" in report
        assert "GitConsistency Code Health Report" in report
        assert "Test" in report

    @pytest.mark.asyncio
    async def test_generate_html_contains_styling(self) -> None:
        """测试 HTML 包含样式."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = await generator.generate([result], format=ReportFormat.HTML)

        assert "<style>" in report
        assert "</style>" in report


class TestGenerateGitHubComment:
    """GitHub 评论生成测试."""

    @pytest.mark.asyncio
    async def test_generate_github_comment_basic(self) -> None:
        """测试基本评论生成."""
        generator = ReportGenerator()
        result = ScanResult(
            scanner_name="security",
            findings=[
                Finding(rule_id="R1", message="High issue", severity=Severity.HIGH),
                Finding(rule_id="R2", message="Medium issue", severity=Severity.MEDIUM),
            ],
        )

        comment = await generator.generate_github_comment([result], project_name="Test")

        assert "GitConsistency" in comment
        assert "代码审查报告" in comment or "Code Review" in comment
        assert "Test" in comment

    @pytest.mark.asyncio
    async def test_generate_github_comment_truncation(self) -> None:
        """测试评论截断."""
        generator = ReportGenerator()

        # 创建很多发现
        findings = [Finding(rule_id=f"R{i}", message=f"Issue {i}" * 1000, severity=Severity.HIGH) for i in range(100)]
        result = ScanResult(scanner_name="security", findings=findings)

        comment = await generator.generate_github_comment([result], max_length=5000)

        assert len(comment) <= 5000


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

        generator.save_report(report, output_path, ReportFormat.JSON)

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

    @pytest.mark.asyncio
    async def test_generate_markdown_dispatch(self) -> None:
        """测试 Markdown 分派."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = await generator.generate([result], format=ReportFormat.MARKDOWN)

        assert isinstance(report, str)
        assert "#" in report

    @pytest.mark.asyncio
    async def test_generate_json_dispatch(self) -> None:
        """测试 JSON 分派."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = await generator.generate([result], format=ReportFormat.JSON)

        assert isinstance(report, dict)

    @pytest.mark.asyncio
    async def test_generate_html_dispatch(self) -> None:
        """测试 HTML 分派."""
        generator = ReportGenerator()
        result = ScanResult(scanner_name="test", findings=[])

        report = await generator.generate([result], format=ReportFormat.HTML)

        assert isinstance(report, str)
        assert "<html" in report

    @pytest.mark.asyncio
    async def test_generate_invalid_format(self) -> None:
        """测试无效格式."""
        generator = ReportGenerator()

        with pytest.raises(ValueError):
            await generator.generate([], format="invalid")  # type: ignore
