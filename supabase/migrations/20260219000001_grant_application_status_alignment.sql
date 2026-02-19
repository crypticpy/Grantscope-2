-- Migration: grant_application_status_alignment
-- Created at: 20260219000001
-- Purpose: Align grant_applications.status constraint with backend lifecycle
--          transitions used by ApplicationService/CollaborationService.

DO $$
BEGIN
    -- Replace status constraint with expanded lifecycle set.
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'grant_applications_status_check'
          AND conrelid = 'grant_applications'::regclass
    ) THEN
        ALTER TABLE grant_applications
            DROP CONSTRAINT grant_applications_status_check;
    END IF;

    ALTER TABLE grant_applications
        ADD CONSTRAINT grant_applications_status_check
        CHECK (status IN (
            'draft',
            'in_progress',
            'under_review',
            'submitted',
            'pending_decision',
            'awarded',
            'declined',
            'withdrawn',
            'expired'
        ));
END $$;

COMMENT ON COLUMN grant_applications.status IS
'Application lifecycle status: draft, in_progress, under_review, submitted, pending_decision, awarded, declined, withdrawn, expired';
