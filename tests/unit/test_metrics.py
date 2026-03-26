"""Tests for metrics module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from consistency.core.metrics import (
    MetricsCollector,
    ScanMetrics,
    format_metrics_for_github_output,
    format_metrics_for_summary,
)


class TestScanMetrics:
    """Test ScanMetrics dataclass."""

    def test_default_initialization(self):
        """Test default initialization."""
        metrics = ScanMetrics()
        assert metrics.files_scanned == 0
        assert metrics.issues_critical == 0
        assert metrics.cache_hits == 0
        assert metrics.ai_review_enabled is False

    def test_finalize_calculates_duration(self):
        """Test finalize calculates duration."""
        metrics = ScanMetrics()
        import time

        metrics.start_time = time.perf_counter() - 1  # 1 second ago
        metrics.finalize()

        assert metrics.duration_ms >= 1000
        assert metrics.end_time > 0

    def test_finalize_calculates_cache_hit_rate(self):
        """Test finalize calculates cache hit rate."""
        metrics = ScanMetrics()
        metrics.cache_hits = 75
        metrics.cache_misses = 25
        metrics.finalize()

        assert metrics.cache_hit_rate == 0.75

    def test_finalize_no_cache_access(self):
        """Test finalize with no cache access."""
        metrics = ScanMetrics()
        metrics.finalize()

        assert metrics.cache_hit_rate == 0.0

    def test_to_dict(self):
        """Test conversion to dict."""
        metrics = ScanMetrics()
        metrics.files_scanned = 10
        metrics.issues_high = 5

        data = metrics.to_dict()
        assert data["files_scanned"] == 10
        assert data["issues_high"] == 5

    def test_to_json(self):
        """Test conversion to JSON."""
        metrics = ScanMetrics()
        metrics.files_scanned = 10

        json_str = metrics.to_json()
        data = json.loads(json_str)
        assert data["files_scanned"] == 10


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_initialization(self):
        """Test initialization."""
        collector = MetricsCollector()
        assert collector.metrics.files_scanned == 0
        assert collector._scanner_times == {}

    def test_start_scan(self):
        """Test start_scan sets start time."""
        collector = MetricsCollector()
        import time

        before = time.perf_counter()
        collector.start_scan()
        after = time.perf_counter()

        assert before <= collector.metrics.start_time <= after

    def test_record_files_scanned(self):
        """Test recording files scanned."""
        collector = MetricsCollector()
        collector.record_files_scanned(42)

        assert collector.metrics.files_scanned == 42
        assert collector.metrics.files_changed == 0

    def test_record_files_scanned_changed_only(self):
        """Test recording changed files."""
        collector = MetricsCollector()
        collector.record_files_scanned(10, changed_only=True)

        assert collector.metrics.files_scanned == 10
        assert collector.metrics.files_changed == 10

    def test_record_lines_of_code(self):
        """Test recording lines of code."""
        collector = MetricsCollector()
        collector.record_lines_of_code(1000)

        assert collector.metrics.lines_of_code == 1000

    def test_record_issues_found(self):
        """Test recording issues."""
        collector = MetricsCollector()
        collector.record_issues_found(
            critical=1, high=2, medium=3, low=4, info=5
        )

        assert collector.metrics.issues_critical == 1
        assert collector.metrics.issues_high == 2
        assert collector.metrics.issues_medium == 3
        assert collector.metrics.issues_low == 4
        assert collector.metrics.issues_info == 5

    def test_record_issues_found_accumulates(self):
        """Test that issues accumulate."""
        collector = MetricsCollector()
        collector.record_issues_found(critical=1)
        collector.record_issues_found(critical=2, high=3)

        assert collector.metrics.issues_critical == 3
        assert collector.metrics.issues_high == 3

    def test_record_scanner_used(self):
        """Test recording scanner usage."""
        collector = MetricsCollector()
        collector.record_scanner_used("semgrep", 150.5)

        assert "semgrep" in collector.metrics.scanners_used
        assert collector._scanner_times["semgrep"] == 150.5

    def test_record_scanner_used_unique(self):
        """Test scanner only added once."""
        collector = MetricsCollector()
        collector.record_scanner_used("semgrep", 100)
        collector.record_scanner_used("semgrep", 200)

        assert collector.metrics.scanners_used.count("semgrep") == 1

    def test_record_scanner_error(self):
        """Test recording scanner error."""
        collector = MetricsCollector()
        collector.record_scanner_error()
        collector.record_scanner_error()

        assert collector.metrics.scanner_errors == 2

    def test_record_ai_review(self):
        """Test recording AI review metrics."""
        collector = MetricsCollector()
        collector.record_ai_review(
            duration_ms=500, tokens_used=1000, model="gpt-4"
        )

        assert collector.metrics.ai_review_enabled is True
        assert collector.metrics.ai_review_duration_ms == 500
        assert collector.metrics.llm_tokens_used == 1000
        assert collector.metrics.llm_model == "gpt-4"

    def test_record_agents_used(self):
        """Test recording agents used."""
        collector = MetricsCollector()
        agents = ["security", "logic", "style"]
        collector.record_agents_used(agents, 300)

        assert collector.metrics.agents_used == agents
        assert collector.metrics.agent_review_duration_ms == 300

    def test_record_cache_hit(self):
        """Test recording cache hit."""
        collector = MetricsCollector()
        collector.record_cache_hit()
        collector.record_cache_hit()

        assert collector.metrics.cache_hits == 2

    def test_record_cache_miss(self):
        """Test recording cache miss."""
        collector = MetricsCollector()
        collector.record_cache_miss()

        assert collector.metrics.cache_misses == 1

    def test_finalize(self):
        """Test finalize returns metrics."""
        collector = MetricsCollector()
        collector.record_files_scanned(10)
        collector.record_issues_found(high=5)

        metrics = collector.finalize()

        assert isinstance(metrics, ScanMetrics)
        assert metrics.files_scanned == 10
        assert metrics.issues_high == 5
        assert metrics.duration_ms > 0

    def test_save(self, tmp_path: Path):
        """Test saving metrics to file."""
        collector = MetricsCollector()
        collector.record_files_scanned(10)
        collector.finalize()

        output_path = tmp_path / "metrics.json"
        collector.save(output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["files_scanned"] == 10


class TestFormatMetricsForSummary:
    """Test format_metrics_for_summary function."""

    def test_basic_formatting(self):
        """Test basic markdown formatting."""
        metrics = ScanMetrics()
        metrics.duration_ms = 1234.5
        metrics.files_scanned = 42
        metrics.issues_critical = 1
        metrics.issues_high = 2
        metrics.issues_medium = 3
        metrics.cache_hit_rate = 0.85

        result = format_metrics_for_summary(metrics)

        assert "Performance Metrics" in result
        assert "1234" in result
        assert "42" in result
        assert "1" in result
        assert "2" in result
        assert "3" in result
        assert "85.0%" in result

    def test_with_changed_files(self):
        """Test formatting with changed files."""
        metrics = ScanMetrics()
        metrics.files_changed = 5
        metrics.lines_of_code = 1000

        result = format_metrics_for_summary(metrics)

        assert "Files Changed" in result
        assert "Lines of Code" in result
        assert "1,000" in result

    def test_with_ai_review(self):
        """Test formatting with AI review."""
        metrics = ScanMetrics()
        metrics.ai_review_enabled = True
        metrics.ai_review_duration_ms = 500
        metrics.llm_tokens_used = 1000
        metrics.llm_model = "gpt-4"

        result = format_metrics_for_summary(metrics)

        assert "AI Review Metrics" in result
        assert "500" in result
        assert "1,000" in result
        assert "gpt-4" in result

    def test_with_agents(self):
        """Test formatting with agents."""
        metrics = ScanMetrics()
        metrics.agents_used = ["security", "logic"]

        result = format_metrics_for_summary(metrics)

        assert "Agents Used" in result
        assert "security" in result
        assert "logic" in result


class TestFormatMetricsForGitHubOutput:
    """Test format_metrics_for_github_output function."""

    def test_basic_output(self):
        """Test basic output formatting."""
        metrics = ScanMetrics()
        metrics.duration_ms = 1234.5
        metrics.files_scanned = 42
        metrics.issues_critical = 1
        metrics.issues_high = 2
        metrics.issues_medium = 3
        metrics.issues_low = 4
        metrics.issues_info = 5
        metrics.cache_hit_rate = 0.85
        metrics.ai_review_enabled = True

        result = format_metrics_for_github_output(metrics)

        assert result["scan_duration_ms"] == "1234"
        assert result["files_scanned"] == "42"
        assert result["issues_critical"] == "1"
        assert result["issues_high"] == "2"
        assert result["issues_medium"] == "3"
        assert result["issues_low"] == "4"
        assert result["issues_total"] == "15"
        assert result["cache_hit_rate"] == "0.85"
        assert result["ai_review_enabled"] == "true"

    def test_ai_disabled(self):
        """Test output when AI review disabled."""
        metrics = ScanMetrics()
        metrics.ai_review_enabled = False

        result = format_metrics_for_github_output(metrics)

        assert result["ai_review_enabled"] == "false"
