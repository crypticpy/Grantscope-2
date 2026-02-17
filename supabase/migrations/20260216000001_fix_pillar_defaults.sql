-- Migration: Fix pillar codes in discovery_schedule
-- Phase 0B: Correct the default pillars_to_scan values
--
-- The original migration (20260213000001_discovery_schedule.sql) used old/wrong
-- pillar codes for the pillars_to_scan column:
--
--   OLD: CH, MC, HS, EC, ES, CE
--
-- These should be the correct CSP-aligned pillar codes (added in
-- 1766739006_fix_pillar_codes.sql):
--
--   NEW: CH, EW, HG, HH, MC, PS
--
-- This migration:
--   1. Updates any existing rows that still have the old default array
--   2. Alters the column default for future inserts
-- It is idempotent — safe to run multiple times.

-- Step 1: Update existing rows that have the old default pillar codes
UPDATE discovery_schedule
SET pillars_to_scan = ARRAY['CH', 'EW', 'HG', 'HH', 'MC', 'PS']
WHERE pillars_to_scan = ARRAY['CH', 'MC', 'HS', 'EC', 'ES', 'CE'];

-- Step 2: Fix the column default for future rows
ALTER TABLE discovery_schedule
ALTER COLUMN pillars_to_scan
SET DEFAULT ARRAY['CH', 'EW', 'HG', 'HH', 'MC', 'PS'];
