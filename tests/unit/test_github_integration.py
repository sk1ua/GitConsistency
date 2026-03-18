"""GitHub 集成单元测试."""

import os
from unittest.mock import MagicMock, patch

import pytest

from consistancy.github_integration import GitHubIntegration, PRComment, PRInfo


class TestGitHubIntegrationInit:
    """初始化测试."""

    def test_default_init(self) -> None:
        """测试默认初始化."""
        with patch("consistancy.github_integration.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(github_token="test-token")
            
            github = GitHubIntegration()
            assert github.token == "test-token"
            assert github.delete_old_comments is True
            assert github.max_concurrent == 5

    def test_custom_init(self) -> None:
        """测试自定义初始化."""
        github = GitHubIntegration(
            token="custom-token",
            delete_old_comments=False,
            max_concurrent=10,
        )
        assert github.token == "custom-token"
        assert github.delete_old_comments is False
        assert github.max_concurrent == 10

    def test_no_token_warning(self) -> None:
        """测试无 token 时警告."""
        with patch("consistancy.github_integration.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(github_token=None)
            
            with patch("consistancy.github_integration.logger") as mock_logger:
                GitHubIntegration()
                mock_logger.warning.assert_called_once()


class TestGetClient:
    """客户端获取测试."""

    def test_lazy_client_creation(self) -> None:
        """测试延迟客户端创建."""
        github = GitHubIntegration(token="test")
        assert github._client is None

        with patch("github.Github") as mock_github:
            client = github._get_client()
            assert client is not None
            mock_github.assert_called_once_with("test")


class TestPostComment:
    """发布评论测试."""

    @pytest.fixture
    def github(self) -> GitHubIntegration:
        return GitHubIntegration(token="test-token")

    @pytest.mark.asyncio
    async def test_post_comment_success(self, github: GitHubIntegration) -> None:
        """测试成功发布评论."""
        mock_comment = MagicMock()
        mock_comment.id = 12345
        mock_comment.html_url = "https://github.com/owner/repo/issues/1#issuecomment-12345"

        mock_pr = MagicMock()
        mock_pr.create_issue_comment.return_value = mock_comment

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        with patch.object(github, "_get_client") as mock_get_client:
            mock_get_client.return_value.get_repo.return_value = mock_repo

            result = await github.post_comment("owner/repo", 1, "Test comment body")

            assert result["id"] == 12345
            assert "url" in result
            mock_pr.create_issue_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_comment_with_signature(self, github: GitHubIntegration) -> None:
        """测试评论添加签名."""
        mock_pr = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        with patch.object(github, "_get_client") as mock_get_client:
            mock_get_client.return_value.get_repo.return_value = mock_repo

            await github.post_comment("owner/repo", 1, "Body")

            call_args = mock_pr.create_issue_comment.call_args[0][0]
            assert "ConsistenCy 2.0" in call_args

    @pytest.mark.asyncio
    async def test_post_comment_truncation(self, github: GitHubIntegration) -> None:
        """测试长评论截断."""
        mock_pr = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        with patch.object(github, "_get_client") as mock_get_client:
            mock_get_client.return_value.get_repo.return_value = mock_repo

            long_body = "A" * 70000
            await github.post_comment("owner/repo", 1, long_body)

            call_args = mock_pr.create_issue_comment.call_args[0][0]
            assert len(call_args) <= github.MAX_COMMENT_LENGTH

    @pytest.mark.asyncio
    async def test_post_comment_not_configured(self) -> None:
        """测试未配置时返回错误."""
        github = GitHubIntegration(token=None)

        result = await github.post_comment("owner/repo", 1, "Body")

        assert "error" in result


class TestDeletePreviousComments:
    """删除旧评论测试."""

    @pytest.mark.asyncio
    async def test_delete_matching_comments(self) -> None:
        """测试删除匹配签名的评论."""
        github = GitHubIntegration(token="test")

        # 创建 mock 评论
        mock_comment1 = MagicMock()
        mock_comment1.body = "Test\n<!-- ConsistenCy 2.0 Code Review -->"
        mock_comment1.id = 1

        mock_comment2 = MagicMock()
        mock_comment2.body = "Other comment"
        mock_comment2.id = 2

        mock_pr = MagicMock()
        mock_pr.get_issue_comments.return_value = [mock_comment1, mock_comment2]

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        with patch.object(github, "_get_client") as mock_get_client:
            mock_get_client.return_value.get_repo.return_value = mock_repo

            deleted = await github._delete_previous_comments("owner/repo", 1)

            assert deleted == 1
            mock_comment1.delete.assert_called_once()
            mock_comment2.delete.assert_not_called()


class TestFileComments:
    """文件评论测试."""

    @pytest.mark.asyncio
    async def test_post_file_comment(self) -> None:
        """测试发布文件行级评论."""
        github = GitHubIntegration(token="test")

        mock_comment = MagicMock()
        mock_comment.id = 123
        mock_comment.html_url = "https://..."

        mock_pr = MagicMock()
        mock_pr.head.sha = "abc123"
        mock_pr.create_review_comment.return_value = mock_comment

        mock_commit = MagicMock()

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr
        mock_repo.get_commit.return_value = mock_commit

        with patch.object(github, "_get_client") as mock_get_client:
            mock_get_client.return_value.get_repo.return_value = mock_repo

            result = await github.post_file_comment(
                "owner/repo", 1, "src/main.py", 42, "Issue here"
            )

            assert result["id"] == 123
            mock_pr.create_review_comment.assert_called_once()


class TestBatchComments:
    """批量评论测试."""

    @pytest.mark.asyncio
    async def test_post_comments_batch(self) -> None:
        """测试批量发布评论."""
        github = GitHubIntegration(token="test")

        comments = [
            PRComment(body="Comment 1"),
            PRComment(body="Comment 2", path="file.py", line=10),
        ]

        with patch.object(github, "post_comment", return_value={"id": 1}) as mock_post, \
             patch.object(github, "post_file_comment", return_value={"id": 2}) as mock_file:
            
            results = await github.post_comments_batch("owner/repo", 1, comments, max_concurrent=2)

            assert len(results) == 2
            mock_post.assert_called_once()
            mock_file.assert_called_once()


class TestPRInfo:
    """PR 信息测试."""

    @pytest.mark.asyncio
    async def test_get_pr_info(self) -> None:
        """测试获取 PR 信息."""
        github = GitHubIntegration(token="test")

        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.title = "Test PR"
        mock_pr.body = "Description"
        mock_pr.head.sha = "head123"
        mock_pr.base.sha = "base123"
        mock_pr.state = "open"
        mock_pr.draft = False

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        with patch.object(github, "_get_client") as mock_get_client:
            mock_get_client.return_value.get_repo.return_value = mock_repo

            info = await github.get_pr_info("owner/repo", 42)

            assert info is not None
            assert info.number == 42
            assert info.title == "Test PR"
            assert not info.is_draft


class TestParsePRUrl:
    """PR URL 解析测试."""

    def test_parse_standard_url(self) -> None:
        """测试标准 PR URL."""
        url = "https://github.com/owner/repo/pull/42"
        result = GitHubIntegration.parse_pr_url(url)

        assert result == ("owner/repo", 42)

    def test_parse_url_with_extra_path(self) -> None:
        """测试带额外路径的 URL."""
        url = "https://github.com/owner/repo/pull/42/files"
        result = GitHubIntegration.parse_pr_url(url)

        assert result == ("owner/repo", 42)

    def test_parse_invalid_url(self) -> None:
        """测试无效 URL."""
        url = "https://example.com/something"
        result = GitHubIntegration.parse_pr_url(url)

        assert result is None


class TestDetectFromEnv:
    """环境变量检测测试."""

    def test_detect_in_actions(self) -> None:
        """测试在 GitHub Actions 中检测."""
        env_vars = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_SHA": "abc123",
            "GITHUB_REF": "refs/pull/42/merge",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            info = GitHubIntegration.detect_from_env()

            assert info is not None
            assert info["event_name"] == "pull_request"
            assert info["repository"] == "owner/repo"

    def test_detect_not_in_actions(self) -> None:
        """测试不在 GitHub Actions 中."""
        with patch.dict(os.environ, {}, clear=True):
            info = GitHubIntegration.detect_from_env()

            assert info is None

    def test_is_github_actions(self) -> None:
        """测试判断是否在 GitHub Actions."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            assert GitHubIntegration.is_github_actions() is True

        with patch.dict(os.environ, {}, clear=True):
            assert GitHubIntegration.is_github_actions() is False


class TestClose:
    """关闭连接测试."""

    @pytest.mark.asyncio
    async def test_close_connection(self) -> None:
        """测试关闭连接."""
        github = GitHubIntegration(token="test")

        mock_client = MagicMock()
        github._client = mock_client

        await github.close()

        mock_client.close.assert_called_once()
        assert github._client is None
