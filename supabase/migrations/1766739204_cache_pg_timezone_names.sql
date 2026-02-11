-- Cache pg_timezone_names to avoid repeated slow function calls.
-- pg_timezone_names() loads timezone data from the OS on every call
-- (0% cache hit rate, ~260ms avg). A materialized view makes it a
-- simple table scan instead.  Timezone lists only change on major
-- PostgreSQL upgrades, so a periodic REFRESH is more than sufficient.

CREATE MATERIALIZED VIEW IF NOT EXISTS public.pg_timezone_names_cache AS
SELECT name, abbrev, utc_offset, is_dst
FROM pg_timezone_names;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tz_cache_name
    ON public.pg_timezone_names_cache (name);
