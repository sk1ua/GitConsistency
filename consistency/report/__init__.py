"""报告生成模块.

生成 Markdown、HTML、JSON 等格式的分析报告.
"""

from consistency.report.generator import ReportGenerator
from consistency.report.templates import ReportFormat, ReportTheme

__all__ = [
    "ReportFormat",
    "ReportGenerator",
    "ReportTheme",
]
