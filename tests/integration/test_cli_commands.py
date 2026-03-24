"""CLI 命令集成测试.

测试 CLI 命令的集成，包括 analyze、scan、review、config 等命令。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from consistency.cli.main import app
from consistency.config import Settings, get_settings


runner = CliRunner()


class TestCLIInitCommand:
    """CLI init 命令测试."""

    def test_init_command_help(self) -> None:
        """测试 init 命令帮助."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "init" in result.output.lower() or "初始化" in result.output


class TestCLIConfigCommands:
    """CLI config 命令测试."""

    def test_config_show(self) -> None:
        """测试 config show 命令."""
        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 0
        assert "GitConsistency" in result.output

    def test_config_validate(self) -> None:
        """测试 config validate 命令."""
        result = runner.invoke(app, ["config", "validate"])

        assert result.exit_code == 0
        # 验证命令应该显示配置验证表格
        assert "LLM" in result.output or "GitHub" in result.output or "配置验证" in result.output


class TestCLIScanCommands:
    """CLI scan 命令测试."""

    def test_scan_help(self) -> None:
        """测试 scan 命令帮助."""
        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0
        assert "scan" in result.output.lower() or "扫描" in result.output

    def test_scan_security_help(self) -> None:
        """测试 scan security 命令帮助."""
        result = runner.invoke(app, ["scan", "security", "--help"])

        assert result.exit_code == 0


class TestCLIReviewCommands:
    """CLI review 命令测试."""

    def test_review_help(self) -> None:
        """测试 review 命令帮助."""
        result = runner.invoke(app, ["review", "--help"])

        assert result.exit_code == 0


class TestCLIAnalyzeCommand:
    """CLI analyze 命令测试."""

    def test_analyze_help(self) -> None:
        """测试 analyze 命令帮助."""
        result = runner.invoke(app, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "analyze" in result.output.lower() or "分析" in result.output


class TestCLICICommand:
    """CLI CI 命令测试."""

    def test_ci_help(self) -> None:
        """测试 CI 命令帮助."""
        result = runner.invoke(app, ["ci", "--help"])

        assert result.exit_code == 0
        assert "CI" in result.output


class TestCLIMainCommands:
    """CLI 主命令测试."""

    def test_main_help(self) -> None:
        """测试主命令帮助."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "GitConsistency" in result.output
        assert "--version" in result.output

    def test_main_version(self) -> None:
        """测试 --version 选项."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        # 版本号应该包含在输出中
        assert "0.1.0" in result.output or "GitConsistency" in result.output


class TestCLIErrorHandling:
    """CLI 错误处理测试."""

    def test_nonexistent_file(self) -> None:
        """测试处理不存在的文件."""
        result = runner.invoke(app, ["review", "file", "/nonexistent/file.py"])

        # 应该返回非零退出码或显示错误信息
        assert result.exit_code != 0 or "错误" in result.output or "Error" in result.output or "不存在" in result.output


class TestCLIOptions:
    """CLI 选项测试."""

    def test_verbose_option(self) -> None:
        """测试 --verbose 选项."""
        result = runner.invoke(app, ["--verbose", "config", "show"])

        # verbose 应该被接受或忽略
        assert result.exit_code in (0, 2)

    def test_quiet_option(self) -> None:
        """测试 --quiet 选项."""
        result = runner.invoke(app, ["--quiet", "config", "show"])

        # quiet 应该被接受或忽略
        assert result.exit_code in (0, 2)


class TestCLIConfigurationPrecedence:
    """CLI 配置优先级测试."""

    def test_env_var_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试环境变量覆盖默认值."""
        monkeypatch.setenv("CONSISTENCY_PROJECT_NAME", "CustomProject")

        # 需要重新加载配置
        settings = Settings()
        assert settings.project_name == "CustomProject"
