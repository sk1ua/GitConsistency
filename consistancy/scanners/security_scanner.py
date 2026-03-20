"""安全扫描器.

集成 Semgrep（语义规则）和 Bandit（Python 专用）进行安全漏洞检测.
支持 GitNexus 上下文辅助语义判断.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from consistancy.scanners.base import BaseScanner, Finding, ScanResult, Severity

logger = logging.getLogger(__name__)


@dataclass
class SemgrepConfig:
    """Semgrep 配置."""

    rules: list[str]
    config: list[str] | None = None
    exclude: list[str] | None = None
    max_memory: int = 500  # MB
    timeout: int = 300  # seconds


@dataclass
class BanditConfig:
    """Bandit 配置."""

    severity: str = "LOW"  # LOW, MEDIUM, HIGH
    confidence: str = "LOW"  # LOW, MEDIUM, HIGH
    skip_tests: bool = True
    exclude_dirs: list[str] | None = None


class SecurityScanner(BaseScanner):
    """安全扫描器.

    结合 Semgrep（语义规则引擎）和 Bandit（Python 专用安全工具），
    支持使用 GitNexus 上下文进行语义增强判断.

    Examples:
        >>> scanner = SecurityScanner(
        ...     semgrep_rules=["p/security-audit", "p/owasp-top-ten"],
        ...     bandit_severity="MEDIUM",
        ... )
        >>> result = await scanner.scan(Path("./my-project"))
        >>> print(f"发现 {len(result.findings)} 个问题")
    """

    SEVERITY_MAP = {
        "INFO": Severity.INFO,
        "LOW": Severity.LOW,
        "MEDIUM": Severity.MEDIUM,
        "HIGH": Severity.HIGH,
        "CRITICAL": Severity.CRITICAL,
        "ERROR": Severity.HIGH,
        "WARNING": Severity.MEDIUM,
    }

    def __init__(
        self,
        semgrep_rules: list[str] | None = None,
        bandit_severity: str = "LOW",
        use_gitnexus: bool = False,
        gitnexus_client: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """初始化安全扫描器.

        Args:
            semgrep_rules: Semgrep 规则集，如 ["p/security-audit", "p/owasp-top-ten"]
            bandit_severity: Bandit 最低严重级别 (LOW/MEDIUM/HIGH)
            use_gitnexus: 是否使用 GitNexus 上下文辅助判断
            gitnexus_client: GitNexus MCP 客户端实例
            config: 额外配置
        """
        super().__init__(config)
        self.semgrep_config = SemgrepConfig(
            rules=semgrep_rules or [
                "p/security-audit",
                "p/owasp-top-ten",
                "p/cwe-top-25",
                "p/ci",
            ],
            exclude=config.get("exclude", []) if config else None,
        )
        self.bandit_config = BanditConfig(
            severity=bandit_severity,
            exclude_dirs=config.get("exclude_dirs", ["tests", "test"]) if config else None,
        )
        self.use_gitnexus = use_gitnexus
        self.gitnexus_client = gitnexus_client

    @property
    def name(self) -> str:
        return "security"

    async def scan(self, path: Path) -> ScanResult:
        """执行安全扫描.

        并行运行 Semgrep 和 Bandit，合并结果.

        Args:
            path: 扫描目标路径

        Returns:
            扫描结果
        """
        logger.info(f"开始安全扫描: {path}")
        
        findings: list[Finding] = []
        errors: list[str] = []
        scanned_files = 0

        # 并行运行两个扫描器
        semgrep_task = asyncio.create_task(
            self._run_semgrep(path),
            name="semgrep_scan",
        )
        bandit_task = asyncio.create_task(
            self._run_bandit(path),
            name="bandit_scan",
        )

        # 等待结果
        try:
            semgrep_findings, semgrep_files, semgrep_errors = await semgrep_task
            findings.extend(semgrep_findings)
            scanned_files = max(scanned_files, semgrep_files)
            errors.extend(semgrep_errors)
        except Exception as e:
            logger.error(f"Semgrep 扫描失败: {e}")
            errors.append(f"Semgrep: {e}")

        try:
            bandit_findings, bandit_files, bandit_errors = await bandit_task
            findings.extend(bandit_findings)
            scanned_files = max(scanned_files, bandit_files)
            errors.extend(bandit_errors)
        except Exception as e:
            logger.error(f"Bandit 扫描失败: {e}")
            errors.append(f"Bandit: {e}")

        # 去重（基于文件路径、行号、规则ID）
        unique_findings = self._deduplicate_findings(findings)

        # 如果使用 GitNexus，增强上下文
        if self.use_gitnexus and self.gitnexus_client:
            unique_findings = await self._enhance_with_context(unique_findings)

        logger.info(f"安全扫描完成: {len(unique_findings)} 个问题")

        return ScanResult(
            scanner_name=self.name,
            findings=unique_findings,
            scanned_files=scanned_files,
            errors=errors,
        )

    async def _run_semgrep(
        self,
        path: Path,
    ) -> tuple[list[Finding], int, list[str]]:
        """运行 Semgrep 扫描.

        Returns:
            (findings, scanned_files, errors)
        """
        findings: list[Finding] = []
        errors: list[str] = []

        cmd = [
            "semgrep",
            "--json",
            "--quiet",
            "--max-memory", str(self.semgrep_config.max_memory),
            "--timeout", str(self.semgrep_config.timeout),
        ]

        # 添加规则
        for rule in self.semgrep_config.rules:
            cmd.extend(["--config", rule])

        # 添加排除模式
        if self.semgrep_config.exclude:
            for pattern in self.semgrep_config.exclude:
                cmd.extend(["--exclude", pattern])

        cmd.append(str(path))

        logger.debug(f"Semgrep 命令: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if stderr:
                err_msg = stderr.decode().strip()
                if err_msg:
                    logger.warning(f"Semgrep stderr: {err_msg}")

            result = json.loads(stdout.decode())

            # 解析结果
            for match in result.get("results", []):
                finding = self._parse_semgrep_match(match)
                if finding:
                    findings.append(finding)

            scanned_files = result.get("paths", {}).get("scanned", 0)

        except FileNotFoundError:
            errors.append("Semgrep 未安装，请运行: pip install semgrep")
            scanned_files = 0
        except json.JSONDecodeError as e:
            errors.append(f"Semgrep 输出解析失败: {e}")
            scanned_files = 0
        except Exception as e:
            errors.append(f"Semgrep 执行错误: {e}")
            scanned_files = 0

        return findings, scanned_files, errors

    def _parse_semgrep_match(self, match: dict[str, Any]) -> Finding | None:
        """解析 Semgrep 匹配结果."""
        try:
            extra = match.get("extra", {})
            metadata = extra.get("metadata", {})

            # 确定严重程度
            severity_str = extra.get("severity", "WARNING").upper()
            severity = self.SEVERITY_MAP.get(severity_str, Severity.MEDIUM)

            # 提升 OWASP/CWE 规则的严重程度
            if any(tag in str(metadata) for tag in ["OWASP", "CWE", "security"]):
                if severity == Severity.LOW:
                    severity = Severity.MEDIUM
                elif severity == Severity.MEDIUM:
                    severity = Severity.HIGH

            return Finding(
                rule_id=match.get("check_id", "unknown"),
                message=extra.get("message", "Security issue detected"),
                severity=severity,
                file_path=Path(match.get("path", "")),
                line=match.get("start", {}).get("line", 0),
                column=match.get("start", {}).get("col", 0),
                code_snippet=extra.get("lines", "").strip(),
                confidence=(
                    0.9 if extra.get("metadata", {}).get("confidence", "MEDIUM").lower() == "high"
                    else 0.7
                ),
                metadata={
                    "source": "semgrep",
                    "cwe": metadata.get("cwe", []),
                    "owasp": metadata.get("owasp", []),
                    "references": metadata.get("references", []),
                },
            )
        except Exception as e:
            logger.warning(f"解析 Semgrep 结果失败: {e}")
            return None

    async def _run_bandit(
        self,
        path: Path,
    ) -> tuple[list[Finding], int, list[str]]:
        """运行 Bandit 扫描.

        Returns:
            (findings, scanned_files, errors)
        """
        findings: list[Finding] = []
        errors: list[str] = []
        scanned_files = 0

        cmd = [
            "bandit",
            "-f", "json",
            "-ll",  # 输出级别
            "-ii",  # 显示更多信息
        ]

        # 严重程度过滤
        if self.bandit_config.severity == "HIGH":
            cmd.append("-lll")

        # 跳过测试文件
        if self.bandit_config.skip_tests:
            cmd.append("-s")
            cmd.append("B101")  # skip assert_used in tests

        # 排除目录
        if self.bandit_config.exclude_dirs:
            cmd.append("-x")
            cmd.append(",".join(self.bandit_config.exclude_dirs))

        cmd.append("-r")
        cmd.append(str(path))

        logger.debug(f"Bandit 命令: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            # Bandit 返回 1 表示发现了问题，这是正常的
            if proc.returncode not in (0, 1):
                err_msg = stderr.decode().strip()
                if err_msg:
                    errors.append(f"Bandit 错误 (exit {proc.returncode}): {err_msg}")

            result = json.loads(stdout.decode())

            # 解析结果
            for issue in result.get("results", []):
                finding = self._parse_bandit_issue(issue)
                if finding:
                    findings.append(finding)

            metrics = result.get("metrics", {})
            scanned_files = len(metrics) - 1 if metrics else 0  # 减去 "_totals"

        except FileNotFoundError:
            errors.append("Bandit 未安装，请运行: pip install bandit[toml]")
        except json.JSONDecodeError as e:
            errors.append(f"Bandit 输出解析失败: {e}")
        except Exception as e:
            errors.append(f"Bandit 执行错误: {e}")

        return findings, scanned_files, errors

    def _parse_bandit_issue(self, issue: dict[str, Any]) -> Finding | None:
        """解析 Bandit 问题."""
        try:
            severity_map = {
                "LOW": Severity.LOW,
                "MEDIUM": Severity.MEDIUM,
                "HIGH": Severity.HIGH,
            }

            return Finding(
                rule_id=issue.get("test_id", "B000"),
                message=issue.get("issue_text", "Security issue"),
                severity=severity_map.get(issue.get("issue_severity", "LOW"), Severity.LOW),
                file_path=Path(issue.get("filename", "")),
                line=issue.get("line_number", 0),
                column=issue.get("col_offset", 0),
                code_snippet=issue.get("code", "").strip(),
                confidence=issue.get("issue_confidence") == "HIGH" and 0.9 or 0.6,
                metadata={
                    "source": "bandit",
                    "test_name": issue.get("test_name", ""),
                    "more_info": issue.get("more_info", ""),
                },
            )
        except Exception as e:
            logger.warning(f"解析 Bandit 结果失败: {e}")
            return None

    def _deduplicate_findings(self, findings: list[Finding]) -> list[Finding]:
        """去重发现的问题."""
        seen: set[str] = set()
        unique: list[Finding] = []

        for finding in findings:
            key = f"{finding.file_path}:{finding.line}:{finding.rule_id}"
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        return unique

    async def _enhance_with_context(self, findings: list[Finding]) -> list[Finding]:
        """使用 GitNexus 上下文增强问题判断."""
        if not self.gitnexus_client:
            return findings

        enhanced = []
        for finding in findings:
            # 获取上下文
            try:
                context = await self.gitnexus_client.context(
                    str(finding.file_path),
                    line=finding.line,
                )

                # 判断变量是否为用户输入（增强漏洞判断）
                if context.symbols:
                    for symbol in context.symbols:
                        name = symbol.get("name")
                        snippet = finding.code_snippet or ""
                        if name in snippet and symbol.get("is_user_input"):
                            finding.severity = Severity.HIGH
                            finding.metadata["is_user_input"] = True

                enhanced.append(finding)
            except Exception as e:
                logger.debug(f"获取上下文失败: {e}")
                enhanced.append(finding)

        return enhanced
