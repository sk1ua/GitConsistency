# 🔍 GitConsistency - 代码安全扫描与 AI 审查

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
# 从源码安装（推荐）
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency
pip install -e ".[full]"

# 或使用 uv（更快）
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency
uv pip install -e ".[full]"
```

### 配置

```bash
# 初始化配置
cd your-project
gitconsistency init

# 编辑 .env 文件配置 API 密钥
vim .env
```

### 运行分析

```bash
# 完整分析（安全扫描 + AI 审查）
gitconsistency analyze .

# 仅安全扫描
gitconsistency scan security .

# CI 模式（GitHub Actions）
gitconsistency ci
```

---

## 📖 使用场景

### Vibe Coding 快速审查

```bash
# 审查变更（快速模式 <2s）
gitconsistency review diff --quick

# 审查暂存区
gitconsistency review diff --cached

# 审查单个文件
gitconsistency review file main.py --quick

# 对比目标分支
gitconsistency review diff --target main
```

### 模式对比

| 特性 | 快速模式 `--quick` | 完整模式 |
|------|-------------------|---------|
| 运行时间 | < 2s | 5-15s |
| 审查 Agent | SecurityAgent | Security + Logic + Style |
| 适用场景 | 保存时、频繁提交 | 提交前检查 |
| 问题深度 | 关键安全问题 | 全面的代码质量 |

---

## 🏗️ 架构

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

## 🔧 详细安装

### 系统要求

- **Python**: 3.12 或更高版本
- **操作系统**: Linux, macOS, Windows (WSL 推荐)
- **内存**: 至少 4GB RAM

### 安装方式

#### 方式一：从源码安装（推荐）

```bash
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency
pip install -e ".[full,dev]"
```

#### 方式二：使用 Docker

```bash
docker build -t gitconsistency .
docker run --rm -v $(pwd):/repo gitconsistency analyze /repo
```

### 验证安装

```bash
gitconsistency --version
gitconsistency config validate
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
        run: |
          pip install setuptools wheel
          pip install -e ".[full]"
      - run: gitconsistency ci
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CONSISTENCY_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CONSISTENCY_LITELLM_API_KEY: ${{ secrets.LITELLM_API_KEY }}
```

### Secrets 配置

| 配置项 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `GITHUB_TOKEN` | Secret | ✅ 自动 | GitHub 自动提供 |
| `CONSISTENCY_LITELLM_API_KEY` | Secret | ❌ 推荐 | LLM API 密钥（推荐） |
| `CONSISTENCY_LITELLM_MODEL` | Variable | ❌ 可选 | 默认 `deepseek/deepseek-chat` |

支持直接设置 `LITELLM_API_KEY`（向后兼容），但推荐使用 `CONSISTENCY_` 前缀。

---

## 🔗 GitNexus 集成（可选）

GitNexus 提供代码知识图谱分析能力，增强 AI 审查的上下文理解。

**前置要求**:
```bash
npm install -g gitnexus
```

**工作原理**:
1. GitNexus 分析代码库构建知识图谱
2. AI 审查时获取函数的调用关系（callers/callees）
3. 识别潜在的副作用和依赖关系

**配置**:
```bash
export CONSISTENCY_GITNEXUS_ENABLED=true
```

> 注意：没有 GitNexus 时工具仍可正常运行，只是缺少上下文增强功能。

---

## 📋 环境变量配置

| 变量 | 说明 | 必需 |
|------|------|------|
| `CONSISTENCY_GITHUB_TOKEN` | GitHub Token，用于 PR 评论 | CI 模式必需 |
| `CONSISTENCY_LITELLM_API_KEY` | LLM API 密钥 | 可选，用于 AI 审查 |
| `CONSISTENCY_LITELLM_MODEL` | 模型名称 | 可选 |
| `CONSISTENCY_GITNEXUS_ENABLED` | 是否启用 GitNexus | 可选，默认 `false` |
| `CONSISTENCY_QUICK_MODE` | 快速模式默认开启 | 可选，默认 `false` |

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

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
