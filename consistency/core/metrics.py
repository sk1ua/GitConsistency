"""性能监控与度量收集.

提供扫描性能、缓存命中率、LLM 使用量等指标的收集和报告。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScanMetrics:
    """扫描度量数据."""

    # 时间指标
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float = 0.0
    duration_ms: float = 0.0

    # 扫描范围
    files_scanned: int = 0
    files_changed: int = 0
    lines_of_code: int = 0

    # 发现问题
    issues_critical: int = 0
    issues_high: int = 0
    issues_medium: int = 0
    issues_low: int = 0
    issues_info: int = 0

    # 扫描器统计
    scanner_errors: int = 0
    scanners_used: list[str] = field(default_factory=list)

    # AI 审查指标
    ai_review_enabled: bool = False
    ai_review_duration_ms: float = 0.0
    llm_tokens_used: int = 0
    llm_model: str = ""

    # 缓存指标
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0

    # Agent 指标
    agents_used: list[str] = field(default_factory=list)
    agent_review_duration_ms: float = 0.0

    def finalize(self) -> None:
        """完成度量收集，计算派生指标."""
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000

        total_cache = self.cache_hits + self.cache_misses
        if total_cache > 0:
            self.cache_hit_rate = self.cache_hits / total_cache

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON 字符串."""
        return json.dumps(self.to_dict(), indent=2)


class MetricsCollector:
    """度量收集器.

    收集和汇总扫描过程中的各项指标。

    Examples:
        >>> collector = MetricsCollector()
        >>> collector.start_scan()
        >>> # ... 执行扫描 ...
        >>> collector.record_files_scanned(45)
        >>> collector.record_issues_found(critical=1, high=3)
        >>> metrics = collector.finalize()
        >>> print(f"扫描耗时: {metrics.duration_ms}ms")
    """

    def __init__(self) -> None:
        """初始化度量收集器."""
        self.metrics = ScanMetrics()
        self._scanner_times: dict[str, float] = {}

    def start_scan(self) -> None:
        """开始扫描计时."""
        self.metrics.start_time = time.perf_counter()
        logger.debug("度量收集: 开始扫描")

    def record_files_scanned(self, count: int, changed_only: bool = False) -> None:
        """记录扫描文件数.

        Args:
            count: 扫描的文件数
            changed_only: 是否为增量扫描
        """
        self.metrics.files_scanned = count
        if changed_only:
            self.metrics.files_changed = count
        logger.debug(f"度量收集: 扫描了 {count} 个文件")

    def record_lines_of_code(self, loc: int) -> None:
        """记录代码行数.

        Args:
            loc: 代码行数
        """
        self.metrics.lines_of_code = loc

    def record_issues_found(
        self,
        critical: int = 0,
        high: int = 0,
        medium: int = 0,
        low: int = 0,
        info: int = 0,
    ) -> None:
        """记录发现的问题数.

        Args:
            critical: 严重问题数
            high: 高优先级问题数
            medium: 中优先级问题数
            low: 低优先级问题数
            info: 信息级别问题数
        """
        self.metrics.issues_critical += critical
        self.metrics.issues_high += high
        self.metrics.issues_medium += medium
        self.metrics.issues_low += low
        self.metrics.issues_info += info

    def record_scanner_used(self, scanner_name: str, duration_ms: float) -> None:
        """记录使用的扫描器.

        Args:
            scanner_name: 扫描器名称
            duration_ms: 扫描耗时
        """
        if scanner_name not in self.metrics.scanners_used:
            self.metrics.scanners_used.append(scanner_name)
        self._scanner_times[scanner_name] = duration_ms

    def record_scanner_error(self) -> None:
        """记录扫描器错误."""
        self.metrics.scanner_errors += 1

    def record_ai_review(
        self,
        duration_ms: float,
        tokens_used: int = 0,
        model: str = "",
    ) -> None:
        """记录 AI 审查指标.

        Args:
            duration_ms: AI 审查耗时
            tokens_used: 使用的 token 数
            model: 使用的模型
        """
        self.metrics.ai_review_enabled = True
        self.metrics.ai_review_duration_ms = duration_ms
        self.metrics.llm_tokens_used = tokens_used
        self.metrics.llm_model = model

    def record_agents_used(self, agent_names: list[str], duration_ms: float) -> None:
        """记录使用的 Agents.

        Args:
            agent_names: Agent 名称列表
            duration_ms: Agent 审查耗时
        """
        self.metrics.agents_used = agent_names
        self.metrics.agent_review_duration_ms = duration_ms

    def record_cache_hit(self) -> None:
        """记录缓存命中."""
        self.metrics.cache_hits += 1

    def record_cache_miss(self) -> None:
        """记录缓存未命中."""
        self.metrics.cache_misses += 1

    def finalize(self) -> ScanMetrics:
        """完成度量收集.

        Returns:
            完整的度量数据
        """
        self.metrics.finalize()
        logger.info(
            f"度量收集完成: 扫描 {self.metrics.files_scanned} 个文件, "
            f"发现 {self.metrics.issues_critical + self.metrics.issues_high} 个高严重问题, "
            f"耗时 {self.metrics.duration_ms:.0f}ms"
        )
        return self.metrics

    def save(self, output_path: Path) -> None:
        """保存度量到文件.

        Args:
            output_path: 输出路径
        """
        output_path.write_text(self.metrics.to_json(), encoding="utf-8")
        logger.debug(f"度量已保存到: {output_path}")


def format_metrics_for_summary(metrics: ScanMetrics) -> str:
    """格式化度量为 Markdown 表格.

    Args:
        metrics: 度量数据

    Returns:
        Markdown 格式的表格
    """
    lines = [
        "## 📊 Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Duration | {metrics.duration_ms:.0f}ms |",
        f"| Files Scanned | {metrics.files_scanned} |",
    ]

    if metrics.files_changed > 0:
        lines.append(f"| Files Changed | {metrics.files_changed} |")

    if metrics.lines_of_code > 0:
        lines.append(f"| Lines of Code | {metrics.lines_of_code:,} |")

    lines.extend([
        f"| Critical Issues | {metrics.issues_critical} |",
        f"| High Issues | {metrics.issues_high} |",
        f"| Medium Issues | {metrics.issues_medium} |",
        f"| Cache Hit Rate | {metrics.cache_hit_rate:.1%} |",
    ])

    if metrics.ai_review_enabled:
        lines.extend([
            "",
            "### 🤖 AI Review Metrics",
            f"- Duration: {metrics.ai_review_duration_ms:.0f}ms",
        ])
        if metrics.llm_tokens_used > 0:
            lines.append(f"- Tokens Used: {metrics.llm_tokens_used:,}")
        if metrics.llm_model:
            lines.append(f"- Model: `{metrics.llm_model}`")

    if metrics.agents_used:
        lines.extend([
            "",
            f"### 🎯 Agents Used ({len(metrics.agents_used)})",
        ])
        for agent in metrics.agents_used:
            lines.append(f"- {agent}")

    return "\n".join(lines)


def format_metrics_for_github_output(metrics: ScanMetrics) -> dict[str, str]:
    """格式化度量为 GitHub Actions 输出变量.

    Args:
        metrics: 度量数据

    Returns:
        输出变量字典
    """
    return {
        "scan_duration_ms": str(int(metrics.duration_ms)),
        "files_scanned": str(metrics.files_scanned),
        "issues_critical": str(metrics.issues_critical),
        "issues_high": str(metrics.issues_high),
        "issues_medium": str(metrics.issues_medium),
        "issues_low": str(metrics.issues_low),
        "issues_total": str(
            metrics.issues_critical
            + metrics.issues_high
            + metrics.issues_medium
            + metrics.issues_low
            + metrics.issues_info
        ),
        "cache_hit_rate": f"{metrics.cache_hit_rate:.2f}",
        "ai_review_enabled": str(metrics.ai_review_enabled).lower(),
    }
