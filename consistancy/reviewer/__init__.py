"""AI 审查模块.

使用 LiteLLM 调用各种 LLM 模型进行代码审查，
支持结构化输出、缓存和降级策略.
"""

from consistancy.reviewer.ai_reviewer import AIReviewer, ReviewCache
from consistancy.reviewer.models import (
    CommentCategory,
    ReviewComment,
    ReviewResult,
    Severity,
)
from consistancy.reviewer.prompts import (
    PromptCache,
    PromptTemplate,
    ReviewContext,
    ReviewType,
)

__all__ = [
    # 审查器
    "AIReviewer",
    "ReviewCache",
    # 数据模型
    "ReviewResult",
    "ReviewComment",
    "Severity",
    "CommentCategory",
    # Prompt
    "ReviewContext",
    "ReviewType",
    "PromptTemplate",
    "PromptCache",
]
