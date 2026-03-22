"""GitNexus MCP 客户端实现.

提供异步 MCP 通信、缓存管理、重试机制和优雅错误处理.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urljoin

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from consistancy.core.cache import GitNexusCache
from consistancy.core.schema import (
    ChangeDetection,
    ContextResult,
    ImpactResult,
    KnowledgeGraph,
)

logger = logging.getLogger(__name__)


class GitNexusError(Exception):
    """GitNexus MCP 操作错误基类."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GitNexusConnectionError(GitNexusError):
    """连接错误."""

    pass


class GitNexusTimeoutError(GitNexusError):
    """超时错误."""

    pass


class GitNexusResponseError(GitNexusError):
    """响应错误."""

    pass


class TransportType(Enum):
    """MCP 传输类型."""

    SSE = auto()      # Server-Sent Events
    STDIO = auto()    # 标准输入输出


@dataclass
class MCPMessage:
    """MCP 消息."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method:
            data["method"] = self.method
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error:
            data["error"] = self.error
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPMessage":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params", {}),
            result=data.get("result"),
            error=data.get("error"),
        )


class GitNexusClient:
    """GitNexus MCP 异步客户端.

    支持 SSE 和 stdio 两种 MCP 传输模式，
    提供代码知识图谱的构建、查询和分析功能.

    Attributes:
        cache: 缓存管理器
        transport: 传输类型
        max_retries: 最大重试次数
        timeout: 请求超时（秒）

    Examples:
        >>> async with GitNexusClient() as client:
        ...     graph = await client.analyze("./my-repo")
        ...     context = await client.context("src/main.py", line=42)
    """

    _message_id = 0
    _lock = asyncio.Lock()

    def __init__(
        self,
        mcp_url: str | None = None,
        mcp_command: str | None = None,
        mcp_args: list[str] | None = None,
        cache_dir: Path | str = ".cache/gitnexus",
        cache_ttl: int = 3600,
        max_retries: int = 3,
        timeout: int = 60,
    ) -> None:
        """初始化客户端.

        Args:
            mcp_url: MCP SSE 端点 URL
            mcp_command: MCP 命令（stdio 模式）
            mcp_args: MCP 命令参数
            cache_dir: 缓存目录
            cache_ttl: 缓存 TTL（秒）
            max_retries: 最大重试次数
            timeout: 请求超时（秒）

        Raises:
            GitNexusError: 既未配置 URL 也未配置命令时
        """
        self.mcp_url = mcp_url
        self.mcp_command = mcp_command
        self.mcp_args = mcp_args or []
        self.cache = GitNexusCache(cache_dir, default_ttl=cache_ttl)
        self.max_retries = max_retries
        self.timeout = timeout

        # 确定传输类型
        if mcp_url:
            self.transport = TransportType.SSE
            self._session: aiohttp.ClientSession | None = None
        elif mcp_command:
            self.transport = TransportType.STDIO
            self._process: asyncio.subprocess.Process | None = None
        else:
            raise GitNexusError(
                "必须配置 mcp_url 或 mcp_command",
                {"hint": "请检查环境变量 GITNEXUS_MCP_URL 或 GITNEXUS_MCP_COMMAND"},
            )

        logger.debug(f"GitNexusClient 初始化完成，传输类型: {self.transport.name}")

    async def __aenter__(self) -> "GitNexusClient":
        """异步上下文管理器入口."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器出口."""
        await self.close()

    async def connect(self) -> None:
        """建立 MCP 连接.

        Raises:
            GitNexusConnectionError: 连接失败时
        """
        try:
            if self.transport == TransportType.SSE:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                self._session = aiohttp.ClientSession(timeout=timeout)
                # 验证连接
                await self._call_method("ping", {})
            else:
                if self.mcp_command is None:
                    raise GitNexusError("mcp_command is not set")
                self._process = await asyncio.create_subprocess_exec(
                    self.mcp_command,
                    *self.mcp_args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # 验证连接
                await self._call_method("ping", {})

            logger.info(f"GitNexus MCP 连接成功 ({self.transport.name})")
        except Exception as e:
            raise GitNexusConnectionError(
                f"无法连接到 GitNexus MCP: {e}",
                {"transport": self.transport.name},
            ) from e

    async def close(self) -> None:
        """关闭连接."""
        if self.transport == TransportType.SSE and self._session:
            await self._session.close()
            self._session = None
        elif self.transport == TransportType.STDIO and self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

        logger.info("GitNexus MCP 连接已关闭")

    def _get_next_id(self) -> int:
        """获取下一个消息 ID."""
        GitNexusClient._message_id += 1
        return GitNexusClient._message_id

    @retry(
        retry=retry_if_exception_type((GitNexusConnectionError, GitNexusTimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _call_method(
        self,
        method: str,
        params: dict[str, Any],
    ) -> Any:
        """调用 MCP 方法.

        Args:
            method: 方法名
            params: 参数

        Returns:
            方法返回结果

        Raises:
            GitNexusError: 调用失败时
        """
        msg = MCPMessage(
            id=self._get_next_id(),
            method=method,
            params=params,
        )

        try:
            if self.transport == TransportType.SSE:
                return await self._call_sse(msg)
            else:
                return await self._call_stdio(msg)
        except asyncio.TimeoutError as e:
            raise GitNexusTimeoutError(
                f"调用 {method} 超时",
                {"timeout": self.timeout, "method": method},
            ) from e

    async def _call_sse(self, msg: MCPMessage) -> Any:
        """通过 SSE 调用方法."""
        if not self._session:
            raise GitNexusConnectionError("会话未建立")

        url = urljoin((self.mcp_url or "") + "/", f"tools/{msg.method}")

        async with self._session.post(
            url,
            json=msg.params,
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise GitNexusResponseError(
                    f"HTTP {resp.status}: {text}",
                    {"status": resp.status, "response": text[:500]},
                )
            return await resp.json()

    async def _call_stdio(self, msg: MCPMessage) -> Any:
        """通过 stdio 调用方法."""
        if not self._process or self._process.stdin is None or self._process.stdin.is_closing():
            raise GitNexusConnectionError("进程未运行")

        request = json.dumps(msg.to_dict()) + "\n"
        # nosemgrep: python.django.security.injection.request-data-write
        # 这是向 MCP 子进程的 stdin 写入，不是文件操作。数据已通过 to_dict() 序列化。
        self._process.stdin.write(request.encode())
        await self._process.stdin.drain()

        if self._process.stdout is None:
            raise GitNexusResponseError("进程无stdout")

        # 读取响应
        line = await self._process.stdout.readline()
        if not isinstance(line, bytes):
            raise GitNexusResponseError("进程无响应")
        if not line:
            raise GitNexusResponseError("进程无响应")

        response = json.loads(line.decode())

        if "error" in response:
            raise GitNexusResponseError(
                response["error"].get("message", "未知错误"),
                response["error"],
            )

        return response.get("result")

    async def analyze(
        self,
        repo_path: str,
        force_refresh: bool = False,
    ) -> KnowledgeGraph:
        """分析仓库并构建知识图谱.

        Args:
            repo_path: 仓库路径
            force_refresh: 强制刷新缓存

        Returns:
            知识图谱
        """
        cache_key = self.cache.make_key("analyze", repo_path)

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"使用缓存的图谱: {repo_path}")
                return cached

        logger.info(f"开始分析仓库: {repo_path}")

        result = await self._call_method(
            "analyze",
            {"repo_path": repo_path},
        )

        # 转换为 KnowledgeGraph 对象
        graph = KnowledgeGraph(
            repo_path=repo_path,
            version=result.get("version", "1.0"),
        )

        # 缓存结果
        self.cache.set(cache_key, graph)

        logger.info(f"图谱分析完成: {graph.node_count} 节点, {graph.edge_count} 边")
        return graph

    async def context(
        self,
        file_path: str,
        line: int | None = None,
        column: int | None = None,
    ) -> ContextResult:
        """获取代码上下文.

        Args:
            file_path: 文件路径
            line: 行号（可选）
            column: 列号（可选）

        Returns:
            上下文信息
        """
        cache_key = self.cache.make_key("context", file_path, str(line), str(column))

        cached = self.cache.get(cache_key)
        if cached:
            return cached

        params: dict[str, Any] = {"file_path": file_path}
        if line is not None:
            params["line"] = line
        if column is not None:
            params["column"] = column

        result = await self._call_method("context", params)

        context = ContextResult(
            file_path=file_path,
            symbols=result.get("symbols", []),
            imports=result.get("imports", []),
            callers=result.get("callers", []),
            callees=result.get("callees", []),
        )

        self.cache.set(cache_key, context)
        return context

    async def impact(self, symbol: str) -> ImpactResult:
        """分析符号影响范围.

        Args:
            symbol: 符号名称（如 "module.Class.method"）

        Returns:
            影响分析结果
        """
        cache_key = self.cache.make_key("impact", symbol)

        cached = self.cache.get(cache_key)
        if cached:
            return cached

        result = await self._call_method("impact", {"symbol": symbol})

        impact = ImpactResult(
            symbol=symbol,
            direct_impacts=result.get("direct_impacts", []),
            indirect_impacts=result.get("indirect_impacts", []),
            test_coverage=result.get("test_coverage", []),
        )

        self.cache.set(cache_key, impact)
        return impact

    async def query(self, query: str, limit: int = 100) -> list[dict[str, Any]]:
        """查询知识图谱.

        Args:
            query: 查询语句（支持类 SQL 语法）
            limit: 最大返回结果数

        Returns:
            查询结果列表
        """
        result = await self._call_method(
            "query",
            {"query": query, "limit": limit},
        )
        result_dict: dict[str, Any] = result if isinstance(result, dict) else {}
        results = result_dict.get("results", [])
        return results if isinstance(results, list) else []

    async def detect_changes(
        self,
        base_ref: str,
        head_ref: str,
        repo_path: str | None = None,
    ) -> ChangeDetection:
        """检测两次引用之间的变更.

        Args:
            base_ref: 基础引用（commit/branch/tag）
            head_ref: 目标引用
            repo_path: 仓库路径（可选）

        Returns:
            变更检测结果
        """
        params: dict[str, Any] = {
            "base_ref": base_ref,
            "head_ref": head_ref,
        }
        if repo_path:
            params["repo_path"] = repo_path

        result = await self._call_method("detect_changes", params)

        return ChangeDetection(
            base_ref=base_ref,
            head_ref=head_ref,
            modified_files=result.get("modified_files", []),
            added_symbols=result.get("added_symbols", []),
            removed_symbols=result.get("removed_symbols", []),
            changed_symbols=result.get("changed_symbols", []),
            affected_tests=result.get("affected_tests", []),
        )

    def invalidate_cache(self, pattern: str | None = None) -> int:
        """使缓存失效.

        Args:
            pattern: 匹配模式（可选，None 表示全部）

        Returns:
            清除的条目数
        """
        if pattern is None:
            stats_before = self.cache.get_stats()
            self.cache.clear()
            return int(stats_before["memory_entries"]) + int(stats_before["file_entries"])

        # FIXME: 需要实现模式匹配删除
        # 实现方案: 遍历 memory_cache 和 file_cache，匹配 key 后删除
        # 代码示例:
        #   import fnmatch
        #   keys_to_delete = [k for k in self.cache.memory_cache if fnmatch.fnmatch(k, pattern)]
        #   for key in keys_to_delete:
        #       self.cache.delete(key)
        #   return len(keys_to_delete)
        logger.warning("模式匹配删除未实现，尝试完全清除缓存")
        return self.invalidate_cache(None)

    @asynccontextmanager
    async def batch(self) -> AsyncIterator["GitNexusClient"]:
        """批量操作上下文管理器.

        用于批量执行多个操作，共享缓存。

        Yields:
            客户端实例
        """
        try:
            yield self
        finally:
            pass  # 批量操作结束后的清理
