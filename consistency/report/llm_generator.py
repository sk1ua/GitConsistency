"""LLM 驱动的报告生成器.

完全基于 LLM 生成所有报告格式，不再使用硬编码模板。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from consistency.llm import LLMProviderFactory
from consistency.scanners.base import Finding, ScanResult

logger = logging.getLogger(__name__)


class LLMReportGenerator:
    """LLM 驱动的报告生成器.

    所有报告内容均由 LLM 生成，提供自然语言、上下文感知的报告。
    """

    # LLM 调用超时时间（秒）
    LLM_TIMEOUT_SECONDS = 60
    # 最大重试次数
    MAX_RETRIES = 3

    # 严格架构师系统提示词
    # ruff: noqa: E501
    STRICT_ARCHITECT_SYSTEM_PROMPT = """# 角色定位

你是一位拥有 20 年经验的资深软件架构师与技术负责人，以极其严格、苛刻的标准著称。你的使命是确保每一行代码都达到工业级生产标准，绝不容忍任何技术债务、潜在隐患或平庸的实现。

## 审查原则

1. **零容忍原则**：对安全隐患、性能陷阱、边界条件处理不当零容忍
2. **工程化思维**：代码不仅是"能跑"，还要可维护、可扩展、可观测
3. **保守主义**：除非证明有益，否则默认质疑新依赖、新语法糖、复杂抽象
4. **数据驱动**：所有性能 claims 必须有复杂度分析，所有架构决策必须有权衡分析

## 审查维度（按严重程度分级）

### 🔴 P0 - 阻断性问题（Blockers）
- **安全隐患**：SQL 注入、XSS、敏感信息硬编码、不安全的反序列化
- **并发问题**：竞态条件、死锁风险、非线程安全操作
- **资源泄漏**：数据库连接未关闭、文件句柄泄漏、内存泄漏
- **逻辑缺陷**：边界条件处理缺失（空值、越界、溢出）、事务边界错误
- **性能灾难**：时间/空间复杂度不合理的嵌套循环、N+1 查询问题

### 🟠 P1 - 严重问题（Critical）
- **错误处理**：裸异常捕获、错误码不一致、重试策略缺失
- **API 契约**：接口幂等性未保障、版本兼容性风险
- **数据一致性**：缺乏事务控制、缓存与数据库不一致风险
- **可观测性**：关键路径无日志、无指标采集
- **测试覆盖**：核心逻辑缺乏单元测试、边界条件未测试

### 🟡 P2 - 中等问题（Major）
- **代码异味**：过长方法（>50 行）、过深嵌套（>3 层）、魔法数字/字符串
- **命名规范**：模糊不清的命名（processData, handleStuff）
- **注释质量**：冗余注释、过时注释、缺少关键算法解释
- **类型安全**：过度使用 any、泛型使用不当
- **依赖管理**：引入重量级依赖仅为了简单功能

### 🟢 P3 - 建议优化（Minor/Nitpicks）
- **风格一致性**：与项目代码风格不符
- **性能微调**：不必要的对象创建
- **现代语法**：可用更现代/安全的语言特性替换旧写法

## 交互规则

1. **严格分级**：绝不把 P0 问题降级为 P1，也绝不把 P3 问题夸大为 P2
2. **建设性刻薄**：严厉批评代码质量，但必须给出具体、可落地的修复方案
3. **拒绝 bullshit**：遇到"这个暂时不会出问题"、"以后重构"直接驳回
4. **教育视角**：对 P0/P1 问题，解释"为什么这是错的"以及"如何在代码审查阶段发现"

## 输出要求

- 使用中文输出
- 严格按格式规范输出
- 每个问题必须有文件路径和行号
- 每个严重问题必须提供修复代码
"""

    # 分层诊断报告格式规范
    REPORT_FORMAT_SPEC = """
## 输出格式规范（必须严格遵守）

### 1. 顶部概览栏（必须放在最开头）

```
🔴 严重问题 {{critical_count}} 项    🟠 中等问题 {{high_count}} 项    🟢 轻微问题 {{medium_count}} 项

🔴 严重 — 会导致系统崩溃/数据丢失/安全漏洞/生产环境宕机
🟠 中等 — 功能异常/性能下降/兼容性问题/让人困惑或浪费资源
🟢 轻微 — 代码异味/文档缺失/优化建议/非阻塞性改进建议
```

### 2. 问题详情（按严重度分组，同类问题连续编号）

**🔴 严重级 — 会导致生产环境宕机或严重安全事故**

<details open>
<summary><b>🔴 严重#1 [问题标题]</b> — [副标题/具体现象]</summary>

**影响：** [一句话说明最坏情况下的后果]

**复现步骤/证据：**
1. 文件路径：`具体/文件/路径.py:行号`
2. 代码片段：
```python
[有问题的原始代码]
```

**风险分析：**
- 最坏情况场景：[描述极端情况下的后果]
- 触发条件：[具体什么情况下会触发]
- 影响范围：[影响的数据量/用户数/系统组件]

**修复方案：**
- [ ] 选项A（推荐）：[具体操作步骤]
```python
[修复后的代码]
```
- [ ] 选项B：[替代方案]

> ⚠️ **警告：** [关键提醒]

</details>

**🟠 中等级 — 功能异常或性能下降**

<details>
<summary><b>🟠 中等#1 [标题]</b> — [副标题]</summary>

**影响：** [一句话说明后果]

**复现步骤/证据：**
1. 文件路径：`具体/文件/路径.py:行号`
2. 代码片段：
```python
[有问题的原始代码]
```

**修复方案：**
- [ ] 选项A（推荐）：[具体操作]
```python
[修复后的代码]
```

> 💡 **建议：** [关键提醒]

</details>

**🟢 轻微级 — 代码异味或优化建议**

<details>
<summary><b>🟢 轻微#1 [标题]</b> — [副标题]</summary>

**影响：** [一句话说明]

**定位：**
- 文件路径：`具体/文件/路径.py:行号`

**修复方案：**
- [ ] [具体修复建议]

</details>

### 3. 格式强制要求

1. **颜色-图标-严重度映射**（绝对禁止混用）：
   - 🔴 = P0/CRITICAL（阻断性）
   - 🟠 = P1/HIGH（严重）
   - 🟡 = P2/MEDIUM（中等）
   - 🟢 = P3/LOW（轻微）

2. **编号规则**：同类问题连续编号（严重#1、严重#2...），不要跨类型混编

3. **高亮规范**：
   - 所有文件路径、命令、代码片段必须用 `代码块` 包裹
   - 关键结论加 **粗体**
   - 使用引用块 `>` 展示警告信息

4. **折叠规则**：
   - 🔴 严重级：`<details open>`（默认展开）
   - 🟠 中等级：`<details>`（默认折叠）
   - 🟢 轻微级：`<details>`（默认折叠）
"""

    def __init__(self) -> None:
        """初始化 LLM 报告生成器."""
        self.llm = LLMProviderFactory.create_from_settings()

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """调用 LLM 生成内容.

        Args:
            messages: 消息列表，包含 system 和 user 角色

        Returns:
            LLM 生成的文本

        Raises:
            asyncio.TimeoutError: 当 LLM 调用超时
            ConnectionError: 当连接失败且重试耗尽
        """
        try:
            # 使用 asyncio.wait_for 添加超时控制
            response = await asyncio.wait_for(
                self.llm.complete(messages=messages),
                timeout=self.LLM_TIMEOUT_SECONDS,
            )
            return response.content.strip()
        except asyncio.TimeoutError:
            logger.warning(f"LLM 调用超时（{self.LLM_TIMEOUT_SECONDS}秒）")
            raise
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

    def _build_messages(
        self,
        findings_data: dict[str, Any],
        project_name: str,
        duration_info: str,
        extra_instructions: str = "",
    ) -> list[dict[str, str]]:
        """构建消息列表供 LLM 使用.

        Args:
            findings_data: 问题数据
            project_name: 项目名称
            duration_info: 耗时信息字符串
            extra_instructions: 额外指令

        Returns:
            消息列表，包含 system 和 user 角色
        """
        user_content_parts = [
            '你是一位经验丰富的技术审计架构师。请对输入内容进行深度分析，输出一份"傻瓜级修复清单"报告。',
            "",
            "## 项目信息",
            f"- 项目名称: {project_name}",
            duration_info,
            "",
            "## 发现的问题数据",
            "```json",
            json.dumps(findings_data, ensure_ascii=False, indent=2),
            "```",
            self.REPORT_FORMAT_SPEC,
        ]

        if extra_instructions:
            user_content_parts.append(extra_instructions)

        user_content_parts.append("\n请直接输出 Markdown 内容，不要添加额外的说明文字。")

        return [
            {"role": "system", "content": self.STRICT_ARCHITECT_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_content_parts)},
        ]

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
        findings_data = self._prepare_findings_data(scan_results)
        duration_info = f"- 提交: {commit_sha[:8] if commit_sha else 'unknown'}\n- 扫描耗时: {duration:.2f}s"

        messages = self._build_messages(findings_data, project_name, duration_info)

        try:
            return await self._call_llm(messages)
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
        duration_info = f"- 提交: {commit_sha[:8] if commit_sha else 'HEAD'}\n- 扫描耗时: {duration:.2f}s"
        extra_instructions = f"\n### 额外要求\n- 适合 GitHub PR 的格式\n- 确保整体长度不超过 {max_length} 字符"

        messages = self._build_messages(findings_data, project_name, duration_info, extra_instructions)

        try:
            comment = await self._call_llm(messages)
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
        duration_info = f"- 扫描耗时: {duration_ms:.0f}ms"
        extra_instructions = """\n### 整体状态判断
- 🔴 有严重问题：概览栏显示 Failed 状态
- 🟠 有中等问题：概览栏显示 Warning 状态
- 🟢 无问题：概览栏显示 Passed 状态

### 额外要求
- 适合 GitHub Actions 的格式"""

        messages = self._build_messages(findings_data, project_name, duration_info, extra_instructions)

        try:
            return await self._call_llm(messages)
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
            "# 🔍 GitConsistency Code Health Report",
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
            "# 🔍 GitConsistency Code Review Report",
            "",
            f"**项目**: {project_name} | **提交**: `{commit_sha[:8] if commit_sha else 'HEAD'}`",
            "",
            summary_line,
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
