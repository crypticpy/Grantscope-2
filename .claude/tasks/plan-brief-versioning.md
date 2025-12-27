# Implementation Plan: Brief Versioning System

Created: 2025-12-26
Status: PENDING APPROVAL

## Summary

Add version tracking to executive briefs, allowing multiple brief versions per card. Users can view version history, regenerate briefs with latest research/sources, and see what's new since the last brief. Each new brief incorporates sources discovered since the previous version.

## Scope

### In Scope
- Database schema: Add `version` column, modify unique constraint
- Backend: Version tracking, list versions endpoint, filter sources by timestamp
- Frontend: Version history UI, regenerate button, "new sources" indicator
- New sources since last brief: Highlight sources discovered after previous brief

### Out of Scope
- Version diffing/comparison view (future feature)
- Rollback to previous version (future feature)
- Version annotations/comments (future feature)

## Prerequisites
- Executive briefs system working (current implementation)
- Database migration applied for executive_briefs table

## Parallel Execution Strategy

Work is divided into 3 independent workstreams that can execute simultaneously, followed by integration.

### Workstream Analysis
| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|---------------|
| Database | backend-engineer | Migration SQL | None |
| Backend | backend-engineer | brief_service.py, main.py, models/brief.py | Migration must run first |
| Frontend | forge-frontend-architect | workstream-api.ts, BriefPreviewModal.tsx, useBriefGeneration.ts | Backend API ready |

### File Ownership Matrix
| File | Phase 1 Owner | Phase 2 Owner |
|------|---------------|---------------|
| `supabase/migrations/1766738001_brief_versioning.sql` | Database Agent | - |
| `backend/app/brief_service.py` | - | Backend Agent |
| `backend/app/main.py` | - | Backend Agent |
| `backend/app/models/brief.py` | - | Backend Agent |
| `frontend/.../lib/workstream-api.ts` | - | Frontend Agent |
| `frontend/.../components/kanban/BriefPreviewModal.tsx` | - | Frontend Agent |
| `frontend/.../components/kanban/actions/useBriefGeneration.ts` | - | Frontend Agent |

## Implementation Phases

### Phase 1: Database Schema Update
**Objective**: Add versioning support to executive_briefs table

**Tasks** (sequential - migration must be applied):
1. **Task 1A**: Create migration to add version column and modify constraints

**New Files to Create**:
- `supabase/migrations/1766738001_brief_versioning.sql`
  - Add `version INTEGER NOT NULL DEFAULT 1` column
  - Add `sources_since_previous JSONB` column (stores new source count/IDs)
  - Drop `UNIQUE(workstream_card_id)` constraint
  - Add `UNIQUE(workstream_card_id, version)` constraint
  - Add index on `(workstream_card_id, version DESC)` for efficient latest lookup
  - Update existing rows to have version = 1

**Phase Verification**:
- [ ] Migration runs without errors
- [ ] Existing briefs have version = 1
- [ ] New constraint allows multiple versions per workstream_card

---

### Phase 2: Backend Updates
**Objective**: Implement versioning logic and new endpoints

**Parallel Tasks** (run simultaneously):
1. **Task 2A**: Update models/brief.py - Owns: models/brief.py
2. **Task 2B**: Update brief_service.py - Owns: brief_service.py
3. **Task 2C**: Update main.py endpoints - Owns: main.py (brief endpoints only)

**Files to Modify**:

**`backend/app/models/brief.py`** - Task 2A:
- Add `version: int` field to `ExecutiveBriefResponse`
- Add `sources_since_previous: Optional[int]` field
- Add `BriefVersionListItem` model for version history
- Add `BriefVersionsResponse` model (list of versions)

**`backend/app/brief_service.py`** - Task 2B:
- Modify `create_brief_record()`:
  - Query max version for workstream_card_id
  - Set new version = max + 1 (or 1 if first)
- Add `get_brief_versions(workstream_card_id)` method:
  - Returns all versions ordered by version DESC
- Modify `_gather_source_materials()`:
  - Accept optional `since_timestamp` parameter
  - When regenerating, filter to sources created after previous brief's `generated_at`
  - Count and store "new sources" metadata
- Modify `get_brief_by_workstream_card()`:
  - Return only the latest version (highest version number)

**`backend/app/main.py`** - Task 2C:
- Modify POST `/brief` endpoint:
  - Always create new version (don't check for existing completed)
  - Pass previous brief's `generated_at` to filter new sources
- Add GET `/brief/versions` endpoint:
  - Returns list of all versions with metadata
  - Response: `BriefVersionsResponse`
- Modify GET `/brief` endpoint:
  - Add optional `?version=N` query param
  - Default to latest version

**Phase Verification**:
- [ ] POST /brief creates version 2 when version 1 exists
- [ ] GET /brief/versions returns all versions
- [ ] GET /brief returns latest version by default
- [ ] GET /brief?version=1 returns specific version
- [ ] New brief captures sources since previous brief's generated_at

**Phase Review Gate**:
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

### Phase 3: Frontend Updates
**Objective**: Add version history UI and regenerate functionality

**Parallel Tasks** (run simultaneously):
1. **Task 3A**: Update workstream-api.ts - Owns: workstream-api.ts
2. **Task 3B**: Update BriefPreviewModal.tsx - Owns: BriefPreviewModal.tsx
3. **Task 3C**: Update useBriefGeneration.ts - Owns: useBriefGeneration.ts

**Files to Modify**:

**`frontend/.../lib/workstream-api.ts`** - Task 3A:
- Add `version: number` to `ExecutiveBrief` interface
- Add `sources_since_previous?: number` field
- Add `BriefVersionListItem` interface
- Add `getBriefVersions(token, workstreamId, cardId)` function
- Update `getBrief()` to support optional version param

**`frontend/.../components/kanban/BriefPreviewModal.tsx`** - Task 3B:
- Add version history panel (collapsible, below main content)
- Display current version number in header (e.g., "v2")
- Add "Regenerate Brief" button (generates new version)
- Show "X new sources since last brief" indicator
- Version history: list all versions with date, click to view
- Follow ResearchHistoryPanel pattern for version list UI

**`frontend/.../components/kanban/actions/useBriefGeneration.ts`** - Task 3C:
- Track brief versions per card
- Add `regenerateBrief()` method (creates new version)
- Add `getCardBriefVersions()` method
- Update state to handle version selection

**Phase Verification**:
- [ ] "Regenerate Brief" button visible for completed briefs
- [ ] Version history shows all versions
- [ ] Clicking version loads that version's content
- [ ] New sources count displayed when regenerating
- [ ] Current version number displayed (v1, v2, etc.)

**Phase Review Gate**:
- [ ] Run `final-review-completeness` agent
- [ ] Run `principal-code-reviewer` agent
- [ ] Address all critical/high issues before proceeding

---

## Final Deliverable Review

**MANDATORY**: After all phases complete, run both review agents:
1. `final-review-completeness` - Full codebase scan for incomplete items
2. `principal-code-reviewer` - Comprehensive quality assessment

## Testing Strategy

**Manual Testing**:
1. Generate first brief for a card → version 1 created
2. Add new sources to the card (via research update)
3. Click "Regenerate Brief" → version 2 created
4. Verify version 2 mentions new sources in content
5. View version history → both versions listed
6. Click version 1 → loads version 1 content
7. Verify latest version shown by default

**Integration Testing**:
- API endpoints return correct version data
- Frontend correctly parses version responses
- Polling works for new version generation

## Rollback Plan

1. If migration fails: Run rollback SQL to restore UNIQUE constraint
2. If backend breaks: Revert brief_service.py and main.py changes
3. If frontend breaks: Revert modal and hook changes
4. Full rollback: Drop `version` column, restore unique constraint

**Rollback SQL**:
```sql
-- Restore original constraint
ALTER TABLE executive_briefs DROP CONSTRAINT IF EXISTS executive_briefs_workstream_card_version_key;
ALTER TABLE executive_briefs ADD CONSTRAINT executive_briefs_workstream_card_id_key UNIQUE (workstream_card_id);
-- Keep only latest version per card
DELETE FROM executive_briefs a USING executive_briefs b
WHERE a.workstream_card_id = b.workstream_card_id AND a.version < b.version;
-- Drop version column
ALTER TABLE executive_briefs DROP COLUMN IF EXISTS version;
ALTER TABLE executive_briefs DROP COLUMN IF EXISTS sources_since_previous;
```

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration breaks existing briefs | Low | High | Rollback SQL ready, test on staging first |
| Version query performance | Low | Medium | Index on (workstream_card_id, version DESC) |
| Frontend state complexity | Medium | Medium | Keep version state simple, fetch on demand |
| File conflict between agents | Medium | High | Clear file ownership matrix above |

## Open Questions

None - requirements are clear. Proceeding with implementation.

---
**USER: Please review this plan. Edit any section directly, then confirm to proceed.**
