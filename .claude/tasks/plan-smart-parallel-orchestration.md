# Implementation Plan: Smart Parallel Orchestration with Dependency-Aware Dispatch

Created: 2025-12-26
Status: COMPLETED

## Summary

Enhance the agent orchestration system to enforce dependency-aware parallelization rather than relying solely on documentation discipline. The current system uses declarative file ownership matrices and phase sequencing but lacks runtime enforcement. This plan adds explicit dependency markers, dispatch validation, and conservative defaults to ensure "methodical and stable over ultra-parallel and brittle."

## Scope

### In Scope
- Enhance `sub-agent-invocation` skill with explicit dependency enforcement protocols
- Update `master-orchestrator` agent config with dependency-first planning requirements
- Add dispatch validation patterns to CLAUDE.md
- Create conservative default rules for Central AI dispatch decisions

### Out of Scope
- Runtime file locking mechanisms (staying with documentation-based approach)
- Automated collision detection code (beyond current capabilities)
- Changes to Claude Code internals

## Prerequisites
- Review current skill and agent configurations
- Understand current workflow patterns

---

## Current State Analysis

### What Works
1. **File Ownership Matrices** - Plans declare which agent owns which files
2. **Phase Review Gates** - Quality agents run at phase boundaries
3. **Sequential Dependency Chains** - Documented patterns like `Schema → API → Frontend`
4. **Parallel Execution Pattern** - "Multiple Task calls in ONE message"

### What's Missing (The Gaps)

| Gap | Problem | Impact |
|-----|---------|--------|
| **No dispatch validation** | Central AI can launch parallel agents without verifying dependencies | File conflicts, race conditions |
| **No conservative default** | System biases toward parallelism without safety checks | Brittle execution |
| **No explicit dependency markers in tasks** | Subtasks lack machine-readable dependency fields | Central AI can't auto-detect sequencing |
| **No "wait for completion" protocol** | No explicit rule to verify Phase N complete before Phase N+1 | Premature parallel dispatch |

---

## Parallel Execution Strategy

This plan itself uses **sequential execution** since all changes affect interconnected configuration files.

### Workstream Analysis
| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|---------------|
| Phase 1: Skill Enhancement | Central AI (direct edit) | sub-agent-invocation/SKILL.md | None |
| Phase 2: Orchestrator Config | Central AI (direct edit) | agents/master-orchestrator.md | Phase 1 complete |
| Phase 3: Global Framework | Central AI (direct edit) | CLAUDE.md | Phases 1-2 complete |

### File Ownership Matrix
All changes owned by Central AI (single thread) - no parallel dispatch needed.

---

## Implementation Phases

### Phase 1: Enhance Sub-Agent Invocation Skill

**Objective**: Add explicit dependency enforcement protocols and conservative dispatch rules

**Sequential Tasks:**

1. **Task 1A: Add Dependency Declaration Section**
   - File: `/Users/aiml/.claude/skills/sub-agent-invocation/SKILL.md`
   - Add new section: "Dependency Declaration Requirements"
   - Define machine-readable dependency markers for task descriptions
   - Example format:
     ```
     DEPENDENCIES: [task_id_1, task_id_2]
     BLOCKS: [task_id_3, task_id_4]
     PARALLEL_SAFE: true/false
     FILE_OWNERSHIP: [list of files this task exclusively modifies]
     ```

2. **Task 1B: Add Dispatch Validation Protocol**
   - Add section: "Pre-Dispatch Validation Checklist"
   - Central AI MUST verify before parallel dispatch:
     - [ ] All dependency tasks marked "completed"
     - [ ] No file ownership overlap between parallel tasks
     - [ ] Phase review gate passed for previous phase
     - [ ] Explicit PARALLEL_SAFE=true on all tasks in batch
   - If ANY check fails → sequence the tasks instead

3. **Task 1C: Add Conservative Default Rules**
   - Add section: "Conservative Parallelization Defaults"
   - Default: PARALLEL_SAFE=false (must explicitly enable)
   - Default: Unknown dependencies → sequence
   - Default: Same file touched → consolidate into one agent
   - Principle: "When in doubt, sequence"

**Files to Modify:**
- `/Users/aiml/.claude/skills/sub-agent-invocation/SKILL.md` - Add 3 new sections

**Phase Verification:**
- [ ] Skill file has Dependency Declaration section
- [ ] Skill file has Pre-Dispatch Validation section
- [ ] Skill file has Conservative Default Rules section

---

### Phase 2: Update Master Orchestrator Configuration

**Objective**: Ensure orchestrator creates dependency-annotated subtasks

**Sequential Tasks:**

1. **Task 2A: Add Dependency-First Subtask Creation**
   - File: `/Users/aiml/.claude/agents/master-orchestrator.md`
   - Update "Task Enrichment Workflow" section
   - REQUIRE dependency fields on every subtask:
     ```
     DEPENDENCIES: [explicit list of prerequisite task IDs]
     PARALLEL_SAFE: [true only if verified no file conflicts]
     FILE_OWNERSHIP: [exclusive file list]
     ```
   - Add validation step: "Verify no file ownership overlap before marking PARALLEL_SAFE=true"

2. **Task 2B: Add Sequencing Strategy Output**
   - Update "Task Enrichment Output" section
   - REQUIRE master-orchestrator to output:
     ```
     ### Execution Strategy
     **Parallel Batches:**
     - Batch 1: [task_ids that can run together]
     - Batch 2: [task_ids that can run together, after Batch 1]

     **Sequential Chain:**
     - task_1 → task_2 → task_3 (reason: file dependency)

     **Verification Points:**
     - After Batch 1: [what to verify]
     - After task_2: [what to verify]
     ```

3. **Task 2C: Add Phase Gate Enforcement**
   - Add explicit rule: "Central AI MUST NOT dispatch Phase N+1 tasks until Phase N review gate passes"
   - Add checkpoint protocol for phase transitions

**Files to Modify:**
- `/Users/aiml/.claude/agents/master-orchestrator.md` - Update workflow and output sections

**Phase Verification:**
- [ ] Subtask creation requires dependency fields
- [ ] Output includes explicit execution strategy
- [ ] Phase gate enforcement documented

---

### Phase 3: Update Global Framework (CLAUDE.md)

**Objective**: Add dispatch validation to Central AI operational protocols

**Sequential Tasks:**

1. **Task 3A: Add Pre-Dispatch Validation Section**
   - File: `/Users/aiml/.claude/CLAUDE.md`
   - Add to "Agent Coordination" section:
     ```
     ### Pre-Dispatch Validation (MANDATORY)

     Before invoking Task tool for sub-agents, Central AI MUST:

     1. **Check Dependencies**: All DEPENDENCIES tasks are "completed"
     2. **Verify Phase Gates**: Previous phase review gate passed
     3. **Validate File Ownership**: No overlap between parallel tasks
     4. **Confirm PARALLEL_SAFE**: Explicit true for all parallel batch members

     **If ANY check fails:**
     - Do NOT dispatch in parallel
     - Sequence the tasks instead
     - Log the reason for sequencing
     ```

2. **Task 3B: Add Conservative Default Principle**
   - Add to "Operational Protocols" section:
     ```
     ### Stability Over Speed Principle

     **Default Behavior**: When orchestration uncertainty exists:
     - Assume dependencies exist (sequence by default)
     - Assume file conflicts possible (don't parallelize)
     - Verify completion before proceeding (check, don't assume)

     **Parallelization requires EXPLICIT verification**, not absence of known conflicts.

     **Principle**: Methodical and stable > ultra-parallel and brittle
     ```

3. **Task 3C: Add Dispatch Decision Flowchart**
   - Add visual decision tree:
     ```
     Can I parallelize these tasks?
     │
     ├── Do they have explicit PARALLEL_SAFE=true?
     │   └── No → SEQUENCE
     │
     ├── Do they share ANY files?
     │   └── Yes → SEQUENCE or CONSOLIDATE
     │
     ├── Are all dependency tasks completed?
     │   └── No → WAIT
     │
     ├── Did previous phase gate pass?
     │   └── No → WAIT
     │
     └── All checks pass → PARALLEL OK
     ```

**Files to Modify:**
- `/Users/aiml/.claude/CLAUDE.md` - Add 3 new subsections to Agent Coordination

**Phase Verification:**
- [ ] Pre-dispatch validation section exists
- [ ] Conservative default principle documented
- [ ] Decision flowchart included

---

### Phase 4: Final Review

**Objective**: Validate all changes work together coherently

**Sequential Tasks:**

1. **Task 4A: Cross-Reference Validation**
   - Verify skill references match agent config
   - Verify CLAUDE.md references match skill definitions
   - Check for contradictions or ambiguities

2. **Task 4B: Test Scenario Walkthrough**
   - Walk through a sample multi-phase plan
   - Verify the new rules would catch unsafe parallelization
   - Verify legitimate parallel work isn't blocked

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before completing

---

## Testing Strategy

**Scenario Testing:**
1. Create mock plan with intentional dependency violations
2. Verify pre-dispatch validation would catch them
3. Create mock plan with legitimate parallel work
4. Verify it's not over-constrained

**Integration Testing:**
- Next real multi-phase implementation uses new protocols
- Validate delays are reduced but stability maintained

## Rollback Plan
- All changes are to documentation/configuration files
- Git revert to previous commits if issues arise
- No code changes to rollback

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-constraining parallelism | Med | Med | Explicit PARALLEL_SAFE flag allows opt-in |
| Increased planning overhead | Low | Low | Dependency fields become habit |
| Contradictory instructions | Low | High | Phase 4 cross-reference validation |
| Central AI ignoring rules | Med | Med | CLAUDE.md is always in context |

## Open Questions

1. **Should PARALLEL_SAFE default to true or false?**
   - Recommendation: false (conservative)
   - User preference?

2. **How strict should file ownership validation be?**
   - Strict: ANY shared file → sequence
   - Loose: Only same function/section → sequence
   - Recommendation: Strict (safer)

3. **Should we add explicit "completion verification" tool calls?**
   - E.g., require Central AI to read session file to verify task status before dispatch
   - This adds overhead but ensures accuracy

---

**USER: Please review this plan. Edit any section directly, then confirm to proceed.**
