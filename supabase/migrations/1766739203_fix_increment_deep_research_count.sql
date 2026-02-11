-- Fix mutable search_path on increment_deep_research_count
CREATE OR REPLACE FUNCTION public.increment_deep_research_count(p_card_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
    v_today DATE := CURRENT_DATE;
BEGIN
    UPDATE public.cards
    SET
        deep_research_count_today = CASE
            WHEN deep_research_reset_date = v_today THEN COALESCE(deep_research_count_today, 0) + 1
            ELSE 1
        END,
        deep_research_reset_date = v_today
    WHERE id = p_card_id;
END;
$fn$;
