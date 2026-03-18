"""一致性漂移检测器单元测试."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistancy.scanners.base import Severity
from consistancy.scanners.drift_detector import (
    DriftDetector,
    DriftResult,
    StylePattern,
)


class TestDriftDetectorInit:
    """初始化测试."""

    def test_default_init(self) -> None:
        """测试默认初始化."""
        detector = DriftDetector()
        assert detector.name == "drift"
        assert detector.threshold == 0.75
        assert detector.zscore_threshold == 2.0
        assert detector.embedding_model_name == "all-MiniLM-L6-v2"

    def test_custom_init(self) -> None:
        """测试自定义初始化."""
        detector = DriftDetector(
            embedding_model="model-x",
            threshold=0.8,
            zscore_threshold=1.5,
        )
        assert detector.threshold == 0.8
        assert detector.zscore_threshold == 1.5
        assert detector.embedding_model_name == "model-x"


class TestNamingStyleAnalysis:
    """命名风格分析测试."""

    @pytest.fixture
    def detector(self) -> DriftDetector:
        return DriftDetector()

    def test_classify_snake_case(self, detector: DriftDetector) -> None:
        """测试 snake_case 识别."""
        assert detector._classify_naming_style("my_function") == "snake_case"
        assert detector._classify_naming_style("private_var") == "snake_case"

    def test_classify_camel_case(self, detector: DriftDetector) -> None:
        """测试 camelCase 识别."""
        assert detector._classify_naming_style("myFunction") == "camelCase"
        assert detector._classify_naming_style("doSomething") == "camelCase"

    def test_classify_pascal_case(self, detector: DriftDetector) -> None:
        """测试 PascalCase 识别."""
        assert detector._classify_naming_style("MyClass") == "PascalCase"
        assert detector._classify_naming_style("HTTPResponse") == "PascalCase"

    def test_classify_unknown(self, detector: DriftDetector) -> None:
        """测试未知风格."""
        assert detector._classify_naming_style("ALL_CAPS") == "unknown"


class TestPatternExtraction:
    """模式提取测试."""

    @pytest.fixture
    def detector(self) -> DriftDetector:
        return DriftDetector()

    def test_extract_naming_conventions(self, tmp_path: Path, detector: DriftDetector) -> None:
        """测试命名约定提取."""
        # 创建测试文件
        (tmp_path / "test.py").write_text("""
def my_function():
    pass

def another_function():
    pass
""")

        pattern = detector._analyze_naming_conventions(tmp_path)

        assert pattern is not None
        assert pattern.pattern_type == "naming_convention"
        assert "snake_case" in pattern.examples
        assert pattern.frequency > 0.5

    def test_extract_function_signatures(self, tmp_path: Path, detector: DriftDetector) -> None:
        """测试函数签名提取."""
        (tmp_path / "test.py").write_text("""
def typed_func(x: int) -> str:
    return str(x)

def another_typed(y: bool) -> int:
    return 1
""")

        pattern = detector._analyze_function_signatures(tmp_path)

        assert pattern is not None
        assert pattern.pattern_type == "function_signature"
        # 应该识别为有类型注解

    def test_extract_error_handling(self, tmp_path: Path, detector: DriftDetector) -> None:
        """测试异常处理风格提取."""
        (tmp_path / "test.py").write_text("""
try:
    risky_op()
except:
    pass

try:
    another_op()
except ValueError:
    pass
""")

        pattern = detector._analyze_error_handling(tmp_path)

        assert pattern is not None
        assert pattern.pattern_type == "error_handling"

    def test_extract_import_style(self, tmp_path: Path, detector: DriftDetector) -> None:
        """测试导入风格提取."""
        (tmp_path / "test.py").write_text("""
import os
import sys
from collections import defaultdict
""")

        pattern = detector._analyze_import_style(tmp_path)

        assert pattern is not None
        assert pattern.pattern_type == "import_style"


class TestDriftDetection:
    """漂移检测测试."""

    @pytest.fixture
    def detector(self) -> DriftDetector:
        return DriftDetector()

    def test_check_naming_drift(self, tmp_path: Path, detector: DriftDetector) -> None:
        """测试命名风格漂移检测."""
        pattern = StylePattern(
            pattern_type="naming_convention",
            examples=["snake_case"],
            frequency=0.9,
        )

        lines = [
            "def my_function():",  # 符合
            "    pass",
            "def myFunction():",    # 不符合
            "    pass",
        ]

        drifts = detector._check_naming_drift(tmp_path / "test.py", lines, pattern)

        assert len(drifts) == 1
        assert drifts[0].observed == "camelCase"
        assert drifts[0].expected == "snake_case"
        assert drifts[0].line == 3

    def test_check_signature_drift(self, tmp_path: Path, detector: DriftDetector) -> None:
        """测试签名风格漂移检测."""
        pattern = StylePattern(
            pattern_type="function_signature",
            examples=["typed"],
            frequency=0.8,
        )

        lines = [
            "def typed_func(x: int) -> str:",
            "    pass",
            "def untyped_func(x):",  # 漂移
            "    pass",
        ]

        drifts = detector._check_signature_drift(tmp_path / "test.py", lines, pattern)

        assert len(drifts) == 1
        assert drifts[0].observed == "untyped"
        assert drifts[0].expected == "typed"

    def test_z_score_calculation(self, detector: DriftDetector) -> None:
        """测试 Z-score 计算."""
        z = detector._calculate_z_score(mean=0.8, observed=0.5, std_dev=0.2)
        assert z == -1.5  # (0.5 - 0.8) / 0.2

    def test_z_score_zero_std(self, detector: DriftDetector) -> None:
        """测试零标准差处理."""
        z = detector._calculate_z_score(mean=0.5, observed=0.3, std_dev=0)
        assert z == 0  # 避免除零


class TestDriftToFinding:
    """漂移结果转换测试."""

    @pytest.fixture
    def detector(self) -> DriftDetector:
        return DriftDetector()

    def test_high_confidence_drift(self, detector: DriftDetector) -> None:
        """测试高置信度漂移."""
        drift = DriftResult(
            file_path="src/test.py",
            line=10,
            pattern_type="naming_convention",
            observed="camelCase",
            expected="snake_case",
            confidence=0.95,
            z_score=2.5,
        )

        finding = detector._drift_to_finding(drift)

        assert finding.severity == Severity.HIGH
        assert finding.rule_id == "drift_naming_convention"
        assert "命名风格不一致" in finding.message

    def test_low_confidence_drift(self, detector: DriftDetector) -> None:
        """测试低置信度漂移."""
        drift = DriftResult(
            file_path="src/test.py",
            line=10,
            pattern_type="function_signature",
            observed="untyped",
            expected="typed",
            confidence=0.5,
            z_score=1.0,
        )

        finding = detector._drift_to_finding(drift)

        assert finding.severity == Severity.LOW


class TestScanExecution:
    """扫描执行测试."""

    @pytest.mark.asyncio
    async def test_scan_without_gitnexus(self, tmp_path: Path) -> None:
        """测试无 GitNexus 的扫描."""
        # 创建测试项目结构
        (tmp_path / "main.py").write_text("""
def my_function():
    pass

def myFunction():  # 漂移
    pass
""")

        detector = DriftDetector()
        result = await detector.scan(tmp_path)

        assert result.scanner_name == "drift"
        assert result.scanned_files >= 1
        # 应该检测到命名风格漂移

    @pytest.mark.asyncio
    async def test_scan_with_gitnexus(self, tmp_path: Path) -> None:
        """测试带 GitNexus 的扫描."""
        mock_graph = MagicMock()
        mock_graph.node_count = 100

        mock_client = AsyncMock()
        mock_client.analyze.return_value = mock_graph

        detector = DriftDetector(gitnexus_client=mock_client)

        # 创建测试文件
        (tmp_path / "test.py").write_text("def func(): pass")

        result = await detector.scan(tmp_path)

        # 应该调用 analyze
        mock_client.analyze.assert_called_once()
        assert result.scanner_name == "drift"

    def test_get_pattern_description(self) -> None:
        """测试模式描述获取."""
        detector = DriftDetector()

        assert "命名风格" in detector._get_pattern_description("naming_convention")
        assert "函数签名" in detector._get_pattern_description("function_signature")
        assert "异常处理" in detector._get_pattern_description("error_handling")
        assert "unknown_type" == detector._get_pattern_description("unknown_type")
