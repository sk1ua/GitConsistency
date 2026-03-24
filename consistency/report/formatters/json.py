"""JSON 报告格式化器."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from consistency.report.formatters.base import BaseFormatter
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import ScanResult, Severity


class JsonFormatter(BaseFormatter):
    """JSON 报告格式化器."""

    def generate(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None,
        project_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成 JSON 报告."""
        all_findings = self._collect_findings(scan_results)
        severity_counts = self._count_by_severity(all_findings)

        report = {
            "version": self.version,
            "scan_date": datetime.now().isoformat(),
            "project_name": project_name,
            "summary": {
                "total_issues": len(all_findings),
                "severity_counts": {k.value: v for k, v in severity_counts.items()},
                "duration_ms": kwargs.get("duration_ms", 0),
            },
            "scanners": [
                {
                    "name": r.scanner_name,
                    "scanned_files": r.scanned_files,
                    "finding_count": len(r.findings),
                    "error_count": len(r.errors),
                    "findings": [
                        {
                            "rule_id": f.rule_id,
                            "severity": f.severity.value,
                            "file": str(f.file_path) if f.file_path else None,
                            "line": f.line,
                            "message": f.message,
                            "confidence": f.confidence,
                        }
                        for f in r.findings
                    ],
                }
                for r in scan_results
            ],
        }

        if ai_review:
            report["ai_review"] = {
                "summary": ai_review.summary,
                "severity": ai_review.severity.value,
                "comment_count": len(ai_review.comments),
                "critical_count": ai_review.critical_count,
                "high_count": ai_review.high_count,
                "has_blocking_issues": ai_review.has_blocking_issues,
                "comments": [
                    {
                        "file": c.file,
                        "line": c.line,
                        "message": c.message,
                        "suggestion": c.suggestion,
                        "severity": c.severity.value,
                        "category": c.category.value,
                        "confidence": c.confidence,
                    }
                    for c in ai_review.comments
                ],
                "action_items": ai_review.action_items,
            }

        return report
