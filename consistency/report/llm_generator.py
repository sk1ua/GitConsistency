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

        prompt = f"""你是一位经验丰富的技术审计架构师。请对输入内容进行深度分析，输出一份"傻瓜级修复清单"报告。

## 项目信息
- 项目名称: {project_name}
- 提交: {commit_sha[:8] if commit_sha else "unknown"}
- 扫描耗时: {duration:.2f}s

## 发现的问题数据
```json
{json.dumps(findings_data, ensure_ascii=False, indent=2)}
```

## 输出格式规范

### 顶部概览栏
在最开头生成统计徽章，格式如下：
```
🔴 严重问题 {{{{N}}}} 项    🟠 中等问题 {{{{N}}}} 项    🟢 轻微问题 {{{{N}}}} 项

🔴 严重 — [一句话说明此类风险的核心影响，如"会导致工具完全无法使用"]
🟠 中等 — [一句话说明，如"让人困惑或浪费依赖空间"]
🟢 轻微 — [一句话说明，如"建议优化但非阻塞"]
```

### 问题详情格式
使用 `<details>` 标签实现可折叠区块：

**🔴 严重级（默认展开）**
```html
<details open>
<summary><b>严重#N [问题标题]</b> — [副标题/现象描述]</summary>

**影响：** [一句话说明后果]

**证据/定位：**
1. 路径：`具体/文件/路径.py:行号`
2. [其他证据]

**修复方案：**
- [ ] 选项A（推荐）：[具体操作步骤]
- [ ] 选项B：[替代方案]

> ⚠️ 警告：[关键提醒，如"别人看README以为功能存在，clone下来跑不起来会直接关掉页面走人"]
</details>
```

**🟠 中等级（默认折叠）**
```html
<details>
<summary><b>中等#N [标题]</b> — [副标题]</summary>
...（同上结构）...
</details>
```

**🟢 轻微级（默认折叠）**
```html
<details>
<summary><b>轻微#N [标题]</b> — [副标题]</summary>
...（同上结构，可简化）...
</details>
```

### 内容规范
1. **编号规则**：同类问题连续编号（严重#1、严重#2...），不要跨类型混编
2. **颜色绑定**：🔴=严重(Critical) 🟠=中等(Warning) 🟢=轻微(Minor)，绝对禁止混用
3. **高亮规范**：所有文件路径、命令、代码片段必须用 `代码块` 包裹
4. **行动导向**：每个严重问题必须提供可执行的修复命令或代码
5. **严重程度映射**：CRITICAL/HIGH → 🔴 严重, MEDIUM → 🟠 中等, LOW/INFO → 🟢 轻微

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

        prompt = (
            """你是一位经验丰富的技术审计架构师。请对输入内容进行深度分析，输出一份
适合 GitHub PR 的"傻瓜级修复清单"报告。

## 项目信息
- 项目名称: """
            + f"{project_name}\n"
            + f"- 提交: {commit_sha[:8] if commit_sha else 'HEAD'}\n"
            + f"- 扫描耗时: {duration:.2f}s\n"
            + """
## 发现的问题数据
```json
"""
            + json.dumps(findings_data, ensure_ascii=False, indent=2)
            + """
```

## 输出格式规范

### 顶部概览栏（必须放在最开头）
```
🔴 严重问题 {{{{N}}}} 项    🟠 中等问题 {{{{N}}}} 项    🟢 轻微问题 {{{{N}}}} 项

🔴 严重 — [一句话说明此类风险的核心影响]
🟠 中等 — [一句话说明]
🟢 轻微 — [一句话说明]
```

### 问题详情格式
使用 `<details>` 标签实现可折叠区块：

**🔴 严重级（默认展开）**
```html
<details open>
<summary><b>严重#N [问题标题]</b> — [副标题/现象描述]</summary>

**影响：** [一句话说明后果]

**证据/定位：**
1. 路径：`具体/文件/路径.py:行号`
2. [其他证据]

**修复方案：**
- [ ] 选项A（推荐）：[具体操作步骤]
- [ ] 选项B：[替代方案]

> ⚠️ 警告：[关键提醒]
</details>
```

**🟠 中等级（默认折叠）**
```html
<details>
<summary><b>中等#N [标题]</b> — [副标题]</summary>
...（同上结构）...
</details>
```

**🟢 轻微级（默认折叠）**
```html
<details>
<summary><b>轻微#N [标题]</b> — [副标题]</summary>
...（简化结构）...
</details>
```

### 内容规范
1. **编号规则**：同类问题连续编号（严重#1、严重#2...）
2. **颜色绑定**：🔴=严重(CRITICAL/HIGH) 🟠=中等(MEDIUM) 🟢=轻微(LOW/INFO)
3. **高亮规范**：所有文件路径、命令、代码片段必须用 `代码块` 包裹
4. **行动导向**：每个严重问题必须提供可执行的修复方案（带 - [ ] checkbox）
5. **长度限制**：确保整体长度不超过 """
            + f"{max_length} 字符\n\n请直接输出 Markdown 内容。"
        )

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

        prompt = (
            """你是一位经验丰富的技术审计架构师。请对输入内容进行深度分析，输出一份
适合 GitHub Actions 的"傻瓜级修复清单"报告。

## 项目信息
- 项目名称: """
            + f"{project_name}\n"
            + f"- 扫描耗时: {duration_ms:.0f}ms\n"
            + """
## 发现的问题数据
```json
"""
            + json.dumps(findings_data, ensure_ascii=False, indent=2)
            + """
```

## 输出格式规范

### 顶部概览栏（必须放在最开头）
```
🔴 严重问题 {{{{N}}}} 项    🟠 中等问题 {{{{N}}}} 项    🟢 轻微问题 {{{{N}}}} 项

🔴 严重 — [一句话说明此类风险的核心影响]
🟠 中等 — [一句话说明]
🟢 轻微 — [一句话说明]
```

### 问题详情格式
使用 `<details>` 标签实现可折叠区块：

**🔴 严重级（默认展开）**
```html
<details open>
<summary><b>严重#N [问题标题]</b> — [副标题/现象描述]</summary>

**影响：** [一句话说明后果]

**证据/定位：**
1. 路径：`具体/文件/路径.py:行号`
2. [其他证据]

**修复方案：**
- [ ] 选项A（推荐）：[具体操作步骤]
- [ ] 选项B：[替代方案]

> ⚠️ 警告：[关键提醒]
</details>
```

**🟠 中等级（默认折叠）**
```html
<details>
<summary><b>中等#N [标题]</b> — [副标题]</summary>
...（同上结构）...
</details>
```

**🟢 轻微级（默认折叠）**
```html
<details>
<summary><b>轻微#N [标题]</b> — [副标题]</summary>
...（简化结构）...
</details>
```

### 内容规范
1. **编号规则**：同类问题连续编号（严重#1、严重#2...）
2. **颜色绑定**：🔴=严重(CRITICAL/HIGH) 🟠=中等(MEDIUM) 🟢=轻微(LOW/INFO)
3. **高亮规范**：所有文件路径、命令、代码片段必须用 `代码块` 包裹
4. **行动导向**：每个严重问题必须提供可执行的修复方案（带 - [ ] checkbox）

### 整体状态判断
- 🔴 有严重问题：概览栏显示 Failed 状态
- 🟠 有中等问题：概览栏显示 Warning 状态
- 🟢 无问题：概览栏显示 Passed 状态

请直接输出 Markdown 内容。"""
        )

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
