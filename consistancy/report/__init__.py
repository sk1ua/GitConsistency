"""报告生成模块.

生成 Markdown、HTML、JSON 等格式的分析报告.
"""

from consistancy.report.generator import ReportGenerator
from consistancy.report.templates import ReportFormat, ReportTheme

__all__ = [
    "ReportGenerator",
    "ReportFormat",
    "ReportTheme",
]
