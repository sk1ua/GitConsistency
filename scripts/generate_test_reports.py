#!/usr/bin/env python3
"""生成示例报告以测试严格提示词系统."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from consistency.report.llm_generator import LLMReportGenerator
from consistency.scanners.base import Finding, ScanResult, Severity


def create_mock_findings() -> list[ScanResult]:
    """创建模拟扫描结果用于测试."""

    # 创建一些模拟发现的问题
    security_finding = Finding(
        rule_id="security-hardcoded-secret",
        message="发现硬编码的 API 密钥: api_key = 'sk-1234567890abcdef'",
        severity=Severity.CRITICAL,
        file_path=Path("settings.py"),
        line=42,
        code_snippet="API_KEY = 'sk-1234567890abcdef'",
        confidence=0.95,
        metadata={"pattern": "hardcoded-secret", "language": "python"},
    )

    logic_finding = Finding(
        rule_id="logic-infinite-loop",
        message="可能导致无限循环的条件",
        severity=Severity.HIGH,
        file_path=Path("processor.py"),
        line=88,
        code_snippet="while i < len(items):\n    if items[i] > threshold:\n        continue",
        confidence=0.7,
        metadata={"pattern": "infinite-loop", "language": "python"},
    )

    style_finding = Finding(
        rule_id="style-line-too-long",
        message="行长度超过 120 字符",
        severity=Severity.LOW,
        file_path=Path("utils.py"),
        line=15,
        code_snippet="def some_very_long_function_name_with_many_parameters(parameter_one, parameter_two, parameter_three, parameter_four):",
        confidence=0.9,
        metadata={"pattern": "line-too-long", "language": "python"},
    )

    medium_finding = Finding(
        rule_id="maintainability-nested-too-deep",
        message="代码嵌套超过 3 层，建议重构",
        severity=Severity.MEDIUM,
        file_path=Path("handlers.py"),
        line=34,
        code_snippet="if x:\n    if y:\n        if z:\n            if w:",
        confidence=0.85,
        metadata={"pattern": "nested-code", "language": "python"},
    )

    # 创建扫描结果
    security_result = ScanResult(
        scanner_name="SecurityAgent",
        findings=[security_finding],
        scanned_files=25,
        duration_ms=500,
    )

    logic_result = ScanResult(
        scanner_name="LogicAgent",
        findings=[logic_finding],
        scanned_files=25,
        duration_ms=300,
    )

    style_result = ScanResult(
        scanner_name="StyleAgent",
        findings=[style_finding, medium_finding],
        scanned_files=25,
        duration_ms=200,
    )

    return [security_result, logic_result, style_result]


def create_sarif_report(scan_results: list[ScanResult], output_path: Path) -> None:
    """创建 SARIF 格式报告."""

    # 收集所有发现
    all_findings: list[Finding] = []
    for result in scan_results:
        all_findings.extend(result.findings)

    # 构建 SARIF 结构
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "GitConsistency",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/sk1ua/GitConsistency",
                        "rules": []
                    }
                },
                "results": [],
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "endTimeUtc": datetime.now().isoformat() + "Z"
                    }
                ]
            }
        ]
    }

    # 添加规则和结果
    rule_ids = set()
    for finding in all_findings:
        # 添加规则
        if finding.rule_id not in rule_ids:
            rule_ids.add(finding.rule_id)
            sarif["runs"][0]["tool"]["driver"]["rules"].append({
                "id": finding.rule_id,
                "shortDescription": {"text": finding.message[:100]},
                "fullDescription": {"text": finding.message},
                "defaultConfiguration": {
                    "level": finding.severity.value
                }
            })

        # 添加结果
        result = {
            "ruleId": finding.rule_id,
            "message": {"text": finding.message},
            "level": finding.severity.value,
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": str(finding.file_path)
                        },
                        "region": {
                            "startLine": finding.line or 1,
                            "snippet": {"text": finding.code_snippet or ""}
                        }
                    }
                }
            ]
        }
        sarif["runs"][0]["results"].append(result)

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sarif, f, indent=2, ensure_ascii=False)

    print(f"  SARIF 报告已生成: {output_path}")


def create_html_report(markdown_content: str, output_path: Path) -> None:
    """创建 HTML 格式报告."""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>GitConsistency Code Health Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        pre {{ background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        code {{
            background: #f1f2f6;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
        }}
        li {{ margin: 5px 0; }}
        .severity-critical {{ color: #e74c3c; }}
        .severity-high {{ color: #e67e22; }}
        .severity-medium {{ color: #f39c12; }}
        .severity-low {{ color: #27ae60; }}
        .severity-info {{ color: #3498db; }}
        details {{ margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; }}
        summary {{ cursor: pointer; font-weight: bold; }}
        summary:hover {{ color: #3498db; }}
    </style>
</head>
<body>
{markdown_to_html(markdown_content)}
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  HTML 报告已生成: {output_path}")


def markdown_to_html(markdown: str) -> str:
    """简单的 Markdown 转 HTML."""
    import re

    html = markdown

    # 标题
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)

    # 粗体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

    # 代码块
    html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)

    # 行内代码
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # 段落
    paragraphs = html.split('\n\n')
    result = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith('<') and not p.startswith('🔴') and not p.startswith('🟠'):
            p = f'<p>{p}</p>'
        result.append(p)
    html = '\n\n'.join(result)

    return html


async def main() -> int:
    """主函数."""
    import sys
    import io

    # 修复 Windows 终端编码问题
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("=" * 60)
    print("GitConsistency 严格提示词系统测试")
    print("=" * 60)

    # 创建输出目录
    temp_dir = Path(__file__).parent.parent / "temp"
    temp_dir.mkdir(exist_ok=True)

    # 创建模拟数据
    print("\n1. 创建模拟扫描结果...")
    scan_results = create_mock_findings()
    total_findings = sum(len(r.findings) for r in scan_results)
    print(f"   共创建 {len(scan_results)} 个扫描结果，{total_findings} 个问题")

    # 生成 SARIF 报告
    print("\n2. 生成 SARIF 报告...")
    sarif_path = temp_dir / "report.sarif.json"
    create_sarif_report(scan_results, sarif_path)

    # 生成 Markdown 报告（使用 LLM 生成器）
    print("\n3. 生成 Markdown 报告（使用严格提示词系统）...")
    print("   注意: 如果没有配置 LLM API，将使用备用报告格式")

    try:
        generator = LLMReportGenerator()
        markdown_content = await generator.generate(
            scan_results=scan_results,
            project_name="GitConsistency-Test",
            commit_sha="abc1234",
            duration=15.5,
        )

        md_path = temp_dir / "report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"   Markdown 报告已生成: {md_path}")

    except Exception as e:
        print(f"   LLM 生成失败，使用备用格式: {e}")
        # 使用备用报告
        generator = LLMReportGenerator()
        findings_data = generator._prepare_findings_data(scan_results)
        markdown_content = generator._fallback_report(
            findings_data, "GitConsistency-Test", "abc1234", 15.5
        )
        md_path = temp_dir / "report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"   Markdown 报告已生成: {md_path}")

    # 生成 HTML 报告
    print("\n4. 生成 HTML 报告...")
    html_path = temp_dir / "report.html"
    create_html_report(markdown_content, html_path)

    # 生成 GitHub Actions Summary
    print("\n5. 生成 GitHub Actions Summary...")
    try:
        generator = LLMReportGenerator()
        actions_summary = await generator.generate_actions_summary(
            scan_results=scan_results,
            project_name="GitConsistency-Test",
            duration_ms=15500,
        )
        actions_path = temp_dir / "actions-summary.md"
        with open(actions_path, "w", encoding="utf-8") as f:
            f.write(actions_summary)
        print(f"   Actions Summary 已生成: {actions_path}")
    except Exception as e:
        print(f"   生成失败: {e}")
        actions_path = temp_dir / "actions-summary.md"
        with open(actions_path, "w", encoding="utf-8") as f:
            f.write("# Actions Summary\n\n生成失败，请检查 LLM 配置。\n")
        print(f"   Actions Summary 已生成（备用）: {actions_path}")

    # 打印报告预览
    print("\n" + "=" * 60)
    print("报告预览 (Markdown 前 1500 字符)")
    print("=" * 60)
    print(markdown_content[:1500])
    print("\n... (内容已截断)")

    print("\n" + "=" * 60)
    print(f"所有报告已保存到: {temp_dir}")
    print("=" * 60)
    print("\n文件列表:")
    for f in temp_dir.iterdir():
        size = f.stat().st_size
        print(f"  - {f.name} ({size} bytes)")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
