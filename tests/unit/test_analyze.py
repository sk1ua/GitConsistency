"""Tests for analyze command."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from consistency.cli.commands.analyze import (
    _print_summary,
    _run_analysis,
    _run_analyze_command,
    register_analyze_command,
)
from consistency.report.templates import ReportFormat
from consistency.scanners.base import Finding, ScanResult, Severity

runner = CliRunner()


@pytest.fixture
def mock_console():
    """Create mock console."""
    return MagicMock()


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.is_litellm_configured = True
    settings.is_github_configured = False
    settings.is_gitnexus_configured = False
    settings.debug = False
    return settings


class TestRegisterAnalyzeCommand:
    """Test register_analyze_command."""

    def test_registration(self, mock_console):
        """Test command registration."""
        app = typer.Typer()
        register_analyze_command(app, mock_console)
        # If no error raised, registration succeeded


class TestRunAnalyzeCommand:
    """Test _run_analyze_command function."""

    @patch("consistency.cli.commands.analyze.asyncio.run")
    def test_run_with_markdown_output(
        self, mock_run, mock_console, mock_settings
    ):
        """Test analyze with markdown format."""
        mock_run.side_effect = [
            {
                "results": {
                    "security": ScanResult(
                        scanner_name="security",
                        findings=[
                            Finding(
                                rule_id="test-rule",
                                message="Test finding",
                                severity=Severity.HIGH,
                                file_path=Path("test.py"),
                                line=10,
                            )
                        ],
                    )
                },
                "duration_ms": 1000,
                "ai_review": None,
                "errors": [],
                "commit_sha": "abc123",
            },
            "# Test Report",
        ]

        with patch("consistency.get_settings", return_value=mock_settings):
            _run_analyze_command(
                path=Path("."),
                output=None,
                format="markdown",
                skip_security=False,
                skip_ai=True,
                console=mock_console,
            )

        # Verify console.print was called
        assert mock_console.print.called

    @patch("consistency.cli.commands.analyze.asyncio.run")
    def test_run_with_json_output(
        self, mock_run, mock_console, mock_settings
    ):
        """Test analyze with json format."""
        mock_run.side_effect = [
            {
                "results": {},
                "duration_ms": 500,
                "ai_review": None,
                "errors": [],
                "commit_sha": "abc123",
            },
            {"summary": "Test", "findings": []},
        ]

        with patch("consistency.get_settings", return_value=mock_settings):
            _run_analyze_command(
                path=Path("."),
                output=None,
                format="json",
                skip_security=False,
                skip_ai=True,
                console=mock_console,
            )

        # Verify console.print_json was called for dict output
        assert mock_console.print.called or mock_console.print_json.called

    @patch("consistency.cli.commands.analyze.asyncio.run")
    def test_run_with_file_output(
        self, mock_run, mock_console, mock_settings, tmp_path: Path
    ):
        """Test analyze with file output."""
        output_file = tmp_path / "report.md"

        mock_run.side_effect = [
            {
                "results": {},
                "duration_ms": 500,
                "ai_review": None,
                "errors": [],
                "commit_sha": "abc123",
            },
            "# Test Report",
        ]

        with patch("consistency.get_settings", return_value=mock_settings):
            with patch(
                "consistency.cli.commands.analyze.ReportGenerator.save_report"
            ) as mock_save:
                mock_save.return_value = output_file
                _run_analyze_command(
                    path=Path("."),
                    output=output_file,
                    format="markdown",
                    skip_security=False,
                    skip_ai=True,
                    console=mock_console,
                )

                mock_save.assert_called_once()

    @patch("consistency.cli.commands.analyze.asyncio.run")
    def test_run_with_gitconsistency_error(
        self, mock_run, mock_console, mock_settings
    ):
        """Test analyze with GitConsistencyError."""
        from consistency.exceptions import ConfigError

        mock_run.side_effect = ConfigError("Test error", details={"code": "TEST_ERROR"})

        with patch("consistency.get_settings", return_value=mock_settings):
            with pytest.raises(Exception):
                _run_analyze_command(
                    path=Path("."),
                    output=None,
                    format="markdown",
                    skip_security=False,
                    skip_ai=True,
                    console=mock_console,
                )

    @patch("consistency.cli.commands.analyze.asyncio.run")
    def test_run_with_generic_exception(
        self, mock_run, mock_console, mock_settings
    ):
        """Test analyze with generic exception."""
        mock_run.side_effect = ValueError("Generic error")

        with patch("consistency.get_settings", return_value=mock_settings):
            with pytest.raises(Exception):
                _run_analyze_command(
                    path=Path("."),
                    output=None,
                    format="markdown",
                    skip_security=False,
                    skip_ai=True,
                    console=mock_console,
                )

    @patch("consistency.cli.commands.analyze.asyncio.run")
    def test_run_with_debug_enabled(
        self, mock_run, mock_console, mock_settings
    ):
        """Test analyze with debug mode."""
        mock_settings.debug = True
        mock_run.side_effect = ValueError("Error with traceback")

        with patch("consistency.get_settings", return_value=mock_settings):
            with pytest.raises(Exception):
                _run_analyze_command(
                    path=Path("."),
                    output=None,
                    format="markdown",
                    skip_security=False,
                    skip_ai=True,
                    console=mock_console,
                )

        # Should print traceback in debug mode
        assert mock_console.print.called


class TestRunAnalysis:
    """Test _run_analysis function."""

    @pytest.mark.asyncio
    async def test_run_analysis_basic(self, mock_console, mock_settings):
        """Test basic analysis run."""
        with patch(
            "consistency.cli.commands.analyze.ScannerOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_report = MagicMock()
            mock_report.results = {}
            mock_report.duration_ms = 1000
            mock_report.errors = []
            mock_orchestrator.scan = AsyncMock(return_value=mock_report)
            mock_orchestrator_class.return_value = mock_orchestrator

            result = await _run_analysis(
                path=Path("."),
                skip_security=False,
                skip_ai=True,
                settings=mock_settings,
                console=mock_console,
            )

            assert "results" in result
            assert "duration_ms" in result
            assert result["ai_review"] is None

    @pytest.mark.asyncio
    async def test_run_analysis_with_ai(self, mock_console, mock_settings):
        """Test analysis with AI review."""
        mock_settings.is_litellm_configured = True

        with patch(
            "consistency.cli.commands.analyze.ScannerOrchestrator"
        ) as mock_orchestrator_class:
            with patch(
                "consistency.reviewer.AIReviewer"
            ) as mock_reviewer_class:
                with patch(
                    "consistency.reviewer.ReviewContext"
                ) as mock_context_class:
                    mock_orchestrator = MagicMock()
                    mock_report = MagicMock()
                    mock_report.results = {
                        "security": ScanResult(
                            scanner_name="security",
                            findings=[
                                Finding(
                                    rule_id="test",
                                    message="Test",
                                    severity=Severity.HIGH,
                                    file_path=Path("test.py"),
                                    line=1,
                                )
                            ],
                        )
                    }
                    mock_report.duration_ms = 1000
                    mock_report.errors = []
                    mock_orchestrator.scan = AsyncMock(return_value=mock_report)
                    mock_orchestrator_class.return_value = mock_orchestrator

                    mock_reviewer = MagicMock()
                    mock_reviewer.review = AsyncMock(return_value=MagicMock())
                    mock_reviewer_class.return_value = mock_reviewer

                    result = await _run_analysis(
                        path=Path("."),
                        skip_security=False,
                        skip_ai=False,
                        settings=mock_settings,
                        console=mock_console,
                    )

                    mock_reviewer.review.assert_called_once()


class TestPrintSummary:
    """Test _print_summary function."""

    def test_print_summary_no_findings(self, mock_console):
        """Test summary with no findings."""
        result = {
            "results": {},
            "errors": [],
        }
        _print_summary(result, mock_console)

        # Should print success message
        assert mock_console.print.called
        call_args = str(mock_console.print.call_args)
        assert "未发现" in call_args or "No issues" in call_args or "great" in call_args

    def test_print_summary_with_findings(self, mock_console):
        """Test summary with findings."""
        result = {
            "results": {
                "security": ScanResult(
                    scanner_name="security",
                    findings=[
                        Finding(
                            rule_id="r1",
                            message="High issue",
                            severity=Severity.HIGH,
                            file_path=Path("test.py"),
                            line=10,
                        ),
                        Finding(
                            rule_id="r2",
                            message="Medium issue",
                            severity=Severity.MEDIUM,
                            file_path=Path("test.py"),
                            line=20,
                        ),
                    ],
                )
            },
            "errors": [],
        }
        _print_summary(result, mock_console)

        # Should print table with findings
        assert mock_console.print.called

    def test_print_summary_with_scanner_errors(self, mock_console):
        """Test summary with scanner errors."""
        result = {
            "results": {
                "security": ScanResult(
                    scanner_name="security",
                    findings=[],
                    errors=["Semgrep not found"],
                )
            },
            "errors": [],
        }
        _print_summary(result, mock_console)

        # Should print warning about errors
        assert mock_console.print.called

    def test_print_summary_with_findings_and_errors(self, mock_console):
        """Test summary with both findings and errors."""
        result = {
            "results": {
                "security": ScanResult(
                    scanner_name="security",
                    findings=[
                        Finding(
                            rule_id="r1",
                            message="Issue",
                            severity=Severity.LOW,
                            file_path=Path("test.py"),
                            line=1,
                        )
                    ],
                    errors=["Scanner error"],
                )
            },
            "errors": [],
        }
        _print_summary(result, mock_console)

        # Should handle both findings and errors
        assert mock_console.print.called

    def test_print_summary_critical_findings(self, mock_console):
        """Test summary with critical findings."""
        result = {
            "results": {
                "security": ScanResult(
                    scanner_name="security",
                    findings=[
                        Finding(
                            rule_id="r1",
                            message="Critical issue",
                            severity=Severity.CRITICAL,
                            file_path=Path("test.py"),
                            line=1,
                        )
                    ],
                )
            },
            "errors": [],
        }
        _print_summary(result, mock_console)

        # Should show critical in summary
        assert mock_console.print.called
