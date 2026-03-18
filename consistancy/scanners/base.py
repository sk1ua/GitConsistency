"""扫描器基类和通用类型定义."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """问题严重程度等级."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Finding:
    """单个发现的问题.

    Attributes:
        rule_id: 规则标识
        message: 问题描述
        severity: 严重程度
        file_path: 文件路径
        line: 行号
        column: 列号
        code_snippet: 相关代码片段
        confidence: 置信度（0-1）
        metadata: 额外元数据
    """

    rule_id: str
    message: str
    severity: Severity
    file_path: Path | None = None
    line: int | None = None
    column: int | None = None
    code_snippet: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """扫描结果.

    Attributes:
        scanner_name: 扫描器名称
        findings: 发现的问题列表
        duration_ms: 扫描耗时（毫秒）
        scanned_files: 扫描的文件数
        errors: 扫描过程中的错误
    """

    scanner_name: str
    findings: list[Finding] = field(default_factory=list)
    duration_ms: float = 0.0
    scanned_files: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        """返回问题统计摘要."""
        counts = {s.value: 0 for s in Severity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts


class BaseScanner(ABC):
    """扫描器抽象基类.

    所有扫描器必须继承此类并实现 scan 方法。
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化扫描器.

        Args:
            config: 扫描器配置
        """
        self.config = config or {}

    @abstractmethod
    async def scan(self, path: Path) -> ScanResult:
        """执行扫描.

        Args:
            path: 扫描目标路径

        Returns:
            扫描结果
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """扫描器名称."""
        raise NotImplementedError
