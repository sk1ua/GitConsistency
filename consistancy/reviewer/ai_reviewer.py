"""AI 代码审查器.

使用 LiteLLM 调用多种 LLM 模型，
支持 DeepSeek、Claude、Grok 等任意 OpenAI 兼容模型.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from consistancy.config import get_settings
from consistancy.reviewer.models import (
    CommentCategory,
    ReviewComment,
    ReviewResult,
    Severity,
)
from consistancy.reviewer.prompts import PromptCache, PromptTemplate, ReviewContext, ReviewType

logger = logging.getLogger(__name__)


@dataclass
class ReviewCache:
    """审查结果缓存项."""

    result: ReviewResult
    timestamp: float
    model: str


class AIReviewer:
    """AI 代码审查器.

    使用 LiteLLM 统一接口调用多种 LLM 模型，
    支持结构化输出、重试、缓存和降级策略.

    Examples:
        >>> reviewer = AIReviewer(model="deepseek/deepseek-chat")
        >>> context = ReviewContext(diff="...", files_changed=["main.py"])
        >>> result = await reviewer.review(context)
        >>> for comment in result.comments:
        ...     print(f"{comment.file}:{comment.line} - {comment.message}")
    """

    def __init__(
        self,
        model: str | None = None,
        fallback_model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        cache_dir: str | Path = ".cache/reviews",
        cache_ttl: int = 3600,
    ) -> None:
        """初始化 AI 审查器.

        Args:
            model: 主模型（LiteLLM 格式，如 "deepseek/deepseek-chat"）
            fallback_model: 备选模型
            temperature: 采样温度（默认从配置读取）
            max_tokens: 最大 token 数
            timeout: 请求超时（秒）
            api_key: API 密钥（默认从环境变量读取）
            api_base: 自定义 API 基础 URL
            cache_dir: 缓存目录
            cache_ttl: 缓存过期时间（秒）
        """
        # 从配置读取默认值
        settings = get_settings()

        self.model = model or settings.litellm_model
        self.fallback_model = fallback_model or settings.litellm_fallback_model
        self.temperature = temperature if temperature is not None else settings.litellm_temperature
        self.max_tokens = max_tokens or settings.litellm_max_tokens
        self.timeout = timeout or settings.litellm_timeout
        self.api_key = api_key or settings.litellm_api_key
        self.api_base = api_base

        # 缓存
        self._prompt_cache = PromptCache()
        self._result_cache: dict[str, ReviewCache] = {}
        self._cache_ttl = cache_ttl

        # 统计
        self._stats = {
            "requests": 0,
            "cache_hits": 0,
            "errors": 0,
            "tokens_used": 0,
        }

        self._validate_setup()

    def _validate_setup(self) -> None:
        """验证配置."""
        if not self.api_key:
            logger.warning("未配置 API 密钥，审查功能将不可用")

        try:
            import litellm  # noqa: F401
        except ImportError:
            raise ImportError(
                "LiteLLM 未安装，请运行: pip install litellm"
            )

    async def review(
        self,
        context: ReviewContext | str,
        review_type: ReviewType = ReviewType.GENERAL,
        use_cache: bool = True,
    ) -> ReviewResult:
        """执行 AI 代码审查.

        Args:
            context: 审查上下文（或 diff 字符串）
            review_type: 审查类型
            use_cache: 是否使用缓存

        Returns:
            结构化审查结果
        """
        # 标准化上下文
        if isinstance(context, str):
            context = ReviewContext(diff=context)

        # 检查缓存
        cache_key = self._make_cache_key(context, review_type)
        if use_cache:
            cached = self._get_cached_result(cache_key)
            if cached:
                logger.debug(f"使用缓存的审查结果: {cache_key[:8]}")
                self._stats["cache_hits"] += 1
                return cached

        # 构建 Prompt
        messages = self._build_messages(context, review_type)

        # 调用 LLM
        start_time = time.perf_counter()
        try:
            response = await self._call_llm(messages)
            duration = time.perf_counter() - start_time
            logger.info(f"LLM 调用完成: {duration:.2f}s")

            # 解析结果
            result = self._parse_response(response)

            # 缓存结果
            if use_cache:
                self._cache_result(cache_key, result)

            return result

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"审查失败: {e}")
            # 返回错误结果
            return ReviewResult(
                summary=f"审查失败: {e}",
                severity=Severity.LOW,
                comments=[],
                action_items=["请检查 API 配置和网络连接"],
                metadata={"error": str(e)},
            )

    async def review_batch(
        self,
        contexts: list[ReviewContext],
        review_type: ReviewType = ReviewType.GENERAL,
        max_concurrency: int = 3,
    ) -> list[ReviewResult]:
        """批量审查.

        Args:
            contexts: 上下文列表
            review_type: 审查类型
            max_concurrency: 最大并发数

        Returns:
            审查结果列表
        """
        import asyncio

        semaphore = asyncio.Semaphore(max_concurrency)

        async def review_with_limit(ctx: ReviewContext) -> ReviewResult:
            async with semaphore:
                return await self.review(ctx, review_type)

        tasks = [review_with_limit(ctx) for ctx in contexts]
        return await asyncio.gather(*tasks)

    async def review_with_fallback(
        self,
        context: ReviewContext | str,
        review_type: ReviewType = ReviewType.GENERAL,
    ) -> ReviewResult:
        """执行审查，失败时使用备选模型.

        Args:
            context: 审查上下文
            review_type: 审查类型

        Returns:
            审查结果
        """
        try:
            return await self.review(context, review_type)
        except Exception as e:
            logger.warning(f"主模型失败，尝试备选模型: {e}")

            # 切换到备选模型
            original_model = self.model
            self.model = self.fallback_model
            try:
                result = await self.review(context, review_type, use_cache=False)
                result.metadata["used_fallback_model"] = True
                return result
            finally:
                self.model = original_model

    def _build_messages(
        self,
        context: ReviewContext,
        review_type: ReviewType,
    ) -> list[dict[str, str]]:
        """构建 Prompt 消息."""
        # 检查 Prompt 缓存
        cached = self._prompt_cache.get(context, review_type)
        if cached:
            return cached

        messages = PromptTemplate.build(context, review_type)
        self._prompt_cache.set(context, review_type, messages)

        return messages

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """调用 LLM.

        Args:
            messages: 消息列表

        Returns:
            LLM 响应文本
        """
        import litellm

        self._stats["requests"] += 1

        # 配置
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        # 调用
        response = await litellm.acompletion(**kwargs)

        # 更新统计
        usage = response.get("usage", {})
        self._stats["tokens_used"] += usage.get("total_tokens", 0)

        # 提取内容
        content = response["choices"][0]["message"]["content"]
        return str(content)

    def _parse_response(self, content: str) -> ReviewResult:
        """解析 LLM 响应.

        Args:
            content: 响应文本

        Returns:
            结构化结果
        """
        # 尝试提取 JSON
        json_content = self._extract_json(content)

        try:
            data = json.loads(json_content)
            return ReviewResult.model_validate(data)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败，使用启发式解析: {e}")
            return self._heuristic_parse(content)
        except Exception as e:
            logger.error(f"解析失败: {e}")
            return self._heuristic_parse(content)

    def _extract_json(self, content: str) -> str:
        """从文本中提取 JSON."""
        # 尝试找到 JSON 代码块
        import re

        # 匹配 ```json ... ```
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
        if match:
            return match.group(1)

        # 尝试找到 {...}
        match = re.search(r'(\{.*\})', content, re.DOTALL)
        if match:
            return match.group(1)

        return content

    def _heuristic_parse(self, content: str) -> ReviewResult:
        """启发式解析非结构化响应."""
        comments: list[ReviewComment] = []

        # 简单提取建议
        import re

        # 查找 "Line X:" 或 "File Y:" 模式
        file_pattern = r'(?:[Ff]ile|[Ff]ile path):?\s*[`\']?(\S+)[`\']?'
        line_pattern = r'(?:[Ll]ine|[Ll]n):?\s*(\d+)'

        lines = content.split('\n')
        current_file: str | None = None
        current_line: int | None = None
        current_message: list[str] = []

        for line in lines:
            # 检查是否是新文件/行
            file_match = re.search(file_pattern, line)
            line_match = re.search(line_pattern, line)

            if file_match or line_match:
                # 保存之前的评论
                if current_message:
                    comments.append(ReviewComment(
                        file=current_file,
                        line=current_line,
                        message=' '.join(current_message).strip(),
                        suggestion=None,
                        severity=Severity.MEDIUM,
                        category=CommentCategory.OTHER,
                        confidence=0.8,
                    ))
                    current_message = []

                if file_match:
                    current_file = file_match.group(1)
                if line_match:
                    current_line = int(line_match.group(1))
            else:
                current_message.append(line)

        # 保存最后一个评论
        if current_message:
            comments.append(ReviewComment(
                file=current_file,
                line=current_line,
                message=' '.join(current_message).strip(),
                suggestion=None,
                severity=Severity.MEDIUM,
                category=CommentCategory.OTHER,
                confidence=0.8,
            ))

        return ReviewResult(
            summary=content[:500] + "..." if len(content) > 500 else content,
            severity=Severity.MEDIUM if comments else Severity.LOW,
            comments=comments,
        )

    def _make_cache_key(self, context: ReviewContext, review_type: ReviewType) -> str:
        """生成缓存键."""
        import hashlib

        content = f"{context.diff}:{review_type.name}:{self.model}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cached_result(self, key: str) -> ReviewResult | None:
        """获取缓存的结果."""
        if key not in self._result_cache:
            return None

        cached = self._result_cache[key]
        if time.time() - cached.timestamp > self._cache_ttl:
            del self._result_cache[key]
            return None

        return cached.result

    def _cache_result(self, key: str, result: ReviewResult) -> None:
        """缓存结果."""
        # 限制缓存大小
        if len(self._result_cache) >= 100:
            # 移除最旧的 50%
            sorted_items = sorted(
                self._result_cache.items(),
                key=lambda x: x[1].timestamp,
            )
            self._result_cache = dict(sorted_items[50:])

        self._result_cache[key] = ReviewCache(
            result=result,
            timestamp=time.time(),
            model=self.model,
        )

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        return {
            **self._stats,
            "cache_size": len(self._result_cache),
            "model": self.model,
            "fallback_model": self.fallback_model,
        }

    def clear_cache(self) -> None:
        """清空缓存."""
        self._result_cache.clear()
        self._prompt_cache.clear()
        logger.info("审查缓存已清空")
