"""端到端测试 - 完整工作流.

测试完整的分析、报告生成和 GitHub 集成流程.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


class TestFullWorkflow:
    """完整工作流测试."""

    @pytest.fixture
    def sample_project(self) -> Path:
        """创建示例项目."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "sample_project"
            project.mkdir()

            # 创建 Python 文件
            (project / "main.py").write_text("""
def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
""")

            # 创建有问题的文件（用于测试）
            (project / "issues.py").write_text("""
import os

def insecure_function(password):
    # 安全问题：硬编码密码
    if password == "secret123":
        return True
    return False
""")

            # 初始化 git
            import subprocess
            subprocess.run(["git", "init"], cwd=project, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=project, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=project, capture_output=True)

            yield project

    @pytest.mark.asyncio
    async def test_scanner_orchestrator(self, sample_project: Path) -> None:
        """测试扫描器协调器."""
        from consistency.scanners.orchestrator import ScannerOrchestrator

        orchestrator = ScannerOrchestrator()
        orchestrator.create_default_scanners()

        report = await orchestrator.scan(sample_project)

        assert report is not None
        assert len(report.results) > 0
        assert report.duration_ms > 0

    @pytest.mark.asyncio
    async def test_report_generation(self, sample_project: Path) -> None:
        """测试报告生成."""
        from consistency.report.generator import ReportGenerator
        from consistency.report.templates import ReportFormat
        from consistency.scanners.orchestrator import ScannerOrchestrator

        # 运行扫描
        orchestrator = ScannerOrchestrator()
        orchestrator.create_default_scanners()
        scan_report = await orchestrator.scan(sample_project)

        # 生成报告
        generator = ReportGenerator()

        # Markdown
        md_report = generator.generate(
            list(scan_report.results.values()),
            format=ReportFormat.MARKDOWN,
        )
        assert isinstance(md_report, str)
        assert "GitConsistency" in md_report

        # JSON
        json_report = generator.generate(
            list(scan_report.results.values()),
            format=ReportFormat.JSON,
        )
        assert isinstance(json_report, dict)
        assert "summary" in json_report

    def test_github_integration_init(self) -> None:
        """测试 GitHub 集成初始化."""
        from consistency.github_integration import GitHubIntegration

        # 无 token 时应警告但不报错
        github = GitHubIntegration(token=None)
        assert github.token is None

    def test_config_loading(self) -> None:
        """测试配置加载."""
        from consistency.config import get_settings

        settings = get_settings()

        assert settings is not None
        assert settings.project_name == "GitConsistency"


class TestCLIE2E:
    """CLI 端到端测试."""

    def test_cli_help(self) -> None:
        """测试 CLI 帮助."""
        from typer.testing import CliRunner

        from consistency.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "GitConsistency" in result.output

    def test_cli_version(self) -> None:
        """测试 CLI 版本."""
        from typer.testing import CliRunner

        from consistency.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_config_validate(self) -> None:
        """测试配置验证命令."""
        from typer.testing import CliRunner

        from consistency.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["config", "validate"])

        assert result.exit_code == 0
        assert "LLM" in result.output or "GitHub" in result.output
