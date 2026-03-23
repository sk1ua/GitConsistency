"""GitConsistency 异常层次结构.

提供结构化的异常分类，便于错误处理和可观测性。
"""

from __future__ import annotations


class GitConsistencyError(Exception):
    """GitConsistency 基础异常类.

    所有自定义异常的基类，包含错误码和详细信息。
    """

    def __init__(self, message: str, error_code: str | None = None, details: dict | None = None) -> None:
        """初始化异常.

        Args:
            message: 错误信息
            error_code: 错误码，用于程序识别
            details: 详细错误信息
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"[{self.error_code}] {self.message} - {self.details}"
        return f"[{self.error_code}] {self.message}"


# =============================================================================
# 配置相关异常
# =============================================================================


class ConfigError(GitConsistencyError):
    """配置错误.

    环境变量、.env 文件或配置值无效时抛出。
    """

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, error_code="CONFIG_ERROR", details=details)


class ValidationError(GitConsistencyError):
    """配置验证错误.

    配置值不符合要求时抛出。
    """

    def __init__(self, message: str, field: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, error_code="VALIDATION_ERROR", details=details)
        self.field = field


# =============================================================================
# 扫描相关异常
# =============================================================================


class ScanError(GitConsistencyError):
    """扫描错误.

    安全扫描过程中发生错误时抛出。
    """

    def __init__(self, message: str, scanner: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, error_code="SCAN_ERROR", details=details)
        self.scanner = scanner


class ScannerNotFoundError(ScanError):
    """扫描器未找到.

    请求的扫描器不存在时抛出。
    """

    def __init__(self, scanner: str, details: dict | None = None) -> None:
        super().__init__(f"扫描器未找到: {scanner}", scanner=scanner, details=details)
        self.error_code = "SCANNER_NOT_FOUND"


class SemgrepError(ScanError):
    """Semgrep 扫描错误."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, scanner="semgrep", details=details)
        self.error_code = "SEMGREP_ERROR"


class BanditError(ScanError):
    """Bandit 扫描错误."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, scanner="bandit", details=details)
        self.error_code = "BANDIT_ERROR"


# =============================================================================
# GitHub 集成相关异常
# =============================================================================


class GitHubError(GitConsistencyError):
    """GitHub 集成错误.

    与 GitHub API 交互时发生错误。
    """

    def __init__(self, message: str, status_code: int | None = None, details: dict | None = None) -> None:
        super().__init__(message, error_code="GITHUB_ERROR", details=details)
        self.status_code = status_code


class GitHubAuthError(GitHubError):
    """GitHub 认证错误.

    Token 无效或权限不足时抛出。
    """

    def __init__(self, message: str = "GitHub 认证失败", details: dict | None = None) -> None:
        super().__init__(message, status_code=401, details=details)
        self.error_code = "GITHUB_AUTH_ERROR"


class GitHubRateLimitError(GitHubError):
    """GitHub 速率限制错误."""

    def __init__(
        self,
        message: str = "GitHub API 速率限制",
        reset_at: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, status_code=429, details=details)
        self.error_code = "GITHUB_RATE_LIMIT"
        self.reset_at = reset_at


class GitHubNotFoundError(GitHubError):
    """GitHub 资源未找到."""

    def __init__(self, resource: str, details: dict | None = None) -> None:
        super().__init__(f"资源未找到: {resource}", status_code=404, details=details)
        self.error_code = "GITHUB_NOT_FOUND"
        self.resource = resource


# =============================================================================
# AI 审查相关异常
# =============================================================================


class AIReviewError(GitConsistencyError):
    """AI 审查错误.

    LLM 调用或审查过程中发生错误。
    """

    def __init__(self, message: str, model: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, error_code="AI_REVIEW_ERROR", details=details)
        self.model = model


class LLMConnectionError(AIReviewError):
    """LLM 连接错误.

    无法连接到 LLM API 时抛出。
    """

    def __init__(self, message: str = "LLM 连接失败", model: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, model=model, details=details)
        self.error_code = "LLM_CONNECTION_ERROR"


class LLMRateLimitError(AIReviewError):
    """LLM 速率限制错误."""

    def __init__(
        self,
        message: str = "LLM API 速率限制",
        model: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, model=model, details=details)
        self.error_code = "LLM_RATE_LIMIT"


class LLMTimeoutError(AIReviewError):
    """LLM 超时错误."""

    def __init__(
        self,
        message: str = "LLM 请求超时",
        model: str | None = None,
        timeout: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, model=model, details=details)
        self.error_code = "LLM_TIMEOUT"
        self.timeout = timeout


class PromptError(AIReviewError):
    """Prompt 错误.

    Prompt 渲染或验证失败时抛出。
    """

    def __init__(self, message: str, prompt_name: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, details=details)
        self.error_code = "PROMPT_ERROR"
        self.prompt_name = prompt_name


# =============================================================================
# GitNexus MCP 相关异常
# =============================================================================


class GitNexusError(GitConsistencyError):
    """GitNexus MCP 错误."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, error_code="GITNEXUS_ERROR", details=details)


class GitNexusConnectionError(GitNexusError):
    """GitNexus 连接错误."""

    def __init__(self, message: str = "GitNexus 连接失败", details: dict | None = None) -> None:
        super().__init__(message, details=details)
        self.error_code = "GITNEXUS_CONNECTION_ERROR"


class GitNexusTimeoutError(GitNexusError):
    """GitNexus 超时错误."""

    def __init__(
        self,
        message: str = "GitNexus 请求超时",
        timeout: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.error_code = "GITNEXUS_TIMEOUT"
        self.timeout = timeout


# =============================================================================
# 报告生成相关异常
# =============================================================================


class ReportError(GitConsistencyError):
    """报告生成错误."""

    def __init__(self, message: str, format: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, error_code="REPORT_ERROR", details=details)
        self.format = format


# =============================================================================
# 网络相关异常
# =============================================================================


class NetworkError(GitConsistencyError):
    """网络错误."""

    def __init__(self, message: str, url: str | None = None, details: dict | None = None) -> None:
        super().__init__(message, error_code="NETWORK_ERROR", details=details)
        self.url = url


class TimeoutError(GitConsistencyError):
    """超时错误."""

    def __init__(
        self,
        message: str = "请求超时",
        timeout: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, error_code="TIMEOUT_ERROR", details=details)
        self.timeout = timeout
