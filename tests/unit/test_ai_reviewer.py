"""AI 审查器单元测试."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistency.reviewer.ai_reviewer import AIReviewer
from consistency.reviewer.models import CommentCategory, ReviewResult, Severity
from consistency.reviewer.prompts import ReviewContext, ReviewType


class TestAIReviewerInit:
    """初始化测试."""

    def test_default_init(self) -> None:
        """测试默认初始化."""
        with patch("consistency.reviewer.ai_reviewer.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                litellm_model="deepseek/deepseek-chat",
                litellm_fallback_model="anthropic/claude-3-haiku",
                litellm_temperature=0.3,
                litellm_max_tokens=4096,
                litellm_timeout=60,
                litellm_api_key="test-key",
            )

            reviewer = AIReviewer()
            assert reviewer.model == "deepseek/deepseek-chat"
            assert reviewer.fallback_model == "anthropic/claude-3-haiku"
            assert reviewer.temperature == 0.3

    def test_custom_init(self) -> None:
        """测试自定义初始化."""
        reviewer = AIReviewer(
            model="custom-model",
            temperature=0.7,
            max_tokens=2048,
        )
        assert reviewer.model == "custom-model"
        assert reviewer.temperature == 0.7
        assert reviewer.max_tokens == 2048

    def test_validate_setup_no_api_key(self) -> None:
        """测试无 API 键时警告."""
        with patch("consistency.reviewer.ai_reviewer.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                litellm_model="test",
                litellm_api_key=None,
            )

            with patch("consistency.reviewer.ai_reviewer.logger") as mock_logger:
                AIReviewer()
                mock_logger.warning.assert_called_once()


class TestReview:
    """审查功能测试."""

    @pytest.fixture
    def reviewer(self) -> AIReviewer:
        """创建测试审查器."""
        return AIReviewer(
            model="test-model",
            api_key="test-key",
        )

    @pytest.fixture
    def mock_llm_response(self) -> str:
        """Mock LLM 响应."""
        return json.dumps({
            "summary": "Test review summary",
            "severity": "medium",
            "comments": [
                {
                    "file": "test.py",
                    "line": 10,
                    "message": "Test issue",
                    "severity": "medium",
                    "category": "style",
                }
            ],
            "action_items": ["Fix the issue"],
        })

    @pytest.mark.asyncio
    async def test_review_success(
        self,
        reviewer: AIReviewer,
        mock_llm_response: str,
    ) -> None:
        """测试成功审查."""
        context = ReviewContext(diff="test diff", files_changed=["test.py"])

        # Mock provider's complete_json method
        mock_response = MagicMock()
        mock_response.content = mock_llm_response
        mock_response.usage = {"total_tokens": 100}

        mock_provider = AsyncMock()
        mock_provider.complete_json.return_value = mock_response

        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            result = await reviewer.review(context)

            assert isinstance(result, ReviewResult)
            assert result.summary == "Test review summary"
            assert len(result.comments) == 1
            assert result.comments[0].file == "test.py"

    @pytest.mark.asyncio
    async def test_review_with_string_context(
        self,
        reviewer: AIReviewer,
        mock_llm_response: str,
    ) -> None:
        """测试使用字符串上下文."""
        mock_response = MagicMock()
        mock_response.content = mock_llm_response
        mock_response.usage = {"total_tokens": 100}

        mock_provider = AsyncMock()
        mock_provider.complete_json.return_value = mock_response

        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            result = await reviewer.review("simple diff string")

            assert isinstance(result, ReviewResult)

    @pytest.mark.asyncio
    async def test_review_cache_hit(
        self,
        reviewer: AIReviewer,
        mock_llm_response: str,
    ) -> None:
        """测试缓存命中."""
        context = ReviewContext(diff="cached diff", files_changed=["test.py"])

        mock_response = MagicMock()
        mock_response.content = mock_llm_response
        mock_response.usage = {"total_tokens": 100}

        mock_provider = AsyncMock()
        mock_provider.complete_json.return_value = mock_response

        # 第一次调用
        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            result1 = await reviewer.review(context)

        # 第二次调用（应该命中缓存）- 使用相同的 provider mock
        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            result2 = await reviewer.review(context)
            # 由于缓存命中，provider 不应该被调用第二次
            assert mock_provider.complete_json.call_count == 1

        assert result1.summary == result2.summary
        assert reviewer._stats["cache_hits"] == 1

    @pytest.mark.asyncio
    async def test_review_no_cache(self, reviewer: AIReviewer, mock_llm_response: str) -> None:
        """测试不使用缓存."""
        context = ReviewContext(diff="test diff", files_changed=["test.py"])

        mock_response = MagicMock()
        mock_response.content = mock_llm_response
        mock_response.usage = {"total_tokens": 100}

        mock_provider = AsyncMock()
        mock_provider.complete_json.return_value = mock_response

        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            # 两次调用，都不使用缓存
            await reviewer.review(context, use_cache=False)
            await reviewer.review(context, use_cache=False)

            assert mock_provider.complete_json.call_count == 2

    @pytest.mark.asyncio
    async def test_review_failure(self, reviewer: AIReviewer) -> None:
        """测试审查失败."""
        context = ReviewContext(diff="test")

        mock_provider = AsyncMock()
        mock_provider.complete_json.side_effect = Exception("API Error")

        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            result = await reviewer.review(context)

            assert "审查失败" in result.summary or "失败" in result.summary
            assert result.severity == Severity.LOW


class TestParseResponse:
    """响应解析测试."""

    @pytest.fixture
    def reviewer(self) -> AIReviewer:
        return AIReviewer(model="test")

    def test_parse_valid_json(self, reviewer: AIReviewer) -> None:
        """测试解析有效 JSON."""
        content = json.dumps({
            "summary": "Good code",
            "severity": "low",
            "comments": [],
            "action_items": [],
        })

        result = reviewer._parse_response(content)

        assert result.summary == "Good code"
        assert result.severity == Severity.LOW

    def test_parse_json_with_code_block(self, reviewer: AIReviewer) -> None:
        """测试解析代码块中的 JSON."""
        content = """```json
{
    "summary": "Good code",
    "severity": "low",
    "comments": []
}
```"""

        result = reviewer._parse_response(content)

        assert result.summary == "Good code"

    def test_parse_invalid_json_fallback(self, reviewer: AIReviewer) -> None:
        """测试无效 JSON 回退到启发式解析."""
        content = """
File: test.py
Line: 42
This is a test issue that needs attention.

Another issue in file: other.py line 10
Please fix this.
"""

        result = reviewer._parse_response(content)

        assert result.summary is not None
        assert len(result.comments) >= 1

    def test_parse_with_comments(self, reviewer: AIReviewer) -> None:
        """测试解析带评论的响应."""
        content = json.dumps({
            "summary": "Issues found",
            "severity": "high",
            "comments": [
                {
                    "file": "test.py",
                    "line": 10,
                    "message": "Security issue",
                    "severity": "critical",
                    "category": "security",
                    "confidence": 0.95,
                },
                {
                    "file": "other.py",
                    "line": 20,
                    "message": "Style issue",
                    "severity": "low",
                    "category": "style",
                },
            ],
        })

        result = reviewer._parse_response(content)

        assert len(result.comments) == 2
        assert result.comments[0].severity == Severity.CRITICAL
        assert result.comments[0].category == CommentCategory.SECURITY


class TestExtractJson:
    """JSON 提取测试."""

    @pytest.fixture
    def reviewer(self) -> AIReviewer:
        return AIReviewer(model="test")

    def test_extract_from_code_block(self, reviewer: AIReviewer) -> None:
        """测试从代码块提取."""
        content = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = reviewer._extract_json(content)
        assert result == '{"key": "value"}'

    def test_extract_from_braces(self, reviewer: AIReviewer) -> None:
        """测试从大括号提取."""
        content = 'Text {"key": "value"} more text'
        result = reviewer._extract_json(content)
        assert result == '{"key": "value"}'

    def test_extract_plain_json(self, reviewer: AIReviewer) -> None:
        """测试纯 JSON."""
        content = '{"key": "value"}'
        result = reviewer._extract_json(content)
        assert result == '{"key": "value"}'


class TestReviewBatch:
    """批量审查测试."""

    @pytest.mark.asyncio
    async def test_review_batch(self) -> None:
        """测试批量审查."""
        reviewer = AIReviewer(model="test")

        contexts = [
            ReviewContext(diff=f"diff {i}")
            for i in range(5)
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "summary": "OK",
            "severity": "low",
            "comments": [],
        })
        mock_response.usage = {"total_tokens": 50}

        mock_provider = AsyncMock()
        mock_provider.complete_json.return_value = mock_response

        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            results = await reviewer.review_batch(contexts, max_concurrency=2)

            assert len(results) == 5
            assert mock_provider.complete_json.call_count == 5


class TestReviewWithFallback:
    """备选模型测试."""

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self) -> None:
        """测试失败时使用备选模型."""
        reviewer = AIReviewer(
            model="primary-model",
            fallback_model="fallback-model",
        )

        # 主模型失败，备选模型成功
        mock_primary = AsyncMock()
        mock_primary.complete_json.side_effect = Exception("Primary failed")

        mock_fallback = AsyncMock()
        mock_fallback.complete_json.return_value = MagicMock(
            content=json.dumps({
                "summary": "Fallback review",
                "severity": "low",
                "comments": [],
            }),
            usage={"total_tokens": 50},
        )

        def get_provider(use_fallback: bool = False):
            return mock_fallback if use_fallback else mock_primary

        with patch.object(reviewer, "_get_provider", side_effect=get_provider):
            result = await reviewer.review_with_fallback(ReviewContext(diff="test"))

            # 应该使用备选模型重试
            assert mock_primary.complete_json.call_count == 1
            assert mock_fallback.complete_json.call_count == 1
            assert result.metadata.get("used_fallback_model") is True

    @pytest.mark.asyncio
    async def test_no_fallback_on_success(self) -> None:
        """测试成功时不使用备选模型."""
        reviewer = AIReviewer(
            model="primary-model",
            fallback_model="fallback-model",
        )

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "summary": "OK",
            "severity": "low",
            "comments": [],
        })
        mock_response.usage = {"total_tokens": 50}

        mock_provider = AsyncMock()
        mock_provider.complete_json.return_value = mock_response

        with patch.object(reviewer, "_get_provider", return_value=mock_provider):
            await reviewer.review_with_fallback(ReviewContext(diff="test"))

            # 只调用一次
            assert mock_provider.complete_json.call_count == 1


class TestCache:
    """缓存测试."""

    @pytest.fixture
    def reviewer(self) -> AIReviewer:
        return AIReviewer(model="test")

    def test_cache_key_consistency(self, reviewer: AIReviewer) -> None:
        """测试缓存键一致性."""
        context1 = ReviewContext(diff="test diff", files_changed=["a.py"])
        context2 = ReviewContext(diff="test diff", files_changed=["a.py"])

        key1 = reviewer._make_cache_key(context1, ReviewType.GENERAL)
        key2 = reviewer._make_cache_key(context2, ReviewType.GENERAL)

        assert key1 == key2

    def test_cache_key_different_type(self, reviewer: AIReviewer) -> None:
        """测试不同审查类型的缓存键不同."""
        context = ReviewContext(diff="test")

        key1 = reviewer._make_cache_key(context, ReviewType.GENERAL)
        key2 = reviewer._make_cache_key(context, ReviewType.SECURITY)

        assert key1 != key2

    def test_cache_result_and_get(self, reviewer: AIReviewer) -> None:
        """测试缓存和获取."""
        result = ReviewResult(summary="Test", severity=Severity.LOW)

        reviewer._cache_result("key1", result)
        cached = reviewer._get_cached_result("key1")

        assert cached is not None
        assert cached.summary == "Test"

    def test_cache_expiration(self, reviewer: AIReviewer) -> None:
        """测试缓存过期."""
        import time

        result = ReviewResult(summary="Test", severity=Severity.LOW)

        # 设置过期时间为 0
        reviewer._cache_ttl = 0
        reviewer._cache_result("key1", result)

        # 立即获取（应该过期）
        time.sleep(0.01)
        cached = reviewer._get_cached_result("key1")

        assert cached is None

    def test_clear_cache(self, reviewer: AIReviewer) -> None:
        """测试清空缓存."""
        result = ReviewResult(summary="Test", severity=Severity.LOW)
        reviewer._cache_result("key1", result)

        assert len(reviewer._result_cache) == 1

        reviewer.clear_cache()

        assert len(reviewer._result_cache) == 0


class TestStats:
    """统计测试."""

    def test_get_stats(self) -> None:
        """测试获取统计."""
        reviewer = AIReviewer(
            model="test-model",
            fallback_model="fallback-model",
        )

        # 修改一些统计
        reviewer._stats["requests"] = 10
        reviewer._stats["cache_hits"] = 5

        stats = reviewer.get_stats()

        assert stats["requests"] == 10
        assert stats["cache_hits"] == 5
        assert stats["model"] == "test-model"
        assert stats["fallback_model"] == "fallback-model"
