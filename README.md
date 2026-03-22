# 🔍 ConsistenCy 2.0 - 代码安全扫描与 AI 审查

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-包管理-purple.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 为 **vibe coding** / **高频 commit** 场景打造的代码安全扫描与 AI 审查工具

---

## ✨ 核心特性

- 🔐 **安全扫描** - Semgrep + Bandit 双引擎，支持 OWASP/CWE 规则集
- 🤖 **AI 代码审查** - LiteLLM 驱动，支持 DeepSeek/Claude/Grok 等任意模型
- 🔗 **GitNexus MCP 集成** - 代码图谱分析，提供上下文感知的审查
- 💬 **GitHub PR 自动评论** - 智能评论，支持旧评论清理

---

## 🚀 快速开始

### 安装

```bash
# 使用 uv（推荐）
uv pip install git+https://github.com/sk1ua/GitConsistency.git

# 或使用 pip
pip install consistancy
```

### 配置

```bash
# 初始化配置
cd your-project
consistancy init

# 编辑 .env 文件，配置 API 密钥
vim .env
```

### 运行分析

```bash
# 完整分析（安全扫描 + AI 审查）
cd your-project
consistancy analyze .

# 仅安全扫描
consistancy scan security .

# CI 模式（GitHub Actions）
consistancy ci
```

---

## 🏗️ 项目架构

```
PR触发
   ↓
GitHub Actions (uv cache)
   ↓
1. GitNexus MCP 构建/更新知识图谱（可选）
   ↓
安全扫描 (Semgrep + Bandit + GitNexus上下文)
   ↓
LLM审查 (LiteLLM，支持DeepSeek/Claude/Grok等)
   ↓
生成Markdown报告
   ↓
自动PR评论
```

---

## 📁 项目结构

```
consistancy/
├── core/                  # GitNexus MCP 封装
│   └── gitnexus_client.py
├── scanners/              # 扫描器
│   ├── security_scanner.py   # Semgrep + Bandit
│   └── orchestrator.py       # 扫描协调器
├── reviewer/              # LLM 审查
│   └── ai_reviewer.py
├── report/                # Markdown 报告生成
│   └── generator.py
├── github_integration.py  # GitHub 集成
├── main.py                # Typer CLI 入口
└── config.py              # Pydantic 配置
```

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| Python | 3.12+ |
| 包管理 | uv |
| CLI | Typer + Rich |
| 配置 | Pydantic v2 |
| 代码智能 | GitNexus MCP (可选) |
| 安全扫描 | Semgrep + Bandit |
| LLM | LiteLLM |
| 测试 | pytest + pytest-asyncio |

---

## 🧪 开发

```bash
# 克隆仓库
git clone https://github.com/sk1ua/GitConsistency.git
cd consistancy

# 安装开发依赖
uv sync

# 运行测试
pytest -v

# 代码检查
ruff check .
mypy consistancy/
```

### Docker 支持

```bash
# 构建镜像
docker build -t consistancy .

# 运行分析
docker run --rm -v $(pwd):/repo consistancy analyze /repo
```

---

## 📝 GitHub Actions 集成

```yaml
# .github/workflows/consistency.yml
name: ConsistenCy Code Review

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
      - name: Install ConsistenCy
        run: pip install consistancy
      - name: Run Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          LITELLM_API_KEY: ${{ secrets.LITELLM_API_KEY }}
        run: consistancy ci
```

---

## 📋 环境变量配置

| 变量 | 说明 | 必需 |
|------|------|------|
| `GITHUB_TOKEN` | GitHub Token，用于 PR 评论 | CI 模式必需 |
| `LITELLM_API_KEY` | LLM API 密钥 | 可选，用于 AI 审查 |
| `LITELLM_MODEL` | 模型名称，默认 `deepseek/deepseek-chat` | 可选 |
| `GITNEXUS_MCP_URL` | GitNexus MCP 地址 | 可选 |

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
