"""AI 审查输出模型.

使用 Pydantic 定义结构化输出格式.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """严重程度."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommentCategory(str, Enum):
    """评论类别."""

    BUG = "bug"
    SECURITY = "security"
    STYLE = "style"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    OTHER = "other"


class ReviewComment(BaseModel):
    """单条审查评论.

    Attributes:
        file: 文件路径
        line: 行号（可选）
        message: 评论内容
        suggestion: 改进建议（可选）
        severity: 严重程度
        category: 评论类别
        confidence: 置信度（0-1）
    """

    file: str | None = Field(None, description="File path")
    line: int | None = Field(None, ge=1, description="Line number")
    message: str = Field(..., min_length=1, description="Review comment")
    suggestion: str | None = Field(None, description="Suggested improvement")
    severity: Severity = Field(Severity.MEDIUM, description="Issue severity")
    category: CommentCategory = Field(CommentCategory.OTHER, description="Comment category")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Confidence score")

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        """验证消息非空."""
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()

    class Config:
        """Pydantic 配置."""

        json_schema_extra = {
            "example": {
                "file": "src/main.py",
                "line": 42,
                "message": "Potential SQL injection vulnerability",
                "suggestion": "Use parameterized queries",
                "severity": "high",
                "category": "security",
                "confidence": 0.95,
            }
        }


class ReviewSummary(BaseModel):
    """审查摘要.

    整体评估和统计信息.
    """

    overall: str = Field(..., description="Overall assessment (2-3 sentences)")
    severity: Severity = Field(Severity.LOW, description="Overall severity")
    categories: dict[str, int] = Field(default_factory=dict, description="Issues by category")
    total_comments: int = Field(0, ge=0, description="Total number of comments")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Overall confidence")


class ReviewResult(BaseModel):
    """完整审查结果.

    AI 审查的结构化输出.
    """

    summary: str = Field(..., description="Brief overall assessment")
    severity: Severity = Field(Severity.LOW, description="Overall severity")
    comments: list[ReviewComment] = Field(default_factory=list, description="Review comments")
    action_items: list[str] = Field(default_factory=list, description="Required actions")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")

    @field_validator("comments")
    @classmethod
    def validate_comments(cls, v: list[ReviewComment]) -> list[ReviewComment]:
        """验证评论列表."""
        # 按严重程度排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(v, key=lambda x: severity_order.get(x.severity.value, 4))

    @property
    def critical_count(self) -> int:
        """严重问题数量."""
        return sum(1 for c in self.comments if c.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        """高优先级问题数量."""
        return sum(1 for c in self.comments if c.severity == Severity.HIGH)

    @property
    def has_blocking_issues(self) -> bool:
        """是否有阻塞性问题."""
        return self.critical_count > 0 or self.high_count > 0

    def get_comments_by_severity(self, severity: Severity) -> list[ReviewComment]:
        """获取指定严重程度的评论."""
        return [c for c in self.comments if c.severity == severity]

    def get_comments_by_category(self, category: CommentCategory) -> list[ReviewComment]:
        """获取指定类别的评论."""
        return [c for c in self.comments if c.category == category]

    def to_markdown(self) -> str:
        """转换为 Markdown 格式."""
        lines = ["# AI Code Review"]
        lines.append(f"\n## Summary\n{self.summary}")
        lines.append(f"\n**Overall Severity**: {self.severity.value.upper()}")

        if self.comments:
            lines.append(f"\n## Comments ({len(self.comments)})")
            for comment in self.comments:
                lines.append(f"\n### {comment.category.value.upper()}: {comment.severity.value}")
                if comment.file:
                    loc = f"{comment.file}:{comment.line}" if comment.line else comment.file
                    lines.append(f"**Location**: `{loc}`")
                lines.append(f"\n{comment.message}")
                if comment.suggestion:
                    lines.append(f"\n**Suggestion**: {comment.suggestion}")

        if self.action_items:
            lines.append("\n## Action Items")
            for item in self.action_items:
                lines.append(f"- [ ] {item}")

        return "\n".join(lines)

    class Config:
        """Pydantic 配置."""

        json_schema_extra = {
            "example": {
                "summary": "The code changes introduce a potential security vulnerability.",
                "severity": "high",
                "comments": [
                    {
                        "file": "src/auth.py",
                        "line": 45,
                        "message": "Password is stored in plain text",
                        "suggestion": "Use bcrypt or argon2 for password hashing",
                        "severity": "critical",
                        "category": "security",
                        "confidence": 0.99,
                    }
                ],
                "action_items": ["Fix password storage vulnerability"],
            }
        }
