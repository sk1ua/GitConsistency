"""Tests for report formatters base module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from consistency.report.formatters.base import BaseFormatter
from consistency.report.templates import ReportTheme
from consistency.scanners.base import Finding, ScanResult, Severity


class MockFormatter(BaseFormatter):
    """Mock formatter for testing."""

    def generate(self, scan_results, ai_review, project_name, **kwargs):
        return "mock report"


class TestBaseFormatter:
    """Test BaseFormatter class."""

    def test_default_initialization(self):
        """Test default initialization."""
        formatter = MockFormatter()

        assert formatter.theme is not None
        assert isinstance(formatter.theme, ReportTheme)
        assert formatter.version is not None

    def test_custom_initialization(self):
        """Test custom initialization."""
        theme = ReportTheme(primary_color="#ff0000")
        formatter = MockFormatter(theme=theme, version="1.0.0")

        assert formatter.theme == theme
        assert formatter.version == "1.0.0"

    def test_save_string_report(self, tmp_path: Path):
        """Test saving string report."""
        formatter = MockFormatter()
        report = "Test report content"
        output_path = tmp_path / "report.txt"

        result = formatter.save(report, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_text() == report

    def test_save_dict_report(self, tmp_path: Path):
        """Test saving dict report as JSON."""
        formatter = MockFormatter()
        report = {"key": "value", "count": 42}
        output_path = tmp_path / "report.json"

        result = formatter.save(report, output_path)

        assert result == output_path
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["key"] == "value"
        assert data["count"] == 42

    def test_save_creates_directories(self, tmp_path: Path):
        """Test save creates parent directories."""
        formatter = MockFormatter()
        report = "Test"
        output_path = tmp_path / "subdir1" / "subdir2" / "report.txt"

        formatter.save(report, output_path)

        assert output_path.parent.exists()

    @patch("consistency.report.formatters.base.logger")
    def test_save_logs_info(self, mock_logger, tmp_path: Path):
        """Test save logs info message."""
        formatter = MockFormatter()
        output_path = tmp_path / "report.txt"

        formatter.save("test", output_path)

        mock_logger.info.assert_called_once()
        assert "报告已保存" in str(mock_logger.info.call_args[0][0])

    def test_collect_findings(self):
        """Test collecting findings from multiple results."""
        formatter = MockFormatter()

        finding1 = Finding(
            rule_id="rule-1",
            message="Issue 1",
            severity=Severity.HIGH,
            file_path=Path("file1.py"),
            line=10,
        )
        finding2 = Finding(
            rule_id="rule-2",
            message="Issue 2",
            severity=Severity.MEDIUM,
            file_path=Path("file2.py"),
            line=20,
        )

        result1 = ScanResult(scanner_name="scanner1", findings=[finding1])
        result2 = ScanResult(scanner_name="scanner2", findings=[finding2])

        findings = formatter._collect_findings([result1, result2])

        assert len(findings) == 2
        assert finding1 in findings
        assert finding2 in findings

    def test_count_by_severity(self):
        """Test counting by severity."""
        formatter = MockFormatter()

        findings = [
            Finding(rule_id="r1", message="m1", severity=Severity.HIGH, file_path=Path("f.py")),
            Finding(rule_id="r2", message="m2", severity=Severity.HIGH, file_path=Path("f.py")),
            Finding(rule_id="r3", message="m3", severity=Severity.MEDIUM, file_path=Path("f.py")),
        ]

        counts = formatter._count_by_severity(findings)

        assert counts[Severity.HIGH] == 2
        assert counts[Severity.MEDIUM] == 1
        assert counts[Severity.LOW] == 0

    def test_get_worst_severity_critical(self):
        """Test getting worst severity with critical."""
        formatter = MockFormatter()
        counts = {
            Severity.CRITICAL: 1,
            Severity.HIGH: 5,
            Severity.MEDIUM: 3,
        }

        result = formatter._get_worst_severity(counts)

        assert result == Severity.CRITICAL

    def test_get_worst_severity_high(self):
        """Test getting worst severity with high only."""
        formatter = MockFormatter()
        counts = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 5,
            Severity.MEDIUM: 3,
        }

        result = formatter._get_worst_severity(counts)

        assert result == Severity.HIGH

    def test_get_worst_severity_info(self):
        """Test getting worst severity with no issues."""
        formatter = MockFormatter()
        counts = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 0,
            Severity.MEDIUM: 0,
            Severity.LOW: 0,
        }

        result = formatter._get_worst_severity(counts)

        assert result == Severity.INFO

    def test_get_status_emoji_critical(self):
        """Test status emoji with critical issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 1, Severity.HIGH: 5}

        result = formatter._get_status_emoji(counts)

        assert "Critical" in result

    def test_get_status_emoji_high(self):
        """Test status emoji with high issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 0, Severity.HIGH: 3}

        result = formatter._get_status_emoji(counts)

        assert "Issues found" in result

    def test_get_status_emoji_medium(self):
        """Test status emoji with medium issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 0, Severity.HIGH: 0, Severity.MEDIUM: 2}

        result = formatter._get_status_emoji(counts)

        assert "Warnings" in result

    def test_get_status_emoji_all_clear(self):
        """Test status emoji with no issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 0, Severity.HIGH: 0, Severity.MEDIUM: 0}

        result = formatter._get_status_emoji(counts)

        assert "All clear" in result or "No issues" in result

    def test_generate_summary_text_critical(self):
        """Test summary text with critical issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 2, Severity.HIGH: 5}
        findings = [MagicMock() for _ in range(10)]

        result = formatter._generate_summary_text(counts, findings)

        assert "critical" in result.lower() or "Critical" in result

    def test_generate_summary_text_high(self):
        """Test summary text with high issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 0, Severity.HIGH: 3}
        findings = [MagicMock() for _ in range(5)]

        result = formatter._generate_summary_text(counts, findings)

        assert "high severity" in result.lower() or "high" in result.lower()

    def test_generate_summary_text_minor(self):
        """Test summary text with minor issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 0, Severity.HIGH: 0, Severity.MEDIUM: 2}
        findings = [MagicMock() for _ in range(2)]

        result = formatter._generate_summary_text(counts, findings)

        assert "minor" in result.lower() or "issues" in result.lower()

    def test_generate_summary_text_all_clear(self):
        """Test summary text with no issues."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 0, Severity.HIGH: 0, Severity.MEDIUM: 0, Severity.LOW: 0}
        findings = []

        result = formatter._generate_summary_text(counts, findings)

        assert "No issues" in result or "All clear" in result or "great" in result.lower()

    def test_generate_summary_text_with_scanner_errors(self):
        """Test summary text with scanner errors."""
        formatter = MockFormatter()
        counts = {Severity.CRITICAL: 0, Severity.HIGH: 0}
        findings = []

        result = formatter._generate_summary_text(counts, findings, scanner_error_count=3)

        assert "error" in result.lower() or "errors" in result.lower()
