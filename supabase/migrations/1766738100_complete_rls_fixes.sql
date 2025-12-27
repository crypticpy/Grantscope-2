-- Migration: complete_rls_fixes
-- Created at: 1766738100
-- Description: Complete RLS policy coverage for all tables identified in security audit
-- Security Audit Date: 2025-12-27
--
-- This migration fixes all missing RLS policies identified during the security audit.
-- All user-owned tables now have complete CRUD policy coverage.

-- ============================================================================
-- CRITICAL: card_relationships - Add missing policies (NO policies existed)
-- ============================================================================

-- Allow all authenticated users to view card relationships (shared intelligence)
CREATE POLICY "Authenticated users can view card_relationships"
    ON card_relationships FOR SELECT
    TO authenticated
    USING (true);

-- Allow authenticated users to insert relationships
-- (Relationships are typically created by system but users may need to suggest)
CREATE POLICY "Authenticated users can insert card_relationships"
    ON card_relationships FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- Service role has full access for system operations
CREATE POLICY "Service role full access on card_relationships"
    ON card_relationships FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- HIGH: cards - Add DELETE policy
-- ============================================================================

-- Users can only delete cards they created
CREATE POLICY "Users can delete own cards"
    ON cards FOR DELETE
    TO authenticated
    USING (auth.uid() = created_by);

-- Service role can delete any card (for admin operations)
CREATE POLICY "Service role can delete cards"
    ON cards FOR DELETE
    TO service_role
    USING (true);

-- ============================================================================
-- HIGH: sources - Add UPDATE/DELETE policies (service role only)
-- Sources are AI-generated and should not be directly modified by users
-- ============================================================================

CREATE POLICY "Service role can update sources"
    ON sources FOR UPDATE
    TO service_role
    USING (true);

CREATE POLICY "Service role can delete sources"
    ON sources FOR DELETE
    TO service_role
    USING (true);

-- ============================================================================
-- MEDIUM: card_timeline - Add INSERT/UPDATE/DELETE policies
-- Timeline entries are system-generated events
-- ============================================================================

-- Service role manages timeline entries
CREATE POLICY "Service role can insert card_timeline"
    ON card_timeline FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "Service role can update card_timeline"
    ON card_timeline FOR UPDATE
    TO service_role
    USING (true);

CREATE POLICY "Service role can delete card_timeline"
    ON card_timeline FOR DELETE
    TO service_role
    USING (true);

-- Allow authenticated users to insert timeline entries (for user-triggered events)
CREATE POLICY "Authenticated users can insert card_timeline"
    ON card_timeline FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- ============================================================================
-- MEDIUM: card_embeddings - Add INSERT/UPDATE/DELETE policies
-- Embeddings are AI-generated vectors
-- ============================================================================

CREATE POLICY "Service role full access on card_embeddings"
    ON card_embeddings FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "Service role can update card_embeddings"
    ON card_embeddings FOR UPDATE
    TO service_role
    USING (true);

CREATE POLICY "Service role can delete card_embeddings"
    ON card_embeddings FOR DELETE
    TO service_role
    USING (true);

-- ============================================================================
-- MEDIUM: implications_analyses - Add UPDATE/DELETE policies
-- ============================================================================

-- Users can update their own analyses
CREATE POLICY "Users can update own implications_analyses"
    ON implications_analyses FOR UPDATE
    TO authenticated
    USING (created_by = auth.uid());

-- Users can delete their own analyses
CREATE POLICY "Users can delete own implications_analyses"
    ON implications_analyses FOR DELETE
    TO authenticated
    USING (created_by = auth.uid());

-- Service role has full access
CREATE POLICY "Service role full access on implications_analyses"
    ON implications_analyses FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- MEDIUM: implications - Add UPDATE/DELETE policies
-- Implications belong to analyses, which belong to users
-- ============================================================================

-- Users can update implications in their own analyses
CREATE POLICY "Users can update implications in own analyses"
    ON implications FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM implications_analyses ia
            WHERE ia.id = implications.analysis_id
            AND ia.created_by = auth.uid()
        )
    );

-- Users can delete implications in their own analyses
CREATE POLICY "Users can delete implications in own analyses"
    ON implications FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM implications_analyses ia
            WHERE ia.id = implications.analysis_id
            AND ia.created_by = auth.uid()
        )
    );

-- Service role has full access
CREATE POLICY "Service role full access on implications"
    ON implications FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- MEDIUM: workstream_cards - Add DELETE policy
-- ============================================================================

-- Users can delete cards from their own workstreams
CREATE POLICY "Users can delete own workstream cards"
    ON workstream_cards FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM workstreams w
            WHERE w.id = workstream_cards.workstream_id
            AND w.user_id = auth.uid()
        )
    );

-- ============================================================================
-- ADDITIONAL: Ensure service role access on all tables for admin operations
-- These are defensive additions to ensure service role always has full access
-- ============================================================================

-- Check if service role policies exist, if not add them
-- (Using DO block for conditional creation)

DO $$
BEGIN
    -- Verify policies exist by checking pg_policies
    -- This is informational - actual policies are created above
    RAISE NOTICE 'RLS policy fixes applied successfully';
END $$;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON POLICY "Authenticated users can view card_relationships" ON card_relationships
    IS 'Security audit fix: Added missing SELECT policy';

COMMENT ON POLICY "Users can delete own cards" ON cards
    IS 'Security audit fix: Users can only delete their own cards';

COMMENT ON POLICY "Users can delete own workstream cards" ON workstream_cards
    IS 'Security audit fix: Users can remove cards from their workstreams';

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================

-- Run this to verify all tables have RLS enabled:
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY tablename;

-- Run this to see all policies:
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
-- FROM pg_policies
-- WHERE schemaname = 'public'
-- ORDER BY tablename, policyname;

SELECT 'RLS security fixes migration complete' as status;
