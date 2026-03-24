# GitConsistency 项目评估与执行计划

> **版本**: v0.1.0
> **评估日期**: 2024-03-24
> **评估人**: Claude Code (Claude Opus 4.6)
> **策略**: KISS (Keep It Simple, Stupid) - 重点强化 CI + GitHub 集成

---

## 目录

1. [执行摘要](#执行摘要)
2. [完整评估报告](se-report-2024-03-24.md)
3. [简化执行计划](#简化执行计划)
4. [CI/GitHub 强化路线图](#cigithub-强化路线图)

---

## 执行摘要

### 当前状态

| 维度 | 评分 | 状态 |
|------|------|------|
| 架构设计 | 8/10 | ✅ 先进的多 Agent 架构 |
| 代码质量 | 8/10 | ✅ 类型安全、风格一致 |
| CI/CD | 8/10 | ✅ 自动化完善 |
| GitHub 集成 | 7/10 | ⚠️ 基础功能完整，需增强 |
| **总体** | **7.8/10** | **Beta 阶段，可用** |

### KISS 原则下的优先事项

**不做**:
- ❌ PyPI 发布（非核心，可延后）
- ❌ Web Dashboard（过重）
- ❌ IDE 插件（复杂度太高）

**重点做**:
- ✅ CI 能力强化（并行、缓存、性能）
- ✅ GitHub 集成深化（Checks、Annotations、Actions 增强）
- ✅ 代码清理（删除重复，简化结构）
- ✅ 测试补强（核心路径覆盖）

---

## 简化执行计划

### Phase 1: 清理与加固 (Week 1-2)

**目标**: 删除冗余，夯实基础

| 任务 | 工作量 | 产出 |
|------|--------|------|
| 删除 `consistency/commands/` 目录 | 2h | 代码结构简化 |
| 删除 `consistency/main.py` | 1h | 统一 CLI 入口 |
| 修复 `README.md` 安装说明 | 2h | 准确的文档 |
| 核心模块测试覆盖提升到 60% | 2d | 质量保障 |

**验证标准**:
- `pytest` 全部通过
- `ruff` 无警告
- `mypy` 无错误
- 目录结构清晰

---

### Phase 2: CI 性能强化 (Week 3-4)

**目标**: 让 CI 更快、更稳、更智能

#### 2.1 缓存策略

```yaml
# .github/workflows/consistency.yml 优化项

# 1. uv/pip 缓存
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/pyproject.toml') }}

# 2. Semgrep 规则缓存
- uses: actions/cache@v4
  with:
    path: ~/.semgrep
    key: semgrep-rules-${{ hashFiles('**/pyproject.toml') }}

# 3. 增量扫描（只扫描变更文件）
gitconsistency ci --changed-only --base ${{ github.base_ref }}
```

#### 2.2 并行执行

```yaml
jobs:
  # 当前：串行（总时间 = sum）
  # 优化后：并行（总时间 = max）

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - run: gitconsistency scan security . --format sarif --output security.sarif

  ai-review:
    runs-on: ubuntu-latest
    steps:
      - run: gitconsistency ci --agents-only

  combine:
    needs: [security-scan, ai-review]
    steps:
      - run: gitconsistency report combine security.sarif agents.json
```

#### 2.3 智能跳过

```yaml
# 无 Python 变更时跳过扫描
- name: Check changed files
  id: changes
  uses: dorny/paths-filter@v3
  with:
    filters: |
      python:
        - '**/*.py'
        - 'pyproject.toml'

- name: Run analysis
  if: steps.changes.outputs.python == 'true'
  run: gitconsistency ci
```

---

### Phase 3: GitHub 集成深化 (Week 5-6)

**目标**: 成为 GitHub 原生体验的一部分

#### 3.1 GitHub Checks API

```python
# consistency/github/checks.py 增强

async def create_check_run(
    self,
    name: str,  # "GitConsistency Security Scan"
    status: str,  # "in_progress" | "completed"
    conclusion: str | None,  # "success" | "failure" | "neutral"
    output: dict,  # 详细报告
):
    """创建 GitHub Check，显示在 PR Checks 标签页"""

    output = {
        "title": "Security Scan Results",
        "summary": f"Found {high_count} high severity issues",
        "annotations": [
            {
                "path": "src/main.py",
                "start_line": 42,
                "end_line": 42,
                "annotation_level": "failure",
                "message": "SQL Injection vulnerability detected",
                "raw_details": "..."
            }
        ]
    }
```

**效果**: 直接在代码行显示问题

```
PR → Files changed → 行内注释显示问题
```

#### 3.2 PR Annotations

```yaml
# 自动在 PR 中创建代码注释
- name: Post annotations
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const report = JSON.parse(fs.readFileSync('report.json'));

      for (const finding of report.findings) {
        github.rest.pulls.createReviewComment({
          owner: context.repo.owner,
          repo: context.repo.repo,
          pull_number: context.issue.number,
          commit_id: context.sha,
          path: finding.file,
          line: finding.line,
          body: `🔍 **${finding.rule}**: ${finding.message}`
        });
      }
```

#### 3.3 自动修复建议

```python
# consistency/github/suggestions.py

class AutoFixer:
    """为简单问题生成 GitHub Suggestion"""

    def generate_fix(self, finding: Finding) -> str | None:
        if finding.rule_id == "B301":
            # pickle → json
            return """```suggestion
- import pickle
- data = pickle.loads(raw)
+ import json
+ data = json.loads(raw)
```"""
        return None
```

---

### Phase 4: 持续优化 (Ongoing)

#### 4.1 监控与度量

```python
# 在 CI 中收集指标
metrics = {
    "scan_duration_ms": 15000,
    "files_scanned": 45,
    "issues_found": 12,
    "agent_severity": "HIGH",
    "llm_tokens_used": 2048,
    "cache_hit_rate": 0.75,
}

# 上报到 GitHub Actions Summary
with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
    f.write(f"| Metric | Value |\n")
    f.write(f"|--------|-------|\n")
    f.write(f"| Duration | {metrics['scan_duration_ms']}ms |\n")
```

#### 4.2 自托管 Runner 支持

```yaml
# 对于需要 GPU/大内存的 AI 审查
jobs:
  ai-review:
    runs-on: self-hosted  # 自托管高性能机器
    steps:
      - run: gitconsistency ci --use-local-llm
```

---

## CI/GitHub 强化路线图

### 当前 vs 目标

| 能力 | 当前 | 目标 | 优先级 |
|------|------|------|--------|
| PR 评论 | ✅ 基础 Markdown | ✅ 富文本 + 折叠 | P1 |
| Checks API | ❌ 未使用 | ✅ 完整集成 | P1 |
| 行内注释 | ❌ 无 | ✅ 代码行标注 | P1 |
| 增量扫描 | ❌ 全量 | ✅ 仅变更文件 | P1 |
| 缓存 | ⚠️ 基础 | ✅ 多层缓存 | P2 |
| 并行 | ❌ 串行 | ✅ Agent/扫描并行 | P2 |
| Auto-fix | ❌ 无 | ✅ 简单问题自动修复 | P3 |
| 趋势图 | ❌ 无 | ✅ 问题趋势 Dashboard | P3 |

### 技术方案选型

```
GitHub Integration Stack
├── PR Comments       ← 现状，够用
├── Checks API        ← 优先实现
├── Annotations       ← 优先实现
├── Actions Summary   ← 快速 win
├── Code Suggestions  ← 长期优化
└── GitHub App        ← 可选（太重，暂缓）
```

---

## 文档更新清单

### README.md 修改

```markdown
## 安装

### 源码安装（推荐开发者）
```bash
git clone https://github.com/sk1ua/GitConsistency.git
cd GitConsistency
pip install -e ".[full]"
```

### CI 中使用
```yaml
- uses: sk1ua/gitconsistency-action@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    litellm-api-key: ${{ secrets.LITELLM_API_KEY }}
```

## GitHub 集成特性

### Checks 标签页集成
扫描结果直接显示在 PR Checks 中，支持：
- ✅ 通过/失败状态
- 📊 详细指标
- 🔗 跳转到问题行

### 行内注释
高严重级别问题直接在 Files changed 中标注：
![annotation-example](docs/images/annotation.png)
```

---

## 测试策略

### 核心路径测试

```python
# 必须覆盖的场景
test_critical_paths = [
    "CI 完整流程",
    "GitHub PR 评论发布",
    "Checks API 创建",
    "多 Agent 并行审查",
    "增量扫描（changed files）",
    "缓存命中/失效",
]
```

### CI 集成测试

```yaml
# .github/workflows/test-ci.yml
name: Test CI Integration
on: [pull_request]

jobs:
  test-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # 测试自举（用 GitConsistency 审查 GitConsistency）
      - name: Self-review
        uses: ./
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## 成功指标

### Phase 1 完成标准
- [ ] 代码重复度 < 5%
- [ ] 核心测试覆盖 > 60%
- [ ] README 安装说明准确

### Phase 2 完成标准
- [ ] CI 运行时间 < 90s（当前 ~150s）
- [ ] 缓存命中率 > 70%
- [ ] 支持增量扫描

### Phase 3 完成标准
- [ ] PR 显示 Checks 标签
- [ ] 高严重问题有行内注释
- [ ] Actions Summary 有度量数据

### Phase 4 完成标准
- [ ] 周活跃用户（内部）> 5 个项目
- [ ] 平均问题修复时间 < 1 天
- [ ] 误报率 < 10%

---

## 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| GitHub API 限制 | 中 | 高 | 实现请求队列 + 重试 |
| LLM 成本高 | 中 | 中 | 缓存 + 本地模型 fallback |
| 误报多 | 低 | 高 | 可调 severity + 白名单 |
| 大仓库 OOM | 中 | 中 | 文件分批 + 大小限制 |

---

## 附录

### A. 参考文档
- [完整评估报告](se-report-2024-03-24.md)
- [GitHub Checks API 文档](https://docs.github.com/en/rest/checks)
- [GitHub Actions 最佳实践](https://docs.github.com/en/actions/learn-github-actions)

### B. 相关 Issue
- #1: CI 性能优化
- #2: GitHub Checks 集成
- #3: 行内注释支持

---

*最后更新: 2024-03-24*
*策略: KISS - 聚焦 CI + GitHub，暂缓 PyPI*
