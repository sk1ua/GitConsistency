"""逻辑审查 Agent (LLM 驱动).

检查代码逻辑缺陷、边界条件、错误处理等问题，使用 LLM 进行智能分析。
"""

from __future__ import annotations

import ast
import json
import logging
import time
from pathlib import Path
from typing import Any

from consistency.agents.base import AgentResult, BaseAgent
from consistency.core.gitnexus_client import GitNexusClient
from consistency.reviewer.models import CommentCategory, ReviewComment, Severity
from consistency.reviewer.prompts import PromptTemplate, ReviewContext, ReviewType

logger = logging.getLogger(__name__)


class LogicAgent(BaseAgent):
    """逻辑审查 Agent.

    使用 LLM 检查代码逻辑缺陷、边界条件、错误处理等问题。

    Examples:
        >>> agent = LogicAgent()
        >>> result = await agent.analyze(Path("main.py"), code)
        >>> print(result.comments)
    """

    def __init__(
        self,
        gitnexus_client: GitNexusClient | None = None,
        llm_provider: Any | None = None,
        timeout: float = 30.0,
    ) -> None:
        """初始化.

        Args:
            gitnexus_client: GitNexus 客户端（可选）
            llm_provider: LLM Provider（可选，默认使用 LiteLLM）
            timeout: LLM 调用超时时间（秒）
        """
        super().__init__()
        self.gitnexus = gitnexus_client
        self.timeout = timeout

        # 初始化 LLM Provider
        self._llm = llm_provider
        if self._llm is None:
            try:
                from consistency.llm.factory import LLMProviderFactory

                self._llm = LLMProviderFactory.create_from_settings()
            except Exception as e:
                logger.warning(f"LLM Provider 初始化失败: {e}")
                self._llm = None

    @property
    def name(self) -> str:
        """Agent 名称."""
        return "LogicAgent"

    async def analyze(self, file_path: Path, code: str) -> AgentResult:
        """执行逻辑分析."""
        start_time = time.perf_counter()

        # 1. 尝试使用 LLM 进行分析
        if self._llm is not None:
            try:
                llm_result = await self._analyze_with_llm(file_path, code)
                if llm_result:
                    duration = (time.perf_counter() - start_time) * 1000
                    return AgentResult(
                        agent_name=self.name,
                        summary=llm_result.get("summary", "LLM 逻辑分析完成"),
                        severity=self._parse_severity(llm_result.get("severity", "low")),
                        comments=llm_result.get("comments", []),
                        action_items=llm_result.get("action_items", []),
                        metadata={"source": "llm"},
                        duration_ms=duration,
                    )
            except Exception as e:
                logger.warning(f"LLM 逻辑分析失败，回退到静态分析: {e}")

        # 2. LLM 失败或不可用，回退到静态分析
        return await self._analyze_with_static(file_path, code, start_time)

    async def _analyze_with_llm(
        self,
        file_path: Path,
        code: str,
    ) -> dict[str, Any] | None:
        """使用 LLM 进行逻辑分析."""
        context = ReviewContext(
            diff=code,
            files_changed=[str(file_path)],
            language="python",
        )

        messages = PromptTemplate.build(context, ReviewType.GENERAL)

        import asyncio

        try:
            response = await asyncio.wait_for(
                self._llm.complete_json(messages),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"LLM 调用超时 ({self.timeout}s)")
            return None

        try:
            content = response.content if hasattr(response, "content") else str(response)
            result = json.loads(content)

            # 过滤出逻辑相关的问题
            comments = []
            for c in result.get("comments", []):
                category = c.get("category", "bug")
                if category in ["bug", "maintainability"]:
                    comment = ReviewComment(
                        file=str(file_path),
                        line=c.get("line"),
                        message=c.get("message", ""),
                        suggestion=c.get("suggestion"),
                        severity=self._parse_severity(c.get("severity", "medium")),
                        category=CommentCategory.BUG,
                        confidence=0.8,
                    )
                    comments.append(comment)

            return {
                "summary": result.get("summary", ""),
                "severity": result.get("severity", "low"),
                "comments": comments,
                "action_items": result.get("action_items", []),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"LLM 响应 JSON 解析失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"LLM 响应处理失败: {e}")
            return None

    async def _analyze_with_static(
        self,
        file_path: Path,
        code: str,
        start_time: float,
    ) -> AgentResult:
        """使用静态分析（降级方案）."""
        findings: list[dict[str, Any]] = []

        # 1. AST 分析
        try:
            tree = ast.parse(code)
            findings.extend(self._analyze_ast(tree, file_path))
        except SyntaxError as e:
            logger.warning(f"语法错误: {e}")
            return AgentResult(
                agent_name=self.name,
                summary=f"语法错误，无法分析: {e}",
                severity=Severity.LOW,
                comments=[],
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 2. 代码质量检查
        findings.extend(self._check_code_quality(code, file_path))

        # 3. GitNexus 增强（可选）
        if self.gitnexus is not None:
            try:
                gitnexus_findings = await self._analyze_call_chains(file_path, code)
                findings.extend(gitnexus_findings)
            except Exception as e:
                logger.debug(f"GitNexus 调用链分析失败: {e}")

        # 4. 生成结果
        comments = self._convert_to_comments(findings, file_path)
        severity = self._determine_severity(findings)
        summary = self._generate_summary(findings)

        duration = (time.perf_counter() - start_time) * 1000

        return AgentResult(
            agent_name=self.name,
            summary=summary,
            severity=severity,
            comments=comments,
            action_items=self._generate_action_items(findings),
            metadata={"findings_count": len(findings)},
            duration_ms=duration,
        )

    def _analyze_ast(self, tree: ast.AST, file_path: Path) -> list[dict[str, Any]]:
        """分析 AST 查找逻辑问题."""
        findings = []

        for node in ast.walk(tree):
            # 检查裸 except
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    findings.append(
                        {
                            "type": "bare_except",
                            "message": "使用裸 except: 会捕获所有异常包括 KeyboardInterrupt，建议指定具体异常类型",
                            "line": node.lineno,
                            "severity": "MEDIUM",
                        }
                    )

            # 检查空函数
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                    findings.append(
                        {
                            "type": "empty_function",
                            "message": f"函数 '{node.name}' 为空或只有 pass，建议实现或删除",
                            "line": node.lineno,
                            "severity": "LOW",
                        }
                    )

                # 检查复杂函数（行数过多）
                func_end = node.end_lineno or node.lineno
                func_lines = func_end - node.lineno
                if func_lines > 50:
                    findings.append(
                        {
                            "type": "complex_function",
                            "message": f"函数 '{node.name}' 过长 ({func_lines} 行)，建议拆分",
                            "line": node.lineno,
                            "severity": "MEDIUM",
                        }
                    )

            # 检查硬编码值
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, str) and len(node.value) > 20:
                    # 可能是 SQL 或 硬编码配置
                    if "SELECT" in node.value.upper() or "INSERT" in node.value.upper():
                        findings.append(
                            {
                                "type": "hardcoded_sql",
                                "message": "检测到硬编码 SQL，建议使用 ORM 或参数化查询",
                                "line": node.lineno,
                                "severity": "MEDIUM",
                            }
                        )

        return findings

    def _check_code_quality(self, code: str, file_path: Path) -> list[dict[str, Any]]:
        """检查代码质量问题."""
        findings = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # 检查 TODO 注释
            if "TODO" in line.upper() or "FIXME" in line.upper():
                findings.append(
                    {
                        "type": "todo",
                        "message": f"发现待办事项: {line.strip()}",
                        "line": i,
                        "severity": "LOW",
                    }
                )

            # 检查长行
            if len(line) > 120:
                findings.append(
                    {
                        "type": "long_line",
                        "message": f"行过长 ({len(line)} 字符)，建议不超过 120 字符",
                        "line": i,
                        "severity": "LOW",
                    }
                )

            # 检查 print 语句
            stripped = line.strip()
            if stripped.startswith("print(") and "logger" not in line.lower():
                findings.append(
                    {
                        "type": "print_statement",
                        "message": "使用 print 输出，建议使用 logging 模块",
                        "line": i,
                        "severity": "LOW",
                    }
                )

        return findings

    async def _analyze_call_chains(
        self,
        file_path: Path,
        code: str,
    ) -> list[dict[str, Any]]:
        """使用 GitNexus 分析调用链."""
        findings: list[dict[str, Any]] = []

        if self.gitnexus is None:
            return findings

        # 提取函数定义
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                try:
                    ctx = await self.gitnexus.get_context(
                        node.name,
                        repo_path=file_path.parent,
                    )
                    if ctx:
                        # 检查调用深度
                        if len(ctx.callees) > 10:
                            findings.append(
                                {
                                    "type": "deep_call_chain",
                                    "message": f"函数 '{node.name}' 调用链较深 ({len(ctx.callees)} 层)，建议简化",
                                    "line": node.lineno,
                                    "severity": "MEDIUM",
                                }
                            )

                        # 检查是否有循环依赖（简化检查）
                        if any(c.get("name") == node.name for c in ctx.callees):
                            findings.append(
                                {
                                    "type": "cyclic_dependency",
                                    "message": f"函数 '{node.name}' 可能存在循环调用",
                                    "line": node.lineno,
                                    "severity": "HIGH",
                                }
                            )

                except Exception as e:
                    logger.debug(f"GitNexus 分析失败 {node.name}: {e}")

        return findings

    def _parse_severity(self, severity: str) -> Severity:
        """解析严重程度字符串."""
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return severity_map.get(severity.lower(), Severity.MEDIUM)

    def _convert_to_comments(
        self,
        findings: list[dict[str, Any]],
        file_path: Path,
    ) -> list[ReviewComment]:
        """转换为 comments."""
        severity_map = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
        }

        comments: list[ReviewComment] = []
        for finding in findings:
            line_value = finding.get("line")
            line = line_value if isinstance(line_value, int) and line_value > 0 else None
            message = str(finding.get("message", ""))
            severity_raw = str(finding.get("severity", "MEDIUM")).upper()
            comments.append(
                ReviewComment(
                    file=str(file_path),
                    line=line,
                    message=message,
                    suggestion=None,
                    severity=severity_map.get(severity_raw, Severity.MEDIUM),
                    category=CommentCategory.BUG,
                    confidence=0.8,
                )
            )
        return comments

    def _determine_severity(self, findings: list[dict[str, Any]]) -> Severity:
        """确定总体严重程度."""
        if not findings:
            return Severity.LOW

        for f in findings:
            if f.get("severity") == "CRITICAL":
                return Severity.CRITICAL
            if f.get("severity") == "HIGH":
                return Severity.HIGH

        has_medium = any(f.get("severity") == "MEDIUM" for f in findings)
        return Severity.MEDIUM if has_medium else Severity.LOW

    def _generate_summary(self, findings: list[dict[str, Any]]) -> str:
        """生成摘要."""
        if not findings:
            return "未检测到逻辑问题"

        types: dict[str, int] = {}
        for f in findings:
            t = f.get("type", "unknown")
            types[t] = types.get(t, 0) + 1

        parts = [f"{count} 个{k}" for k, count in types.items()]
        return f"逻辑分析发现: {', '.join(parts)}"

    def _generate_action_items(self, findings: list[dict[str, Any]]) -> list[str]:
        """生成修复建议."""
        items = []

        critical_high = [f for f in findings if f.get("severity") in ["CRITICAL", "HIGH"]]

        if critical_high:
            items.append(f"优先处理 {len(critical_high)} 个严重/高危逻辑问题")

        todos = [f for f in findings if f.get("type") == "todo"]
        if todos:
            items.append(f"处理 {len(todos)} 个待办事项")

        return items
