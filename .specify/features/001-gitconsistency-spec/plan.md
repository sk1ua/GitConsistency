# Implementation Plan: GitConsistency - Code Security & AI Review Tool

**Branch**: `001-gitconsistency-spec` | **Date**: 2026-03-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/speckit.specify` based on existing codebase

---

## Summary

GitConsistency 是一个 Python CLI 工具，提供代码安全扫描（Semgrep + Bandit）和 AI 驱动的多 Agent 代码审查。核心架构采用 Supervisor Pattern 协调多个专业 Agent（Security/Logic/Style），通过 LiteLLM 支持多种 LLM 后端，并集成 GitHub Actions 实现 PR 自动评论。

**技术方案**：基于已有代码库，这是一个已完整实现的工具。本计划记录其架构设计和技术决策。

---

## Technical Context

| 属性 | 值 |
|------|-----|
| **Language/Version** | Python 3.12+ |
| **Primary Dependencies** | Typer (CLI), Rich (输出), Pydantic v2 (配置/模型), LiteLLM (LLM), aiohttp (异步), Semgrep/Bandit (安全扫描), PyGithub (GitHub API) |
| **Storage** | 文件系统缓存（两级缓存：内存 TTLCache + 磁盘 pickle） |
| **Testing** | pytest + pytest-asyncio + pytest-cov + respx (HTTP mock) |
| **Target Platform** | Linux/macOS/Windows (WSL 推荐) |
| **Project Type** | CLI 工具 + Python 库 |
| **Performance Goals** | 快速模式 <2s，完整模式 <15s（单文件） |
| **Constraints** | 评论长度 <65536 字符（GitHub 限制），并发 API 调用默认限制 5 个 |
| **Scale/Scope** | 支持 1000+ 文件代码库，单 PR 最多 20 条评论 |

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 技术栈合理性 | ✅ 通过 | Python 3.12+ 现代化栈，异步优先 |
| 依赖最小化 | ✅ 通过 | 核心依赖精简，可选功能分组依赖 |
| 可测试性 | ✅ 通过 | pytest 全栈测试，覆盖率工具链完整 |
| 架构模式 | ✅ 通过 | Supervisor Pattern 解耦多 Agent 逻辑 |

**结果**: 所有检查通过，可以继续。

---

## Project Structure

### Documentation (this feature)

```text
.specify/features/001-gitconsistency-spec/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # (Optional) Architecture decisions
├── data-model.md        # Data entities documentation
├── quickstart.md        # Development guide
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (repository root)

```text
git-consistency/
├── consistency/                 # 核心包
│   ├── __init__.py
│   ├── __main__.py             # python -m consistency 入口
│   ├── config.py               # Pydantic Settings 配置
│   ├── exceptions.py           # 自定义异常体系
│   │
│   ├── cli/                    # CLI 层
│   │   ├── main.py             # Typer 应用主入口
│   │   ├── banner.py           # 启动横幅
│   │   ├── utils.py            # CLI 工具函数
│   │   └── commands/           # 命令实现
│   │       ├── analyze.py      # 分析命令
│   │       ├── ci.py           # CI/CD 命令
│   │       ├── config_cmd.py   # 配置命令
│   │       ├── init.py         # 初始化命令
│   │       ├── review.py       # 审查命令
│   │       └── scan.py         # 扫描命令
│   │
│   ├── agents/                 # 多 Agent 架构（核心）
│   │   ├── base.py             # Agent 基类（抽象接口）
│   │   ├── supervisor.py       # ReviewSupervisor（监督者）
│   │   ├── security_agent.py   # 安全审查 Agent
│   │   ├── logic_agent.py      # 逻辑审查 Agent
│   │   ├── style_agent.py      # 风格审查 Agent
│   │   └── synthesis_agent.py  # 结果综合 Agent
│   │
│   ├── scanners/               # 安全扫描器
│   │   ├── base.py             # 扫描器基类
│   │   ├── security_scanner.py # Semgrep + Bandit 实现
│   │   └── orchestrator.py     # 扫描器协调器
│   │
│   ├── reviewer/               # AI 审查器
│   │   ├── ai_reviewer.py      # AI 审查主类
│   │   ├── models.py           # Pydantic 数据模型
│   │   ├── prompts.py          # LLM 提示词模板
│   │   ├── context_enhancer.py # 上下文增强
│   │   └── disk_cache.py       # 磁盘缓存实现
│   │
│   ├── github/                 # GitHub 集成
│   │   ├── client.py           # GitHub API 客户端
│   │   ├── comments.py         # PR 评论管理
│   │   ├── checks.py           # Checks API
│   │   ├── labels.py           # 标签管理
│   │   ├── utils.py            # GitHub 工具
│   │   └── ci_utils.py         # CI/CD 工具
│   │
│   ├── llm/                    # LLM 抽象层
│   │   ├── base.py             # Provider 基类
│   │   ├── factory.py          # Provider 工厂
│   │   └── providers/
│   │       └── litellm.py      # LiteLLM 实现
│   │
│   ├── report/                 # 报告生成
│   │   ├── generator.py        # 报告生成器
│   │   ├── llm_generator.py    # LLM 驱动报告
│   │   ├── templates.py        # 报告模板
│   │   └── formatters/         # 格式输出
│   │       ├── base.py
│   │       ├── json.py
│   │       ├── markdown.py
│   │       └── html.py
│   │
│   ├── core/                   # 核心功能
│   │   ├── cache.py            # 两级缓存
│   │   ├── gitnexus_client.py  # GitNexus MCP 客户端
│   │   ├── schema.py           # 数据模型
│   │   ├── metrics.py          # 指标收集
│   │   └── self_hosted.py      # 自托管支持
│   │
│   └── tools/                  # 工具函数
│       ├── diff_tools.py       # 差异分析
│       ├── gitnexus_tools.py   # GitNexus 工具
│       └── security_tools.py   # 安全工具
│
├── tests/                      # 测试目录
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   └── conftest.py             # pytest 配置
│
├── docs/                       # 文档
├── examples/                   # 示例
├── pyproject.toml             # 项目配置
├── uv.lock                    # 依赖锁定
└── README.md                  # 项目说明
```

**Structure Decision**: 采用模块化分层架构，CLI/Agents/Scanners/GitHub/LLM/Report 各层职责清晰，通过接口抽象实现可测试性和可扩展性。

---

## Architecture Decisions

### ADR-001: Multi-Agent Supervisor Pattern

**决策**: 使用 Supervisor Pattern 协调 SecurityAgent、LogicAgent、StyleAgent 三个专业 Agent。

**理由**:
- 并行执行提高性能（asyncio.gather）
- 单个 Agent 失败不影响整体流程
- 易于添加新类型的 Agent
- SynthesisAgent 统一结果格式和去重

**替代方案**: 单一大模型调用所有检查点 — 拒绝原因：无法并行，错误隔离差，提示词过于复杂。

### ADR-002: Dual-Engine Security Scanning

**决策**: 同时使用 Semgrep（语义规则）和 Bandit（Python AST）。

**理由**:
- Semgrep 覆盖 OWASP/CWE 行业标准
- Bandit 专注 Python 特定漏洞
- 两者互补，减少漏报
- 并行执行不增加总耗时

### ADR-003: LiteLLM Abstraction Layer

**决策**: 使用 LiteLLM 作为 LLM 统一接口。

**理由**:
- 支持 100+ LLM 后端（DeepSeek、Claude、Grok 等）
- 统一 API 接口，无需为每个模型单独适配
- 内置重试、错误处理、速率限制

### ADR-004: Two-Level Caching

**决策**: 实现内存 TTLCache + 磁盘 pickle 两级缓存。

**理由**:
- 内存缓存：亚毫秒级响应热数据
- 磁盘缓存：进程重启后保持，减少重复 LLM 调用
- GitNexus 分析结果缓存，避免重复构建图谱

---

## Complexity Tracking

> 本项目的复杂度均在合理范围内，无需额外简化。

| 组件 | 复杂度评估 | 理由 |
|------|-----------|------|
| Agent 架构 | 中等 | 3 个 Agent + Supervisor，职责清晰 |
| 缓存系统 | 低 | 标准 TTLCache + pickle 模式 |
| GitHub 集成 | 中等 | 签名机制 + 批量操作 + 错误处理 |
| LLM 抽象 | 低 | LiteLLM 封装，工厂模式创建 |

---

## Dependencies by Feature Group

```toml
# 核心依赖（必需）
[project.dependencies]
typer = ">=0.12.0"          # CLI 框架
rich = ">=13.0.0"           # 富文本输出
pydantic = ">=2.5.0"        # 配置和数据验证
pydantic-settings = ">=2.1.0"  # 环境变量支持
aiohttp = ">=3.9.0"         # 异步 HTTP
httpx = ">=0.25.0"          # HTTP 客户端
tenacity = ">=8.2.3"        # 重试机制
python-dotenv = ">=1.0.0"   # .env 文件支持
cachetools = ">=5.3.0"      # 内存缓存

# 安全扫描（可选）
[project.optional-dependencies.security]
semgrep = ">=1.52.0"        # 语义规则引擎
bandit = { extras = ["toml"], version = ">=1.7.6" }  # Python 安全扫描

# AI 审查（可选）
[project.optional-dependencies.ai]
litellm = ">=1.35.0"        # LLM 统一接口

# GitHub 集成（可选）
[project.optional-dependencies.github]
pygithub = ">=2.1.1"        # GitHub API 封装

# 完整功能
[project.optional-dependencies.full]
# 包含 security + ai + github
```

---

## Post-Design Constitution Re-Check

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 技术栈合理性 | ✅ 通过 | 现代化 Python 异步栈 |
| 依赖最小化 | ✅ 通过 | 可选依赖分组，按需安装 |
| 可测试性 | ✅ 通过 | 接口抽象，易于 mock |
| 架构模式 | ✅ 通过 | 符合项目规模的最佳实践 |

**最终结果**: ✅ 所有检查通过，计划完成。
