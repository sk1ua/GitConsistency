# GitConsistency 示例项目

这是一个故意包含代码问题的示例项目，用于演示 GitConsistency 的检测能力。

## 包含的问题

### 安全问题 (Security Issues)

1. **硬编码密码** (Line 11)
   - `DEFAULT_PASSWORD = "admin123"`
   - 检测工具：Bandit

2. **使用 eval** (Line 15)
   - `eval(user_input)`
   - 检测工具：Bandit, Semgrep

3. **命令注入风险** (Line 21)
   - `subprocess.call(cmd, shell=True)`
   - 检测工具：Bandit, Semgrep

4. **硬编码凭证比较** (Line 33)
   - `password == DEFAULT_PASSWORD`
   - 检测工具：Bandit

5. **敏感信息打印** (Line 58)
   - 打印包含密码的数据库 URL
   - 检测工具：Bandit

### 代码质量问题 (Code Quality Issues)

6. **未使用的导入** (Line 26)
   - `import json`
   - 检测工具：Ruff, Pylint

7. **复杂条件** (Line 44)
   - 多层嵌套的 if-elif-else
   - 检测工具：AI Review

## 运行分析

```bash
# 进入示例项目目录
cd examples/sample-project

# 运行 GitConsistency 分析
gitconsistency analyze . --skip-ai

# 或带 AI 审查（需要 API 密钥）
gitconsistency analyze .
```

## 预期输出

GitConsistency 应该能够检测到：
- 至少 5 个安全问题（Bandit + Semgrep）
- 代码质量问题（如果启用 AI 审查）

生成的报告将包含：
- 问题详情和位置
- 严重级别分类
- 修复建议
