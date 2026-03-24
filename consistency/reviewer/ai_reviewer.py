"""AI 代码审查器.

使用 LLM Provider 抽象层调用多种模型，
支持 DeepSeek、Claude、Grok 等任意 OpenAI 兼容模型.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from consistency.config import get_settings
from consistency.core.gitnexus_client import GitNexusClient, get_gitnexus_client
from consistency.llm import LLMConfig, LLMProviderFactory
from consistency.llm.base import BaseLLMProvider
from consistency.reviewer.context_enhancer import ContextEnhancer
from consistency.reviewer.disk_cache import DiskCache
from consistency.reviewer.models import (
    CommentCategory,
    ReviewComment,
    ReviewResult,
    Severity,
)
from consistency.reviewer.prompts import PromptCache, PromptTemplate, ReviewContext, ReviewType

logger = logging.getLogger(__name__)


@dataclass
class ReviewCache:
    """审查结果缓存项."""

    result: ReviewResult
    timestamp: float
    model: str


class AIReviewer:
    """AI 代码审查器.

    使用 LLM Provider 统一接口调用多种 LLM 模型，
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
        force_json: bool = True,
        provider_type: str = "litellm",
        gitnexus_client: GitNexusClient | None = None,
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
            force_json: 是否强制 JSON 输出（使用 response_format，需要模型支持）
            provider_type: LLM Provider 类型（默认 litellm）
            gitnexus_client: GitNexus 客户端（可选，如果不提供则尝试自动获取）
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
        self.force_json = force_json
        self.provider_type = provider_type
        self.gitnexus = gitnexus_client or get_gitnexus_client()

        # 初始化 LLM Provider
        self._provider: BaseLLMProvider | None = None
        self._fallback_provider: BaseLLMProvider | None = None

        # 缓存
        self._prompt_cache = PromptCache()
        self._result_cache: dict[str, ReviewCache] = {}
        self._cache_ttl = cache_ttl
        self._disk_cache = DiskCache(cache_dir, ttl=cache_ttl) if cache_dir else None

        # 统计
        self._stats = {
            "requests": 0,
            "cache_hits": 0,
            "disk_cache_hits": 0,
            "errors": 0,
            "tokens_used": 0,
            "json_parse_success": 0,
            "json_parse_fallback": 0,
        }

        self._validate_setup()

    def _get_provider(self, use_fallback: bool = False) -> BaseLLMProvider:
        """获取或创建 LLM Provider 实例.

        Args:
            use_fallback: 是否使用备选模型

        Returns:
            LLM Provider 实例
        """
        if use_fallback:
            if self._fallback_provider is None:
                config = LLMConfig(
                    model=self.fallback_model,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                )
                self._fallback_provider = LLMProviderFactory.create(self.provider_type, config)
            return self._fallback_provider

        if self._provider is None:
            config = LLMConfig(
                model=self.model,
                api_key=self.api_key,
                api_base=self.api_base,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
            self._provider = LLMProviderFactory.create(self.provider_type, config)
        return self._provider

    def _validate_setup(self) -> None:
        """验证配置."""
        if not self.api_key:
            logger.warning("未配置 API 密钥，审查功能将不可用")

    async def review(
        self,
        context: ReviewContext | str,
        review_type: ReviewType = ReviewType.GENERAL,
        use_cache: bool = True,
        raise_on_error: bool = False,
    ) -> ReviewResult:
        """执行 AI 代码审查.

        Args:
            context: 审查上下文（或 diff 字符串）
            review_type: 审查类型
            use_cache: 是否使用缓存
            raise_on_error: 是否在错误时抛出异常（用于备选模型回退）

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
                return cached

        # 获取 GitNexus 上下文增强
        gitnexus_context = ""
        if self.gitnexus.is_available():
            context_enhancer = ContextEnhancer(self.gitnexus)
            try:
                primary_file = Path(context.files_changed[0]) if context.files_changed else Path(".")
                gitnexus_context = await context_enhancer.enhance(
                    file_path=primary_file,
                    code=context.diff or "",
                )
            except Exception as e:
                logger.debug(f"GitNexus 上下文获取失败: {e}")
                gitnexus_context = ""
        else:
            logger.debug("GitNexus 不可用，跳过上下文增强")

        # 构建 Prompt
        messages = self._build_messages(context, review_type)

        # 添加上下文到 system message（如果获取成功）
        if gitnexus_context and messages:
            # 在第一条消息（system）后添加上下文
            messages[0]["content"] += f"\n\n{gitnexus_context}"

        # 调用 LLM
        start_time = time.perf_counter()
        try:
            provider = self._get_provider()
            response = await provider.complete_json(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
            duration = time.perf_counter() - start_time
            logger.info(f"LLM 调用完成: {duration:.2f}s")

            # 更新统计
            self._stats["requests"] += 1
            if response.usage:
                self._stats["tokens_used"] += response.usage.get("total_tokens", 0)

            # 解析结果
            result = self._parse_response(response.content)

            # 缓存结果
            if use_cache:
                self._cache_result(cache_key, result)

            return result

        except TimeoutError as e:
            self._stats["errors"] += 1
            logger.error(f"LLM 调用超时: {e}")
            if raise_on_error:
                raise
            return ReviewResult(
                summary="审查超时，请稍后重试",
                severity=Severity.LOW,
                comments=[],
                action_items=["增加超时时间或稍后重试"],
                metadata={"error": "timeout", "detail": str(e)},
            )
        except ConnectionError as e:
            self._stats["errors"] += 1
            logger.error(f"网络连接错误: {e}")
            if raise_on_error:
                raise
            return ReviewResult(
                summary="网络连接失败，请检查网络",
                severity=Severity.LOW,
                comments=[],
                action_items=["检查网络连接和 API 配置"],
                metadata={"error": "connection", "detail": str(e)},
            )
        except Exception as e:
            self._stats["errors"] += 1
            logger.exception(f"审查失败（未预期错误）: {e}")
            if raise_on_error:
                raise
            # 返回错误结果
            return ReviewResult(
                summary=f"审查失败: {e}",
                severity=Severity.LOW,
                comments=[],
                action_items=["请检查 API 配置和网络连接，如问题持续请联系支持"],
                metadata={"error": str(e), "error_type": type(e).__name__},
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
            return await self.review(context, review_type, raise_on_error=True)
        except Exception as e:
            logger.warning(f"主模型失败，尝试备选模型: {e}")

            # 切换到备选 Provider
            try:
                fallback_provider = self._get_provider(use_fallback=True)
                # 标准化上下文
                if isinstance(context, str):
                    context = ReviewContext(diff=context)

                messages = self._build_messages(context, review_type)
                response = await fallback_provider.complete_json(
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                )

                # 更新统计
                self._stats["requests"] += 1
                if response.usage:
                    self._stats["tokens_used"] += response.usage.get("total_tokens", 0)

                result = self._parse_response(response.content)
                result.metadata["used_fallback_model"] = True
                result.metadata["fallback_model"] = self.fallback_model
                return result

            except Exception as fallback_error:
                logger.error(f"备选模型也失败: {fallback_error}")
                return ReviewResult(
                    summary=f"主模型和备选模型均失败: {e}, {fallback_error}",
                    severity=Severity.LOW,
                    comments=[],
                    action_items=["检查 API 配置和网络连接"],
                    metadata={
                        "error": "both_models_failed",
                        "primary_error": str(e),
                        "fallback_error": str(fallback_error),
                    },
                )

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

    def _parse_response(self, content: str) -> ReviewResult:
        """解析 LLM 响应.

        由于使用了 response_format={"type": "json_object"}，
        LLM 应该直接返回有效的 JSON 字符串。

        Args:
            content: 响应文本

        Returns:
            结构化结果
        """
        # 首先尝试直接解析（JSON mode 应该直接返回有效 JSON）
        try:
            data = json.loads(content)
            self._stats["json_parse_success"] += 1
            return ReviewResult.model_validate(data)
        except json.JSONDecodeError:
            pass  # 继续尝试提取

        # 尝试从文本中提取 JSON（兼容模式，某些模型可能不完全支持 JSON mode）
        json_content = self._extract_json(content)

        try:
            data = json.loads(json_content)
            self._stats["json_parse_success"] += 1
            return ReviewResult.model_validate(data)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败，使用启发式解析: {e}")
            self._stats["json_parse_fallback"] += 1
            return self._heuristic_parse(content)
        except Exception as e:
            logger.error(f"解析失败: {e}")
            self._stats["json_parse_fallback"] += 1
            return self._heuristic_parse(content)

    def _extract_json(self, content: str) -> str:
        """从文本中提取 JSON."""
        # 尝试找到 JSON 代码块
        import re

        # 匹配 ```json ... ```
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            return match.group(1)

        # 尝试找到 {...}
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            return match.group(1)

        return content

    def _heuristic_parse(self, content: str) -> ReviewResult:
        """启发式解析非结构化响应."""
        comments: list[ReviewComment] = []

        # 简单提取建议
        import re

        # 查找 "Line X:" 或 "File Y:" 模式
        file_pattern = r"(?:[Ff]ile|[Ff]ile path):?\s*[`\']?(\S+)[`\']?"
        line_pattern = r"(?:[Ll]ine|[Ll]n):?\s*(\d+)"

        lines = content.split("\n")
        current_file: str | None = None
        current_line: int | None = None
        current_message: list[str] = []

        def _save_comment() -> None:
            """保存当前评论（如果消息不为空）."""
            nonlocal current_message
            if current_message:
                msg = " ".join(current_message).strip()
                if msg:  # 确保消息不为空
                    comments.append(
                        ReviewComment(
                            file=current_file,
                            line=current_line,
                            message=msg,
                            suggestion=None,
                            severity=Severity.MEDIUM,
                            category=CommentCategory.OTHER,
                            confidence=0.8,
                        )
                    )
                current_message = []

        for line in lines:
            # 检查是否是新文件/行
            file_match = re.search(file_pattern, line)
            line_match = re.search(line_pattern, line)

            if file_match or line_match:
                _save_comment()

                if file_match:
                    current_file = file_match.group(1)
                if line_match:
                    current_line = int(line_match.group(1))
            else:
                current_message.append(line)

        # 保存最后一个评论
        _save_comment()

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
        """获取缓存的结果（内存 + 磁盘）."""
        # 先检查内存缓存
        if key in self._result_cache:
            cached = self._result_cache[key]
            if time.time() - cached.timestamp <= self._cache_ttl:
                self._stats["cache_hits"] += 1
                return cached.result
            del self._result_cache[key]

        # 再检查磁盘缓存
        if self._disk_cache:
            disk_cached = self._disk_cache.get(key)
            if disk_cached:
                result, model = disk_cached
                self._stats["disk_cache_hits"] += 1
                # 回填内存缓存
                self._result_cache[key] = ReviewCache(
                    result=result,
                    timestamp=time.time(),
                    model=model,
                )
                return result

        return None

    def _cache_result(self, key: str, result: ReviewResult) -> None:
        """缓存结果（内存 + 磁盘）."""
        # 内存缓存
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

        # 磁盘缓存
        if self._disk_cache:
            self._disk_cache.set(key, result, self.model)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        stats = {
            **self._stats,
            "memory_cache_size": len(self._result_cache),
            "model": self.model,
            "fallback_model": self.fallback_model,
            "provider_type": self.provider_type,
        }
        if self._disk_cache:
            stats["disk_cache"] = self._disk_cache.get_stats()
        return stats

    def clear_cache(self) -> None:
        """清空缓存."""
        self._result_cache.clear()
        self._prompt_cache.clear()
        if self._disk_cache:
            self._disk_cache.clear()
        logger.info("审查缓存已清空")
