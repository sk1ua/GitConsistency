"""配置模块单元测试."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from consistency.config import (
    CacheConfig,
    GitHubConfig,
    GitNexusConfig,
    LLMConfig,
    PerformanceConfig,
    ScannerConfig,
    Settings,
    get_settings,
    reload_settings,
)


class TestSettings:
    """Settings 类测试."""

    def test_default_values(self) -> None:
        """测试默认值."""
        settings = Settings()
        assert settings.project_name == "GitConsistency"
        assert settings.version == "0.1.0"
        assert settings.llm.temperature == 0.3

    def test_litellm_model_default(self) -> None:
        """测试 LLM 模型默认值."""
        settings = Settings()
        assert settings.llm.model == "deepseek/deepseek-chat"

    def test_sensitivity_validation(self) -> None:
        """测试敏感字段验证."""
        # API key 通过 llm config 设置
        llm_config = LLMConfig(api_key="key123")
        settings = Settings(llm=llm_config)
        assert settings.llm.api_key == "key123"

    def test_path_validation(self) -> None:
        """测试路径字段验证."""
        # 通过 cache config 设置
        cache_config = CacheConfig(dir=Path("/tmp/test_cache"))
        settings = Settings(cache=cache_config)
        assert isinstance(settings.cache.dir, Path)

    def test_temperature_range(self) -> None:
        """测试温度范围验证."""
        # 有效范围
        llm_config = LLMConfig(temperature=0.5)
        settings = Settings(llm=llm_config)
        assert settings.llm.temperature == 0.5

        # 超出范围应该失败 - pydantic 会自动验证
        with pytest.raises(ValidationError):
            LLMConfig(temperature=1.5)

    def test_semgrep_rules_parsing(self) -> None:
        """测试 Semgrep 规则解析."""
        # 字符串格式 - 通过 scanner config
        scanner_config = ScannerConfig(semgrep_rules=["rule1", "rule2", "rule3"])
        settings = Settings(scanner=scanner_config)
        assert settings.scanner.semgrep_rules == ["rule1", "rule2", "rule3"]

        # 列表格式
        scanner_config2 = ScannerConfig(semgrep_rules=["a", "b"])
        settings2 = Settings(scanner=scanner_config2)
        assert settings2.scanner.semgrep_rules == ["a", "b"]

    def test_is_configured_properties(self) -> None:
        """测试配置状态属性."""
        # 未配置（默认）
        settings = Settings()
        assert not settings.is_litellm_configured
        assert not settings.is_github_configured
        assert not settings.is_gitnexus_configured

        # 已配置 - 通过 nested config
        settings = Settings(
            llm=LLMConfig(api_key="test"),
            github=GitHubConfig(token="test"),
            gitnexus=GitNexusConfig(mcp_url="http://localhost"),
        )
        assert settings.is_litellm_configured
        assert settings.is_github_configured
        assert settings.is_gitnexus_configured

    def test_effective_worker_threads(self) -> None:
        """测试有效工作线程数计算."""
        # 自动计算
        perf_config = PerformanceConfig(worker_threads=0)
        settings = Settings(performance=perf_config)
        assert settings.effective_worker_threads > 0

        # 指定值
        perf_config2 = PerformanceConfig(worker_threads=8)
        settings2 = Settings(performance=perf_config2)
        assert settings2.effective_worker_threads == 8


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


class TestLLMConfig:
    """LLMConfig 测试."""

    def test_default_values(self) -> None:
        """测试默认值."""
        config = LLMConfig()
        assert config.model == "deepseek/deepseek-chat"
        assert config.temperature == 0.3
        assert config.max_tokens == 4096

    def test_temperature_validation(self) -> None:
        """测试温度范围验证."""
        # 有效值
        config = LLMConfig(temperature=0.5)
        assert config.temperature == 0.5

        # 无效值
        with pytest.raises(ValidationError):
            LLMConfig(temperature=-0.1)
        with pytest.raises(ValidationError):
            LLMConfig(temperature=1.5)


class TestGitHubConfig:
    """GitHubConfig 测试."""

    def test_default_values(self) -> None:
        """测试默认值."""
        config = GitHubConfig()
        assert config.token is None
        assert config.delete_old_comments is True

    def test_custom_values(self) -> None:
        """测试自定义值."""
        config = GitHubConfig(token="ghp_xxx", delete_old_comments=False)
        assert config.token == "ghp_xxx"
        assert config.delete_old_comments is False


class TestScannerConfig:
    """ScannerConfig 测试."""

    def test_default_semgrep_rules(self) -> None:
        """测试默认 Semgrep 规则."""
        config = ScannerConfig()
        assert len(config.semgrep_rules) == 3
        assert "p/security-audit" in config.semgrep_rules

    def test_custom_rules(self) -> None:
        """测试自定义规则."""
        config = ScannerConfig(semgrep_rules=["custom1", "custom2"])
        assert config.semgrep_rules == ["custom1", "custom2"]


class TestCacheConfig:
    """CacheConfig 测试."""

    def test_default_values(self) -> None:
        """测试默认值."""
        config = CacheConfig()
        assert config.dir == Path(".cache")
        assert config.max_size == 1000

    def test_custom_dir(self) -> None:
        """测试自定义目录."""
        config = CacheConfig(dir=Path("/tmp/cache"))
        assert config.dir == Path("/tmp/cache")
