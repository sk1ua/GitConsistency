"""初始化命令.

在新项目中初始化 GitConsistency 配置，创建 .env 文件和 GitHub Actions 工作流.

Examples:
    >>> from consistency.commands.init import InitCommand
    >>> cmd = InitCommand()
    >>> cmd.init_project(Path("./my-project"))
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


class InitCommand:
    """初始化命令处理器.

    为新项目创建 GitConsistency 配置文件和 GitHub Actions 工作流.

    Attributes:
        force: 是否覆盖现有文件
    """

    def __init__(self, force: bool = False) -> None:
        """初始化命令.

        Args:
            force: 覆盖现有文件
        """
        self.force = force

    def init_project(self, path: Path) -> dict[str, Any]:
        """初始化项目配置.

        Args:
            path: 初始化路径

        Returns:
            初始化结果
        """
        console.print(f"[blue]📁 初始化路径:[/blue] {path.absolute()}")

        created_files = []

        # 创建 .env 文件
        env_result = self._create_env_file(path)
        if env_result["created"]:
            created_files.append(env_result["path"])

        # 创建 GitHub Actions 工作流
        workflow_result = self._create_workflow(path)
        if workflow_result["created"]:
            created_files.append(workflow_result["path"])

        if created_files:
            console.print("\n[green]🎉 初始化完成！[/green]")
            console.print("[dim]下一步: 编辑 .env 文件，配置 API 密钥[/dim]")
        else:
            console.print("\n[yellow]⚠ 未创建任何文件，使用 --force 覆盖现有文件[/yellow]")

        return {
            "success": True,
            "created_files": created_files,
            "path": str(path.absolute()),
        }

    def _create_env_file(self, path: Path) -> dict[str, Any]:
        """创建 .env 配置文件.

        Args:
            path: 目标路径

        Returns:
            创建结果
        """
        env_file = path / ".env"

        if env_file.exists() and not self.force:
            console.print(f"[yellow]⚠[/yellow] {env_file} 已存在，使用 --force 覆盖")
            return {"created": False, "path": str(env_file)}

        env_content = """# GitConsistency 配置

# LiteLLM API 密钥（用于 AI 审查）
CONSISTENCY_LITELLM_API_KEY=your_api_key_here

# GitHub Token（用于 PR 评论）
CONSISTENCY_GITHUB_TOKEN=your_github_token_here

# 可选：自定义模型
# CONSISTENCY_LITELLM_MODEL=deepseek/deepseek-chat

# 可选：启用 GitNexus
# CONSISTENCY_GITNEXUS_ENABLED=true
"""

        env_file.write_text(env_content, encoding="utf-8")
        console.print(f"[green]✓[/green] 创建: {env_file}")
        return {"created": True, "path": str(env_file)}

    def _create_workflow(self, path: Path) -> dict[str, Any]:
        """创建 GitHub Actions 工作流.

        Args:
            path: 目标路径

        Returns:
            创建结果
        """
        github_dir = path / ".github" / "workflows"
        github_dir.mkdir(parents=True, exist_ok=True)

        workflow_file = github_dir / "consistency.yml"

        if workflow_file.exists() and not self.force:
            console.print(f"[yellow]⚠[/yellow] {workflow_file} 已存在，使用 --force 覆盖")
            return {"created": False, "path": str(workflow_file)}

        workflow_content = """name: 🔍 GitConsistency Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install GitConsistency
        run: pip install "git-consistency[full]"

      - name: Run Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          LITELLM_API_KEY: ${{ secrets.LITELLM_API_KEY }}
        run: gitconsistency ci
"""

        workflow_file.write_text(workflow_content, encoding="utf-8")
        console.print(f"[green]✓[/green] 创建: {workflow_file}")
        return {"created": True, "path": str(workflow_file)}
