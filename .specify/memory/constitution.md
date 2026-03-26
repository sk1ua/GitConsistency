<!--
Sync Impact Report:
- Version change: N/A → 1.0.0 (initial ratification)
- Modified principles: N/A (new constitution)
- Added sections: Core Principles (I-V), Performance Standards, Quality Gates, Governance
- Removed sections: N/A
- Templates requiring updates:
  - ✅ plan-template.md: Constitution Check section aligns with principles I-V
  - ✅ spec-template.md: User Stories align with principle II (Independent Testability)
  - ✅ tasks-template.md: Phase structure aligns with principle III (Modular Architecture)
- Follow-up TODOs: None
-->

# GitConsistency Constitution

## Core Principles

### I. Security-First (NON-NEGOTIABLE)

Security is the primary value proposition. All features MUST prioritize security detection accuracy and vulnerability prevention.

- Security scanning MUST be accurate (minimize false negatives)
- All security findings MUST include severity classification and remediation guidance
- Code review Agents MUST identify security issues as highest priority
- Dependencies MUST be regularly audited for known vulnerabilities

**Rationale**: Users trust this tool to catch vulnerabilities before they reach production. A missed vulnerability undermines the entire tool's purpose.

### II. Independent Testability

Every User Story MUST be independently completable and testable without requiring other stories to be finished.

- Each User Story MUST have a defined independent test command
- Stories MUST NOT have hard dependencies on other stories for core functionality
- Optional integrations (e.g., GitNexus) MUST gracefully degrade when unavailable
- Test scenarios MUST be executable in isolation

**Rationale**: Enables incremental delivery, parallel development, and clear progress tracking. Aligns with MVP-first approach.

### III. Modular Agent Architecture

The system MUST use a Supervisor Pattern with specialized, composable Agents.

- Each Agent MUST have a single, well-defined responsibility (Security/Logic/Style)
- Agents MUST be independently testable and replaceable
- New Agent types MUST be addable without modifying existing Agents
- SynthesisAgent MUST aggregate and deduplicate Agent outputs deterministically

**Rationale**: Parallel execution improves performance; error isolation prevents cascade failures; extensibility supports future analysis types.

### IV. Performance Constraints (NON-NEGOTIABLE)

All features MUST meet defined performance targets.

- Quick mode MUST complete in <2 seconds for single-file review
- Full mode MUST complete in <15 seconds for single-file review
- Security scanning MUST handle 1000+ file repositories without timeout
- Cache implementations MUST reduce repeated review time by ≥50%

**Rationale**: Developers need fast feedback to maintain flow state. Slow tools get bypassed or disabled.

### V. CI/CD Native

The tool MUST be designed for seamless CI/CD integration, with GitHub Actions as primary target.

- All CLI commands MUST return appropriate exit codes for CI pipelines
- PR comment integration MUST be idempotent (signature-based update)
- Output formats MUST include machine-readable options (JSON)
- Configuration MUST support environment variables for CI secrets

**Rationale**: Maximum value comes from automated enforcement in the development workflow, not just local manual checks.

---

## Performance Standards

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Quick mode latency | <2000ms | End-to-end CLI execution time |
| Full mode latency | <15000ms | End-to-end CLI execution time |
| Cache hit reduction | ≥50% | (uncached_time - cached_time) / uncached_time |
| Large repo scan | <60s | 1000+ files, no timeout |
| PR comment success | ≥99% | CI success rate over 30 days |

**Enforcement**: Performance regressions block release. Benchmarks run in CI on every PR.

---

## Quality Gates

All code changes MUST pass the following gates:

1. **Type Safety**: MyPy strict mode, zero errors
2. **Linting**: Ruff format and lint, zero violations
3. **Security Scan**: Bandit + Semgrep, zero HIGH/CRITICAL findings
4. **Test Coverage**: Minimum 30% coverage, all tests passing
5. **Pre-commit Hooks**: All hooks pass before commit allowed

**Exemptions**: Security findings in test fixtures require explicit `# nosec` annotation with justification.

---

## Governance

### Authority

This constitution supersedes all other development practices. When in conflict, constitution principles prevail.

### Amendment Process

1. Propose amendment via PR with rationale and impact analysis
2. Review against existing principles for conflicts
3. Update dependent templates (plan, spec, tasks) if affected
4. Increment version per semantic rules below
5. Ratify with documented approval

### Versioning Policy

- **MAJOR**: Principle removal or redefinition that invalidates existing design decisions
- **MINOR**: New principle added, or material expansion of existing principle scope
- **PATCH**: Clarification, wording refinement, non-semantic corrections

### Compliance Review

- All PRs MUST verify constitution compliance in review checklist
- Architecture decisions MUST reference relevant principles
- Quarterly review of constitution relevance and completeness

---

**Version**: 1.0.0 | **Ratified**: 2026-03-26 | **Last Amended**: 2026-03-26
