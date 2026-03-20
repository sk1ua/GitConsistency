"""Dashboard 配置.

Streamlit 配置和部署支持.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any



class DashboardConfig:
    """Dashboard 配置管理."""

    # 默认配置
    DEFAULTS = {
        "page_title": "ConsistenCy Dashboard",
        "page_icon": "🔍",
        "layout": "wide",
        "initial_sidebar_state": "expanded",
        "theme_primary_color": "#0366d6",
        "max_findings_display": 100,
        "history_limit": 100,
        "default_project_path": ".",
    }

    @classmethod
    def load(cls) -> dict[str, Any]:
        """加载配置."""
        # 尝试从文件加载
        config_file = Path(".consistancy-dashboard.toml")
        if config_file.exists():
            try:
                import tomllib
                with open(config_file, "rb") as f:
                    return {**cls.DEFAULTS, **tomllib.load(f)}
            except Exception:
                pass

        return cls.DEFAULTS.copy()

    @classmethod
    def save(cls, config: dict[str, Any]) -> None:
        """保存配置."""
        config_file = Path(".consistancy-dashboard.toml")
        try:
            import tomli_w
            with open(config_file, "wb") as f:
                tomli_w.dump(config, f)
        except Exception:
            pass


# Streamlit 配置 (保存到 .streamlit/config.toml)
STREAMLIT_CONFIG = """
[theme]
primaryColor = "#0366d6"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f6f8fa"
textColor = "#24292e"
font = "sans serif"

[server]
headless = true
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
"""


def setup_streamlit_config() -> None:
    """设置 Streamlit 配置."""
    streamlit_dir = Path(".streamlit")
    streamlit_dir.mkdir(exist_ok=True)

    config_file = streamlit_dir / "config.toml"
    if not config_file.exists():
        config_file.write_text(STREAMLIT_CONFIG.strip())


def get_deploy_instructions() -> str:
    """获取部署说明."""
    return """
# 🚀 Dashboard 部署指南

## 本地运行

```bash
# 安装依赖
pip install streamlit plotly

# 运行 Dashboard
streamlit run consistancy/dashboard/app.py
```

## Streamlit Community Cloud 部署

1. 推送代码到 GitHub
2. 访问 https://share.streamlit.io
3. 选择仓库和 `consistancy/dashboard/app.py`
4. 添加 Secrets:
   - `LITELLM_API_KEY`
   - `GITHUB_TOKEN`

## Docker 部署

```bash
docker-compose up dashboard
```

访问 http://localhost:8501

## 环境变量

| 变量 | 说明 |
|------|------|
| `STREAMLIT_PORT` | 端口 (默认 8501) |
| `STREAMLIT_SERVER_ADDRESS` | 绑定地址 |
| `DASHBOARD_DATA_DIR` | 数据目录 |
| `DASHBOARD_REALTIME` | 实时模式 |
"""
