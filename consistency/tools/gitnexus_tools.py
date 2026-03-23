"""GitNexus 工具封装."""

from __future__ import annotations

import logging
from typing import Any

from consistency.core.gitnexus_client import get_gitnexus_client

logger = logging.getLogger(__name__)


class GitNexusQueryTool:
    """GitNexus 查询工具.

    语义搜索代码库中的符号.

    Examples:
        >>> tool = GitNexusQueryTool()
        >>> results = await tool.execute("user authentication")
    """

    name = "gitnexus_query"
    description = """搜索代码库中的符号.

Args:
    query: 搜索查询，可以是函数名、类名或描述
    limit: 最大结果数（默认 5）

Returns:
    符号列表，包含名称、类型、文件位置和代码内容
"""

    def __init__(self) -> None:
        """初始化."""
        self.client = get_gitnexus_client()

    async def execute(self, query: str, limit: int = 5) -> dict[str, Any]:
        """执行查询.

        Args:
            query: 搜索查询
            limit: 最大结果数

        Returns:
            查询结果
        """
        if not self.client.is_available():
            return {
                "error": "GitNexus 未安装，请运行: npm install -g gitnexus",
                "results": [],
            }

        try:
            results = await self.client.query(query, limit=limit)

            return {
                "query": query,
                "count": len(results),
                "results": [
                    {
                        "symbol": r.symbol,
                        "type": r.type,
                        "file": r.file_path,
                        "line": r.line,
                        "content": r.content[:200] if r.content else "",
                        "score": r.score,
                    }
                    for r in results
                ],
            }

        except Exception as e:
            logger.error(f"GitNexus 查询失败: {e}")
            return {"error": str(e), "results": []}


class GitNexusContextTool:
    """GitNexus 上下文工具.

    获取符号的完整上下文（调用者、被调用者、导入关系）.

    Examples:
        >>> tool = GitNexusContextTool()
        >>> context = await tool.execute("validate_user")
    """

    name = "gitnexus_context"
    description = """获取符号的完整上下文.

Args:
    symbol: 符号名称（如 "validate_user" 或 "UserService.validate"）

Returns:
    符号定义、调用者、被调用者、导入关系
"""

    def __init__(self) -> None:
        """初始化."""
        self.client = get_gitnexus_client()

    async def execute(self, symbol: str) -> dict[str, Any]:
        """执行查询.

        Args:
            symbol: 符号名称

        Returns:
            上下文信息
        """
        if not self.client.is_available():
            return {
                "error": "GitNexus 未安装，请运行: npm install -g gitnexus",
            }

        try:
            ctx = await self.client.get_context(symbol)

            if not ctx:
                return {
                    "symbol": symbol,
                    "found": False,
                    "message": f"未找到符号: {symbol}",
                }

            return {
                "symbol": symbol,
                "found": True,
                "definition": ctx.definition,
                "callers": [
                    {
                        "name": c.get("name", "unknown"),
                        "file": c.get("file", ""),
                        "line": c.get("line", 0),
                    }
                    for c in ctx.callers[:5]  # 限制数量
                ],
                "callees": [
                    {
                        "name": c.get("name", "unknown"),
                        "file": c.get("file", ""),
                        "line": c.get("line", 0),
                    }
                    for c in ctx.callees[:5]
                ],
                "imports": ctx.imports,
            }

        except Exception as e:
            logger.error(f"GitNexus 上下文获取失败: {e}")
            return {"error": str(e)}
