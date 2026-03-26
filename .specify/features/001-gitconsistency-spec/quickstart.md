# Quick Start Guide: GitConsistency Development

**Feature**: GitConsistency - Code Security & AI Review Tool
**Date**: 2026-03-25

---

## Prerequisites

- **Python**: 3.12 或更高版本
- **操作系统**: Linux, macOS, Windows (WSL 推荐)
- **内存**: 至少 4GB RAM
- **Git**: 用于版本控制和 diff 分析

---

## Installation

### 方式一：从源码安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency

# 使用 uv 安装（推荐）
uv pip install -e ".[full,dev]"

# 或使用 pip
pip install -e ".[full,dev]"
```

### 方式二：使用 Docker

```bash
docker build -t gitconsistency .
docker run --rm -v $(pwd):/repo gitconsistency analyze /repo
```

---

## Configuration

### 1. 初始化配置

```bash
# 在项目目录下初始化
gitconsistency init

# 这会创建 .env 文件
```

### 2. 编辑环境变量

```bash
# 编辑 .env 文件
vim .env
```

**必需配置**:

```env
# GitHub Token（用于 PR 评论）
CONSISTENCY_GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# LLM API 密钥（用于 AI 审查）
CONSISTENCY_LITELLM_API_KEY=sk-xxxxxxxxxxxx

# LLM 模型（可选，默认 deepseek/deepseek-chat）
CONSISTENCY_LITELLM_MODEL=deepseek/deepseek-chat
```

**可选配置**:

```env
# GitNexus 集成
CONSISTENCY_GITNEXUS_ENABLED=true

# 扫描器配置
CONSISTENCY_SCANNER__SEMGREP_RULES=p/security-audit,p/owasp-top-ten
CONSISTENCY_SCANNER__BANDIT_SEVERITY=LOW

# 缓存配置
CONSISTENCY_CACHE__DIR=.cache
CONSISTENCY_CACHE__TTL=3600
```

---

## Usage

### 基本命令

```bash
# 查看帮助
gitconsistency --help

# 验证配置
gitconsistency config validate

# 查看版本
gitconsistency --version
```

### 安全扫描

```bash
# 扫描当前目录
gitconsistency scan security .

# 扫描特定目录
gitconsistency scan security ./src

# 扫描特定文件
gitconsistency scan security ./main.py

# 仅显示高危和严重问题
gitconsistency scan security . --severity HIGH
```

### AI 代码审查

```bash
# 审查当前变更（git diff）
gitconsistency review diff

# 快速模式（<2s）
gitconsistency review diff --quick

# 审查暂存区
gitconsistency review diff --cached

# 审查特定文件
gitconsistency review file main.py

# 对比目标分支
gitconsistency review diff --target main
```

### 完整分析

```bash
# 完整分析（安全扫描 + AI 审查）
gitconsistency analyze .

# 输出 JSON 格式
gitconsistency analyze . --format json

# 保存到文件
gitconsistency analyze . --output report.md
```

### CI/CD 模式

```bash
# 在 GitHub Actions 中使用
gitconsistency ci

# 这会:
# 1. 自动检测 PR 环境
# 2. 分析变更文件
# 3. 发布评论到 PR
```

---

## Development

### 项目结构

```
consistency/
├── cli/           # CLI 命令
├── agents/        # AI Agent 实现
├── scanners/      # 安全扫描器
├── github/        # GitHub 集成
├── llm/           # LLM 抽象层
├── report/        # 报告生成
├── core/          # 核心功能
└── tools/         # 工具函数
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/unit/test_agents.py -v

# 运行带覆盖率
pytest --cov=consistency --cov-report=html

# 运行特定标记的测试
pytest -m unit
pytest -m integration
```

### 代码质量

```bash
# 代码格式化
ruff format .

# 代码检查
ruff check .

# 类型检查
mypy consistency/

# 安全扫描
bandit -r consistency/

# 运行所有 pre-commit 钩子
pre-commit run --all-files
```

---

## Architecture Overview

### Multi-Agent 架构

```
┌─────────────────────────────────────┐
│         ReviewSupervisor            │
│  ┌─────────┬─────────┬─────────┐   │
│  │Security │  Logic  │  Style  │   │
│  │ Agent   │ Agent   │ Agent   │   │
│  └────┬────┴────┬────┴────┬────┘   │
│       └─────────┼─────────┘        │
│                 ▼                  │
│         SynthesisAgent             │
└─────────────────────────────────────┘
```

### 数据流

1. **输入**: 文件/diff → CLI
2. **安全扫描**: Semgrep + Bandit → `list[Finding]`
3. **AI 审查**: Multi-Agent → `ReviewResult`
4. **输出**: 报告 → CLI/GitHub PR

---

## Troubleshooting

### 常见问题

**问题**: Semgrep/Bandit 未安装

```bash
# 安装完整依赖
pip install -e ".[full]"

# 或单独安装
pip install semgrep bandit
```

**问题**: LLM API 调用失败

```bash
# 检查 API 密钥
export CONSISTENCY_LITELLM_API_KEY=your_key

# 测试连接
gitconsistency config validate
```

**问题**: GitHub PR 评论未发布

```bash
# 检查 Token 权限
gitconsistency config validate

# 确保有 PR 写权限
```

---

## Resources

- **Repository**: https://github.com/sk1ua/GitConsistency
- **Issues**: https://github.com/sk1ua/GitConsistency/issues
- **Documentation**: See `docs/` directory
