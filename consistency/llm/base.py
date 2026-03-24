"""LLM Provider 抽象基类.

定义统一的 LLM 调用接口，支持多种后端实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """LLM 响应."""

    content: str
    usage: dict[str, int] | None = None
    model: str | None = None
    finish_reason: str | None = None


@dataclass
class LLMConfig:
    """LLM 配置."""

    model: str
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60
    extra_params: dict[str, Any] | None = None


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类.

    所有 LLM 后端都需要实现此接口，以提供统一调用方式。

    Examples:
        >>> provider = LiteLLMProvider(config)
        >>> response = await provider.complete(messages=[
        ...     {"role": "system", "content": "You are a code reviewer."},
        ...     {"role": "user", "content": "Review this code..."},
        ... ])
        >>> print(response.content)
    """

    def __init__(self, config: LLMConfig) -> None:
        """初始化 Provider.

        Args:
            config: LLM 配置
        """
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """执行完成请求.

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            LLM 响应
        """
        ...

    @abstractmethod
    async def complete_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """执行 JSON 格式完成请求.

        Args:
            messages: 消息列表
            schema: JSON Schema（可选）
            **kwargs: 额外参数

        Returns:
            LLM 响应（内容为 JSON 字符串）
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称."""
        ...

    @property
    @abstractmethod
    def supports_json_mode(self) -> bool:
        """是否支持 JSON mode."""
        ...

    def validate_config(self) -> None:
        """验证配置有效性.

        Raises:
            ValueError: 配置无效
        """
        if not self.config.model:
            raise ValueError("模型名称不能为空")
