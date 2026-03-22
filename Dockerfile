# ConsistenCy 2.0 - 代码安全扫描与 AI 审查
# 多阶段构建，优化镜像大小和安全性

# ==================== 构建阶段 ====================
FROM python:3.12-slim-bookworm AS builder

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（超快包管理器）
RUN pip install --no-cache-dir uv

# 设置工作目录
WORKDIR /build

# 复制依赖定义
COPY pyproject.toml ./

# 创建虚拟环境并安装依赖
RUN uv venv /opt/venv && \
    uv pip install --no-cache -e "." --python /opt/venv/bin/python

# 复制源代码
COPY consistancy/ ./consistancy/

# 安装项目本身
RUN uv pip install --no-cache -e . --python /opt/venv/bin/python

# ==================== 生产阶段 ====================
FROM python:3.12-slim-bookworm AS production

# 安全：创建非 root 用户
RUN groupadd -r consistancy && useradd -r -g consistancy consistancy

# 安装运行时依赖（semgrep 需要 git）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置环境变量
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 设置工作目录
WORKDIR /app

# 创建缓存目录并设置权限
RUN mkdir -p /app/.cache && chown -R consistancy:consistancy /app

# 切换到非 root 用户
USER consistancy

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD consistancy --help || exit 1

# 默认命令
ENTRYPOINT ["consistancy"]
CMD ["--help"]

# ==================== 开发阶段 ====================
FROM builder AS development

WORKDIR /app

# 安装开发依赖
RUN uv pip install --no-cache -e ".[dev]" --python /opt/venv/bin/python

ENV PATH="/opt/venv/bin:$PATH"

# 安装 pre-commit hooks
COPY .pre-commit-config.yaml ./
RUN git init && pre-commit install-hooks || true

CMD ["bash"]
