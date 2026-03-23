# 安装指南

详细安装说明。

## 系统要求

- **Python**: 3.12 或更高版本
- **操作系统**: Linux, macOS, Windows (WSL 推荐)
- **内存**: 至少 4GB RAM（推荐 8GB）
- **磁盘**: 至少 500MB 可用空间

## 安装方式

### 方式一：使用 pip 安装（推荐用户）

```bash
# 完整功能
pip install "git-consistency[full]"

# 按需安装
pip install "git-consistency[security]"    # 仅安全扫描
pip install "git-consistency[ai]"          # 包含 AI 审查
pip install "git-consistency[github]"      # 包含 GitHub 集成
```

### 方式二：使用 uv 安装（推荐开发者）

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 使用 uv 安装
uv pip install "git-consistency[full]"
```

### 方式三：从源码安装

```bash
# 克隆仓库
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency

# 使用 uv 安装（推荐）
uv venv
uv pip install -e ".[full,dev]"

# 或使用 pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[full,dev]"
```

### 方式四：使用 Docker

```bash
# 本地构建
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency
docker-compose build
```

## 验证安装

```bash
# 检查版本
gitconsistency --version

# 检查配置
gitconsistency config validate

# 运行帮助
gitconsistency --help
```

## 配置

### 1. 初始化配置

```bash
cd your-project
gitconsistency init
```

这将创建：
- `.env` - 环境变量配置文件
- `.github/workflows/consistency.yml` - GitHub Actions 工作流

### 2. 编辑 `.env` 文件

```bash
# 必需配置
LITELLM_API_KEY=your_litellm_api_key_here
GITHUB_TOKEN=ghp_your_github_token_here

# 可选配置
LITELLM_MODEL=deepseek/deepseek-chat
SEMGREP_RULES=p/security-audit p/owasp-top-ten
```

### 3. 获取 API 密钥

#### LiteLLM API Key
- 访问 [DeepSeek](https://platform.deepseek.com/) 或其他 LLM 提供商
- 创建 API Key
- 复制到 `.env` 文件

#### GitHub Token
- 访问 GitHub Settings → Developer settings → Personal access tokens
- 生成 Token，勾选 `repo` 权限
- 复制到 `.env` 文件

## 常见问题

### Q: 安装时出现权限错误

```bash
# 使用 --user 安装
pip install --user "git-consistency[full]"

# 或使用 uv（不需要 sudo）
uv pip install "git-consistency[full]"
```

### Q: Windows 上安装失败

推荐使用 WSL2：
```bash
# 在 WSL2 Ubuntu 中
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
pip install "git-consistency[full]"
```

### Q: Docker 构建失败

```bash
# 确保 Docker 版本 >= 20.10
docker --version

# 清理缓存重试
docker-compose build --no-cache
```

### Q: 找不到命令

```bash
# 检查 PATH
echo $PATH

# 如果是用户安装，添加本地 bin 到 PATH
export PATH="$HOME/.local/bin:$PATH"
```

## 卸载

```bash
pip uninstall git-consistency

# 清理缓存
rm -rf ~/.cache/gitconsistency
rm -rf .cache/gitnexus
```

## 获取帮助

- 🐛 Issues：https://github.com/sk1ua/GitConsistency/issues
- 💬 Discussions：https://github.com/sk1ua/GitConsistency/discussions
