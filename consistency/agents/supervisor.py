"""Supervisor Agent - 审查主控."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from consistency.agents.base import AgentResult, BaseAgent, Severity
from consistency.agents.logic_agent import LogicAgent
from consistency.agents.security_agent import SecurityAgent
from consistency.agents.style_agent import StyleAgent
from consistency.agents.synthesis_agent import SynthesisAgent
from consistency.core.gitnexus_client import GitNexusClient
from consistency.reviewer.models import ReviewResult

logger = logging.getLogger(__name__)


class ReviewSupervisor:
    """审查 Supervisor.

    协调多个 Agent 并行执行审查，并综合结果.

    Examples:
        >>> supervisor = ReviewSupervisor()
        >>> result = await supervisor.review(Path("main.py"), code)
        >>> print(result.summary)
    """

    def __init__(
        self,
        gitnexus_client: GitNexusClient,
        enable_security: bool = True,
        enable_logic: bool = True,
        enable_style: bool = True,
        quick_mode: bool = False,
    ) -> None:
        """初始化 Supervisor.

        Args:
            gitnexus_client: GitNexus 客户端（必需）
            enable_security: 启用安全审查
            enable_logic: 启用逻辑审查
            enable_style: 启用风格审查
            quick_mode: 快速模式（仅安全审查）

        Raises:
            ValueError: 如果 gitnexus_client 为 None 或不可用
        """
        if gitnexus_client is None:
            raise ValueError(
                "GitNexus 客户端是必需的。请提供有效的 GitNexusClient 实例。\n"
                "使用指南: npm install -g gitnexus && export CONSISTENCY_GITNEXUS_ENABLED=true"
            )
        if not gitnexus_client.is_available():
            raise ValueError(
                "GitNexus 客户端不可用。请确保:\n"
                "1. 已安装 GitNexus: npm install -g gitnexus\n"
                "2. 已设置环境变量: export CONSISTENCY_GITNEXUS_ENABLED=true"
            )

        self.gitnexus = gitnexus_client
        self.quick_mode = quick_mode

        # 初始化各 Agent
        self.agents: dict[str, Any] = {}

        if quick_mode:
            # 快速模式：仅安全审查
            self.agents["security"] = SecurityAgent(self.gitnexus)
        else:
            # 完整模式
            if enable_security:
                self.agents["security"] = SecurityAgent(self.gitnexus)
            if enable_logic:
                self.agents["logic"] = LogicAgent(self.gitnexus)
            if enable_style:
                self.agents["style"] = StyleAgent(self.gitnexus)

        self.synthesis_agent = SynthesisAgent()

        logger.info(f"Supervisor 初始化完成，Agent: {list(self.agents.keys())}")

    async def review(
        self,
        file_path: Path,
        code: str,
    ) -> ReviewResult:
        """执行完整审查流程.

        Args:
            file_path: 文件路径
            code: 代码内容

        Returns:
            审查结果
        """
        logger.info(f"开始审查: {file_path} (Agent: {list(self.agents.keys())})")

        # 1. 并行执行各 Agent
        agent_tasks = [self._run_agent(name, agent, file_path, code) for name, agent in self.agents.items()]

        agent_results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # 2. 过滤成功的结果
        successful_results: list[AgentResult] = []
        for i, result in enumerate(agent_results):
            agent_name = list(self.agents.keys())[i]

            if isinstance(result, BaseException):
                logger.error(f"{agent_name} 失败: {result}")
                # 创建失败的占位结果
                successful_results.append(
                    AgentResult(
                        agent_name=agent_name,
                        summary=f"{agent_name} 执行失败: {result}",
                        severity=Severity.LOW,
                        comments=[],
                    ),
                )
            else:
                successful_results.append(result)

        # 3. 综合结果
        synthesis_result = await self.synthesis_agent.synthesize(
            successful_results,
            file_path,
        )

        # 4. 转换为 ReviewResult
        return self.synthesis_agent.to_review_result(synthesis_result)

    async def review_batch(
        self,
        files: list[tuple[Path, str]],
        max_concurrency: int = 3,
    ) -> list[ReviewResult]:
        """批量审查多个文件.

        Args:
            files: (文件路径, 代码内容) 列表
            max_concurrency: 最大并发数

        Returns:
            审查结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def review_with_limit(fp: Path, code: str) -> ReviewResult:
            async with semaphore:
                return await self.review(fp, code)

        tasks = [review_with_limit(fp, code) for fp, code in files]
        return await asyncio.gather(*tasks)

    async def _run_agent(
        self,
        name: str,
        agent: BaseAgent,
        file_path: Path,
        code: str,
    ) -> AgentResult:
        """运行单个 Agent.

        Args:
            name: Agent 名称
            agent: Agent 实例
            file_path: 文件路径
            code: 代码内容

        Returns:
            Agent 结果
        """
        logger.debug(f"运行 {name}...")

        try:
            result = await agent.analyze(file_path, code)
            logger.debug(f"{name} 完成: {len(result.comments)} 条发现")
            return result

        except Exception as e:
            logger.exception(f"{name} 异常: {e}")
            raise

    def get_stats(self) -> dict[str, Any]:
        """获取 Supervisor 统计信息."""
        return {
            "agents": list(self.agents.keys()),
            "quick_mode": self.quick_mode,
            "gitnexus_available": self.gitnexus.is_available(),
        }


# 便捷函数
async def review_code(
    file_path: Path,
    code: str,
    gitnexus_client: GitNexusClient,
    quick: bool = False,
) -> ReviewResult:
    """便捷函数：审查代码.

    Args:
        file_path: 文件路径
        code: 代码内容
        gitnexus_client: GitNexus 客户端（必需）
        quick: 是否快速模式

    Returns:
        审查结果
    """
    supervisor = ReviewSupervisor(gitnexus_client=gitnexus_client, quick_mode=quick)
    return await supervisor.review(file_path, code)


async def review_files(
    files: list[tuple[Path, str]],
    gitnexus_client: GitNexusClient,
    quick: bool = False,
) -> list[ReviewResult]:
    """便捷函数：批量审查文件.

    Args:
        files: (文件路径, 代码内容) 列表
        gitnexus_client: GitNexus 客户端（必需）
        quick: 是否快速模式

    Returns:
        审查结果列表
    """
    supervisor = ReviewSupervisor(gitnexus_client=gitnexus_client, quick_mode=quick)
    return await supervisor.review_batch(files)
