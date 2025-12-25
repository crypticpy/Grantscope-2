-- Migration: enable_rls_security
-- Created at: 1766435004
-- Description: Enable RLS on all public tables and create appropriate policies
-- Fixes: policy_exists_rls_disabled, rls_disabled_in_public errors

-- ============================================================================
-- ENABLE RLS ON ALL TABLES
-- ============================================================================

-- card_embeddings already has policies, just need to enable RLS
ALTER TABLE public.card_embeddings ENABLE ROW LEVEL SECURITY;

-- Reference tables (read-only for all authenticated users)
ALTER TABLE public.pillars ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.anchors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.priorities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.goals ENABLE ROW LEVEL SECURITY;

-- Analysis tables
ALTER TABLE public.implications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.implications_analyses ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- POLICIES FOR REFERENCE TABLES (read-only for authenticated users)
-- These are static reference data that all users can view
-- ============================================================================

-- Pillars
CREATE POLICY "Authenticated users can view pillars"
    ON public.pillars FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on pillars"
    ON public.pillars FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Anchors
CREATE POLICY "Authenticated users can view anchors"
    ON public.anchors FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on anchors"
    ON public.anchors FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Priorities
CREATE POLICY "Authenticated users can view priorities"
    ON public.priorities FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on priorities"
    ON public.priorities FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Stages
CREATE POLICY "Authenticated users can view stages"
    ON public.stages FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on stages"
    ON public.stages FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Goals
CREATE POLICY "Authenticated users can view goals"
    ON public.goals FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on goals"
    ON public.goals FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- POLICIES FOR IMPLICATIONS TABLES
-- ============================================================================

-- Implications (linked to cards)
CREATE POLICY "Authenticated users can view implications"
    ON public.implications FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on implications"
    ON public.implications FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Implications Analyses
CREATE POLICY "Authenticated users can view implications_analyses"
    ON public.implications_analyses FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access on implications_analyses"
    ON public.implications_analyses FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON POLICY "Authenticated users can view pillars" ON public.pillars
    IS 'Reference data - all authenticated users can read';
COMMENT ON POLICY "Authenticated users can view anchors" ON public.anchors
    IS 'Reference data - all authenticated users can read';
COMMENT ON POLICY "Authenticated users can view priorities" ON public.priorities
    IS 'Reference data - all authenticated users can read';
COMMENT ON POLICY "Authenticated users can view stages" ON public.stages
    IS 'Reference data - all authenticated users can read';
COMMENT ON POLICY "Authenticated users can view goals" ON public.goals
    IS 'Reference data - all authenticated users can read';
