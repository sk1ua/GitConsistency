"""安全扫描工具封装."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from consistency.scanners.security_scanner import SecurityScanner

logger = logging.getLogger(__name__)


class SecurityScanTool:
    """安全扫描工具.

    使用 Semgrep 和 Bandit 扫描代码安全问题.

    Examples:
        >>> tool = SecurityScanTool()
        >>> results = await tool.execute("code here", "/path/to/file.py")
    """

    name = "security_scan"
    description = """扫描代码中的安全问题.

Args:
    code: 代码内容
    file_path: 文件路径（用于确定语言）

Returns:
    安全问题列表，包含规则ID、严重级别、位置和建议
"""

    def __init__(self) -> None:
        """初始化."""
        self.scanner = SecurityScanner()

    async def execute(self, code: str, file_path: str) -> dict[str, Any]:
        """执行扫描.

        Args:
            code: 代码内容
            file_path: 文件路径

        Returns:
            扫描结果
        """
        try:
            path = Path(file_path)

            # 运行 Semgrep
            semgrep_results = await self.scanner._run_semgrep_on_code(code, path)

            # 运行 Bandit
            bandit_results = await self.scanner._run_bandit_on_code(code, path)

            all_findings = semgrep_results + bandit_results

            return {
                "file": file_path,
                "findings_count": len(all_findings),
                "findings": [
                    {
                        "rule_id": f.get("rule_id", "unknown"),
                        "message": f.get("message", ""),
                        "severity": f.get("severity", "MEDIUM"),
                        "line": f.get("line", 0),
                        "file": f.get("file_path", file_path),
                    }
                    for f in all_findings[:10]  # 限制数量
                ],
                "sources": ["semgrep", "bandit"],
            }

        except Exception as e:
            logger.error(f"安全扫描失败: {e}")
            return {"error": str(e), "findings": []}
