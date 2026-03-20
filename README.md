# 🔍 ConsistenCy 2.0 - 现代代码健康智能守护者

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-包管理-purple.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 为 **vibe coding** / **高频 commit** / **多人协作** 场景打造的智能代码健康守护系统

---

## ✨ 核心特性

- 🔐 **安全扫描** - Semgrep + Bandit 双引擎，支持自定义规则
- 🔄 **一致性漂移检测** - 基于代码图谱和 embedding 的命名/风格一致性监控
- 🔥 **技术债务热点** - 复杂度 × 变更频率，精准定位高风险代码
- 🤖 **AI 代码审查** - LiteLLM 驱动，支持 DeepSeek/Claude/Grok 等任意模型
- 📊 **Streamlit Dashboard** - 交互式可视化报告
- 💬 **GitHub PR 自动评论** - 智能评论，支持旧评论清理

---

## 🚀 快速开始

### 安装

```bash
# 使用 uv（推荐）
uv pip install git+https://github.com/consistancy-team/consistancy.git

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
# 完整分析
cd your-project
consistancy analyze .

# 仅安全扫描
consistancy scan security .

# 启动 Dashboard
consistancy dashboard
```

---

## 🏗️ 项目架构

```
PR触发
   ↓
GitHub Actions (uv cache)
   ↓
1. GitNexus MCP 构建/更新知识图谱（核心大脑）
   ↓
并行执行：
   ├── 安全扫描 (Semgrep + Bandit + GitNexus上下文)
   ├── 一致性漂移检测 (图谱统计 + embedding)
   └── 技术债务热点 (复杂度 × 变更频率)
   ↓
LLM审查 (LiteLLM，支持DeepSeek/Claude/Grok等)
   ↓
生成Markdown报告 + Streamlit Dashboard更新
   ↓
自动PR评论 + 可选Webhook通知
```

---

## 📁 项目结构

```
consistancy/
├── core/                  # GitNexus MCP 封装
│   └── gitnexus_client.py
├── scanners/              # 三种扫描器
│   ├── security_scanner.py
│   ├── drift_detector.py
│   └── hotspot_analyzer.py
├── reviewer/              # LLM 审查
│   └── ai_reviewer.py
├── report/                # Markdown 报告生成
│   └── generator.py
├── dashboard/             # Streamlit 界面
│   └── app.py
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
| 代码智能 | GitNexus MCP |
| 安全扫描 | Semgrep + Bandit |
| LLM | LiteLLM |
| Dashboard | Streamlit + Plotly |
| 测试 | pytest + pytest-asyncio |

---

## 🧪 开发

```bash
# 克隆仓库
git clone https://github.com/consistancy-team/consistancy.git
cd consistancy

# 安装开发依赖
uv sync

# 运行测试
pytest -v

# 代码检查
ruff check .
mypy consistancy/

# 启动 Dashboard
streamlit run consistancy/dashboard/app.py
```

### Docker 支持

```bash
# 构建镜像
docker-compose build

# 运行分析
docker-compose run --rm consistancy analyze /repo

# 启动 Dashboard
docker-compose up dashboard
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
    steps:
      - uses: actions/checkout@v4
      - name: Run ConsistenCy
        uses: consistancy-team/consistancy-action@v2
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          litellm_api_key: ${{ secrets.LITELLM_API_KEY }}
```

---

## 📋 开发路线图

- [x] **阶段0**: 项目初始化 - pyproject.toml, Dockerfile, CLI 框架
- [x] **阶段1**: GitNexus MCP 核心封装 - 异步 MCP 客户端、缓存
- [x] **阶段2**: 扫描引擎 - 安全扫描、漂移检测、热点分析
- [x] **阶段3**: AI 审查核心 - LiteLLM、Prompt 模板、结构化输出
- [x] **阶段4**: 报告与 GitHub 集成 - Markdown/HTML/JSON、PR 评论
- [x] **阶段5**: Streamlit Dashboard - 交互式可视化、趋势分析
- [x] **阶段6**: CI/CD 自动化 - GitHub Actions、完整 CLI、测试
- [x] **阶段7**: 文档与打包 - README、CONTRIBUTING、Docker 支持

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🤝 贡献

欢迎提交 Issue 和 PR！详见 [CONTRIBUTING.md](CONTRIBUTING.md)

---

<p align="center">
  <sub>Built with ❤️ by the ConsistenCy Team</sub>
</p>
