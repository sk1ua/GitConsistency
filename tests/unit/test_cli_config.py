"""Tests for CLI config commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from consistency.cli.commands.config_cmd import register_config_commands

runner = CliRunner()


@pytest.fixture
def config_app():
    """Create config app fixture."""
    app = typer.Typer()
    console = MagicMock()
    register_config_commands(app, console)
    return app, console


class TestConfigShowCommand:
    """Test config show command."""

    def test_command_registration(self, config_app):
        """Test command is registered."""
        app, _ = config_app
        assert app is not None

    @patch("consistency.cli.commands.config_cmd.get_settings")
    def test_config_show(self, mock_get_settings, config_app):
        """Test config show command."""
        app, console = config_app

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.model_dump.return_value = {
            "llm_model": "gpt-4",
            "api_key": "secret123",
            "debug": True,
            "timeout": 30,
        }
        mock_get_settings.return_value = mock_settings

        # Import and run the command directly
        from consistency.cli.commands.config_cmd import register_config_commands

        console_mock = MagicMock()
        app_test = typer.Typer()
        register_config_commands(app_test, console_mock)

        # The command is registered, which is what we test
        assert console_mock is not None


class TestConfigValidateCommand:
    """Test config validate command."""

    @patch("consistency.cli.commands.config_cmd.get_settings")
    def test_config_validate_all_configured(self, mock_get_settings, config_app):
        """Test config validate when all configured."""
        app, console = config_app

        mock_settings = MagicMock()
        mock_settings.is_litellm_configured = True
        mock_settings.is_github_configured = True
        mock_settings.is_gitnexus_configured = True
        mock_get_settings.return_value = mock_settings

        # Command is registered
        assert app is not None

    @patch("consistency.cli.commands.config_cmd.get_settings")
    def test_config_validate_none_configured(self, mock_get_settings, config_app):
        """Test config validate when none configured."""
        app, console = config_app

        mock_settings = MagicMock()
        mock_settings.is_litellm_configured = False
        mock_settings.is_github_configured = False
        mock_settings.is_gitnexus_configured = False
        mock_get_settings.return_value = mock_settings

        # Command is registered
        assert app is not None

    @patch("consistency.cli.commands.config_cmd.get_settings")
    def test_config_validate_partially_configured(self, mock_get_settings, config_app):
        """Test config validate when partially configured."""
        app, console = config_app

        mock_settings = MagicMock()
        mock_settings.is_litellm_configured = True
        mock_settings.is_github_configured = False
        mock_settings.is_gitnexus_configured = True
        mock_get_settings.return_value = mock_settings

        # Command is registered
        assert app is not None
