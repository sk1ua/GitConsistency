"""技术债务热点分析器单元测试."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistancy.scanners.base import Severity
from consistancy.scanners.hotspot_analyzer import (
    ChangeFrequency,
    ComplexityMetrics,
    Hotspot,
    HotspotAnalyzer,
)


class TestHotspotAnalyzerInit:
    """初始化测试."""

    def test_default_init(self) -> None:
        """测试默认初始化."""
        analyzer = HotspotAnalyzer()
        assert analyzer.name == "hotspot"
        assert analyzer.complexity_threshold == "C"
        assert analyzer.lookback_days == 90
        assert analyzer.max_cc == 20

    def test_custom_init(self) -> None:
        """测试自定义初始化."""
        analyzer = HotspotAnalyzer(
            complexity_threshold="A",
            lookback_days=30,
        )
        assert analyzer.complexity_threshold == "A"
        assert analyzer.lookback_days == 30
        assert analyzer.max_cc == 5  # A 对应的阈值

    def test_threshold_mapping(self) -> None:
        """测试阈值映射."""
        test_cases = [
            ("A", 5),
            ("B", 10),
            ("C", 20),
            ("D", 30),
            ("E", 40),
            ("F", 50),
        ]

        for threshold, expected_cc in test_cases:
            analyzer = HotspotAnalyzer(complexity_threshold=threshold)
            assert analyzer.max_cc == expected_cc


class TestComplexityAnalysis:
    """复杂度分析测试."""

    @pytest.fixture
    def analyzer(self) -> HotspotAnalyzer:
        return HotspotAnalyzer()

    @pytest.mark.asyncio
    async def test_basic_complexity_basic(self, tmp_path: Path, analyzer: HotspotAnalyzer) -> None:
        """测试基础复杂度分析."""
        # 创建测试文件
        (tmp_path / "simple.py").write_text("""
def simple():
    return 1
""")

        (tmp_path / "complex.py").write_text("""
def complex_func(x):
    if x > 0:
        if x < 10:
            return x
        elif x < 20:
            return x * 2
        else:
            return x * 3
    return 0
""")

        complexity_map = await analyzer._analyze_complexity_basic(tmp_path)

        assert len(complexity_map) == 2

        # simple.py 复杂度较低
        simple_cc = complexity_map[str(tmp_path / "simple.py")].cyclomatic_complexity
        assert simple_cc < 5

        # complex.py 复杂度较高
        complex_cc = complexity_map[str(tmp_path / "complex.py")].cyclomatic_complexity
        assert complex_cc > 5

    def test_mi_calculation(self, tmp_path: Path) -> None:
        """测试可维护性指数计算."""
        analyzer = HotspotAnalyzer()

        metrics = ComplexityMetrics(
            file_path="test.py",
            cyclomatic_complexity=10.0,
            maintainability_index=80.0,
            loc=100,
            comments=20,
        )

        # 高 MI 应该是低风险
        risk = analyzer._determine_risk_level(10.0, metrics)
        assert risk in ["low", "medium"]


class TestChangeFrequency:
    """变更频率测试."""

    @pytest.fixture
    def analyzer(self) -> HotspotAnalyzer:
        return HotspotAnalyzer(lookback_days=30)

    @pytest.mark.asyncio
    async def test_empty_git_repo(self, tmp_path: Path, analyzer: HotspotAnalyzer) -> None:
        """测试无 git 仓库的情况."""
        frequency_map = await analyzer._analyze_change_frequency(tmp_path)

        # 应该返回空 map 但不抛出异常
        assert isinstance(frequency_map, dict)


class TestHotspotCalculation:
    """热点计算测试."""

    @pytest.fixture
    def analyzer(self) -> HotspotAnalyzer:
        return HotspotAnalyzer()

    def test_calculate_hotspots_basic(self, analyzer: HotspotAnalyzer) -> None:
        """测试基本热点计算."""
        complexity_map = {
            "file1.py": ComplexityMetrics(
                file_path="file1.py",
                cyclomatic_complexity=30.0,
                maintainability_index=40.0,
            ),
            "file2.py": ComplexityMetrics(
                file_path="file2.py",
                cyclomatic_complexity=5.0,
                maintainability_index=80.0,
            ),
        }

        frequency_map = {
            "file1.py": ChangeFrequency(
                file_path="file1.py",
                commit_count=20,
                last_modified=datetime.now(),
                authors={"alice", "bob"},
            ),
            "file2.py": ChangeFrequency(
                file_path="file2.py",
                commit_count=2,
                last_modified=datetime.now(),
                authors={"alice"},
            ),
        }

        hotspots = analyzer._calculate_hotspots(complexity_map, frequency_map)

        # file1.py 应该是热点（高复杂度 + 高频变更）
        file1_hotspot = next((h for h in hotspots if h.file_path == "file1.py"), None)
        assert file1_hotspot is not None
        assert file1_hotspot.hotspot_score > 50
        assert file1_hotspot.risk_level in ["high", "critical"]

    def test_hotspot_sorting(self, analyzer: HotspotAnalyzer) -> None:
        """测试热点排序."""
        complexity_map = {
            "high.py": ComplexityMetrics("high.py", 50.0, 20.0),
            "low.py": ComplexityMetrics("low.py", 5.0, 80.0),
        }

        frequency_map = {
            "high.py": ChangeFrequency("high.py", 30, datetime.now()),
            "low.py": ChangeFrequency("low.py", 3, datetime.now()),
        }

        hotspots = analyzer._calculate_hotspots(complexity_map, frequency_map)

        # 应该按分数降序排列
        if len(hotspots) >= 2:
            assert hotspots[0].hotspot_score >= hotspots[1].hotspot_score

    def test_risk_level_determination(self, analyzer: HotspotAnalyzer) -> None:
        """测试风险等级判定."""
        metrics_low = ComplexityMetrics("test.py", 5.0, 80.0)
        metrics_high = ComplexityMetrics("test.py", 40.0, 10.0)

        assert analyzer._determine_risk_level(10.0, metrics_low) == "low"
        assert analyzer._determine_risk_level(100.0, metrics_high) == "critical"


class TestHotspotToFinding:
    """热点转换测试."""

    def test_critical_hotspot(self) -> None:
        """测试严重热点转换."""
        analyzer = HotspotAnalyzer()

        hotspot = Hotspot(
            file_path="src/critical.py",
            complexity=ComplexityMetrics("src/critical.py", 50.0, 10.0),
            frequency=ChangeFrequency(
                "src/critical.py",
                50,
                datetime.now(),
                authors={"a", "b", "c"},
                churn_lines=5000,
            ),
            hotspot_score=150.0,
            risk_level="critical",
        )

        finding = analyzer._hotspot_to_finding(hotspot)

        assert finding.severity == Severity.CRITICAL
        assert finding.rule_id == "hotspot_critical"
        assert "150.0" in finding.message or "150" in finding.message
        assert "50.0" in finding.message or "50" in finding.message

    def test_medium_hotspot(self) -> None:
        """测试中等热点转换."""
        analyzer = HotspotAnalyzer()

        hotspot = Hotspot(
            file_path="src/medium.py",
            complexity=ComplexityMetrics("src/medium.py", 15.0, 60.0),
            frequency=ChangeFrequency(
                "src/medium.py",
                10,
                datetime.now(),
                authors={"a"},
            ),
            hotspot_score=30.0,
            risk_level="medium",
        )

        finding = analyzer._hotspot_to_finding(hotspot)

        assert finding.severity == Severity.MEDIUM
        assert finding.rule_id == "hotspot_medium"


class TestScanExecution:
    """扫描执行测试."""

    @pytest.mark.asyncio
    async def test_scan_empty_directory(self, tmp_path: Path) -> None:
        """测试空目录扫描."""
        analyzer = HotspotAnalyzer()
        result = await analyzer.scan(tmp_path)

        assert result.scanner_name == "hotspot"
        assert result.scanned_files == 0
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_scan_with_files(self, tmp_path: Path) -> None:
        """测试带文件的扫描."""
        # 创建 Python 文件
        (tmp_path / "test.py").write_text("""
def complex_function(x, y, z):
    if x > 0 and y < 10 or z == 5:
        if x < y:
            return x
        elif y < z:
            return y
    return z
""")

        analyzer = HotspotAnalyzer()
        result = await analyzer.scan(tmp_path)

        assert result.scanned_files >= 1
        # 应该有复杂度数据


class TestHotspotsData:
    """热点数据导出测试."""

    def test_get_hotspots_data(self) -> None:
        """测试热点数据获取."""
        analyzer = HotspotAnalyzer()

        findings = [
            MagicMock(
                file_path=Path("file1.py"),
                metadata={
                    "hotspot_score": 100.0,
                    "cyclomatic_complexity": 30.0,
                    "commit_count": 20,
                    "risk_level": "high",
                },
            ),
            MagicMock(
                file_path=Path("file2.py"),
                metadata={
                    "hotspot_score": 50.0,
                    "cyclomatic_complexity": 10.0,
                    "commit_count": 5,
                    "risk_level": "medium",
                },
            ),
        ]

        data = analyzer.get_hotspots_data(findings)

        assert len(data) == 2
        assert data[0]["score"] == 100.0
        assert data[0]["risk"] == "high"
