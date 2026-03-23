"""安全审查 Agent."""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from consistency.agents.base import AgentResult, BaseAgent
from consistency.core.gitnexus_client import GitNexusClient, get_gitnexus_client
from consistency.reviewer.models import CommentCategory, ReviewComment, Severity
from consistency.scanners.security_scanner import SecurityScanner

logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """安全审查 Agent.

    结合 Semgrep、Bandit 和 GitNexus 调用链分析进行安全审查.

    Examples:
        >>> agent = SecurityAgent()
        >>> result = await agent.analyze(Path("main.py"), code)
        >>> print(result.summary)
    """

    def __init__(
        self,
        gitnexus_client: GitNexusClient | None = None,
        use_gitnexus: bool = True,
    ) -> None:
        """初始化.

        Args:
            gitnexus_client: GitNexus 客户端
            use_gitnexus: 是否使用 GitNexus 增强
        """
        super().__init__()
        self.scanner = SecurityScanner()
        self.gitnexus = gitnexus_client or get_gitnexus_client()
        self.use_gitnexus = use_gitnexus and self.gitnexus.is_available()

    @property
    def name(self) -> str:
        """Agent 名称."""
        return "SecurityAgent"

    async def analyze(self, file_path: Path, code: str) -> AgentResult:
        """执行安全分析.

        Args:
            file_path: 文件路径
            code: 代码内容

        Returns:
            审查结果
        """
        start_time = time.perf_counter()
        all_findings: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {"sources": []}

        # 1. 使用标准扫描流程（Semgrep + Bandit）
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_file = Path(tmpdir) / (file_path.name or "snippet.py")
                temp_file.write_text(code, encoding="utf-8")

                scan_result = await self.scanner.scan(temp_file)
                for finding in scan_result.findings:
                    all_findings.append(
                        {
                            "rule_id": finding.rule_id,
                            "message": finding.message,
                            "severity": finding.severity.value.upper(),
                            "file_path": file_path,
                            "line": finding.line,
                            "source": scan_result.scanner_name,
                        }
                    )

                metadata["sources"].append(scan_result.scanner_name)
                if scan_result.errors:
                    metadata["scan_errors"] = scan_result.errors
        except Exception as e:
            logger.warning(f"安全扫描失败: {e}")

        # 2. GitNexus 增强（如果有）
        if self.use_gitnexus:
            try:
                gitnexus_findings = await self._analyze_with_gitnexus(file_path, code)
                all_findings.extend(gitnexus_findings)
                metadata["sources"].append("gitnexus")
            except Exception as e:
                logger.warning(f"GitNexus 分析失败: {e}")

        # 3. 转换为 comments
        comments = self._convert_to_comments(all_findings)

        # 4. 确定严重程度
        severity = self._determine_severity(all_findings)

        # 5. 生成摘要
        summary = self._generate_summary(all_findings)

        duration = (time.perf_counter() - start_time) * 1000

        return AgentResult(
            agent_name=self.name,
            summary=summary,
            severity=severity,
            comments=comments,
            action_items=self._generate_action_items(all_findings),
            metadata=metadata,
            duration_ms=duration,
        )

    async def _analyze_with_gitnexus(
        self,
        file_path: Path,
        code: str,
    ) -> list[dict[str, Any]]:
        """使用 GitNexus 进行增强分析.

        检查危险函数的调用链.
        """
        findings = []

        # 危险函数列表
        dangerous_functions = [
            "eval",
            "exec",
            "subprocess.call",
            "os.system",
            "pickle.loads",
            "yaml.load",
        ]

        # 检查代码中是否包含危险函数
        for func in dangerous_functions:
            if func in code:
                # 获取上下文
                try:
                    ctx = await self.gitnexus.get_context(func)
                    if ctx and ctx.callers:
                        findings.append(
                            {
                                "rule_id": f"gitnexus-dangerous-{func}",
                                "message": f"危险函数 '{func}' 被调用，调用链: {len(ctx.callers)} 处",
                                "severity": "HIGH" if func in ["eval", "exec"] else "MEDIUM",
                                "file_path": file_path,
                                "line": self._find_line(code, func),
                                "source": "gitnexus",
                            }
                        )
                except Exception as e:
                    logger.debug(f"GitNexus 上下文获取失败 {func}: {e}")

        return findings

    def _convert_to_comments(self, findings: list[dict[str, Any]]) -> list[ReviewComment]:
        """将发现转换为 ReviewComment."""
        comments: list[ReviewComment] = []

        for finding in findings:
            severity_map = {
                "CRITICAL": Severity.CRITICAL,
                "HIGH": Severity.HIGH,
                "MEDIUM": Severity.MEDIUM,
                "LOW": Severity.LOW,
            }

            line_value = finding.get("line")
            line = line_value if isinstance(line_value, int) and line_value > 0 else None
            message = str(finding.get("message", ""))
            severity_raw = str(finding.get("severity", "MEDIUM")).upper()
            comment = ReviewComment(
                file=str(finding.get("file_path", "")),
                line=line,
                message=message,
                suggestion=None,
                severity=severity_map.get(
                    severity_raw,
                    Severity.MEDIUM,
                ),
                category=CommentCategory.SECURITY,
                confidence=0.8,
            )
            comments.append(comment)

        return comments

    def _determine_severity(self, findings: list[dict[str, Any]]) -> Severity:
        """确定总体严重程度."""
        if not findings:
            return Severity.LOW

        worst = Severity.LOW
        for finding in findings:
            sev = finding.get("severity", "MEDIUM").upper()
            if sev == "CRITICAL":
                return Severity.CRITICAL
            elif sev == "HIGH" and worst != Severity.CRITICAL:
                worst = Severity.HIGH
            elif sev == "MEDIUM" and worst not in [Severity.CRITICAL, Severity.HIGH]:
                worst = Severity.MEDIUM

        return worst

    def _generate_summary(self, findings: list[dict[str, Any]]) -> str:
        """生成摘要."""
        if not findings:
            return "未检测到安全问题"

        critical = sum(1 for f in findings if f.get("severity") == "CRITICAL")
        high = sum(1 for f in findings if f.get("severity") == "HIGH")
        medium = sum(1 for f in findings if f.get("severity") == "MEDIUM")
        low = sum(1 for f in findings if f.get("severity") == "LOW")

        parts = []
        if critical:
            parts.append(f"{critical} 个严重")
        if high:
            parts.append(f"{high} 个高危")
        if medium:
            parts.append(f"{medium} 个中危")
        if low:
            parts.append(f"{low} 个低危")

        return f"安全扫描发现: {', '.join(parts)} 问题"

    def _generate_action_items(self, findings: list[dict[str, Any]]) -> list[str]:
        """生成修复建议."""
        items = []

        critical_high = [f for f in findings if f.get("severity") in ["CRITICAL", "HIGH"]]

        if critical_high:
            items.append(f"优先修复 {len(critical_high)} 个严重/高危安全问题")

        items.append("使用 'gitconsistency scan security <path>' 查看详细信息")

        return items

    @staticmethod
    def _find_line(code: str, pattern: str) -> int:
        """查找模式在代码中的行号."""
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if pattern in line:
                return i
        return 0
