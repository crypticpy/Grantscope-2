-- ==========================================================================
-- Fix remaining RLS performance warnings on research_tasks & source_ratings
--
-- research_tasks:
--   Migration 1766739200 created the optimized "research_tasks_own" policy
--   (FOR ALL, TO authenticated, (select auth.uid())), but the 4 older
--   policies from 1766434900 were never dropped. They cause:
--     - auth_rls_initplan warnings (bare auth.uid() / auth.role())
--     - multiple_permissive_policies (overlap with research_tasks_own)
--   The "Service role full access" policy is also unnecessary because
--   service_role has BYPASSRLS privilege.
--
-- source_ratings:
--   3 policies use bare auth.uid() — wrap in (select auth.uid()) to fix
--   the auth_rls_initplan warning.
-- ==========================================================================

BEGIN;

-- =========================================================================
-- RESEARCH_TASKS — drop redundant / unoptimized policies
-- =========================================================================
-- "research_tasks_own" (FOR ALL, TO authenticated) already covers
-- SELECT, INSERT, UPDATE, DELETE for authenticated users.

DROP POLICY IF EXISTS "Users can view own research tasks" ON public.research_tasks;
DROP POLICY IF EXISTS "Users can create own research tasks" ON public.research_tasks;
DROP POLICY IF EXISTS "Users can update own research tasks" ON public.research_tasks;
DROP POLICY IF EXISTS "Service role full access on research_tasks" ON public.research_tasks;


-- =========================================================================
-- SOURCE_RATINGS — fix initplan on INSERT / UPDATE / DELETE policies
-- =========================================================================

DROP POLICY IF EXISTS "Users can create their own source ratings" ON public.source_ratings;
DROP POLICY IF EXISTS "Users can update their own source ratings" ON public.source_ratings;
DROP POLICY IF EXISTS "Users can delete their own source ratings" ON public.source_ratings;

CREATE POLICY "Users can create their own source ratings"
    ON public.source_ratings FOR INSERT
    TO authenticated
    WITH CHECK (user_id = (select auth.uid()));

CREATE POLICY "Users can update their own source ratings"
    ON public.source_ratings FOR UPDATE
    TO authenticated
    USING (user_id = (select auth.uid()));

CREATE POLICY "Users can delete their own source ratings"
    ON public.source_ratings FOR DELETE
    TO authenticated
    USING (user_id = (select auth.uid()));

COMMIT;
