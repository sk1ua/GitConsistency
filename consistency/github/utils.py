"""GitHub 环境检测工具.

提供从环境变量检测 GitHub 信息的功能.
"""

from __future__ import annotations

import os
import re
from typing import Any


def parse_pr_url(url: str) -> tuple[str, int] | None:
    """从 PR URL 解析信息.

    Args:
        url: PR URL

    Returns:
        (repo, pr_number) 或 None
    """
    patterns = [
        r"github\.com/([^/]+/[^/]+)/pull/(\d+)",
        r"github\.com/([^/]+/[^/]+)/pulls/(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), int(match.group(2))

    return None


def detect_from_env() -> dict[str, Any] | None:
    """从环境变量检测 GitHub 信息.

    Returns:
        检测到的信息或 None
    """
    event_name = os.environ.get("GITHUB_EVENT_NAME")

    if not event_name:
        return None

    info = {
        "event_name": event_name,
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "sha": os.environ.get("GITHUB_SHA"),
        "ref": os.environ.get("GITHUB_REF"),
        "head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "base_ref": os.environ.get("GITHUB_BASE_REF"),
        "actor": os.environ.get("GITHUB_ACTOR"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "action": os.environ.get("GITHUB_ACTION"),
        "event_path": os.environ.get("GITHUB_EVENT_PATH"),
    }

    # 尝试从 event payload 获取 PR 编号
    if event_name == "pull_request" and info["event_path"]:
        try:
            import json

            with open(info["event_path"]) as f:
                event_data = json.load(f)
            info["pr_number"] = event_data.get("pull_request", {}).get("number")
        except Exception:
            pass

    return info


def is_github_actions() -> bool:
    """检查是否在 GitHub Actions 环境中运行."""
    return os.environ.get("GITHUB_ACTIONS") == "true"
