"""综合 Agent."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from consistency.agents.base import AgentResult, BaseAgent
from consistency.config import get_settings
from consistency.reviewer.models import ReviewComment, ReviewResult, Severity

logger = logging.getLogger(__name__)


class SynthesisAgent(BaseAgent):
    """综合 Agent.

    汇总各专项 Agent 的结果，生成最终的审查报告.

    Examples:
        >>> agent = SynthesisAgent()
        >>> results = [security_result, logic_result, style_result]
        >>> final = await agent.synthesize(results)
    """

    def __init__(self) -> None:
        """初始化."""
        super().__init__()
        self.settings = get_settings()

    @property
    def name(self) -> str:
        """Agent 名称."""
        return "SynthesisAgent"

    async def analyze(self, file_path: Path, code: str) -> AgentResult:
        """SynthesisAgent 不直接分析代码."""
        raise NotImplementedError(
            "SynthesisAgent 不直接分析代码，使用 synthesize() 方法",
        )

    async def synthesize(
        self,
        agent_results: list[AgentResult],
        file_path: Path | None = None,
    ) -> AgentResult:
        """综合各 Agent 的结果.

        Args:
            agent_results: 各 Agent 的审查结果
            file_path: 文件路径（可选）

        Returns:
            综合后的审查结果
        """
        start_time = time.perf_counter()

        if not agent_results:
            return AgentResult(
                agent_name=self.name,
                summary="未执行任何审查",
                severity=Severity.LOW,
                comments=[],
            )

        # 1. 汇总所有评论
        all_comments = []
        for result in agent_results:
            all_comments.extend(result.comments)

        # 2. 去重（相同位置的评论合并）
        deduplicated = self._deduplicate_comments(all_comments)

        # 3. 按严重程度排序
        sorted_comments = self._sort_by_severity(deduplicated)

        # 4. 限制评论数量（避免过多）
        limited_comments = sorted_comments[:20]

        # 5. 生成综合摘要
        summary = self._generate_summary(agent_results)

        # 6. 确定总体严重程度
        severity = self._determine_overall_severity(agent_results)

        # 7. 汇总行动项
        all_action_items = []
        for result in agent_results:
            all_action_items.extend(result.action_items)
        action_items = self._deduplicate_action_items(all_action_items)

        # 8. 汇总元数据
        metadata = {
            "agents": [r.agent_name for r in agent_results],
            "total_findings": len(all_comments),
            "deduplicated_findings": len(deduplicated),
            "agent_durations": {r.agent_name: r.duration_ms for r in agent_results},
        }

        duration = (time.perf_counter() - start_time) * 1000

        return AgentResult(
            agent_name=self.name,
            summary=summary,
            severity=severity,
            comments=limited_comments,
            action_items=action_items[:10],  # 限制行动项数量
            metadata=metadata,
            duration_ms=duration,
        )

    def _deduplicate_comments(
        self,
        comments: list[ReviewComment],
    ) -> list[ReviewComment]:
        """去重评论."""
        seen = set()
        unique = []

        for comment in comments:
            # 使用文件、行号、消息作为唯一键
            key = (comment.file, comment.line, comment.message)
            if key not in seen:
                seen.add(key)
                unique.append(comment)

        return unique

    def _sort_by_severity(
        self,
        comments: list[ReviewComment],
    ) -> list[ReviewComment]:
        """按严重程度排序."""
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }

        return sorted(
            comments,
            key=lambda c: severity_order.get(c.severity, 5),
        )

    def _generate_summary(self, agent_results: list[AgentResult]) -> str:
        """生成综合摘要."""
        agent_summaries = []

        for result in agent_results:
            comment_count = len(result.comments)
            agent_summaries.append(
                f"{result.agent_name}: {result.summary} ({comment_count} 条)",
            )

        return " | ".join(agent_summaries)

    def _determine_overall_severity(
        self,
        agent_results: list[AgentResult],
    ) -> Severity:
        """确定总体严重程度."""
        severities = [r.severity for r in agent_results]

        if Severity.CRITICAL in severities:
            return Severity.CRITICAL
        if Severity.HIGH in severities:
            return Severity.HIGH
        if Severity.MEDIUM in severities:
            return Severity.MEDIUM

        return Severity.LOW

    def _deduplicate_action_items(self, items: list[str]) -> list[str]:
        """去重行动项."""
        seen = set()
        unique = []

        for item in items:
            # 简化去重
            key = item.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique

    def to_review_result(self, agent_result: AgentResult) -> ReviewResult:
        """转换为 ReviewResult.

        Args:
            agent_result: Agent 结果

        Returns:
            ReviewResult
        """
        return ReviewResult(
            summary=agent_result.summary,
            severity=agent_result.severity,
            comments=agent_result.comments,
            action_items=agent_result.action_items,
            metadata={
                "synthesized": True,
                "agents": agent_result.metadata.get("agents", []),
                **agent_result.metadata,
            },
        )
