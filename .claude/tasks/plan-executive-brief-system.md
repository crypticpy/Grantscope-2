# Implementation Plan: Executive Brief Generation System

Created: 2025-12-26
Status: **APPROVED - EXECUTING**

## Summary

Implement a complete Executive Brief generation system for the Foresight platform's workstream Kanban workflow. When cards reach the "Brief" column, users will trigger AI-powered brief generation that produces leadership-ready content. The brief synthesizes the card data, user notes, related cards, and workstream context into a comprehensive "car ride briefing" that a City Manager could read before an interview and sound knowledgeable. Briefs persist with creation date, are visible to all users, and have an Austin-specific strategic perspective.

## Scope

### In Scope
- New database schema for storing executive briefs (`executive_briefs` table) with public visibility
- Backend API endpoints for brief generation and retrieval (including gathering related cards, user notes, sources)
- Comprehensive AI prompt for Austin-focused executive briefs (800-1500 words)
- Frontend hook `useBriefGeneration` for triggering brief creation
- Updated Kanban column actions: "Generate Brief" as primary, "Export Brief" as secondary (only enabled when brief exists)
- Brief preview modal to view generated content before export
- Fix existing export bug (wrong card ID being passed)
- Toast notifications and loading states for brief generation
- Brief persistence with creation date attached to card (visible to all users)

### Out of Scope
- Brief versioning/history (v2 feature)
- Brief sharing/distribution system (v2 feature)
- Custom brief templates (v2 feature)
- Collaborative brief editing (v2 feature)
- Brief scheduling/automation (v2 feature)

## Prerequisites
- Understanding of existing `ResearchTask` async pattern
- OpenAI API access for brief generation
- Supabase migration access

## Parallel Execution Strategy

Work is divided into 3 parallel workstreams after database migration:

| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|---------------|
| Backend API | backend-engineer | `main.py` (new endpoints only), `brief_service.py` (new), `models/brief.py` (new) | Database migration must complete first |
| Frontend Hooks | fullstack-architect | `useBriefGeneration.ts` (new), `workstream-api.ts` (brief functions) | None |
| Frontend UI | forge-frontend-architect | `types.ts`, `CardActions.tsx`, `BriefPreviewModal.tsx` (new) | None |

### File Ownership Matrix

| File | Phase 1 Owner | Phase 2 Owner | Phase 3 Owner |
|------|---------------|---------------|---------------|
| `supabase/migrations/` | Central (sequential) | - | - |
| `backend/app/brief_service.py` | - | Backend API | - |
| `backend/app/models/brief.py` | - | Backend API | - |
| `backend/app/main.py` | - | Backend API (new endpoints) | - |
| `frontend/src/lib/workstream-api.ts` | - | Frontend Hooks | - |
| `frontend/src/components/kanban/actions/useBriefGeneration.ts` | - | Frontend Hooks | - |
| `frontend/src/components/kanban/types.ts` | - | - | Frontend UI |
| `frontend/src/components/kanban/CardActions.tsx` | - | - | Frontend UI |
| `frontend/src/components/kanban/BriefPreviewModal.tsx` | - | - | Frontend UI |
| `frontend/src/pages/WorkstreamKanban.tsx` | - | - | Integration (Central) |

## Implementation Phases

### Phase 1: Database Schema
**Objective**: Create database table for storing executive briefs

**Sequential Task** (must run first):
1. **Task 1.1**: Create Supabase migration for `executive_briefs` table

**New Files to Create**:
- `supabase/migrations/1766738000_executive_briefs.sql`
  ```sql
  CREATE TABLE executive_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workstream_card_id UUID NOT NULL REFERENCES workstream_cards(id) ON DELETE CASCADE,
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'completed', 'failed')),
    content JSONB, -- Structured brief content (sections as JSON)
    content_markdown TEXT, -- Full brief as markdown for display
    summary TEXT, -- Executive summary extracted for quick display
    generated_at TIMESTAMPTZ,
    generation_time_ms INTEGER,
    model_used TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workstream_card_id) -- One brief per workstream card
  );

  CREATE INDEX idx_executive_briefs_workstream_card ON executive_briefs(workstream_card_id);
  CREATE INDEX idx_executive_briefs_card ON executive_briefs(card_id);
  CREATE INDEX idx_executive_briefs_status ON executive_briefs(status);

  -- Trigger for updated_at
  CREATE TRIGGER trigger_executive_briefs_updated_at
    BEFORE UPDATE ON executive_briefs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

  -- RLS: Briefs are readable by all authenticated users
  ALTER TABLE executive_briefs ENABLE ROW LEVEL SECURITY;

  CREATE POLICY "Briefs are viewable by all authenticated users"
    ON executive_briefs FOR SELECT
    TO authenticated
    USING (true);

  CREATE POLICY "Users can create briefs for their workstream cards"
    ON executive_briefs FOR INSERT
    TO authenticated
    WITH CHECK (
      EXISTS (
        SELECT 1 FROM workstream_cards wc
        JOIN workstreams w ON wc.workstream_id = w.id
        WHERE wc.id = workstream_card_id AND w.user_id = auth.uid()
      )
    );

  CREATE POLICY "Users can update their own briefs"
    ON executive_briefs FOR UPDATE
    TO authenticated
    USING (created_by = auth.uid());
  ```

**Phase Verification**:
- [ ] Migration runs successfully
- [ ] Table and indexes created
- [ ] RLS policies applied

---

### Phase 2: Backend Implementation
**Objective**: Create brief generation service and API endpoints

**Parallel Tasks** (run simultaneously via Opus sub-agents):

1. **Task 2A: Brief Service** - Owns: `brief_service.py`, `models/brief.py`
   - Create `ExecutiveBriefService` class
   - Implement `generate_executive_brief()` method using adapted prompt
   - Implement `get_brief()` and `get_brief_status()` methods
   - Use existing `@with_retry` decorator pattern from `ai_service.py`

2. **Task 2B: API Endpoints** - Owns: `main.py` (new endpoints section only)
   - `POST /api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief` - Generate brief
   - `GET /api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief` - Get brief
   - `GET /api/v1/me/workstreams/{workstream_id}/cards/{card_id}/brief/status` - Poll status
   - Follow existing deep-dive endpoint pattern for auth, validation, async execution

3. **Task 2C: Fix Export Bug** - Owns: Fix in `CardActions.tsx` (small change)
   - Change `onExport(card.id, format)` to `onExport(card.card.id, format)`
   - This is a critical bug fix that should be done regardless

**New Files to Create**:
- `backend/app/brief_service.py` - Executive brief generation service
- `backend/app/models/brief.py` - Pydantic models for brief requests/responses

**Files to Modify**:
- `backend/app/main.py` - Add 3 new endpoints (lines ~3735-3900)

**AI Prompt for Executive Brief** (to be placed in `brief_service.py`):
```python
EXECUTIVE_BRIEF_PROMPT = """You are a strategic advisor preparing a comprehensive leadership briefing for City of Austin decision-makers.

Generate an executive brief on "{card_name}" that a City Manager could read on the car ride to an interview and sound knowledgeable about this topic. This brief should synthesize all available information into actionable intelligence with an Austin-specific perspective.

---

## CARD INFORMATION
Name: {card_name}
Summary: {summary}
Description: {description}
Pillar: {pillar}
Horizon: {horizon}
Stage: {stage}
Scores: Novelty={novelty}/100, Impact={impact}/100, Relevance={relevance}/100, Risk={risk}/100

## USER CONTEXT & NOTES
Workstream: {workstream_name}
Workstream Description: {workstream_description}
User Notes on Card: {user_notes}

## RELATED INTELLIGENCE
{related_cards_summary}

## SOURCE MATERIALS
{source_excerpts}

---

Create an executive brief with these sections:

## EXECUTIVE SUMMARY
(3-4 sentences capturing what this is, why it matters to Austin, and the key takeaway for leadership)

## VALUE PROPOSITION FOR AUSTIN
- What specific value does this offer the City of Austin?
- How does it align with Austin's strategic priorities?
- What problem does it solve or opportunity does it create?

## KEY TALKING POINTS
(5-7 bullet points a leader could use in conversation - clear, memorable, quotable)

## CURRENT LANDSCAPE
- Where is this in terms of maturity and adoption?
- Who are the key players and what are peer cities doing?
- What's the trajectory - accelerating, stable, or declining?

## AUSTIN-SPECIFIC CONSIDERATIONS
- How does this intersect with Austin's unique context (growth, tech hub, equity focus)?
- Which city departments or initiatives would this affect?
- What existing Austin programs or infrastructure does this relate to?

## STRATEGIC IMPLICATIONS
- What decisions or preparations should city leadership consider?
- What happens if Austin acts vs. waits?
- What's the cost of inaction?

## RISK FACTORS & CONCERNS
- What could go wrong or what challenges exist?
- What are the equity, privacy, or political considerations?
- What unknowns or uncertainties should leadership be aware of?

## RECOMMENDED ACTIONS
(3-5 numbered, specific, actionable recommendations prioritized by urgency)

## TIMELINE & URGENCY
- How urgent is this? What's the decision window?
- What signals should Austin watch for?

---

Guidelines:
- Write for a busy executive who needs to sound informed in 10 minutes
- Be SPECIFIC with examples, numbers, and city names where available
- Frame everything through Austin's lens and priorities
- Include concrete talking points that could be quoted
- Use plain language - no jargon or acronyms without explanation
- If information is limited, acknowledge gaps and focus on what IS known
- Total length: 800-1500 words depending on available information
"""
```

**Phase Verification**:
- [ ] Brief service generates content correctly
- [ ] Endpoints authenticate and authorize properly
- [ ] Async generation works with status polling
- [ ] Export bug is fixed

**Phase Review Gate**:
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 3: Frontend Implementation
**Objective**: Create UI for brief generation and preview

**Parallel Tasks** (run simultaneously via Opus sub-agents):

1. **Task 3A: Brief Generation Hook** - Owns: `useBriefGeneration.ts`, `workstream-api.ts`
   - Create `useBriefGeneration` hook following `useQuickUpdate` pattern
   - Add API functions: `generateBrief()`, `getBrief()`, `getBriefStatus()`
   - Implement polling for generation status
   - Handle loading, success, error states

2. **Task 3B: Kanban Types & Actions** - Owns: `types.ts`, `CardActions.tsx`
   - Add `generateBrief` to `ActionHandler` type
   - Update "Brief" column definition:
     - Primary action: "Generate Brief" (handler: `generateBrief`)
     - Secondary action: "Export Brief PDF" (handler: `exportPdf`, disabled if no brief)
     - Secondary action: "Export Brief PPTX" (handler: `exportPptx`, disabled if no brief)
   - Add `handleGenerateBrief` callback to CardActions
   - Add `onGenerateBrief` to `CardActionCallbacks` interface

3. **Task 3C: Brief Preview Modal** - Owns: `BriefPreviewModal.tsx` (new)
   - Modal to display generated brief content
   - Render markdown sections with proper formatting
   - Export buttons (PDF, PPTX) at bottom of modal
   - Loading state while brief generates
   - Error state if generation fails

**New Files to Create**:
- `frontend/src/components/kanban/actions/useBriefGeneration.ts`
- `frontend/src/components/kanban/BriefPreviewModal.tsx`

**Files to Modify**:
- `frontend/src/lib/workstream-api.ts` - Add brief API functions
- `frontend/src/components/kanban/types.ts` - Add `generateBrief` handler, update column def
- `frontend/src/components/kanban/CardActions.tsx` - Add generate brief handler
- `frontend/src/components/kanban/index.ts` - Export new components

**Phase Verification**:
- [ ] Brief generation hook triggers API correctly
- [ ] Loading states display during generation
- [ ] Brief preview modal renders content properly
- [ ] Export buttons work from preview modal

**Phase Review Gate**:
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 4: Integration & Polish
**Objective**: Wire everything together in WorkstreamKanban page

**Sequential Task** (depends on Phase 2 and 3):

1. **Task 4.1: WorkstreamKanban Integration** - Owner: Central
   - Initialize `useBriefGeneration` hook with toast callbacks
   - Add `handleGenerateBrief` function
   - Pass to `cardActions` object for KanbanBoard
   - Add brief preview modal state and rendering
   - Track which cards have briefs (for conditional export enable)

**Files to Modify**:
- `frontend/src/pages/WorkstreamKanban.tsx` - Full integration

**Phase Verification**:
- [ ] End-to-end flow works: Generate Brief → View Preview → Export
- [ ] Toast notifications appear for all states
- [ ] Cards without briefs show "Generate Brief" as primary
- [ ] Cards with briefs show "View/Export Brief" options

**Phase Review Gate**:
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

## Final Deliverable Review

**MANDATORY**: After all phases complete, run both review agents on the ENTIRE deliverable:
1. `final-review-completeness` - Full codebase scan for incomplete items
2. `principal-code-reviewer` - Comprehensive quality assessment

## Testing Strategy

### Backend Tests
- Unit test `ExecutiveBriefService.generate_executive_brief()`
- Integration test for brief endpoints (auth, validation, async flow)
- Test brief retrieval and status polling
- Add to `backend/tests/test_brief_service.py` (new file)

### Frontend Tests
- Unit test `useBriefGeneration` hook with vitest
- Component test `BriefPreviewModal` rendering
- Add to `frontend/src/components/kanban/actions/__tests__/useBriefGeneration.test.ts`

### Manual Testing Steps
1. Navigate to workstream Kanban board
2. Move a card to "Brief" column
3. Click "Generate Brief" action
4. Verify loading toast appears
5. Wait for generation (poll status)
6. Verify success toast and brief preview opens
7. Review brief content sections
8. Click "Export PDF" - verify download
9. Click "Export PPTX" - verify download
10. Close modal, verify can re-open brief

## Rollback Plan

1. **Database**: Run down migration to drop `executive_briefs` table
2. **Backend**: Revert to previous commit (new files can be deleted)
3. **Frontend**: Revert types.ts column definition to use `exportPdf` as primary action
4. **Quick fix**: If brief generation fails but export works, disable generate brief action

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenAI API latency causes timeout | Med | Med | Use async task pattern with status polling; show "generating" state |
| Brief content too long/short | Low | Low | Enforce token limits in prompt; validate output length |
| File conflict between agents | Med | High | Clear file ownership matrix above |
| Export still broken after fix | Low | Med | Test export fix independently before full integration |
| Brief generation costs too high | Low | Med | Use GPT-4o-mini for cost efficiency; track token usage |

## Open Questions - RESOLVED

1. **Brief Expiration**: ~~Should briefs expire and require regeneration after card data changes?~~
   - **RESOLVED**: Briefs persist with creation date attached. No expiration in v1.

2. **Multiple Briefs**: ~~Can a card in multiple workstreams have different briefs?~~
   - **RESOLVED**: Yes, briefs are tied to `workstream_card_id` - same card can have different briefs in different workstreams.

3. **Brief Visibility**: ~~Who can see briefs?~~
   - **RESOLVED**: All authenticated users can view briefs (they are shareable assets).

4. **Brief Content**: ~~Should briefs be concise or comprehensive?~~
   - **RESOLVED**: Comprehensive (800-1500 words). Include user notes, related cards, and source materials. Austin-specific perspective with key talking points for leadership.

---
**STATUS: APPROVED - EXECUTING BUILD**
