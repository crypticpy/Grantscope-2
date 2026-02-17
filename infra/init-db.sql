-- =============================================================================
-- GrantScope2 — PostgreSQL Initialization
-- =============================================================================
-- Creates the roles, extensions, and schemas required by PostgREST and GoTrue.
-- This file runs ONCE when the PostgreSQL container is first created via
-- docker-entrypoint-initdb.d. Migrations (supabase/migrations/*.sql) run
-- separately via infra/migrate.sh.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Extensions schema (Supabase convention: keep public schema clean)
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS extensions;
COMMENT ON SCHEMA extensions IS 'Schema for PostgreSQL extensions';

-- ---------------------------------------------------------------------------
-- Auth schema (GoTrue manages its own tables here)
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS auth;
COMMENT ON SCHEMA auth IS 'Schema for GoTrue authentication tables';

-- ---------------------------------------------------------------------------
-- Roles required by PostgREST
-- ---------------------------------------------------------------------------
-- NOTE: Role passwords here MUST match POSTGRES_PASSWORD in docker-compose.yml.
-- Default is 'postgres'. If you change POSTGRES_PASSWORD, update these too.
-- ---------------------------------------------------------------------------

-- Authenticator: PostgREST connects as this role and switches per-request
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
        CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'postgres';
    END IF;
END $$;

-- Anonymous role: used for requests with the anon JWT
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
END $$;
GRANT anon TO authenticator;

-- Authenticated role: used for requests with a user JWT
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
END $$;
GRANT authenticated TO authenticator;

-- Service role: bypasses RLS, used by backend with service key
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
    END IF;
END $$;
GRANT service_role TO authenticator;

-- GoTrue auth admin: manages auth schema tables
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
        CREATE ROLE supabase_auth_admin NOINHERIT LOGIN PASSWORD 'postgres';
    END IF;
END $$;
GRANT supabase_auth_admin TO postgres;

-- ---------------------------------------------------------------------------
-- Schema permissions
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA extensions TO anon, authenticated, service_role;
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT USAGE ON SCHEMA auth TO authenticated, service_role;

-- Service role gets full access to public tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON FUNCTIONS TO service_role;

-- Anon and authenticated get select by default (RLS handles row-level filtering)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO anon, authenticated;

-- GoTrue admin gets full access to auth schema
ALTER DEFAULT PRIVILEGES IN SCHEMA auth
    GRANT ALL ON TABLES TO supabase_auth_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth
    GRANT ALL ON SEQUENCES TO supabase_auth_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth
    GRANT ALL ON FUNCTIONS TO supabase_auth_admin;

-- ---------------------------------------------------------------------------
-- Seed: ensure postgres superuser can run migrations that reference these roles
-- ---------------------------------------------------------------------------
GRANT anon, authenticated, service_role TO postgres;
