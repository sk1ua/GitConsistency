"""数据管理器单元测试."""

from pathlib import Path

import pytest

from consistancy.dashboard.data_manager import DataManager, ScanHistory


class TestDataManagerInit:
    """初始化测试."""

    def test_default_init(self, tmp_path: Path) -> None:
        """测试默认初始化."""
        data_dir = tmp_path / "data"
        manager = DataManager(data_dir)

        assert manager.data_dir == data_dir
        assert data_dir.exists()

    def test_creates_directory(self, tmp_path: Path) -> None:
        """测试创建目录."""
        data_dir = tmp_path / "nested" / "data"
        assert not data_dir.exists()

        DataManager(data_dir)

        assert data_dir.exists()


class TestSaveAndLoad:
    """保存和加载测试."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> DataManager:
        return DataManager(tmp_path / "data")

    def test_save_scan(self, manager: DataManager) -> None:
        """测试保存扫描."""
        scan_data = {
            "summary": {"total_issues": 10},
            "scanners": [],
        }

        manager.save_scan(scan_data, "/path/to/project", 1234.5)

        # 验证文件创建
        assert manager.latest_file.exists()
        assert manager.history_file.exists()

    def test_load_latest(self, manager: DataManager) -> None:
        """测试加载最新."""
        scan_data = {
            "summary": {"total_issues": 5},
            "scanners": [{"name": "security"}],
        }

        manager.save_scan(scan_data, "/project", 1000.0)
        loaded = manager.load_latest()

        assert loaded is not None
        assert loaded["summary"]["total_issues"] == 5
        assert "_meta" in loaded

    def test_load_latest_empty(self, manager: DataManager) -> None:
        """测试加载空数据."""
        loaded = manager.load_latest()
        assert loaded is None

    def test_load_history(self, manager: DataManager) -> None:
        """测试加载历史."""
        # 保存多个扫描
        for i in range(3):
            manager.save_scan(
                {"summary": {"total_issues": i}},
                "/project",
                1000.0,
            )

        history = manager.load_history()

        assert len(history) == 3
        assert all(isinstance(h, ScanHistory) for h in history)


class TestTrendData:
    """趋势数据测试."""

    def test_get_trend_data(self, tmp_path: Path) -> None:
        """测试获取趋势数据."""
        manager = DataManager(tmp_path / "data")

        # 保存一些数据
        for i in range(5):
            manager.save_scan(
                {"summary": {"total_issues": 10 + i}},
                "/project",
                1000.0 + i * 100,
            )

        trend = manager.get_trend_data(days=30)

        assert "dates" in trend
        assert "issues" in trend
        assert "duration" in trend
        assert len(trend["dates"]) == 5

    def test_get_trend_data_empty(self, tmp_path: Path) -> None:
        """测试空趋势数据."""
        manager = DataManager(tmp_path / "data")

        trend = manager.get_trend_data()

        assert trend["dates"] == []
        assert trend["issues"] == []


class TestClearAndExport:
    """清空和导出测试."""

    def test_clear_history(self, tmp_path: Path) -> None:
        """测试清空历史."""
        manager = DataManager(tmp_path / "data")

        manager.save_scan({"summary": {}}, "/project", 1000.0)
        assert manager.latest_file.exists()

        manager.clear_history()

        assert not manager.latest_file.exists()
        assert not manager.history_file.exists()

    def test_export_data(self, tmp_path: Path) -> None:
        """测试导出数据."""
        manager = DataManager(tmp_path / "data")

        manager.save_scan(
            {"summary": {"total_issues": 10}},
            "/project",
            1000.0,
        )

        export_path = tmp_path / "export.json"
        result = manager.export_data(export_path)

        assert result == export_path
        assert export_path.exists()

        import json
        data = json.loads(export_path.read_text())
        assert "exported_at" in data
        assert "latest_scan" in data
