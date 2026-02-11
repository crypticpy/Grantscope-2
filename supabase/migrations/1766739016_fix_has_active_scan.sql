-- Fix mutable search_path on has_active_workstream_scan
CREATE OR REPLACE FUNCTION public.has_active_workstream_scan(
    p_workstream_id UUID
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
    active_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO active_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND status IN ('queued', 'running');

    RETURN active_count > 0;
END;
$fn$;
