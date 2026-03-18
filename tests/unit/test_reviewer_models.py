"""AI 审查模型单元测试."""

import pytest
from pydantic import ValidationError

from consistancy.reviewer.models import (
    CommentCategory,
    ReviewComment,
    ReviewResult,
    Severity,
)


class TestReviewComment:
    """ReviewComment 测试."""

    def test_basic_creation(self) -> None:
        """测试基本创建."""
        comment = ReviewComment(
            file="test.py",
            line=42,
            message="This is a test comment",
            severity=Severity.HIGH,
            category=CommentCategory.BUG,
        )

        assert comment.file == "test.py"
        assert comment.line == 42
        assert comment.severity == Severity.HIGH

    def test_defaults(self) -> None:
        """测试默认值."""
        comment = ReviewComment(message="Test")

        assert comment.severity == Severity.MEDIUM
        assert comment.category == CommentCategory.OTHER
        assert comment.confidence == 0.8
        assert comment.file is None
        assert comment.line is None

    def test_message_required(self) -> None:
        """测试消息必填."""
        with pytest.raises(ValidationError):
            ReviewComment(message="")

    def test_message_stripped(self) -> None:
        """测试消息去除空白."""
        comment = ReviewComment(message="  test  ")
        assert comment.message == "test"

    def test_invalid_severity(self) -> None:
        """测试无效严重程度."""
        with pytest.raises(ValidationError):
            ReviewComment(message="Test", severity="invalid")

    def test_invalid_category(self) -> None:
        """测试无效类别."""
        with pytest.raises(ValidationError):
            ReviewComment(message="Test", category="invalid")

    def test_confidence_range(self) -> None:
        """测试置信度范围."""
        # 有效范围
        comment = ReviewComment(message="Test", confidence=0.5)
        assert comment.confidence == 0.5

        comment = ReviewComment(message="Test", confidence=1.0)
        assert comment.confidence == 1.0

        comment = ReviewComment(message="Test", confidence=0.0)
        assert comment.confidence == 0.0

        # 无效范围
        with pytest.raises(ValidationError):
            ReviewComment(message="Test", confidence=1.5)

        with pytest.raises(ValidationError):
            ReviewComment(message="Test", confidence=-0.1)

    def test_line_positive(self) -> None:
        """测试行号必须为正."""
        with pytest.raises(ValidationError):
            ReviewComment(message="Test", line=0)

        with pytest.raises(ValidationError):
            ReviewComment(message="Test", line=-1)


class TestReviewResult:
    """ReviewResult 测试."""

    def test_basic_creation(self) -> None:
        """测试基本创建."""
        result = ReviewResult(
            summary="Test summary",
            severity=Severity.MEDIUM,
        )

        assert result.summary == "Test summary"
        assert result.severity == Severity.MEDIUM
        assert result.comments == []

    def test_comments_sorted_by_severity(self) -> None:
        """测试评论按严重程度排序."""
        result = ReviewResult(
            summary="Test",
            comments=[
                ReviewComment(message="Low", severity=Severity.LOW),
                ReviewComment(message="Critical", severity=Severity.CRITICAL),
                ReviewComment(message="High", severity=Severity.HIGH),
                ReviewComment(message="Medium", severity=Severity.MEDIUM),
            ],
        )

        severities = [c.severity for c in result.comments]
        assert severities == [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
        ]

    def test_critical_count(self) -> None:
        """测试严重问题计数."""
        result = ReviewResult(
            summary="Test",
            comments=[
                ReviewComment(message="Critical", severity=Severity.CRITICAL),
                ReviewComment(message="Critical2", severity=Severity.CRITICAL),
                ReviewComment(message="High", severity=Severity.HIGH),
            ],
        )

        assert result.critical_count == 2
        assert result.high_count == 1

    def test_has_blocking_issues(self) -> None:
        """测试阻塞性问题判断."""
        # 无阻塞问题
        result1 = ReviewResult(
            summary="Test",
            comments=[
                ReviewComment(message="Low", severity=Severity.LOW),
            ],
        )
        assert not result1.has_blocking_issues

        # 有严重问题
        result2 = ReviewResult(
            summary="Test",
            comments=[
                ReviewComment(message="Critical", severity=Severity.CRITICAL),
            ],
        )
        assert result2.has_blocking_issues

        # 有高优先级问题
        result3 = ReviewResult(
            summary="Test",
            comments=[
                ReviewComment(message="High", severity=Severity.HIGH),
            ],
        )
        assert result3.has_blocking_issues

    def test_get_comments_by_severity(self) -> None:
        """测试按严重程度获取评论."""
        result = ReviewResult(
            summary="Test",
            comments=[
                ReviewComment(message="High1", severity=Severity.HIGH),
                ReviewComment(message="Low", severity=Severity.LOW),
                ReviewComment(message="High2", severity=Severity.HIGH),
            ],
        )

        high_comments = result.get_comments_by_severity(Severity.HIGH)
        assert len(high_comments) == 2
        assert all(c.severity == Severity.HIGH for c in high_comments)

    def test_get_comments_by_category(self) -> None:
        """测试按类别获取评论."""
        result = ReviewResult(
            summary="Test",
            comments=[
                ReviewComment(message="Bug", category=CommentCategory.BUG),
                ReviewComment(message="Style", category=CommentCategory.STYLE),
                ReviewComment(message="Another bug", category=CommentCategory.BUG),
            ],
        )

        bug_comments = result.get_comments_by_category(CommentCategory.BUG)
        assert len(bug_comments) == 2
        assert all(c.category == CommentCategory.BUG for c in bug_comments)

    def test_to_markdown(self) -> None:
        """测试 Markdown 转换."""
        result = ReviewResult(
            summary="Test summary",
            severity=Severity.HIGH,
            comments=[
                ReviewComment(
                    file="test.py",
                    line=42,
                    message="Test issue",
                    suggestion="Fix it",
                    severity=Severity.MEDIUM,
                    category=CommentCategory.BUG,
                ),
            ],
            action_items=["Fix the bug"],
        )

        md = result.to_markdown()

        assert "# AI Code Review" in md
        assert "Test summary" in md
        assert "test.py:42" in md
        assert "Fix it" in md
        assert "Action Items" in md

    def test_to_markdown_no_comments(self) -> None:
        """测试无评论的 Markdown 转换."""
        result = ReviewResult(
            summary="LGTM",
            severity=Severity.LOW,
        )

        md = result.to_markdown()

        assert "LGTM" in md
        assert "Comments" not in md


class TestSeverity:
    """Severity 枚举测试."""

    def test_values(self) -> None:
        """测试枚举值."""
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
        assert Severity.CRITICAL.value == "critical"

    def test_comparison(self) -> None:
        """测试比较."""
        # 可以按严重性排序
        severities = [
            Severity.LOW,
            Severity.CRITICAL,
            Severity.MEDIUM,
            Severity.HIGH,
        ]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_severities = sorted(severities, key=lambda s: order[s.value])

        assert sorted_severities == [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
        ]


class TestCommentCategory:
    """CommentCategory 枚举测试."""

    def test_values(self) -> None:
        """测试枚举值."""
        assert CommentCategory.BUG.value == "bug"
        assert CommentCategory.SECURITY.value == "security"
        assert CommentCategory.STYLE.value == "style"
