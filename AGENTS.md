# GitConsistency - Agent Guide

## Project Overview

GitConsistency is a Python code security scanner with AI review capabilities, designed for "vibe coding" (high-frequency commit) scenarios.

**Key Features:**
- Security scanning (Semgrep + Bandit)
- Multi-agent AI review (Security/Logic/Style agents)
- GitNexus integration for code knowledge graph
- Incremental diff review for fast feedback

## Architecture

```
CLI (Typer) 
    └── ReviewCommand
            └── ReviewSupervisor
                    ├── SecurityAgent (quick mode only)
                    ├── LogicAgent (full mode)
                    ├── StyleAgent (full mode)
                    └── SynthesisAgent
                            └── GitNexusClient (optional)
```

## Module Structure

```
consistency/
├── agents/              # LangChain-style multi-agent system
│   ├── base.py          # BaseAgent, AgentResult, Severity
│   ├── security_agent.py
│   ├── logic_agent.py
│   ├── style_agent.py
│   ├── synthesis_agent.py
│   └── supervisor.py    # ReviewSupervisor
├── commands/            # CLI commands
│   └── review.py        # ReviewCommand
├── core/                # Core utilities
│   ├── gitnexus_client.py
│   └── cache.py
├── scanners/            # Security scanners
│   ├── security_scanner.py
│   └── orchestrator.py
├── reviewer/            # AI reviewer
│   ├── ai_reviewer.py
│   ├── models.py
│   └── prompts.py
├── tools/               # LangChain tools
│   ├── diff_tools.py    # Incremental review
│   ├── gitnexus_tools.py
│   └── security_tools.py
├── main.py              # CLI entry
└── config.py            # Settings
```

## Quick Start

```bash
# Install
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/unit -v --ignore=tests/e2e

# Quick review (vibe coding)
gitconsistency review diff --quick

# Full review
gitconsistency review file main.py
```

## Coding Conventions

### Python Style
- **Formatter**: Ruff (configured in pyproject.toml)
- **Type hints**: Required for all public functions
- **Docstrings**: Google style

### Naming
- Package: `consistency` (not `consistancy`)
- CLI command: `gitconsistency`
- PyPI package: `git-consistency`
- Env prefix: `CONSISTENCY_`

### Async Patterns
```python
# Use asyncio.gather for parallel agent execution
results = await asyncio.gather(
    self.security.analyze(file_path, code),
    self.logic.analyze(file_path, code) if self.logic else empty(),
)
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CONSISTENCY_LITELLM_API_KEY` | LLM API key |
| `CONSISTENCY_LITELLM_MODEL` | Model (default: deepseek/deepseek-chat) |
| `CONSISTENCY_GITHUB_TOKEN` | GitHub token for PR comments |
| `CONSISTENCY_GITNEXUS_ENABLED` | Enable GitNexus (default: false) |

## Testing

```bash
# Unit tests only (fast)
uv run pytest tests/unit -v

# Exclude tests requiring optional deps
uv run pytest tests/unit -v --ignore=tests/unit/test_main.py --ignore=tests/unit/test_github_integration.py --ignore=tests/unit/test_gitnexus_client.py
```

## Skills Available

This project has associated skills in `C:\Users\15857\kimi-skills`:

| Skill | Purpose |
|-------|---------|
| `code-review` | Code review workflows with multi-agent system |
| `analyze-architecture` | Understand codebase architecture |
| `refactor-plan` | Plan and execute refactoring safely |
| `setup-ci` | CI/CD configuration for GitHub Actions |
| `write-skill` | Create new skills for agent enhancement |

Use these skills when working on corresponding tasks.

## Common Tasks

### Adding a New Agent
1. Create `consistency/agents/my_agent.py`
2. Extend `BaseAgent`
3. Implement `analyze()` method
4. Register in `ReviewSupervisor`

### Adding a New CLI Command
1. Add command in `consistency/main.py`
2. Or create `consistency/commands/my_command.py`
3. Use `ReviewCommand` as reference

### Modifying Models
- Update `consistency/reviewer/models.py`
- Ensure backward compatibility
- Update tests if needed
