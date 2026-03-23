"""风格审查 Agent."""

from __future__ import annotations

import ast
import logging
import re
import time
from pathlib import Path
from typing import Any

from consistency.agents.base import AgentResult, BaseAgent
from consistency.reviewer.models import CommentCategory, ReviewComment, Severity

logger = logging.getLogger(__name__)


class StyleAgent(BaseAgent):
    """风格审查 Agent.

    检查代码风格、命名规范、PEP8 等问题.

    Examples:
        >>> agent = StyleAgent()
        >>> result = await agent.analyze(Path("main.py"), code)
    """

    def __init__(self) -> None:
        """初始化."""
        super().__init__()

    @property
    def name(self) -> str:
        """Agent 名称."""
        return "StyleAgent"

    async def analyze(self, file_path: Path, code: str) -> AgentResult:
        """执行风格分析."""
        start_time = time.perf_counter()
        findings = []

        # 1. 命名规范检查
        try:
            tree = ast.parse(code)
            findings.extend(self._check_naming(tree))
        except SyntaxError:
            pass

        # 2. 文档字符串检查
        try:
            tree = ast.parse(code)
            findings.extend(self._check_docstrings(tree))
        except SyntaxError:
            pass

        # 3. 代码格式检查
        findings.extend(self._check_formatting(code))

        # 4. 导入排序检查
        findings.extend(self._check_imports(code))

        # 生成结果
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

    def _check_naming(self, tree: ast.AST) -> list[dict[str, Any]]:
        """检查命名规范."""
        findings = []

        for node in ast.walk(tree):
            # 检查函数命名（snake_case）
            if isinstance(node, ast.FunctionDef):
                if not re.match(r"^[a-z_][a-z0-9_]*$", node.name):
                    if not (node.name.startswith("__") and node.name.endswith("__")):
                        findings.append({
                            "type": "naming_function",
                            "message": f"函数名 '{node.name}' 不符合 snake_case 规范",
                            "line": node.lineno,
                            "severity": "LOW",
                        })

            # 检查类命名（PascalCase）
            elif isinstance(node, ast.ClassDef):
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
                    findings.append({
                        "type": "naming_class",
                        "message": f"类名 '{node.name}' 不符合 PascalCase 规范",
                        "line": node.lineno,
                        "severity": "LOW",
                    })

            # 检查常量（UPPER_CASE）
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id.isupper():
                            # 已经是全大写，没问题
                            pass
                        elif re.match(r"^[A-Z][A-Z0-9_]*$", target.id):
                            # 检查是否应该用大写
                            if isinstance(node.value, ast.Constant):
                                if isinstance(node.value.value, (int, float, str)):
                                    if target.id not in ["True", "False", "None"]:
                                        findings.append({
                                            "type": "naming_constant",
                                            "message": f"常量 '{target.id}' 建议使用全大写",
                                            "line": node.lineno,
                                            "severity": "LOW",
                                        })

        return findings

    def _check_docstrings(self, tree: ast.AST) -> list[dict[str, Any]]:
        """检查文档字符串."""
        findings = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 检查公共函数是否有 docstring
                if not node.name.startswith("_"):
                    has_docstring = (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    )
                    if not has_docstring:
                        findings.append({
                            "type": "missing_docstring",
                            "message": f"公共函数 '{node.name}' 缺少文档字符串",
                            "line": node.lineno,
                            "severity": "LOW",
                        })

            elif isinstance(node, ast.ClassDef):
                # 检查公共类是否有 docstring
                if not node.name.startswith("_"):
                    has_docstring = (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    )
                    if not has_docstring:
                        findings.append({
                            "type": "missing_docstring",
                            "message": f"类 '{node.name}' 缺少文档字符串",
                            "line": node.lineno,
                            "severity": "LOW",
                        })

        return findings

    def _check_formatting(self, code: str) -> list[dict[str, Any]]:
        """检查代码格式."""
        findings = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            # 检查行尾空格
            if line.rstrip() != line:
                findings.append({
                    "type": "trailing_whitespace",
                    "message": "行尾有多余空格",
                    "line": i,
                    "severity": "INFO",
                })

            # 检查 Tab 使用
            if "\t" in line:
                findings.append({
                    "type": "tab_indent",
                    "message": "使用 Tab 缩进，建议使用空格",
                    "line": i,
                    "severity": "LOW",
                })

            # 检查多余空行
            if i > 1 and not lines[i - 2].strip() and not line.strip():
                findings.append({
                    "type": "extra_blank_line",
                    "message": "多余的空行",
                    "line": i,
                    "severity": "INFO",
                })

        return findings

    def _check_imports(self, code: str) -> list[dict[str, Any]]:
        """检查导入规范."""
        findings = []
        lines = code.split("\n")

        import_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                import_lines.append((i, stripped))

        # 检查是否有未使用的导入（简化检查）
        # 实际应该用更复杂的方法

        # 检查导入排序（标准库 > 第三方 > 本地）
        stdlib_modules = {"os", "sys", "json", "re", "time", "logging", "pathlib"}

        prev_is_stdlib = None
        for i, line in import_lines:
            module = line.split()[1].split(".")[0]
            is_stdlib = module in stdlib_modules

            if prev_is_stdlib is False and is_stdlib:
                findings.append({
                    "type": "import_order",
                    "message": "导入排序可能不正确，标准库导入应在第三方库之前",
                    "line": i,
                    "severity": "INFO",
                })

            prev_is_stdlib = is_stdlib

        return findings

    def _convert_to_comments(
        self,
        findings: list[dict],
        file_path: Path,
    ) -> list[ReviewComment]:
        """转换为 comments."""
        severity_map = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
            "INFO": Severity.INFO,
        }

        return [
            ReviewComment(
                file=str(file_path),
                line=f.get("line", 0),
                message=f.get("message", ""),
                severity=severity_map.get(f.get("severity", "LOW").upper(), Severity.LOW),
                category=CommentCategory.STYLE,
                rule_id=f"style-{f.get('type', 'unknown')}",
            )
            for f in findings
        ]

    def _determine_severity(self, findings: list[dict]) -> Severity:
        """确定总体严重程度."""
        if not findings:
            return Severity.LOW

        # 风格问题通常不会很严重
        has_medium = any(f.get("severity") == "MEDIUM" for f in findings)
        return Severity.MEDIUM if has_medium else Severity.LOW

    def _generate_summary(self, findings: list[dict]) -> str:
        """生成摘要."""
        if not findings:
            return "代码风格良好"

        by_type = {}
        for f in findings:
            t = f.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        parts = [f"{count} 个{k}" for k, count in by_type.items()]
        return f"风格检查: {', '.join(parts)}"

    def _generate_action_items(self, findings: list[dict]) -> list[str]:
        """生成修复建议."""
        items = []

        naming = [f for f in findings if "naming" in f.get("type", "")]
        if naming:
            items.append(f"修复 {len(naming)} 个命名规范问题")

        docs = [f for f in findings if "docstring" in f.get("type", "")]
        if docs:
            items.append(f"补充 {len(docs)} 个文档字符串")

        return items if items else ["代码风格整体良好"]
