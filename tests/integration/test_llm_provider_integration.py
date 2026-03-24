"""LLM Provider 集成测试.

测试 LLM Provider 抽象层与各个模块的集成。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from consistency.llm import LLMConfig, LLMProviderFactory
from consistency.llm.base import BaseLLMProvider, LLMResponse
from consistency.llm.providers.litellm import LiteLLMProvider
from consistency.reviewer.ai_reviewer import AIReviewer
from consistency.reviewer.models import ReviewResult, Severity
from consistency.reviewer.prompts import ReviewContext, ReviewType


class TestLLMProviderFactory:
    """LLM Provider 工厂测试."""

    def test_create_litellm_provider(self) -> None:
        """测试创建 LiteLLM Provider."""
        config = LLMConfig(
            model="deepseek/deepseek-chat",
            api_key="test-key",
            temperature=0.5,
        )
        provider = LLMProviderFactory.create("litellm", config)

        assert isinstance(provider, LiteLLMProvider)
        assert provider.config.model == "deepseek/deepseek-chat"
        assert provider.config.api_key == "test-key"
        assert provider.config.temperature == 0.5

    def test_create_from_settings(self) -> None:
        """测试从设置创建 Provider."""
        provider = LLMProviderFactory.create_from_settings()

        assert isinstance(provider, LiteLLMProvider)
        assert provider.config.model is not None

    def test_create_unknown_provider(self) -> None:
        """测试创建未知 Provider 抛出异常."""
        config = LLMConfig(model="test")

        with pytest.raises(ValueError, match="未知的 LLM Provider"):
            LLMProviderFactory.create("unknown", config)

    def test_list_providers(self) -> None:
        """测试列出可用 Providers."""
        providers = LLMProviderFactory.list_providers()

        assert "litellm" in providers

    def test_register_custom_provider(self) -> None:
        """测试注册自定义 Provider."""

        class CustomProvider(BaseLLMProvider):
            @property
            def name(self) -> str:
                return "custom"

            @property
            def supports_json_mode(self) -> bool:
                return False

            async def complete(self, messages, **kwargs):
                return LLMResponse(content="test")

            async def complete_json(self, messages, schema=None, **kwargs):
                return LLMResponse(content="{}")

        LLMProviderFactory.register("custom", CustomProvider)

        config = LLMConfig(model="test")
        provider = LLMProviderFactory.create("custom", config)

        assert isinstance(provider, CustomProvider)
        assert provider.name == "custom"


class TestLiteLLMProvider:
    """LiteLLM Provider 集成测试."""

    @pytest.fixture
    def config(self) -> LLMConfig:
        """创建测试配置."""
        return LLMConfig(
            model="deepseek/deepseek-chat",
            api_key="test-api-key",
            temperature=0.3,
            max_tokens=1000,
            timeout=30,
        )

    @pytest.fixture
    def provider(self, config: LLMConfig) -> LiteLLMProvider:
        """创建 Provider 实例."""
        return LiteLLMProvider(config)

    @pytest.mark.asyncio
    async def test_complete_success(self, provider: LiteLLMProvider) -> None:
        """测试成功完成请求."""
        mock_response = MagicMock()
        mock_response.__getitem__ = lambda s, k: {
            "choices": [{"message": {"content": "Test response"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50},
            "model": "deepseek/deepseek-chat",
        }[k]
        mock_response.get = lambda k, default: {
            "usage": {"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50},
            "model": "deepseek/deepseek-chat",
        }.get(k, default)

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            messages = [{"role": "user", "content": "Hello"}]
            response = await provider.complete(messages)

            assert isinstance(response, LLMResponse)
            assert response.content == "Test response"
            assert response.model == "deepseek/deepseek-chat"
            assert response.usage["total_tokens"] == 100
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_complete_json_success(self, provider: LiteLLMProvider) -> None:
        """测试 JSON 模式成功."""
        mock_response = MagicMock()
        mock_response.__getitem__ = lambda s, k: {
            "choices": [{"message": {"content": '{"result": "ok"}'}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 50},
            "model": "deepseek/deepseek-chat",
        }[k]
        mock_response.get = lambda k, default: {"usage": {"total_tokens": 50}}.get(k, default)

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            messages = [{"role": "user", "content": "Return JSON"}]
            response = await provider.complete_json(messages)

            assert isinstance(response, LLMResponse)
            assert response.content == '{"result": "ok"}'

    def test_provider_properties(self, provider: LiteLLMProvider) -> None:
        """测试 Provider 属性."""
        assert provider.name == "litellm"
        assert provider.supports_json_mode is True

    def test_validate_litellm_not_installed(self) -> None:
        """测试未安装 litellm 时抛出异常."""
        with patch.dict("sys.modules", {"litellm": None}):
            config = LLMConfig(model="test")
            with pytest.raises(ImportError, match="LiteLLM 未安装"):
                LiteLLMProvider(config)


class TestAIReviewerWithProvider:
    """AIReviewer 使用 LLM Provider 的集成测试."""

    @pytest.fixture
    def reviewer(self) -> AIReviewer:
        """创建测试 Reviewer."""
        return AIReviewer(
            model="deepseek/deepseek-chat",
            api_key="test-key",
            cache_dir=None,  # 禁用磁盘缓存
        )

    @pytest.mark.asyncio
    async def test_review_with_mock_provider(self, reviewer: AIReviewer) -> None:
        """测试使用 mock provider 进行审查."""
        mock_response = LLMResponse(
            content='{"summary": "Test review", "severity": "low", "comments": []}',
            usage={"total_tokens": 100},
            model="deepseek/deepseek-chat",
        )

        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.complete_json = AsyncMock(return_value=mock_response)

        # 注入 mock provider
        reviewer._provider = mock_provider

        context = ReviewContext(diff="test code", files_changed=["test.py"])
        result = await reviewer.review(context, use_cache=False)

        assert isinstance(result, ReviewResult)
        assert result.summary == "Test review"
        assert result.severity == Severity.LOW
        assert result.comments == []

    @pytest.mark.asyncio
    async def test_review_with_fallback(self, reviewer: AIReviewer) -> None:
        """测试备选模型回退."""
        # 设置测试用的 fallback model
        reviewer.fallback_model = "fallback-model"

        # 主模型失败
        mock_primary = MagicMock(spec=BaseLLMProvider)
        mock_primary.complete_json = AsyncMock(side_effect=Exception("Primary failed"))

        # 备选模型成功
        mock_fallback_response = LLMResponse(
            content='{"summary": "Fallback review", "severity": "medium", "comments": []}',
            usage={"total_tokens": 50},
            model="fallback-model",
        )
        mock_fallback = MagicMock(spec=BaseLLMProvider)
        mock_fallback.complete_json = AsyncMock(return_value=mock_fallback_response)

        reviewer._provider = mock_primary
        reviewer._fallback_provider = mock_fallback

        context = ReviewContext(diff="test code", files_changed=["test.py"])
        result = await reviewer.review_with_fallback(context)

        assert isinstance(result, ReviewResult)
        assert result.metadata.get("used_fallback_model") is True
        assert result.metadata.get("fallback_model") == "fallback-model"

    @pytest.mark.asyncio
    async def test_review_batch(self, reviewer: AIReviewer) -> None:
        """测试批量审查."""
        mock_response = LLMResponse(
            content='{"summary": "Batch review", "severity": "low", "comments": []}',
            usage={"total_tokens": 100},
        )

        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.complete_json = AsyncMock(return_value=mock_response)

        reviewer._provider = mock_provider

        contexts = [
            ReviewContext(diff="code1", files_changed=["file1.py"]),
            ReviewContext(diff="code2", files_changed=["file2.py"]),
        ]

        results = await reviewer.review_batch(contexts, max_concurrency=2)

        assert len(results) == 2
        assert all(isinstance(r, ReviewResult) for r in results)
        assert mock_provider.complete_json.call_count == 2

    def test_reviewer_stats(self, reviewer: AIReviewer) -> None:
        """测试 Reviewer 统计信息."""
        stats = reviewer.get_stats()

        assert stats["model"] == "deepseek/deepseek-chat"
        assert stats["provider_type"] == "litellm"
        assert "requests" in stats
        assert "cache_hits" in stats

    def test_reviewer_cache_operations(self, reviewer: AIReviewer) -> None:
        """测试 Reviewer 缓存操作."""
        # 初始状态
        assert reviewer.get_stats()["memory_cache_size"] == 0

        # 手动添加缓存
        from consistency.reviewer.models import ReviewResult
        from consistency.reviewer.ai_reviewer import ReviewCache
        result = ReviewResult(summary="Test", severity=Severity.LOW)
        reviewer._result_cache["test-key"] = ReviewCache(
            result=result,
            timestamp=__import__("time").time(),
            model="test-model",
        )

        assert reviewer.get_stats()["memory_cache_size"] == 1

        # 清空缓存
        reviewer.clear_cache()
        assert reviewer.get_stats()["memory_cache_size"] == 0


class TestLLMConfig:
    """LLM 配置测试."""

    def test_config_defaults(self) -> None:
        """测试配置默认值."""
        config = LLMConfig(model="test-model")

        assert config.model == "test-model"
        assert config.api_key is None
        assert config.api_base is None
        assert config.temperature == 0.3
        assert config.max_tokens == 4096
        assert config.timeout == 60
        assert config.extra_params is None

    def test_config_with_extra_params(self) -> None:
        """测试带额外参数的配置."""
        config = LLMConfig(
            model="test-model",
            extra_params={"top_p": 0.9, "presence_penalty": 0.5},
        )

        assert config.extra_params["top_p"] == 0.9
        assert config.extra_params["presence_penalty"] == 0.5

    def test_config_modifiable(self) -> None:
        """测试配置是可修改的（非 frozen）."""
        config = LLMConfig(model="test")

        # 配置应该是可修改的
        config.model = "other"
        assert config.model == "other"

        config.temperature = 0.5
        assert config.temperature == 0.5


class TestProviderErrorHandling:
    """Provider 错误处理测试."""

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self) -> None:
        """测试超时错误处理."""
        reviewer = AIReviewer(cache_dir=None)

        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.complete_json = AsyncMock(side_effect=TimeoutError("Connection timeout"))

        reviewer._provider = mock_provider

        context = ReviewContext(diff="test")
        result = await reviewer.review(context, use_cache=False)

        assert "超时" in result.summary
        assert result.metadata.get("error") == "timeout"

    @pytest.mark.asyncio
    async def test_connection_error_handling(self) -> None:
        """测试连接错误处理."""
        reviewer = AIReviewer(cache_dir=None)

        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.complete_json = AsyncMock(side_effect=ConnectionError("Network error"))

        reviewer._provider = mock_provider

        context = ReviewContext(diff="test")
        result = await reviewer.review(context, use_cache=False)

        assert "网络连接失败" in result.summary
        assert result.metadata.get("error") == "connection"
