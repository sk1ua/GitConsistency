# Feature Specification: GitConsistency - Code Security & AI Review Tool

**Feature Branch**: `001-gitconsistency-spec`
**Created**: 2026-03-25
**Status**: Draft
**Input**: User description: "为 GitConsistency 项目创建规范文档 - 代码安全扫描与 AI 审查工具"

## Overview

GitConsistency 是一个专为 **vibe coding** / **高频 commit** 场景设计的代码安全扫描与 AI 审查工具。它集成 Semgrep、Bandit 双引擎安全扫描和基于 LiteLLM 的多 Agent AI 审查，为开发者提供快速、准确的代码质量和安全评估。

### Core Value Proposition

- **快速反馈**: 快速模式 <2s 完成关键安全检查
- **深度分析**: 多 Agent 并行审查（安全、逻辑、风格）
- **上下文感知**: 可选 GitNexus 代码图谱增强
- **CI/CD 原生**: GitHub Actions 集成，PR 自动评论

---

## User Scenarios & Testing

### User Story 1 - 本地代码安全扫描 (Priority: P1)

作为开发者，我需要在提交代码前快速检查安全漏洞，以便在问题进入代码库之前修复它们。

**Why this priority**: 安全是代码质量的基础，防止漏洞进入代码库是核心需求。

**Independent Test**: 可以独立测试，运行 `gitconsistency scan security <path>` 并验证是否检测到已知漏洞。

**Acceptance Scenarios**:

1. **Given** 一个包含已知安全漏洞的 Python 文件, **When** 运行安全扫描命令, **Then** 系统应该检测到漏洞并报告严重程度、位置和修复建议
2. **Given** 一个干净的代码库, **When** 运行安全扫描, **Then** 系统应该报告 "无安全问题"
3. **Given** 用户只想检查关键和高危漏洞, **When** 配置严重级别过滤, **Then** 系统只报告匹配的漏洞

---

### User Story 2 - AI 代码审查 (Priority: P1)

作为开发者，我需要 AI 帮助我审查代码逻辑、风格和安全问题，以便提高代码质量和学习最佳实践。

**Why this priority**: AI 审查可以发现自动化工具难以识别的逻辑问题和代码异味。

**Independent Test**: 可以独立测试，运行 `gitconsistency review diff` 并验证是否生成有意义的审查评论。

**Acceptance Scenarios**:

1. **Given** 一个包含逻辑缺陷的代码变更, **When** 运行 AI 审查, **Then** 系统应该识别逻辑问题并提供改进建议
2. **Given** 用户需要快速反馈, **When** 使用 `--quick` 模式, **Then** 系统应在 2 秒内返回关键安全问题
3. **Given** 用户需要全面审查, **When** 使用完整模式, **Then** 系统应并行运行安全、逻辑、风格三个 Agent 并综合结果

---

### User Story 3 - GitHub PR 自动评论 (Priority: P2)

作为团队成员，我需要审查结果自动发布到 GitHub PR，以便团队成员在代码审查时看到 AI 建议。

**Why this priority**: 将审查集成到现有工作流，减少上下文切换，提高团队协作效率。

**Independent Test**: 可以独立测试，运行 `gitconsistency ci` 在 CI 环境并验证 PR 是否收到评论。

**Acceptance Scenarios**:

1. **Given** 一个打开的 PR, **When** CI 运行 GitConsistency, **Then** 系统应该在 PR 上发布格式化的审查报告
2. **Given** 已经存在 GitConsistency 评论, **When** 再次运行 CI, **Then** 系统应该删除旧评论并发布新评论
3. **Given** PR 包含严重安全问题, **When** 生成报告, **Then** 严重问题应该在评论中默认展开显示

---

### User Story 4 - 代码图谱上下文增强 (Priority: P3)

作为高级用户，我需要了解代码变更的影响范围和调用关系，以便做出更明智的审查决策。

**Why this priority**: 提供更深层次的代码理解，帮助识别潜在的副作用和依赖问题。

**Independent Test**: 可以独立测试，启用 GitNexus 后审查代码并验证是否包含调用链分析。

**Acceptance Scenarios**:

1. **Given** 启用 GitNexus 集成, **When** 审查一个函数, **Then** 系统应该显示该函数的调用者和被调用者
2. **Given** 修改了一个被多处调用的函数, **When** 生成审查报告, **Then** 系统应该警告潜在的副作用风险

---

### Edge Cases

- **空代码库**: 如何处理没有任何文件的仓库扫描请求？
- **大规模代码库**: 如何确保 10000+ 文件的仓库扫描性能？
- **LLM 不可用**: 当 LLM API 密钥未配置或超时时，如何优雅降级？
- **并发审查限制**: 如何处理 GitHub API 速率限制？
- **无效配置文件**: 如何处理格式错误的 `.env` 或配置文件？
- **Semgrep/Bandit 未安装**: 如何处理可选依赖缺失的情况？

---

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 支持通过 CLI 命令对指定路径进行安全扫描
- **FR-002**: 系统 MUST 集成 Semgrep 语义规则引擎检测安全漏洞
- **FR-003**: 系统 MUST 集成 Bandit Python 安全扫描器
- **FR-004**: 系统 MUST 支持按严重级别（CRITICAL/HIGH/MEDIUM/LOW/INFO）过滤扫描结果
- **FR-005**: 系统 MUST 提供快速模式（<2s）仅运行安全审查 Agent
- **FR-006**: 系统 MUST 提供完整模式，并行运行 Security、Logic、Style 三个 Agent
- **FR-007**: 系统 MUST 使用 SynthesisAgent 综合多 Agent 结果并去重
- **FR-008**: 系统 MUST 支持通过 LiteLLM 调用多种 LLM 后端（DeepSeek/Claude/Grok 等）
- **FR-009**: 系统 MUST 支持审查单个文件、git diff 或暂存区变更
- **FR-010**: 系统 MUST 支持 GitHub PR 自动评论，包含签名以识别和更新旧评论
- **FR-011**: 系统 MUST 生成 Markdown/HTML/JSON 格式的报告
- **FR-012**: 系统 MUST 支持通过环境变量或 `.env` 文件配置所有选项
- **FR-013**: 系统 MUST 可选集成 GitNexus 提供代码知识图谱上下文
- **FR-014**: 系统 MUST 实现两级缓存（内存 + 文件）优化重复审查性能
- **FR-015**: 系统 MUST 支持 CI/CD 模式，自动检测 GitHub Actions 环境

### Key Entities

- **Finding**: 安全扫描发现的问题
  - rule_id: 规则标识
  - severity: 严重级别（CRITICAL/HIGH/MEDIUM/LOW/INFO）
  - file_path: 文件路径
  - line/column: 位置信息
  - message: 问题描述
  - code_snippet: 代码片段
  - metadata: CWE、OWASP 分类等扩展信息

- **ReviewComment**: AI 审查生成的评论
  - file: 文件路径
  - line: 行号
  - message: 评论内容
  - suggestion: 改进建议
  - severity: 严重级别
  - category: 类别（SECURITY/LOGIC/STYLE）
  - confidence: 置信度

- **ReviewResult**: 审查结果汇总
  - summary: 整体评估摘要
  - severity: 总体严重级别
  - comments: 评论列表
  - action_items: 行动项列表
  - metadata: 审查元数据（耗时、Agent 结果等）

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 用户可以在 2 秒内获得快速模式的审查结果
- **SC-002**: 完整模式审查时间不超过 15 秒（单个文件）
- **SC-003**: 安全扫描检测率达到行业标准（覆盖 OWASP Top 10、CWE Top 25）
- **SC-004**: 误报率低于 20%（通过用户反馈和置信度阈值控制）
- **SC-005**: GitHub PR 评论发布成功率 99%+
- **SC-006**: 系统支持处理 1000+ 文件的代码库审查
- **SC-007**: 缓存命中情况下审查响应时间减少 50%+
- **SC-008**: 代码变更影响分析覆盖度达到调用链的 3 层深度（启用 GitNexus 时）

---

## Assumptions

- 目标用户是熟悉命令行的软件开发者
- 用户拥有 GitHub 仓库的写权限（用于 PR 评论）
- Python 3.12+ 环境已安装
- 可选依赖（Semgrep、Bandit、LiteLLM）可以按需安装
- 对于 AI 审查，用户自备 LLM API 密钥
- GitNexus 是可选增强功能，非必需依赖
- 扫描主要针对 Python 代码库（Semgrep 支持其他语言）
- CI/CD 环境主要指 GitHub Actions

---

## Out of Scope

- 实时代码编辑器集成（VS Code 插件等）
- 除 Python 外的语言专属扫描器（仅依赖 Semgrep 通用规则）
- 自动代码修复（只提供建议，不自动修改代码）
- 除 GitHub 外的其他 Git 平台集成（GitLab、Bitbucket 等）
- 历史代码审查（只关注当前变更）
