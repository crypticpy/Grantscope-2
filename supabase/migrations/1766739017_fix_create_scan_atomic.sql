-- Fix mutable search_path on create_workstream_scan_atomic
CREATE OR REPLACE FUNCTION public.create_workstream_scan_atomic(
    p_workstream_id UUID,
    p_user_id UUID,
    p_config JSONB
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
    new_scan_id UUID;
    daily_count INTEGER;
    active_count INTEGER;
BEGIN
    PERFORM id FROM public.workstreams WHERE id = p_workstream_id FOR UPDATE;

    SELECT COUNT(*) INTO active_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND status IN ('queued', 'running');

    IF active_count > 0 THEN
        RETURN NULL;
    END IF;

    SELECT COUNT(*) INTO daily_count
    FROM public.workstream_scans
    WHERE workstream_id = p_workstream_id
      AND created_at > NOW() - INTERVAL '24 hours';

    IF daily_count >= 2 THEN
        RETURN NULL;
    END IF;

    INSERT INTO public.workstream_scans (workstream_id, user_id, status, config, created_at)
    VALUES (p_workstream_id, p_user_id, 'queued', p_config, NOW())
    RETURNING id INTO new_scan_id;

    RETURN new_scan_id;
END;
$fn$;
