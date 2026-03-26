# Tasks: GitConsistency - Code Security & AI Review Tool

**Input**: Design documents from `.specify/features/001-gitconsistency-spec/`
**Prerequisites**: plan.md, spec.md, data-model.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

**Status**: Core implementation complete. All tests passing (508 unit tests + 11 integration tests).

---

## Phase 8: Critical Fixes & GitNexus Integration Strengthening

**Purpose**: Fix issues discovered during comprehensive testing and strengthen GitNexus optional integration

**Status**: [COMPLETED] All fixes verified

### Fixes Applied

- [X] **F001** Fix Windows UnicodeEncodeError in CLI output
  - Added `os.environ.setdefault("PYTHONIOENCODING", "utf-8")` in:
    - `consistency/cli/main.py`
    - `consistency/cli/commands/scan.py`
    - `consistency/cli/commands/review.py`
  - Replaced Unicode characters (✓, ✗, ⚠) with ASCII equivalents in test outputs

- [X] **F002** Fix LLMFactory import error
  - Changed `LLMFactory.create_default()` to `LLMProviderFactory.create_from_settings()`
  - Files: `consistency/agents/security_agent.py`, `logic_agent.py`, `style_agent.py`

- [X] **F003** Make GitNexus truly optional in ReviewSupervisor
  - Changed `gitnexus_client: GitNexusClient` to `gitnexus_client: GitNexusClient | None = None`
  - Removed ValueError when gitnexus_client is None
  - Updated `get_stats()` to handle None case
  - Files: `consistency/agents/supervisor.py`

- [X] **F004** Restore SARIF support in scan.py
  - Re-added `--fmt sarif` and `--output` parameters
  - SARIF 2.1.0 format output verified

### GitNexus Integration Testing

- [X] **T001** Created comprehensive integration test: `test_gitnexus_integration.py`
- [X] **T002** Verified GitNexus availability detection
- [X] **T003** Verified graceful degradation when GitNexus unavailable
- [X] **T004** Verified Agent behavior with mock GitNexus
- [X] **T005** Verified Supervisor optional GitNexus integration
- [X] **T006** Verified error handling when GitNexus fails
- [X] **T007** Verified diff integration
- [X] **T008** Verified CLI commands

**Test Results**: 11/11 tests passing (100%)

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Initialize Python 3.12+ project with `pyproject.toml` including Typer, Rich, Pydantic dependencies
- [X] T002 [P] Create project directory structure: `consistency/`, `tests/`, `docs/`
- [X] T003 [P] Configure development tools: ruff, mypy, pytest, pre-commit hooks
- [X] T004 Create package entry points: `consistency/__init__.py`, `consistency/__main__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**Status**: [COMPLETED]

- [X] T005 Create `consistency/config.py` with Pydantic Settings for environment configuration
- [X] T006 [P] Define core data models in `consistency/core/schema.py`: Severity enum, base entities
- [X] T007 [P] Create `consistency/exceptions.py` with custom exception hierarchy
- [X] T008 Implement `consistency/core/cache.py` with two-level caching (TTLCache + disk pickle)
- [X] T009 Create CLI entry point `consistency/cli/main.py` with Typer and basic command structure
- [X] T010 Implement `consistency/cli/banner.py` for startup display

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 本地代码安全扫描 (Priority: P1) 🎯 MVP

**Goal**: Implement Semgrep + Bandit dual-engine security scanning with CLI commands

**Status**: [COMPLETED] - All tests passing

**Independent Test**: Run `gitconsistency scan security <path>` and verify detection of known vulnerabilities

### Implementation for User Story 1

- [X] T011 [P] Create `consistency/scanners/base.py` with BaseScanner abstract class
- [X] T012 [P] Define `Finding` dataclass in `consistency/scanners/base.py`
- [X] T013 Implement `consistency/scanners/security_scanner.py` with Semgrep integration
- [X] T014 Implement `consistency/scanners/security_scanner.py` with Bandit integration
- [X] T015 Create `consistency/scanners/orchestrator.py` for parallel scanner execution
- [X] T016 Implement `consistency/cli/commands/scan.py` with `scan security` command
- [X] T017 Add severity filtering support in scan command (`--severity` flag)
- [X] T018 Create `consistency/tools/security_tools.py` for security-related utilities

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - AI 代码审查 (Priority: P1)

**Goal**: Implement multi-Agent AI review system with Security, Logic, and Style Agents

**Status**: [COMPLETED] - All tests passing

**Independent Test**: Run `gitconsistency review diff` and verify generation of meaningful review comments

### Implementation for User Story 2

- [X] T019 [P] Create `consistency/agents/base.py` with BaseAgent abstract class and AgentResult dataclass
- [X] T020 [P] Define `ReviewComment` and `ReviewResult` models in `consistency/reviewer/models.py`
- [X] T021 [P] Create LLM prompts in `consistency/reviewer/prompts.py` for each Agent type
- [X] T022 Implement `consistency/agents/security_agent.py` for security-focused code review
- [X] T023 Implement `consistency/agents/logic_agent.py` for logic and structure review
- [X] T024 Implement `consistency/agents/style_agent.py` for code style review
- [X] T025 Create `consistency/agents/synthesis_agent.py` for aggregating and deduplicating Agent results
- [X] T026 Implement `consistency/agents/supervisor.py` (ReviewSupervisor) for coordinating parallel Agents
- [X] T027 Create `consistency/reviewer/ai_reviewer.py` as main AI review orchestrator
- [X] T028 Implement `consistency/cli/commands/review.py` with `review diff` and `review file` commands
- [X] T029 Add `--quick` flag for fast mode (<2s) in review command
- [X] T030 Implement `consistency/tools/diff_tools.py` for git diff analysis

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - GitHub PR 自动评论 (Priority: P2)

**Goal**: Implement GitHub Actions integration with automatic PR comments

**Status**: [COMPLETED] - Core implementation done

**Independent Test**: Run `gitconsistency ci` in GitHub Actions and verify PR receives formatted review report

### Implementation for User Story 3

- [X] T031 [P] Create `consistency/llm/base.py` with BaseLLMProvider abstract class
- [X] T032 [P] Implement `consistency/llm/providers/litellm.py` for LiteLLM integration
- [X] T033 Create `consistency/llm/factory.py` for Provider factory pattern
- [X] T034 Implement `consistency/github/client.py` with PyGithub wrapper and asyncio support
- [X] T035 Create `consistency/github/comments.py` with PR comment management (signature-based)
- [X] T036 Implement `consistency/github/checks.py` for GitHub Checks API integration
- [X] T037 Create `consistency/github/ci_utils.py` for CI environment detection
- [X] T038 Implement `consistency/github/utils.py` for GitHub-related utilities
- [X] T039 Create `consistency/report/generator.py` for report generation
- [X] T040 Implement `consistency/report/llm_generator.py` for LLM-driven report generation
- [X] T041 Create report formatters: `consistency/report/formatters/markdown.py`, `json.py`, `html.py`
- [X] T042 Implement `consistency/cli/commands/ci.py` with CI/CD command
- [X] T043 Create `consistency/cli/commands/analyze.py` combining scan + review

**Checkpoint**: User Stories 1, 2, and 3 should now be independently functional

---

## Phase 6: User Story 4 - 代码图谱上下文增强 (Priority: P3)

**Goal**: Implement optional GitNexus integration for code knowledge graph context

**Status**: [COMPLETED] - GitNexus is truly optional with graceful degradation

**Independent Test**: Enable GitNexus and verify review reports include call chain analysis

### Implementation for User Story 4

- [X] T044 Implement `consistency/core/gitnexus_client.py` for GitNexus MCP communication
- [X] T045 Create `consistency/tools/gitnexus_tools.py` for GitNexus-related utilities
- [X] T046 Implement `consistency/reviewer/context_enhancer.py` for enriching review with GitNexus context
- [X] T047 [P] Update Agents to consume GitNexus context when available
- [X] T048 Add GitNexus configuration options to `consistency/config.py`

**Checkpoint**: All user stories should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

**Status**: [IN PROGRESS] - Core polish complete, documentation ongoing

- [X] T049 [P] Implement `consistency/cli/commands/init.py` for project initialization command
- [X] T050 [P] Implement `consistency/cli/commands/config_cmd.py` for configuration management
- [X] T051 Create `consistency/reviewer/disk_cache.py` for persistent review result caching
- [X] T052 [P] Add comprehensive CLI help and documentation
- [X] T053 [P] Create `consistency/cli/utils.py` for shared CLI utilities
- [X] T054 Implement `consistency/core/metrics.py` for performance metrics collection
- [X] T055 Create `consistency/core/self_hosted.py` for self-hosted deployment support
- [X] T056 [P] Write unit tests for core models in `tests/unit/` (508 tests passing)
- [X] T057 [P] Write integration tests for CLI commands in `tests/integration/`
- [ ] T058 Update `README.md` with comprehensive documentation
- [ ] T059 Create GitHub Actions workflow examples in `.github/workflows/`
- [X] T060 Validate against `quickstart.md` scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: ✅ No dependencies - can start immediately
- **Foundational (Phase 2)**: ✅ Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: ✅ All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 7)**: Depends on all desired user stories being complete
- **Phase 8 (Fixes)**: ✅ Applied to stabilize the implementation

### User Story Dependencies

| Story | Priority | Dependencies | Can Parallel With |
|-------|----------|--------------|-------------------|
| US1 - Security Scan | P1 | ✅ Phase 2 | - |
| US2 - AI Review | P1 | ✅ Phase 2, US1 (optional) | US1 (after Phase 2) |
| US3 - GitHub Integration | P2 | ✅ Phase 2, US1, US2 | - |
| US4 - GitNexus | P3 | ✅ Phase 2, US1, US2 | US3 (after Phase 2) |

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

## Test Summary

### Unit Tests
- **Total**: 508 tests
- **Status**: ✅ All passing

### Integration Tests (GitNexus)
- **Total**: 11 tests
- **Status**: ✅ All passing (100%)
- **Coverage**:
  - GitNexus availability detection
  - Agent graceful degradation (no GitNexus)
  - Agent enhancement (with mock GitNexus)
  - Supervisor optional integration
  - Error handling
  - Diff integration
  - CLI commands

---

## Task Summary

| Phase | Tasks | Description | Status |
|-------|-------|-------------|--------|
| Setup | 4 | Project initialization | ✅ Complete |
| Foundational | 6 | Core infrastructure | ✅ Complete |
| US1 (P1) | 8 | Security scanning | ✅ Complete |
| US2 (P1) | 12 | AI review system | ✅ Complete |
| US3 (P2) | 13 | GitHub integration | ✅ Complete |
| US4 (P3) | 5 | GitNexus context | ✅ Complete |
| Phase 8 (Fixes) | 4 | Critical fixes | ✅ Complete |
| Polish | 12 | Testing, docs, cleanup | 🔄 In Progress |
| **Total** | **64** | | **95% Complete** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- This task list reflects the existing codebase structure
- **GitNexus Integration**: Fully verified as optional dependency with graceful degradation
