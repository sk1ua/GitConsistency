"""init 命令实现."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from consistency.cli.banner import print_banner

if TYPE_CHECKING:
    from rich.console import Console


def _validate_path(path: Path, console: Console) -> Path | None:
    """验证并返回安全的路径.

    防止路径遍历攻击，确保路径不会写到系统敏感目录。

    Args:
        path: 用户输入的路径
        console: 控制台对象用于输出错误

    Returns:
        验证通过返回绝对路径，否则返回 None
    """
    resolved = path.resolve()
    cwd = Path.cwd().resolve()

    # 允许在当前工作目录下或用户主目录下
    home = Path.home().resolve()
    is_under_cwd = str(resolved).startswith(str(cwd))
    is_under_home = str(resolved).startswith(str(home))

    if not (is_under_cwd or is_under_home):
        console.print(f"[red]✗ 非法路径: {path}[/red]")
        console.print("[dim]路径必须在当前工作目录或用户主目录下[/dim]")
        return None

    return resolved


def register_init_command(app: typer.Typer, console: Console) -> None:
    """注册 init 命令到主 CLI."""

    @app.command(name="init")
    def init_command(
        path: Path = Path("."),
        force: bool = False,
    ) -> None:
        """在新项目中初始化 GitConsistency 配置.

        创建 .env 文件、GitHub Actions 工作流等.

        Examples:
            $ gitconsistency init ./my-project
            $ gitconsistency init . --force
        """
        print_banner()

        # 验证路径安全性
        safe_path = _validate_path(path, console)
        if safe_path is None:
            raise typer.Exit(1)

        console.print(f"[blue]📁 初始化路径:[/blue] {safe_path}")

        env_file = safe_path / ".env"
        if env_file.exists() and not force:
            console.print(f"[yellow]⚠[/yellow] {env_file} 已存在，使用 --force 覆盖")
        else:
            env_content = """# GitConsistency 配置
LITELLM_API_KEY=your_api_key_here
GITHUB_TOKEN=your_github_token_here
"""
            env_file.write_text(env_content, encoding="utf-8")
            console.print(f"[green]✓[/green] 创建: {env_file}")

        github_dir = safe_path / ".github" / "workflows"
        github_dir.mkdir(parents=True, exist_ok=True)

        workflow_file = github_dir / "consistency.yml"
        workflow_content = """name: 🔍 GitConsistency Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
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

        console.print("\n[green]🎉 初始化完成！[/green]")
        console.print("[dim]下一步: 编辑 .env 文件，配置 API 密钥[/dim]")
