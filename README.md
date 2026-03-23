# 🔍 GitConsistency - 代码安全扫描与 AI 审查

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-包管理-purple.svg)](https://github.com/astral-sh/uv)
[![CI](https://github.com/sk1ua/GitConsistency/actions/workflows/consistency.yml/badge.svg)](https://github.com/sk1ua/GitConsistency/actions)
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
# 完整功能（推荐）
pip install "git-consistency[full]"

# 或按需安装
pip install "git-consistency[security]"    # 仅安全扫描
pip install "git-consistency[ai]"          # 包含 AI 审查

# 使用 uv（推荐）
uv pip install "git-consistency[full]"
```

### 配置

```bash
# 初始化配置
cd your-project
gitconsistency init

# 编辑 .env 文件，配置 API 密钥
vim .env
```

### 运行分析

```bash
# 完整分析（安全扫描 + AI 审查）
cd your-project
gitconsistency analyze .

# 仅安全扫描
gitconsistency scan security .

# CI 模式（GitHub Actions）
gitconsistency ci

# 🚀 Vibe Coding 场景 - 快速审查
gitconsistency review diff --quick           # 审查变更（快速）
gitconsistency review file main.py --quick   # 审查单个文件
gitconsistency review diff --cached          # 审查暂存区
```

📚 **更多示例**: 查看 [examples/](examples/) 目录和 [Vibe Coding 指南](docs/vibe-coding.md)

---

## 🏗️ 项目架构

```
PR触发 / 手动审查
   ↓
┌─────────────────────────────────────────────────────┐
│                 ReviewSupervisor                    │
│  ┌──────────────┬──────────────┬──────────────┐    │
│  │ SecurityAgent │ LogicAgent   │ StyleAgent   │    │
│  │  (安全)       │  (逻辑)      │  (风格)      │    │
│  └──────────────┴──────────────┴──────────────┘    │
│              ↓ 并行执行 (asyncio)                   │
│           SynthesisAgent (结果汇总)                 │
└─────────────────────────────────────────────────────┘
   ↓
GitNexus 代码图谱（可选，提供上下文）
   ↓
生成报告 → GitHub PR 评论 / CLI 输出
```

**增量审查流程**（Vibe Coding 场景）：
```
保存文件 / git commit
   ↓
git diff → DiffParser 解析变更
   ↓
只审查变更的代码块
   ↓
快速反馈 (< 2s)
```

---

## 📁 项目结构

```
consistency/
├── agents/                # LangChain 多 Agent 架构
│   ├── base.py            # BaseAgent, AgentResult
│   ├── security_agent.py  # 安全检查
│   ├── logic_agent.py     # 逻辑分析
│   ├── style_agent.py     # 风格检查
│   ├── synthesis_agent.py # 结果汇总
│   └── supervisor.py      # ReviewSupervisor
├── commands/              # CLI 命令
│   └── review.py          # review 子命令
├── core/                  # GitNexus 客户端
│   └── gitnexus_client.py
├── scanners/              # 扫描器
│   ├── security_scanner.py
│   └── orchestrator.py
├── reviewer/              # LLM 审查
│   └── ai_reviewer.py
├── tools/                 # LangChain 工具
│   ├── gitnexus_tools.py
│   ├── security_tools.py
│   └── diff_tools.py      # 增量审查
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
| 多 Agent 架构 | LangChain 风格 |
| 代码智能 | GitNexus (可选) |
| 安全扫描 | Semgrep + Bandit |
| LLM | LiteLLM |
| 测试 | pytest + pytest-asyncio |

---

## 🧪 开发

```bash
# 克隆仓库
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency

# 安装开发依赖
uv sync

# 运行测试
pytest -v

# 代码检查
ruff check .
mypy consistency/
```

### Docker 支持

```bash
# 构建镜像
docker build -t gitconsistency .

# 运行分析
docker run --rm -v $(pwd):/repo gitconsistency analyze /repo
```

---

## 📝 GitHub Actions 集成

```yaml
# .github/workflows/consistency.yml
name: GitConsistency Code Review

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
```

---

## 📋 环境变量配置

| 变量 | 说明 | 必需 |
|------|------|------|
| `CONSISTENCY_GITHUB_TOKEN` | GitHub Token，用于 PR 评论 | CI 模式必需 |
| `CONSISTENCY_LITELLM_API_KEY` | LLM API 密钥 | 可选，用于 AI 审查 |
| `CONSISTENCY_LITELLM_MODEL` | 模型名称，默认 `deepseek/deepseek-chat` | 可选 |
| `CONSISTENCY_GITNEXUS_ENABLED` | 是否启用 GitNexus | 可选，默认 `false` |
| `CONSISTENCY_QUICK_MODE` | 快速模式（只运行 SecurityAgent） | 可选，默认 `false` |

---

## 🔗 GitNexus 集成（可选）

GitNexus 提供代码知识图谱分析能力，增强 AI 审查的上下文理解。

**前置要求**：
1. 安装 GitNexus CLI：`npm install -g gitnexus`
2. 启用环境变量：`export CONSISTENCY_GITNEXUS_ENABLED=true`

**工作原理**：
- GitNexus 分析代码库构建知识图谱
- AI 审查时获取函数的调用关系（callers/callees）
- 识别潜在的副作用和依赖关系

**注意**：没有 GitNexus 时工具仍可正常运行，只是缺少上下文增强功能。

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
