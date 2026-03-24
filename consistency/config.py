"""GitConsistency 配置管理.

使用 Pydantic Settings 实现环境变量、.env 文件和默认值的统一管理。
采用嵌套配置类结构，提高可维护性。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    """LLM (LiteLLM) 配置."""

    model_config = {"extra": "ignore"}

    api_key: str | None = Field(default=None, description="LiteLLM API Key")
    model: str = Field(
        default="deepseek/deepseek-chat",
        description="默认 LLM 模型 (LiteLLM 格式)",
    )
    fallback_model: str = Field(
        default="anthropic/claude-3-haiku-20240307",
        description="备选模型",
    )
    temperature: float = Field(default=0.3, ge=0.0, le=1.0, description="采样温度")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大生成 token 数")
    timeout: int = Field(default=60, ge=1, description="请求超时（秒）")


class GitHubConfig(BaseModel):
    """GitHub 集成配置."""

    model_config = {"extra": "ignore"}

    token: str | None = Field(default=None, description="GitHub Personal Access Token")
    delete_old_comments: bool = Field(default=True, description="是否删除旧评论")
    comment_signature: str = Field(
        default="<!-- GitConsistency Code Review -->",
        description="PR 评论签名",
    )


class GitNexusConfig(BaseModel):
    """GitNexus MCP 配置."""

    model_config = {"extra": "ignore"}

    mcp_url: str | None = Field(default=None, description="GitNexus MCP SSE 端点 URL")
    mcp_command: str | None = Field(default=None, description="GitNexus MCP 命令（stdio 模式）")
    mcp_args: list[str] = Field(default_factory=list, description="GitNexus MCP 命令参数")
    cache_dir: Path = Field(default=Path(".cache/gitnexus"), description="GitNexus 缓存目录")
    cache_ttl: int = Field(default=3600, ge=0, description="缓存 TTL（秒）")


class ScannerConfig(BaseModel):
    """安全扫描器配置."""

    model_config = {"extra": "ignore"}

    semgrep_rules: list[str] = Field(
        default_factory=lambda: ["p/security-audit", "p/owasp-top-ten", "p/cwe-top-25"],
        description="Semgrep 规则集",
    )
    bandit_severity: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        default="LOW",
        description="Bandit 最低严重级别",
    )


class CacheConfig(BaseModel):
    """缓存配置."""

    model_config = {"extra": "ignore"}

    dir: Path = Field(default=Path(".cache"), description="全局缓存目录")
    max_size: int = Field(default=1000, ge=100, description="缓存最大大小（MB）")
    enable_memory: bool = Field(default=True, description="是否启用内存缓存")
    ttl: int = Field(default=3600, ge=0, description="缓存 TTL（秒）")


class LoggingConfig(BaseModel):
    """日志配置."""

    model_config = {"extra": "ignore"}

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志级别",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式",
    )


class PerformanceConfig(BaseModel):
    """性能配置."""

    model_config = {"extra": "ignore"}

    worker_threads: int = Field(default=0, ge=0, description="工作线程数（0=自动）")
    max_concurrent: int = Field(default=5, ge=1, description="最大并发请求数")


class Settings(BaseSettings):
    """GitConsistency 全局配置类.

    所有配置项都可以通过环境变量或 .env 文件设置。
    使用嵌套配置组织相关参数。

    Examples:
        >>> settings = get_settings()
        >>> print(settings.llm.model)
        'deepseek/deepseek-chat'
        >>> print(settings.github.token)
        'ghp_xxx'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
        env_prefix="CONSISTENCY_",
        validate_default=True,
    )

    # =============================================================================
    # 项目元数据
    # =============================================================================
    project_name: str = Field(default="GitConsistency", description="项目名称")
    version: str = Field(default="0.1.0", description="版本号")
    debug: bool = Field(default=False, description="调试模式")

    # =============================================================================
    # 嵌套配置
    # =============================================================================
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM 配置")
    github: GitHubConfig = Field(default_factory=GitHubConfig, description="GitHub 配置")
    gitnexus: GitNexusConfig = Field(default_factory=GitNexusConfig, description="GitNexus 配置")
    scanner: ScannerConfig = Field(default_factory=ScannerConfig, description="扫描器配置")
    cache: CacheConfig = Field(default_factory=CacheConfig, description="缓存配置")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="日志配置")
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig, description="性能配置")

    # =============================================================================
    # 兼容性属性（向后兼容）
    # =============================================================================
    @property
    def litellm_api_key(self) -> str | None:
        """向后兼容: LLM API Key."""
        return self.llm.api_key

    @property
    def litellm_model(self) -> str:
        """向后兼容: LLM 模型."""
        return self.llm.model

    @property
    def litellm_fallback_model(self) -> str:
        """向后兼容: 备选模型."""
        return self.llm.fallback_model

    @property
    def litellm_temperature(self) -> float:
        """向后兼容: 采样温度."""
        return self.llm.temperature

    @property
    def litellm_max_tokens(self) -> int:
        """向后兼容: 最大 token 数."""
        return self.llm.max_tokens

    @property
    def litellm_timeout(self) -> int:
        """向后兼容: 超时."""
        return self.llm.timeout

    @property
    def github_token(self) -> str | None:
        """向后兼容: GitHub Token."""
        return self.github.token

    @property
    def github_delete_old_comments(self) -> bool:
        """向后兼容: 删除旧评论."""
        return self.github.delete_old_comments

    @property
    def github_comment_signature(self) -> str:
        """向后兼容: 评论签名."""
        return self.github.comment_signature

    @property
    def gitnexus_mcp_url(self) -> str | None:
        """向后兼容: GitNexus URL."""
        return self.gitnexus.mcp_url

    @property
    def gitnexus_mcp_command(self) -> str | None:
        """向后兼容: GitNexus 命令."""
        return self.gitnexus.mcp_command

    @property
    def gitnexus_mcp_args(self) -> list[str]:
        """向后兼容: GitNexus 参数."""
        return self.gitnexus.mcp_args

    @property
    def gitnexus_cache_dir(self) -> Path:
        """向后兼容: GitNexus 缓存目录."""
        return self.gitnexus.cache_dir

    @property
    def gitnexus_cache_ttl(self) -> int:
        """向后兼容: GitNexus 缓存 TTL."""
        return self.gitnexus.cache_ttl

    @property
    def semgrep_rules(self) -> list[str]:
        """向后兼容: Semgrep 规则."""
        return self.scanner.semgrep_rules

    @property
    def bandit_severity(self) -> Literal["LOW", "MEDIUM", "HIGH"]:
        """向后兼容: Bandit 严重级别."""
        return self.scanner.bandit_severity

    @property
    def cache_dir(self) -> Path:
        """向后兼容: 缓存目录."""
        return self.cache.dir

    @property
    def cache_max_size(self) -> int:
        """向后兼容: 缓存最大大小."""
        return self.cache.max_size

    @property
    def enable_memory_cache(self) -> bool:
        """向后兼容: 内存缓存开关."""
        return self.cache.enable_memory

    @property
    def log_level(self) -> Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        """向后兼容: 日志级别."""
        return self.logging.level

    @property
    def log_format(self) -> str:
        """向后兼容: 日志格式."""
        return self.logging.format

    @property
    def worker_threads(self) -> int:
        """向后兼容: 工作线程数."""
        return self.performance.worker_threads

    # =============================================================================
    # 派生属性
    # =============================================================================
    @property
    def is_github_configured(self) -> bool:
        """检查 GitHub 是否已配置."""
        return self.github.token is not None

    @property
    def is_litellm_configured(self) -> bool:
        """检查 LiteLLM 是否已配置."""
        return self.llm.api_key is not None

    @property
    def is_gitnexus_configured(self) -> bool:
        """检查 GitNexus MCP 是否已配置."""
        return self.gitnexus.mcp_url is not None or self.gitnexus.mcp_command is not None

    @property
    def effective_worker_threads(self) -> int:
        """获取有效的工作线程数."""
        if self.performance.worker_threads == 0:
            return min(32, (os.cpu_count() or 1) + 4)
        return self.performance.worker_threads


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局配置实例（单例模式）.

    Returns:
        Settings: 全局配置实例
    """
    return Settings()


def reload_settings() -> Settings:
    """重新加载配置.

    Returns:
        Settings: 新的配置实例
    """
    get_settings.cache_clear()
    return get_settings()
