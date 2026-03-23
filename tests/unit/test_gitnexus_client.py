"""GitNexus 客户端单元测试."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from consistency.core.gitnexus_client import (
    GitNexusClient,
    GitNexusError,
)


class TestGitNexusClientInit:
    """客户端初始化测试."""

    def test_init_default(self) -> None:
        """测试默认初始化."""
        client = GitNexusClient()
        assert client.cache_dir is not None
        assert client._analyzed_repos == set()

    def test_init_with_cache_dir(self, tmp_path: Path) -> None:
        """测试自定义缓存目录."""
        cache_dir = tmp_path / "cache"
        client = GitNexusClient(cache_dir=cache_dir)
        assert client.cache_dir == cache_dir
        assert cache_dir.exists()


class TestGitNexusClientAvailability:
    """可用性检查测试."""

    def test_is_available_true(self) -> None:
        """测试 gitnexus 已安装."""
        with patch("shutil.which", return_value="/usr/bin/gitnexus"):
            assert GitNexusClient.is_available() is True

    def test_is_available_false(self) -> None:
        """测试 gitnexus 未安装."""
        with patch("shutil.which", return_value=None):
            assert GitNexusClient.is_available() is False


class TestGitNexusClientAnalyze:
    """分析功能测试."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> GitNexusClient:
        """创建测试客户端."""
        return GitNexusClient(cache_dir=tmp_path / "cache")

    @pytest.mark.asyncio
    async def test_analyze_already_done(self, client: GitNexusClient, tmp_path: Path) -> None:
        """测试已分析过的仓库."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Mock subprocess to avoid needing gitnexus CLI
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"{}", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # 第一次分析
            await client.analyze(repo_path)

            # 第二次应该跳过 - verify subprocess not called again
            mock_process.reset_mock()
            await client.analyze(repo_path)
            mock_process.communicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_force_refresh(self, client: GitNexusClient, tmp_path: Path) -> None:
        """测试强制重新分析."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"{}", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # Mark as already analyzed first
            client._analyzed_repos.add(str(repo_path.resolve()))

            # Force should still call subprocess
            await client.analyze(repo_path, force=True)
            mock_process.communicate.assert_called_once()


class TestGitNexusClientContext:
    """上下文查询测试."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> GitNexusClient:
        """创建测试客户端."""
        return GitNexusClient(cache_dir=tmp_path / "cache")

    @pytest.mark.asyncio
    async def test_get_context_success(self, client: GitNexusClient) -> None:
        """测试获取上下文成功."""
        mock_response = {
            "definition": {"name": "test_func", "line": 10},
            "callers": [{"name": "caller1", "file": "test.py", "line": 20}],
            "callees": [],
            "imports": [],
        }

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock:
            mock.return_value = __import__("json").dumps(mock_response)
            ctx = await client.get_context("test_func")

        assert ctx is not None
        assert ctx.symbol == "test_func"
        assert len(ctx.callers) == 1

    @pytest.mark.asyncio
    async def test_get_context_not_found(self, client: GitNexusClient) -> None:
        """测试获取不存在的符号."""
        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock:
            mock.side_effect = GitNexusError("not found")
            ctx = await client.get_context("unknown_func")

        assert ctx is None


class TestGitNexusClientQuery:
    """语义搜索测试."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> GitNexusClient:
        """创建测试客户端."""
        return GitNexusClient(cache_dir=tmp_path / "cache")

    @pytest.mark.asyncio
    async def test_query_success(self, client: GitNexusClient) -> None:
        """测试搜索成功."""
        mock_response = {
            "results": [
                {
                    "symbol": "validate_user",
                    "type": "function",
                    "file": "auth.py",
                    "line": 15,
                    "content": "def validate_user",
                    "score": 0.95,
                }
            ]
        }

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock:
            mock.return_value = __import__("json").dumps(mock_response)
            results = await client.query("user validation")

        assert len(results) == 1
        assert results[0].symbol == "validate_user"
        assert results[0].score == 0.95

    @pytest.mark.asyncio
    async def test_query_empty(self, client: GitNexusClient) -> None:
        """测试空结果."""
        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock:
            mock.return_value = '{"results": []}'
            results = await client.query("unknown")

        assert len(results) == 0


class TestGitNexusClientError:
    """错误处理测试."""

    def test_error_creation(self) -> None:
        """测试错误创建."""
        error = GitNexusError("test error", stderr="stderr output")
        assert error.message == "test error"
        assert error.stderr == "stderr output"
        assert str(error) == "test error"
