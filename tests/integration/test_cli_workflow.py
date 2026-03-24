"""CLI 工作流集成测试.

测试完整的工作流程，包括：
- 配置加载
- 扫描执行
- 报告生成
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from consistency.config import get_settings
from consistency.report.generator import ReportGenerator
from consistency.report.templates import ReportFormat
from consistency.scanners.orchestrator import ScannerOrchestrator


class TestCLIWorkflow:
    """CLI 工作流测试."""

    @pytest.fixture
    def temp_project(self) -> Path:
        """创建临时项目目录."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            # 创建一个简单的 Python 文件
            (path / "main.py").write_text("""
def hello():
    print("Hello World")

if __name__ == "__main__":
    hello()
""")
            yield path

    def test_settings_loading(self) -> None:
        """测试配置加载."""
        settings = get_settings()
        assert settings.project_name == "GitConsistency"
        assert settings.version == "0.1.0"

    def test_report_generator(self) -> None:
        """测试报告生成器初始化."""
        generator = ReportGenerator()
        # ReportGenerator uses theme
        assert generator.theme is not None

    def test_scanner_orchestrator_init(self) -> None:
        """测试扫描器协调器初始化."""
        orchestrator = ScannerOrchestrator()
        assert orchestrator is not None


class TestReportGeneration:
    """报告生成集成测试."""

    def test_markdown_report_structure(self) -> None:
        """测试 Markdown 报告结构."""
        generator = ReportGenerator()

        # 模拟扫描结果
        mock_results = []

        report = generator.generate(
            scan_results=mock_results,
            ai_review=None,
            project_name="test-project",
            format=ReportFormat.MARKDOWN,
            duration=1.5,
        )

        assert "GitConsistency" in report
        assert "test-project" in report

    def test_github_comment_generation(self) -> None:
        """测试 GitHub 评论生成."""
        generator = ReportGenerator()

        comment = generator.generate_github_comment(
            scan_results=[],
            ai_review=None,
            project_name="test-project",
        )

        assert "GitConsistency" in comment
        assert "test-project" in comment
