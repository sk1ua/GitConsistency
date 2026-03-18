"""一致性漂移检测器.

基于代码图谱统计和 embedding 相似度计算，
检测命名风格、函数签名、异常处理等模式的一致性漂移.
"""

from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from consistancy.scanners.base import BaseScanner, Finding, ScanResult, Severity

logger = logging.getLogger(__name__)


@dataclass
class StylePattern:
    """代码风格模式."""

    pattern_type: str  # naming, error_handling, signature, etc.
    examples: list[str]
    frequency: float
    embedding: np.ndarray | None = None


@dataclass
class DriftResult:
    """漂移检测结果."""

    file_path: str
    line: int
    pattern_type: str
    observed: str
    expected: str
    confidence: float  # 0-1
    z_score: float


class DriftDetector(BaseScanner):
    """一致性漂移检测器.

    通过分析代码库中的历史模式，检测新代码是否偏离既有规范.
    支持命名风格、函数签名、异常处理、导入风格等维度.

    Examples:
        >>> detector = DriftDetector(
        ...     threshold=0.75,
        ...     zscore_threshold=2.0,
        ... )
        >>> result = await detector.scan(Path("./my-project"))
    """

    PATTERN_TYPES = [
        "naming_convention",      # snake_case vs camelCase vs PascalCase
        "function_signature",     # 参数风格、返回值注解
        "error_handling",         # try/except vs if/else
        "import_style",           # import x vs from x import y
        "docstring_format",       # Google vs NumPy vs reST
        "type_annotation",        # typing 使用习惯
    ]

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        threshold: float = 0.75,
        zscore_threshold: float = 2.0,
        gitnexus_client: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """初始化漂移检测器.

        Args:
            embedding_model: sentence-transformers 模型名称
            threshold: embedding 相似度阈值（低于此值视为漂移）
            zscore_threshold: 统计偏离 Z-score 阈值
            gitnexus_client: GitNexus MCP 客户端
            config: 额外配置
        """
        super().__init__(config)
        self.embedding_model_name = embedding_model
        self.threshold = threshold
        self.zscore_threshold = zscore_threshold
        self.gitnexus_client = gitnexus_client
        self._embedding_model: Any | None = None

    @property
    def name(self) -> str:
        return "drift"

    async def scan(self, path: Path) -> ScanResult:
        """执行一致性漂移检测.

        Args:
            path: 扫描目标路径

        Returns:
            扫描结果
        """
        logger.info(f"开始漂移检测: {path}")

        findings: list[Finding] = []
        scanned_files = 0

        try:
            # 1. 获取或构建代码图谱
            if self.gitnexus_client:
                graph = await self.gitnexus_client.analyze(str(path))
                logger.debug(f"图谱分析完成: {graph.node_count} 节点")
            else:
                # 无 GitNexus 时使用本地分析
                graph = None

            # 2. 提取历史模式
            patterns = await self._extract_patterns(path, graph)
            logger.debug(f"提取到 {len(patterns)} 种模式")

            # 3. 检测当前文件的漂移
            drift_results = await self._detect_drifts(path, patterns)
            logger.debug(f"检测到 {len(drift_results)} 处漂移")

            # 4. 转换为 Finding
            for drift in drift_results:
                finding = self._drift_to_finding(drift)
                findings.append(finding)

            scanned_files = sum(1 for f in path.rglob("*.py") if f.is_file())

        except Exception as e:
            logger.error(f"漂移检测失败: {e}")
            return ScanResult(
                scanner_name=self.name,
                findings=[],
                scanned_files=0,
                errors=[str(e)],
            )

        logger.info(f"漂移检测完成: {len(findings)} 个问题")

        return ScanResult(
            scanner_name=self.name,
            findings=findings,
            scanned_files=scanned_files,
            errors=[],
        )

    async def _extract_patterns(
        self,
        path: Path,
        graph: Any | None,
    ) -> dict[str, StylePattern]:
        """从历史代码中提取风格模式."""
        patterns: dict[str, StylePattern] = {}

        # 命名风格分析
        naming_patterns = self._analyze_naming_conventions(path)
        if naming_patterns:
            patterns["naming_convention"] = naming_patterns

        # 函数签名分析
        signature_patterns = self._analyze_function_signatures(path)
        if signature_patterns:
            patterns["function_signature"] = signature_patterns

        # 异常处理风格
        error_patterns = self._analyze_error_handling(path)
        if error_patterns:
            patterns["error_handling"] = error_patterns

        # 导入风格
        import_patterns = self._analyze_import_style(path)
        if import_patterns:
            patterns["import_style"] = import_patterns

        # 如果有 embedding 模型，计算 embedding
        await self._compute_embeddings(patterns)

        return patterns

    def _analyze_naming_conventions(self, path: Path) -> StylePattern | None:
        """分析命名约定."""
        snake_case_count = 0
        camel_case_count = 0
        pascal_case_count = 0
        total = 0

        snake_pattern = re.compile(r'^[a-z_][a-z0-9_]*$')
        camel_pattern = re.compile(r'^[a-z][a-zA-Z0-9]*$')
        pascal_pattern = re.compile(r'^[A-Z][a-zA-Z0-9]*$')

        for py_file in path.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    # 简单统计（实际应该解析 AST）
                    for match in re.finditer(r'def\s+(\w+)', content):
                        name = match.group(1)
                        total += 1
                        if snake_pattern.match(name):
                            snake_case_count += 1
                        elif camel_pattern.match(name) and '_' not in name:
                            camel_case_count += 1
                        elif pascal_pattern.match(name):
                            pascal_case_count += 1
                except Exception:
                    continue

        if total == 0:
            return None

        # 确定主导风格
        counts = [
            ("snake_case", snake_case_count),
            ("camelCase", camel_case_count),
            ("PascalCase", pascal_case_count),
        ]
        dominant = max(counts, key=lambda x: x[1])

        return StylePattern(
            pattern_type="naming_convention",
            examples=[dominant[0]],
            frequency=dominant[1] / total if total > 0 else 0,
        )

    def _analyze_function_signatures(self, path: Path) -> StylePattern | None:
        """分析函数签名风格."""
        typed_count = 0
        untyped_count = 0

        for py_file in path.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    # 检查类型注解
                    func_defs = re.findall(r'def\s+\w+\s*\([^)]*\)\s*(->\s*\w+)?\s*:', content)
                    for match in func_defs:
                        if match:  # 有返回类型注解
                            typed_count += 1
                        else:
                            untyped_count += 1
                except Exception:
                    continue

        total = typed_count + untyped_count
        if total == 0:
            return None

        if typed_count / total > 0.5:
            return StylePattern(
                pattern_type="function_signature",
                examples=["typed"],
                frequency=typed_count / total,
            )
        else:
            return StylePattern(
                pattern_type="function_signature",
                examples=["untyped"],
                frequency=untyped_count / total,
            )

    def _analyze_error_handling(self, path: Path) -> StylePattern | None:
        """分析异常处理风格."""
        try_except_count = 0
        error_value_count = 0

        for py_file in path.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    try_except_count += len(re.findall(r'\btry\s*:', content))
                    # 简单判断返回值错误处理
                    error_value_count += len(re.findall(r'return\s+(None|False|Error)', content))
                except Exception:
                    continue

        total = try_except_count + error_value_count
        if total == 0:
            return None

        if try_except_count > error_value_count:
            return StylePattern(
                pattern_type="error_handling",
                examples=["try_except"],
                frequency=try_except_count / total,
            )
        else:
            return StylePattern(
                pattern_type="error_handling",
                examples=["error_values"],
                frequency=error_value_count / total,
            )

    def _analyze_import_style(self, path: Path) -> StylePattern | None:
        """分析导入风格."""
        import_module = 0
        from_import = 0

        for py_file in path.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    import_module += len(re.findall(r'^import\s+\w+', content, re.MULTILINE))
                    from_import += len(re.findall(r'^from\s+\w+', content, re.MULTILINE))
                except Exception:
                    continue

        total = import_module + from_import
        if total == 0:
            return None

        if import_module > from_import:
            return StylePattern(
                pattern_type="import_style",
                examples=["import_module"],
                frequency=import_module / total,
            )
        else:
            return StylePattern(
                pattern_type="import_style",
                examples=["from_import"],
                frequency=from_import / total,
            )

    async def _compute_embeddings(self, patterns: dict[str, StylePattern]) -> None:
        """计算模式 embedding（可选，需要 sentence-transformers）."""
        try:
            if self._embedding_model is None:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer(self.embedding_model_name)

            for pattern in patterns.values():
                text = f"{pattern.pattern_type}: {', '.join(pattern.examples)}"
                pattern.embedding = self._embedding_model.encode([text])[0]

        except ImportError:
            logger.debug("sentence-transformers 未安装，跳过 embedding 计算")
        except Exception as e:
            logger.debug(f"embedding 计算失败: {e}")

    async def _detect_drifts(
        self,
        path: Path,
        patterns: dict[str, StylePattern],
    ) -> list[DriftResult]:
        """检测当前代码的漂移."""
        drifts: list[DriftResult] = []

        # 如果没有历史模式，无法检测漂移
        if not patterns:
            return drifts

        # 遍历 Python 文件
        for py_file in path.rglob("*.py"):
            if not py_file.is_file():
                continue

            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')

                # 检测命名风格漂移
                if "naming_convention" in patterns:
                    drifts.extend(self._check_naming_drift(
                        py_file, lines, patterns["naming_convention"],
                    ))

                # 检测函数签名漂移
                if "function_signature" in patterns:
                    drifts.extend(self._check_signature_drift(
                        py_file, lines, patterns["function_signature"],
                    ))

                # 检测异常处理漂移
                if "error_handling" in patterns:
                    drifts.extend(self._check_error_handling_drift(
                        py_file, lines, patterns["error_handling"],
                    ))

            except Exception as e:
                logger.debug(f"分析文件失败 {py_file}: {e}")
                continue

        return drifts

    def _check_naming_drift(
        self,
        file_path: Path,
        lines: list[str],
        pattern: StylePattern,
    ) -> list[DriftResult]:
        """检查命名风格漂移."""
        drifts: list[DriftResult] = []
        expected_style = pattern.examples[0] if pattern.examples else "snake_case"

        for i, line in enumerate(lines, 1):
            # 查找函数定义
            match = re.search(r'def\s+(\w+)', line)
            if match:
                name = match.group(1)
                actual_style = self._classify_naming_style(name)

                if actual_style != expected_style and actual_style != "unknown":
                    # 计算置信度（基于频率）
                    confidence = pattern.frequency
                    z_score = self._calculate_z_score(
                        pattern.frequency,
                        confidence,
                    )

                    if confidence < self.threshold or abs(z_score) > self.zscore_threshold:
                        drifts.append(DriftResult(
                            file_path=str(file_path),
                            line=i,
                            pattern_type="naming_convention",
                            observed=actual_style,
                            expected=expected_style,
                            confidence=1 - confidence,
                            z_score=z_score,
                        ))

        return drifts

    def _check_signature_drift(
        self,
        file_path: Path,
        lines: list[str],
        pattern: StylePattern,
    ) -> list[DriftResult]:
        """检查函数签名漂移."""
        drifts: list[DriftResult] = []
        expected_style = pattern.examples[0] if pattern.examples else "untyped"

        for i, line in enumerate(lines, 1):
            if not line.strip().startswith('def '):
                continue

            has_types = '->' in line or ':' in line.split(')')[0] if ')' in line else False
            actual_style = "typed" if has_types else "untyped"

            if actual_style != expected_style:
                confidence = 0.5
                z_score = self._calculate_z_score(pattern.frequency, 0.5)

                if confidence < self.threshold or abs(z_score) > self.zscore_threshold:
                    drifts.append(DriftResult(
                        file_path=str(file_path),
                        line=i,
                        pattern_type="function_signature",
                        observed=actual_style,
                        expected=expected_style,
                        confidence=1 - confidence,
                        z_score=z_score,
                    ))

        return drifts

    def _check_error_handling_drift(
        self,
        file_path: Path,
        lines: list[str],
        pattern: StylePattern,
    ) -> list[DriftResult]:
        """检查异常处理风格漂移."""
        drifts: list[DriftResult] = []
        expected_style = pattern.examples[0] if pattern.examples else "try_except"

        for i, line in enumerate(lines, 1):
            # 简单的 try: 检测
            if re.match(r'\s*try\s*:', line) and expected_style == "error_values":
                confidence = 0.6
                z_score = self._calculate_z_score(pattern.frequency, 0.6)

                if confidence < self.threshold or abs(z_score) > self.zscore_threshold:
                    drifts.append(DriftResult(
                        file_path=str(file_path),
                        line=i,
                        pattern_type="error_handling",
                        observed="try_except",
                        expected=expected_style,
                        confidence=1 - confidence,
                        z_score=z_score,
                    ))

        return drifts

    def _classify_naming_style(self, name: str) -> str:
        """分类命名风格."""
        if '_' in name and name.islower():
            return "snake_case"
        elif name[0].islower() and any(c.isupper() for c in name):
            return "camelCase"
        elif name[0].isupper():
            return "PascalCase"
        return "unknown"

    def _calculate_z_score(self, mean: float, observed: float, std_dev: float = 0.2) -> float:
        """计算 Z-score."""
        if std_dev == 0:
            return 0
        return (observed - mean) / std_dev

    def _drift_to_finding(self, drift: DriftResult) -> Finding:
        """将漂移结果转换为 Finding."""
        # 根据置信度确定严重程度
        if drift.confidence > 0.9:
            severity = Severity.HIGH
        elif drift.confidence > 0.7:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        return Finding(
            rule_id=f"drift_{drift.pattern_type}",
            message=f"{self._get_pattern_description(drift.pattern_type)} "
                    f"漂移: 观察到 '{drift.observed}', 期望 '{drift.expected}'",
            severity=severity,
            file_path=Path(drift.file_path),
            line=drift.line,
            confidence=drift.confidence,
            metadata={
                "pattern_type": drift.pattern_type,
                "observed": drift.observed,
                "expected": drift.expected,
                "z_score": drift.z_score,
                "drift_detected": True,
            },
        )

    def _get_pattern_description(self, pattern_type: str) -> str:
        """获取模式描述."""
        descriptions = {
            "naming_convention": "命名风格不一致",
            "function_signature": "函数签名风格不一致",
            "error_handling": "异常处理风格不一致",
            "import_style": "导入风格不一致",
            "docstring_format": "文档字符串格式不一致",
            "type_annotation": "类型注解风格不一致",
        }
        return descriptions.get(pattern_type, pattern_type)
