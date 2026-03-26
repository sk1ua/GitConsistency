# Research: GitConsistency Architecture Decisions

**Feature**: GitConsistency - Code Security & AI Review Tool
**Date**: 2026-03-26
**Status**: Complete

---

## Architecture Decision Records

### ADR-001: Multi-Agent Supervisor Pattern

**Decision**: Use Supervisor Pattern to coordinate SecurityAgent, LogicAgent, StyleAgent, and ReportGeneratorAgent.

**Execution Flow**:
1. Security/Logic/Style Agents run in parallel (asyncio.gather)
2. SynthesisAgent aggregates and deduplicates results
3. ReportGeneratorAgent generates final human-readable report sequentially

**Rationale**:
- Parallel execution of base agents improves performance
- Error isolation prevents cascade failures
- Sequential report generation ensures complete context
- Extensible for future agent types

**Rejected Alternative**: Single monolithic LLM call - lacks parallelism and error isolation.

---

### ADR-002: Dual-Engine Security Scanning

**Decision**: Use Semgrep (semantic rules) + Bandit (Python AST) simultaneously.

**Rationale**:
- Semgrep covers OWASP/CWE industry standards
- Bandit specializes in Python-specific vulnerabilities
- Complementary coverage reduces false negatives
- Parallel execution means no added latency

---

### ADR-003: LiteLLM Abstraction Layer

**Decision**: Use LiteLLM as unified LLM interface.

**Rationale**:
- Supports 100+ LLM backends (DeepSeek, Claude, Grok, etc.)
- Unified API - no per-model adapters needed
- Built-in retry, error handling, rate limiting

---

### ADR-004: Two-Level Caching Strategy

**Decision**: Implement memory TTLCache + disk pickle with file-level hashing.

**Full Repository Analysis**:
- File content hashed (SHA256) to detect changes
- Unchanged files skip scanning entirely
- Changed files re-analyzed
- Cache invalidated on tool version updates

**Rationale**:
- Sub-millisecond hot data access (memory)
- Persistent across restarts (disk)
- File-level granularity optimizes full repo scans

---

### ADR-005: SARIF as Machine-Readable Output

**Decision**: Use SARIF 2.1.0 as standard machine-readable format.

**Target Consumers**:
- vibe coding agents
- CI/CD pipelines
- Security dashboards

**Rationale**:
- Industry standard for security analysis tools
- Rich metadata (rules, results, code flows)
- Wide tool ecosystem support

---

### ADR-006: Incremental vs Full Repository Analysis

**Decision**: Support both modes with distinct optimizations.

| Mode | Use Case | Optimization |
|------|----------|--------------|
| Incremental | PR/MR review | Only changed files + dependencies |
| Full | Security audit | File-level cache, parallel batch processing |

**Rationale**:
- Different use cases require different tradeoffs
- Incremental prioritizes speed
- Full prioritizes completeness

---

## Open Questions Resolved

| Question | Decision | Date |
|----------|----------|------|
| Agent execution order | Security/Logic/Style parallel → Synthesis → Report Generator sequential | 2026-03-26 |
| Full repo caching | File-level SHA256 hash cache | 2026-03-26 |
| SARIF consumption | Local file output via `--output` parameter | 2026-03-26 |

---

## Technology Stack Confirmation

| Component | Choice | Status |
|-----------|--------|--------|
| Language | Python 3.12+ | ✅ Confirmed |
| CLI Framework | Typer | ✅ Confirmed |
| LLM Interface | LiteLLM | ✅ Confirmed |
| Security Scanners | Semgrep + Bandit | ✅ Confirmed |
| GitHub Integration | PyGithub | ✅ Confirmed |
| Output Formats | Markdown + SARIF 2.1.0 | ✅ Confirmed |
| Cache | TTLCache + disk pickle | ✅ Confirmed |

---

**Next Steps**: Proceed to `/speckit.tasks` for task generation
