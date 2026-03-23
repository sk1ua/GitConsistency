"""安全审查 Agent."""

from __future__ import annotations

import logging
import time
from dataclasses import field
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
        all_findings = []
        metadata = {"sources": []}

        # 1. 运行 Semgrep
        try:
            semgrep_results = await self.scanner._run_semgrep_on_code(code, file_path)
            all_findings.extend(semgrep_results)
            metadata["sources"].append("semgrep")
        except Exception as e:
            logger.warning(f"Semgrep 扫描失败: {e}")

        # 2. 运行 Bandit
        try:
            bandit_results = await self.scanner._run_bandit_on_code(code, file_path)
            all_findings.extend(bandit_results)
            metadata["sources"].append("bandit")
        except Exception as e:
            logger.warning(f"Bandit 扫描失败: {e}")

        # 3. GitNexus 增强（如果有）
        if self.use_gitnexus:
            try:
                gitnexus_findings = await self._analyze_with_gitnexus(file_path, code)
                all_findings.extend(gitnexus_findings)
                metadata["sources"].append("gitnexus")
            except Exception as e:
                logger.warning(f"GitNexus 分析失败: {e}")

        # 4. 转换为 comments
        comments = self._convert_to_comments(all_findings)

        # 5. 确定严重程度
        severity = self._determine_severity(all_findings)

        # 6. 生成摘要
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
                        findings.append({
                            "rule_id": f"gitnexus-dangerous-{func}",
                            "message": f"危险函数 '{func}' 被调用，调用链: {len(ctx.callers)} 处",
                            "severity": "HIGH" if func in ["eval", "exec"] else "MEDIUM",
                            "file_path": file_path,
                            "line": self._find_line(code, func),
                            "source": "gitnexus",
                        })
                except Exception as e:
                    logger.debug(f"GitNexus 上下文获取失败 {func}: {e}")

        return findings

    def _convert_to_comments(self, findings: list[dict]) -> list[ReviewComment]:
        """将发现转换为 ReviewComment."""
        comments = []

        for finding in findings:
            severity_map = {
                "CRITICAL": Severity.CRITICAL,
                "HIGH": Severity.HIGH,
                "MEDIUM": Severity.MEDIUM,
                "LOW": Severity.LOW,
            }

            comment = ReviewComment(
                file=str(finding.get("file_path", "")),
                line=finding.get("line", 0),
                message=finding.get("message", ""),
                severity=severity_map.get(
                    finding.get("severity", "MEDIUM").upper(),
                    Severity.MEDIUM,
                ),
                category=CommentCategory.SECURITY,
                rule_id=finding.get("rule_id", "unknown"),
            )
            comments.append(comment)

        return comments

    def _determine_severity(self, findings: list[dict]) -> Severity:
        """确定总体严重程度."""
        if not findings:
            return Severity.LOW

        severity_order = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
        ]

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

    def _generate_summary(self, findings: list[dict]) -> str:
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

    def _generate_action_items(self, findings: list[dict]) -> list[str]:
        """生成修复建议."""
        items = []

        critical_high = [
            f for f in findings
            if f.get("severity") in ["CRITICAL", "HIGH"]
        ]

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
