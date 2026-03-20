"""Dashboard 数据管理.

管理扫描数据、历史记录和缓存.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScanHistory:
    """扫描历史记录."""

    timestamp: str
    project_path: str
    total_issues: int
    severity_counts: dict[str, int]
    duration_ms: float
    commit_sha: str = ""


class DataManager:
    """Dashboard 数据管理器.

    管理扫描结果、历史记录和数据持久化.
    """

    def __init__(self, data_dir: str | Path = "data") -> None:
        """初始化数据管理器.

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.data_dir / "scan_history.json"
        self.latest_file = self.data_dir / "latest_scan.json"

    def save_scan(
        self,
        scan_data: dict[str, Any],
        project_path: str,
        duration_ms: float,
    ) -> None:
        """保存扫描结果.

        Args:
            scan_data: 扫描结果数据
            project_path: 项目路径
            duration_ms: 扫描耗时
        """
        # 添加元数据
        scan_data["_meta"] = {
            "timestamp": datetime.now().isoformat(),
            "project_path": project_path,
            "duration_ms": duration_ms,
        }

        # 保存最新结果
        self.latest_file.write_text(
            json.dumps(scan_data, indent=2),
            encoding="utf-8",
        )

        # 添加到历史
        self._add_to_history(scan_data, project_path, duration_ms)

        logger.info(f"扫描结果已保存: {self.latest_file}")

    def _add_to_history(
        self,
        scan_data: dict[str, Any],
        project_path: str,
        duration_ms: float,
    ) -> None:
        """添加到历史记录."""
        history = self.load_history()

        summary = scan_data.get("summary", {})
        entry = ScanHistory(
            timestamp=datetime.now().isoformat(),
            project_path=project_path,
            total_issues=summary.get("total_issues", 0),
            severity_counts=summary.get("severity_counts", {}),
            duration_ms=duration_ms,
            commit_sha=scan_data.get("commit_sha", ""),
        )

        history.append(entry)

        # 只保留最近 100 条
        if len(history) > 100:
            history = history[-100:]

        # 保存
        history_data = [
            {
                "timestamp": h.timestamp,
                "project_path": h.project_path,
                "total_issues": h.total_issues,
                "severity_counts": h.severity_counts,
                "duration_ms": h.duration_ms,
                "commit_sha": h.commit_sha,
            }
            for h in history
        ]

        self.history_file.write_text(
            json.dumps(history_data, indent=2),
            encoding="utf-8",
        )

    def load_latest(self) -> dict[str, Any] | None:
        """加载最新扫描结果.

        Returns:
            扫描数据或 None
        """
        if not self.latest_file.exists():
            return None

        try:
            data = json.loads(self.latest_file.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            logger.error(f"加载最新扫描结果失败: {e}")
            return None

    def load_history(self) -> list[ScanHistory]:
        """加载扫描历史.

        Returns:
            历史记录列表
        """
        if not self.history_file.exists():
            return []

        try:
            data = json.loads(self.history_file.read_text(encoding="utf-8"))
            return [
                ScanHistory(
                    timestamp=h["timestamp"],
                    project_path=h["project_path"],
                    total_issues=h["total_issues"],
                    severity_counts=h["severity_counts"],
                    duration_ms=h["duration_ms"],
                    commit_sha=h.get("commit_sha", ""),
                )
                for h in data
            ]
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            return []

    def get_trend_data(self, days: int = 30) -> dict[str, Any]:
        """获取趋势数据.

        Args:
            days: 天数

        Returns:
            趋势数据
        """
        history = self.load_history()

        # 过滤日期
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)

        filtered = [
            h for h in history
            if datetime.fromisoformat(h.timestamp) > cutoff
        ]

        if not filtered:
            return {"dates": [], "issues": [], "duration": []}

        dates = [h.timestamp[:10] for h in filtered]  # YYYY-MM-DD
        issues = [h.total_issues for h in filtered]
        durations = [h.duration_ms / 1000 for h in filtered]  # 转换为秒

        return {
            "dates": dates,
            "issues": issues,
            "duration": durations,
        }

    def clear_history(self) -> None:
        """清空历史记录."""
        if self.history_file.exists():
            self.history_file.unlink()
        if self.latest_file.exists():
            self.latest_file.unlink()
        logger.info("历史记录已清空")

    def export_data(self, output_path: str | Path) -> Path:
        """导出所有数据.

        Args:
            output_path: 输出路径

        Returns:
            输出文件路径
        """
        output_path = Path(output_path)

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "latest_scan": self.load_latest(),
            "history": [
                {
                    "timestamp": h.timestamp,
                    "project_path": h.project_path,
                    "total_issues": h.total_issues,
                    "severity_counts": h.severity_counts,
                }
                for h in self.load_history()
            ],
        }

        output_path.write_text(
            json.dumps(export_data, indent=2),
            encoding="utf-8",
        )

        logger.info(f"数据已导出: {output_path}")
        return output_path
