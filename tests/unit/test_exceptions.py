"""Tests for exceptions module."""

from __future__ import annotations

import pytest

from consistency.exceptions import (
    ConfigError,
    GitConsistencyError,
    GitHubError,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubNotFoundError,
    ScanError,
    SemgrepError,
    BanditError,
    AIReviewError,
    LLMConnectionError,
    GitNexusError,
    ReportError,
    NetworkError,
)


class TestGitConsistencyError:
    """Test base GitConsistencyError class."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = GitConsistencyError("Something went wrong")
        assert "Something went wrong" in str(error)
        assert error.error_code == "UNKNOWN_ERROR"

    def test_error_with_code(self):
        """Test error with error code."""
        error = GitConsistencyError("Error message", error_code="CUSTOM_ERROR")
        assert error.error_code == "CUSTOM_ERROR"
        assert "CUSTOM_ERROR" in str(error)

    def test_error_with_details(self):
        """Test error with details."""
        details = {"key": "value", "count": 42}
        error = GitConsistencyError("Error with details", details=details)
        assert error.details == details
        assert "value" in str(error)


class TestConfigError:
    """Test ConfigError class."""

    def test_config_error(self):
        """Test configuration error."""
        error = ConfigError("Invalid configuration")
        assert "Invalid configuration" in str(error)
        assert error.error_code == "CONFIG_ERROR"
        assert isinstance(error, GitConsistencyError)

    def test_config_error_with_details(self):
        """Test configuration error with details."""
        error = ConfigError(
            "Missing required field",
            details={"file": "config.yaml", "field": "api_key"}
        )
        assert error.details["file"] == "config.yaml"


class TestScanError:
    """Test ScanError class."""

    def test_scan_error(self):
        """Test scanner error."""
        error = ScanError("Scanner failed")
        assert "Scanner failed" in str(error)
        assert isinstance(error, GitConsistencyError)

    def test_scan_error_with_scanner(self):
        """Test scanner error with scanner name."""
        error = ScanError("Semgrep failed", scanner="semgrep", details={"exit_code": 1})
        assert error.scanner == "semgrep"


class TestSemgrepError:
    """Test SemgrepError class."""

    def test_semgrep_error(self):
        """Test Semgrep error."""
        error = SemgrepError("Rule parsing failed")
        assert "Rule parsing failed" in str(error)
        assert error.error_code == "SEMGREP_ERROR"
        assert error.scanner == "semgrep"


class TestBanditError:
    """Test BanditError class."""

    def test_bandit_error(self):
        """Test Bandit error."""
        error = BanditError("AST parsing failed")
        assert "AST parsing failed" in str(error)
        assert error.error_code == "BANDIT_ERROR"
        assert error.scanner == "bandit"


class TestGitHubError:
    """Test GitHubError class."""

    def test_github_error(self):
        """Test GitHub error."""
        error = GitHubError("GitHub API failed")
        assert "GitHub API failed" in str(error)
        assert isinstance(error, GitConsistencyError)

    def test_github_error_with_status_code(self):
        """Test GitHub error with status code."""
        error = GitHubError("API Error", status_code=500)
        assert error.status_code == 500


class TestGitHubAuthError:
    """Test GitHubAuthError class."""

    def test_auth_error_default_message(self):
        """Test auth error with default message."""
        error = GitHubAuthError()
        assert "认证失败" in str(error) or "Auth" in str(error)
        assert error.error_code == "GITHUB_AUTH_ERROR"
        assert error.status_code == 401

    def test_auth_error_custom_message(self):
        """Test auth error with custom message."""
        error = GitHubAuthError("Token expired")
        assert "Token expired" in str(error)


class TestGitHubRateLimitError:
    """Test GitHubRateLimitError class."""

    def test_rate_limit_error(self):
        """Test rate limit error."""
        error = GitHubRateLimitError(reset_at=1234567890)
        assert error.error_code == "GITHUB_RATE_LIMIT"
        assert error.status_code == 429
        assert error.reset_at == 1234567890


class TestGitHubNotFoundError:
    """Test GitHubNotFoundError class."""

    def test_not_found_error(self):
        """Test not found error."""
        error = GitHubNotFoundError("repo/owner")
        assert "repo/owner" in str(error)
        assert error.resource == "repo/owner"
        assert error.status_code == 404


class TestAIReviewError:
    """Test AIReviewError class."""

    def test_ai_review_error(self):
        """Test AI review error."""
        error = AIReviewError("LLM request failed")
        assert "LLM request failed" in str(error)
        assert isinstance(error, GitConsistencyError)

    def test_ai_review_error_with_model(self):
        """Test AI review error with model."""
        error = AIReviewError("Model error", model="gpt-4")
        assert error.model == "gpt-4"


class TestLLMConnectionError:
    """Test LLMConnectionError class."""

    def test_connection_error(self):
        """Test connection error."""
        error = LLMConnectionError()
        assert error.error_code == "LLM_CONNECTION_ERROR"

    def test_connection_error_with_model(self):
        """Test connection error with model."""
        error = LLMConnectionError(model="claude-3")
        assert error.model == "claude-3"


class TestGitNexusError:
    """Test GitNexusError class."""

    def test_gitnexus_error(self):
        """Test GitNexus error."""
        error = GitNexusError("GitNexus failed")
        assert "GitNexus failed" in str(error)
        assert error.error_code == "GITNEXUS_ERROR"


class TestReportError:
    """Test ReportError class."""

    def test_report_error(self):
        """Test report error."""
        error = ReportError("Failed to generate report")
        assert "Failed to generate report" in str(error)
        assert error.error_code == "REPORT_ERROR"

    def test_report_error_with_format(self):
        """Test report error with format."""
        error = ReportError("Invalid format", format="pdf")
        assert error.format == "pdf"


class TestNetworkError:
    """Test NetworkError class."""

    def test_network_error(self):
        """Test network error."""
        error = NetworkError("Connection failed")
        assert "Connection failed" in str(error)
        assert error.error_code == "NETWORK_ERROR"

    def test_network_error_with_url(self):
        """Test network error with URL."""
        error = NetworkError("Failed", url="https://api.example.com")
        assert error.url == "https://api.example.com"
