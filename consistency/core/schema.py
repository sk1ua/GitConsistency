"""GitNexus 数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextResult:
    """上下文查询结果."""

    file_path: str
    symbols: list[dict[str, Any]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
