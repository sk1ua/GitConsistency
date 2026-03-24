"""LLM Provider 工厂.

用于创建和管理 LLM Provider 实例。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from consistency.config import get_settings
from consistency.llm.providers.litellm import LiteLLMProvider

if TYPE_CHECKING:
    from consistency.llm.base import BaseLLMProvider, LLMConfig


class LLMProviderFactory:
    """LLM Provider 工厂.

    根据配置创建对应的 Provider 实例。

    Examples:
        >>> factory = LLMProviderFactory()
        >>> provider = factory.create("litellm", config)
        >>> response = await provider.complete(messages=[...])
    """

    _providers: dict[str, type[BaseLLMProvider]] = {
        "litellm": LiteLLMProvider,
        # 预留其他 Provider
        # "openai": OpenAIProvider,
        # "ollama": OllamaProvider,
    }

    @classmethod
    def register(
        cls,
        name: str,
        provider_class: type[BaseLLMProvider],
    ) -> None:
        """注册新的 Provider.

        Args:
            name: Provider 名称
            provider_class: Provider 类
        """
        cls._providers[name] = provider_class

    @classmethod
    def create(
        cls,
        name: str,
        config: LLMConfig | None = None,
    ) -> BaseLLMProvider:
        """创建 Provider 实例.

        Args:
            name: Provider 名称
            config: LLM 配置（为 None 时从全局配置创建）

        Returns:
            Provider 实例

        Raises:
            ValueError: 未知的 Provider
        """
        if config is None:
            config = cls._config_from_settings()

        provider_class = cls._providers.get(name)
        if not provider_class:
            raise ValueError(
                f"未知的 LLM Provider: {name}. "
                f"可用选项: {', '.join(cls._providers.keys())}"
            )

        return provider_class(config)

    @classmethod
    def create_from_settings(cls) -> BaseLLMProvider:
        """从全局配置创建默认 Provider.

        Returns:
            Provider 实例
        """
        config = cls._config_from_settings()
        return cls.create("litellm", config)

    @classmethod
    def _config_from_settings(cls) -> LLMConfig:
        """从全局配置创建 LLMConfig."""
        from consistency.llm.base import LLMConfig

        settings = get_settings()
        return LLMConfig(
            model=settings.litellm_model,
            api_key=settings.litellm_api_key,
            temperature=settings.litellm_temperature,
            max_tokens=settings.litellm_max_tokens,
            timeout=settings.litellm_timeout,
        )

    @classmethod
    def list_providers(cls) -> list[str]:
        """列出所有可用的 Provider.

        Returns:
            Provider 名称列表
        """
        return list(cls._providers.keys())
