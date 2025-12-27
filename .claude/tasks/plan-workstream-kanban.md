# Implementation Plan: Workstream Kanban Research Companion

Created: 2025-12-25
Status: PENDING APPROVAL

## Summary

Transform the Workstreams feature from a simple filter-based card list into a full **Kanban Research Companion** with 6 columns (Inbox → Screening → Research → Brief → Watching → Archived), drag-and-drop functionality, card actions (notes, reminders, deep dive requests), and auto-population from the existing AI research system. This leverages the existing `workstream_cards` junction table, research service, and card follow patterns.

## Scope

### In Scope
- Database migration: Add `status` column to `workstream_cards` table for kanban state
- New KanbanBoard component with drag-and-drop (using @dnd-kit library)
- Card actions: Add to workstream, notes, request deep dive, set reminder
- Navigation: Make workstream cards clickable to open the kanban view
- Integration with existing research service for "Request Deep Dive" action
- Auto-population: Cards matching workstream filters auto-add to "Inbox" column
- Mobile-responsive kanban layout

### Out of Scope
- Collaborative/shared workstreams (future phase)
- Real-time sync between users (future phase)
- Workstream analytics dashboard (future phase)
- Email notifications for workstream updates (future phase)

## Prerequisites
- Install @dnd-kit packages for drag-and-drop
- Existing research service endpoints functional
- Backend running and healthy

## Parallel Execution Strategy

Work is divided into 4 independent workstreams that can execute in parallel using my sub agents, with clear file ownership to prevent conflicts.

### Workstream Analysis
| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|---------------|
| Database & API | backend-engineer | Supabase migration, main.py API endpoints | None |
| Kanban Components | fullstack-architect | New kanban components in frontend | Database schema |
| Workstream Pages | fullstack-architect | Workstreams.tsx, WorkstreamKanban.tsx | Kanban components |
| Integration & Actions | fullstack-architect | Card actions, research integration | API endpoints |

### File Ownership Matrix

**Database/Backend (Agent A):**
- `/supabase/migrations/XXXX_workstream_kanban.sql` (NEW)
- `/backend/app/main.py` (lines for new endpoints only)

**Kanban Components (Agent B):**
- `/frontend/src/components/kanban/KanbanBoard.tsx` (NEW)
- `/frontend/src/components/kanban/KanbanColumn.tsx` (NEW)
- `/frontend/src/components/kanban/KanbanCard.tsx` (NEW)
- `/frontend/src/components/kanban/index.ts` (NEW)

**Workstream Pages (Agent C):**
- `/frontend/src/pages/Workstreams.tsx` (MODIFY - add navigation)
- `/frontend/src/pages/WorkstreamKanban.tsx` (NEW - main kanban page)
- `/frontend/src/App.tsx` (MODIFY - add route)

**Integration & Actions (Agent D):**
- `/frontend/src/components/kanban/CardActions.tsx` (NEW)
- `/frontend/src/components/kanban/AddCardToWorkstream.tsx` (NEW)
- `/frontend/src/lib/workstream-api.ts` (NEW)

---

## Implementation Phases

### Phase 1: Foundation (Database + Dependencies)
**Objective**: Set up database schema and install required packages

**Parallel Tasks:**

1. **Task 1A: Database Migration** - Owns: `supabase/migrations/`
   - Create migration file `1766437000_workstream_kanban.sql`
   - Add `status` column to `workstream_cards` table
   - Add `position` column for ordering within columns
   - Add `notes` column for user annotations
   - Add `reminder_at` column for reminders
   - Add `added_from` column (manual, auto, follow)
   - Create index on (workstream_id, status)
   - Add RLS policies for new columns

2. **Task 1B: Install Dependencies** - Owns: `package.json`
   - Install `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`
   - Run `pnpm install`

**Schema for `workstream_cards` update:**
```sql
ALTER TABLE workstream_cards
ADD COLUMN status TEXT DEFAULT 'inbox'
    CHECK (status IN ('inbox', 'screening', 'research', 'brief', 'watching', 'archived')),
ADD COLUMN position INTEGER DEFAULT 0,
ADD COLUMN notes TEXT,
ADD COLUMN reminder_at TIMESTAMPTZ,
ADD COLUMN added_from TEXT DEFAULT 'manual'
    CHECK (added_from IN ('manual', 'auto', 'follow'));

CREATE INDEX idx_workstream_cards_status ON workstream_cards(workstream_id, status);
```

**Phase Verification:**
- [ ] Migration runs without errors
- [ ] Dependencies install successfully
- [ ] Supabase schema reflects new columns

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 2: API Endpoints
**Objective**: Create backend API for kanban operations

**Sequential Tasks (depends on Phase 1):**

1. **Task 2A: Workstream Card API** - Owns: `/backend/app/main.py` (new endpoints only)

   **New Endpoints:**
   ```
   GET  /api/v1/me/workstreams/{id}/cards
        Returns all cards in workstream grouped by status
        Response: { inbox: Card[], screening: Card[], ... }

   POST /api/v1/me/workstreams/{id}/cards
        Add a card to workstream
        Body: { card_id, status?, notes? }

   PATCH /api/v1/me/workstreams/{id}/cards/{card_id}
        Update card status/position/notes
        Body: { status?, position?, notes?, reminder_at? }

   DELETE /api/v1/me/workstreams/{id}/cards/{card_id}
        Remove card from workstream

   POST /api/v1/me/workstreams/{id}/cards/{card_id}/deep-dive
        Trigger deep research for card (calls existing research service)

   POST /api/v1/me/workstreams/{id}/auto-populate
        Manually trigger auto-population of inbox from filters
   ```

**Files to Modify:**
- `/backend/app/main.py` - Add new route handlers (~150 lines)

**Phase Verification:**
- [ ] All endpoints return correct status codes
- [ ] RLS policies enforced (user can only access own workstreams)
- [ ] Deep dive triggers research task correctly

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 3: Kanban UI Components
**Objective**: Build reusable kanban board components with drag-and-drop

**Parallel Tasks:**

1. **Task 3A: Core Kanban Components** - Owns: `/frontend/src/components/kanban/`

   **KanbanBoard.tsx** (~200 lines):
   - DndContext provider with sensors
   - Horizontal scroll for columns on mobile
   - Column drop zones
   - Drag overlay for visual feedback

   **KanbanColumn.tsx** (~150 lines):
   - SortableContext for cards within column
   - Column header with count badge
   - Empty state message
   - Droppable area styling

   **KanbanCard.tsx** (~180 lines):
   - useSortable hook for drag handle
   - Card preview (name, pillar badge, horizon, stage)
   - Quick actions (notes, deep dive, archive)
   - Visual feedback during drag

   **Types:**
   ```typescript
   type KanbanStatus = 'inbox' | 'screening' | 'research' | 'brief' | 'watching' | 'archived';

   interface WorkstreamCard {
     id: string;
     card_id: string;
     workstream_id: string;
     status: KanbanStatus;
     position: number;
     notes: string | null;
     reminder_at: string | null;
     added_from: 'manual' | 'auto' | 'follow';
     card: {
       id: string;
       name: string;
       summary: string;
       pillar_id: string;
       stage_id: number;
       horizon: 'H1' | 'H2' | 'H3';
       novelty_score: number;
       // ... other card fields
     };
   }
   ```

2. **Task 3B: Workstream API Client** - Owns: `/frontend/src/lib/workstream-api.ts`
   - `fetchWorkstreamCards(workstreamId): Promise<GroupedCards>`
   - `addCardToWorkstream(workstreamId, cardId, status?): Promise<WorkstreamCard>`
   - `updateCardStatus(workstreamId, cardId, status, position): Promise<void>`
   - `updateCardNotes(workstreamId, cardId, notes): Promise<void>`
   - `removeCardFromWorkstream(workstreamId, cardId): Promise<void>`
   - `triggerDeepDive(workstreamId, cardId): Promise<ResearchTask>`
   - `autoPopulateInbox(workstreamId): Promise<{ added: number }>`

**New Files to Create:**
- `/frontend/src/components/kanban/KanbanBoard.tsx`
- `/frontend/src/components/kanban/KanbanColumn.tsx`
- `/frontend/src/components/kanban/KanbanCard.tsx`
- `/frontend/src/components/kanban/index.ts`
- `/frontend/src/lib/workstream-api.ts`

**Phase Verification:**
- [ ] Drag and drop works smoothly
- [ ] Cards can move between columns
- [ ] Position ordering persists
- [ ] Mobile horizontal scroll works

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 4: Page Integration
**Objective**: Integrate kanban into workstream pages with navigation

**Parallel Tasks:**

1. **Task 4A: WorkstreamKanban Page** - Owns: `/frontend/src/pages/WorkstreamKanban.tsx`
   - Route: `/workstreams/:id/board`
   - Workstream header with name, description, filters summary
   - KanbanBoard component with 6 columns
   - Column definitions:
     ```typescript
     const COLUMNS: { id: KanbanStatus; title: string; description: string }[] = [
       { id: 'inbox', title: 'Inbox', description: 'New cards matching your filters' },
       { id: 'screening', title: 'Screening', description: 'Quick triage - is this relevant?' },
       { id: 'research', title: 'Research', description: 'Deep investigation in progress' },
       { id: 'brief', title: 'Brief', description: 'Ready to present to leadership' },
       { id: 'watching', title: 'Watching', description: 'Monitoring for updates' },
       { id: 'archived', title: 'Archived', description: 'No longer active' },
     ];
     ```
   - Toolbar: Refresh inbox, Export report, Edit filters
   - Stats bar: Card counts per column

2. **Task 4B: Navigation Updates** - Owns: `/frontend/src/pages/Workstreams.tsx`, `/frontend/src/App.tsx`

   **Workstreams.tsx changes:**
   - Make entire WorkstreamCard clickable (wrap in Link)
   - Navigate to `/workstreams/:id/board` on click
   - Keep Edit/Delete buttons with stopPropagation

   **App.tsx changes:**
   - Add route: `<Route path="/workstreams/:id/board" element={<WorkstreamKanban />} />`

3. **Task 4C: Card Actions Component** - Owns: `/frontend/src/components/kanban/CardActions.tsx`
   - Dropdown menu on KanbanCard
   - Actions: View Details, Add Notes, Request Deep Dive, Set Reminder, Move to Column, Remove
   - Notes modal with textarea
   - Deep dive triggers research service
   - Reminder date picker

**Files to Modify:**
- `/frontend/src/pages/Workstreams.tsx` - Add Link wrapper (~20 lines)
- `/frontend/src/App.tsx` - Add route (~3 lines)

**New Files to Create:**
- `/frontend/src/pages/WorkstreamKanban.tsx` (~400 lines)
- `/frontend/src/components/kanban/CardActions.tsx` (~200 lines)

**Phase Verification:**
- [ ] Clicking workstream navigates to board view
- [ ] Board loads cards in correct columns
- [ ] Card actions work (notes, deep dive, move)
- [ ] Export generates PDF/PPTX

**Phase Review Gate:**
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 5: Auto-Population & Polish
**Objective**: Connect auto-population and add finishing touches

**Sequential Tasks:**

1. **Task 5A: Auto-Population Logic** - Owns: Backend logic
   - When user opens workstream board, check for new matching cards
   - Compare cards matching filter criteria vs cards already in workstream
   - Auto-add new matches to "inbox" with `added_from: 'auto'`
   - Show toast: "3 new cards added to inbox"

2. **Task 5B: Follow Integration** - Owns: Card detail integration
   - When user follows a card from CardDetail, offer to add to workstream
   - "Add to Workstream" dropdown in card detail header
   - Selected workstream adds card to "screening" (user explicitly followed)

3. **Task 5C: Polish & Testing**
   - Empty state designs for each column
   - Loading skeletons
   - Error boundaries
   - Keyboard navigation (a11y)
   - Mobile touch drag support

**Phase Verification:**
- [ ] Auto-population adds new cards on page load
- [ ] Following a card offers workstream addition
- [ ] All columns have appropriate empty states
- [ ] Mobile drag works with touch

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
   - Security considerations (RLS, auth)
   - Performance (no N+1 queries)
   - Accessibility compliance

---

## Testing Strategy

### Unit Tests (Vitest)
- KanbanBoard: renders columns, handles drag events
- KanbanColumn: renders cards, droppable behavior
- KanbanCard: drag handle, action buttons
- workstream-api.ts: API client functions

### Integration Tests
- Card moves between columns and persists
- Deep dive triggers research task
- Auto-population adds new cards

### E2E Tests (Playwright)
- Navigate to workstream → board loads
- Drag card from inbox to screening
- Click card → opens detail modal
- Request deep dive → research status shows

### Manual Testing
- [ ] Create workstream with filters
- [ ] Verify matching cards appear in inbox
- [ ] Drag card through all columns
- [ ] Add notes to card
- [ ] Request deep dive
- [ ] Export report from board
- [ ] Mobile: swipe to see columns, touch drag

---

## Rollback Plan

1. **Database**: Migration includes `DROP COLUMN IF EXISTS` for rollback
2. **Frontend**: Feature flag `VITE_ENABLE_KANBAN=true` gates new routes
3. **Backend**: New endpoints are additive, old endpoints unchanged
4. **If issues**: Revert to WorkstreamFeed.tsx (existing grid view)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Drag-drop performance with many cards | Med | Med | Virtualize columns if >50 cards |
| Auto-population adds too many cards | Low | Med | Limit to 20 cards per auto-populate |
| Research service rate limits | Low | Low | Show user-friendly message if limited |
| Mobile drag not intuitive | Med | Med | Add tutorial/onboarding hint |
| File conflict between agents | Med | High | Clear file ownership matrix enforced |

---

## Open Questions

1. **Reminder notifications**: Should reminders trigger push notifications or just visual indicators?
2. **Card limits per workstream**: Should we limit total cards (e.g., max 200)?
3. **Archive auto-delete**: Should archived cards auto-delete after 30 days?

---

## Column Definitions Reference

| Column | Purpose | Auto-populated? | Research Actions |
|--------|---------|-----------------|------------------|
| **Inbox** | New matching cards | Yes (from filters) | None |
| **Screening** | Quick triage | From follows | Quick update available |
| **Research** | Active investigation | No | Deep dive available |
| **Brief** | Ready for leadership | No | Export to PDF/PPTX |
| **Watching** | Monitor for changes | No | Auto-update on refresh |
| **Archived** | Completed/dismissed | No | None |

---

**USER: Please review this plan. Edit any section directly, then confirm to proceed.**
