"""init 命令实现."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from consistency.cli.banner import print_banner

if TYPE_CHECKING:
    import typer
    from rich.console import Console


def register_init_command(app: "typer.Typer", console: "Console") -> None:
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

        console.print(f"[blue]📁 初始化路径:[/blue] {path.absolute()}")

        env_file = path / ".env"
        if env_file.exists() and not force:
            console.print(f"[yellow]⚠[/yellow] {env_file} 已存在，使用 --force 覆盖")
        else:
            env_content = """# GitConsistency 配置
LITELLM_API_KEY=your_api_key_here
GITHUB_TOKEN=your_github_token_here
"""
            env_file.write_text(env_content, encoding="utf-8")
            console.print(f"[green]✓[/green] 创建: {env_file}")

        github_dir = path / ".github" / "workflows"
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
