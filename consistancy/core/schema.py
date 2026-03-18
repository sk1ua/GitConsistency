"""GitNexus MCP 数据模型.

定义图谱、节点、边等核心数据结构.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class NodeType(Enum):
    """图谱节点类型."""

    FILE = auto()
    FUNCTION = auto()
    CLASS = auto()
    METHOD = auto()
    VARIABLE = auto()
    IMPORT = auto()
    MODULE = auto()


class EdgeType(Enum):
    """图谱边类型."""

    CALLS = auto()
    IMPORTS = auto()
    CONTAINS = auto()
    INHERITS = auto()
    USES = auto()
    DEFINES = auto()


@dataclass
class Location:
    """代码位置信息."""

    file_path: str
    line_start: int
    line_end: int = 0
    column_start: int = 0
    column_end: int = 0

    def __post_init__(self) -> None:
        if self.line_end == 0:
            self.line_end = self.line_start


@dataclass
class CodeNode:
    """代码图谱节点."""

    id: str
    name: str
    node_type: NodeType
    location: Location
    signature: str = ""
    docstring: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeEdge:
    """代码图谱边."""

    source: str
    target: str
    edge_type: EdgeType
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeGraph:
    """知识图谱."""

    repo_path: str
    version: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    nodes: list[CodeNode] = field(default_factory=list)
    edges: list[CodeEdge] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


@dataclass
class ContextResult:
    """上下文查询结果."""

    file_path: str
    symbols: list[dict[str, Any]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)


@dataclass
class ImpactResult:
    """影响分析结果."""

    symbol: str
    direct_impacts: list[str] = field(default_factory=list)
    indirect_impacts: list[str] = field(default_factory=list)
    test_coverage: list[str] = field(default_factory=list)


@dataclass
class ChangeDetection:
    """变更检测结果."""

    base_ref: str
    head_ref: str
    modified_files: list[str] = field(default_factory=list)
    added_symbols: list[str] = field(default_factory=list)
    removed_symbols: list[str] = field(default_factory=list)
    changed_symbols: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
