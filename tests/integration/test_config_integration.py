"""配置集成测试.

测试配置系统与各个模块的集成。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from consistency.config import Settings, get_settings
from consistency.exceptions import ConfigError


class TestConfigIntegration:
    """配置集成测试."""

    def test_default_settings(self) -> None:
        """测试默认配置."""
        settings = get_settings()

        assert settings.project_name == "GitConsistency"
        assert settings.version == "0.1.0"
        assert settings.litellm_model == "deepseek/deepseek-chat"
        assert settings.github_delete_old_comments is True

    def test_env_file_loading(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """测试 .env 文件加载."""
        env_file = tmp_path / ".env"
        # 使用嵌套分隔符 __ 设置嵌套配置
        env_file.write_text("""
CONSISTENCY_LLM__MODEL=test-model
CONSISTENCY_LOGGING__LEVEL=DEBUG
""")

        # 创建新的 settings 实例，强制重新加载
        settings = Settings(_env_file=str(env_file))

        assert settings.llm.model == "test-model"
        assert settings.logging.level == "DEBUG"

    def test_github_signature_format(self) -> None:
        """测试 GitHub 评论签名格式."""
        settings = get_settings()

        assert "GitConsistency" in settings.github_comment_signature
        assert "<!--" in settings.github_comment_signature
        assert "-->" in settings.github_comment_signature


class TestExceptionHierarchy:
    """异常层次结构测试."""

    def test_base_exception(self) -> None:
        """测试基础异常."""
        from consistency.exceptions import GitConsistencyError

        exc = GitConsistencyError("Test error", error_code="TEST_ERROR")
        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert "TEST_ERROR" in str(exc)

    def test_config_error(self) -> None:
        """测试配置错误."""
        exc = ConfigError("Invalid config", details={"field": "api_key"})
        assert exc.error_code == "CONFIG_ERROR"
        assert exc.details["field"] == "api_key"

    def test_github_error_with_status(self) -> None:
        """测试 GitHub 错误带状态码."""
        from consistency.exceptions import GitHubError

        exc = GitHubError("API Error", status_code=404, details={"repo": "test"})
        assert exc.error_code == "GITHUB_ERROR"
        assert exc.status_code == 404

    def test_ai_review_error_with_model(self) -> None:
        """测试 AI 审查错误带模型信息."""
        from consistency.exceptions import AIReviewError

        exc = AIReviewError("Model failed", model="deepseek-chat", details={"timeout": 30})
        assert exc.error_code == "AI_REVIEW_ERROR"
        assert exc.model == "deepseek-chat"
