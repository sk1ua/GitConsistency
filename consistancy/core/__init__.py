"""GitNexus MCP 核心封装模块.

提供与 GitNexus MCP 服务器的异步通信、缓存管理和错误处理。
"""

from consistancy.core.cache import GitNexusCache
from consistancy.core.gitnexus_client import (
    GitNexusClient,
    GitNexusConnectionError,
    GitNexusError,
    GitNexusResponseError,
    GitNexusTimeoutError,
    TransportType,
)
from consistancy.core.schema import (
    ChangeDetection,
    CodeEdge,
    CodeNode,
    ContextResult,
    EdgeType,
    ImpactResult,
    KnowledgeGraph,
    Location,
    NodeType,
)

__all__ = [
    # 客户端
    "GitNexusClient",
    "GitNexusError",
    "GitNexusConnectionError",
    "GitNexusTimeoutError",
    "GitNexusResponseError",
    "TransportType",
    # 缓存
    "GitNexusCache",
    # 数据模型
    "KnowledgeGraph",
    "CodeNode",
    "CodeEdge",
    "NodeType",
    "EdgeType",
    "Location",
    "ContextResult",
    "ImpactResult",
    "ChangeDetection",
]
