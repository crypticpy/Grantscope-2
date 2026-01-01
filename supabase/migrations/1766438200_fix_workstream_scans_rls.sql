-- Fix RLS policy for workstream_scans to allow service role access
-- The auth.role() function doesn't work as expected with service key
-- Use a more permissive approach for backend/worker access

-- Drop the existing service role policy
DROP POLICY IF EXISTS "Service role full access to workstream_scans" ON workstream_scans;

-- Create a policy that allows access when using service role key
-- Service role bypasses RLS by default in Supabase, but we need to ensure
-- the policy allows operations when RLS is enabled

-- Allow all operations for service role (checking JWT role claim)
CREATE POLICY "Service role full access to workstream_scans"
    ON workstream_scans FOR ALL
    USING (
        -- Check if the current role is service_role via JWT
        coalesce(current_setting('request.jwt.claims', true)::json->>'role', '') = 'service_role'
        OR
        -- Fallback: auth.role() for newer Supabase versions  
        auth.role() = 'service_role'
        OR
        -- User-based access (existing check)
        user_id = auth.uid()
    )
    WITH CHECK (
        coalesce(current_setting('request.jwt.claims', true)::json->>'role', '') = 'service_role'
        OR
        auth.role() = 'service_role'
        OR
        user_id = auth.uid()
    );
