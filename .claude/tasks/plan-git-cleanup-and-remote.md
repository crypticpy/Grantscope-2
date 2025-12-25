# Implementation Plan: Git Cleanup, Branch Merging & Remote Repository Setup

Created: 2025-12-24
Status: PENDING APPROVAL

## Summary

Clean up the git repository by removing stale worktrees, merging remaining feature branches (001 and 006) into main, create a new private GitHub repository called `foresight-app`, enhance the README with badges and cleaner formatting, and push everything to origin.

## Scope

### In Scope
- Remove stale worktrees (002, 010 - already merged)
- Delete merged branches (002, 010)
- Commit staged changes (from 006 branch work)
- Merge branch 001 (card creation dates) into main
- Merge branch 006 (advanced search) into main
- Remove remaining worktrees after merge
- Delete remaining branches after merge
- Enhance README.md with badges, better formatting
- Add .worktrees/ to .gitignore
- Create private GitHub repository `foresight-app`
- Push all code to origin

### Out of Scope
- Modifying application code
- Database changes
- Deployment configuration
- CI/CD setup (can be added later)

## Prerequisites
- GitHub CLI (`gh`) installed and authenticated
- Git configured with user credentials

## Parallel Execution Strategy

This task is primarily **sequential** due to git operations that must happen in order. However, some documentation work can be parallelized.

### Workstream Analysis
| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|---------------|
| Git Cleanup | Central AI | Git operations | None |
| README Enhancement | Opus sub-agent | README.md | After git stable |

### File Ownership Matrix
| File | Owner |
|------|-------|
| README.md | README Enhancement agent |
| .gitignore | Central AI |
| Git operations | Central AI (sequential) |

## Implementation Phases

### Phase 1: Git Cleanup - Remove Stale Worktrees & Branches
**Objective**: Clean up already-merged branches and their worktrees

**Sequential Tasks** (must run in order):
1. Remove worktree for 002-enhanced-ai-content-processing-pipeline
2. Remove worktree for 010-complete-discovery-logic-implementation
3. Delete branch auto-claude/002-enhanced-ai-content-processing-pipeline
4. Delete branch auto-claude/010-complete-discovery-logic-implementation

**Commands**:
```bash
git worktree remove .worktrees/002-enhanced-ai-content-processing-pipeline
git worktree remove .worktrees/010-complete-discovery-logic-implementation
git branch -d auto-claude/002-enhanced-ai-content-processing-pipeline
git branch -d auto-claude/010-complete-discovery-logic-implementation
```

**Phase Verification**:
- [ ] `git worktree list` shows only 3 worktrees (main, 001, 006)
- [ ] `git branch` shows only 3 branches (main, 001, 006)

---

### Phase 2: Commit Staged Changes
**Objective**: Commit the staged changes that appear to be from branch 006 work

**Sequential Tasks**:
1. Review staged changes
2. Commit with appropriate message

**Commands**:
```bash
git status
git commit -m "feat: Add advanced search and filtering infrastructure"
```

**Phase Verification**:
- [ ] `git status` shows no staged changes

---

### Phase 3: Merge Remaining Feature Branches
**Objective**: Merge 001 and 006 branches into main

**Sequential Tasks**:
1. Merge branch 001 (card creation dates and sorting)
2. Resolve any conflicts if needed
3. Merge branch 006 (advanced search and filtering)
4. Resolve any conflicts if needed

**Commands**:
```bash
git merge auto-claude/001-add-card-creation-dates-and-sorting -m "Merge branch 001: Card creation dates and sorting"
git merge auto-claude/006-advanced-search-and-filtering -m "Merge branch 006: Advanced search and filtering"
```

**Phase Verification**:
- [ ] Both branches merged successfully
- [ ] `git log --oneline -5` shows merge commits

---

### Phase 4: Clean Up Remaining Worktrees & Branches
**Objective**: Remove the now-merged worktrees and branches

**Sequential Tasks**:
1. Remove worktree for 001
2. Remove worktree for 006
3. Delete branch 001
4. Delete branch 006

**Commands**:
```bash
git worktree remove .worktrees/001-add-card-creation-dates-and-sorting
git worktree remove .worktrees/006-advanced-search-and-filtering
git branch -d auto-claude/001-add-card-creation-dates-and-sorting
git branch -d auto-claude/006-advanced-search-and-filtering
```

**Phase Verification**:
- [ ] `git worktree list` shows only main worktree
- [ ] `git branch` shows only main branch
- [ ] `.worktrees/` directory is empty or can be deleted

---

### Phase 5: Update .gitignore
**Objective**: Add .worktrees/ to .gitignore to prevent future tracking

**Files to Modify**:
- `.gitignore` - Add `.worktrees/` pattern

**Phase Verification**:
- [ ] `.gitignore` contains `.worktrees/` entry

---

### Phase 6: Enhance README (Optional)
**Objective**: Polish the README with badges and cleaner formatting

The current README is already comprehensive. Minor enhancements:
- Add status badges (build, license, etc.)
- Add table of contents
- Minor formatting improvements

**Files to Modify**:
- `README.md` - Add badges, TOC, polish

**Phase Verification**:
- [ ] README renders correctly with badges

---

### Phase 7: Create GitHub Repository & Push
**Objective**: Create private repo and push all code

**Sequential Tasks**:
1. Create private GitHub repository using `gh` CLI
2. Add remote origin
3. Push main branch to origin
4. Verify push succeeded

**Commands**:
```bash
gh repo create foresight-app --private --source=. --remote=origin --push
```

**Phase Verification**:
- [ ] `git remote -v` shows origin pointing to GitHub
- [ ] Repository visible at github.com/[username]/foresight-app
- [ ] All code pushed successfully

---

## Final Deliverable Review

**MANDATORY**: After all phases complete:
1. Verify repository is private on GitHub
2. Verify all branches merged and cleaned up
3. Verify .gitignore updated
4. Verify README displays correctly on GitHub

## Rollback Plan

- If merge conflicts are too complex: `git merge --abort`
- If repository creation fails: Can retry or create manually via GitHub web UI
- If push fails: Check authentication and try again

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Merge conflicts | Medium | Medium | Review conflicts carefully, keep both changes where possible |
| GitHub CLI not authenticated | Low | Low | Run `gh auth login` if needed |
| Branch already deleted | Low | Low | Use `-D` force delete if needed |

## Open Questions

None - task is straightforward.

---
**USER: Please review this plan. Edit any section directly, then confirm to proceed.**
