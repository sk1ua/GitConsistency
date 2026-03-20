"""Streamlit Dashboard 应用.

交互式 Web 界面，展示代码健康指标和趋势图表.
"""
# ruff: noqa: E402  # 需要先修改 sys.path 才能导入本地模块

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

from consistancy.dashboard.components import Components
from consistancy.dashboard.data_manager import DataManager
from consistancy.report.generator import ReportGenerator
from consistancy.report.templates import ReportFormat
from consistancy.scanners.orchestrator import ScannerOrchestrator


async def run_scan(
    project_path: str,
    config: dict[str, bool],
) -> dict:
    """运行扫描.

    Args:
        project_path: 项目路径
        config: 扫描配置

    Returns:
        扫描结果
    """
    orchestrator = ScannerOrchestrator()
    orchestrator.create_default_scanners()

    # 确定要跳过的扫描器
    skip_scanners = []
    if not config.get("enable_security"):
        skip_scanners.append("security")
    if not config.get("enable_drift"):
        skip_scanners.append("drift")
    if not config.get("enable_hotspot"):
        skip_scanners.append("hotspot")

    # 运行扫描
    report = await orchestrator.scan(
        Path(project_path),
        skip_scanners=skip_scanners,
    )

    # AI 审查
    ai_review = None
    if config.get("enable_ai"):
        try:
            from consistancy.reviewer import AIReviewer, ReviewContext

            reviewer = AIReviewer(model=config.get("ai_model", "deepseek/deepseek-chat"))

            # 构建上下文
            context = ReviewContext(
                diff="",  # TODO: 获取实际 diff
                files_changed=[str(f) for f in report.results.keys()],
            )

            ai_review_result = await reviewer.review(context)
            ai_review = {
                "summary": ai_review_result.summary,
                "severity": ai_review_result.severity.value,
                "comments": [
                    {
                        "file": c.file,
                        "line": c.line,
                        "message": c.message,
                        "suggestion": c.suggestion,
                        "category": c.category.value,
                    }
                    for c in ai_review_result.comments
                ],
            }
        except Exception as e:
            st.warning(f"AI 审查失败: {e}")

    # 生成报告
    generator = ReportGenerator()
    scan_results = list(report.results.values())

    json_report = generator.generate(
        scan_results,
        ai_review=ai_review_result if ai_review else None,
        project_path=project_path,
        format=ReportFormat.JSON,
        duration_ms=report.duration_ms,
    )

    return {
        "report": json_report,
        "scan_results": scan_results,
        "ai_review": ai_review,
        "duration_ms": report.duration_ms,
    }


def render_overview(json_report: dict) -> None:
    """渲染概览页面."""
    st.header("📊 概览")

    summary = json_report.get("summary", {})
    severity_counts = summary.get("severity_counts", {})

    # 指标卡片
    Components.render_metrics({
        "critical": severity_counts.get("critical", 0),
        "high": severity_counts.get("high", 0),
        "medium": severity_counts.get("medium", 0),
        "low": severity_counts.get("low", 0),
        "files": summary.get("total_files", 0),
    })

    st.markdown("---")

    # 左右布局
    col1, col2 = st.columns(2)

    with col1:
        # 严重程度饼图
        all_findings = []
        for scanner in json_report.get("scanners", []):
            all_findings.extend(scanner.get("findings", []))

        Components.render_severity_chart(all_findings)

    with col2:
        # 扫描器统计
        st.subheader("扫描器结果")
        for scanner in json_report.get("scanners", []):
            name = scanner.get("name", "unknown")
            count = scanner.get("finding_count", 0)
            st.metric(f"{name.upper()}", f"{count} 个问题")


def render_security(json_report: dict) -> None:
    """渲染安全页面."""
    st.header("🔐 安全扫描")

    security_scanner = None
    for scanner in json_report.get("scanners", []):
        if scanner.get("name") == "security":
            security_scanner = scanner
            break

    if not security_scanner:
        st.info("未运行安全扫描")
        return

    findings = security_scanner.get("findings", [])

    if not findings:
        st.success("🎉 未发现安全问题！")
        return

    # 分类统计
    severity_counts = {}
    for f in findings:
        sev = f.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    cols = st.columns(4)
    for i, (sev, count) in enumerate(severity_counts.items()):
        with cols[i % 4]:
            st.metric(sev.upper(), count)

    # 问题列表
    Components.render_findings_table(findings, "安全漏洞")


def render_hotspots(json_report: dict) -> None:
    """渲染热点页面."""
    st.header("🔥 技术债务热点")

    hotspot_scanner = None
    for scanner in json_report.get("scanners", []):
        if scanner.get("name") == "hotspot":
            hotspot_scanner = scanner
            break

    if not hotspot_scanner:
        st.info("未运行热点分析")
        return

    findings = hotspot_scanner.get("findings", [])

    if not findings:
        st.success("🎉 未发现技术债务热点！")
        return

    # 准备热点数据
    hotspots = []
    for f in findings:
        meta = f.get("metadata", {})
        hotspots.append({
            "file": str(f.get("file", "-")),
            "complexity": meta.get("cyclomatic_complexity", 0),
            "frequency": meta.get("commit_count", 0),
            "score": meta.get("hotspot_score", 0),
            "risk": meta.get("risk_level", "unknown"),
        })

    # 散点图
    Components.render_hotspot_scatter(hotspots)

    # 热点列表
    st.subheader("热点文件列表")
    hotspots_sorted = sorted(hotspots, key=lambda x: x["score"], reverse=True)[:20]
    st.dataframe(hotspots_sorted, use_container_width=True)


def render_drift(json_report: dict) -> None:
    """渲染漂移页面."""
    st.header("🔄 一致性漂移")

    drift_scanner = None
    for scanner in json_report.get("scanners", []):
        if scanner.get("name") == "drift":
            drift_scanner = scanner
            break

    if not drift_scanner:
        st.info("未运行一致性检测")
        return

    findings = drift_scanner.get("findings", [])

    if not findings:
        st.success("🎉 未发现一致性漂移！")
        return

    # 准备漂移数据
    drifts = []
    for f in findings:
        meta = f.get("metadata", {})
        drifts.append({
            "file": str(f.get("file", "-")),
            "line": f.get("line", 0),
            "pattern": meta.get("pattern_type", "unknown"),
            "observed": meta.get("observed", "-"),
            "expected": meta.get("expected", "-"),
            "confidence": meta.get("confidence", 0),
        })

    # 时间线
    Components.render_drift_timeline(drifts)

    # 漂移列表
    Components.render_findings_table(findings, "一致性漂移")


def render_ai_review(json_report: dict) -> None:
    """渲染 AI 审查页面."""
    st.header("🤖 AI Code Review")

    ai_review = json_report.get("ai_review")
    Components.render_ai_review(ai_review)


def render_trends(data_manager: DataManager) -> None:
    """渲染趋势页面."""
    st.header("📈 历史趋势")

    trend_data = data_manager.get_trend_data(days=30)

    if not trend_data.get("dates"):
        st.info("暂无历史数据")
        return

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    # 创建子图
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("问题数量趋势", "扫描耗时趋势"),
        vertical_spacing=0.15,
    )

    # 问题数量
    fig.add_trace(
        go.Scatter(
            x=trend_data["dates"],
            y=trend_data["issues"],
            mode="lines+markers",
            name="问题数量",
            line=dict(color="#dc3545"),
        ),
        row=1, col=1,
    )

    # 扫描耗时
    fig.add_trace(
        go.Scatter(
            x=trend_data["dates"],
            y=trend_data["duration"],
            mode="lines+markers",
            name="扫描耗时 (s)",
            line=dict(color="#0366d6"),
        ),
        row=2, col=1,
    )

    fig.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    """Dashboard 主入口."""
    # 页面头部
    Components.render_header("ConsistenCy Dashboard")

    # 侧边栏配置
    config = Components.render_sidebar()

    # 数据管理器
    data_manager = DataManager()

    # 检查是否有最新数据
    latest_data = data_manager.load_latest()

    # 创建标签页
    tabs = st.tabs([
        "📊 概览",
        "🔐 安全",
        "🔥 热点",
        "🔄 漂移",
        "🤖 AI 审查",
        "📈 趋势",
    ])

    # 运行扫描
    if config["run_button"]:
        with Components.render_progress("正在分析代码..."):
            try:
                result = asyncio.run(run_scan(
                    config["project_path"],
                    config,
                ))

                # 保存数据
                data_manager.save_scan(
                    result["report"],
                    config["project_path"],
                    result["duration_ms"],
                )

                latest_data = result["report"]
                Components.render_success(f"分析完成！耗时 {result['duration_ms']:.2f}ms")

            except Exception as e:
                Components.render_error(str(e))
                import traceback
                st.error(traceback.format_exc())

    # 渲染各标签页
    if latest_data:
        with tabs[0]:
            render_overview(latest_data)

        with tabs[1]:
            render_security(latest_data)

        with tabs[2]:
            render_hotspots(latest_data)

        with tabs[3]:
            render_drift(latest_data)

        with tabs[4]:
            render_ai_review(latest_data)

        with tabs[5]:
            render_trends(data_manager)
    else:
        for tab in tabs:
            with tab:
                st.info("点击左侧「🚀 开始分析」按钮运行首次扫描")

    # 页脚
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'>"
        "Made with ❤️ by ConsistenCy Team | "
        "<a href='https://github.com/consistancy-team/consistancy'>GitHub</a>"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
