# 贡献指南

感谢您对 GitConsistency 的兴趣！本文档帮助您参与项目开发。

## 开发环境设置

### 前置要求

- Python 3.12+
- uv (包管理器)
- Git

### 设置步骤

```bash
# 1. Fork 并克隆仓库
git clone https://github.com/YOUR_USERNAME/GitConsistency.git
cd GitConsistency

# 2. 创建虚拟环境并安装依赖
uv venv
uv pip install -e ".[dev]"

# 3. 验证安装
gitconsistency --version
```

## 代码规范

### 风格

使用 Ruff 进行代码格式化和 lint：

```bash
# 格式化
ruff format .

# Lint 检查
ruff check . --fix

# 类型检查
mypy consistency/
```

### 提交信息

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
feat: 添加新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
test: 测试相关
chore: 构建/工具相关
```

## 开发流程

1. **创建分支**: `git checkout -b feat/your-feature`
2. **编写代码**: 遵循现有代码风格
3. **编写测试**: 新功能必须包含测试
4. **运行测试**: `pytest -v`
5. **提交更改**: `git commit -m "feat: ..."`
6. **推送到 Fork**: `git push origin feat/your-feature`
7. **创建 PR**: 在 GitHub 上创建 Pull Request

## 测试

```bash
# 全部测试
pytest -v

# 仅单元测试
pytest tests/unit/ -v

# 带覆盖率
pytest -v --cov=consistency --cov-report=html
```

### 测试规范

- 单元测试放在 `tests/unit/`
- 集成测试放在 `tests/integration/`
- 使用 pytest-asyncio 测试异步代码

## 问题报告

### Bug 报告

请包含：
- Python 版本
- GitConsistency 版本
- 复现步骤
- 预期行为 vs 实际行为
- 错误日志

### 功能请求

请包含：
- 使用场景
- 期望的功能描述
- 可能的实现思路（可选）

## 获取帮助

- 💬 加入 [Discussions](https://github.com/sk1ua/GitConsistency/discussions)
- 🐛 提交 [Issue](https://github.com/sk1ua/GitConsistency/issues)

再次感谢您的贡献！🎉
