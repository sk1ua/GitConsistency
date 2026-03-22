"""技术债务热点分析器.

计算圈复杂度（radon）× 变更频率（git log），
输出技术债务热点用于可视化.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from consistancy.scanners.base import BaseScanner, Finding, ScanResult, Severity

logger = logging.getLogger(__name__)


@dataclass
class ComplexityMetrics:
    """复杂度指标."""

    file_path: str
    cyclomatic_complexity: float
    maintainability_index: float
    loc: int = 0
    sloc: int = 0
    comments: int = 0


@dataclass
class ChangeFrequency:
    """变更频率."""

    file_path: str
    commit_count: int
    last_modified: datetime
    authors: set[str] = field(default_factory=set)
    churn_lines: int = 0  # 代码行变更量


@dataclass
class Hotspot:
    """技术债务热点."""

    file_path: str
    complexity: ComplexityMetrics
    frequency: ChangeFrequency
    hotspot_score: float  # 复杂度 × 频率的归一化分数
    risk_level: str  # low, medium, high, critical


class HotspotAnalyzer(BaseScanner):
    """技术债务热点分析器.

    结合代码复杂度（radon）和变更频率（git）识别高风险代码区域。
    热点 = 复杂 × 频繁变更，是最需要重构的目标。

    Examples:
        >>> analyzer = HotspotAnalyzer(
        ...     complexity_threshold="C",
        ...     lookback_days=90,
        ... )
        >>> result = await analyzer.scan(Path("./my-project"))
        >>> for finding in result.findings:
        ...     print(f"{finding.file_path}: {finding.metadata['hotspot_score']}")
    """

    # 复杂度等级阈值
    CC_THRESHOLDS = {
        "A": 5,    # 简单
        "B": 10,   # 中等
        "C": 20,   # 复杂
        "D": 30,   # 非常复杂
        "E": 40,   # 危险
        "F": 50,   # 不可维护
    }

    # 风险等级阈值
    RISK_THRESHOLDS = {
        "low": 10.0,
        "medium": 25.0,
        "high": 50.0,
        "critical": 100.0,
    }

    def __init__(
        self,
        complexity_threshold: str = "C",
        lookback_days: int = 90,
        config: dict[str, Any] | None = None,
    ) -> None:
        """初始化热点分析器.

        Args:
            complexity_threshold: 复杂度阈值（A-F），低于此等级视为问题
            lookback_days: 变更频率计算回溯天数
            config: 额外配置
        """
        super().__init__(config)
        self.complexity_threshold = complexity_threshold.upper()
        self.lookback_days = lookback_days
        self.max_cc = self.CC_THRESHOLDS.get(self.complexity_threshold, 20)

    @property
    def name(self) -> str:
        return "hotspot"

    async def scan(self, path: Path) -> ScanResult:
        """执行技术债务热点分析.

        Args:
            path: 扫描目标路径

        Returns:
            扫描结果
        """
        logger.info(f"开始热点分析: {path}")

        findings: list[Finding] = []
        errors: list[str] = []

        try:
            # 1. 计算代码复杂度
            complexity_map = await self._analyze_complexity(path)
            logger.debug(f"分析了 {len(complexity_map)} 个文件的复杂度")

            # 2. 计算变更频率
            frequency_map = await self._analyze_change_frequency(path)
            logger.debug(f"分析了 {len(frequency_map)} 个文件的变更频率")

            # 3. 计算热点分数
            hotspots = self._calculate_hotspots(complexity_map, frequency_map)
            logger.debug(f"识别了 {len(hotspots)} 个热点")

            # 4. 转换为 Finding
            for hotspot in hotspots:
                finding = self._hotspot_to_finding(hotspot)
                findings.append(finding)

            # 5. 按热点分数排序
            findings.sort(key=lambda f: f.metadata.get("hotspot_score", 0), reverse=True)

        except Exception as e:
            logger.error(f"热点分析失败: {e}")
            errors.append(str(e))

        scanned_files = len(complexity_map)
        logger.info(f"热点分析完成: {len(findings)} 个热点")

        return ScanResult(
            scanner_name=self.name,
            findings=findings,
            scanned_files=scanned_files,
            errors=errors,
        )

    async def _analyze_complexity(self, path: Path) -> dict[str, ComplexityMetrics]:
        """分析代码复杂度（使用 radon）."""
        complexity_map: dict[str, ComplexityMetrics] = {}

        try:
            # 使用 radon cc 命令获取圈复杂度
            cmd = [
                "radon", "cc",
                "-a",  # 平均
                "-j",  # JSON 输出
                str(path),
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                if err_msg:
                    logger.warning(f"radon stderr: {err_msg}")

            result = json.loads(stdout.decode())

            # 解析结果
            for file_path, blocks in result.items():
                if not isinstance(blocks, list):
                    continue

                total_cc = 0
                max_cc = 0
                for block in blocks:
                    cc = block.get("complexity", 0)
                    total_cc += cc
                    max_cc = max(max_cc, cc)

                # 计算文件级平均复杂度
                avg_cc = total_cc / len(blocks) if blocks else 0

                # 获取可维护性指数
                mi = await self._get_maintainability_index(file_path)

                complexity_map[file_path] = ComplexityMetrics(
                    file_path=file_path,
                    cyclomatic_complexity=avg_cc,
                    maintainability_index=mi,
                )

        except FileNotFoundError:
            logger.warning("radon 未安装，回退到基础分析")
            complexity_map = await self._analyze_complexity_basic(path)
        except json.JSONDecodeError as e:
            logger.warning(f"radon 输出解析失败: {e}")
            complexity_map = await self._analyze_complexity_basic(path)
        except Exception as e:
            logger.warning(f"radon 执行失败: {e}")
            complexity_map = await self._analyze_complexity_basic(path)

        return complexity_map

    async def _analyze_complexity_basic(self, path: Path) -> dict[str, ComplexityMetrics]:
        """基础复杂度分析（无需 radon）."""
        complexity_map: dict[str, ComplexityMetrics] = {}

        for py_file in path.rglob("*.py"):
            if not py_file.is_file():
                continue

            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')

                # 简单估算：if/while/for/except 数量
                complexity = 1  # 基础复杂度
                for line in lines:
                    stripped = line.strip()
                    if any(kw in stripped for kw in ['if ', 'elif ', 'while ', 'for ', 'except', 'with ']):
                        complexity += 1
                    if ' and ' in stripped or ' or ' in stripped:
                        complexity += stripped.count(' and ') + stripped.count(' or ')

                loc = len(lines)
                comments = sum(1 for line in lines if line.strip().startswith('#'))

                # 估算可维护性指数（简化版）
                mi = max(0, 171 - 5.2 * (complexity / 10) - 0.23 * loc - 16.2 * (comments / max(loc, 1)))

                complexity_map[str(py_file)] = ComplexityMetrics(
                    file_path=str(py_file),
                    cyclomatic_complexity=float(complexity),
                    maintainability_index=mi,
                    loc=loc,
                    comments=comments,
                )

            except Exception as e:
                logger.debug(f"分析文件失败 {py_file}: {e}")
                continue

        return complexity_map

    async def _get_maintainability_index(self, file_path: str) -> float:
        """获取文件可维护性指数."""
        try:
            cmd = ["radon", "mi", "-j", file_path]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()

            result: dict[str, Any] = json.loads(stdout.decode())
            mi_info: dict[str, Any] = result.get(file_path, {})
            mi_value = mi_info.get("mi", 50.0)
            return float(mi_value) if mi_value is not None else 50.0

        except Exception:
            return 50.0  # 默认值

    async def _analyze_change_frequency(self, path: Path) -> dict[str, ChangeFrequency]:
        """分析代码变更频率（使用 git log）."""
        frequency_map: dict[str, ChangeFrequency] = {}

        # 计算日期范围
        since_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")

        try:
            # 获取 git log 统计
            cmd = [
                "git", "-C", str(path),
                "log",
                f"--since={since_date}",
                "--pretty=format:%H|%an|%ad",
                "--date=iso",
                "--name-only",
                "--",
                "*.py",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                if err_msg:
                    logger.debug(f"git log 错误: {err_msg}")
                return frequency_map

            # 解析 git log 输出
            _commit = None  # commit hash not used in this context
            current_author = None
            current_date = None

            for line in stdout.decode().split('\n'):
                line = line.strip()
                if not line:
                    continue

                # 提交信息行
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        _ = parts[0]  # commit hash not used
                        current_author = parts[1]
                        current_date = datetime.fromisoformat(parts[2].replace(' ', 'T'))
                    continue

                # 文件路径行
                if line.endswith('.py'):
                    file_path = line
                    if file_path not in frequency_map:
                        frequency_map[file_path] = ChangeFrequency(
                            file_path=file_path,
                            commit_count=0,
                            last_modified=current_date or datetime.now(),
                        )

                    freq = frequency_map[file_path]
                    freq.commit_count += 1
                    freq.authors.add(current_author or "unknown")
                    if current_date and current_date > freq.last_modified:
                        freq.last_modified = current_date

            # 获取代码行变更量（churn）
            await self._enrich_churn_stats(path, frequency_map, since_date)

        except FileNotFoundError:
            logger.warning("git 不可用，跳过变更频率分析")
        except Exception as e:
            logger.warning(f"git log 分析失败: {e}")

        return frequency_map

    async def _enrich_churn_stats(
        self,
        path: Path,
        frequency_map: dict[str, ChangeFrequency],
        since_date: str,
    ) -> None:
        """丰富变更统计（代码行变更量）."""
        try:
            cmd = [
                "git", "-C", str(path),
                "log",
                f"--since={since_date}",
                "--pretty=format:",
                "--numstat",
                "--",
                "*.py",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()

            for line in stdout.decode().split('\n'):
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    added = int(parts[0]) if parts[0].isdigit() else 0
                    deleted = int(parts[1]) if parts[1].isdigit() else 0
                    file_path = parts[2]

                    if file_path in frequency_map:
                        frequency_map[file_path].churn_lines += added + deleted

        except Exception as e:
            logger.debug(f"churn 统计失败: {e}")

    def _calculate_hotspots(
        self,
        complexity_map: dict[str, ComplexityMetrics],
        frequency_map: dict[str, ChangeFrequency],
    ) -> list[Hotspot]:
        """计算热点分数."""
        hotspots: list[Hotspot] = []

        # 收集所有文件的复杂度和频率
        all_cc = [m.cyclomatic_complexity for m in complexity_map.values()]
        all_freq = [f.commit_count for f in frequency_map.values()]

        if not all_cc or not all_freq:
            return hotspots

        max_cc = max(all_cc) if all_cc else 1
        max_freq = max(all_freq) if all_freq else 1

        # 归一化因子
        cc_norm = max_cc if max_cc > 0 else 1
        freq_norm = max_freq if max_freq > 0 else 1

        # 遍历所有文件
        all_files = set(complexity_map.keys()) | set(frequency_map.keys())

        for file_path in all_files:
            complexity = complexity_map.get(file_path)
            frequency = frequency_map.get(file_path)

            if complexity is None:
                # 如果没有复杂度数据，使用默认值
                complexity = ComplexityMetrics(
                    file_path=file_path,
                    cyclomatic_complexity=5.0,
                    maintainability_index=50.0,
                )

            if frequency is None:
                # 如果没有频率数据，跳过
                continue

            # 计算归一化分数
            cc_score = complexity.cyclomatic_complexity / cc_norm
            freq_score = frequency.commit_count / freq_norm

            # 热点分数 = 复杂度 × 频率（加权）
            # 复杂度权重 60%，频率权重 40%
            hotspot_score = (cc_score * 0.6 + freq_score * 0.4) * 100

            # 根据 churn 调整分数
            if frequency.churn_lines > 0:
                churn_score = min(frequency.churn_lines / 1000, 1.0)  # 上限 1000 行
                hotspot_score = hotspot_score * (1 + churn_score * 0.5)

            # 确定风险等级
            risk_level = self._determine_risk_level(hotspot_score, complexity)

            # 只返回超过阈值的
            if complexity.cyclomatic_complexity >= self.max_cc or frequency.commit_count > 5:
                hotspots.append(Hotspot(
                    file_path=file_path,
                    complexity=complexity,
                    frequency=frequency,
                    hotspot_score=round(hotspot_score, 2),
                    risk_level=risk_level,
                ))

        # 按分数排序
        hotspots.sort(key=lambda h: h.hotspot_score, reverse=True)

        return hotspots

    def _determine_risk_level(self, score: float, complexity: ComplexityMetrics) -> str:
        """确定风险等级."""
        # 综合考虑热点分数和可维护性指数
        mi_penalty = 0
        if complexity.maintainability_index < 20:
            mi_penalty = 20
        elif complexity.maintainability_index < 50:
            mi_penalty = 10

        adjusted_score = score + mi_penalty

        if adjusted_score >= self.RISK_THRESHOLDS["critical"]:
            return "critical"
        elif adjusted_score >= self.RISK_THRESHOLDS["high"]:
            return "high"
        elif adjusted_score >= self.RISK_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"

    def _hotspot_to_finding(self, hotspot: Hotspot) -> Finding:
        """将热点转换为 Finding."""
        # 根据风险等级确定严重程度
        severity_map = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }
        severity = severity_map.get(hotspot.risk_level, Severity.MEDIUM)

        # 构建消息
        message = (
            f"技术债务热点: {hotspot.risk_level.upper()} 风险\n"
            f"  - 圈复杂度: {hotspot.complexity.cyclomatic_complexity:.1f}\n"
            f"  - {self.lookback_days}天内提交: {hotspot.frequency.commit_count}次\n"
            f"  - 参与开发者: {len(hotspot.frequency.authors)}人\n"
            f"  - 代码变更: {hotspot.frequency.churn_lines}行"
        )

        return Finding(
            rule_id=f"hotspot_{hotspot.risk_level}",
            message=message,
            severity=severity,
            file_path=Path(hotspot.file_path),
            line=1,
            confidence=min(hotspot.hotspot_score / 100, 0.99),
            metadata={
                "hotspot_score": hotspot.hotspot_score,
                "risk_level": hotspot.risk_level,
                "cyclomatic_complexity": hotspot.complexity.cyclomatic_complexity,
                "maintainability_index": hotspot.complexity.maintainability_index,
                "commit_count": hotspot.frequency.commit_count,
                "author_count": len(hotspot.frequency.authors),
                "churn_lines": hotspot.frequency.churn_lines,
                "authors": list(hotspot.frequency.authors),
            },
        )

    def get_hotspots_data(self, findings: list[Finding]) -> list[dict[str, Any]]:
        """获取热点数据（用于可视化）."""
        data = []
        for finding in findings:
            if finding.metadata.get("hotspot_score"):
                data.append({
                    "file": str(finding.file_path),
                    "complexity": finding.metadata.get("cyclomatic_complexity", 0),
                    "frequency": finding.metadata.get("commit_count", 0),
                    "score": finding.metadata.get("hotspot_score", 0),
                    "risk": finding.metadata.get("risk_level", "unknown"),
                })
        return data
