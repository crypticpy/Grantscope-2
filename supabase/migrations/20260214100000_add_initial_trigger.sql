-- Add 'initial' as a valid trigger for V1 snapshots of existing descriptions
ALTER TABLE card_snapshots DROP CONSTRAINT IF EXISTS card_snapshots_trigger_check;
ALTER TABLE card_snapshots ADD CONSTRAINT card_snapshots_trigger_check
    CHECK (trigger IN ('deep_research', 'profile_refresh', 'enhance_research', 'manual_edit', 'restore', 'initial'));
