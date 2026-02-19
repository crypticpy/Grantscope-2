-- Migration: proposals_section_approvals
-- Created at: 20260219000002
-- Purpose: Add section-level review metadata storage used by collaboration
--          approve/revise endpoints.

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS section_approvals JSONB DEFAULT '{}'::jsonb;

UPDATE proposals
SET section_approvals = '{}'::jsonb
WHERE section_approvals IS NULL;

COMMENT ON COLUMN proposals.section_approvals IS
'JSONB section-level review map keyed by section_name with status/reviewer/reviewed_at/notes.';
