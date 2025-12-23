-- Migration: create_embeddings_and_rls
-- Created at: 1766434562

-- Vector embeddings for semantic search
CREATE TABLE card_embeddings (
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE PRIMARY KEY,
    embedding VECTOR(1536), -- OpenAI ada-002 embedding dimension
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS Policies

-- Users: users can only see their own profile
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid() = id);

-- Cards: everyone can read, authenticated users can create
CREATE POLICY "Anyone can view cards" ON cards
    FOR SELECT USING (true);

CREATE POLICY "Authenticated users can create cards" ON cards
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Users can update own cards" ON cards
    FOR UPDATE USING (auth.uid() = created_by);

-- Sources: users can read sources for cards they can see
CREATE POLICY "Users can view sources" ON sources
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM cards 
            WHERE cards.id = sources.card_id
        )
    );

-- Timeline: users can read timeline for visible cards
CREATE POLICY "Users can view timeline" ON card_timeline
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM cards 
            WHERE cards.id = card_timeline.card_id
        )
    );

-- Follows: users can only see/manage their own follows
CREATE POLICY "Users can view own follows" ON card_follows
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own follows" ON card_follows
    FOR ALL USING (auth.uid() = user_id);

-- Notes: users can see their own notes and public notes
CREATE POLICY "Users can view notes" ON card_notes
    FOR SELECT USING (
        auth.uid() = user_id OR 
        is_private = false
    );

CREATE POLICY "Users can manage own notes" ON card_notes
    FOR ALL USING (auth.uid() = user_id);

-- Workstreams: users can only see/manage their own workstreams
CREATE POLICY "Users can manage own workstreams" ON workstreams
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view own workstream cards" ON workstream_cards
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM workstreams 
            WHERE workstreams.id = workstream_cards.workstream_id 
            AND workstreams.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can manage own workstream cards" ON workstream_cards
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM workstreams 
            WHERE workstreams.id = workstream_cards.workstream_id 
            AND workstreams.user_id = auth.uid()
        )
    );

-- Embeddings: readable by authenticated users
CREATE POLICY "Users can view embeddings" ON card_embeddings
    FOR SELECT USING (auth.role() = 'authenticated');;