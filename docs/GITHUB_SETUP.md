# GitHub 集成配置指南

配置 GitHub Actions 和 Secrets。

## 🔐 必需配置

### 1. GitHub Token (自动提供)

`GITHUB_TOKEN` 由 GitHub Actions 自动提供，无需手动设置。

---

## 🤖 可选配置（推荐）

### 2. LiteLLM API Key (用于 AI 审查)

**作用**：让 AI 分析代码并提供审查意见

**获取方式**：
1. 访问 [DeepSeek 平台](https://platform.deepseek.com/)
2. 注册账号并充值
3. 创建 API Key
4. 复制 Key

**配置步骤**：
1. 打开仓库页面 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name: `LITELLM_API_KEY`
4. Secret: 粘贴你的 API Key
5. 点击 **Add secret**

### 3. LiteLLM_MODEL (可选，推荐设置)

**作用**：指定使用的 AI 模型

**配置步骤**：
1. 打开仓库页面 → **Settings** → **Secrets and variables** → **Actions**
2. 切换到 **Variables** 标签
3. 点击 **New repository variable**
4. Name: `LITELLM_MODEL`
5. Value: `deepseek/deepseek-chat` (或其他模型)
6. 点击 **Add variable**

**支持的模型**：
| 模型 | Value |
|------|-------|
| DeepSeek | `deepseek/deepseek-chat` |
| Claude 3.5 Sonnet | `anthropic/claude-3-5-sonnet-20241022` |
| GPT-4 | `openai/gpt-4` |
| Grok | `xai/grok-beta` |

### 4. 备选模型 (可选)

**作用**：主模型失败时自动切换

配置变量：
- Name: `LITELLM_FALLBACK_MODEL`
- Value: `anthropic/claude-3-haiku-20240307`

---

## 🔧 高级配置（可选）

### 5. GitNexus MCP URL

**作用**：连接代码知识图谱服务

**配置步骤**：
1. 如果你有自托管的 GitNexus MCP 服务
2. 添加 Secret: `GITNEXUS_MCP_URL`
3. Value: `http://your-server:3000/sse`

---

## 📊 配置检查清单

| 配置项 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `GITHUB_TOKEN` | Secret | ✅ 自动 | GitHub 自动提供 |
| `LITELLM_API_KEY` | Secret | ❌ 推荐 | LLM API 密钥 |
| `LITELLM_MODEL` | Variable | ❌ 可选 | AI 模型选择 |
| `LITELLM_FALLBACK_MODEL` | Variable | ❌ 可选 | 备选模型 |
| `GITNEXUS_MCP_URL` | Secret | ❌ 可选 | 代码图谱服务 |

---

## 🧪 测试配置

配置完成后，可以手动触发工作流测试：

1. 打开仓库 → **Actions** → **GitConsistency Code Review**
2. 点击 **Run workflow**
3. 选择分支
4. 点击 **Run workflow**

查看运行日志确认：
- ✅ `✅ LLM API Key 已配置，将启用 AI 审查`
- 或 `⚠️ 未配置 LLM API Key，跳过 AI 审查`

---

## 💡 费用参考

使用 DeepSeek API 的费用（仅供参考）：

| 操作 | 费用 |
|------|------|
| 单次 PR 审查 | ~￥0.01-0.1 |
| 月度 100 次 PR | ~￥1-10 |

**省钱技巧**：
- 小项目可以不配置 API Key，只使用安全扫描和静态分析
- 大项目建议配置，AI 能发现更多问题

---

## 🔒 安全提醒

⚠️ **永远不要**：
- 把 API Key 直接写在代码里
- 把 API Key 提交到 Git
- 在日志中打印 API Key

✅ **Secrets 的优势**：
- 加密存储
- 不会出现在日志中
- 只在运行时可用

---

## 🆘 常见问题

### Q: 配置了 API Key 但 AI 审查没运行？

检查：
1. Secret 名称是否正确：`LITELLM_API_KEY`
2. 是否有拼写错误
3. 查看 Actions 日志是否有 `✅ LLM API Key 已配置`

### Q: API Key 泄露了怎么办？

1. 立即到 DeepSeek/OpenAI 平台删除该 Key
2. 在 GitHub 删除该 Secret
3. 创建新的 API Key
4. 重新添加到 GitHub Secrets

### Q: 可以不配置 API Key 吗？

可以！项目会：
- ✅ 正常运行安全扫描（Semgrep + Bandit）
- ✅ 正常运行漂移检测
- ✅ 正常运行热点分析
- ❌ 跳过 AI 代码审查

---

## 📚 相关文档

- [LiteLLM 文档](https://docs.litellm.ai/)
- [DeepSeek API](https://platform.deepseek.com/)
- [GitHub Secrets 文档](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
