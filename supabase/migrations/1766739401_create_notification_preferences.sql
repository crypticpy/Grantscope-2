-- Migration: create_notification_preferences
-- Created at: 1766739401
-- Purpose: Add notification preferences table for email digest configuration

-- ============================================================================
-- NOTIFICATION PREFERENCES TABLE
-- Stores per-user email digest settings including a configurable
-- notification email (separate from auth email, since test accounts
-- often use fake emails).
-- ============================================================================

CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    notification_email TEXT,  -- NULL means use auth email
    digest_frequency TEXT DEFAULT 'weekly' CHECK (digest_frequency IN ('daily', 'weekly', 'none')),
    digest_day TEXT DEFAULT 'monday' CHECK (digest_day IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday')),
    include_new_signals BOOLEAN DEFAULT true,
    include_velocity_changes BOOLEAN DEFAULT true,
    include_pattern_insights BOOLEAN DEFAULT true,
    include_workstream_updates BOOLEAN DEFAULT true,
    last_digest_sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY;

-- Users can only read/write their own notification preferences
CREATE POLICY "Users can manage own notification preferences"
    ON notification_preferences FOR ALL
    USING (auth.uid() = user_id);

-- Service role needs full access for batch digest processing
CREATE POLICY "Service role full access on notification_preferences"
    ON notification_preferences FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Fast lookup by user_id (unique constraint already creates an index,
-- but explicit index helps with service-role batch queries)
CREATE INDEX IF NOT EXISTS idx_notification_prefs_user
    ON notification_preferences (user_id);

-- For batch digest processing: find users due for a digest
CREATE INDEX IF NOT EXISTS idx_notification_prefs_frequency
    ON notification_preferences (digest_frequency, digest_day)
    WHERE digest_frequency != 'none';

-- ============================================================================
-- DIGEST LOG TABLE
-- Stores generated digest content for audit and retry purposes
-- ============================================================================

CREATE TABLE IF NOT EXISTS digest_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    digest_type TEXT NOT NULL DEFAULT 'weekly',  -- 'daily' or 'weekly'
    subject TEXT NOT NULL,
    html_content TEXT NOT NULL,
    summary_json JSONB,  -- Structured digest data before HTML rendering
    status TEXT NOT NULL DEFAULT 'generated' CHECK (status IN ('generated', 'sent', 'failed')),
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE digest_logs ENABLE ROW LEVEL SECURITY;

-- Users can view their own digest history
CREATE POLICY "Users can view own digest logs"
    ON digest_logs FOR SELECT
    USING (auth.uid() = user_id);

-- Service role needs full access for digest generation
CREATE POLICY "Service role full access on digest_logs"
    ON digest_logs FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_digest_logs_user
    ON digest_logs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_digest_logs_status
    ON digest_logs (status, created_at)
    WHERE status = 'generated';

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE notification_preferences IS 'Per-user email digest configuration including notification email override';
COMMENT ON COLUMN notification_preferences.notification_email IS 'Override email for digests — NULL means use the auth.users email';
COMMENT ON COLUMN notification_preferences.digest_frequency IS 'How often digests are sent: daily, weekly, or none (disabled)';
COMMENT ON COLUMN notification_preferences.digest_day IS 'Day of week for weekly digests (ignored for daily)';
COMMENT ON COLUMN notification_preferences.last_digest_sent_at IS 'Timestamp of last successfully sent digest';

COMMENT ON TABLE digest_logs IS 'Audit log of generated digest emails with content and delivery status';

-- ============================================================================
-- DONE
-- ============================================================================

SELECT 'notification_preferences and digest_logs tables created' as status;
