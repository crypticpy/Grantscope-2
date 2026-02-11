-- Restore composite index on card_score_history that supports
-- the /cards/compare endpoint (filters by card_id, orders by recorded_at).
-- This was incorrectly dropped in 1766739202 as "unused" but is needed
-- for efficient comparison queries as the table grows.

CREATE INDEX IF NOT EXISTS idx_card_score_history_card_id_recorded_at
    ON public.card_score_history (card_id, recorded_at);
