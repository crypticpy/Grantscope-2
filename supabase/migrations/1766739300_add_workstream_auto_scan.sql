-- Add auto_scan column to workstreams table
-- This enables the automatic background scanning feature introduced in the wizard
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS auto_scan BOOLEAN DEFAULT false;

COMMENT ON COLUMN workstreams.auto_scan IS 'Enable automatic background source scanning for this workstream';
