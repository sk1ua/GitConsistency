# GitNexus 集成说明

## 概述

GitConsistency 已集成 GitNexus，为 AI 代码审查提供额外的代码上下文信息。

## 前置要求

```bash
# 安装 GitNexus
npm install -g gitnexus

# 验证安装
gitnexus --version
```

## 工作原理

1. **代码分析**：首次运行时会调用 `gitnexus analyze` 构建知识图谱
2. **上下文获取**：审查代码时自动提取符号（函数/类/方法）
3. **Prompt 增强**：将调用关系、依赖信息添加到 AI Prompt

## 使用示例

```python
from consistency.core.gitnexus_client import get_gitnexus_client

# 获取 GitNexus 客户端
client = get_gitnexus_client()

# 分析代码库
await client.analyze("/path/to/repo")

# 获取符号上下文
context = await client.get_context("validate_user")
print(context.callers)   # 谁调用了这个函数
print(context.callees)   # 这个函数调用了谁
```

## 配置文件

```bash
# .env
CONSISTENCY_GITNEXUS_CACHE_DIR=.cache/gitnexus
```

## 禁用 GitNexus

如果未安装 gitnexus，系统会自动跳过上下文增强，不影响正常审查功能。

## 性能优化

- 知识图谱默认缓存 1 小时
- 大型代码库首次分析可能需要几分钟
- 建议在使用前手动运行 `gitnexus analyze`
