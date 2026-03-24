"""Agent 基类."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from consistency.reviewer.models import ReviewComment, ReviewResult, Severity

__all__ = ["AgentResult", "BaseAgent", "Severity"]

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Agent 审查结果."""

    agent_name: str
    summary: str
    severity: Severity
    comments: list[ReviewComment] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_review_result(self) -> ReviewResult:
        """转换为 ReviewResult."""
        return ReviewResult(
            summary=self.summary,
            severity=self.severity,
            comments=self.comments,
            action_items=self.action_items,
            metadata={"agent": self.agent_name, **self.metadata},
        )


class BaseAgent(ABC):
    """Agent 基类.

    所有审查 Agent 的抽象基类.

    Examples:
        >>> class MyAgent(BaseAgent):
        ...     @property
        ...     def name(self) -> str:
        ...         return "MyAgent"
        ...
        ...     async def analyze(self, file_path, code) -> AgentResult:
        ...         # 实现审查逻辑
        ...         return AgentResult(...)
    """

    def __init__(self) -> None:
        """初始化 Agent."""
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 名称."""
        ...

    @abstractmethod
    async def analyze(self, file_path: Path, code: str) -> AgentResult:
        """执行代码分析.

        Args:
            file_path: 文件路径
            code: 代码内容

        Returns:
            审查结果
        """
        ...

    async def analyze_batch(
        self,
        files: list[tuple[Path, str]],
    ) -> list[AgentResult]:
        """批量分析多个文件.

        Args:
            files: (文件路径, 代码内容) 列表

        Returns:
            审查结果列表
        """
        import asyncio

        tasks = [self.analyze(fp, code) for fp, code in files]
        return await asyncio.gather(*tasks)
