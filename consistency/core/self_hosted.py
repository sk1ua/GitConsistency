"""自托管 Runner 支持.

提供本地 LLM、离线模式、资源优化等功能，支持在自托管环境中运行。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SelfHostedConfig:
    """自托管配置."""

    # 本地 LLM 配置
    use_local_llm: bool = False
    local_llm_url: str = "http://localhost:11434"  # Ollama 默认地址
    local_llm_model: str = "codellama"

    # 离线模式
    offline_mode: bool = False  # 完全离线，不使用任何外部 API

    # 资源限制
    max_memory_mb: int = 4096  # 最大内存使用
    max_cpu_cores: int = 4  # 最大 CPU 核心数
    max_file_size_mb: int = 10  # 单个文件大小限制

    # 缓存配置
    cache_dir: Path | None = None
    cache_ttl_hours: int = 24

    # 并发控制
    max_concurrent_scans: int = 2
    max_concurrent_agents: int = 2

    @classmethod
    def from_env(cls) -> SelfHostedConfig:
        """从环境变量创建配置."""
        return cls(
            use_local_llm=os.environ.get("CONSISTENCY_USE_LOCAL_LLM", "false").lower() == "true",
            local_llm_url=os.environ.get("CONSISTENCY_LOCAL_LLM_URL", "http://localhost:11434"),
            local_llm_model=os.environ.get("CONSISTENCY_LOCAL_LLM_MODEL", "codellama"),
            offline_mode=os.environ.get("CONSISTENCY_OFFLINE_MODE", "false").lower() == "true",
            max_memory_mb=int(os.environ.get("CONSISTENCY_MAX_MEMORY_MB", "4096")),
            max_cpu_cores=int(os.environ.get("CONSISTENCY_MAX_CPU_CORES", "4")),
            max_file_size_mb=int(os.environ.get("CONSISTENCY_MAX_FILE_SIZE_MB", "10")),
            cache_dir=Path(os.environ["CONSISTENCY_CACHE_DIR"]) if os.environ.get("CONSISTENCY_CACHE_DIR") else None,
            cache_ttl_hours=int(os.environ.get("CONSISTENCY_CACHE_TTL_HOURS", "24")),
            max_concurrent_scans=int(os.environ.get("CONSISTENCY_MAX_CONCURRENT_SCANS", "2")),
            max_concurrent_agents=int(os.environ.get("CONSISTENCY_MAX_CONCURRENT_AGENTS", "2")),
        )

    def validate(self) -> list[str]:
        """验证配置.

        Returns:
            错误信息列表（空列表表示验证通过）
        """
        errors = []

        if self.use_local_llm and not self.offline_mode:
            # 检查本地 LLM 是否可用
            try:
                import urllib.request

                req = urllib.request.Request(
                    f"{self.local_llm_url}/api/tags",
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status != 200:
                        errors.append(f"Local LLM not responding at {self.local_llm_url}")
            except Exception as e:
                errors.append(f"Cannot connect to local LLM at {self.local_llm_url}: {e}")

        if self.cache_dir and not self.cache_dir.exists():
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"Cannot create cache directory {self.cache_dir}: {e}")

        return errors


def is_self_hosted_runner() -> bool:
    """检测是否在自托管 Runner 上运行.

    Returns:
        True 如果是自托管环境
    """
    # GitHub-hosted runners 有特定的 runner 名称
    github_hosted_prefixes = (
        "GitHub Actions",
        "Hosted Agent",
    )

    runner_name = os.environ.get("RUNNER_NAME", "")
    runner_environment = os.environ.get("RUNNER_ENVIRONMENT", "")

    # 如果是 GitHub-hosted，返回 False
    if any(prefix in runner_name for prefix in github_hosted_prefixes):
        return False

    # 如果明确标记为 self-hosted
    if runner_environment == "self-hosted":
        return True

    # 如果存在自托管配置变量，认为是自托管
    if os.environ.get("CONSISTENCY_SELF_HOSTED"):
        return True

    return False


def detect_runner_capabilities() -> dict[str, Any]:
    """检测 Runner 能力.

    Returns:
        Runner 能力信息字典
    """
    import multiprocessing
    import platform

    capabilities = {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "cpu_count": multiprocessing.cpu_count(),
        "is_self_hosted": is_self_hosted_runner(),
    }

    # 检测 GPU
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            capabilities["gpu"] = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        capabilities["gpu"] = None

    # 检测内存
    try:
        import psutil

        mem = psutil.virtual_memory()
        capabilities["memory_total_gb"] = mem.total / (1024**3)
        capabilities["memory_available_gb"] = mem.available / (1024**3)
    except ImportError:
        capabilities["memory_total_gb"] = None
        capabilities["memory_available_gb"] = None

    # 检测本地 LLM
    config = SelfHostedConfig.from_env()
    if config.use_local_llm:
        try:
            import urllib.request

            req = urllib.request.Request(
                f"{config.local_llm_url}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    capabilities["local_llm"] = "available"
                else:
                    capabilities["local_llm"] = "unavailable"
        except Exception:
            capabilities["local_llm"] = "unavailable"

    return capabilities


def get_resource_limits(config: SelfHostedConfig | None = None) -> dict[str, int]:
    """获取资源限制.

    Args:
        config: 自托管配置

    Returns:
        资源限制字典
    """
    if config is None:
        config = SelfHostedConfig.from_env()

    return {
        "max_memory_mb": config.max_memory_mb,
        "max_cpu_cores": config.max_cpu_cores,
        "max_file_size_bytes": config.max_file_size_mb * 1024 * 1024,
        "max_concurrent_scans": config.max_concurrent_scans,
        "max_concurrent_agents": config.max_concurrent_agents,
    }


def optimize_for_self_hosted(config: SelfHostedConfig | None = None) -> dict[str, Any]:
    """获取自托管优化配置.

    Args:
        config: 自托管配置

    Returns:
        优化后的配置字典
    """
    if config is None:
        config = SelfHostedConfig.from_env()

    optimizations = {
        "use_local_llm": config.use_local_llm,
        "offline_mode": config.offline_mode,
        "max_concurrent": min(config.max_concurrent_scans, config.max_concurrent_agents),
    }

    # 根据可用内存调整批处理大小
    try:
        import psutil

        mem = psutil.virtual_memory()
        available_mb = mem.available / (1024 * 1024)

        if available_mb < 2048:  # < 2GB
            optimizations["batch_size"] = 5
            optimizations["max_workers"] = 1
        elif available_mb < 4096:  # < 4GB
            optimizations["batch_size"] = 10
            optimizations["max_workers"] = 2
        else:
            optimizations["batch_size"] = 20
            optimizations["max_workers"] = config.max_concurrent_scans
    except ImportError:
        optimizations["batch_size"] = 10
        optimizations["max_workers"] = config.max_concurrent_scans

    return optimizations
