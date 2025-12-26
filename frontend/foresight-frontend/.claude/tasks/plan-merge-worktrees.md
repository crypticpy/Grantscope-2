# Implementation Plan: Merge All Open Worktrees

Created: 2025-12-25
Status: PENDING APPROVAL

## Summary
Merge 10 open worktrees containing feature branches into the main branch. Three worktrees (016, 020, 021) have already been merged and will be cleaned up. The remaining worktrees need rebasing onto current main (which now includes TypeScript strict mode changes) and careful conflict resolution.

## Scope
### In Scope
- Merge 10 worktrees with actual changes (017, 018, 019, 022, 023, 024, 025, 026, 027, 028)
- Clean up 3 already-merged worktrees (016, 020, 021)
- Resolve merge conflicts with TypeScript strict mode changes
- Verify build, lint, and tests pass after each merge
- Remove worktrees after successful merge

### Out of Scope
- Creating new features
- Modifying any merged code beyond conflict resolution
- Pushing to remote (user will do this)

## Prerequisites
- Current main branch is clean (verified: 629727b)
- Backend running on port 8000 (verified)
- Frontend can build successfully (verified)

## Worktree Status Summary

| # | Worktree | Commits | Key Changes | Conflict Risk |
|---|----------|---------|-------------|---------------|
| 016 | skip-navigation-link | 0 | Already merged | None - cleanup only |
| 017 | empty-state-dashboard | 1 | Dashboard.tsx | Medium - overlaps strict mode |
| 018 | visible-form-labels | 4 | Login.tsx + tests | Medium - overlaps strict mode |
| 019 | button-loading-states | 4 | LoadingButton component, Settings.tsx, Login.tsx | Medium |
| 020 | code-splitting | 0 | Already merged | None - cleanup only |
| 021 | dashboard-queries | 0 | Already merged | None - cleanup only |
| 022 | virtualization | 11 | VirtualizedList/Grid, DiscoverCard, package.json | High - many files |
| 023 | debounce-search | 3 | useDebouncedCallback hook, Discover.tsx | Low |
| 024 | memoize-callbacks | 10 | DiscoveryQueue.tsx, SwipeableCard | Medium |
| 025 | carddetail-refactor | 21 | New CardDetail directory structure | High - major refactor |
| 026 | parsestagenumber | 6 | stage-utils.ts, multiple component updates | Medium |
| 027 | badge-utilities | 12 | badge-utils.ts, all badge components | Medium |
| 028 | typescript-strict | 0 | Already merged (we just did this) | None - cleanup only |

## Parallel Execution Strategy

Due to the sequential nature of git merges (each merge changes main, affecting subsequent merges), we will process worktrees sequentially but can parallelize verification tasks within each phase.

### Workstream Analysis
| Workstream | Agent Type | Tasks | Dependencies |
|------------|------------|-------|--------------|
| Cleanup | Opus sub-agent | Remove already-merged worktrees | None |
| Merge-Simple | Central AI | Merge low-conflict worktrees | After cleanup |
| Merge-Complex | Opus sub-agents | Merge high-conflict worktrees with resolution | After simple merges |
| Verification | Opus sub-agents | Run tests, lint, build in parallel | After each merge |

## Implementation Phases

### Phase 1: Cleanup Already-Merged Worktrees
**Objective**: Remove worktrees that have no unique changes

**Sequential Tasks** (must run in order due to git state):
1. Delete worktree 016-add-skip-navigation-link
2. Delete worktree 020-implement-route-based-code-splitting
3. Delete worktree 021-consolidate-dashboard-supabase-queries
4. Delete worktree 028-enable-typescript-strict-mode (we just merged this on main)

**Commands**:
```bash
git worktree remove .worktrees/016-add-skip-navigation-link-for-keyboard-accessibilit --force
git worktree remove .worktrees/020-implement-route-based-code-splitting-with-react-la --force
git worktree remove .worktrees/021-consolidate-dashboard-supabase-queries-into-single --force
git worktree remove .worktrees/028-enable-typescript-strict-mode-and-fix-any-type-usa --force
git branch -D auto-claude/016-add-skip-navigation-link-for-keyboard-accessibilit
git branch -D auto-claude/020-implement-route-based-code-splitting-with-react-la
git branch -D auto-claude/021-consolidate-dashboard-supabase-queries-into-single
git branch -D auto-claude/028-enable-typescript-strict-mode-and-fix-any-type-usa
```

**Phase Verification**:
- [ ] `git worktree list` shows only 9 worktrees (main + 9 active)
- [ ] Deleted branches no longer appear in `git branch`

---

### Phase 2: Merge Low-Conflict Worktrees
**Objective**: Merge worktrees with minimal expected conflicts

**Order** (based on dependency and conflict risk):
1. **017-empty-state-dashboard** (1 commit, touches Dashboard.tsx)
2. **023-debounce-search** (3 commits, new hook + Discover.tsx)
3. **026-parsestagenumber** (6 commits, new utility + component updates)

**Process for each**:
1. Checkout main, ensure clean
2. Merge the feature branch
3. If conflicts, resolve by keeping strict mode changes + feature additions
4. Run verification (lint, typecheck, test, build)
5. Commit merge
6. Remove worktree

**Files to Watch for Conflicts**:
- `src/pages/Dashboard.tsx` - 017 adds empty state, main has strict fixes
- `src/pages/Discover.tsx` - 023 adds debounce, main has strict fixes
- `src/pages/CardDetail.tsx` - 026 removes parseStageNumber, main has strict fixes
- `src/components/PersonalizedQueue.tsx` - 026 updates, main has strict fixes
- `src/components/visualizations/TrendComparisonView.tsx` - 026 updates, main has strict fixes

**Phase Verification**:
- [ ] All 3 branches merged successfully
- [ ] `npm run lint` passes
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` passes
- [ ] `npm run build` succeeds

---

### Phase 3: Merge Medium-Conflict Worktrees
**Objective**: Merge worktrees with moderate expected conflicts

**Order**:
1. **018-visible-form-labels** (4 commits, Login.tsx changes + new tests)
2. **019-button-loading-states** (4 commits, new LoadingButton, Login/Settings changes)
3. **024-memoize-callbacks** (10 commits, DiscoveryQueue optimizations)
4. **027-badge-utilities** (12 commits, new utilities + badge component updates)

**Files to Watch for Conflicts**:
- `src/pages/Login.tsx` - 018 & 019 both modify this, plus main strict fixes
- `src/pages/Settings.tsx` - 019 adds loading to sign-out
- `src/pages/DiscoveryQueue.tsx` - 024 adds memoization, main has strict fixes
- `src/components/HorizonBadge.tsx` - 027 refactors, main has strict fixes
- Various badge components - 027 refactors all

**Phase Verification**:
- [ ] All 4 branches merged successfully
- [ ] `npm run lint` passes
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` passes
- [ ] `npm run build` succeeds

---

### Phase 4: Merge High-Conflict Worktrees
**Objective**: Merge the two largest/most complex worktrees

**Order**:
1. **022-virtualization** (11 commits, new packages, VirtualizedList/Grid, major Discover changes)
2. **025-carddetail-refactor** (21 commits, complete CardDetail restructure)

**022 Key Files**:
- `package.json` / `pnpm-lock.yaml` - adds @tanstack/react-virtual
- New files: VirtualizedList.tsx, VirtualizedGrid.tsx, DiscoverCard.tsx, DiscoveryQueueCard.tsx
- `src/pages/Discover.tsx` - major changes for virtualization
- `src/pages/DiscoveryQueue.tsx` - major changes for virtualization

**025 Key Files**:
- New directory: `src/components/CardDetail/` with ~25 new files
- `src/pages/CardDetail.tsx` - becomes thin wrapper
- Multiple hooks, tabs, and utility files

**Phase Verification**:
- [ ] All 2 branches merged successfully
- [ ] `npm run lint` passes
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` passes
- [ ] `npm run build` succeeds

---

### Phase 5: Final Cleanup and Verification
**Objective**: Ensure all worktrees are cleaned up and codebase is stable

**Parallel Tasks**:
1. Remove all successfully merged worktree directories
2. Delete all merged feature branches
3. Run full verification suite

**Final Verification**:
- [ ] `git worktree list` shows only main
- [ ] `git branch` shows only main (and remote tracking)
- [ ] Full test suite passes
- [ ] Production build succeeds
- [ ] No TypeScript errors
- [ ] No ESLint errors

---

## Final Deliverable Review
**MANDATORY**: After all phases complete:
1. `final-review-completeness` - Verify no incomplete merges or leftover conflicts
2. `principal-code-reviewer` - Ensure merged code maintains quality standards

## Testing Strategy
- After each merge: `npm run lint && npx tsc --noEmit && npm run test`
- After all merges: Full build verification with `npm run build`
- Manual: Start dev server and verify app loads correctly

## Rollback Plan
- Before each merge, note current HEAD: `git rev-parse HEAD`
- If merge fails badly: `git merge --abort` or `git reset --hard <previous-HEAD>`
- Keep backup of working state before complex merges

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TypeScript strict conflicts | High | Medium | Accept main's strict fixes, apply feature on top |
| Overlapping file changes | Medium | Medium | Merge in dependency order, simpler first |
| Test failures after merge | Medium | Low | Run tests after each merge, fix before proceeding |
| Build failures | Low | Medium | Verify build after each phase |
| Worktree state corruption | Low | High | Use --force flag, delete branches after |

## Open Questions
- None - proceeding with sequential merge strategy

---
**USER: Please review this plan. Edit any section directly, then confirm to proceed.**
