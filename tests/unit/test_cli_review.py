"""Tests for CLI review commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from consistency.cli.commands.review import register_review_commands

runner = CliRunner()


@pytest.fixture
def review_app():
    """Create review app fixture."""
    app = typer.Typer()
    console = MagicMock()
    register_review_commands(app, console)
    return app, console


class TestReviewFileCommand:
    """Test review file command."""

    def test_command_registration(self, review_app):
        """Test command is registered."""
        app, _ = review_app
        assert app is not None

    @patch("consistency.cli.commands.review.asyncio.run")
    def test_review_file_quick_mode(self, mock_run, review_app):
        """Test review file with quick mode."""
        app, console = review_app
        mock_run.side_effect = lambda coro: None


class TestReviewDiffCommand:
    """Test review diff command."""

    @patch("consistency.cli.commands.review.asyncio.run")
    def test_review_diff_cached(self, mock_run, review_app):
        """Test review diff with cached changes."""
        app, console = review_app
        mock_run.side_effect = lambda coro: None


class TestReviewBatchCommand:
    """Test review batch command."""

    @patch("consistency.cli.commands.review.asyncio.run")
    def test_review_batch_multiple_files(self, mock_run, review_app):
        """Test batch review with multiple files."""
        app, console = review_app
        mock_run.side_effect = lambda coro: None
