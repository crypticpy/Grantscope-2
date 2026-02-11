-- Drop the timezone cache materialized view.
-- The slow pg_timezone_names calls come from PostgREST internal schema
-- introspection which won't use our MV. Remove to avoid unnecessary
-- API exposure flagged by Supabase advisor.

DROP INDEX IF EXISTS idx_tz_cache_name;
DROP MATERIALIZED VIEW IF EXISTS public.pg_timezone_names_cache;
