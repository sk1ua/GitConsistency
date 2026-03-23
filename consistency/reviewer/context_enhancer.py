"""上下文增强器.

使用 GitNexus 为代码审查提供额外的上下文信息.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from consistency.core.gitnexus_client import GitNexusClient, get_gitnexus_client

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """符号信息."""

    name: str
    type: str  # function, class, method
    line: int
    context: str | None = None


class ContextEnhancer:
    """上下文增强器.

    提取代码中的符号，并从 GitNexus 获取上下文.

    Examples:
        >>> enhancer = ContextEnhancer()
        >>> context = await enhancer.enhance("/path/to/file.py", python_code)
        >>> print(context)
    """

    def __init__(self, gitnexus_client: GitNexusClient | None = None) -> None:
        """初始化增强器.

        Args:
            gitnexus_client: GitNexus 客户端
        """
        self.gitnexus = gitnexus_client or get_gitnexus_client()

    async def enhance(
        self,
        file_path: Path | str,
        code: str,
        repo_path: Path | str | None = None,
    ) -> str:
        """增强代码上下文.

        Args:
            file_path: 代码文件路径
            code: 代码内容
            repo_path: 代码库根路径（可选）

        Returns:
            增强后的上下文描述
        """
        # 检查 GitNexus 是否可用
        if not self.gitnexus.is_available():
            logger.debug("GitNexus 不可用，跳过上下文增强")
            return ""

        # 提取符号
        symbols = self._extract_symbols(code)
        if not symbols:
            return ""

        # 确保代码库已分析
        if repo_path:
            try:
                await self.gitnexus.ensure_analyzed(repo_path)
            except Exception as e:
                logger.warning(f"GitNexus 分析失败: {e}")
                return ""

        # 获取每个符号的上下文
        contexts = []
        for symbol in symbols[:5]:  # 限制前 5 个符号，避免过多上下文
            try:
                ctx = await self.gitnexus.get_context(symbol.name, repo_path)
                if ctx:
                    symbol_context = self._format_context(symbol, ctx)
                    if symbol_context:
                        contexts.append(symbol_context)
            except Exception as e:
                logger.debug(f"获取符号上下文失败 {symbol.name}: {e}")

        if not contexts:
            return ""

        return self._build_enhanced_prompt(contexts)

    def _extract_symbols(self, code: str) -> list[SymbolInfo]:
        """从代码中提取符号.

        Args:
            code: 代码内容

        Returns:
            符号列表
        """
        symbols = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return symbols

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        type="function",
                        line=node.lineno or 0,
                    ),
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        type="class",
                        line=node.lineno or 0,
                    ),
                )
                # 提取类方法
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_name = f"{node.name}.{item.name}"
                        symbols.append(
                            SymbolInfo(
                                name=method_name,
                                type="method",
                                line=item.lineno or 0,
                            ),
                        )
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        type="async_function",
                        line=node.lineno or 0,
                    ),
                )

        # 按行号排序
        symbols.sort(key=lambda s: s.line)
        return symbols

    def _format_context(
        self,
        symbol: SymbolInfo,
        ctx: Any,  # GitNexusContext
    ) -> dict[str, Any] | None:
        """格式化符号上下文."""
        result = {
            "name": symbol.name,
            "type": symbol.type,
            "callers": [],
            "callees": [],
        }

        # 提取调用者信息
        for caller in ctx.callers[:3]:  # 限制前 3 个
            result["callers"].append({
                "name": caller.get("name", "unknown"),
                "file": caller.get("file", ""),
                "line": caller.get("line", 0),
            })

        # 提取被调用者信息
        for callee in ctx.callees[:3]:
            result["callees"].append({
                "name": callee.get("name", "unknown"),
                "file": callee.get("file", ""),
                "line": callee.get("line", 0),
            })

        return result

    def _build_enhanced_prompt(self, contexts: list[dict[str, Any]]) -> str:
        """构建增强的 Prompt 上下文.

        Args:
            contexts: 符号上下文列表

        Returns:
            格式化的上下文字符串
        """
        lines = [
            "",
            "## 代码上下文（来自知识图谱）",
            "",
        ]

        for ctx in contexts:
            lines.append(f"### {ctx['name']} ({ctx['type']})")

            if ctx["callers"]:
                lines.append("**被以下函数调用：**")
                for caller in ctx["callers"]:
                    lines.append(f"- `{caller['name']}` ({caller['file']}:{caller['line']})")
                lines.append("")

            if ctx["callees"]:
                lines.append("**调用以下函数：**")
                for callee in ctx["callees"]:
                    lines.append(f"- `{callee['name']}` ({callee['file']}:{callee['line']})")
                lines.append("")

        return "\n".join(lines)


# 便捷函数
async def enhance_code_context(
    file_path: Path | str,
    code: str,
    repo_path: Path | str | None = None,
) -> str:
    """便捷函数：增强代码上下文.

    Args:
        file_path: 代码文件路径
        code: 代码内容
        repo_path: 代码库根路径

    Returns:
        增强后的上下文描述
    """
    enhancer = ContextEnhancer()
    return await enhancer.enhance(file_path, code, repo_path)
