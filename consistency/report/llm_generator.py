"""LLM 驱动的报告生成器.

完全基于 LLM 生成所有报告格式，不再使用硬编码模板。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from consistency.llm import LLMProviderFactory
from consistency.scanners.base import Finding, ScanResult

logger = logging.getLogger(__name__)


class LLMReportGenerator:
    """LLM 驱动的报告生成器.

    所有报告内容均由 LLM 生成，提供自然语言、上下文感知的报告。
    """

    def __init__(self) -> None:
        """初始化 LLM 报告生成器."""
        self.llm = LLMProviderFactory.create_from_settings()

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM 生成内容."""
        messages = [
            {"role": "system", "content": "你是一个专业的代码审查报告生成专家。"},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self.llm.complete(messages=messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

    async def generate(
        self,
        scan_results: list[ScanResult],
        project_name: str = "Unknown",
        commit_sha: str = "unknown",
        duration: float = 0.0,
    ) -> str:
        """生成 Markdown 报告.

        Args:
            scan_results: 扫描结果列表
            project_name: 项目名称
            commit_sha: 提交 SHA
            duration: 扫描耗时

        Returns:
            Markdown 格式的报告
        """
        # 构建问题数据
        findings_data = self._prepare_findings_data(scan_results)

        prompt = f"""你是一个专业的代码审查报告生成专家。请基于以下代码扫描结果生成一份清晰、可执行的审查报告。

## 项目信息
- 项目名称: {project_name}
- 提交: {commit_sha[:8] if commit_sha else "unknown"}
- 扫描耗时: {duration:.2f}s

## 发现的问题数据
```json
{json.dumps(findings_data, ensure_ascii=False, indent=2)}
```

## 报告要求

请生成一份 Markdown 格式的代码审查报告，包含以下部分：

1. **执行摘要** - 概述整体情况，关键统计数据
2. **严重问题**（CRITICAL/HIGH）- 详细列出，包括：
   - 问题描述和影响
   - 具体位置（文件、行号）
   - 修复建议（具体的代码修改）
   - 验收标准（如何验证修复）
3. **中等问题**（MEDIUM）- 简要列出主要问题和建议
4. **信息提示**（LOW/INFO）- 可选优化项
5. **修复优先级清单** - 按优先级排序的可执行任务列表

## 报告风格

- 使用清晰的 emoji 图标区分严重程度（🔴 严重、🟠 中等、🟡 轻微、🟢 信息）
- 每个问题都要有可执行的修复建议，不要只是描述问题
- 使用 collapsible sections (<details>) 组织内容，保持报告整洁
- 代码片段使用 Markdown 代码块
- 报告应该直接可用，开发者能按图索骥修复问题

请直接输出 Markdown 内容，不要添加额外的说明文字。"""

        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM 报告生成失败: {e}")
            return self._fallback_report(findings_data, project_name, commit_sha, duration)

    async def generate_github_comment(
        self,
        scan_results: list[ScanResult],
        project_name: str = "Unknown",
        commit_sha: str = "HEAD",
        duration: float = 0.0,
        max_length: int = 65536,
    ) -> str:
        """生成 GitHub PR 评论.

        Args:
            scan_results: 扫描结果列表
            project_name: 项目名称
            commit_sha: 提交 SHA
            duration: 扫描耗时
            max_length: 最大长度限制

        Returns:
            评论内容
        """
        findings_data = self._prepare_findings_data(scan_results)

        prompt = f"""你是一个 GitHub PR 评论生成专家。请基于代码扫描结果生成一份适合 GitHub PR 评论的审查报告。

## 项目信息
- 项目名称: {project_name}
- 提交: {commit_sha[:8] if commit_sha else "HEAD"}
- 扫描耗时: {duration:.2f}s

## 发现的问题数据
```json
{json.dumps(findings_data, ensure_ascii=False, indent=2)}
```

## 评论要求

生成一份 GitHub PR 评论，格式如下：

1. **顶部概览栏** - 显示统计信息：
   ```
   🔴 严重问题 X 项    🟠 中等问题 Y 项    🟢 轻微问题 Z 项
   ```

2. **严重问题**（默认展开 <details open>）：
   - 清晰的问题标题和描述
   - 影响说明
   - 证据/位置信息
   - 具体修复方案（带 checkbox）
   - ⚠️ 警告标签

3. **中等问题**（默认折叠 <details>）：
   - 类似严重问题的格式但默认折叠
   - 💡 建议标签

4. **轻微问题**：
   - 简化显示，一行一个

5. **统计摘要表格**：
   | 类别 | 数量 | 状态 |

## 格式要求

- 使用 GitHub 支持的 Markdown
- 使用 <details> 标签组织可折叠内容
- 严重问题默认展开，其他默认折叠
- 每个修复项使用 `- [ ]` checkbox 格式
- 确保整体长度不超过 {max_length} 字符

请直接输出评论内容。"""

        try:
            comment = await self._call_llm(prompt)
            if len(comment) > max_length:
                comment = comment[: max_length - 100] + "\n\n... (内容已截断)"
            return comment
        except Exception as e:
            logger.error(f"LLM GitHub 评论生成失败: {e}")
            return self._fallback_github_comment(findings_data, project_name, commit_sha, duration)

    async def generate_actions_summary(
        self,
        scan_results: list[ScanResult],
        project_name: str = "Unknown",
        duration_ms: float = 0.0,
    ) -> str:
        """生成 GitHub Actions Job Summary.

        Args:
            scan_results: 扫描结果列表
            project_name: 项目名称
            duration_ms: 扫描耗时（毫秒）

        Returns:
            Markdown 摘要内容
        """
        findings_data = self._prepare_findings_data(scan_results)

        prompt = f"""你是一个 CI/CD 报告生成专家。请生成一份 GitHub Actions Job Summary。

## 项目信息
- 项目名称: {project_name}
- 扫描耗时: {duration_ms:.0f}ms

## 发现的问题数据
```json
{json.dumps(findings_data, ensure_ascii=False, indent=2)}
```

## 摘要要求

生成一份适合 GitHub Actions Step Summary 的 Markdown，包含：

1. **标题** - 使用合适的 emoji 表示整体状态
2. **执行摘要表格** - 关键指标
3. **严重问题表格** - 最多显示前 10 个严重/高优先级问题
4. **修复建议** - 按优先级排序的行动项

## 整体状态判断
- 🔴 有严重问题：状态为 Failed
- ⚠️ 有高优先级问题：状态为 Warning
- ✅ 无严重/高优先级问题：状态为 Passed

请直接输出 Markdown 内容。"""

        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM Actions Summary 生成失败: {e}")
            return self._fallback_actions_summary(findings_data, project_name, duration_ms)

    def _prepare_findings_data(self, scan_results: list[ScanResult]) -> dict[str, Any]:
        """准备问题数据供 LLM 使用."""
        all_findings: list[Finding] = []
        for result in scan_results:
            all_findings.extend(result.findings)

        # 按严重级别分组
        findings_by_severity: dict[str, list[dict[str, Any]]] = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
            "INFO": [],
        }

        for finding in all_findings:
            severity = finding.severity.value.upper()
            finding_data = {
                "rule_id": finding.rule_id,
                "message": finding.message,
                "severity": severity,
                "file": str(finding.file_path) if finding.file_path else None,
                "line": finding.line,
                "code_snippet": finding.code_snippet,
                "confidence": finding.confidence,
                "metadata": finding.metadata,
            }
            if severity in findings_by_severity:
                findings_by_severity[severity].append(finding_data)

        return {
            "total_findings": len(all_findings),
            "severity_counts": {sev: len(items) for sev, items in findings_by_severity.items()},
            "findings_by_severity": findings_by_severity,
            "scanner_errors": [
                {"scanner": result.scanner_name, "errors": result.errors} for result in scan_results if result.errors
            ],
        }

    def _fallback_report(
        self,
        findings_data: dict[str, Any],
        project_name: str,
        commit_sha: str,
        duration: float,
    ) -> str:
        """当 LLM 失败时的备用报告."""
        lines = [
            "# 🔍 GitConsistency Code Review Report",
            "",
            f"> **Project**: {project_name}",
            f"> **Commit**: `{commit_sha[:8] if commit_sha else 'unknown'}`",
            f"> **Duration**: {duration:.2f}s",
            "",
            "## 📊 Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ]

        counts = findings_data["severity_counts"]
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "⚪"}.get(sev, "⚪")
            lines.append(f"| {emoji} {sev} | {counts.get(sev, 0)} |")

        lines.extend(["", "## 🔍 Findings", ""])

        for severity in ["CRITICAL", "HIGH", "MEDIUM"]:
            findings = findings_data["findings_by_severity"].get(severity, [])
            if findings:
                lines.append(f"### {severity} Issues ({len(findings)})")
                for f in findings[:5]:
                    file_str = f"`{f['file']}:{f['line']}`" if f["file"] and f["line"] else "-"
                    lines.append(f"- **{f['rule_id']}**: {f['message']} ({file_str})")
                if len(findings) > 5:
                    lines.append(f"- ... and {len(findings) - 5} more")
                lines.append("")

        return "\n".join(lines)

    def _fallback_github_comment(
        self,
        findings_data: dict[str, Any],
        project_name: str,
        commit_sha: str,
        duration: float,
    ) -> str:
        """当 LLM 失败时的备用评论."""
        counts = findings_data["severity_counts"]
        total = sum(counts.values())

        crit_count = counts.get("CRITICAL", 0)
        high_count = counts.get("HIGH", 0)
        med_count = counts.get("MEDIUM", 0)
        summary_line = f"🔴 严重问题 {crit_count} 项    🟠 中等问题 {high_count} 项    🟢 轻微问题 {med_count} 项"

        lines = [
            "# 🔍 GitConsistency 代码审查报告",
            "",
            "```",
            summary_line,
            "```",
            "",
            f"> **项目**: {project_name}",
            f"> **提交**: `{commit_sha[:8] if commit_sha else 'HEAD'}`",
            "",
            f"发现 {total} 个问题，请查看完整报告获取详细信息。",
            "",
            "---",
            "",
            "*Generated by GitConsistency*",
        ]

        return "\n".join(lines)

    def _fallback_actions_summary(
        self,
        findings_data: dict[str, Any],
        project_name: str,
        duration_ms: float,
    ) -> str:
        """当 LLM 失败时的备用 Actions Summary."""
        counts = findings_data["severity_counts"]
        critical = counts.get("CRITICAL", 0)
        high = counts.get("HIGH", 0)

        if critical > 0:
            status = "❌ Failed"
        elif high > 0:
            status = "⚠️ Warning"
        else:
            status = "✅ Passed"

        return f"""# {status} GitConsistency Code Review

| Metric | Value |
|--------|-------|
| **Project** | {project_name} |
| **Status** | {status} |
| **Duration** | {duration_ms:.0f}ms |

## Severity Counts

| Severity | Count |
|----------|-------|
| 🔴 Critical | {critical} |
| 🟠 High | {high} |
| 🟡 Medium | {counts.get("MEDIUM", 0)} |
| 🟢 Low | {counts.get("LOW", 0)} |
| 🔵 Info | {counts.get("INFO", 0)} |
"""
