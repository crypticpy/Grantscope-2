-- Fix mutable search_path on cleanup_search_history
CREATE OR REPLACE FUNCTION public.cleanup_search_history()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
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
$fn$;
