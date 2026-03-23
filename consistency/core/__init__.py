"""GitNexus 核心模块.

提供与 GitNexus CLI 的异步通信和缓存管理.
"""

from consistency.core.cache import GitNexusCache
from consistency.core.gitnexus_client import (
    GitNexusClient,
    GitNexusContext,
    GitNexusError,
    GitNexusQueryResult,
    get_gitnexus_client,
)
from consistency.core.schema import ContextResult

__all__ = [
    "ContextResult",
    "GitNexusCache",
    "GitNexusClient",
    "GitNexusContext",
    "GitNexusError",
    "GitNexusQueryResult",
    "get_gitnexus_client",
]
