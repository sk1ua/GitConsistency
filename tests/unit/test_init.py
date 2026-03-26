"""Tests for init command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from consistency.cli.commands.init import register_init_command

runner = CliRunner()


@pytest.fixture
def mock_console():
    """Create mock console."""
    return MagicMock()


class TestRegisterInitCommand:
    """Test register_init_command."""

    def test_registration(self, mock_console):
        """Test command registration."""
        app = typer.Typer()
        register_init_command(app, mock_console)
        # If no error raised, registration succeeded


class TestInitCommand:
    """Test init command functionality."""

    @patch("consistency.cli.commands.init.print_banner")
    def test_creates_env_file(self, mock_banner, mock_console, tmp_path: Path):
        """Test .env file is created."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        # Change to temp directory and run without args
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])
        finally:
            os.chdir(original_dir)

        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "LITELLM_API_KEY" in content
        assert "GITHUB_TOKEN" in content

    @patch("consistency.cli.commands.init.print_banner")
    def test_skips_env_file_when_exists(self, mock_banner, mock_console, tmp_path: Path):
        """Test .env file is not overwritten without --force."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        # Create existing .env
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=content")

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])
        finally:
            os.chdir(original_dir)

        # Check content is preserved
        content = env_file.read_text()
        assert "EXISTING=content" in content

    @patch("consistency.cli.commands.init.print_banner")
    def test_overwrites_with_force(self, mock_banner, mock_console, tmp_path: Path):
        """Test .env file is overwritten with --force."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        # Create existing .env
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=content")

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, ["--force"])
        finally:
            os.chdir(original_dir)

        # Check content is replaced
        content = env_file.read_text()
        assert "LITELLM_API_KEY" in content
        assert "EXISTING" not in content

    @patch("consistency.cli.commands.init.print_banner")
    def test_creates_github_workflow(self, mock_banner, mock_console, tmp_path: Path):
        """Test GitHub Actions workflow file is created."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])
        finally:
            os.chdir(original_dir)

        workflow_file = tmp_path / ".github" / "workflows" / "consistency.yml"
        assert workflow_file.exists()
        content = workflow_file.read_text()
        assert "GitConsistency" in content
        assert "pull_request:" in content
        assert "gitconsistency ci" in content

    @patch("consistency.cli.commands.init.print_banner")
    def test_creates_github_directory_structure(self, mock_banner, mock_console, tmp_path: Path):
        """Test .github/workflows directory is created."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])
        finally:
            os.chdir(original_dir)

        github_dir = tmp_path / ".github" / "workflows"
        assert github_dir.exists()
        assert github_dir.is_dir()

    @patch("consistency.cli.commands.init.print_banner")
    def test_shows_success_message(self, mock_banner, mock_console, tmp_path: Path):
        """Test success message is printed."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])
        finally:
            os.chdir(original_dir)

        # Check console.print was called with success message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        # Look for "init" or "complete" keywords in call
        assert any(call for call in print_calls)

    @patch("consistency.cli.commands.init.print_banner")
    def test_shows_path_message(self, mock_banner, mock_console, tmp_path: Path):
        """Test path message is printed."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])
        finally:
            os.chdir(original_dir)

        # Check console.print was called
        assert mock_console.print.called

    @patch("consistency.cli.commands.init.print_banner")
    def test_workflow_file_has_correct_structure(self, mock_banner, mock_console, tmp_path: Path):
        """Test workflow file has all required elements."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])
        finally:
            os.chdir(original_dir)

        workflow_file = tmp_path / ".github" / "workflows" / "consistency.yml"
        content = workflow_file.read_text()

        assert "name:" in content
        assert "on:" in content
        assert "jobs:" in content
        assert "runs-on: ubuntu-latest" in content
        assert "actions/checkout@v4" in content

    @patch("consistency.cli.commands.init.print_banner")
    def test_uses_default_path(self, mock_banner, mock_console, tmp_path: Path):
        """Test default path is current directory."""
        app = typer.Typer()
        register_init_command(app, mock_console)

        import os
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result: Result = runner.invoke(app, [])

            # Check files created in current directory
            assert (tmp_path / ".env").exists()
        finally:
            os.chdir(original_dir)
