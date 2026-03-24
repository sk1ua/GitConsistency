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
from consistency.core.metrics import MetricsCollector, ScanMetrics
from consistency.core.schema import ContextResult
from consistency.core.self_hosted import (
    SelfHostedConfig,
    detect_runner_capabilities,
    is_self_hosted_runner,
    optimize_for_self_hosted,
)

__all__ = [
    "ContextResult",
    "GitNexusCache",
    "GitNexusClient",
    "GitNexusContext",
    "GitNexusError",
    "GitNexusQueryResult",
    "get_gitnexus_client",
    # Metrics
    "MetricsCollector",
    "ScanMetrics",
    # Self-hosted
    "SelfHostedConfig",
    "detect_runner_capabilities",
    "is_self_hosted_runner",
    "optimize_for_self_hosted",
]
