"""CLI 工具函数."""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_git_commit_sha(path: Path) -> str:
    """获取目标路径下的 Git 提交 SHA，失败时返回 unknown."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
        sha = result.stdout.strip()
        return sha if sha else "unknown"
    except Exception:
        return "unknown"
