"""GitNexus MCP 客户端单元测试."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from consistancy.core.gitnexus_client import (
    GitNexusClient,
    GitNexusConnectionError,
    GitNexusError,
    TransportType,
)
from consistancy.core.schema import ContextResult, ImpactResult, KnowledgeGraph


class TestGitNexusClientInit:
    """客户端初始化测试."""

    def test_init_with_url(self) -> None:
        """测试使用 URL 初始化."""
        client = GitNexusClient(mcp_url="http://localhost:3000")
        assert client.mcp_url == "http://localhost:3000"
        assert client.transport == TransportType.SSE

    def test_init_with_command(self) -> None:
        """测试使用命令初始化."""
        client = GitNexusClient(mcp_command="npx", mcp_args=["@gitnexus/mcp"])
        assert client.mcp_command == "npx"
        assert client.mcp_args == ["@gitnexus/mcp"]
        assert client.transport == TransportType.STDIO

    def test_init_without_config(self) -> None:
        """测试无配置时抛出错误."""
        with pytest.raises(GitNexusError) as exc_info:
            GitNexusClient()
        assert "必须配置 mcp_url 或 mcp_command" in str(exc_info.value)

    def test_default_params(self) -> None:
        """测试默认参数."""
        client = GitNexusClient(mcp_url="http://localhost:3000")
        assert client.max_retries == 3
        assert client.timeout == 60
        assert client.cache is not None


class TestGitNexusClientConnection:
    """连接管理测试."""

    @pytest.mark.asyncio
    async def test_connect_sse_success(self) -> None:
        """测试 SSE 连接成功."""
        client = GitNexusClient(mcp_url="http://localhost:3000")
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"status": "ok"}
            await client.connect()
            mock_call.assert_called_once_with("ping", {})

    @pytest.mark.asyncio
    async def test_connect_failure(self) -> None:
        """测试连接失败."""
        client = GitNexusClient(mcp_url="http://localhost:3000")
        
        with patch.object(
            client,
            "_call_method",
            new_callable=AsyncMock,
            side_effect=Exception("connection refused"),
        ):
            with pytest.raises(GitNexusConnectionError):
                await client.connect()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """测试异步上下文管理器."""
        with patch.object(GitNexusClient, "connect", new_callable=AsyncMock) as mock_connect, \
             patch.object(GitNexusClient, "close", new_callable=AsyncMock) as mock_close:
            
            async with GitNexusClient(mcp_url="http://localhost:3000") as client:
                assert isinstance(client, GitNexusClient)
            
            mock_connect.assert_called_once()
            mock_close.assert_called_once()


class TestGitNexusClientAnalyze:
    """analyze 方法测试."""

    @pytest.fixture
    def client(self) -> GitNexusClient:
        """创建测试客户端."""
        return GitNexusClient(mcp_url="http://localhost:3000")

    @pytest.mark.asyncio
    async def test_analyze_success(self, client: GitNexusClient) -> None:
        """测试分析成功."""
        mock_result = {
            "version": "1.0",
            "nodes": [],
            "edges": [],
        }
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result
            result = await client.analyze("/path/to/repo")
            
            assert isinstance(result, KnowledgeGraph)
            assert result.repo_path == "/path/to/repo"
            assert result.version == "1.0"
            mock_call.assert_called_once_with(
                "analyze",
                {"repo_path": "/path/to/repo"},
            )

    @pytest.mark.asyncio
    async def test_analyze_uses_cache(self, client: GitNexusClient) -> None:
        """测试分析使用缓存."""
        mock_result = {"version": "1.0"}
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result
            
            # 第一次调用
            result1 = await client.analyze("/path/to/repo")
            # 第二次调用（应该从缓存获取）
            result2 = await client.analyze("/path/to/repo")
            
            # 应该只调用一次底层方法
            mock_call.assert_called_once()
            # 但返回相同的图谱对象
            assert result1.repo_path == result2.repo_path

    @pytest.mark.asyncio
    async def test_analyze_force_refresh(self, client: GitNexusClient) -> None:
        """测试强制刷新."""
        mock_result = {"version": "1.0"}
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result
            
            # 第一次调用
            await client.analyze("/path/to/repo")
            # 强制刷新
            await client.analyze("/path/to/repo", force_refresh=True)
            
            # 应该调用两次
            assert mock_call.call_count == 2


class TestGitNexusClientContext:
    """context 方法测试."""

    @pytest.fixture
    def client(self) -> GitNexusClient:
        return GitNexusClient(mcp_url="http://localhost:3000")

    @pytest.mark.asyncio
    async def test_context_basic(self, client: GitNexusClient) -> None:
        """测试基本上下文查询."""
        mock_result = {
            "symbols": [{"name": "MyClass", "type": "class"}],
            "imports": ["os", "sys"],
            "callers": [],
            "callees": ["helper()"],
        }
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result
            result = await client.context("src/main.py")
            
            assert isinstance(result, ContextResult)
            assert result.file_path == "src/main.py"
            assert len(result.symbols) == 1
            assert result.symbols[0]["name"] == "MyClass"

    @pytest.mark.asyncio
    async def test_context_with_line(self, client: GitNexusClient) -> None:
        """测试带行号的上下文查询."""
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"symbols": []}
            await client.context("src/main.py", line=42)
            
            mock_call.assert_called_once_with(
                "context",
                {"file_path": "src/main.py", "line": 42},
            )

    @pytest.mark.asyncio
    async def test_context_uses_cache(self, client: GitNexusClient) -> None:
        """测试上下文缓存."""
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"symbols": []}
            
            # 第一次调用
            await client.context("src/main.py", line=42)
            # 第二次调用（应该使用缓存）
            await client.context("src/main.py", line=42)
            
            # 只调用一次
            mock_call.assert_called_once()


class TestGitNexusClientImpact:
    """impact 方法测试."""

    @pytest.fixture
    def client(self) -> GitNexusClient:
        return GitNexusClient(mcp_url="http://localhost:3000")

    @pytest.mark.asyncio
    async def test_impact_success(self, client: GitNexusClient) -> None:
        """测试影响分析成功."""
        mock_result = {
            "direct_impacts": ["caller1", "caller2"],
            "indirect_impacts": ["indirect1"],
            "test_coverage": ["test_module.py"],
        }
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result
            result = await client.impact("my_module.my_function")
            
            assert isinstance(result, ImpactResult)
            assert result.symbol == "my_module.my_function"
            assert len(result.direct_impacts) == 2
            assert "caller1" in result.direct_impacts
            assert len(result.test_coverage) == 1

    @pytest.mark.asyncio
    async def test_impact_caches_result(self, client: GitNexusClient) -> None:
        """测试结果缓存."""
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"direct_impacts": []}
            
            # 多次调用相同符号
            await client.impact("symbol1")
            await client.impact("symbol1")
            await client.impact("symbol1")
            
            # 只调用一次
            mock_call.assert_called_once()


class TestGitNexusClientQuery:
    """query 方法测试."""

    @pytest.fixture
    def client(self) -> GitNexusClient:
        return GitNexusClient(mcp_url="http://localhost:3000")

    @pytest.mark.asyncio
    async def test_query_success(self, client: GitNexusClient) -> None:
        """测试查询成功."""
        mock_result = {
            "results": [
                {"name": "func1", "type": "function"},
                {"name": "func2", "type": "function"},
            ]
        }
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result
            results = await client.query("SELECT * FROM functions LIMIT 10")
            
            assert len(results) == 2
            assert results[0]["name"] == "func1"
            mock_call.assert_called_once_with(
                "query",
                {"query": "SELECT * FROM functions LIMIT 10", "limit": 100},
            )

    @pytest.mark.asyncio
    async def test_query_with_limit(self, client: GitNexusClient) -> None:
        """测试自定义 limit."""
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"results": []}
            await client.query("SELECT *", limit=50)
            
            mock_call.assert_called_once_with(
                "query",
                {"query": "SELECT *", "limit": 50},
            )


class TestGitNexusClientDetectChanges:
    """detect_changes 方法测试."""

    @pytest.fixture
    def client(self) -> GitNexusClient:
        return GitNexusClient(mcp_url="http://localhost:3000")

    @pytest.mark.asyncio
    async def test_detect_changes_success(self, client: GitNexusClient) -> None:
        """测试变更检测成功."""
        mock_result = {
            "modified_files": ["src/main.py", "tests/test_main.py"],
            "added_symbols": ["new_function"],
            "removed_symbols": ["old_function"],
            "changed_symbols": ["modified_function"],
            "affected_tests": ["tests/test_main.py"],
        }
        
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result
            result = await client.detect_changes("main", "feature-branch")
            
            assert result.base_ref == "main"
            assert result.head_ref == "feature-branch"
            assert len(result.modified_files) == 2
            assert "src/main.py" in result.modified_files
            assert len(result.affected_tests) == 1

    @pytest.mark.asyncio
    async def test_detect_changes_with_repo_path(self, client: GitNexusClient) -> None:
        """测试带仓库路径的变更检测."""
        with patch.object(client, "_call_method", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"modified_files": []}
            await client.detect_changes("v1.0", "v2.0", repo_path="/path/to/repo")
            
            mock_call.assert_called_once_with(
                "detect_changes",
                {
                    "base_ref": "v1.0",
                    "head_ref": "v2.0",
                    "repo_path": "/path/to/repo",
                },
            )


class TestGitNexusClientCache:
    """缓存管理测试."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> GitNexusClient:
        return GitNexusClient(
            mcp_url="http://localhost:3000",
            cache_dir=tmp_path / "cache",
        )

    def test_invalidate_cache_all(self, client: GitNexusClient) -> None:
        """测试清空所有缓存."""
        # 添加一些缓存
        client.cache.set("key1", "value1")
        client.cache.set("key2", "value2")
        
        # 清空
        count = client.invalidate_cache()
        
        assert count == 4  # 2 memory + 2 file (file缓存每个条目算作2个)
        assert client.cache.get("key1") is None
        assert client.cache.get("key2") is None
