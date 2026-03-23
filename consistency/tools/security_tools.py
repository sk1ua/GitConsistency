"""安全扫描工具封装."""

from __future__ import annotations

import logging
import tempfile
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
            source_path = Path(file_path)
            suffix = source_path.suffix or ".py"

            # 将代码写入临时目录并复用标准扫描流程，避免依赖不存在的私有方法
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_file = Path(tmpdir) / f"snippet{suffix}"
                temp_file.write_text(code, encoding="utf-8")

                scan_result = await self.scanner.scan(temp_file)
                all_findings = scan_result.findings

            return {
                "file": file_path,
                "findings_count": len(all_findings),
                "findings": [
                    {
                        "rule_id": f.rule_id,
                        "message": f.message,
                        "severity": f.severity.value.upper(),
                        "line": f.line,
                        "file": str(f.file_path) if f.file_path else file_path,
                    }
                    for f in all_findings[:10]  # 限制数量
                ],
                "sources": ["semgrep", "bandit"],
            }

        except Exception as e:
            logger.error(f"安全扫描失败: {e}")
            return {"error": str(e), "findings": []}
