# 贡献指南

感谢您对 ConsistenCy 的兴趣！本文档将帮助您参与项目开发。

## 开发环境设置

### 前置要求

- Python 3.12+
- uv (包管理器)
- Git

### 设置步骤

```bash
# 1. Fork 并克隆仓库
git clone https://github.com/YOUR_USERNAME/consistancy.git
cd consistancy

# 2. 创建虚拟环境并安装依赖
uv venv
uv pip install -e ".[dev]"

# 3. 安装 pre-commit hooks
pre-commit install

# 4. 验证安装
consistancy --version
```

## 项目结构

```
consistancy/
├── core/           # GitNexus MCP 客户端
├── scanners/       # 扫描引擎
├── reviewer/       # AI 审查
├── report/         # 报告生成
└── tests/          # 测试
    ├── unit/       # 单元测试
    ├── integration/# 集成测试
    └── e2e/        # 端到端测试
```

## 代码规范

### 风格

我们使用 Ruff 进行代码格式化和 lint：

```bash
# 格式化
ruff format .

# Lint 检查
ruff check . --fix

# 类型检查
mypy consistancy/
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

### 运行测试

```bash
# 全部测试
pytest -v

# 仅单元测试
pytest tests/unit/ -v

# 带覆盖率
pytest -v --cov=consistancy --cov-report=html

# 并行测试
pytest -v -n auto
```

### 测试规范

- 单元测试放在 `tests/unit/`
- 集成测试放在 `tests/integration/`
- 测试文件命名为 `test_*.py`
- 使用 pytest-asyncio 测试异步代码
- 使用 respx 模拟 HTTP 请求

## 添加新扫描器

要添加新的扫描器，需要：

1. 在 `scanners/` 创建新文件
2. 继承 `BaseScanner` 接口
3. 实现 `scan()` 方法
4. 添加单元测试
5. 更新 CLI 命令

示例：

```python
# scanners/my_scanner.py
from consistancy.scanners.base import BaseScanner, ScanResult

class MyScanner(BaseScanner):
    async def scan(self, path: Path) -> ScanResult:
        # 实现扫描逻辑
        return ScanResult(
            scanner_name="my_scanner",
            findings=[...],
        )
```

## 问题报告

### Bug 报告

请包含：
- Python 版本
- ConsistenCy 版本
- 复现步骤
- 预期行为 vs 实际行为
- 错误日志

### 功能请求

请包含：
- 使用场景
- 期望的功能描述
- 可能的实现思路（可选）

## 发布流程

维护者使用以下流程发布新版本：

```bash
# 1. 更新版本号
# 修改 __init__.py 和 pyproject.toml

# 2. 更新 CHANGELOG.md

# 3. 创建标签
git tag -a v2.x.x -m "Release v2.x.x"

# 4. 推送标签
git push origin v2.x.x

# 5. GitHub Actions 自动发布到 PyPI
```

## 获取帮助

- 📖 阅读 [文档](https://docs.consistancy.dev)
- 💬 加入 [Discussions](https://github.com/sk1ua/GitConsistency/discussions)
- 🐛 提交 [Issue](https://github.com/sk1ua/GitConsistency/issues)

## 行为准则

- 尊重所有贡献者
- 欢迎新手，耐心指导
- 专注于技术讨论
- 遵守 MIT 许可证

再次感谢您的贡献！🎉
