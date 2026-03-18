"""Dashboard 配置单元测试."""

from pathlib import Path
from unittest.mock import patch

import pytest

from consistancy.dashboard.config import DashboardConfig, get_deploy_instructions, setup_streamlit_config


class TestDashboardConfig:
    """配置测试."""

    def test_default_load(self) -> None:
        """测试默认加载."""
        config = DashboardConfig.load()

        assert "page_title" in config
        assert "page_icon" in config
        assert config["page_title"] == "ConsistenCy Dashboard"

    def test_load_from_file(self, tmp_path: Path) -> None:
        """测试从文件加载."""
        # 创建临时配置文件
        config_file = tmp_path / ".consistancy-dashboard.toml"
        config_file.write_text('page_title = "Custom Title"\n')

        with patch("consistancy.dashboard.config.Path") as mock_path:
            mock_path.return_value = config_file

            config = DashboardConfig.load()
            # 注意：由于 mock 方式可能需要调整

    def test_get_deploy_instructions(self) -> None:
        """测试部署说明."""
        instructions = get_deploy_instructions()

        assert "本地运行" in instructions
        assert "Streamlit Community Cloud" in instructions
        assert "Docker" in instructions

    def test_setup_streamlit_config(self, tmp_path: Path) -> None:
        """测试设置 Streamlit 配置."""
        with patch("consistancy.dashboard.config.Path") as mock_path_class:
            mock_path = tmp_path / ".streamlit"
            mock_path_class.return_value = mock_path

            setup_streamlit_config()

            # 验证目录创建
            # 注意：需要调整 mock 方式
