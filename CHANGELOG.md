# Changelog

所有重要的变更都会记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.0.0] - 2026-03-22

### 🎉 初始发布

ConsistenCy 2.0 - 代码安全扫描与 AI 审查工具正式发布！

### ✨ 新增功能

#### 🔧 核心功能
- **GitNexus MCP 客户端** - 异步代码知识图谱客户端，支持 SSE 和 stdio 传输
- **两级缓存系统** - 内存缓存 (TTLCache) + 文件缓存 (pickle)，自动过期管理

#### 🔐 安全扫描
- **Semgrep 集成** - 语义化安全规则扫描，支持 OWASP、CWE 规则集
- **Bandit 集成** - Python 专用安全扫描器
- **并行执行** - 同时运行 Semgrep 和 Bandit，结果去重
- **上下文增强** - 使用 GitNexus 判断变量是否为用户输入

#### 🤖 AI 审查
- **LiteLLM 集成** - 支持 DeepSeek、Claude、Grok 等任意模型
- **Prompt 模板系统** - 5 种审查类型（通用/安全/性能/文档）
- **结构化输出** - Pydantic v2 强类型验证
- **双重缓存** - Prompt 缓存 + 结果缓存
- **降级策略** - 主模型失败自动切换备选模型

#### 📊 报告生成
- **Markdown 报告** - 漂亮的表格、代码块、图标
- **HTML 报告** - 独立页面，内置 CSS 样式
- **JSON 报告** - 结构化数据，支持后续处理
- **GitHub 评论** - PR 评论格式，自动长度限制

#### 💬 GitHub 集成
- **PR 评论** - 发布带签名的评论，自动删除旧评论
- **文件行级评论** - 对特定代码行发表评论
- **批量评论** - 并发发布多条评论

#### 🖥️ CLI
- **完整命令集** - analyze / ci / scan / config / init
- **Rich 输出** - 漂亮的表格、进度条、彩色文本
- **配置验证** - 检查 LLM/GitHub/GitNexus 配置状态

#### 🔧 CI/CD
- **GitHub Actions** - PR 触发、uv 缓存、多任务并行
- **Docker 支持** - 多阶段构建，production/dev 阶段
- **Docker Compose** - 支持 CLI、测试等多种模式

### 🧪 测试
- **30+ 单元测试** - 覆盖核心模块
- **E2E 测试** - 完整工作流测试

### 📦 依赖
- Python 3.12+
- uv / pip 包管理
- 详见 pyproject.toml

### 📝 文档
- README.md - 项目介绍和使用指南
- CONTRIBUTING.md - 贡献指南
- CHANGELOG.md - 变更日志

---

## [Unreleased]

### 计划中
- [ ] GitNexus MCP 服务端支持
- [ ] 更多语言支持（JavaScript/TypeScript/Go）
- [ ] VS Code 扩展
- [ ] Webhook 通知（Slack/Discord/飞书）
