"""安全扫描器.

集成 Semgrep（语义规则）和 Bandit（Python 专用）进行安全漏洞检测.
支持 GitNexus 上下文辅助语义判断.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from consistency.scanners.base import BaseScanner, Finding, ScanResult, Severity

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
            rules=semgrep_rules
            or [
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

        # 并行运行两个扫描器
        semgrep_task = asyncio.create_task(
            self._run_semgrep(path),
            name="semgrep_scan",
        )
        bandit_task = asyncio.create_task(
            self._run_bandit(path),
            name="bandit_scan",
        )

        # 收集结果
        findings, scanned_files, errors = await self._collect_scan_results(semgrep_task, bandit_task)

        # 后处理
        unique_findings = await self._post_process_findings(findings)

        logger.info(f"安全扫描完成: {len(unique_findings)} 个问题")

        return ScanResult(
            scanner_name=self.name,
            findings=unique_findings,
            scanned_files=scanned_files,
            errors=errors,
        )

    async def _collect_scan_results(
        self,
        semgrep_task: asyncio.Task[tuple[list[Finding], int, list[str]]],
        bandit_task: asyncio.Task[tuple[list[Finding], int, list[str]]],
    ) -> tuple[list[Finding], int, list[str]]:
        """收集扫描结果."""
        findings: list[Finding] = []
        errors: list[str] = []
        scanned_files = 0

        for task, name in [(semgrep_task, "Semgrep"), (bandit_task, "Bandit")]:
            try:
                task_findings, task_files, task_errors = await task
                findings.extend(task_findings)
                scanned_files = max(scanned_files, task_files)
                errors.extend(task_errors)
            except Exception as e:
                logger.error(f"{name} 扫描失败: {e}")
                errors.append(f"{name}: {e}")

        return findings, scanned_files, errors

    async def _post_process_findings(self, findings: list[Finding]) -> list[Finding]:
        """后处理发现的问题：去重和增强."""
        # 去重
        unique = self._deduplicate_findings(findings)

        # 如果使用 GitNexus，增强上下文
        if self.use_gitnexus and self.gitnexus_client:
            unique = await self._enhance_with_context(unique)

        return unique

    def _build_semgrep_cmd(self, path: Path) -> list[str] | None:
        """构建 Semgrep 命令."""
        # 验证路径合法性，防止路径遍历
        resolved_path = path.resolve()
        if not resolved_path.exists():
            return None

        cmd = [
            "semgrep",
            "--json",
            "--quiet",
            "--max-memory",
            str(self.semgrep_config.max_memory),
            "--timeout",
            str(self.semgrep_config.timeout),
        ]

        # 添加规则
        for rule in self.semgrep_config.rules:
            cmd.extend(["--config", rule])

        # 添加排除模式
        if self.semgrep_config.exclude:
            for pattern in self.semgrep_config.exclude:
                cmd.extend(["--exclude", pattern])

        cmd.append(str(resolved_path))
        return cmd

    def _parse_semgrep_results(self, result: dict[str, Any]) -> tuple[list[Finding], int]:
        """解析 Semgrep JSON 结果."""
        findings: list[Finding] = []

        # 解析结果
        for match in result.get("results", []):
            finding = self._parse_semgrep_match(match)
            if finding:
                findings.append(finding)

        # 安全地获取扫描文件数
        paths_data = result.get("paths", {})
        if isinstance(paths_data, dict):
            scanned_raw = paths_data.get("scanned", 0)
            scanned_files = int(scanned_raw) if not isinstance(scanned_raw, list) else len(scanned_raw)
        elif isinstance(paths_data, list):
            scanned_files = len(paths_data)
        else:
            scanned_files = 0

        return findings, scanned_files

    async def _run_semgrep(
        self,
        path: Path,
    ) -> tuple[list[Finding], int, list[str]]:
        """运行 Semgrep 扫描."""
        findings: list[Finding] = []
        errors: list[str] = []
        scanned_files = 0

        cmd = self._build_semgrep_cmd(path)
        if cmd is None:
            errors.append(f"扫描路径不存在: {path}")
            return findings, 0, errors

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
            findings, scanned_files = self._parse_semgrep_results(result)

        except FileNotFoundError:
            errors.append("Semgrep 未安装，请运行: pip install semgrep")
        except json.JSONDecodeError as e:
            errors.append(f"Semgrep 输出解析失败: {e}")
        except Exception as e:
            errors.append(f"Semgrep 执行错误: {e}")

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
                confidence=(0.9 if extra.get("metadata", {}).get("confidence", "MEDIUM").lower() == "high" else 0.7),
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

    def _build_bandit_cmd(self, path: Path) -> list[str] | None:
        """构建 Bandit 命令."""
        resolved_path = path.resolve()
        if not resolved_path.exists():
            return None

        cmd = [
            "bandit",
            "-f",
            "json",
            "-ll",
            "-ii",
        ]

        if self.bandit_config.severity == "HIGH":
            cmd.append("-lll")

        if self.bandit_config.skip_tests:
            cmd.extend(["-s", "B101"])

        if self.bandit_config.exclude_dirs:
            cmd.extend(["-x", ",".join(self.bandit_config.exclude_dirs)])

        cmd.extend(["-r", str(resolved_path)])
        return cmd

    def _parse_bandit_results(self, result: dict[str, Any]) -> tuple[list[Finding], int]:
        """解析 Bandit JSON 结果."""
        findings = []
        for issue in result.get("results", []):
            finding = self._parse_bandit_issue(issue)
            if finding:
                findings.append(finding)

        metrics = result.get("metrics", {})
        if isinstance(metrics, dict):
            scanned_files = len(metrics) - 1 if metrics else 0
        else:
            scanned_files = 0

        return findings, scanned_files

    async def _run_bandit(
        self,
        path: Path,
    ) -> tuple[list[Finding], int, list[str]]:
        """运行 Bandit 扫描."""
        findings: list[Finding] = []
        errors: list[str] = []
        scanned_files = 0

        cmd = self._build_bandit_cmd(path)
        if cmd is None:
            errors.append(f"扫描路径不存在: {path}")
            return findings, 0, errors

        logger.debug(f"Bandit 命令: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            # 记录调试信息
            logger.debug(f"Bandit stdout (first 200 chars): {stdout_str[:200] if stdout_str else '(empty)'}")
            logger.debug(f"Bandit stderr: {stderr_str[:200] if stderr_str else '(empty)'}")
            logger.debug(f"Bandit return code: {proc.returncode}")

            # Bandit 在找不到文件或出错时会输出到 stderr
            if stderr_str and proc.returncode not in (0, 1):
                errors.append(f"Bandit 错误 (exit {proc.returncode}): {stderr_str}")
                return findings, 0, errors

            # 如果 stdout 为空，说明没有扫描结果
            if not stdout_str:
                if stderr_str:
                    logger.warning(f"Bandit: {stderr_str}")
                return findings, 0, errors

            # Bandit 输出可能包含 Rich 进度条前缀（如 "Working... ━━ 100%"），需要提取 JSON
            # 找到 JSON 开始的 { 位置
            json_start = stdout_str.find("{")
            if json_start == -1:
                logger.warning(f"Bandit 输出中没有找到 JSON: {stdout_str[:100]}")
                return findings, 0, errors

            # 提取 JSON 部分
            json_str = stdout_str[json_start:]

            # 找到最后一个 } 以确保 JSON 完整
            json_end = json_str.rfind("}")
            if json_end == -1:
                logger.warning(f"Bandit JSON 不完整: {json_str[:100]}")
                return findings, 0, errors

            json_str = json_str[: json_end + 1]

            result = json.loads(json_str)
            findings, scanned_files = self._parse_bandit_results(result)

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
                confidence=(issue.get("issue_confidence") == "HIGH" and 0.9) or 0.6,
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
