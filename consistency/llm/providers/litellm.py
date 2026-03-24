"""LiteLLM Provider 实现.

使用 LiteLLM 统一接口调用多种 LLM 模型。
"""

from __future__ import annotations

from typing import Any

from consistency.llm.base import BaseLLMProvider, LLMConfig, LLMResponse


class LiteLLMProvider(BaseLLMProvider):
    """LiteLLM Provider.

    支持 DeepSeek、Claude、OpenAI 等任意 LiteLLM 兼容模型。

    Examples:
        >>> config = LLMConfig(model="deepseek/deepseek-chat", api_key="sk-...")
        >>> provider = LiteLLMProvider(config)
        >>> response = await provider.complete(messages=[...])
    """

    def __init__(self, config: LLMConfig) -> None:
        """初始化 LiteLLM Provider."""
        super().__init__(config)
        self._validate_litellm()

    def _validate_litellm(self) -> None:
        """验证 LiteLLM 已安装."""
        try:
            import litellm  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "LiteLLM 未安装，请运行: pip install litellm"
            ) from e

    @property
    def name(self) -> str:
        """Provider 名称."""
        return "litellm"

    @property
    def supports_json_mode(self) -> bool:
        """是否支持 JSON mode."""
        # LiteLLM 通过底层模型判断是否支持 JSON mode
        # 这里返回 True，实际调用时根据模型决定
        return True

    async def complete(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """执行完成请求."""
        import litellm

        # 构建请求参数
        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "timeout": kwargs.get("timeout", self.config.timeout),
        }

        # 添加可选参数
        if self.config.api_key:
            request_kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            request_kwargs["api_base"] = self.config.api_base

        # 合并额外参数
        if self.config.extra_params:
            request_kwargs.update(self.config.extra_params)
        request_kwargs.update(kwargs)

        # 调用 LiteLLM
        response = await litellm.acompletion(**request_kwargs)

        # 解析响应
        content = response["choices"][0]["message"]["content"]
        usage = dict(response.get("usage", {}))
        model = response.get("model", self.config.model)
        finish_reason = response["choices"][0].get("finish_reason")

        return LLMResponse(
            content=str(content),
            usage=usage,
            model=model,
            finish_reason=finish_reason,
        )

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """执行 JSON 格式完成请求."""
        import litellm

        # 构建请求参数
        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "timeout": kwargs.get("timeout", self.config.timeout),
            "response_format": {"type": "json_object"},
        }

        # 添加可选参数
        if self.config.api_key:
            request_kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            request_kwargs["api_base"] = self.config.api_base

        # 合并额外参数（但保留 response_format）
        if self.config.extra_params:
            for key, value in self.config.extra_params.items():
                if key not in request_kwargs:
                    request_kwargs[key] = value

        # 更新非冲突参数
        for key, value in kwargs.items():
            if key not in ("response_format",):
                request_kwargs[key] = value

        # 调用 LiteLLM
        response = await litellm.acompletion(**request_kwargs)

        # 解析响应
        content = response["choices"][0]["message"]["content"]
        usage = dict(response.get("usage", {}))
        model = response.get("model", self.config.model)
        finish_reason = response["choices"][0].get("finish_reason")

        return LLMResponse(
            content=str(content),
            usage=usage,
            model=model,
            finish_reason=finish_reason,
        )
