"""Streamlit Dashboard 模块.

交互式 Web 界面，展示代码健康指标和趋势图表.
"""

from consistancy.dashboard.components import Components
from consistancy.dashboard.data_manager import DataManager, ScanHistory

__all__ = [
    "Components",
    "DataManager",
    "ScanHistory",
]
