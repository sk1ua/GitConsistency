"""Dashboard 组件.

可复用的 Streamlit 组件.
"""

from __future__ import annotations

from typing import Any

import streamlit as st



class Components:
    """Dashboard UI 组件."""

    @staticmethod
    def render_header(title: str = "ConsistenCy Dashboard") -> None:
        """渲染页面头部."""
        st.set_page_config(
            page_title=title,
            page_icon="🔍",
            layout="wide",
            initial_sidebar_state="expanded",
        )

        st.title(f"🔍 {title}")
        st.markdown("---")

    @staticmethod
    def render_sidebar() -> dict[str, Any]:
        """渲染侧边栏."""
        with st.sidebar:
            st.header("⚙️ 配置")

            # 项目选择
            project_path = st.text_input(
                "项目路径",
                value=".",
                help="要分析的代码仓库路径",
            )

            # 扫描器选择
            st.subheader("扫描器")
            enable_security = st.checkbox("安全扫描", value=True)
            enable_drift = st.checkbox("一致性检测", value=True)
            enable_hotspot = st.checkbox("热点分析", value=True)

            # AI 审查
            st.subheader("AI 审查")
            enable_ai = st.checkbox("启用 AI 审查", value=False)
            ai_model = st.selectbox(
                "AI 模型",
                ["deepseek/deepseek-chat", "anthropic/claude-3-sonnet", "openai/gpt-4"],
                disabled=not enable_ai,
            )

            # 运行按钮
            st.markdown("---")
            run_button = st.button("🚀 开始分析", type="primary", use_container_width=True)

        return {
            "project_path": project_path,
            "enable_security": enable_security,
            "enable_drift": enable_drift,
            "enable_hotspot": enable_hotspot,
            "enable_ai": enable_ai,
            "ai_model": ai_model,
            "run_button": run_button,
        }

    @staticmethod
    def render_metrics(summary: dict[str, Any]) -> None:
        """渲染指标卡片."""
        cols = st.columns(5)

        metrics = [
            ("🔴 Critical", summary.get("critical", 0), "#dc3545"),
            ("🟠 High", summary.get("high", 0), "#fd7e14"),
            ("🟡 Medium", summary.get("medium", 0), "#ffc107"),
            ("🟢 Low", summary.get("low", 0), "#28a745"),
            ("📁 Files", summary.get("files", 0), "#0366d6"),
        ]

        for col, (label, value, color) in zip(cols, metrics):
            with col:
                st.metric(label, value)

    @staticmethod
    def render_severity_chart(findings: list[dict[str, Any]]) -> None:
        """渲染严重程度饼图."""
        import plotly.express as px

        severity_counts: dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        if severity_counts:
            fig = px.pie(
                names=list(severity_counts.keys()),
                values=list(severity_counts.values()),
                title="问题严重程度分布",
                color=list(severity_counts.keys()),
                color_discrete_map={
                    "critical": "#dc3545",
                    "high": "#fd7e14",
                    "medium": "#ffc107",
                    "low": "#28a745",
                    "info": "#17a2b8",
                },
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")

    @staticmethod
    def render_findings_table(findings: list[dict[str, Any]], title: str = "发现的问题") -> None:
        """渲染问题表格."""
        if not findings:
            st.info(f"{title}: 未发现")
            return

        st.subheader(title)

        # 准备数据
        data = []
        for f in findings[:100]:  # 限制显示数量
            data.append({
                "严重程度": f.get("severity", "unknown").upper(),
                "规则": f.get("rule_id", "-"),
                "文件": f.get("file", "-"),
                "行号": f.get("line", "-"),
                "消息": f.get("message", "")[:100],
            })

        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
        )

    @staticmethod
    def render_ai_review(ai_review: dict[str, Any] | None) -> None:
        """渲染 AI 审查结果."""
        if not ai_review:
            st.info("AI 审查未启用")
            return

        st.subheader("🤖 AI Code Review")

        summary = ai_review.get("summary", "")
        severity = ai_review.get("severity", "low")
        comments = ai_review.get("comments", [])

        # 摘要
        st.markdown(f"**整体评估**: {summary}")
        st.markdown(f"**严重程度**: `{severity.upper()}`")

        # 评论列表
        if comments:
            for i, comment in enumerate(comments[:10]):
                title = f"💬 {comment.get('category', 'general').upper()}"
                msg = comment.get('message', '')[:50]
                with st.expander(f"{title} - {msg}..."):
                    st.markdown(f"**文件**: `{comment.get('file', '-')}`")
                    st.markdown(f"**行号**: {comment.get('line', '-')}")
                    st.markdown(f"**消息**: {comment.get('message', '')}")
                    if comment.get("suggestion"):
                        st.markdown(f"**建议**: {comment.get('suggestion')}")
        else:
            st.success("AI 未发现显著问题")

    @staticmethod
    def render_hotspot_scatter(hotspots: list[dict[str, Any]]) -> None:
        """渲染热点散点图."""
        import plotly.express as px

        if not hotspots:
            st.info("暂无热点数据")
            return

        # 准备数据
        data = []
        for h in hotspots:
            data.append({
                "文件": h.get("file", "-"),
                "复杂度": h.get("complexity", 0),
                "变更频率": h.get("frequency", 0),
                "热点分数": h.get("score", 0),
                "风险等级": h.get("risk", "unknown"),
            })

        fig = px.scatter(
            data,
            x="复杂度",
            y="变更频率",
            size="热点分数",
            color="风险等级",
            hover_data=["文件"],
            title="技术债务热点图 (复杂度 × 变更频率)",
            color_discrete_map={
                "critical": "#dc3545",
                "high": "#fd7e14",
                "medium": "#ffc107",
                "low": "#28a745",
            },
        )

        fig.update_layout(
            xaxis_title="圈复杂度",
            yaxis_title="90天内变更次数",
        )

        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def render_drift_timeline(drifts: list[dict[str, Any]]) -> None:
        """渲染漂移时间线."""
        import plotly.graph_objects as go

        if not drifts:
            st.info("暂无漂移数据")
            return

        # 按文件分组统计
        file_counts: dict[str, int] = {}
        for d in drifts:
            file = d.get("file", "unknown")
            file_counts[file] = file_counts.get(file, 0) + 1

        # 取前 10 个文件
        top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        fig = go.Figure(data=[
            go.Bar(
                x=[f[0] for f in top_files],
                y=[f[1] for f in top_files],
                marker_color="#ffc107",
            )
        ])

        fig.update_layout(
            title="漂移最多文件 (Top 10)",
            xaxis_title="文件",
            yaxis_title="漂移数量",
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def render_progress(message: str = "分析中...") -> Any:
        """渲染进度条."""
        return st.spinner(message)

    @staticmethod
    def render_error(message: str) -> None:
        """渲染错误信息."""
        st.error(f"❌ {message}")

    @staticmethod
    def render_success(message: str) -> None:
        """渲染成功信息."""
        st.success(f"✅ {message}")
