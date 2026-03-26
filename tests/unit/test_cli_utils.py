"""Tests for CLI utils module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from consistency.cli.utils import get_git_commit_sha


class TestGetGitCommitSha:
    """Test get_git_commit_sha function."""

    @patch("consistency.cli.utils.subprocess.run")
    def test_successful_git_command(self, mock_run):
        """Test successful git command."""
        mock_result = MagicMock()
        mock_result.stdout = "abc123def456\n"
        mock_run.return_value = mock_result

        result = get_git_commit_sha(Path("/some/path"))

        assert result == "abc123def456"
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "git"

    @patch("consistency.cli.utils.subprocess.run")
    def test_empty_output(self, mock_run):
        """Test empty git output returns unknown."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = get_git_commit_sha(Path("/some/path"))

        assert result == "unknown"

    @patch("consistency.cli.utils.subprocess.run")
    def test_git_command_failure(self, mock_run):
        """Test git command failure returns unknown."""
        mock_run.side_effect = Exception("Git not found")

        result = get_git_commit_sha(Path("/some/path"))

        assert result == "unknown"

    @patch("consistency.cli.utils.subprocess.run")
    def test_whitespace_stripping(self, mock_run):
        """Test whitespace is stripped from output."""
        mock_result = MagicMock()
        mock_result.stdout = "  abc123  \n\n"
        mock_run.return_value = mock_result

        result = get_git_commit_sha(Path("/some/path"))

        assert result == "abc123"
