-- Security Lint Fixes (retry) — split into individual statements for CLI compatibility
-- Addresses: function_search_path_mutable + rls_policy_always_true

-- Drop overly permissive INSERT policies first (simple statements)
DROP POLICY IF EXISTS "Authenticated users can insert score history"
    ON public.card_score_history;

DROP POLICY IF EXISTS "Authenticated users can suggest blocks"
    ON public.discovery_blocks;
