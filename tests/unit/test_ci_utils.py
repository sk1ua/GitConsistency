"""Tests for github/ci_utils module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from consistency.github.ci_utils import (
    debug_print_context,
    get_workflow_context,
    is_github_actions,
    set_actions_output,
    set_actions_outputs_from_results,
    write_actions_summary,
    write_annotations_from_findings,
    write_workflow_annotation,
)
from consistency.scanners.base import Finding, ScanResult, Severity


class TestWriteActionsSummary:
    """Test write_actions_summary function."""

    def test_writes_to_file_when_env_set(self, tmp_path: Path):
        """Test summary is written when GITHUB_STEP_SUMMARY is set."""
        summary_file = tmp_path / "summary.md"

        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            write_actions_summary("# Test Summary")

        assert summary_file.exists()
        content = summary_file.read_text()
        assert "# Test Summary" in content

    def test_skips_when_env_not_set(self):
        """Test nothing happens when GITHUB_STEP_SUMMARY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise
            write_actions_summary("# Test")

    def test_appends_to_existing_file(self, tmp_path: Path):
        """Test summary is appended to existing file."""
        summary_file = tmp_path / "summary.md"
        summary_file.write_text("# Existing\n")

        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            write_actions_summary("# New")

        content = summary_file.read_text()
        assert "# Existing" in content
        assert "# New" in content

    @patch("consistency.github.ci_utils.logger")
    def test_handles_write_error(self, mock_logger, tmp_path: Path):
        """Test error handling when write fails."""
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": "/nonexistent/path/summary.md"}):
            write_actions_summary("# Test")

        mock_logger.warning.assert_called_once()


class TestWriteWorkflowAnnotation:
    """Test write_workflow_annotation function."""

    def test_basic_annotation(self, capsys):
        """Test basic annotation output."""
        write_workflow_annotation("error", "Something went wrong")

        captured = capsys.readouterr()
        assert "::error::Something went wrong" in captured.out

    def test_annotation_with_file(self, capsys):
        """Test annotation with file path."""
        write_workflow_annotation("warning", "Deprecated API", file="src/main.py")

        captured = capsys.readouterr()
        assert "::warning file=src/main.py::" in captured.out

    def test_annotation_with_line(self, capsys):
        """Test annotation with line number."""
        write_workflow_annotation("error", "Syntax error", file="test.py", line=42)

        captured = capsys.readouterr()
        assert "::error file=test.py,line=42::" in captured.out

    def test_annotation_with_title(self, capsys):
        """Test annotation with title."""
        write_workflow_annotation("notice", "Info", title="My Title")

        captured = capsys.readouterr()
        assert "::notice title=My Title::" in captured.out

    def test_annotation_escapes_special_chars(self, capsys):
        """Test special characters are escaped."""
        write_workflow_annotation("error", "Line 1\nLine 2\rLine 3%")

        captured = capsys.readouterr()
        assert "%0A" in captured.out  # newline
        assert "%0D" in captured.out  # carriage return
        assert "%25" in captured.out  # percent sign

    def test_annotation_with_all_params(self, capsys):
        """Test annotation with all parameters."""
        write_workflow_annotation(
            "error",
            "Critical error",
            file="src/app.py",
            line=100,
            title="Security Issue"
        )

        captured = capsys.readouterr()
        assert "file=src/app.py" in captured.out
        assert "line=100" in captured.out
        assert "title=Security Issue" in captured.out

    def test_skips_line_zero(self, capsys):
        """Test line=0 is skipped."""
        write_workflow_annotation("error", "Error", file="test.py", line=0)

        captured = capsys.readouterr()
        assert "line=0" not in captured.out


class TestWriteAnnotationsFromFindings:
    """Test write_annotations_from_findings function."""

    def test_no_findings(self):
        """Test with empty findings list."""
        count = write_annotations_from_findings([])
        assert count == 0

    def test_critical_finding(self, capsys):
        """Test critical finding outputs error annotation."""
        finding = Finding(
            rule_id="SEC001",
            message="SQL injection vulnerability",
            severity=Severity.CRITICAL,
            file_path=Path("db.py"),
            line=10,
        )

        write_annotations_from_findings([finding])

        captured = capsys.readouterr()
        assert "::error" in captured.out
        assert "SQL injection" in captured.out

    def test_high_finding_as_error(self, capsys):
        """Test high severity outputs error annotation."""
        finding = Finding(
            rule_id="SEC002",
            message="Hardcoded password",
            severity=Severity.HIGH,
            file_path=Path("config.py"),
            line=5,
        )

        write_annotations_from_findings([finding])

        captured = capsys.readouterr()
        assert "::error" in captured.out

    def test_medium_finding_as_warning(self, capsys):
        """Test medium severity outputs warning annotation."""
        finding = Finding(
            rule_id="STYLE001",
            message="Line too long",
            severity=Severity.MEDIUM,
            file_path=Path("long.py"),
            line=20,
        )

        write_annotations_from_findings([finding])

        captured = capsys.readouterr()
        assert "::warning" in captured.out

    def test_low_finding_as_notice(self, capsys):
        """Test low severity outputs notice annotation."""
        finding = Finding(
            rule_id="INFO001",
            message="Consider using type hints",
            severity=Severity.LOW,
            file_path=Path("untyped.py"),
            line=1,
        )

        write_annotations_from_findings([finding])

        captured = capsys.readouterr()
        assert "::notice" in captured.out

    def test_respects_max_errors(self, capsys):
        """Test max_errors limit is respected."""
        findings = [
            Finding(
                rule_id=f"SEC{i:03d}",
                message=f"Error {i}",
                severity=Severity.CRITICAL,
                file_path=Path(f"file{i}.py"),
                line=i,
            )
            for i in range(15)
        ]

        count = write_annotations_from_findings(findings, max_errors=5, max_warnings=10)
        assert count == 5  # Only 5 errors

    def test_respects_max_warnings(self, capsys):
        """Test max_warnings limit is respected."""
        findings = [
            Finding(
                rule_id=f"WARN{i:03d}",
                message=f"Warning {i}",
                severity=Severity.MEDIUM,
                file_path=Path(f"file{i}.py"),
                line=i,
            )
            for i in range(15)
        ]

        count = write_annotations_from_findings(findings, max_errors=10, max_warnings=3)
        assert count == 3  # Only 3 warnings

    def test_includes_code_snippet(self, capsys):
        """Test code snippet is included in message."""
        finding = Finding(
            rule_id="SEC001",
            message="Issue found",
            severity=Severity.HIGH,
            file_path=Path("code.py"),
            line=10,
            code_snippet="eval(user_input)",
        )

        write_annotations_from_findings([finding])

        captured = capsys.readouterr()
        assert "Code:" in captured.out
        assert "eval(user_input)" in captured.out

    def test_shows_truncation_notice(self, capsys):
        """Test notice shown when errors are truncated."""
        findings = [
            Finding(
                rule_id=f"SEC{i:03d}",
                message=f"Error {i}",
                severity=Severity.HIGH,
                file_path=Path(f"file{i}.py"),
                line=i,
            )
            for i in range(15)
        ]

        write_annotations_from_findings(findings, max_errors=5)

        captured = capsys.readouterr()
        assert "更多问题" in captured.out or "more" in captured.out.lower()

    def test_sorts_by_severity(self, capsys):
        """Test findings are sorted by severity."""
        findings = [
            Finding(
                rule_id="LOW",
                message="Low priority",
                severity=Severity.LOW,
                file_path=Path("low.py"),
                line=1,
            ),
            Finding(
                rule_id="CRITICAL",
                message="Critical issue",
                severity=Severity.CRITICAL,
                file_path=Path("critical.py"),
                line=1,
            ),
        ]

        write_annotations_from_findings(findings)

        captured = capsys.readouterr()
        # Critical should appear before low
        critical_pos = captured.out.find("Critical issue")
        low_pos = captured.out.find("Low priority")
        assert critical_pos < low_pos


class TestSetActionsOutput:
    """Test set_actions_output function."""

    def test_writes_output(self, tmp_path: Path):
        """Test output is written to GITHUB_OUTPUT file."""
        output_file = tmp_path / "github_output"

        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            set_actions_output("result", "success")

        content = output_file.read_text()
        assert "result=success" in content

    def test_skips_when_env_not_set(self):
        """Test nothing happens when GITHUB_OUTPUT is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise
            set_actions_output("key", "value")

    @patch("consistency.github.ci_utils.logger")
    def test_handles_write_error(self, mock_logger):
        """Test error handling when write fails."""
        with patch.dict(os.environ, {"GITHUB_OUTPUT": "/nonexistent/path/output"}):
            set_actions_output("key", "value")

        mock_logger.warning.assert_called_once()


class TestSetActionsOutputsFromResults:
    """Test set_actions_outputs_from_results function."""

    def test_outputs_set_correctly(self, tmp_path: Path):
        """Test all outputs are set correctly."""
        output_file = tmp_path / "github_output"

        findings = [
            Finding(rule_id="R1", message="Critical", severity=Severity.CRITICAL, file_path=Path("a.py")),
            Finding(rule_id="R2", message="High", severity=Severity.HIGH, file_path=Path("b.py")),
            Finding(rule_id="R3", message="Medium", severity=Severity.MEDIUM, file_path=Path("c.py")),
            Finding(rule_id="R4", message="Low", severity=Severity.LOW, file_path=Path("d.py")),
        ]
        scan_result = ScanResult(scanner_name="test", findings=findings)

        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            outputs = set_actions_outputs_from_results([scan_result], 1234.5)

        content = output_file.read_text()
        assert "total_findings=4" in content
        assert "critical_count=1" in content
        assert "high_count=1" in content
        assert "medium_count=1" in content
        assert "low_count=1" in content
        assert "duration_ms=1234" in content
        assert "has_issues=true" in content

        assert outputs["total_findings"] == "4"
        assert outputs["has_issues"] == "true"

    def test_no_issues_when_only_low(self, tmp_path: Path):
        """Test has_issues is false when only low severity."""
        output_file = tmp_path / "github_output"

        findings = [
            Finding(rule_id="R1", message="Low", severity=Severity.LOW, file_path=Path("a.py")),
        ]
        scan_result = ScanResult(scanner_name="test", findings=findings)

        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            outputs = set_actions_outputs_from_results([scan_result], 100)

        assert outputs["has_issues"] == "false"

    def test_empty_results(self, tmp_path: Path):
        """Test with empty results."""
        output_file = tmp_path / "github_output"

        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            outputs = set_actions_outputs_from_results([], 500)

        assert outputs["total_findings"] == "0"
        assert outputs["has_issues"] == "false"


class TestIsGithubActions:
    """Test is_github_actions function."""

    def test_returns_true_in_actions(self):
        """Test returns True when GITHUB_ACTIONS=true."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            assert is_github_actions() is True

    def test_returns_false_not_in_actions(self):
        """Test returns False when GITHUB_ACTIONS is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_github_actions() is False

    def test_returns_false_when_not_true(self):
        """Test returns False when GITHUB_ACTIONS is not 'true'."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "1"}):
            assert is_github_actions() is False


class TestGetWorkflowContext:
    """Test get_workflow_context function."""

    def test_returns_context_dict(self):
        """Test returns dictionary with context."""
        env_vars = {
            "GITHUB_WORKFLOW": "Test Workflow",
            "GITHUB_RUN_ID": "12345",
            "GITHUB_RUN_NUMBER": "42",
            "GITHUB_ACTOR": "testuser",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_SHA": "abc123",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_HEAD_REF": "feature-branch",
            "GITHUB_BASE_REF": "main",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            context = get_workflow_context()

        assert context["workflow"] == "Test Workflow"
        assert context["run_id"] == "12345"
        assert context["run_number"] == "42"
        assert context["actor"] == "testuser"
        assert context["repository"] == "owner/repo"
        assert context["event_name"] == "push"
        assert context["sha"] == "abc123"
        assert context["ref"] == "refs/heads/main"
        assert context["head_ref"] == "feature-branch"
        assert context["base_ref"] == "main"

    def test_reads_event_data(self, tmp_path: Path):
        """Test reads event data from file."""
        event_file = tmp_path / "event.json"
        event_data = {"action": "opened", "number": 123}
        event_file.write_text(json.dumps(event_data))

        with patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event_file)}):
            context = get_workflow_context()

        assert context["event_data"] == event_data

    def test_handles_missing_event_file(self):
        """Test handles missing event file gracefully."""
        with patch.dict(os.environ, {"GITHUB_EVENT_PATH": "/nonexistent/event.json"}):
            context = get_workflow_context()

        assert context["event_data"] == {}

    def test_handles_invalid_json(self, tmp_path: Path):
        """Test handles invalid JSON in event file."""
        event_file = tmp_path / "event.json"
        event_file.write_text("not valid json")

        with patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event_file)}):
            context = get_workflow_context()

        assert context["event_data"] == {}


class TestDebugPrintContext:
    """Test debug_print_context function."""

    @patch("consistency.github.ci_utils.logger")
    def test_prints_when_debug_set(self, mock_logger):
        """Test prints context when CONSISTENCY_DEBUG is set."""
        with patch.dict(os.environ, {"CONSISTENCY_DEBUG": "1", "GITHUB_WORKFLOW": "Test"}):
            debug_print_context()

        mock_logger.debug.assert_called()

    @patch("consistency.github.ci_utils.logger")
    def test_prints_when_runner_debug_set(self, mock_logger):
        """Test prints context when RUNNER_DEBUG is set."""
        with patch.dict(os.environ, {"RUNNER_DEBUG": "1", "GITHUB_WORKFLOW": "Test"}):
            debug_print_context()

        mock_logger.debug.assert_called()

    @patch("consistency.github.ci_utils.logger")
    def test_skips_when_not_debug(self, mock_logger):
        """Test does nothing when not in debug mode."""
        with patch.dict(os.environ, {}, clear=True):
            debug_print_context()

        mock_logger.debug.assert_not_called()
