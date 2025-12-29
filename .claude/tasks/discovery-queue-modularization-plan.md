# Implementation Plan: DiscoveryQueue Modularization

Created: 2025-12-28
Status: PENDING APPROVAL

## Summary

Restore the full DiscoveryQueue component from the 1747-line backup file using a modular structure. The component will be split into reusable components, custom hooks, types (already done), and utilities (already done), following the CardDetail component pattern established in the codebase.

## Scope

### In Scope
- Extract `ImpactScoreBadge` and `ImpactScoreTooltipContent` to `components/ImpactScoreBadge.tsx`
- Extract `SwipeableCard` to `components/SwipeableCard.tsx`
- Extract `UndoToast` to `components/UndoToast.tsx`
- Extract queue card rendering to `components/QueueCard.tsx`
- Extract undo/toast logic to `hooks/useUndoManager.ts`
- Create barrel exports in `components/index.ts` and `hooks/index.ts`
- Create main `index.tsx` with documentation following CardDetail pattern
- Restore keyboard shortcuts (useHotkeys) after modularization
- Ensure types.ts and utils.ts are properly integrated

### Out of Scope
- Changing functionality (pure refactor)
- Adding tests (can be done later)
- Modularizing other pages

## Prerequisites
- The useScrollRestoration hook fix is already deployed (v9 confirmed working)
- types.ts and utils.ts already exist with correct content
- Backup file exists at DiscoveryQueue.backup.tsx

## Parallel Execution Strategy

This is a focused modularization task that can be parallelized at the component extraction level. Each component is independent and can be extracted in parallel.

### Workstream Analysis

| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|---------------|
| Component Extraction 1 | forge-frontend-architect | ImpactScoreBadge.tsx, SwipeableCard.tsx | None |
| Component Extraction 2 | forge-frontend-architect | UndoToast.tsx, QueueCard.tsx | None |
| Hook Extraction | forge-frontend-architect | hooks/useUndoManager.ts, hooks/index.ts | None |
| Main Component | forge-frontend-architect | index.tsx, components/index.ts | All above |

### File Ownership Matrix

| File | Phase | Owner |
|------|-------|-------|
| components/ImpactScoreBadge.tsx | 1 | Stream 1 |
| components/SwipeableCard.tsx | 1 | Stream 1 |
| components/UndoToast.tsx | 1 | Stream 2 |
| components/QueueCard.tsx | 1 | Stream 2 |
| hooks/useUndoManager.ts | 1 | Stream 3 |
| hooks/index.ts | 2 | Sequential |
| components/index.ts | 2 | Sequential |
| index.tsx | 2 | Sequential |

## Implementation Phases

### Phase 1: Component & Hook Extraction (Parallel)

**Objective**: Extract reusable components and hooks from backup file

**Parallel Tasks** (run simultaneously via Opus sub-agents):

1. **Task 1A: ImpactScoreBadge & SwipeableCard** - Owns: `components/ImpactScoreBadge.tsx`, `components/SwipeableCard.tsx`
   - Extract lines 149-236 (ImpactScoreTooltipContent, ImpactScoreBadge)
   - Extract lines 259-533 (SwipeableCard with areSwipeableCardPropsEqual)
   - Import getImpactLevel from utils.ts
   - Import SWIPE_CONFIG from types.ts

2. **Task 1B: UndoToast & QueueCard** - Owns: `components/UndoToast.tsx`, `components/QueueCard.tsx`
   - Extract lines 535-631 (getActionDescription, UndoToast)
   - Extract QueueCard from renderItem (lines 1541-1721) as separate component
   - Import UNDO_TIMEOUT_MS from types.ts

3. **Task 1C: Undo Manager Hook** - Owns: `hooks/useUndoManager.ts`
   - Extract undo stack logic (lines 669-676, 753-807, 812-829, 834-878)
   - Include: pushToUndoStack, undoLastAction, canUndo, getLastUndoableAction
   - Include: toast timer management (showToast, dismissToast, handleUndoFromToast)
   - Return all state and handlers

**Files to Modify**:
- None (all new files)

**New Files to Create**:
- `src/pages/DiscoveryQueue/components/ImpactScoreBadge.tsx`
- `src/pages/DiscoveryQueue/components/SwipeableCard.tsx`
- `src/pages/DiscoveryQueue/components/UndoToast.tsx`
- `src/pages/DiscoveryQueue/components/QueueCard.tsx`
- `src/pages/DiscoveryQueue/hooks/useUndoManager.ts`

**Phase Verification**:
- [ ] Each file compiles without TypeScript errors
- [ ] Imports are correct (relative to new locations)
- [ ] No circular dependencies

**Phase Review Gate**:
- [ ] Review each extracted component for correctness
- [ ] Verify all imports reference types.ts and utils.ts correctly

### Phase 2: Integration & Barrel Exports

**Objective**: Create barrel exports and integrate components into main file

**Sequential Tasks** (must run in order after Phase 1):

1. **Create hooks/index.ts** - Export useUndoManager with types
2. **Create components/index.ts** - Export all components
3. **Create index.tsx** - Main DiscoveryQueue component with:
   - JSDoc documentation following CardDetail pattern
   - Import from ./components, ./hooks, ./types, ./utils
   - Restore full functionality including useHotkeys
   - Remove debug render counter
   - Update version marker to [v10-modular]

**Files to Modify**:
- `src/pages/DiscoveryQueue.tsx` - Replace with import from DiscoveryQueue/index.tsx

**New Files to Create**:
- `src/pages/DiscoveryQueue/hooks/index.ts`
- `src/pages/DiscoveryQueue/components/index.ts`
- `src/pages/DiscoveryQueue/index.tsx`

**Phase Verification**:
- [ ] `pnpm build` succeeds
- [ ] No TypeScript errors
- [ ] Component renders correctly
- [ ] Keyboard shortcuts work
- [ ] Swipe gestures work
- [ ] Undo functionality works

**Phase Review Gate**:
- [ ] Run `principal-code-reviewer` agent on full module
- [ ] Verify barrel exports follow CardDetail pattern

## Final Deliverable Review

**MANDATORY**: After all phases complete:
1. `final-review-completeness` - Scan for incomplete items, TODOs, mocks
2. `principal-code-reviewer` - Full quality assessment

## Testing Strategy

- Manual testing: Navigate to /discover/queue, verify rendering
- Manual testing: Test swipe gestures on mobile
- Manual testing: Test keyboard shortcuts (j/k/f/d/z)
- Manual testing: Test undo functionality
- Verify no infinite re-render (console should not show rapid render counts)

## Rollback Plan

- Keep DiscoveryQueue.backup.tsx as reference
- If modularization fails, can restore from backup
- Git branch allows easy revert

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import path errors | Medium | Low | Verify all relative paths |
| Missing dependency in extracted component | Low | Medium | Compare against backup file |
| Circular dependencies | Low | High | Keep components isolated |
| useHotkeys causing re-render again | Low | High | Use memoized options pattern |

## File Structure After Modularization

```
src/pages/DiscoveryQueue/
├── index.tsx                 # Main component with exports + docs
├── types.ts                  # (exists) Types and constants
├── utils.ts                  # (exists) Utility functions
├── components/
│   ├── index.ts              # Barrel exports
│   ├── ImpactScoreBadge.tsx  # Impact score display
│   ├── SwipeableCard.tsx     # Touch gesture wrapper
│   ├── UndoToast.tsx         # Undo notification
│   └── QueueCard.tsx         # Individual card rendering
└── hooks/
    ├── index.ts              # Barrel exports
    └── useUndoManager.ts     # Undo state management
```

---
**USER: Please review this plan. Edit any section directly, then confirm to proceed.**
