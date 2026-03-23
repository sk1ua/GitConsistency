"""LangChain 多 Agent 架构.

提供基于 LangChain 的多 Agent 代码审查系统.
"""

from consistency.agents.base import BaseAgent, AgentResult, Severity
from consistency.agents.security_agent import SecurityAgent
from consistency.agents.logic_agent import LogicAgent
from consistency.agents.style_agent import StyleAgent
from consistency.agents.synthesis_agent import SynthesisAgent
from consistency.agents.supervisor import ReviewSupervisor

__all__ = [
    "BaseAgent",
    "AgentResult",
    "Severity",
    "SecurityAgent",
    "LogicAgent",
    "StyleAgent",
    "SynthesisAgent",
    "ReviewSupervisor",
]
