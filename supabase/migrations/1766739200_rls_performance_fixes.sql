-- ==========================================================================
-- RLS Performance Fixes
--
-- Addresses two categories of Supabase database linter warnings:
--
-- 1. auth_rls_initplan (28 policies) — Wrap auth.uid() / auth.role() in
--    (select ...) so the value is computed once per query instead of
--    re-evaluated for every row.
--
-- 2. multiple_permissive_policies (4 tables) — Eliminate overlapping
--    permissive policies for the same role + action by either:
--    a) Dropping the redundant narrower policy when a FOR ALL exists, or
--    b) Splitting a FOR ALL into per-operation policies to avoid overlap.
--
-- Strategy per table:
--   card_follows      — drop redundant FOR SELECT (FOR ALL covers it)
--   card_notes        — split FOR ALL into INSERT/UPDATE/DELETE (keep FOR SELECT with broader condition)
--   workstream_cards  — drop redundant FOR SELECT (FOR ALL covers it)
--   workstream_scans  — drop FOR ALL service_role policy (service_role bypasses RLS anyway)
-- ==========================================================================

BEGIN;

-- =========================================================================
-- CARD_FOLLOWS — fix initplan + eliminate duplicate SELECT
-- =========================================================================
-- "Users can manage own follows" (FOR ALL) already covers SELECT.
-- Drop the redundant FOR SELECT policy, recreate FOR ALL with initplan fix.

DROP POLICY IF EXISTS "Users can view own follows" ON public.card_follows;
DROP POLICY IF EXISTS "Users can manage own follows" ON public.card_follows;

CREATE POLICY "Users can manage own follows" ON public.card_follows
    FOR ALL
    TO authenticated
    USING ((select auth.uid()) = user_id)
    WITH CHECK ((select auth.uid()) = user_id);


-- =========================================================================
-- CARD_NOTES — fix initplan + eliminate duplicate SELECT
-- =========================================================================
-- "Users can view notes" (FOR SELECT) has a broader condition (includes
-- non-private notes). "Users can manage own notes" (FOR ALL) overlaps on
-- SELECT. Split FOR ALL into per-operation policies.

DROP POLICY IF EXISTS "Users can view notes" ON public.card_notes;
DROP POLICY IF EXISTS "Users can manage own notes" ON public.card_notes;

CREATE POLICY "Users can view notes" ON public.card_notes
    FOR SELECT
    TO authenticated
    USING (
        (select auth.uid()) = user_id
        OR is_private = false
    );

CREATE POLICY "Users can insert own notes" ON public.card_notes
    FOR INSERT
    TO authenticated
    WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "Users can update own notes" ON public.card_notes
    FOR UPDATE
    TO authenticated
    USING ((select auth.uid()) = user_id);

CREATE POLICY "Users can delete own notes" ON public.card_notes
    FOR DELETE
    TO authenticated
    USING ((select auth.uid()) = user_id);


-- =========================================================================
-- WORKSTREAM_CARDS — fix initplan + eliminate duplicate SELECT
-- =========================================================================
-- "Users can manage own workstream cards" (FOR ALL) already covers SELECT.
-- Drop the redundant FOR SELECT policy, recreate FOR ALL with initplan fix.

DROP POLICY IF EXISTS "Users can view own workstream cards" ON public.workstream_cards;
DROP POLICY IF EXISTS "Users can manage own workstream cards" ON public.workstream_cards;

CREATE POLICY "Users can manage own workstream cards" ON public.workstream_cards
    FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.workstreams
            WHERE workstreams.id = workstream_cards.workstream_id
            AND workstreams.user_id = (select auth.uid())
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.workstreams
            WHERE workstreams.id = workstream_cards.workstream_id
            AND workstreams.user_id = (select auth.uid())
        )
    );


-- =========================================================================
-- WORKSTREAM_SCANS — fix initplan + eliminate duplicate SELECT/INSERT
-- =========================================================================
-- The service_role bypasses RLS (BYPASSRLS privilege), so the explicit
-- "Service role full access" FOR ALL policy is unnecessary and causes
-- overlap with user SELECT/INSERT policies. Drop it and fix user policies.

DROP POLICY IF EXISTS "Service role full access to workstream_scans" ON public.workstream_scans;
DROP POLICY IF EXISTS "Users can view own workstream scans" ON public.workstream_scans;
DROP POLICY IF EXISTS "Users can create scans for own workstreams" ON public.workstream_scans;

CREATE POLICY "Users can view own workstream scans" ON public.workstream_scans
    FOR SELECT
    TO authenticated
    USING (
        user_id = (select auth.uid())
        OR workstream_id IN (
            SELECT id FROM public.workstreams WHERE user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can create scans for own workstreams" ON public.workstream_scans
    FOR INSERT
    TO authenticated
    WITH CHECK (
        user_id = (select auth.uid())
        AND workstream_id IN (
            SELECT id FROM public.workstreams WHERE user_id = (select auth.uid())
        )
    );


-- =========================================================================
-- USERS — fix initplan
-- =========================================================================

DROP POLICY IF EXISTS "Users can view own profile" ON public.users;
DROP POLICY IF EXISTS "Users can update own profile" ON public.users;

CREATE POLICY "Users can view own profile" ON public.users
    FOR SELECT
    TO authenticated
    USING ((select auth.uid()) = id);

CREATE POLICY "Users can update own profile" ON public.users
    FOR UPDATE
    TO authenticated
    USING ((select auth.uid()) = id);


-- =========================================================================
-- CARDS — fix initplan
-- =========================================================================

DROP POLICY IF EXISTS "Authenticated users can create cards" ON public.cards;
DROP POLICY IF EXISTS "Users can update own cards" ON public.cards;

CREATE POLICY "Authenticated users can create cards" ON public.cards
    FOR INSERT
    TO authenticated
    WITH CHECK ((select auth.role()) = 'authenticated');

CREATE POLICY "Users can update own cards" ON public.cards
    FOR UPDATE
    TO authenticated
    USING ((select auth.uid()) = created_by);


-- =========================================================================
-- CARD_EMBEDDINGS — fix initplan
-- =========================================================================

DROP POLICY IF EXISTS "Users can view embeddings" ON public.card_embeddings;

CREATE POLICY "Users can view embeddings" ON public.card_embeddings
    FOR SELECT
    TO authenticated
    USING ((select auth.role()) = 'authenticated');


-- =========================================================================
-- RESEARCH_TASKS — fix initplan
-- =========================================================================

DROP POLICY IF EXISTS research_tasks_own ON public.research_tasks;

CREATE POLICY research_tasks_own ON public.research_tasks
    FOR ALL
    TO authenticated
    USING ((select auth.uid()) = user_id)
    WITH CHECK ((select auth.uid()) = user_id);


-- =========================================================================
-- WORKSTREAMS — fix initplan
-- =========================================================================

DROP POLICY IF EXISTS "Users can manage own workstreams" ON public.workstreams;

CREATE POLICY "Users can manage own workstreams" ON public.workstreams
    FOR ALL
    TO authenticated
    USING ((select auth.uid()) = user_id)
    WITH CHECK ((select auth.uid()) = user_id);


-- =========================================================================
-- USER_CARD_DISMISSALS — fix initplan (4 policies)
-- =========================================================================

DROP POLICY IF EXISTS "Users can view own dismissals" ON public.user_card_dismissals;
DROP POLICY IF EXISTS "Users can create own dismissals" ON public.user_card_dismissals;
DROP POLICY IF EXISTS "Users can update own dismissals" ON public.user_card_dismissals;
DROP POLICY IF EXISTS "Users can delete own dismissals" ON public.user_card_dismissals;

CREATE POLICY "Users can view own dismissals" ON public.user_card_dismissals
    FOR SELECT
    TO authenticated
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can create own dismissals" ON public.user_card_dismissals
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "Users can update own dismissals" ON public.user_card_dismissals
    FOR UPDATE
    TO authenticated
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can delete own dismissals" ON public.user_card_dismissals
    FOR DELETE
    TO authenticated
    USING (user_id = (select auth.uid()));


-- =========================================================================
-- EXECUTIVE_BRIEFS — fix initplan (3 policies)
-- =========================================================================

DROP POLICY IF EXISTS "Users can create briefs for their workstream cards" ON public.executive_briefs;
DROP POLICY IF EXISTS "Users can update their own briefs" ON public.executive_briefs;
DROP POLICY IF EXISTS "Users can delete briefs in their workstreams" ON public.executive_briefs;

CREATE POLICY "Users can create briefs for their workstream cards"
    ON public.executive_briefs FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.workstream_cards wc
            JOIN public.workstreams w ON wc.workstream_id = w.id
            WHERE wc.id = workstream_card_id
            AND w.user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can update their own briefs"
    ON public.executive_briefs FOR UPDATE
    TO authenticated
    USING (
        created_by = (select auth.uid())
        OR EXISTS (
            SELECT 1 FROM public.workstream_cards wc
            JOIN public.workstreams w ON wc.workstream_id = w.id
            WHERE wc.id = workstream_card_id
            AND w.user_id = (select auth.uid())
        )
    );

CREATE POLICY "Users can delete briefs in their workstreams"
    ON public.executive_briefs FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.workstream_cards wc
            JOIN public.workstreams w ON wc.workstream_id = w.id
            WHERE wc.id = workstream_card_id
            AND w.user_id = (select auth.uid())
        )
    );


-- =========================================================================
-- SAVED_SEARCHES — fix initplan (4 policies)
-- =========================================================================

DROP POLICY IF EXISTS "Users can view own saved searches" ON public.saved_searches;
DROP POLICY IF EXISTS "Users can create own saved searches" ON public.saved_searches;
DROP POLICY IF EXISTS "Users can update own saved searches" ON public.saved_searches;
DROP POLICY IF EXISTS "Users can delete own saved searches" ON public.saved_searches;

CREATE POLICY "Users can view own saved searches" ON public.saved_searches
    FOR SELECT
    TO authenticated
    USING ((select auth.uid()) = user_id);

CREATE POLICY "Users can create own saved searches" ON public.saved_searches
    FOR INSERT
    TO authenticated
    WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "Users can update own saved searches" ON public.saved_searches
    FOR UPDATE
    TO authenticated
    USING ((select auth.uid()) = user_id);

CREATE POLICY "Users can delete own saved searches" ON public.saved_searches
    FOR DELETE
    TO authenticated
    USING ((select auth.uid()) = user_id);


-- =========================================================================
-- SEARCH_HISTORY — fix initplan (3 policies)
-- =========================================================================

DROP POLICY IF EXISTS "Users can view own search history" ON public.search_history;
DROP POLICY IF EXISTS "Users can create own search history" ON public.search_history;
DROP POLICY IF EXISTS "Users can delete own search history" ON public.search_history;

CREATE POLICY "Users can view own search history" ON public.search_history
    FOR SELECT
    TO authenticated
    USING ((select auth.uid()) = user_id);

CREATE POLICY "Users can create own search history" ON public.search_history
    FOR INSERT
    TO authenticated
    WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "Users can delete own search history" ON public.search_history
    FOR DELETE
    TO authenticated
    USING ((select auth.uid()) = user_id);


-- =========================================================================
-- USER_SIGNAL_PREFERENCES — fix initplan (from recent migration)
-- =========================================================================

DROP POLICY IF EXISTS "Users manage own signal preferences" ON public.user_signal_preferences;

CREATE POLICY "Users manage own signal preferences" ON public.user_signal_preferences
    FOR ALL
    TO authenticated
    USING ((select auth.uid()) = user_id)
    WITH CHECK ((select auth.uid()) = user_id);


COMMIT;
