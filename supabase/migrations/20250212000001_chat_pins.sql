-- Pin/save chat messages for quick reference
CREATE TABLE IF NOT EXISTS chat_pinned_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    message_id uuid NOT NULL,
    conversation_id uuid NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, message_id)
);

-- Index for user's pinned messages
CREATE INDEX idx_chat_pinned_user ON chat_pinned_messages(user_id, created_at DESC);

-- RLS policies
ALTER TABLE chat_pinned_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own pins"
    ON chat_pinned_messages
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
