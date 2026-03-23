"""配置模块单元测试."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from consistency.config import Settings, get_settings, reload_settings


class TestSettings:
    """Settings 类测试."""

    def test_default_values(self) -> None:
        """测试默认值."""
        settings = Settings()
        assert settings.project_name == "GitConsistency"
        assert settings.version == "0.1.0"
        assert settings.litellm_temperature == 0.3

    def test_litellm_model_default(self) -> None:
        """测试 LLM 模型默认值."""
        settings = Settings()
        assert settings.litellm_model == "deepseek/deepseek-chat"

    def test_sensitivity_validation(self) -> None:
        """测试敏感字段验证."""
        # 空白字符应该被去除
        settings = Settings(litellm_api_key="  key123  ")
        assert settings.litellm_api_key == "key123"

        # None 保持不变
        settings = Settings(litellm_api_key=None)
        assert settings.litellm_api_key is None

    def test_path_validation(self) -> None:
        """测试路径字段验证."""
        settings = Settings(cache_dir="/tmp/test_cache")
        assert isinstance(settings.cache_dir, Path)
        assert settings.cache_dir == Path("/tmp/test_cache")

    def test_temperature_range(self) -> None:
        """测试温度范围验证."""
        # 有效范围
        settings = Settings(litellm_temperature=0.5)
        assert settings.litellm_temperature == 0.5

        # 超出范围应该失败
        with pytest.raises(ValidationError):
            Settings(litellm_temperature=1.5)

        with pytest.raises(ValidationError):
            Settings(litellm_temperature=-0.1)

    def test_semgrep_rules_parsing(self) -> None:
        """测试 Semgrep 规则解析."""
        # 字符串格式
        settings = Settings(semgrep_rules="rule1, rule2, rule3")
        assert settings.semgrep_rules == ["rule1", "rule2", "rule3"]

        # 列表格式
        settings = Settings(semgrep_rules=["a", "b"])
        assert settings.semgrep_rules == ["a", "b"]

    def test_is_configured_properties(self) -> None:
        """测试配置状态属性."""
        # 未配置
        settings = Settings()
        assert not settings.is_litellm_configured
        assert not settings.is_github_configured
        assert not settings.is_gitnexus_configured

        # 已配置
        settings = Settings(
            litellm_api_key="test",
            github_token="test",
            gitnexus_mcp_url="http://localhost",
        )
        assert settings.is_litellm_configured
        assert settings.is_github_configured
        assert settings.is_gitnexus_configured

    def test_effective_worker_threads(self) -> None:
        """测试有效工作线程数计算."""
        # 自动计算
        settings = Settings(worker_threads=0)
        assert settings.effective_worker_threads > 0

        # 指定值
        settings = Settings(worker_threads=8)
        assert settings.effective_worker_threads == 8


class TestGetSettings:
    """get_settings 函数测试."""

    def test_singleton(self) -> None:
        """测试单例模式."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload(self) -> None:
        """测试重新加载."""
        settings1 = get_settings()
        settings2 = reload_settings()
        assert settings1 is not settings2
        # 重新加载后缓存应该被清除，再次获取应该是新的实例
        settings3 = get_settings()
        assert settings2 is settings3


class TestEnvironmentVariables:
    """环境变量测试."""

    def test_env_file_loading(self, tmp_path: Path) -> None:
        """测试从 .env 文件加载."""
        env_file = tmp_path / ".env"
        env_file.write_text("CONSISTENCY_LITELLM_MODEL=test-model\nCONSISTENCY_LOG_LEVEL=DEBUG")

        settings = Settings(_env_file=str(env_file))
        assert settings.litellm_model == "test-model"
        assert settings.log_level == "DEBUG"

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试环境变量覆盖."""
        monkeypatch.setenv("CONSISTENCY_LITELLM_MODEL", "env-model")
        monkeypatch.setenv("CONSISTENCY_LOG_LEVEL", "ERROR")

        reload_settings()
        settings = get_settings()

        assert settings.litellm_model == "env-model"
        assert settings.log_level == "ERROR"

        # 清理
        monkeypatch.delenv("CONSISTENCY_LITELLM_MODEL", raising=False)
        monkeypatch.delenv("CONSISTENCY_LOG_LEVEL", raising=False)
        reload_settings()
