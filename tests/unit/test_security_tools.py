"""Tests for security_tools module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistency.tools.security_tools import SecurityScanTool


class TestSecurityScanTool:
    """Test SecurityScanTool class."""

    def test_initialization(self):
        """Test tool initialization."""
        tool = SecurityScanTool()

        assert tool.name == "security_scan"
        assert "扫描代码中的安全问题" in tool.description
        assert tool.scanner is not None

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful scan execution."""
        tool = SecurityScanTool()

        # Mock scanner response
        mock_result = MagicMock()
        mock_result.findings = [
            MagicMock(
                rule_id="test-rule",
                message="Test finding",
                severity=MagicMock(value="high"),
                line=10,
                file_path=None,
            )
        ]
        mock_result.scanned_files = 1

        with patch.object(
            tool.scanner, "scan", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await tool.execute("code = 'test'", "/path/to/file.py")

        assert result["file"] == "/path/to/file.py"
        assert result["findings_count"] == 1
        assert len(result["findings"]) == 1
        assert result["findings"][0]["rule_id"] == "test-rule"
        assert result["findings"][0]["severity"] == "HIGH"
        assert result["sources"] == ["semgrep", "bandit"]

    @pytest.mark.asyncio
    async def test_execute_with_file_path(self):
        """Test scan with file path containing suffix."""
        tool = SecurityScanTool()

        mock_result = MagicMock()
        mock_result.findings = [
            MagicMock(
                rule_id="python-rule",
                message="Python issue",
                severity=MagicMock(value="medium"),
                line=5,
                file_path=Path("/some/path.py"),
            )
        ]

        with patch.object(
            tool.scanner, "scan", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await tool.execute("def test(): pass", "/project/main.py")

        assert result["findings"][0]["file"] == str(Path("/some/path.py"))

    @pytest.mark.asyncio
    async def test_execute_no_findings(self):
        """Test scan with no findings."""
        tool = SecurityScanTool()

        mock_result = MagicMock()
        mock_result.findings = []

        with patch.object(
            tool.scanner, "scan", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await tool.execute("safe_code = 1", "/path/file.py")

        assert result["findings_count"] == 0
        assert result["findings"] == []

    @pytest.mark.asyncio
    async def test_execute_limits_findings(self):
        """Test that findings are limited to 10."""
        tool = SecurityScanTool()

        mock_result = MagicMock()
        mock_result.findings = [
            MagicMock(
                rule_id=f"rule-{i}",
                message=f"Finding {i}",
                severity=MagicMock(value="low"),
                line=i,
                file_path=None,
            )
            for i in range(15)
        ]

        with patch.object(
            tool.scanner, "scan", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await tool.execute("code", "/path/file.py")

        assert result["findings_count"] == 15
        assert len(result["findings"]) == 10  # Limited to 10

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        """Test handling of scanner exception."""
        tool = SecurityScanTool()

        with patch.object(
            tool.scanner, "scan", new_callable=AsyncMock, side_effect=Exception("Scan failed")
        ):
            result = await tool.execute("code", "/path/file.py")

        assert "error" in result
        assert "Scan failed" in result["error"]
        assert result["findings"] == []

    @pytest.mark.asyncio
    async def test_execute_with_js_file(self):
        """Test scan with JavaScript file."""
        tool = SecurityScanTool()

        mock_result = MagicMock()
        mock_result.findings = []

        with patch.object(
            tool.scanner, "scan", new_callable=AsyncMock, return_value=mock_result
        ) as mock_scan:
            result = await tool.execute("const x = 1;", "/path/script.js")

            # Verify temp file was created with .js extension
            call_args = mock_scan.call_args
            temp_path = call_args[0][0]
            assert temp_path.suffix == ".js"
