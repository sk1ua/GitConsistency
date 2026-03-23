"""ConsistenCy 配置管理.

使用 Pydantic Settings 实现环境变量、.env 文件和默认值的统一管理。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ConsistenCy 全局配置类.

    所有配置项都可以通过环境变量或 .env 文件设置。

    Examples:
        >>> settings = get_settings()
        >>> print(settings.litellm_model)
        'deepseek/deepseek-chat'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # =============================================================================
    # 项目元数据
    # =============================================================================
    project_name: str = Field(default="ConsistenCy", description="项目名称")
    version: str = Field(default="2.0.0", description="版本号")
    debug: bool = Field(default=False, description="调试模式")

    # =============================================================================
    # LLM 配置 (LiteLLM)
    # =============================================================================
    litellm_api_key: str | None = Field(default=None, description="LiteLLM API Key")
    litellm_model: str = Field(
        default="deepseek/deepseek-chat",
        description="默认 LLM 模型 (LiteLLM 格式)",
    )
    litellm_fallback_model: str = Field(
        default="anthropic/claude-3-haiku-20240307",
        description="备选模型",
    )
    litellm_temperature: float = Field(default=0.3, ge=0.0, le=1.0, description="采样温度")
    litellm_max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大生成 token 数")
    litellm_timeout: int = Field(default=60, ge=1, description="请求超时（秒）")

    # =============================================================================
    # GitHub 配置
    # =============================================================================
    github_token: str | None = Field(default=None, description="GitHub Personal Access Token")
    github_delete_old_comments: bool = Field(default=True, description="是否删除旧评论")
    github_comment_signature: str = Field(default="<!-- ConsistenCy 2.0 Code Review -->", description="PR 评论签名")

    # =============================================================================
    # GitNexus MCP 配置
    # =============================================================================
    gitnexus_mcp_url: str | None = Field(default=None, description="GitNexus MCP SSE 端点 URL")
    gitnexus_mcp_command: str | None = Field(default=None, description="GitNexus MCP 命令（stdio 模式）")
    gitnexus_mcp_args: list[str] = Field(default_factory=list, description="GitNexus MCP 命令参数")
    gitnexus_cache_dir: Path = Field(default=Path(".cache/gitnexus"), description="GitNexus 缓存目录")
    gitnexus_cache_ttl: int = Field(default=3600, ge=0, description="缓存 TTL（秒）")

    # =============================================================================
    # 安全扫描器配置
    # =============================================================================
    semgrep_rules: list[str] = Field(
        default_factory=lambda: ["p/security-audit", "p/owasp-top-ten", "p/cwe-top-25"],
        description="Semgrep 规则集",
    )
    bandit_severity: Literal["LOW", "MEDIUM", "HIGH"] = Field(default="LOW", description="Bandit 最低严重级别")

    # =============================================================================
    # 缓存配置
    # =============================================================================
    cache_dir: Path = Field(default=Path(".cache"), description="全局缓存目录")
    cache_max_size: int = Field(default=1000, ge=100, description="缓存最大大小（MB）")
    enable_memory_cache: bool = Field(default=True, description="是否启用内存缓存")

    # =============================================================================
    # 日志配置
    # =============================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO", description="日志级别")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式",
    )

    # =============================================================================
    # 性能配置
    # =============================================================================
    worker_threads: int = Field(default=0, ge=0, description="工作线程数（0=自动）")

    # =============================================================================
    # 字段验证器
    # =============================================================================
    @field_validator("litellm_api_key", "github_token", mode="before")
    @classmethod
    def validate_sensitive_fields(cls, v: str | None) -> str | None:
        """验证敏感字段，去除空白字符."""
        if v is None:
            return None
        v = v.strip()
        return v if v else None

    @field_validator("litellm_model", "litellm_fallback_model", mode="before")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        """验证并修复模型名称格式."""
        if not v:
            return v
        v = v.strip()
        if "/" in v:
            return v
        provider_map = {
            "deepseek": "deepseek/deepseek-chat",
            "gpt-4": "openai/gpt-4",
            "gpt-3.5": "openai/gpt-3.5-turbo",
            "claude": "anthropic/claude-3-sonnet-20240229",
            "claude-3": "anthropic/claude-3-sonnet-20240229",
            "claude-3-haiku": "anthropic/claude-3-haiku-20240307",
        }
        for prefix, full_name in provider_map.items():
            if v.lower().startswith(prefix):
                return full_name
        if "chat" in v.lower():
            return f"deepseek/{v}"
        return v

    @field_validator("gitnexus_mcp_args", mode="before")
    @classmethod
    def parse_mcp_args(cls, v: str | list[str]) -> list[str]:
        """解析 MCP 参数，支持字符串或列表."""
        if isinstance(v, str):
            return v.split(",") if v else []
        return v if v else []

    @field_validator("semgrep_rules", mode="before")
    @classmethod
    def parse_semgrep_rules(cls, v: str | list[str]) -> list[str]:
        """解析 Semgrep 规则，支持逗号分隔字符串或列表."""
        if isinstance(v, str):
            return [r.strip() for r in v.split(",") if r.strip()]
        return v if v else []

    @field_validator("cache_dir", "gitnexus_cache_dir", mode="before")
    @classmethod
    def parse_path(cls, v: str | Path) -> Path:
        """解析路径字段."""
        return Path(v) if isinstance(v, str) else v

    # =============================================================================
    # 属性方法
    # =============================================================================
    @property
    def is_github_configured(self) -> bool:
        """检查 GitHub 是否已配置."""
        return self.github_token is not None

    @property
    def is_litellm_configured(self) -> bool:
        """检查 LiteLLM 是否已配置."""
        return self.litellm_api_key is not None

    @property
    def is_gitnexus_configured(self) -> bool:
        """检查 GitNexus MCP 是否已配置."""
        return self.gitnexus_mcp_url is not None or self.gitnexus_mcp_command is not None

    @property
    def effective_worker_threads(self) -> int:
        """获取有效的工作线程数."""
        if self.worker_threads == 0:
            return min(32, (os.cpu_count() or 1) + 4)
        return self.worker_threads


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
