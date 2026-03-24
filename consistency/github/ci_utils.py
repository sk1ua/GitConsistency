"""CI 集成工具.

提供 GitHub Actions 集成功能，包括：
- Actions Summary 输出
- PR Annotations（通过 workflow commands）
- GitHub Checks API 集成
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from consistency.scanners.base import Finding, ScanResult, Severity

logger = logging.getLogger(__name__)


def write_actions_summary(summary: str) -> None:
    """写入 GitHub Actions Job Summary。

    通过写入 GITHUB_STEP_SUMMARY 环境变量指定的文件，
    在 GitHub Actions 界面显示 Job Summary。

    Args:
        summary: Markdown 格式的摘要内容
    """
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        logger.debug("GITHUB_STEP_SUMMARY 未设置，跳过摘要写入")
        return

    try:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(summary)
            f.write("\n")
        logger.info("已写入 Actions Summary")
    except OSError as e:
        logger.warning(f"写入 Actions Summary 失败: {e}")


def write_workflow_annotation(
    level: str,
    message: str,
    file: str | None = None,
    line: int | None = None,
    title: str | None = None,
) -> None:
    """输出 GitHub Actions workflow command 注解。

    通过 stdout 输出特殊格式的 workflow command，
    GitHub Actions 会解析并在 PR 界面显示行级注解。

    Args:
        level: 级别（error, warning, notice）
        message: 消息内容
        file: 文件路径（可选）
        line: 行号（可选）
        title: 标题（可选）
    """
    # 构建参数
    params: list[str] = []
    if file:
        params.append(f"file={file}")
    if line and line > 0:
        params.append(f"line={line}")
    if title:
        # 转义特殊字符
        safe_title = title.replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")
        params.append(f"title={safe_title}")

    # 转义消息中的特殊字符
    safe_message = message.replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")

    # 构建命令
    if params:
        cmd = f"::{level} {','.join(params)}::{safe_message}"
    else:
        cmd = f"::{level}::{safe_message}"

    print(cmd)


def write_annotations_from_findings(
    findings: list[Finding],
    max_errors: int = 10,
    max_warnings: int = 10,
) -> int:
    """从发现的问题批量输出 workflow annotations。

    Args:
        findings: 发现问题列表
        max_errors: 最大错误注解数
        max_warnings: 最大警告注解数

    Returns:
        输出的注解数量
    """
    error_count = 0
    warning_count = 0
    total_annotations = 0

    # 按严重级别排序
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 5))

    for finding in sorted_findings:
        # 确定级别和配额
        if finding.severity in (Severity.CRITICAL, Severity.HIGH):
            level = "error"
            if error_count >= max_errors:
                continue
            error_count += 1
        elif finding.severity == Severity.MEDIUM:
            level = "warning"
            if warning_count >= max_warnings:
                continue
            warning_count += 1
        else:
            level = "notice"

        # 构建消息
        message = finding.message
        if finding.code_snippet:
            message += f"\n\nCode:\n{finding.code_snippet[:200]}"

        # 输注解
        line_num = finding.line if finding.line and finding.line > 0 else None
        write_workflow_annotation(
            level=level,
            message=message,
            file=str(finding.file_path) if finding.file_path else None,
            line=line_num,
            title=finding.rule_id,
        )
        total_annotations += 1

    # 如果还有更多问题，添加汇总信息
    total_critical_high = sum(1 for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH))
    if total_critical_high > max_errors:
        write_workflow_annotation(
            level="notice",
            message=f"还有 {total_critical_high - max_errors} 个高/严重级别问题未显示，请查看详细报告",
            title="更多问题",
        )

    return total_annotations


def set_actions_output(name: str, value: str) -> None:
    """设置 GitHub Actions 输出变量。

    Args:
        name: 变量名
        value: 变量值
    """
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        logger.debug("GITHUB_OUTPUT 未设置，跳过输出变量")
        return

    try:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
        logger.debug(f"已设置输出变量: {name}={value}")
    except OSError as e:
        logger.warning(f"设置输出变量失败: {e}")


def set_actions_outputs_from_results(
    scan_results: list[ScanResult],
    duration_ms: float,
) -> dict[str, str]:
    """从扫描结果设置 Actions 输出变量。

    Args:
        scan_results: 扫描结果列表
        duration_ms: 扫描耗时

    Returns:
        设置的输出变量字典
    """
    # 统计问题
    all_findings: list[Finding] = []
    for result in scan_results:
        all_findings.extend(result.findings)

    severity_counts: dict[Severity, int] = dict.fromkeys(Severity, 0)
    for finding in all_findings:
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

    outputs = {
        "total_findings": str(len(all_findings)),
        "critical_count": str(severity_counts.get(Severity.CRITICAL, 0)),
        "high_count": str(severity_counts.get(Severity.HIGH, 0)),
        "medium_count": str(severity_counts.get(Severity.MEDIUM, 0)),
        "low_count": str(severity_counts.get(Severity.LOW, 0)),
        "duration_ms": str(int(duration_ms)),
        "has_issues": str(
            bool(severity_counts.get(Severity.CRITICAL, 0) + severity_counts.get(Severity.HIGH, 0))
        ).lower(),
    }

    for name, value in outputs.items():
        set_actions_output(name, value)

    return outputs


def is_github_actions() -> bool:
    """检查是否在 GitHub Actions 环境中运行。"""
    return os.environ.get("GITHUB_ACTIONS") == "true"


def get_workflow_context() -> dict[str, Any]:
    """获取 GitHub Actions 工作流上下文。

    Returns:
        包含环境信息的字典
    """
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event_data: dict[str, Any] = {}

    if event_path:
        try:
            with open(event_path, encoding="utf-8") as f:
                event_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.debug(f"读取 event payload 失败: {e}")

    return {
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
        "actor": os.environ.get("GITHUB_ACTOR"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "sha": os.environ.get("GITHUB_SHA"),
        "ref": os.environ.get("GITHUB_REF"),
        "head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "base_ref": os.environ.get("GITHUB_BASE_REF"),
        "event_data": event_data,
    }


def debug_print_context() -> None:
    """打印调试信息（仅在 debug 模式下）。"""
    if os.environ.get("CONSISTENCY_DEBUG") or os.environ.get("RUNNER_DEBUG"):
        context = get_workflow_context()
        logger.debug("GitHub Actions Context:")
        for key, value in context.items():
            if key != "event_data":  # 避免打印太多内容
                logger.debug(f"  {key}: {value}")
