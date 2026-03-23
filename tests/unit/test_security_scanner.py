"""安全扫描器单元测试."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistency.scanners.base import Finding, Severity
from consistency.scanners.security_scanner import (
    BanditConfig,
    SecurityScanner,
    SemgrepConfig,
)


class TestSecurityScannerInit:
    """初始化测试."""

    def test_default_init(self) -> None:
        """测试默认初始化."""
        scanner = SecurityScanner()
        assert scanner.name == "security"
        assert scanner.semgrep_config.rules == [
            "p/security-audit",
            "p/owasp-top-ten",
            "p/cwe-top-25",
            "p/ci",
        ]
        assert scanner.bandit_config.severity == "LOW"
        assert not scanner.use_gitnexus

    def test_custom_init(self) -> None:
        """测试自定义初始化."""
        scanner = SecurityScanner(
            semgrep_rules=["custom-rule"],
            bandit_severity="HIGH",
            use_gitnexus=True,
        )
        assert scanner.semgrep_config.rules == ["custom-rule"]
        assert scanner.bandit_config.severity == "HIGH"
        assert scanner.use_gitnexus

    def test_config_override(self) -> None:
        """测试配置覆盖."""
        scanner = SecurityScanner(config={
            "exclude": ["test*.py"],
            "exclude_dirs": ["tests"],
        })
        assert scanner.semgrep_config.exclude == ["test*.py"]
        assert scanner.bandit_config.exclude_dirs == ["tests"]


class TestSemgrepParsing:
    """Semgrep 结果解析测试."""

    @pytest.fixture
    def scanner(self) -> SecurityScanner:
        return SecurityScanner()

    def test_parse_semgrep_match_basic(self, scanner: SecurityScanner) -> None:
        """测试基本结果解析."""
        match = {
            "check_id": "python.lang.security.eval-eval.eval",
            "path": "src/vuln.py",
            "start": {"line": 10, "col": 5},
            "extra": {
                "message": "Dangerous use of eval",
                "severity": "ERROR",
                "lines": "eval(user_input)",
                "metadata": {
                    "cwe": ["CWE-95"],
                    "owasp": ["A1: Injection"],
                    "confidence": "HIGH",
                },
            },
        }

        finding = scanner._parse_semgrep_match(match)

        assert finding is not None
        assert finding.rule_id == "python.lang.security.eval-eval.eval"
        assert finding.severity == Severity.HIGH
        assert finding.file_path == Path("src/vuln.py")
        assert finding.line == 10
        assert finding.metadata["cwe"] == ["CWE-95"]

    def test_parse_semgrep_match_owasp_boost(self, scanner: SecurityScanner) -> None:
        """测试 OWASP 规则严重程度提升."""
        match = {
            "check_id": "owasp.test",
            "path": "src/test.py",
            "start": {"line": 1, "col": 1},
            "extra": {
                "message": "Test",
                "severity": "WARNING",  # 原始为 MEDIUM
                "lines": "code",
                "metadata": {"OWASP": ["A1"]},
            },
        }

        finding = scanner._parse_semgrep_match(match)

        # OWASP 规则应该提升为 HIGH
        assert finding.severity == Severity.HIGH

    def test_parse_semgrep_match_minimal(self, scanner: SecurityScanner) -> None:
        """测试最小数据解析."""
        match = {"invalid": "data"}

        finding = scanner._parse_semgrep_match(match)

        # 代码会尝试用默认值创建 Finding
        assert finding is not None
        assert finding.rule_id == "unknown"


class TestBanditParsing:
    """Bandit 结果解析测试."""

    @pytest.fixture
    def scanner(self) -> SecurityScanner:
        return SecurityScanner()

    def test_parse_bandit_issue_basic(self, scanner: SecurityScanner) -> None:
        """测试基本问题解析."""
        issue = {
            "test_id": "B105",
            "test_name": "hardcoded_password_string",
            "issue_text": "Possible hardcoded password",
            "issue_severity": "HIGH",
            "issue_confidence": "MEDIUM",
            "filename": "src/config.py",
            "line_number": 15,
            "col_offset": 10,
            "code": "password = 'secret123'",
            "more_info": "https://bandit.readthedocs.io/...",
        }

        finding = scanner._parse_bandit_issue(issue)

        assert finding is not None
        assert finding.rule_id == "B105"
        assert finding.severity == Severity.HIGH
        assert finding.file_path == Path("src/config.py")
        assert finding.line == 15

    def test_parse_bandit_issue_severity_map(self, scanner: SecurityScanner) -> None:
        """测试严重程度映射."""
        test_cases = [
            ("LOW", Severity.LOW),
            ("MEDIUM", Severity.MEDIUM),
            ("HIGH", Severity.HIGH),
        ]

        for bandit_sev, expected in test_cases:
            issue = {
                "test_id": "B001",
                "issue_text": "Test",
                "issue_severity": bandit_sev,
                "issue_confidence": "HIGH",
                "filename": "test.py",
                "line_number": 1,
            }
            finding = scanner._parse_bandit_issue(issue)
            assert finding.severity == expected


class TestFindingDeduplication:
    """去重逻辑测试."""

    def test_deduplicate_same_location(self) -> None:
        """测试相同位置的去重."""
        scanner = SecurityScanner()

        findings = [
            Finding(
                rule_id="RULE-1",
                message="Duplicate 1",
                severity=Severity.HIGH,
                file_path=Path("src/file.py"),
                line=10,
            ),
            Finding(
                rule_id="RULE-1",
                message="Duplicate 2",
                severity=Severity.HIGH,
                file_path=Path("src/file.py"),
                line=10,
            ),
            Finding(
                rule_id="RULE-2",
                message="Different rule",
                severity=Severity.HIGH,
                file_path=Path("src/file.py"),
                line=10,
            ),
        ]

        unique = scanner._deduplicate_findings(findings)

        # 应该只剩下2个（RULE-1 去重，RULE-2 保留）
        assert len(unique) == 2

    def test_deduplicate_different_lines(self) -> None:
        """测试不同行号保留."""
        scanner = SecurityScanner()

        findings = [
            Finding(
                rule_id="RULE-1",
                message="Line 10",
                severity=Severity.HIGH,
                file_path=Path("src/file.py"),
                line=10,
            ),
            Finding(
                rule_id="RULE-1",
                message="Line 20",
                severity=Severity.HIGH,
                file_path=Path("src/file.py"),
                line=20,
            ),
        ]

        unique = scanner._deduplicate_findings(findings)

        # 不同行号应该都保留
        assert len(unique) == 2


class TestScanExecution:
    """扫描执行测试."""

    @pytest.mark.asyncio
    async def test_scan_with_mock_results(self) -> None:
        """测试带 Mock 结果的扫描."""
        scanner = SecurityScanner()

        # Mock Semgrep 结果
        semgrep_mock = ([
            Finding(
                rule_id="SEM-001",
                message="Semgrep issue",
                severity=Severity.HIGH,
                file_path=Path("src/file.py"),
                line=1,
            ),
        ], 10, [])

        # Mock Bandit 结果
        bandit_mock = ([
            Finding(
                rule_id="B001",
                message="Bandit issue",
                severity=Severity.MEDIUM,
                file_path=Path("src/file.py"),
                line=2,
            ),
        ], 10, [])

        with patch.object(scanner, "_run_semgrep", new_callable=AsyncMock) as mock_semgrep, \
             patch.object(scanner, "_run_bandit", new_callable=AsyncMock) as mock_bandit:
            
            mock_semgrep.return_value = semgrep_mock
            mock_bandit.return_value = bandit_mock

            result = await scanner.scan(Path("./test"))

            assert result.scanner_name == "security"
            assert len(result.findings) == 2
            assert result.scanned_files == 10

    @pytest.mark.asyncio
    async def test_scan_partial_failure(self) -> None:
        """测试部分失败处理."""
        scanner = SecurityScanner()

        with patch.object(scanner, "_run_semgrep", new_callable=AsyncMock) as mock_semgrep, \
             patch.object(scanner, "_run_bandit", new_callable=AsyncMock) as mock_bandit:
            
            # Semgrep 成功，Bandit 失败
            mock_semgrep.return_value = ([], 5, [])
            mock_bandit.side_effect = Exception("Bandit crashed")

            result = await scanner.scan(Path("./test"))

            # 应该仍然有结果，但有错误记录
            assert len(result.errors) == 1
            assert "Bandit" in result.errors[0]

    @pytest.mark.asyncio
    async def test_enhance_with_context(self) -> None:
        """测试 GitNexus 上下文增强."""
        mock_client = AsyncMock()
        mock_client.context.return_value = MagicMock(
            symbols=[{"name": "user_input", "is_user_input": True}],
        )

        scanner = SecurityScanner(
            use_gitnexus=True,
            gitnexus_client=mock_client,
        )

        findings = [
            Finding(
                rule_id="RULE-1",
                message="Test",
                severity=Severity.MEDIUM,
                file_path=Path("src/file.py"),
                line=10,
                code_snippet="user_input",
            ),
        ]

        enhanced = await scanner._enhance_with_context(findings)

        assert len(enhanced) == 1
        # 应该升级为 HIGH（因为是用户输入）
        assert enhanced[0].severity == Severity.HIGH
