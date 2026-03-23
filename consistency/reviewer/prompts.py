"""Prompt 模板管理.

提供统一、结构化的 Prompt 模板系统，支持代码审查、安全分析、一致性检查等场景.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ReviewType(Enum):
    """审查类型."""

    GENERAL = auto()  # 通用代码审查
    SECURITY = auto()  # 安全焦点审查
    CONSISTENCY = auto()  # 一致性检查
    PERFORMANCE = auto()  # 性能审查
    DOCS = auto()  # 文档审查


@dataclass
class ReviewContext:
    """审查上下文.

    收集审查所需的所有上下文信息.
    """

    # 代码变更
    diff: str = ""
    files_changed: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_deleted: int = 0

    # 图谱信息
    graph_summary: dict[str, Any] = field(default_factory=dict)
    affected_symbols: list[str] = field(default_factory=list)
    impacted_tests: list[str] = field(default_factory=list)

    # 扫描结果
    security_findings: list[dict[str, Any]] = field(default_factory=list)
    drift_findings: list[dict[str, Any]] = field(default_factory=list)
    hotspot_findings: list[dict[str, Any]] = field(default_factory=list)

    # 项目信息
    language: str = "python"
    project_name: str = ""
    base_ref: str = ""
    head_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "diff": self.diff[:5000] if len(self.diff) > 5000 else self.diff,  # 截断
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "affected_symbols": self.affected_symbols[:20],  # 限制数量
            "impacted_tests": self.impacted_tests[:10],
            "security_findings_count": len(self.security_findings),
            "drift_findings_count": len(self.drift_findings),
            "hotspot_findings_count": len(self.hotspot_findings),
            "language": self.language,
            "project_name": self.project_name,
        }


class PromptTemplate:
    """Prompt 模板基类."""

    # 系统 Prompt - 定义 AI 角色和能力
    SYSTEM_PROMPT = """You are an expert code reviewer with deep expertise in software engineering, security, and code quality.

Your responsibilities:
1. Review code changes for bugs, security issues, and anti-patterns
2. Ensure consistency with existing codebase patterns
3. Suggest improvements for readability, performance, and maintainability
4. Be constructive and specific in your feedback

Guidelines:
- Focus on significant issues, not nitpicks
- Explain the "why" behind your suggestions
- Provide code examples when helpful
- Consider context from the knowledge graph and scan results"""

    @classmethod
    def build(
        cls,
        context: ReviewContext,
        review_type: ReviewType = ReviewType.GENERAL,
    ) -> list[dict[str, str]]:
        """构建完整 Prompt.

        Args:
            context: 审查上下文
            review_type: 审查类型

        Returns:
            OpenAI 格式的消息列表
        """
        messages = [
            {"role": "system", "content": cls.SYSTEM_PROMPT},
        ]

        # 添加上下文信息
        context_msg = cls._build_context_message(context)
        messages.append({"role": "user", "content": context_msg})

        # 添加特定类型的审查请求
        review_msg = cls._build_review_message(context, review_type)
        messages.append({"role": "user", "content": review_msg})

        return messages

    @classmethod
    def _build_context_message(cls, context: ReviewContext) -> str:
        """构建上下文消息."""
        parts = ["# Code Review Context"]

        # 变更统计
        parts.append("\n## Changes")
        parts.append(f"- Files changed: {len(context.files_changed)}")
        parts.append(f"- Lines added: {context.lines_added}")
        parts.append(f"- Lines deleted: {context.lines_deleted}")

        if context.files_changed:
            parts.append(f"- Modified files: {', '.join(context.files_changed[:10])}")

        # 安全发现
        if context.security_findings:
            parts.append(f"\n## Security Findings ({len(context.security_findings)})")
            for finding in context.security_findings[:5]:
                parts.append(f"- [{finding.get('severity', 'UNKNOWN')}] {finding.get('message', '')[:100]}")

        # 漂移发现
        if context.drift_findings:
            parts.append(f"\n## Consistency Drifts ({len(context.drift_findings)})")
            for finding in context.drift_findings[:3]:
                parts.append(f"- {finding.get('message', '')[:100]}")

        # 热点发现
        if context.hotspot_findings:
            parts.append(f"\n## Technical Debt Hotspots ({len(context.hotspot_findings)})")
            for finding in context.hotspot_findings[:3]:
                parts.append(f"- {finding.get('message', '').split(chr(10))[0][:100]}")

        # 影响分析
        if context.affected_symbols:
            parts.append("\n## Affected Symbols")
            parts.append(f"- {', '.join(context.affected_symbols[:10])}")

        if context.impacted_tests:
            parts.append("\n## Impacted Tests")
            parts.append(f"- {', '.join(context.impacted_tests[:5])}")

        return "\n".join(parts)

    @classmethod
    def _build_review_message(
        cls,
        context: ReviewContext,
        review_type: ReviewType,
    ) -> str:
        """构建审查请求消息."""
        parts = []

        # 代码 diff
        if context.diff:
            parts.append("# Code Diff")
            parts.append("```diff")
            parts.append(context.diff[:10000])  # 限制长度
            parts.append("```")

        # 审查类型特定指令
        parts.append(f"\n# Review Request ({review_type.name})")

        if review_type == ReviewType.GENERAL:
            parts.append(cls._general_review_instructions())
        elif review_type == ReviewType.SECURITY:
            parts.append(cls._security_review_instructions())
        elif review_type == ReviewType.CONSISTENCY:
            parts.append(cls._consistency_review_instructions())
        elif review_type == ReviewType.PERFORMANCE:
            parts.append(cls._performance_review_instructions())

        # 输出格式要求
        parts.append(cls._output_format_instructions())

        return "\n".join(parts)

    @classmethod
    def _general_review_instructions(cls) -> str:
        """通用审查指令."""
        return """
Please provide a comprehensive code review focusing on:
1. Code correctness and potential bugs
2. Code readability and maintainability
3. Adherence to best practices
4. Edge cases and error handling
5. Test coverage considerations"""

    @classmethod
    def _security_review_instructions(cls) -> str:
        """安全审查指令."""
        return """
Security-focused review - prioritize:
1. Injection vulnerabilities (SQL, command, etc.)
2. Input validation and sanitization
3. Authentication/authorization issues
4. Sensitive data exposure
5. Cryptographic weaknesses
6. Insecure dependencies"""

    @classmethod
    def _consistency_review_instructions(cls) -> str:
        """一致性审查指令."""
        return """
Consistency-focused review - check:
1. Naming conventions and style
2. Error handling patterns
3. API design consistency
4. Documentation completeness
5. Test patterns and coverage"""

    @classmethod
    def _performance_review_instructions(cls) -> str:
        """性能审查指令."""
        return """
Performance-focused review - examine:
1. Algorithmic complexity
2. Resource usage (memory, CPU, I/O)
3. Database query efficiency
4. Caching opportunities
5. Async/await usage patterns"""

    @classmethod
    def _output_format_instructions(cls) -> str:
        """输出格式指令."""
        return """

## Output Format

Provide your review in the following JSON structure:

```json
{
  "summary": "Brief overall assessment (2-3 sentences)",
  "severity": "low|medium|high|critical",
  "comments": [
    {
      "file": "path/to/file",
      "line": 42,
      "message": "Specific feedback with explanation",
      "suggestion": "Suggested code improvement (optional)",
      "severity": "low|medium|high|critical",
      "category": "bug|security|style|performance|maintainability"
    }
  ],
  "action_items": [
    "Required changes before approval",
    "Suggested improvements"
  ]
}
```

Requirements:
- Be specific with file paths and line numbers
- Prioritize high-impact issues
- Include code examples for complex suggestions
- If no issues found, confirm with {  # noqa: E501
"summary": "LGTM! No significant issues found.", "severity": "low", "comments": []}"""


class PromptCache:
    """Prompt 缓存.

    缓存相同上下文的 Prompt，避免重复构建.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._cache: dict[str, list[dict[str, str]]] = {}
        self._max_size = max_size

    def get_key(self, context: ReviewContext, review_type: ReviewType) -> str:
        """生成缓存键."""
        # 基于 diff 哈希和类型
        import hashlib

        content = f"{context.diff[:1000]}:{review_type.name}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(
        self,
        context: ReviewContext,
        review_type: ReviewType,
    ) -> list[dict[str, str]] | None:
        """获取缓存的 Prompt."""
        key = self.get_key(context, review_type)
        return self._cache.get(key)

    def set(
        self,
        context: ReviewContext,
        review_type: ReviewType,
        messages: list[dict[str, str]],
    ) -> None:
        """缓存 Prompt."""
        key = self.get_key(context, review_type)

        if len(self._cache) >= self._max_size:
            # 简单的 LRU：清空一半
            self._cache = dict(list(self._cache.items())[self._max_size // 2 :])

        self._cache[key] = messages

    def clear(self) -> None:
        """清空缓存."""
        self._cache.clear()
