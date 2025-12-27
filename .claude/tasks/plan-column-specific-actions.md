# Implementation Plan: Column-Specific Actions & Feature Complete Kanban

Created: 2025-12-26
Status: PENDING APPROVAL

## Summary

Transform the Workstream Kanban board from having identical actions on all cards to a context-aware system where each column provides relevant research workflow tools. Additionally, implement auto-population on page load, follow-to-workstream integration, and column-specific UI hints. This completes the originally planned kanban feature set.

## Scope

### In Scope
1. **Column-specific card actions** - Different menu items based on which column the card is in
2. **Screening tools** - "Quick Update" action for screening column cards
3. **Research tools** - "Deep Dive" action (already exists, make column-aware)
4. **Brief tools** - "Export to PDF/PPTX" action for individual cards in brief column
5. **Watching tools** - "Check for Updates" action with auto-refresh integration
6. **Auto-population on page load** - Automatically add matching cards to inbox with toast notification
7. **Follow-to-workstream integration** - When following a card, offer to add to a workstream
8. **Column-specific UI hints** - Contextual descriptions in column headers and empty states

### Out of Scope
- Collaborative/shared workstreams
- Real-time sync between users
- Email notifications
- Reminder push notifications

## Prerequisites
- Existing kanban drag-and-drop working (verified)
- Research service endpoints functional (verified)
- Export service endpoints functional (verified)
- Card follow system working (verified)

## Parallel Execution Strategy

Work is divided into 5 independent workstreams that can execute in parallel, with clear file ownership to prevent conflicts.

### Workstream Analysis
| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|---------------|
| Column Actions Types | fullstack-architect | types.ts, CardActions.tsx | None |
| Screening/Research Actions | fullstack-architect | New: ScreeningAction.tsx, useQuickUpdate.ts | Types complete |
| Brief/Export Actions | fullstack-architect | New: BriefExportAction.tsx | Types complete |
| Auto-Population | backend-engineer + fullstack-architect | WorkstreamKanban.tsx (specific sections) | None |
| Follow Integration | fullstack-architect | CardDetail components | None |

### File Ownership Matrix

**Phase 1 - Types & Core (Agent A):**
- `/frontend/src/components/kanban/types.ts` - Add column action definitions
- `/frontend/src/components/kanban/CardActions.tsx` - Refactor for column-aware actions

**Phase 2 - Screening Actions (Agent B):**
- `/frontend/src/components/kanban/actions/ScreeningActions.tsx` (NEW)
- `/frontend/src/components/kanban/actions/useQuickUpdate.ts` (NEW)
- `/frontend/src/components/kanban/actions/index.ts` (NEW)

**Phase 2 - Brief Actions (Agent C):**
- `/frontend/src/components/kanban/actions/BriefActions.tsx` (NEW)
- `/frontend/src/components/kanban/actions/useCardExport.ts` (NEW - kanban-specific)

**Phase 2 - Watching Actions (Agent D):**
- `/frontend/src/components/kanban/actions/WatchingActions.tsx` (NEW)
- `/frontend/src/components/kanban/actions/useCheckUpdates.ts` (NEW)

**Phase 3 - Auto-Population (Agent E):**
- `/frontend/src/pages/WorkstreamKanban.tsx` - Lines 440-480 (auto-populate on load)
- `/backend/app/main.py` - Modify auto-populate response

**Phase 4 - Follow Integration (Agent F):**
- `/frontend/src/components/CardDetail/CardActionButtons.tsx` - Add workstream selector
- `/frontend/src/components/CardDetail/AddToWorkstreamModal.tsx` (NEW)

---

## Implementation Phases

### Phase 1: Column Action Type System
**Objective**: Define the type system for column-specific actions and refactor CardActions

**Sequential Tasks** (must complete before Phase 2):

1. **Task 1A: Extend Column Definitions** - Owns: `types.ts`

   Add to `KanbanColumnDefinition`:
   ```typescript
   interface ColumnAction {
     id: string;
     label: string;
     icon: LucideIcon;
     description?: string;
     /** Action handler receives card and returns Promise */
     handler?: 'quickUpdate' | 'deepDive' | 'exportPdf' | 'exportPptx' | 'checkUpdates' | 'viewDetails' | 'addNotes' | 'remove';
     /** Whether this action is always available or column-specific */
     availability: 'always' | 'column-specific';
   }

   interface KanbanColumnDefinition {
     id: KanbanStatus;
     title: string;
     description: string;
     /** Primary action for this column (shown prominently) */
     primaryAction?: ColumnAction;
     /** Additional column-specific actions */
     secondaryActions?: ColumnAction[];
     /** Hint text shown in empty state */
     emptyStateHint?: string;
   }
   ```

   Update `KANBAN_COLUMNS` with actions:
   ```typescript
   {
     id: 'inbox',
     title: 'Inbox',
     description: 'New cards matching your filters',
     emptyStateHint: 'Cards matching your filters will appear here automatically',
     // No primary action - inbox is for triage
   },
   {
     id: 'screening',
     title: 'Screening',
     description: 'Quick triage - is this relevant?',
     primaryAction: {
       id: 'quick-update',
       label: 'Quick Update',
       icon: RefreshCw,
       description: 'Run a quick 5-source research update',
       handler: 'quickUpdate',
       availability: 'column-specific',
     },
     emptyStateHint: 'Drag cards here to evaluate their relevance',
   },
   {
     id: 'research',
     title: 'Research',
     description: 'Deep investigation in progress',
     primaryAction: {
       id: 'deep-dive',
       label: 'Deep Dive',
       icon: Search,
       description: 'Run comprehensive 15-source research',
       handler: 'deepDive',
       availability: 'column-specific',
     },
     emptyStateHint: 'Cards here are being actively researched',
   },
   {
     id: 'brief',
     title: 'Brief',
     description: 'Ready to present to leadership',
     primaryAction: {
       id: 'export-pdf',
       label: 'Export Brief',
       icon: FileDown,
       description: 'Export card as PDF briefing document',
       handler: 'exportPdf',
       availability: 'column-specific',
     },
     secondaryActions: [{
       id: 'export-pptx',
       label: 'Export Slides',
       icon: Presentation,
       handler: 'exportPptx',
       availability: 'column-specific',
     }],
     emptyStateHint: 'Cards ready for leadership briefings',
   },
   {
     id: 'watching',
     title: 'Watching',
     description: 'Monitoring for updates',
     primaryAction: {
       id: 'check-updates',
       label: 'Check for Updates',
       icon: Bell,
       description: 'Search for recent developments',
       handler: 'checkUpdates',
       availability: 'column-specific',
     },
     emptyStateHint: 'Cards here will be monitored for new developments',
   },
   {
     id: 'archived',
     title: 'Archived',
     description: 'No longer active',
     emptyStateHint: 'Completed or dismissed cards',
     // No primary action - archived cards are dormant
   },
   ```

2. **Task 1B: Refactor CardActions** - Owns: `CardActions.tsx`

   Modify `CardActionsProps` to accept column context:
   ```typescript
   interface CardActionsProps {
     card: WorkstreamCard;
     workstreamId: string;
     /** Current column the card is in - determines available actions */
     columnId: KanbanStatus;
     // ... existing callbacks
     /** New callbacks for column-specific actions */
     onQuickUpdate?: (cardId: string) => Promise<void>;
     onExportPdf?: (cardId: string) => Promise<void>;
     onExportPptx?: (cardId: string) => Promise<void>;
     onCheckUpdates?: (cardId: string) => Promise<void>;
   }
   ```

   Refactor menu rendering to show:
   - **Always visible**: View Details, Add Notes, Move to Column, Remove
   - **Column-specific**: Primary action + secondary actions based on `columnId`
   - Visual separator between universal and column-specific actions

**Files to Modify:**
- `/frontend/src/components/kanban/types.ts` - Add ColumnAction types - Owner: Task 1A
- `/frontend/src/components/kanban/CardActions.tsx` - Refactor for column awareness - Owner: Task 1B

**Phase Verification:**
- [ ] TypeScript compiles without errors
- [ ] CardActions shows different menus for different columns
- [ ] Menu items are properly grouped with separators

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 2: Column-Specific Action Implementations
**Objective**: Implement the actual action handlers for each column type

**Parallel Tasks** (can run simultaneously after Phase 1):

1. **Task 2A: Screening Actions (Quick Update)** - Owns: `actions/ScreeningActions.tsx`, `actions/useQuickUpdate.ts`

   Create hook `useQuickUpdate`:
   ```typescript
   function useQuickUpdate(workstreamId: string) {
     const [isLoading, setIsLoading] = useState<Record<string, boolean>>({});

     const triggerQuickUpdate = async (cardId: string) => {
       setIsLoading(prev => ({ ...prev, [cardId]: true }));
       try {
         // Call existing research endpoint with task_type='update'
         const response = await fetch(`/api/v1/research`, {
           method: 'POST',
           body: JSON.stringify({ card_id: cardId, task_type: 'update' }),
         });
         // Show toast with result
       } finally {
         setIsLoading(prev => ({ ...prev, [cardId]: false }));
       }
     };

     return { triggerQuickUpdate, isLoading };
   }
   ```

2. **Task 2B: Brief Actions (Export)** - Owns: `actions/BriefActions.tsx`, `actions/useCardExport.ts`

   Create hook `useCardExport` (kanban-specific):
   ```typescript
   function useCardExport() {
     const [isExporting, setIsExporting] = useState<Record<string, boolean>>({});

     const exportCard = async (cardId: string, format: 'pdf' | 'pptx') => {
       setIsExporting(prev => ({ ...prev, [cardId]: true }));
       try {
         // Call existing export endpoint
         const response = await fetch(`/api/v1/cards/${cardId}/export/${format}`);
         const blob = await response.blob();
         // Trigger download
       } finally {
         setIsExporting(prev => ({ ...prev, [cardId]: false }));
       }
     };

     return { exportCard, isExporting };
   }
   ```

3. **Task 2C: Watching Actions (Check Updates)** - Owns: `actions/WatchingActions.tsx`, `actions/useCheckUpdates.ts`

   Create hook `useCheckUpdates`:
   ```typescript
   function useCheckUpdates(workstreamId: string) {
     const [isChecking, setIsChecking] = useState<Record<string, boolean>>({});

     const checkForUpdates = async (cardId: string) => {
       setIsChecking(prev => ({ ...prev, [cardId]: true }));
       try {
         // Call research endpoint with task_type='update' (same as quick update)
         // But with different messaging/toast
       } finally {
         setIsChecking(prev => ({ ...prev, [cardId]: false }));
       }
     };

     return { checkForUpdates, isChecking };
   }
   ```

4. **Task 2D: Wire Actions to KanbanCard** - Owns: `KanbanCard.tsx`, `KanbanColumn.tsx`

   Pass `columnId` through the component chain:
   - `KanbanBoard` → `KanbanColumn` (already has `id`)
   - `KanbanColumn` → `KanbanCard` (pass `columnId={id}`)
   - `KanbanCard` → `CardActions` (pass `columnId`)

**New Files to Create:**
- `/frontend/src/components/kanban/actions/index.ts` - Exports
- `/frontend/src/components/kanban/actions/useQuickUpdate.ts` - Screening hook
- `/frontend/src/components/kanban/actions/useCardExport.ts` - Brief export hook
- `/frontend/src/components/kanban/actions/useCheckUpdates.ts` - Watching hook

**Files to Modify:**
- `/frontend/src/components/kanban/KanbanCard.tsx` - Pass columnId
- `/frontend/src/components/kanban/KanbanColumn.tsx` - Pass columnId to cards

**Phase Verification:**
- [ ] Quick Update triggers research task from screening column
- [ ] Export PDF/PPTX downloads file from brief column
- [ ] Check Updates works from watching column
- [ ] Actions only appear in correct columns

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 3: Auto-Population on Page Load
**Objective**: Automatically add matching cards to inbox when opening workstream board

**Sequential Tasks:**

1. **Task 3A: Backend Enhancement** - Owns: `/backend/app/main.py` (auto-populate endpoint)

   Modify `auto_populate_workstream` response to include:
   ```python
   class AutoPopulateResponse(BaseModel):
       added: int
       cards: List[WorkstreamCardWithDetails]
       already_in_workstream: int  # NEW - cards that matched but were already added
       total_matching: int  # NEW - total cards matching filters
   ```

2. **Task 3B: Frontend Auto-Load** - Owns: `/frontend/src/pages/WorkstreamKanban.tsx` (loadCards section)

   Add auto-populate trigger on page load:
   ```typescript
   // In useEffect that loads cards
   useEffect(() => {
     const loadAndAutoPopulate = async () => {
       // 1. Load existing cards
       const existingCards = await fetchWorkstreamCards(token, id);
       setCards(existingCards);

       // 2. Auto-populate inbox with new matches
       try {
         const result = await autoPopulateWorkstream(token, id, 20);
         if (result.added > 0) {
           showToast('info', `${result.added} new card${result.added > 1 ? 's' : ''} added to inbox`);
           // Refresh cards to include new additions
           const refreshedCards = await fetchWorkstreamCards(token, id);
           setCards(refreshedCards);
         }
       } catch (err) {
         // Silent fail - auto-populate is enhancement, not critical
         console.warn('Auto-populate failed:', err);
       }
     };

     loadAndAutoPopulate();
   }, [id]);
   ```

3. **Task 3C: Toast Notification Enhancement** - Owns: Toast component in WorkstreamKanban

   Add 'info' toast type if not exists (blue styling for informational messages)

**Files to Modify:**
- `/backend/app/main.py` - Enhance AutoPopulateResponse
- `/frontend/src/pages/WorkstreamKanban.tsx` - Add auto-populate on load

**Phase Verification:**
- [ ] Opening workstream board triggers auto-populate
- [ ] Toast shows "X new cards added to inbox"
- [ ] New cards appear in inbox column
- [ ] No duplicate cards added

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 4: Follow-to-Workstream Integration
**Objective**: When following a card, offer to add it to a workstream

**Sequential Tasks:**

1. **Task 4A: Add to Workstream Modal** - Owns: New component

   Create `/frontend/src/components/CardDetail/AddToWorkstreamModal.tsx`:
   ```typescript
   interface AddToWorkstreamModalProps {
     isOpen: boolean;
     onClose: () => void;
     cardId: string;
     cardName: string;
     onSuccess: (workstreamName: string) => void;
   }

   // Features:
   // - Fetch user's workstreams
   // - Show list with workstream names and descriptions
   // - "Add to Screening" button for each (adds with status='screening')
   // - Create new workstream option at bottom
   ```

2. **Task 4B: Integrate with Follow Action** - Owns: `CardActionButtons.tsx`

   Modify follow button flow:
   ```typescript
   const handleFollow = async () => {
     // Toggle follow status
     await toggleFollow();

     // If now following, show modal to add to workstream
     if (!isFollowing) { // Was not following, now is
       setShowAddToWorkstreamModal(true);
     }
   };
   ```

3. **Task 4C: Add "Add to Workstream" Standalone Button** - Owns: `CardActionButtons.tsx`

   Add separate button (not just on follow):
   ```typescript
   <button onClick={() => setShowAddToWorkstreamModal(true)}>
     <Plus className="h-4 w-4" />
     Add to Workstream
   </button>
   ```

**New Files to Create:**
- `/frontend/src/components/CardDetail/AddToWorkstreamModal.tsx`

**Files to Modify:**
- `/frontend/src/components/CardDetail/CardActionButtons.tsx` - Add modal trigger
- `/frontend/src/components/CardDetail/CardDetail.tsx` - Pass workstream modal state if needed

**Phase Verification:**
- [ ] Following a card shows "Add to Workstream" modal
- [ ] Modal lists user's workstreams
- [ ] Selecting workstream adds card to screening column
- [ ] Toast confirms addition
- [ ] Standalone "Add to Workstream" button works independently

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 5: Column UI Hints & Polish
**Objective**: Add contextual hints and polish the column experience

**Parallel Tasks:**

1. **Task 5A: Enhanced Column Headers** - Owns: `KanbanColumn.tsx`

   Show primary action as button in column header:
   ```typescript
   {column.primaryAction && cards.length > 0 && (
     <button
       onClick={() => handleBulkAction(column.primaryAction)}
       className="text-xs text-blue-600 hover:text-blue-700"
     >
       <column.primaryAction.icon className="h-3 w-3 mr-1" />
       {column.primaryAction.label} All
     </button>
   )}
   ```

2. **Task 5B: Enhanced Empty States** - Owns: `KanbanColumn.tsx`

   Use `emptyStateHint` from column definition:
   ```typescript
   <EmptyColumnState
     columnId={id}
     hint={columnDefinition.emptyStateHint}
   />
   ```

3. **Task 5C: Loading States for Actions** - Owns: `CardActions.tsx`

   Show spinner on action buttons while processing:
   - Quick Update in progress
   - Export generating
   - Check Updates running

**Files to Modify:**
- `/frontend/src/components/kanban/KanbanColumn.tsx` - Enhanced headers and empty states
- `/frontend/src/components/kanban/CardActions.tsx` - Loading states

**Phase Verification:**
- [ ] Column headers show contextual action buttons
- [ ] Empty states have helpful hints
- [ ] Loading spinners appear during async actions

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

## Final Deliverable Review

**MANDATORY**: After all phases complete, run both review agents on the ENTIRE deliverable:

1. **final-review-completeness** - Full codebase scan for:
   - No TODO/FIXME comments left
   - No placeholder implementations
   - No mock data in production code
   - All error handling complete
   - All loading states implemented

2. **principal-code-reviewer** - Comprehensive quality assessment:
   - Code follows project patterns
   - TypeScript types are complete
   - Security considerations (auth on all endpoints)
   - Performance (no N+1 queries)
   - Accessibility compliance

---

## Testing Strategy

### Unit Tests (Vitest)
- `useQuickUpdate`: triggers research task, handles errors
- `useCardExport`: downloads file, handles formats
- `useCheckUpdates`: triggers update check
- `CardActions`: renders correct actions per column
- `AddToWorkstreamModal`: lists workstreams, adds card

### Integration Tests
- Quick Update from screening column triggers research
- Export from brief column downloads PDF/PPTX
- Auto-populate adds cards on page load
- Follow-to-workstream flow completes

### Manual Testing Checklist
- [ ] Create workstream with filters
- [ ] Open board - verify auto-populate adds matching cards
- [ ] Drag card to screening - verify Quick Update action appears
- [ ] Trigger Quick Update - verify research task runs
- [ ] Drag card to research - verify Deep Dive action
- [ ] Drag card to brief - verify Export PDF/PPTX actions
- [ ] Trigger export - verify file downloads
- [ ] Drag card to watching - verify Check Updates action
- [ ] Follow card from detail page - verify modal appears
- [ ] Add card to workstream from modal - verify card appears in screening

---

## Rollback Plan

1. **Types**: Revert `types.ts` to remove ColumnAction types
2. **CardActions**: Revert to show all actions unconditionally
3. **New Files**: Delete all files in `/actions/` directory
4. **Auto-populate**: Remove useEffect auto-trigger
5. **Follow Modal**: Remove modal component and button

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Research rate limits hit | Low | Med | Show clear message, disable button when limited |
| Export timeout for large cards | Low | Med | Show progress indicator, increase timeout |
| Auto-populate adds too many cards | Low | Med | Limit to 20 cards per load, deduplicate |
| File conflicts between agents | Med | High | Clear file ownership matrix enforced |
| Type changes break existing code | Med | High | Run TypeScript check after Phase 1 |

---

## Open Questions

1. **Bulk Actions**: Should column headers have "Quick Update All" for multiple cards? (Deferred to future)
2. **Auto-populate Frequency**: Should auto-populate run only once per session or every page load? (Current plan: every load)
3. **Archived Restrictions**: Should archived cards have Move action disabled? (Current plan: allow move)

---

**Column Actions Reference**

| Column | Primary Action | Secondary Actions | Handler |
|--------|---------------|-------------------|---------|
| **Inbox** | None | - | - |
| **Screening** | Quick Update | - | `triggerQuickUpdate()` |
| **Research** | Deep Dive | - | `onDeepDive()` (existing) |
| **Brief** | Export PDF | Export PPTX | `exportCard('pdf'\|'pptx')` |
| **Watching** | Check Updates | - | `checkForUpdates()` |
| **Archived** | None | - | - |

**Universal Actions** (all columns):
- View Details
- Add/Edit Notes
- Move to Column
- Remove from Workstream

---

**USER: Please review this plan. Edit any section directly, then confirm to proceed.**
