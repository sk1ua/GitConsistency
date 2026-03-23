"""GitNexus 客户端.

调用 GitNexus CLI 构建知识图谱并查询代码上下文.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from consistency.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class GitNexusContext:
    """GitNexus 符号上下文."""

    symbol: str
    definition: dict[str, Any] | None
    callers: list[dict[str, Any]]
    callees: list[dict[str, Any]]
    imports: list[dict[str, Any]]


@dataclass
class GitNexusQueryResult:
    """GitNexus 查询结果."""

    symbol: str
    type: str
    file_path: str
    line: int
    content: str
    score: float


class GitNexusError(Exception):
    """GitNexus 错误."""

    def __init__(self, message: str, stderr: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.stderr = stderr


class GitNexusClient:
    """GitNexus 客户端.

    调用 gitnexus CLI 构建知识图谱并查询代码上下文.

    Examples:
        >>> client = GitNexusClient()
        >>> await client.ensure_analyzed("/path/to/repo")
        >>> context = await client.get_context("validate_user")
        >>> print(context.callers)
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """初始化客户端.

        Args:
            cache_dir: 知识图谱缓存目录
        """
        self.cache_dir = cache_dir or Path(".cache/gitnexus")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._analyzed_repos: set[str] = set()

    @staticmethod
    def is_available() -> bool:
        """检查 gitnexus 是否已安装."""
        return shutil.which("gitnexus") is not None

    async def analyze(self, repo_path: Path | str, force: bool = False) -> Path:
        """分析代码库构建知识图谱.

        Args:
            repo_path: 代码库路径
            force: 强制重新分析

        Returns:
            知识图谱存储路径

        Raises:
            GitNexusError: 分析失败
        """
        repo_path = Path(repo_path).resolve()
        repo_key = str(repo_path)

        # 检查是否已分析
        if not force and repo_key in self._analyzed_repos:
            logger.info(f"知识图谱已存在: {repo_path}")
            return self._get_graph_path(repo_path)

        logger.info(f"开始分析代码库: {repo_path}")

        try:
            # 调用 gitnexus analyze
            cmd = ["gitnexus", "analyze", str(repo_path)]
            if force:
                cmd.append("--force")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise GitNexusError(
                    f"GitNexus 分析失败: {stderr.decode()}",
                    stderr=stderr.decode(),
                )

            self._analyzed_repos.add(repo_key)
            logger.info(f"知识图谱构建完成: {repo_path}")

            return self._get_graph_path(repo_path)

        except FileNotFoundError:
            raise GitNexusError(
                "gitnexus 未安装，请运行: npm install -g gitnexus",
            )

    async def get_context(
        self,
        symbol: str,
        repo_path: Path | str | None = None,
    ) -> GitNexusContext | None:
        """获取符号的完整上下文.

        Args:
            symbol: 符号名称（如 "validate_user" 或 "UserService.validate"）
            repo_path: 代码库路径（可选，用于定位知识图谱）

        Returns:
            符号上下文，如果未找到返回 None
        """
        if repo_path:
            await self.ensure_analyzed(repo_path)

        try:
            cmd = ["gitnexus", "context", "--json", symbol]
            if repo_path:
                cmd.extend(["--repo", str(repo_path)])

            result = await self._run_command(cmd)
            data = json.loads(result)

            return GitNexusContext(
                symbol=symbol,
                definition=data.get("definition"),
                callers=data.get("callers", []),
                callees=data.get("callees", []),
                imports=data.get("imports", []),
            )

        except (GitNexusError, json.JSONDecodeError) as e:
            logger.warning(f"获取上下文失败 {symbol}: {e}")
            return None

    async def query(
        self,
        query: str,
        repo_path: Path | str | None = None,
        limit: int = 10,
    ) -> list[GitNexusQueryResult]:
        """语义搜索代码.

        Args:
            query: 搜索查询
            repo_path: 代码库路径
            limit: 最大结果数

        Returns:
            搜索结果列表
        """
        if repo_path:
            await self.ensure_analyzed(repo_path)

        try:
            cmd = [
                "gitnexus",
                "query",
                "--json",
                "--limit",
                str(limit),
                query,
            ]
            if repo_path:
                cmd.extend(["--repo", str(repo_path)])

            result = await self._run_command(cmd)
            data = json.loads(result)

            results = []
            for item in data.get("results", []):
                results.append(
                    GitNexusQueryResult(
                        symbol=item.get("symbol", ""),
                        type=item.get("type", ""),
                        file_path=item.get("file", ""),
                        line=item.get("line", 0),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                    ),
                )

            return results

        except (GitNexusError, json.JSONDecodeError) as e:
            logger.warning(f"查询失败 {query}: {e}")
            return []

    async def get_impact(
        self,
        symbol: str,
        repo_path: Path | str | None = None,
    ) -> dict[str, Any] | None:
        """分析符号的影响范围.

        Args:
            symbol: 符号名称
            repo_path: 代码库路径

        Returns:
            影响分析结果
        """
        if repo_path:
            await self.ensure_analyzed(repo_path)

        try:
            cmd = ["gitnexus", "impact", "--json", symbol]
            if repo_path:
                cmd.extend(["--repo", str(repo_path)])

            result = await self._run_command(cmd)
            return json.loads(result)

        except (GitNexusError, json.JSONDecodeError) as e:
            logger.warning(f"影响分析失败 {symbol}: {e}")
            return None

    async def ensure_analyzed(self, repo_path: Path | str) -> Path:
        """确保代码库已分析（如未分析则自动分析）.

        Args:
            repo_path: 代码库路径

        Returns:
            知识图谱存储路径
        """
        repo_path = Path(repo_path).resolve()

        # 检查是否存在知识图谱
        graph_path = self._get_graph_path(repo_path)
        if graph_path.exists():
            self._analyzed_repos.add(str(repo_path))
            return graph_path

        # 需要分析
        return await self.analyze(repo_path)

    def _get_graph_path(self, repo_path: Path) -> Path:
        """获取知识图谱路径."""
        # 使用 repo 路径的 hash 作为子目录
        import hashlib

        repo_hash = hashlib.md5(str(repo_path).encode()).hexdigest()[:8]
        return self.cache_dir / f"{repo_hash}" / "graph.lbug"

    async def _run_command(self, cmd: list[str]) -> str:
        """运行 gitnexus 命令.

        Args:
            cmd: 命令列表

        Returns:
            命令输出

        Raises:
            GitNexusError: 命令执行失败
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise GitNexusError(
                f"命令失败: {' '.join(cmd)}: {stderr.decode()}",
                stderr=stderr.decode(),
            )

        return stdout.decode()


# 单例客户端
gitnexus_client: GitNexusClient | None = None


def get_gitnexus_client() -> GitNexusClient:
    """获取 GitNexus 客户端单例."""
    global gitnexus_client
    if gitnexus_client is None:
        settings = get_settings()
        gitnexus_client = GitNexusClient(
            cache_dir=settings.gitnexus_cache_dir,
        )
    return gitnexus_client
