"""CLI 主模块单元测试."""

from typer.testing import CliRunner

from consistency.cli.main import app

runner = CliRunner()


class TestCLI:
    """CLI 测试."""

    def test_help(self) -> None:
        """测试帮助信息."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "GitConsistency" in result.output

    def test_version(self) -> None:
        """测试版本信息."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_analyze_help(self) -> None:
        """测试 analyze 命令帮助."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "分析代码仓库的安全状况" in result.output

    def test_ci_help(self) -> None:
        """测试 ci 命令帮助."""
        result = runner.invoke(app, ["ci", "--help"])
        assert result.exit_code == 0
        assert "CI/CD" in result.output

    def test_config_show(self) -> None:
        """测试 config show 命令."""
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "project_name" in result.output

    def test_config_validate(self) -> None:
        """测试 config validate 命令."""
        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 0
        assert "LLM" in result.output

    def test_scan_security_help(self) -> None:
        """测试 scan security 命令帮助."""
        result = runner.invoke(app, ["scan", "security", "--help"])
        assert result.exit_code == 0
        assert "安全扫描" in result.output
