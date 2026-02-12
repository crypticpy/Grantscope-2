-- Chat conversations and messages for Ask Foresight NLQ feature
-- Supports 3 scopes: signal (per-card), workstream, global

CREATE TABLE chat_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK (scope IN ('signal', 'workstream', 'global')),
  scope_id UUID,  -- card_id for signal, workstream_id for workstream, NULL for global
  title TEXT,     -- auto-generated from first message
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  citations JSONB DEFAULT '[]',  -- [{card_id, source_id, title, url, excerpt}]
  tokens_used INTEGER,
  model TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX idx_chat_conv_user ON chat_conversations(user_id, updated_at DESC);
CREATE INDEX idx_chat_conv_scope ON chat_conversations(scope, scope_id, user_id);
CREATE INDEX idx_chat_msg_conv ON chat_messages(conversation_id, created_at);

-- RLS
ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users own their conversations"
  ON chat_conversations FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users access their messages"
  ON chat_messages FOR ALL
  USING (conversation_id IN (
    SELECT id FROM chat_conversations WHERE user_id = auth.uid()
  ));
