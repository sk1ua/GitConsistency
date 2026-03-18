"""扫描器模块.

包含安全扫描、一致性漂移检测、技术债务热点分析三大扫描引擎，
以及扫描器协调器用于并行执行.
"""

from consistancy.scanners.base import BaseScanner, Finding, ScanResult, Severity
from consistancy.scanners.drift_detector import DriftDetector
from consistancy.scanners.hotspot_analyzer import HotspotAnalyzer
from consistancy.scanners.orchestrator import ScanReport, ScannerOrchestrator
from consistancy.scanners.security_scanner import SecurityScanner

__all__ = [
    # 基类
    "BaseScanner",
    "ScanResult",
    "Finding",
    "Severity",
    # 扫描器
    "SecurityScanner",
    "DriftDetector",
    "HotspotAnalyzer",
    # 协调器
    "ScannerOrchestrator",
    "ScanReport",
]
