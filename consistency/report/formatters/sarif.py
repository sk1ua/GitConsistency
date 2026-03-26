"""SARIF 2.1.0 报告格式化器.

符合 SARIF (Static Analysis Results Interchange Format) 2.1.0 标准，
供 vibe coding agent 和其他自动化工具消费。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from consistency.report.formatters.base import BaseFormatter
from consistency.reviewer.models import ReviewResult
from consistency.scanners.base import Finding, ScanResult, Severity


class SARIFFormatter(BaseFormatter):
    """SARIF 2.1.0 格式化器.

    生成符合 SARIF 标准的 JSON 报告，包含以下关键字段:
    - $schema: SARIF schema URI
    - version: "2.1.0"
    - runs[].tool.driver: 工具信息（GitConsistency）
    - runs[].results: 扫描结果
    - runs[].resources.rules: 规则定义
    """

    # SARIF severity 映射
    SEVERITY_MAP: dict[Severity, str] = {
        Severity.CRITICAL: "error",
        Severity.HIGH: "error",
        Severity.MEDIUM: "warning",
        Severity.LOW: "note",
        Severity.INFO: "note",
    }

    def __init__(self, **kwargs: Any) -> None:
        """初始化 SARIF 格式化器."""
        super().__init__(**kwargs)
        self._rule_index_map: dict[str, int] = {}

    def generate(
        self,
        scan_results: list[ScanResult],
        ai_review: ReviewResult | None,
        project_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成 SARIF 2.1.0 报告.

        Args:
            scan_results: 扫描结果列表
            ai_review: AI 审查结果（可选，SARIF 主要关注安全扫描结果）
            project_name: 项目名称
            **kwargs: 额外参数
                - commit_sha: Git commit SHA
                - repository_uri: 仓库 URI

        Returns:
            SARIF 格式的字典
        """
        all_findings = self._collect_findings(scan_results)

        # 构建 rules 和 results
        rules = self._build_rules(all_findings)
        results = self._build_results(all_findings)

        # 构建 SARIF 文档
        sarif_doc: dict[str, Any] = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "GitConsistency",
                            "version": self.version,
                            "informationUri": "https://github.com/gitconsistency/gitconsistency",
                            "rules": rules,
                        }
                    },
                    "invocations": [
                        {
                            "executionSuccessful": True,
                            "startTimeUtc": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                    "versionControlProvenance": [
                        {
                            "repositoryUri": kwargs.get("repository_uri", ""),
                            "revisionId": kwargs.get("commit_sha", ""),
                        }
                    ],
                    "results": results,
                }
            ],
        }

        # 添加属性包（扩展信息）
        sarif_doc["runs"][0]["properties"] = {
            "projectName": project_name,
            "scannerCount": len(scan_results),
            "totalFindings": len(all_findings),
        }

        return sarif_doc

    def _build_rules(self, findings: list[Finding]) -> list[dict[str, Any]]:
        """构建 SARIF rules 列表.

        每个唯一的 rule_id 对应一个 rule 定义。
        """
        rules: list[dict[str, Any]] = []
        seen_rules: set[str] = set()

        for finding in findings:
            if finding.rule_id in seen_rules:
                continue

            seen_rules.add(finding.rule_id)
            self._rule_index_map[finding.rule_id] = len(rules)

            rule: dict[str, Any] = {
                "id": finding.rule_id,
                "name": finding.rule_id,
                "shortDescription": {"text": finding.message[:100]},
                "defaultConfiguration": {
                    "level": self.SEVERITY_MAP.get(finding.severity, "warning"),
                },
            }

            # 添加元数据
            if finding.metadata:
                if "cwe" in finding.metadata:
                    rule["relationships"] = [
                        {
                            "target": {
                                "id": f"CWE-{finding.metadata['cwe']}",
                                "toolComponent": {
                                    "name": "CWE",
                                    "index": 0,
                                },
                            },
                            "kinds": ["relevant"],
                        }
                    ]
                if "owasp" in finding.metadata:
                    rule["properties"] = {"owasp": finding.metadata["owasp"]}

            rules.append(rule)

        return rules

    def _build_results(self, findings: list[Finding]) -> list[dict[str, Any]]:
        """构建 SARIF results 列表."""
        results: list[dict[str, Any]] = []

        for finding in findings:
            result: dict[str, Any] = {
                "ruleId": finding.rule_id,
                "level": self.SEVERITY_MAP.get(finding.severity, "warning"),
                "message": {"text": finding.message},
            }

            # 添加位置信息
            if finding.file_path:
                location: dict[str, Any] = {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": str(finding.file_path).replace("\\", "/"),
                        }
                    }
                }

                # 添加行列信息
                if finding.line:
                    location["physicalLocation"]["region"] = {
                        "startLine": finding.line,
                    }
                    if finding.column:
                        location["physicalLocation"]["region"]["startColumn"] = finding.column

                # 添加代码片段
                if finding.code_snippet:
                    location["physicalLocation"]["region"]["snippet"] = {"text": finding.code_snippet}

                result["locations"] = [location]

            # 添加指纹（用于去重）
            fingerprint = self._generate_fingerprint(finding)
            result["partialFingerprints"] = {"primaryLocationLineHash": fingerprint}

            # 添加置信度
            if finding.confidence < 1.0:
                result["properties"] = {"confidence": finding.confidence}

            results.append(result)

        return results

    def _generate_fingerprint(self, finding: Finding) -> str:
        """生成问题指纹（用于去重）."""
        content = f"{finding.rule_id}:{finding.file_path}:{finding.line}:{finding.message[:50]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def save(
        self,
        report: dict[str, Any],
        output_path: Path,
    ) -> Path:
        """保存 SARIF 报告到文件.

        Args:
            report: SARIF 格式的报告字典
            output_path: 输出路径

        Returns:
            实际保存的路径
        """
        import json

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # SARIF 使用标准 JSON 格式
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return output_path
