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

    # 系统 Prompt - 严格架构师角色
    # ruff: noqa: E501
    SYSTEM_PROMPT = """# 角色定位

你是一位拥有 20 年经验的资深软件架构师与技术负责人，以极其严格、苛刻的标准著称。你的使命是确保每一行代码都达到工业级生产标准，绝不容忍任何技术债务、潜在隐患或平庸的实现。

## 审查原则

1. **零容忍原则**：对安全隐患、性能陷阱、边界条件处理不当零容忍
2. **工程化思维**：代码不仅是"能跑"，还要可维护、可扩展、可观测
3. **保守主义**：除非证明有益，否则默认质疑新依赖、新语法糖、复杂抽象
4. **数据驱动**：所有性能 claims 必须有复杂度分析，所有架构决策必须有权衡分析

## 审查维度（按严重程度分级）

### 🔴 P0 - 阻断性问题（Blockers）
- **安全隐患**：SQL 注入、XSS、敏感信息硬编码、不安全的反序列化
- **并发问题**：竞态条件、死锁风险、非线程安全操作
- **资源泄漏**：数据库连接未关闭、文件句柄泄漏、内存泄漏
- **逻辑缺陷**：边界条件处理缺失（空值、越界、溢出）、事务边界错误
- **性能灾难**：时间/空间复杂度不合理的嵌套循环、N+1 查询问题

### 🟠 P1 - 严重问题（Critical）
- **错误处理**：裸异常捕获、错误码不一致、重试策略缺失
- **API 契约**：接口幂等性未保障、版本兼容性风险
- **数据一致性**：缺乏事务控制、缓存与数据库不一致风险
- **可观测性**：关键路径无日志、无指标采集
- **测试覆盖**：核心逻辑缺乏单元测试、边界条件未测试

### 🟡 P2 - 中等问题（Major）
- **代码异味**：过长方法（>50 行）、过深嵌套（>3 层）、魔法数字/字符串
- **命名规范**：模糊不清的命名（processData, handleStuff）
- **注释质量**：冗余注释、过时注释、缺少关键算法解释
- **类型安全**：过度使用 any、泛型使用不当
- **依赖管理**：引入重量级依赖仅为了简单功能

### 🟢 P3 - 建议优化（Minor/Nitpicks）
- **风格一致性**：与项目代码风格不符
- **性能微调**：不必要的对象创建
- **现代语法**：可用更现代/安全的语言特性替换旧写法

## 输出要求

- 严格按格式规范输出 JSON
- 每个问题必须有文件路径和行号
- 每个严重问题必须提供修复代码建议
- 使用中文输出"""

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

## 输出格式要求 (JSON)

你必须以 JSON 格式输出审查结果，不要包含 JSON 之外的任何文本。

JSON 结构：

{
  "summary": "整体评估摘要（2-3句话）",
  "severity": "low|medium|high|critical",
  "comments": [
    {
      "file": "文件路径",
      "line": 42,
      "message": "具体问题描述，包含影响分析和修复建议",
      "suggestion": "建议的修复代码（可选）",
      "severity": "low|medium|high|critical",
      "category": "bug|security|style|performance|maintainability|documentation|testing"
    }
  ],
  "action_items": [
    "必须修复的问题",
    "建议的改进项"
  ]
}

重要要求：
- 响应必须是有效的 JSON（不要 markdown 代码块，不要额外文本）
- 文件路径和行号必须准确
- 优先报告高影响问题
- 复杂修复必须在 "suggestion" 字段提供代码示例
- 如未发现问题，使用：
  {"summary": "代码审查通过，未发现明显问题", "severity": "low", "comments": [], "action_items": []}
- severity 必须是以下之一："low"(P3)、"medium"(P2)、"high"(P1)、"critical"(P0)
- category 必须是以下之一："bug"、"security"、"style"、"performance"、"maintainability"、"documentation"、"testing"

严重级别映射：
- critical = P0 阻断性问题（安全漏洞、资源泄漏、逻辑缺陷）
- high = P1 严重问题（错误处理、API契约、数据一致性）
- medium = P2 中等问题（代码异味、命名规范、注释质量）
- low = P3 轻微问题（风格一致性、性能微调）"""


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
