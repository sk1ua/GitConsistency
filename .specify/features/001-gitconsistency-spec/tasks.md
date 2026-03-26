# Tasks: GitConsistency - Code Security & AI Review Tool

**Input**: Design documents from `.specify/features/001-gitconsistency-spec/`
**Prerequisites**: plan.md, spec.md, data-model.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Initialize Python 3.12+ project with `pyproject.toml` including Typer, Rich, Pydantic dependencies
- [ ] T002 [P] Create project directory structure: `consistency/`, `tests/`, `docs/`
- [ ] T003 [P] Configure development tools: ruff, mypy, pytest, pre-commit hooks
- [ ] T004 Create package entry points: `consistency/__init__.py`, `consistency/__main__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create `consistency/config.py` with Pydantic Settings for environment configuration
- [ ] T006 [P] Define core data models in `consistency/core/schema.py`: Severity enum, base entities
- [ ] T007 [P] Create `consistency/exceptions.py` with custom exception hierarchy
- [ ] T008 Implement `consistency/core/cache.py` with two-level caching (TTLCache + disk pickle)
- [ ] T009 Create CLI entry point `consistency/cli/main.py` with Typer and basic command structure
- [ ] T010 Implement `consistency/cli/banner.py` for startup display

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 本地代码安全扫描 (Priority: P1) 🎯 MVP

**Goal**: Implement Semgrep + Bandit dual-engine security scanning with CLI commands

**Independent Test**: Run `gitconsistency scan security <path>` and verify detection of known vulnerabilities

### Implementation for User Story 1

- [ ] T011 [P] Create `consistency/scanners/base.py` with BaseScanner abstract class
- [ ] T012 [P] Define `Finding` dataclass in `consistency/scanners/base.py`
- [ ] T013 Implement `consistency/scanners/security_scanner.py` with Semgrep integration
- [ ] T014 Implement `consistency/scanners/security_scanner.py` with Bandit integration
- [ ] T015 Create `consistency/scanners/orchestrator.py` for parallel scanner execution
- [ ] T016 Implement `consistency/cli/commands/scan.py` with `scan security` command
- [ ] T017 Add severity filtering support in scan command (`--severity` flag)
- [ ] T018 Create `consistency/tools/security_tools.py` for security-related utilities

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - AI 代码审查 (Priority: P1)

**Goal**: Implement multi-Agent AI review system with Security, Logic, and Style Agents

**Independent Test**: Run `gitconsistency review diff` and verify generation of meaningful review comments

### Implementation for User Story 2

- [ ] T019 [P] Create `consistency/agents/base.py` with BaseAgent abstract class and AgentResult dataclass
- [ ] T020 [P] Define `ReviewComment` and `ReviewResult` models in `consistency/reviewer/models.py`
- [ ] T021 [P] Create LLM prompts in `consistency/reviewer/prompts.py` for each Agent type
- [ ] T022 Implement `consistency/agents/security_agent.py` for security-focused code review
- [ ] T023 Implement `consistency/agents/logic_agent.py` for logic and structure review
- [ ] T024 Implement `consistency/agents/style_agent.py` for code style review
- [ ] T025 Create `consistency/agents/synthesis_agent.py` for aggregating and deduplicating Agent results
- [ ] T026 Implement `consistency/agents/supervisor.py` (ReviewSupervisor) for coordinating parallel Agents
- [ ] T027 Create `consistency/reviewer/ai_reviewer.py` as main AI review orchestrator
- [ ] T028 Implement `consistency/cli/commands/review.py` with `review diff` and `review file` commands
- [ ] T029 Add `--quick` flag for fast mode (<2s) in review command
- [ ] T030 Implement `consistency/tools/diff_tools.py` for git diff analysis

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - GitHub PR 自动评论 (Priority: P2)

**Goal**: Implement GitHub Actions integration with automatic PR comments

**Independent Test**: Run `gitconsistency ci` in GitHub Actions and verify PR receives formatted review report

### Implementation for User Story 3

- [ ] T031 [P] Create `consistency/llm/base.py` with BaseLLMProvider abstract class
- [ ] T032 [P] Implement `consistency/llm/providers/litellm.py` for LiteLLM integration
- [ ] T033 Create `consistency/llm/factory.py` for Provider factory pattern
- [ ] T034 Implement `consistency/github/client.py` with PyGithub wrapper and asyncio support
- [ ] T035 Create `consistency/github/comments.py` with PR comment management (signature-based)
- [ ] T036 Implement `consistency/github/checks.py` for GitHub Checks API integration
- [ ] T037 Create `consistency/github/ci_utils.py` for CI environment detection
- [ ] T038 Implement `consistency/github/utils.py` for GitHub-related utilities
- [ ] T039 Create `consistency/report/generator.py` for report generation
- [ ] T040 Implement `consistency/report/llm_generator.py` for LLM-driven report generation
- [ ] T041 Create report formatters: `consistency/report/formatters/markdown.py`, `json.py`, `html.py`
- [ ] T042 Implement `consistency/cli/commands/ci.py` with CI/CD command
- [ ] T043 Create `consistency/cli/commands/analyze.py` combining scan + review

**Checkpoint**: User Stories 1, 2, and 3 should now be independently functional

---

## Phase 6: User Story 4 - 代码图谱上下文增强 (Priority: P3)

**Goal**: Implement optional GitNexus integration for code knowledge graph context

**Independent Test**: Enable GitNexus and verify review reports include call chain analysis

### Implementation for User Story 4

- [ ] T044 Implement `consistency/core/gitnexus_client.py` for GitNexus MCP communication
- [ ] T045 Create `consistency/tools/gitnexus_tools.py` for GitNexus-related utilities
- [ ] T046 Implement `consistency/reviewer/context_enhancer.py` for enriching review with GitNexus context
- [ ] T047 [P] Update Agents to consume GitNexus context when available
- [ ] T048 Add GitNexus configuration options to `consistency/config.py`

**Checkpoint**: All user stories should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T049 [P] Implement `consistency/cli/commands/init.py` for project initialization command
- [ ] T050 [P] Implement `consistency/cli/commands/config_cmd.py` for configuration management
- [ ] T051 Create `consistency/reviewer/disk_cache.py` for persistent review result caching
- [ ] T052 [P] Add comprehensive CLI help and documentation
- [ ] T053 [P] Create `consistency/cli/utils.py` for shared CLI utilities
- [ ] T054 Implement `consistency/core/metrics.py` for performance metrics collection
- [ ] T055 Create `consistency/core/self_hosted.py` for self-hosted deployment support
- [ ] T056 [P] Write unit tests for core models in `tests/unit/`
- [ ] T057 [P] Write integration tests for CLI commands in `tests/integration/`
- [ ] T058 Update `README.md` with comprehensive documentation
- [ ] T059 Create GitHub Actions workflow examples in `.github/workflows/`
- [ ] T060 Validate against `quickstart.md` scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

| Story | Priority | Dependencies | Can Parallel With |
|-------|----------|--------------|-------------------|
| US1 - Security Scan | P1 | Phase 2 | - |
| US2 - AI Review | P1 | Phase 2, US1 (optional) | US1 (after Phase 2) |
| US3 - GitHub Integration | P2 | Phase 2, US1, US2 | - |
| US4 - GitNexus | P3 | Phase 2, US1, US2 | US3 (after Phase 2) |

**Note**: US1 and US2 are both P1 and can be worked on in parallel after Phase 2. US2 may optionally integrate with US1 findings but should function independently.

### Within Each User Story

- Models before services
- Services before CLI commands
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members
- US1 and US2 can proceed in parallel after Phase 2
- US3 and US4 can proceed in parallel after US1/US2 core components

---

## Parallel Example: User Story 2

```bash
# Launch all models for User Story 2 together:
Task: "Create BaseAgent in consistency/agents/base.py"
Task: "Define ReviewComment/ReviewResult in consistency/reviewer/models.py"
Task: "Create prompts in consistency/reviewer/prompts.py"

# After models complete, launch Agent implementations in parallel:
Task: "Implement SecurityAgent in consistency/agents/security_agent.py"
Task: "Implement LogicAgent in consistency/agents/logic_agent.py"
Task: "Implement StyleAgent in consistency/agents/style_agent.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Security Scanning)
4. **STOP and VALIDATE**: Test `gitconsistency scan security` independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (Core security scanning!)
3. Add User Story 2 → Test independently → Deploy/Demo (AI review added!)
4. Add User Story 3 → Test independently → Deploy/Demo (GitHub integration!)
5. Add User Story 4 → Test independently → Deploy/Demo (Context enhancement!)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Security Scan)
   - Developer B: User Story 2 (AI Review)
3. After US1/US2 core:
   - Developer C: User Story 3 (GitHub Integration)
   - Developer D: User Story 4 (GitNexus)
4. Stories complete and integrate independently

---

## Task Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Setup | 4 | Project initialization |
| Foundational | 6 | Core infrastructure |
| US1 (P1) | 8 | Security scanning |
| US2 (P1) | 12 | AI review system |
| US3 (P2) | 13 | GitHub integration |
| US4 (P3) | 5 | GitNexus context |
| Polish | 12 | Testing, docs, cleanup |
| **Total** | **60** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- This task list reflects the existing codebase structure
