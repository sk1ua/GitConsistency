"""扫描器协调器单元测试."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from consistency.scanners.base import Finding, ScanResult, Severity
from consistency.scanners.orchestrator import ScannerOrchestrator, ScanReport


class TestScanReport:
    """ScanReport 测试."""

    def test_all_findings(self) -> None:
        """测试获取所有发现."""
        report = ScanReport(target_path="./test")
        report.results["scanner1"] = ScanResult(
            scanner_name="scanner1",
            findings=[
                Finding(rule_id="R1", message="Issue 1", severity=Severity.HIGH),
            ],
        )
        report.results["scanner2"] = ScanResult(
            scanner_name="scanner2",
            findings=[
                Finding(rule_id="R2", message="Issue 2", severity=Severity.LOW),
                Finding(rule_id="R3", message="Issue 3", severity=Severity.MEDIUM),
            ],
        )

        all_findings = report.all_findings

        assert len(all_findings) == 3

    def test_summary(self) -> None:
        """测试汇总信息."""
        report = ScanReport(target_path="./test")
        report.results["security"] = ScanResult(
            scanner_name="security",
            findings=[
                Finding(rule_id="R1", message="High", severity=Severity.HIGH),
                Finding(rule_id="R2", message="Medium", severity=Severity.MEDIUM),
            ],
        )

        summary = report.summary

        assert summary["total_findings"] == 2
        assert summary["scanner_counts"]["security"] == 2
        assert summary["severity_counts"]["high"] == 1
        assert summary["severity_counts"]["medium"] == 1


class TestScannerOrchestrator:
    """ScannerOrchestrator 测试."""

    def test_init(self) -> None:
        """测试初始化."""
        orchestrator = ScannerOrchestrator()
        assert orchestrator._scanners == {}

    def test_register_scanner(self) -> None:
        """测试注册扫描器."""
        orchestrator = ScannerOrchestrator()
        mock_scanner = MagicMock()
        mock_scanner.name = "test"

        orchestrator.register_scanner("test_scanner", mock_scanner)

        assert "test_scanner" in orchestrator._scanners

    def test_create_default_scanners_without_settings(self) -> None:
        """测试无配置时创建默认扫描器."""
        orchestrator = ScannerOrchestrator()
        orchestrator.create_default_scanners()

        assert "security" in orchestrator._scanners

    @pytest.mark.asyncio
    async def test_scan_single_scanner(self) -> None:
        """测试单个扫描器扫描."""
        orchestrator = ScannerOrchestrator()

        mock_scanner = MagicMock()
        mock_scanner.scan = AsyncMock(return_value=ScanResult(
            scanner_name="test",
            findings=[Finding(rule_id="R1", message="Test", severity=Severity.HIGH)],
        ))

        orchestrator.register_scanner("test", mock_scanner)

        report = await orchestrator.scan(Path("./test"))

        assert report.target_path == str(Path("./test"))
        assert "test" in report.results
        assert len(report.results["test"].findings) == 1

    @pytest.mark.asyncio
    async def test_scan_multiple_scanners(self) -> None:
        """测试多个扫描器并行扫描."""
        orchestrator = ScannerOrchestrator()

        for name in ["s1", "s2", "s3"]:
            mock_scanner = MagicMock()
            mock_scanner.scan = AsyncMock(return_value=ScanResult(
                scanner_name=name,
                findings=[],
            ))
            orchestrator.register_scanner(name, mock_scanner)

        report = await orchestrator.scan(Path("./test"))

        assert len(report.results) == 3
        assert all(name in report.results for name in ["s1", "s2", "s3"])

    @pytest.mark.asyncio
    async def test_scan_with_skip(self) -> None:
        """测试跳过指定扫描器."""
        orchestrator = ScannerOrchestrator()

        for name in ["s1", "s2", "s3"]:
            mock_scanner = MagicMock()
            mock_scanner.scan = AsyncMock(return_value=ScanResult(
                scanner_name=name,
                findings=[],
            ))
            orchestrator.register_scanner(name, mock_scanner)

        report = await orchestrator.scan(Path("./test"), skip_scanners=["s2"])

        assert "s1" in report.results
        assert "s2" not in report.results
        assert "s3" in report.results

    @pytest.mark.asyncio
    async def test_scan_with_specific_scanners(self) -> None:
        """测试指定扫描器列表."""
        orchestrator = ScannerOrchestrator()

        for name in ["s1", "s2", "s3"]:
            mock_scanner = MagicMock()
            mock_scanner.scan = AsyncMock(return_value=ScanResult(
                scanner_name=name,
                findings=[],
            ))
            orchestrator.register_scanner(name, mock_scanner)

        report = await orchestrator.scan(Path("./test"), scanners=["s1", "s3"])

        assert "s1" in report.results
        assert "s2" not in report.results
        assert "s3" in report.results

    @pytest.mark.asyncio
    async def test_scan_partial_failure(self) -> None:
        """测试部分扫描器失败."""
        orchestrator = ScannerOrchestrator()

        # 成功的扫描器
        success_scanner = MagicMock()
        success_scanner.scan = AsyncMock(return_value=ScanResult(
            scanner_name="success",
            findings=[],
        ))

        # 失败的扫描器
        fail_scanner = MagicMock()
        fail_scanner.scan = AsyncMock(side_effect=Exception("Scanner failed"))

        orchestrator.register_scanner("success", success_scanner)
        orchestrator.register_scanner("fail", fail_scanner)

        report = await orchestrator.scan(Path("./test"))

        assert "success" in report.results
        assert "fail" not in report.results
        assert len(report.errors) == 1
        assert "Scanner failed" in report.errors[0]

    def test_get_scanner_info(self) -> None:
        """测试获取扫描器信息."""
        orchestrator = ScannerOrchestrator()

        mock_scanner = MagicMock()
        mock_scanner.name = "test_scanner"
        mock_scanner.config = {"key": "value"}

        orchestrator.register_scanner("test", mock_scanner)

        info = orchestrator.get_scanner_info()

        assert "test" in info
        assert info["test"]["name"] == "test_scanner"
