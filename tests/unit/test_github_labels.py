"""Tests for GitHub labels module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistency.exceptions import GitHubError
from consistency.github.labels import LabelManager


class TestLabelManager:
    """Test LabelManager class."""

    @pytest.fixture
    def mock_client(self):
        """Create mock GitHub client."""
        client = MagicMock()
        client.semaphore = MagicMock()
        client.semaphore.__aenter__ = AsyncMock(return_value=None)
        client.semaphore.__aexit__ = AsyncMock(return_value=None)
        client.get_client = MagicMock()
        return client

    @pytest.fixture
    def label_manager(self, mock_client):
        """Create label manager with mock client."""
        return LabelManager(mock_client)

    def test_initialization(self, mock_client):
        """Test initialization."""
        manager = LabelManager(mock_client)
        assert manager.client == mock_client
        assert manager.LABEL_ISSUES_FOUND == "gitconsistency:issues-found"
        assert manager.LABEL_PASSED == "gitconsistency:passed"

    @pytest.mark.asyncio
    async def test_update_pr_status_with_issues(self, label_manager, mock_client):
        """Test updating PR status with issues found."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.labels = []

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        result = await label_manager.update_pr_status(
            "owner/repo", 42, has_issues=True
        )

        assert result["success"] is True
        mock_pr.add_to_labels.assert_called_once_with("gitconsistency:issues-found")

    @pytest.mark.asyncio
    async def test_update_pr_status_without_issues(self, label_manager, mock_client):
        """Test updating PR status without issues."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_label = MagicMock()
        mock_label.name = "gitconsistency:issues-found"
        mock_pr.labels = [mock_label]

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        result = await label_manager.update_pr_status(
            "owner/repo", 42, has_issues=False
        )

        assert result["success"] is True
        mock_pr.add_to_labels.assert_called_once_with("gitconsistency:passed")
        mock_pr.remove_from_labels.assert_called_once_with("gitconsistency:issues-found")

    @pytest.mark.asyncio
    async def test_update_pr_status_preserves_existing_labels(self, label_manager, mock_client):
        """Test that existing labels are preserved."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_label = MagicMock()
        mock_label.name = "existing-label"
        mock_pr.labels = [mock_label]

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        await label_manager.update_pr_status("owner/repo", 42, has_issues=True)

        # Should not touch existing labels
        mock_pr.remove_from_labels.assert_not_called()

    @pytest.mark.asyncio
    async def test_manage_labels_add_and_remove(self, label_manager, mock_client):
        """Test managing labels with add and remove."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_label = MagicMock()
        mock_label.name = "old-label"
        mock_pr.labels = [mock_label]

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        await label_manager._manage_labels(
            "owner/repo", 42, add=["new-label"], remove=["old-label"]
        )

        mock_pr.add_to_labels.assert_called_once_with("new-label")
        mock_pr.remove_from_labels.assert_called_once_with("old-label")

    @pytest.mark.asyncio
    async def test_manage_labels_no_changes(self, label_manager, mock_client):
        """Test managing labels with no changes needed."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_label = MagicMock()
        mock_label.name = "existing-label"
        mock_pr.labels = [mock_label]

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        await label_manager._manage_labels(
            "owner/repo", 42, add=["existing-label"], remove=["other-label"]
        )

        # Should not add already existing label
        mock_pr.add_to_labels.assert_not_called()
        # Should not remove non-existing label
        mock_pr.remove_from_labels.assert_not_called()

    @pytest.mark.asyncio
    async def test_manage_labels_error(self, label_manager, mock_client):
        """Test error handling in label management."""
        mock_client.get_client.side_effect = Exception("GitHub API Error")

        with pytest.raises(GitHubError) as exc_info:
            await label_manager._manage_labels(
                "owner/repo", 42, add=["label"], remove=[]
            )

        assert "标签管理失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_labels(self, label_manager, mock_client):
        """Test add_labels convenience method."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.labels = []

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        await label_manager.add_labels("owner/repo", 42, ["label1", "label2"])

        assert mock_pr.add_to_labels.call_count == 2
        mock_pr.add_to_labels.assert_any_call("label1")
        mock_pr.add_to_labels.assert_any_call("label2")

    @pytest.mark.asyncio
    async def test_remove_labels(self, label_manager, mock_client):
        """Test remove_labels convenience method."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_label = MagicMock()
        mock_label.name = "label1"
        mock_pr.labels = [mock_label]

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        await label_manager.remove_labels("owner/repo", 42, ["label1"])

        mock_pr.remove_from_labels.assert_called_once_with("label1")

    @pytest.mark.asyncio
    async def test_update_pr_status_with_summary(self, label_manager, mock_client):
        """Test updating PR status with summary parameter."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.labels = []

        mock_client.get_client.return_value = mock_gh
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        result = await label_manager.update_pr_status(
            "owner/repo", 42, has_issues=True, summary="Found 5 issues"
        )

        # Summary is accepted but not currently used
        assert result["success"] is True
        assert result["labels_updated"] is True
