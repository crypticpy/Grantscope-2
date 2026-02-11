-- Fix mutable search_path on check_workstream_scan_rate_limit
CREATE OR REPLACE FUNCTION public.check_workstream_scan_rate_limit(
    p_workstream_id UUID
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
    scan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO scan_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND created_at > NOW() - INTERVAL '24 hours';

    RETURN scan_count < 2;
END;
$fn$;
