# Data Model: GitConsistency

**Feature**: GitConsistency - Code Security & AI Review Tool
**Date**: 2026-03-25

---

## Core Entities

### 1. Finding (安全扫描结果)

安全扫描器（Semgrep/Bandit）发现的问题。

```python
@dataclass
class Finding:
    """安全扫描发现的问题"""

    # 标识信息
    rule_id: str                    # 规则标识，如 "python.sql.security.audit"
    message: str                    # 问题描述（人类可读）

    # 严重程度
    severity: Severity              # 枚举: CRITICAL, HIGH, MEDIUM, LOW, INFO

    # 位置信息
    file_path: Path | None          # 文件路径
    line: int | None                # 行号（1-based）
    column: int | None              # 列号（1-based）

    # 代码上下文
    code_snippet: str | None        # 相关代码片段

    # 元数据
    confidence: float               # 置信度 0.0-1.0
    metadata: dict[str, Any]        # 扩展信息:
                                    #   - cwe: CWE 编号列表
                                    #   - owasp: OWASP 分类
                                    #   - fix: 修复建议
                                    #   - references: 参考链接
```

**Validation Rules**:
- `severity` 必须是预定义枚举值之一
- `confidence` 范围 0.0-1.0
- `line` 和 `column` 如果存在必须 >= 1

---

### 2. ReviewComment (AI 审查评论)

AI Agent 生成的代码审查评论。

```python
class ReviewComment(BaseModel):
    """AI 审查生成的评论"""

    # 位置
    file: str | None                # 文件路径（可选，用于整体评论）
    line: int | None                # 行号（可选）

    # 内容
    message: str                    # 评论内容（必需）
    suggestion: str | None          # 改进建议/代码建议

    # 分类
    severity: Severity              # 严重程度
    category: CommentCategory       # 枚举: SECURITY, LOGIC, STYLE, GENERAL

    # 可信度
    confidence: float               # 置信度 0.0-1.0（AI 对评论的确信程度）
```

**Categories**:
- `SECURITY`: 安全问题（SQL 注入、XSS、硬编码密钥等）
- `LOGIC`: 逻辑问题（空函数、裸 except、复杂函数等）
- `STYLE`: 风格问题（命名规范、文档字符串等）
- `GENERAL`: 一般性建议

---

### 3. ReviewResult (审查结果汇总)

单次审查的完整结果。

```python
class ReviewResult(BaseModel):
    """审查结果汇总"""

    # 摘要
    summary: str                    # 整体评估摘要（1-2 句话）
    severity: Severity              # 总体严重级别（最高级别）

    # 详细结果
    comments: list[ReviewComment]   # 评论列表（最多 20 条）
    action_items: list[str]         # 行动项列表（最多 10 条）

    # 元数据
    metadata: dict[str, Any]        # 审查元数据:
                                    #   - duration_ms: 总耗时
                                    #   - agent_results: 各 Agent 结果
                                    #   - file_count: 审查文件数
                                    #   - quick_mode: 是否快速模式
```

---

### 4. AgentResult (Agent 执行结果)

单个 Agent 的分析结果。

```python
@dataclass
class AgentResult:
    """Agent 执行结果"""

    # 标识
    agent_name: str                 # Agent 名称（Security/Logic/Style）

    # 结果
    summary: str                    # 结果摘要
    severity: Severity              # 最高严重级别
    comments: list[ReviewComment]   # 生成的评论
    action_items: list[str]         # 行动建议

    # 元数据
    metadata: dict[str, Any]        # Agent 特定数据
    duration_ms: float              # 执行耗时（毫秒）
```

---

### 5. ScanResult (扫描结果)

安全扫描的完整结果。

```python
@dataclass
class ScanResult:
    """安全扫描结果"""

    # 扫描发现
    findings: list[Finding]         # 发现的问题列表

    # 扫描统计
    scanned_files: list[Path]       # 扫描的文件列表
    error_files: list[tuple[Path, str]]  # 错误文件及原因

    # 元数据
    metadata: dict[str, Any]        # 扫描元数据:
                                    #   - duration_ms: 总耗时
                                    #   - scanner_versions: 扫描器版本
                                    #   - rules_applied: 应用的规则集
```

---

## Enumerations

### Severity (严重级别)

```python
class Severity(Enum):
    CRITICAL = "critical"    # 严重漏洞，必须立即修复
    HIGH = "high"            # 高危问题，尽快修复
    MEDIUM = "medium"        # 中等问题，计划修复
    LOW = "low"              # 低危问题，建议修复
    INFO = "info"            # 信息性提示
```

**排序**: CRITICAL > HIGH > MEDIUM > LOW > INFO

---

### CommentCategory (评论类别)

```python
class CommentCategory(Enum):
    SECURITY = "security"    # 安全问题
    LOGIC = "logic"          # 逻辑问题
    STYLE = "style"          # 风格问题
    GENERAL = "general"      # 一般建议
```

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    ScanResult                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  findings: list[Finding]                            │   │
│  │    ├── rule_id, severity, file_path, line, message │   │
│  │    └── metadata: {cwe, owasp, fix, references}     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ReviewResult                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  comments: list[ReviewComment]                      │   │
│  │    ├── file, line, message, suggestion             │   │
│  │    ├── severity, category, confidence              │   │
│  │    └── category ∈ {SECURITY, LOGIC, STYLE}         │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  action_items: list[str]                            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│                  AgentResult (x3)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │SecurityAgent │ │ LogicAgent   │ │ StyleAgent   │        │
│  │  - security  │ │  - logic     │ │  - style     │        │
│  │  findings    │ │  issues      │ │  issues      │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 SynthesisAgent                               │
│         (aggregate, deduplicate, rank)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## State Transitions

### Review Flow

```
[Code Input]
     │
     ▼
[SecurityScanner] ──(parallel)──► [Finding list]
     │                                    │
     ▼                                    ▼
[ReviewSupervisor]              [Agent Results]
     │                                    │
     ├──► [SecurityAgent] ───────────────┤
     ├──► [LogicAgent]    ───────────────┤
     └──► [StyleAgent]    ───────────────┘
     │
     ▼
[SynthesisAgent] ──► [ReviewResult]
     │
     ▼
[ReportGenerator] ──► [Markdown/HTML/JSON]
```

---

## Configuration Model

### Settings (全局配置)

```python
class Settings(BaseSettings):
    """全局配置（Pydantic Settings）"""

    # LLM 配置
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # GitHub 配置
    github: GitHubConfig = Field(default_factory=GitHubConfig)

    # GitNexus 配置
    gitnexus: GitNexusConfig = Field(default_factory=GitNexusConfig)

    # 扫描器配置
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)

    # 缓存配置
    cache: CacheConfig = Field(default_factory=CacheConfig)
```

### LLMConfig

```python
class LLMConfig(BaseModel):
    """LLM 配置"""
    model: str = "deepseek/deepseek-chat"
    api_key: str | None = None
    temperature: float = 0.1
    max_tokens: int = 4096
```

### GitHubConfig

```python
class GitHubConfig(BaseModel):
    """GitHub 配置"""
    token: str | None = None
    max_concurrent: int = 5
    comment_signature: str = "<!-- GitConsistency Code Review -->"
```

### ScannerConfig

```python
class ScannerConfig(BaseModel):
    """扫描器配置"""
    semgrep_rules: list[str] = ["p/security-audit", "p/owasp-top-ten"]
    bandit_severity: str = "LOW"
```

### CacheConfig

```python
class CacheConfig(BaseModel):
    """缓存配置"""
    dir: Path = Path(".cache")
    ttl: int = 3600  # 秒
    maxsize: int = 128
```

---

## Data Flow Summary

| 阶段 | 输入 | 处理 | 输出 |
|------|------|------|------|
| 安全扫描 | 文件路径/代码 | Semgrep + Bandit | `list[Finding]` |
| AI 审查 | 文件路径/代码 | Multi-Agent | `list[AgentResult]` |
| 结果综合 | Agent 结果 | SynthesisAgent | `ReviewResult` |
| 报告生成 | ScanResult + ReviewResult | LLM + 模板 | Markdown/HTML/JSON |
