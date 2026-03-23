# Vibe Coding 场景优化

为高频编码场景（vibe coding）优化的快速反馈机制。

## 快速开始

### 1. 单文件审查

```bash
# 完整模式 - 全量分析
gitconsistency review file main.py

# 快速模式 - 只检查关键问题
gitconsistency review file main.py --quick

# 显示代码片段
gitconsistency review file main.py --show-code
```

### 2. 增量审查（git diff）

```bash
# 审查工作区的变更
gitconsistency review diff

# 审查暂存区的变更
gitconsistency review diff --cached

# 对比目标分支
gitconsistency review diff --target main

# 快速模式
gitconsistency review diff --quick
```

### 3. 批量审查

```bash
# 审查多个文件
gitconsistency review batch main.py utils.py config.py

# 快速审查所有 Python 文件
gitconsistency review batch *.py --quick
```

## 使用场景

### 场景一：IDE 保存时触发

在 VS Code 中配置 `tasks.json`：

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Quick Review",
      "type": "shell",
      "command": "gitconsistency review file ${file} --quick",
      "group": "build",
      "presentation": {
        "panel": "shared"
      }
    }
  ]
}
```

绑定到快捷键：`Ctrl+Shift+R`

### 场景二：pre-commit 钩子

`.pre-commit-hooks.yaml`：

```yaml
- repo: local
  hooks:
    - id: gitconsistency-diff
      name: GitConsistency Review
      entry: gitconsistency review diff --quick
      language: system
      pass_filenames: false
      always_run: true
```

### 场景三：GitHub Actions

```yaml
name: Quick Review

on:
  pull_request:
    types: [synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install git-consistency
      - run: gitconsistency review diff --target ${{ github.base_ref }}
```

## 快速模式 vs 完整模式

| 特性 | 快速模式 `--quick` | 完整模式 |
|------|-------------------|---------|
| 运行时间 | < 2s | 5-15s |
| 审查 Agent | SecurityAgent | Security + Logic + Style |
| 适用场景 | 保存时、频繁提交 | 提交前检查 |
| 问题深度 | 关键安全问题 | 全面的代码质量 |
| 误报率 | 较低 | 中等 |

## 多 Agent 架构

```
ReviewSupervisor (协调器)
    ├── SecurityAgent (安全检查)
    ├── LogicAgent (逻辑分析) - 完整模式
    ├── StyleAgent (风格检查) - 完整模式
    └── SynthesisAgent (结果汇总)
```

## 输出示例

### 快速模式

```
🔍 正在审查 main.py (快速模式)...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
main.py 审查结果
未发现关键问题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ 未发现明显问题
```

### 发现问题

```
🔍 正在审查 main.py (完整模式)...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
main.py 审查结果
发现 3 个问题：1 个关键，2 个建议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
严重级别    类别        行号    描述
─────────  ─────────  ─────  ──────────────────
HIGH       security     15    检测到 eval() 调用
MEDIUM     logic        42    函数复杂度过高
LOW        style        28    变量名不符合规范
```

## 配置

环境变量：

```bash
# 设置快速模式为默认
export CONSISTENCY_QUICK_MODE=true

# 禁用 GitNexus（离线模式）
export CONSISTENCY_GITNEXUS_ENABLED=false
```

## 性能数据

在典型项目中（100 个文件，~5000 行代码）：

| 操作 | 快速模式 | 完整模式 |
|------|---------|---------|
| 单文件审查 | ~800ms | ~3s |
| diff 审查（10 文件） | ~2s | ~8s |
| 批量审查（50 文件） | ~10s | ~45s |

## 与其他工具集成

### 与 pre-commit 集成

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: gitconsistency-quick
        name: Quick Security Review
        entry: gitconsistency review diff --quick
        language: system
        pass_filenames: false
        stages: [commit]
```

### 与 Makefile 集成

```makefile
review-quick:
	gitconsistency review diff --quick

review-full:
	gitconsistency review diff

review-file:
	gitconsistency review file $(FILE) --quick
```
