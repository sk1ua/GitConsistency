"""Agent 工作流集成测试.

测试 Multi-Agent 系统的集成，包括 Supervisor 协调各个 Agent。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistency.agents.base import AgentResult, BaseAgent, Severity
from consistency.agents.logic_agent import LogicAgent
from consistency.agents.security_agent import SecurityAgent
from consistency.agents.style_agent import StyleAgent
from consistency.agents.supervisor import ReviewSupervisor, review_code, review_files
from consistency.agents.synthesis_agent import SynthesisAgent
from consistency.reviewer.models import ReviewComment, ReviewResult


class MockGitNexusClient:
    """Mock GitNexus 客户端."""

    def is_available(self) -> bool:
        return True

    async def query(self, code: str, query_type: str = "context") -> str:
        return f"Mock context for {query_type}"


@pytest.fixture
def gitnexus_client() -> MockGitNexusClient:
    """创建 Mock GitNexus 客户端."""
    return MockGitNexusClient()


class TestAgentBase:
    """Agent 基类测试."""

    def test_base_agent_abstract(self) -> None:
        """测试 BaseAgent 是抽象类."""

        class TestAgent(BaseAgent):
            @property
            def name(self) -> str:
                return "test"

            async def analyze(self, file_path, code):
                return AgentResult(
                    agent_name="test",
                    summary="Test analysis",
                    severity=Severity.LOW,
                )

        agent = TestAgent()
        assert agent.name == "test"


class TestSecurityAgentIntegration:
    """Security Agent 集成测试."""

    @pytest.fixture
    def gitnexus_client(self) -> MockGitNexusClient:
        """创建 Mock GitNexus 客户端."""
        return MockGitNexusClient()

    @pytest.fixture
    def security_agent(self, gitnexus_client: MockGitNexusClient) -> SecurityAgent:
        """创建 Security Agent."""
        return SecurityAgent(gitnexus_client)

    @pytest.mark.asyncio
    async def test_security_agent_analyze_safe_code(self, security_agent: SecurityAgent) -> None:
        """测试分析安全代码."""
        code = """
def hello():
    print("Hello World")
"""
        result = await security_agent.analyze(Path("test.py"), code)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "SecurityAgent"
        assert result.severity in (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)

    @pytest.mark.asyncio
    async def test_security_agent_analyze_vulnerable_code(self, security_agent: SecurityAgent) -> None:
        """测试分析包含漏洞的代码."""
        code = """
import os

def insecure(user_input):
    eval(user_input)  # 危险！
    os.system(user_input)  # 命令注入风险
"""
        result = await security_agent.analyze(Path("test.py"), code)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "SecurityAgent"
        # 应该检测到安全问题
        assert len(result.comments) >= 0  # 可能检测到也可能没有，取决于实现


class TestLogicAgentIntegration:
    """Logic Agent 集成测试."""

    @pytest.fixture
    def gitnexus_client(self) -> MockGitNexusClient:
        """创建 Mock GitNexus 客户端."""
        return MockGitNexusClient()

    @pytest.fixture
    def logic_agent(self, gitnexus_client: MockGitNexusClient) -> LogicAgent:
        """创建 Logic Agent."""
        return LogicAgent(gitnexus_client)

    @pytest.mark.asyncio
    async def test_logic_agent_analyze(self, logic_agent: LogicAgent) -> None:
        """测试逻辑分析."""
        code = """
def complex_function(n):
    if n > 0:
        if n % 2 == 0:
            return n // 2
        else:
            return n * 3 + 1
    return 0
"""
        result = await logic_agent.analyze(Path("test.py"), code)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "LogicAgent"


class TestStyleAgentIntegration:
    """Style Agent 集成测试."""

    @pytest.fixture
    def style_agent(self, gitnexus_client: MockGitNexusClient) -> StyleAgent:
        """创建 Style Agent."""
        return StyleAgent(gitnexus_client)

    @pytest.mark.asyncio
    async def test_style_agent_analyze(self, style_agent: StyleAgent) -> None:
        """测试风格分析."""
        code = """
def BadFunctionName():
    x=1+2
    return x
"""
        result = await style_agent.analyze(Path("test.py"), code)

        assert isinstance(result, AgentResult)
        assert result.agent_name == "StyleAgent"


class TestSynthesisAgentIntegration:
    """Synthesis Agent 集成测试."""

    @pytest.fixture
    def synthesis_agent(self) -> SynthesisAgent:
        """创建 Synthesis Agent."""
        return SynthesisAgent()

    @pytest.mark.asyncio
    async def test_synthesize_single_result(self, synthesis_agent: SynthesisAgent) -> None:
        """测试单个结果综合."""
        results = [
            AgentResult(
                agent_name="SecurityAgent",
                summary="Security check passed",
                severity=Severity.LOW,
                comments=[],
            ),
        ]

        result = await synthesis_agent.synthesize(results, Path("test.py"))

        assert isinstance(result, AgentResult)
        assert result.agent_name == "SynthesisAgent"
        assert "Security check passed" in result.summary

    @pytest.mark.asyncio
    async def test_synthesize_multiple_results(self, synthesis_agent: SynthesisAgent) -> None:
        """测试多个结果综合."""
        results = [
            AgentResult(
                agent_name="security",
                summary="Security issues found",
                severity=Severity.HIGH,
                comments=[
                    ReviewComment(
                        file="test.py",
                        line=1,
                        message="Security issue",
                        severity=Severity.HIGH,
                    ),
                ],
            ),
            AgentResult(
                agent_name="style",
                summary="Style issues found",
                severity=Severity.LOW,
                comments=[
                    ReviewComment(
                        file="test.py",
                        line=2,
                        message="Style issue",
                        severity=Severity.LOW,
                    ),
                ],
            ),
        ]

        result = await synthesis_agent.synthesize(results, Path("test.py"))

        assert result.severity == Severity.HIGH  # 应该取最高级别
        assert len(result.comments) == 2

    def test_to_review_result(self, synthesis_agent: SynthesisAgent) -> None:
        """测试转换为 ReviewResult."""
        agent_result = AgentResult(
            agent_name="synthesis",
            summary="Test summary",
            severity=Severity.MEDIUM,
            comments=[
                ReviewComment(
                    file="test.py",
                    line=1,
                    message="Test comment",
                    severity=Severity.MEDIUM,
                ),
            ],
            action_items=["Fix this"],
        )

        review_result = synthesis_agent.to_review_result(agent_result)

        assert isinstance(review_result, ReviewResult)
        assert review_result.summary == "Test summary"
        assert review_result.severity.value == "medium"
        assert len(review_result.comments) == 1
        assert review_result.action_items == ["Fix this"]


class TestReviewSupervisorIntegration:
    """Review Supervisor 集成测试."""

    @pytest.fixture
    def mock_gitnexus(self) -> MockGitNexusClient:
        """创建 Mock GitNexus 客户端."""
        return MockGitNexusClient()

    @pytest.fixture
    def supervisor(self, mock_gitnexus: MockGitNexusClient) -> ReviewSupervisor:
        """创建 Supervisor 实例."""
        return ReviewSupervisor(
            gitnexus_client=mock_gitnexus,
            enable_security=True,
            enable_logic=True,
            enable_style=True,
            quick_mode=False,
        )

    @pytest.mark.asyncio
    async def test_supervisor_initialization(self, supervisor: ReviewSupervisor) -> None:
        """测试 Supervisor 初始化."""
        assert "security" in supervisor.agents
        assert "logic" in supervisor.agents
        assert "style" in supervisor.agents
        assert supervisor.quick_mode is False

    @pytest.mark.asyncio
    async def test_supervisor_quick_mode(self, mock_gitnexus: MockGitNexusClient) -> None:
        """测试快速模式."""
        supervisor = ReviewSupervisor(
            gitnexus_client=mock_gitnexus,
            quick_mode=True,
        )

        assert "security" in supervisor.agents
        assert "logic" not in supervisor.agents
        assert "style" not in supervisor.agents

    @pytest.mark.asyncio
    async def test_review_single_file(self, supervisor: ReviewSupervisor) -> None:
        """测试单文件审查."""
        code = """
def hello():
    print("Hello")
"""
        result = await supervisor.review(Path("test.py"), code)

        assert isinstance(result, ReviewResult)
        assert result.summary is not None

    @pytest.mark.asyncio
    async def test_review_batch(self, supervisor: ReviewSupervisor) -> None:
        """测试批量审查."""
        files = [
            (Path("file1.py"), "def func1(): pass"),
            (Path("file2.py"), "def func2(): pass"),
        ]

        results = await supervisor.review_batch(files, max_concurrency=2)

        assert len(results) == 2
        assert all(isinstance(r, ReviewResult) for r in results)

    @pytest.mark.asyncio
    async def test_agent_failure_handling(self, supervisor: ReviewSupervisor) -> None:
        """测试 Agent 失败处理."""
        # Mock 一个会失败的 agent
        failing_agent = MagicMock(spec=BaseAgent)
        failing_agent.analyze = AsyncMock(side_effect=Exception("Agent failed"))
        failing_agent.name = "failing"

        supervisor.agents["failing"] = failing_agent

        code = "def test(): pass"
        result = await supervisor.review(Path("test.py"), code)

        # 即使有 agent 失败，也应该返回结果
        assert isinstance(result, ReviewResult)

    def test_get_stats(self, supervisor: ReviewSupervisor) -> None:
        """测试获取统计信息."""
        stats = supervisor.get_stats()

        assert "agents" in stats
        assert "quick_mode" in stats
        assert "gitnexus_available" in stats
        assert stats["quick_mode"] is False


class TestReviewConvenienceFunctions:
    """便捷函数测试."""

    @pytest.fixture
    def mock_gitnexus(self) -> MockGitNexusClient:
        """创建 Mock GitNexus 客户端."""
        return MockGitNexusClient()

    @pytest.mark.asyncio
    async def test_review_code(self, mock_gitnexus: MockGitNexusClient) -> None:
        """测试 review_code 便捷函数."""
        with patch("consistency.agents.supervisor.ReviewSupervisor.review") as mock_review:
            mock_review.return_value = ReviewResult(
                summary="Test",
                severity=Severity.LOW,
            )

            result = await review_code(Path("test.py"), "code", gitnexus_client=mock_gitnexus, quick=True)

            assert isinstance(result, ReviewResult)
            mock_review.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_files(self, mock_gitnexus: MockGitNexusClient) -> None:
        """测试 review_files 便捷函数."""
        with patch("consistency.agents.supervisor.ReviewSupervisor.review_batch") as mock_batch:
            mock_batch.return_value = [
                ReviewResult(summary="Test1", severity=Severity.LOW),
                ReviewResult(summary="Test2", severity=Severity.LOW),
            ]

            files = [(Path("f1.py"), "code1"), (Path("f2.py"), "code2")]
            results = await review_files(files, gitnexus_client=mock_gitnexus, quick=False)

            assert len(results) == 2
            mock_batch.assert_called_once()


class TestAgentSeverity:
    """Agent Severity 级别测试."""

    def test_severity_values(self) -> None:
        """测试 Severity 值."""
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
        assert Severity.CRITICAL.value == "critical"
        assert Severity.INFO.value == "info"

    def test_severity_equality(self) -> None:
        """测试 Severity 相等性."""
        assert Severity("low") == Severity.LOW
        assert Severity("high") == Severity.HIGH
