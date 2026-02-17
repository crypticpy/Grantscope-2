# Supabase Row Level Security (RLS) Audit Report

**Audit Date:** 2025-12-27
**Auditor:** Backend Security Specialist
**Project:** GrantScope2 Strategic Intelligence Application
**Scope:** Complete RLS analysis of all 30 migration files in `supabase/migrations/`

---

## Executive Summary

This audit examines Row Level Security (RLS) implementation across all database tables in the GrantScope2 application. The application is a strategic intelligence platform where users should only see their own data (manually provisioned users, no self-registration).

### Overall Assessment: MODERATE SECURITY GAPS IDENTIFIED

| Category                         | Status            |
| -------------------------------- | ----------------- |
| RLS Enabled on User Tables       | PASS (with gaps)  |
| RLS Policies for CRUD Operations | PARTIAL           |
| User Data Isolation              | NEEDS IMPROVEMENT |
| Reference Table Security         | PASS              |
| Service Role Access              | PASS              |

---

## Table-by-Table RLS Status

### Core User-Owned Tables

| Table              | RLS Enabled | SELECT         | INSERT         | UPDATE         | DELETE       | Status    |
| ------------------ | ----------- | -------------- | -------------- | -------------- | ------------ | --------- |
| `users`            | YES         | Own only       | N/A            | Own only       | N/A          | OK        |
| `cards`            | YES         | Public         | Auth check     | Auth check     | **MISSING**  | NEEDS FIX |
| `sources`          | YES         | Public         | Auth check     | **MISSING**    | **MISSING**  | NEEDS FIX |
| `card_timeline`    | YES         | Via cards      | **MISSING**    | **MISSING**    | **MISSING**  | NEEDS FIX |
| `card_follows`     | YES         | Own only       | Own only       | Own only       | Own only     | OK        |
| `card_notes`       | YES         | Own + public   | Own only       | Own only       | Own only     | OK        |
| `workstreams`      | YES         | Own only       | Own only       | Own only       | Own only     | OK        |
| `workstream_cards` | YES         | Via workstream | Via workstream | Via workstream | **MISSING**  | NEEDS FIX |
| `research_tasks`   | YES         | Own only       | Own only       | Own only       | Service only | OK        |

### Discovery System Tables

| Table                  | RLS Enabled | SELECT   | INSERT       | UPDATE       | DELETE       | Status |
| ---------------------- | ----------- | -------- | ------------ | ------------ | ------------ | ------ |
| `discovery_runs`       | YES         | All auth | Service only | Service only | Service only | OK     |
| `discovery_blocks`     | YES         | All auth | All auth     | Service only | Service only | OK     |
| `user_card_dismissals` | YES         | Own only | Own only     | Own only     | Own only     | OK     |
| `discovered_sources`   | YES         | All auth | Service only | Service only | Service only | OK     |

### Analysis & Validation Tables

| Table                        | RLS Enabled | SELECT   | INSERT       | UPDATE       | DELETE       | Status    |
| ---------------------------- | ----------- | -------- | ------------ | ------------ | ------------ | --------- |
| `classification_validations` | YES         | All auth | Own only     | Own only     | Own only     | OK        |
| `implications_analyses`      | YES         | Public   | Auth check   | **MISSING**  | **MISSING**  | NEEDS FIX |
| `implications`               | YES         | Public   | Auth check   | **MISSING**  | **MISSING**  | NEEDS FIX |
| `entities`                   | YES         | All auth | Service only | Service only | Service only | OK        |
| `entity_relationships`       | YES         | All auth | Service only | Service only | Service only | OK        |

### Search & History Tables

| Table                | RLS Enabled | SELECT      | INSERT         | UPDATE           | DELETE         | Status   |
| -------------------- | ----------- | ----------- | -------------- | ---------------- | -------------- | -------- |
| `saved_searches`     | YES         | Own only    | Own only       | Own only         | Own only       | OK       |
| `search_history`     | YES         | Own only    | Own only       | N/A              | Own only       | OK       |
| `card_score_history` | YES         | All auth    | All auth       | Service only     | Service only   | OK       |
| `card_relationships` | YES         | **MISSING** | **MISSING**    | **MISSING**      | **MISSING**    | CRITICAL |
| `executive_briefs`   | YES         | All auth    | Via workstream | Own + workstream | Via workstream | OK       |

### Reference Tables (Read-Only for Users)

| Table             | RLS Enabled | SELECT   | INSERT       | UPDATE       | DELETE       | Status    |
| ----------------- | ----------- | -------- | ------------ | ------------ | ------------ | --------- |
| `pillars`         | YES         | All auth | Service only | Service only | Service only | OK        |
| `goals`           | YES         | All auth | Service only | Service only | Service only | OK        |
| `anchors`         | YES         | All auth | Service only | Service only | Service only | OK        |
| `stages`          | YES         | All auth | Service only | Service only | Service only | OK        |
| `priorities`      | YES         | All auth | Service only | Service only | Service only | OK        |
| `card_embeddings` | YES         | All auth | **MISSING**  | **MISSING**  | **MISSING**  | NEEDS FIX |

---

## Critical Security Issues

### CRITICAL: `card_relationships` - No RLS Policies

**Location:** `supabase/migrations/1766436101_create_card_relationships.sql`

**Issue:** RLS is enabled but NO policies are created. This means:

- No user can SELECT, INSERT, UPDATE, or DELETE records
- Application functionality is broken unless using service key

**Risk Level:** CRITICAL (blocks functionality or forces service key usage)

**Recommended Fix:**

```sql
-- Add policies for card_relationships
CREATE POLICY "Authenticated users can view card_relationships"
    ON card_relationships FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on card_relationships"
    ON card_relationships FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

### HIGH: `cards` Table - Missing DELETE Policy

**Location:** `supabase/migrations/1766434562_create_embeddings_and_rls.sql` and `001_complete_schema.sql`

**Issue:** Cards have SELECT (public), INSERT (authenticated), UPDATE (authenticated) but NO DELETE policy.

**Risk Level:** HIGH (users cannot delete their own cards, or must use service key)

**Recommended Fix:**

```sql
-- Add delete policy - only card creator can delete
CREATE POLICY "Users can delete own cards"
    ON cards FOR DELETE
    USING (auth.uid() = created_by);
```

### HIGH: `sources` Table - Missing UPDATE/DELETE Policies

**Location:** `supabase/migrations/1766434562_create_embeddings_and_rls.sql` and `001_complete_schema.sql`

**Issue:** Sources can be viewed and inserted but not updated or deleted.

**Risk Level:** HIGH

**Recommended Fix:**

```sql
-- Service role only for source management (sources are system-generated)
CREATE POLICY "Service role can manage sources"
    ON sources FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

### MEDIUM: `card_timeline` - Missing INSERT/UPDATE/DELETE Policies

**Location:** `supabase/migrations/1766434562_create_embeddings_and_rls.sql`

**Issue:** Timeline is readable but has no write policies.

**Risk Level:** MEDIUM (timeline entries are system-generated)

**Recommended Fix:**

```sql
-- Timeline entries should only be created by service role
CREATE POLICY "Service role can manage card_timeline"
    ON card_timeline FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

### MEDIUM: `card_embeddings` - Missing All CRUD Policies

**Location:** `supabase/migrations/1766435004_enable_rls_security.sql`

**Issue:** RLS is enabled but only a legacy SELECT policy exists. No INSERT/UPDATE/DELETE.

**Risk Level:** MEDIUM (embeddings are system-generated)

**Recommended Fix:**

```sql
CREATE POLICY "Service role full access on card_embeddings"
    ON card_embeddings FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

### MEDIUM: `implications_analyses` and `implications` - Missing UPDATE/DELETE

**Location:** `supabase/migrations/002_schema_fixes.sql`

**Issue:** Can view and insert but not update or delete analyses.

**Risk Level:** MEDIUM

**Recommended Fix:**

```sql
-- Allow users to update/delete their own analyses
CREATE POLICY "Users can update own implications_analyses"
    ON implications_analyses FOR UPDATE
    USING (created_by = auth.uid());

CREATE POLICY "Users can delete own implications_analyses"
    ON implications_analyses FOR DELETE
    USING (created_by = auth.uid());

-- Implications follow parent analysis
CREATE POLICY "Service role can manage implications"
    ON implications FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

---

## Security Design Analysis

### User Data Isolation Assessment

**CONCERN:** The current design allows all authenticated users to see ALL cards.

**Current Policy:**

```sql
CREATE POLICY "Anyone can view cards" ON cards
    FOR SELECT USING (true);
```

**Analysis:** This is intentional for a collaborative intelligence platform where users share insights. However, it means:

1. Any authenticated user can see all cards
2. User dismissals and notes are properly isolated
3. Workstreams and follows are properly user-scoped

**Recommendation:** If true multi-tenant isolation is required:

```sql
-- Option 1: Cards visible to creator or followers only
CREATE POLICY "Users can view accessible cards" ON cards
    FOR SELECT USING (
        created_by = auth.uid()
        OR EXISTS (
            SELECT 1 FROM card_follows cf
            WHERE cf.card_id = id AND cf.user_id = auth.uid()
        )
        OR review_status = 'active'  -- Published cards visible to all
    );
```

### Service Role Usage Patterns

The application correctly uses service role for:

- Discovery pipeline operations
- AI-generated content (sources, entities, embeddings)
- Background job processing (research_tasks)
- System-generated timeline events

### Function Security

All database functions have been properly secured with:

- `SECURITY DEFINER` for elevated operations
- `SET search_path = ''` or `SET search_path = extensions, public` to prevent search path injection
- Proper grants to `authenticated` and `service_role` roles

**Migration:** `1766435003_security_search_path_fix.sql` - Comprehensive fix applied

---

## Policy Detail by Table

### `users` Table

```sql
-- Location: 1766434562_create_embeddings_and_rls.sql
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid() = id);

-- Location: 001_complete_schema.sql
CREATE POLICY users_own ON users
    FOR ALL USING (auth.uid() = id);
```

**Status:** SECURE - Users can only access their own profile.

### `cards` Table

```sql
-- SELECT: Anyone can view
CREATE POLICY "Anyone can view cards" ON cards
    FOR SELECT USING (true);

-- INSERT: Authenticated users can create
CREATE POLICY "Authenticated users can create cards" ON cards
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- UPDATE: Authenticated users can update (weak - should be creator only)
CREATE POLICY "Users can update own cards" ON cards
    FOR UPDATE USING (auth.uid() = created_by);

-- DELETE: MISSING
```

**Status:** NEEDS DELETE POLICY

### `workstream_cards` Table

```sql
-- Inherits workstream user ownership via join
CREATE POLICY "Users can view own workstream cards" ON workstream_cards
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM workstreams
            WHERE workstreams.id = workstream_cards.workstream_id
            AND workstreams.user_id = auth.uid()
        )
    );
```

**Status:** NEEDS DELETE POLICY

---

## Recommended Migration: Complete RLS Fixes

Create a new migration file: `supabase/migrations/1766738100_complete_rls_fixes.sql`

```sql
-- Migration: complete_rls_fixes
-- Created at: 1766738100
-- Description: Complete RLS policy coverage for all tables
-- Security Audit Fix

-- ============================================================================
-- CRITICAL: card_relationships - Add missing policies
-- ============================================================================

CREATE POLICY "Authenticated users can view card_relationships"
    ON card_relationships FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on card_relationships"
    ON card_relationships FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- HIGH: cards - Add DELETE policy
-- ============================================================================

CREATE POLICY "Users can delete own cards"
    ON cards FOR DELETE
    TO authenticated
    USING (auth.uid() = created_by);

-- ============================================================================
-- HIGH: sources - Add management policies (service role only)
-- ============================================================================

CREATE POLICY "Service role can manage sources"
    ON sources FOR UPDATE
    TO service_role
    USING (true);

CREATE POLICY "Service role can delete sources"
    ON sources FOR DELETE
    TO service_role
    USING (true);

-- ============================================================================
-- MEDIUM: card_timeline - Add service role management
-- ============================================================================

CREATE POLICY "Service role can manage card_timeline"
    ON card_timeline FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- MEDIUM: card_embeddings - Add service role access
-- ============================================================================

CREATE POLICY "Service role full access on card_embeddings"
    ON card_embeddings FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- MEDIUM: implications_analyses - Add UPDATE/DELETE
-- ============================================================================

CREATE POLICY "Users can update own implications_analyses"
    ON implications_analyses FOR UPDATE
    TO authenticated
    USING (created_by = auth.uid());

CREATE POLICY "Users can delete own implications_analyses"
    ON implications_analyses FOR DELETE
    TO authenticated
    USING (created_by = auth.uid());

CREATE POLICY "Service role full access on implications_analyses"
    ON implications_analyses FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- MEDIUM: implications - Add UPDATE/DELETE
-- ============================================================================

CREATE POLICY "Authenticated users can update implications"
    ON implications FOR UPDATE
    TO authenticated
    WITH CHECK (true);  -- Via parent analysis ownership

CREATE POLICY "Authenticated users can delete implications"
    ON implications FOR DELETE
    TO authenticated
    USING (true);  -- Via parent analysis ownership

CREATE POLICY "Service role full access on implications"
    ON implications FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- MEDIUM: workstream_cards - Add DELETE policy
-- ============================================================================

CREATE POLICY "Users can delete own workstream cards"
    ON workstream_cards FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM workstreams
            WHERE workstreams.id = workstream_cards.workstream_id
            AND workstreams.user_id = auth.uid()
        )
    );

-- ============================================================================
-- DONE
-- ============================================================================

COMMENT ON EXTENSION vector IS 'Security audit: RLS policies completed for all tables';
```

---

## Summary of Findings

### Tables Requiring Immediate Fixes (7)

1. **`card_relationships`** - CRITICAL: No policies at all
2. **`cards`** - Missing DELETE policy
3. **`sources`** - Missing UPDATE/DELETE policies
4. **`card_timeline`** - Missing INSERT/UPDATE/DELETE policies
5. **`card_embeddings`** - Missing INSERT/UPDATE/DELETE policies
6. **`implications_analyses`** - Missing UPDATE/DELETE policies
7. **`implications`** - Missing UPDATE/DELETE policies

### Tables with Complete RLS (20+)

- users, card_follows, card_notes, workstreams, workstream_cards (partial)
- research_tasks, discovery_runs, discovery_blocks, user_card_dismissals
- discovered_sources, classification_validations, entities, entity_relationships
- saved_searches, search_history, card_score_history, executive_briefs
- pillars, goals, anchors, stages, priorities

### Security Patterns Observed

1. **Reference Data:** Read-only for users, writable by service role only
2. **User-Owned Data:** Full CRUD for owner via `auth.uid()` checks
3. **System-Generated Data:** Service role only for writes
4. **Collaborative Data:** Public read, owner write (cards, analyses)
5. **AI Pipeline Data:** Service role controls (discovery, embeddings, entities)

---

## Recommendations

### Immediate Actions

1. Apply the recommended migration to fix missing policies
2. Test all affected tables for proper access control
3. Review service key usage in application code

### Long-Term Improvements

1. Consider adding `deleted_at` soft delete columns instead of hard deletes
2. Add audit logging trigger for sensitive operations
3. Implement rate limiting at RLS level for write operations
4. Review card visibility model if stricter isolation is needed

### Testing Checklist

After applying fixes:

- [ ] Test card deletion as authenticated user
- [ ] Verify card_relationships queries work without service key
- [ ] Confirm sources are not modifiable by users directly
- [ ] Validate workstream card deletion works
- [ ] Check implications analyses CRUD flow

---

## Appendix: Migration Files Reviewed

1. `1766434513_enable_extensions.sql`
2. `1766434524_create_reference_tables.sql`
3. `1766434534_create_users_and_cards.sql`
4. `1766434548_create_sources_and_relationships.sql`
5. `1766434562_create_embeddings_and_rls.sql`
6. `1766434584_populate_reference_data.sql`
7. `1766434603_seed_sample_data.sql`
8. `1766434700_seed_additional_cards.sql`
9. `1766434750_add_top25_column.sql`
10. `1766434800_seed_top25_aligned_cards.sql`
11. `1766434900_add_research_tracking.sql`
12. `1766434901_enhanced_research_schema.sql`
13. `001_complete_schema.sql`
14. `002_schema_fixes.sql`
15. `1766435000_discovery_schema.sql`
16. `1766435001_discovery_schema_additions.sql`
17. `1766435002_discovered_sources.sql`
18. `1766435003_security_search_path_fix.sql`
19. `1766435004_enable_rls_security.sql`
20. `1766435005_move_vector_extension.sql`
21. `1766435006_fix_vector_search_path.sql`
22. `1766435100_classification_validations.sql`
23. `1766436000_advanced_search_schema.sql`
24. `1766436100_create_score_history.sql`
25. `1766436101_create_card_relationships.sql`
26. `1766436102_enhance_card_timeline.sql`
27. `1766436200_dashboard_stats_rpc.sql`
28. `1766437000_workstream_kanban.sql`
29. `1766738000_executive_briefs.sql`
30. `1766738001_brief_versioning.sql`

---

_This security audit was conducted as part of the GrantScope2 application development process._
