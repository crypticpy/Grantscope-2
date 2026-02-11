-- ==========================================================================
-- Security Lint Fixes
--
-- Addresses findings from the Supabase database linter:
--   1. function_search_path_mutable — 5 functions missing SET search_path
--   2. rls_policy_always_true — 2 overly permissive INSERT policies
--
-- Note: auth_leaked_password_protection is a Supabase dashboard setting
-- and cannot be fixed via migration. Enable it at:
--   Dashboard → Auth → Settings → Password Protection → Enable
-- ==========================================================================


-- --------------------------------------------------------------------------
-- 1. Fix mutable search_path on 5 functions
--
-- Without `SET search_path = ''`, a malicious actor who can alter the
-- search_path could hijack function execution by shadowing pg catalog
-- or public schema objects.  Setting it to '' forces fully-qualified
-- references inside the function body.
-- --------------------------------------------------------------------------

-- 1a. update_updated_at — generic trigger used on many tables
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- 1b. cleanup_search_history — after-insert trigger
CREATE OR REPLACE FUNCTION public.cleanup_search_history()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    DELETE FROM public.search_history
    WHERE user_id = NEW.user_id
    AND id NOT IN (
        SELECT id FROM public.search_history
        WHERE user_id = NEW.user_id
        ORDER BY executed_at DESC
        LIMIT 50
    );
    RETURN NEW;
END;
$$;

-- 1c. check_workstream_scan_rate_limit
CREATE OR REPLACE FUNCTION public.check_workstream_scan_rate_limit(
    p_workstream_id UUID
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    scan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO scan_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND created_at > NOW() - INTERVAL '24 hours';

    RETURN scan_count < 2;
END;
$$;

-- 1d. has_active_workstream_scan
CREATE OR REPLACE FUNCTION public.has_active_workstream_scan(
    p_workstream_id UUID
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    active_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO active_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND status IN ('queued', 'running');

    RETURN active_count > 0;
END;
$$;

-- 1e. create_workstream_scan_atomic
CREATE OR REPLACE FUNCTION public.create_workstream_scan_atomic(
    p_workstream_id UUID,
    p_user_id UUID,
    p_config JSONB
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    new_scan_id UUID;
    daily_count INTEGER;
    active_count INTEGER;
BEGIN
    -- Lock the workstream row to prevent race conditions
    PERFORM id FROM public.workstreams WHERE id = p_workstream_id FOR UPDATE;

    -- Check for active scans
    SELECT COUNT(*) INTO active_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND status IN ('queued', 'running');

    IF active_count > 0 THEN
        RETURN NULL;  -- Already has active scan
    END IF;

    -- Check daily rate limit
    SELECT COUNT(*) INTO daily_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND created_at > NOW() - INTERVAL '24 hours';

    IF daily_count >= 2 THEN
        RETURN NULL;  -- Rate limit exceeded
    END IF;

    -- Create the scan
    INSERT INTO public.workstream_scans (workstream_id, user_id, status, config, created_at)
    VALUES (p_workstream_id, p_user_id, 'queued', p_config, NOW())
    RETURNING id INTO new_scan_id;

    RETURN new_scan_id;
END;
$$;


-- --------------------------------------------------------------------------
-- 2. Tighten overly permissive RLS INSERT policies
--
-- Both card_score_history and discovery_blocks are written exclusively by
-- the backend (service_role).  The frontend never inserts into these tables.
-- Dropping the blanket authenticated INSERT policies removes unnecessary
-- attack surface while the existing service_role ALL policy continues to
-- allow backend writes.
-- --------------------------------------------------------------------------

-- 2a. card_score_history — drop blanket INSERT, keep SELECT + service_role
DROP POLICY IF EXISTS "Authenticated users can insert score history"
    ON public.card_score_history;

-- 2b. discovery_blocks — drop blanket INSERT, keep SELECT + service_role
DROP POLICY IF EXISTS "Authenticated users can suggest blocks"
    ON public.discovery_blocks;
