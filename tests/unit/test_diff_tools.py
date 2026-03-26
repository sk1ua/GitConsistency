"""Tests for diff_tools module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistency.tools.diff_tools import (
    DiffHunk,
    DiffParser,
    FileDiff,
    IncrementalReviewer,
    QuickReviewTool,
    quick_review,
    review_diff,
)


class TestDiffHunk:
    """Test DiffHunk dataclass."""

    def test_default_initialization(self):
        """Test default initialization."""
        hunk = DiffHunk(old_start=1, old_count=5, new_start=1, new_count=5)
        assert hunk.old_start == 1
        assert hunk.old_count == 5
        assert hunk.new_start == 1
        assert hunk.new_count == 5
        assert hunk.lines == []
        assert hunk.added_lines == []
        assert hunk.removed_lines == []


class TestFileDiff:
    """Test FileDiff dataclass."""

    def test_default_initialization(self):
        """Test default initialization."""
        diff = FileDiff(old_path="old.py", new_path="new.py")
        assert diff.old_path == "old.py"
        assert diff.new_path == "new.py"
        assert diff.is_new is False
        assert diff.is_deleted is False
        assert diff.hunks == []


class TestDiffParser:
    """Test DiffParser class."""

    @pytest.fixture
    def parser(self):
        """Create parser fixture."""
        return DiffParser()

    def test_parse_empty_diff(self, parser):
        """Test parsing empty diff."""
        result = parser.parse("")
        assert result == []

    def test_parse_whitespace_only_diff(self, parser):
        """Test parsing whitespace-only diff."""
        result = parser.parse("   \n\n   ")
        assert result == []

    def test_parse_simple_diff(self, parser):
        """Test parsing simple diff."""
        diff_text = """diff --git a/test.py b/test.py
index 123..456 789
--- a/test.py
+++ b/test.py
@@ -1,5 +1,5 @@
 line1
-line2
+line2_modified
 line3
 line4
 line5
"""
        result = parser.parse(diff_text)

        assert len(result) == 1
        assert result[0].new_path == "test.py"
        # When old_path == new_path, old_path is set to None
        assert result[0].old_path is None
        assert len(result[0].hunks) == 1

    def test_parse_new_file(self, parser):
        """Test parsing new file diff."""
        diff_text = """diff --git a/new_file.py b/new_file.py
new file mode 100644
index 000..123
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,3 @@
+line1
+line2
+line3
"""
        result = parser.parse(diff_text)

        assert len(result) == 1
        assert result[0].is_new is True
        assert result[0].new_path == "new_file.py"

    def test_parse_deleted_file(self, parser):
        """Test parsing deleted file diff."""
        diff_text = """diff --git a/deleted.py b/deleted.py
deleted file mode 100644
index 123..000
--- a/deleted.py
+++ /dev/null
@@ -1,3 +0,0 @@
-line1
-line2
-line3
"""
        result = parser.parse(diff_text)

        assert len(result) == 1
        assert result[0].is_deleted is True
        assert result[0].new_path == "deleted.py"
        # old_path is same as new_path when deleted, so it's None
        assert result[0].old_path is None

    def test_parse_multiple_files(self, parser):
        """Test parsing diff with multiple files."""
        diff_text = """diff --git a/file1.py b/file1.py
index 123..456 789
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,2 @@
 line1
-line2
+line2_new

diff --git a/file2.py b/file2.py
index abc..def 789
--- a/file2.py
+++ b/file2.py
@@ -1,3 +1,3 @@
 unchanged
-removed
+added
 unchanged
"""
        result = parser.parse(diff_text)

        assert len(result) == 2
        assert result[0].new_path == "file1.py"
        assert result[1].new_path == "file2.py"

    def test_parse_complex_hunk(self, parser):
        """Test parsing complex hunk with multiple changes."""
        diff_text = """diff --git a/complex.py b/complex.py
--- a/complex.py
+++ b/complex.py
@@ -10,15 +10,16 @@
 context_before
-removed1
-removed2
+added1
+added2
+added3
 context_after
 more_context
"""
        result = parser.parse(diff_text)

        assert len(result) == 1
        assert len(result[0].hunks) == 1
        hunk = result[0].hunks[0]
        assert len(hunk.added_lines) == 3
        assert len(hunk.removed_lines) == 2

    def test_parse_hunk_with_no_newline(self, parser):
        """Test parsing hunk with \\ No newline marker."""
        diff_text = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 line1
 line2
\\ No newline at end of file
"""
        result = parser.parse(diff_text)

        assert len(result) == 1
        # The \\ line should be ignored in context counting

    def test_parse_hunk_with_single_line_count(self, parser):
        """Test parsing hunk with implicit count of 1."""
        diff_text = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -5 +5 @@
-old_line
+new_line
"""
        result = parser.parse(diff_text)

        assert len(result) == 1
        hunk = result[0].hunks[0]
        assert hunk.old_start == 5
        assert hunk.old_count == 1
        assert hunk.new_start == 5
        assert hunk.new_count == 1


class TestIncrementalReviewer:
    """Test IncrementalReviewer class."""

    @pytest.fixture
    def reviewer(self):
        """Create reviewer fixture."""
        return IncrementalReviewer()

    def test_initialization(self):
        """Test initialization."""
        reviewer = IncrementalReviewer()
        assert reviewer.diff_parser is not None

    @pytest.mark.asyncio
    async def test_review_diff_empty(self, reviewer):
        """Test reviewing empty diff."""
        result = await reviewer.review_diff("", "/repo/path")

        assert result["files_count"] == 0
        assert result["issues_count"] == 0
        assert "没有检测到变更" in result["summary"]

    @pytest.mark.asyncio
    async def test_review_diff_no_gitnexus(self, reviewer):
        """Test review when GitNexus is unavailable."""
        diff_text = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""
        with patch(
            "consistency.tools.diff_tools.get_gitnexus_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available.return_value = False
            mock_get_client.return_value = mock_client

            with pytest.raises(ValueError) as exc_info:
                await reviewer.review_diff(diff_text, "/repo/path")

            assert "GitNexus" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_review_diff_with_supervisor(self, reviewer):
        """Test review with provided supervisor."""
        diff_text = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 line1
-old_line
+new_line
 line3
"""
        mock_supervisor = MagicMock()
        mock_result = MagicMock()
        mock_result.comments = []
        mock_supervisor.review_batch = AsyncMock(return_value=[mock_result])

        result = await reviewer.review_diff(
            diff_text, "/repo/path", supervisor=mock_supervisor
        )

        assert result["files_count"] == 1
        mock_supervisor.review_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_diff_skips_deleted_files(self, reviewer):
        """Test review skips deleted files."""
        diff_text = """diff --git a/deleted.py b/deleted.py
deleted file mode 100644
--- a/deleted.py
+++ /dev/null
@@ -1,3 +0,0 @@
-line1
-line2
-line3

diff --git a/modified.py b/modified.py
--- a/modified.py
+++ b/modified.py
@@ -1 +1 @@
-old
+new
"""
        mock_supervisor = MagicMock()
        mock_result = MagicMock()
        mock_result.comments = []
        mock_supervisor.review_batch = AsyncMock(return_value=[mock_result])

        result = await reviewer.review_diff(
            diff_text, "/repo/path", supervisor=mock_supervisor
        )

        # Should only review the modified file, not the deleted one
        assert result["files_count"] == 1

    def test_extract_changed_code(self, reviewer):
        """Test extracting changed code."""
        file_diff = FileDiff(
            old_path="old.py",
            new_path="new.py",
            hunks=[
                DiffHunk(
                    old_start=1,
                    old_count=2,
                    new_start=1,
                    new_count=3,
                    added_lines=[(1, "added1"), (2, "added2")],
                )
            ],
        )

        result = reviewer._extract_changed_code(file_diff)

        assert "added1" in result
        assert "added2" in result

    def test_summarize_changes(self, reviewer):
        """Test summarizing changes."""
        file_diff = FileDiff(
            old_path="old.py",
            new_path="new.py",
            is_new=True,
            hunks=[
                DiffHunk(
                    old_start=0,
                    old_count=0,
                    new_start=1,
                    new_count=3,
                    added_lines=[(1, "line1"), (2, "line2"), (3, "line3")],
                    removed_lines=[],
                )
            ],
        )

        result = reviewer._summarize_changes(file_diff)

        assert result["path"] == "new.py"
        assert result["is_new"] is True
        assert result["added_lines"] == 3
        assert result["removed_lines"] == 0


class TestQuickReviewTool:
    """Test QuickReviewTool class."""

    def test_initialization_no_gitnexus(self):
        """Test initialization without GitNexus."""
        with patch(
            "consistency.tools.diff_tools.get_gitnexus_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available.return_value = False
            mock_get_client.return_value = mock_client

            with pytest.raises(ValueError) as exc_info:
                QuickReviewTool()

            assert "GitNexus" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_review_code_no_critical_issues(self):
        """Test reviewing code with no critical issues."""
        from consistency.agents.base import Severity

        with patch(
            "consistency.tools.diff_tools.get_gitnexus_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available.return_value = True
            mock_get_client.return_value = mock_client

            with patch(
                "consistency.agents.ReviewSupervisor"
            ) as mock_supervisor_class:
                mock_supervisor = MagicMock()
                mock_result = MagicMock()
                mock_result.comments = []
                mock_result.summary = "Looks good"
                mock_supervisor.review = AsyncMock(return_value=mock_result)
                mock_supervisor_class.return_value = mock_supervisor

                tool = QuickReviewTool(gitnexus_client=mock_client)
                result = await tool.review_code("code", "test.py")

                assert result["has_critical_issues"] is False
                assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_review_code_with_critical_issues(self):
        """Test reviewing code with critical issues."""
        from consistency.agents.base import Severity
        from consistency.reviewer.models import CommentCategory, ReviewComment

        with patch(
            "consistency.tools.diff_tools.get_gitnexus_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available.return_value = True

            with patch(
                "consistency.agents.ReviewSupervisor"
            ) as mock_supervisor_class:
                mock_supervisor = MagicMock()
                mock_result = MagicMock()
                mock_result.comments = [
                    ReviewComment(
                        message="Critical issue",
                        severity=Severity.CRITICAL,
                        category=CommentCategory.SECURITY,
                        line=10,
                    ),
                    ReviewComment(
                        message="High issue",
                        severity=Severity.HIGH,
                        category=CommentCategory.BUG,
                        line=20,
                    ),
                ]
                mock_result.summary = "Found issues"
                mock_supervisor.review = AsyncMock(return_value=mock_result)
                mock_supervisor_class.return_value = mock_supervisor

                tool = QuickReviewTool(gitnexus_client=mock_client)
                result = await tool.review_code("code", "test.py")

                assert result["has_critical_issues"] is True
                assert len(result["issues"]) == 2


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_review_diff_function(self):
        """Test review_diff convenience function."""
        diff_text = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1 @@
-old
+new
"""

        with patch(
            "consistency.tools.diff_tools.get_gitnexus_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available.return_value = True
            mock_get_client.return_value = mock_client

            with patch(
                "consistency.agents.ReviewSupervisor"
            ) as mock_supervisor_class:
                mock_supervisor = MagicMock()
                mock_result = MagicMock()
                mock_result.comments = []
                mock_supervisor.review_batch = AsyncMock(return_value=[mock_result])
                mock_supervisor_class.return_value = mock_supervisor

                result = await review_diff(diff_text, "/repo")

                assert "files_count" in result

    @pytest.mark.asyncio
    async def test_quick_review_function(self):
        """Test quick_review convenience function."""
        with patch(
            "consistency.tools.diff_tools.get_gitnexus_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.is_available.return_value = True
            mock_get_client.return_value = mock_client

            with patch(
                "consistency.agents.ReviewSupervisor"
            ) as mock_supervisor_class:
                mock_supervisor = MagicMock()
                mock_result = MagicMock()
                mock_result.comments = []
                mock_result.summary = "OK"
                mock_supervisor.review = AsyncMock(return_value=mock_result)
                mock_supervisor_class.return_value = mock_supervisor

                result = await quick_review("code", "test.py")

                assert "file" in result
                assert "duration_ms" in result
