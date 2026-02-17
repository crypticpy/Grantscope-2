# GrantScope2: Data Model & Database Schema

## Entity Relationship Overview

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    User     │──────<│  Workstream │>──────│    Card     │
└─────────────┘       └─────────────┘       └──────┬──────┘
      │                                            │
      │                                            │
      ▼                                            ▼
┌─────────────┐                            ┌─────────────┐
│  CardFollow │                            │   Source    │
└─────────────┘                            └─────────────┘
                                                  │
┌─────────────┐       ┌─────────────┐             │
│   CardNote  │       │ CardTimeline│◄────────────┘
└─────────────┘       └─────────────┘

┌─────────────┐       ┌─────────────┐
│  Analysis   │──────>│ Implication │
└─────────────┘       └─────────────┘
```

---

## Core Tables

### users

Managed by Supabase Auth, extended with profile data.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email TEXT NOT NULL,
    display_name TEXT,
    department TEXT,
    role TEXT,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Preferences JSON structure:
-- {
--   "digest_frequency": "daily" | "weekly",
--   "notification_email": true,
--   "default_pillars": ["CH", "MC"],
--   "theme": "light" | "dark"
-- }
```

### cards

The core entity - atomic units of strategic intelligence.

```sql
CREATE TABLE cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    summary TEXT,  -- AI-generated current summary

    -- Classification
    horizon TEXT CHECK (horizon IN ('H1', 'H2', 'H3')),
    stage INTEGER CHECK (stage BETWEEN 1 AND 8),
    triage_score INTEGER CHECK (triage_score IN (1, 3, 5)),

    -- Taxonomy (arrays for multi-select)
    pillars TEXT[] DEFAULT '{}',           -- ['CH', 'MC']
    goals TEXT[] DEFAULT '{}',             -- ['CH.1', 'CH.3']
    steep_categories TEXT[] DEFAULT '{}',  -- ['T', 'E']
    anchors TEXT[] DEFAULT '{}',           -- ['Equity', 'Innovation']
    top25_relevance TEXT[] DEFAULT '{}',   -- Matching Top 25 items

    -- Scoring (7 criteria)
    credibility_score NUMERIC(3,2),        -- 1.0 - 5.0
    novelty_score NUMERIC(3,2),
    likelihood_score NUMERIC(3,2),         -- 1.0 - 9.0
    impact_score NUMERIC(3,2),
    relevance_score NUMERIC(3,2),
    time_to_awareness_months INTEGER,
    time_to_prepare_months INTEGER,

    -- Computed
    velocity_score NUMERIC(5,2) DEFAULT 0, -- Updated by trigger
    follower_count INTEGER DEFAULT 0,
    source_count INTEGER DEFAULT 0,

    -- Embedding for semantic search
    embedding VECTOR(1536),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    is_archived BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_cards_embedding ON cards
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_cards_pillars ON cards USING GIN (pillars);
CREATE INDEX idx_cards_horizon ON cards (horizon);
CREATE INDEX idx_cards_stage ON cards (stage);
CREATE INDEX idx_cards_updated ON cards (updated_at DESC);
```

### Stage Reference

| Stage | Name            | Horizon | Description                    |
| ----- | --------------- | ------- | ------------------------------ |
| 1     | Concept         | H3      | Academic/theoretical           |
| 2     | Emerging        | H3      | Startups, patents, VC interest |
| 3     | Prototype       | H2      | Working demos                  |
| 4     | Pilot           | H2      | Real-world testing             |
| 5     | Municipal Pilot | H2      | Government testing             |
| 6     | Early Adoption  | H1      | Multiple cities implementing   |
| 7     | Mainstream      | H1      | Widespread adoption            |
| 8     | Mature          | H1      | Established, commoditized      |

### sources

Individual articles, papers, and documents linked to cards.

```sql
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,

    -- Source info
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    publication TEXT,
    author TEXT,
    published_at TIMESTAMPTZ,

    -- Processing
    api_source TEXT,  -- 'newsapi', 'arxiv', 'rss', 'manual'
    full_text TEXT,
    ai_summary TEXT,
    key_excerpts TEXT[],
    relevance_to_card NUMERIC(3,2),

    -- Embedding
    embedding VECTOR(1536),

    -- Metadata
    ingested_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(card_id, url)
);

CREATE INDEX idx_sources_card ON sources (card_id);
CREATE INDEX idx_sources_embedding ON sources
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### card_timeline

Event log tracking card evolution.

```sql
CREATE TABLE card_timeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,

    event_type TEXT NOT NULL,
    -- 'created', 'stage_change', 'source_added',
    -- 'summary_updated', 'analysis_added', 'user_note'

    event_description TEXT,
    previous_value JSONB,
    new_value JSONB,
    triggered_by_source_id UUID REFERENCES sources(id),
    triggered_by_user_id UUID REFERENCES users(id),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_timeline_card ON card_timeline (card_id, created_at DESC);
```

### workstreams

User-defined lenses for filtering intelligence.

```sql
CREATE TABLE workstreams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    description TEXT,

    -- Filter criteria
    pillars TEXT[] DEFAULT '{}',
    goals TEXT[] DEFAULT '{}',
    anchors TEXT[] DEFAULT '{}',
    keywords TEXT[] DEFAULT '{}',
    min_stage INTEGER,
    max_stage INTEGER,
    horizons TEXT[] DEFAULT '{}',

    -- Settings
    is_default BOOLEAN DEFAULT FALSE,
    notification_enabled BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workstreams_user ON workstreams (user_id);
```

### card_follows

Junction table for users following cards.

```sql
CREATE TABLE card_follows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    workstream_id UUID REFERENCES workstreams(id) ON DELETE SET NULL,

    followed_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, card_id)
);

CREATE INDEX idx_follows_user ON card_follows (user_id);
CREATE INDEX idx_follows_card ON card_follows (card_id);
```

### card_notes

User annotations on cards.

```sql
CREATE TABLE card_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    content TEXT NOT NULL,
    is_private BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notes_card ON card_notes (card_id);
```

---

## Analysis Tables

### implications_analyses

Implications Wheel analysis sessions.

```sql
CREATE TABLE implications_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,

    perspective TEXT NOT NULL,  -- 'general', department name, or pillar
    perspective_detail TEXT,    -- Additional context

    summary TEXT,  -- AI-generated summary of key findings

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analyses_card ON implications_analyses (card_id);
```

### implications

Individual implications in an analysis (hierarchical).

```sql
CREATE TABLE implications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID REFERENCES implications_analyses(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES implications(id) ON DELETE CASCADE,

    order_level INTEGER NOT NULL CHECK (order_level BETWEEN 1 AND 3),
    -- 1 = first-order, 2 = second-order, 3 = third-order

    content TEXT NOT NULL,

    -- Scoring
    likelihood_score INTEGER CHECK (likelihood_score BETWEEN 1 AND 9),
    desirability_score INTEGER CHECK (desirability_score BETWEEN -5 AND 5),

    -- Flags
    flag TEXT CHECK (flag IN (
        'likely_strong_negative',
        'unlikely_strong_positive',
        'catastrophe',
        'triumph'
    )),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_implications_analysis ON implications (analysis_id);
CREATE INDEX idx_implications_parent ON implications (parent_id);
```

---

## Reference Tables

### pillars

```sql
CREATE TABLE pillars (
    code TEXT PRIMARY KEY,  -- 'CH', 'EW', etc.
    name TEXT NOT NULL,
    description TEXT
);

INSERT INTO pillars VALUES
    ('CH', 'Community Health & Sustainability', 'Public health, parks, climate, preparedness'),
    ('EW', 'Economic & Workforce Development', 'Economic mobility, small business, creative economy'),
    ('HG', 'High-Performing Government', 'Fiscal, technology, workforce, engagement'),
    ('HH', 'Homelessness & Housing', 'Communities, affordable housing, homelessness reduction'),
    ('MC', 'Mobility & Critical Infrastructure', 'Transportation, transit, utilities, facilities'),
    ('PS', 'Public Safety', 'Relationships, fair delivery, disaster preparedness');
```

### goals

```sql
CREATE TABLE goals (
    code TEXT PRIMARY KEY,  -- 'CH.1', 'CH.2', etc.
    pillar_code TEXT REFERENCES pillars(code),
    name TEXT NOT NULL,
    description TEXT
);

-- Insert all 23 goals...
INSERT INTO goals VALUES
    ('CH.1', 'CH', 'Equitable public health services', NULL),
    ('CH.2', 'CH', 'Parks, trails, recreation access', NULL),
    ('CH.3', 'CH', 'Natural resources & climate mitigation', NULL),
    ('CH.4', 'CH', 'Community preparedness & resiliency', NULL),
    ('CH.5', 'CH', 'Animal Center operations', NULL),
    ('EW.1', 'EW', 'Economic mobility', NULL),
    ('EW.2', 'EW', 'Small/BIPOC business economy', NULL),
    ('EW.3', 'EW', 'Creative ecosystem', NULL),
    ('HG.1', 'HG', 'Fiscal integrity', NULL),
    ('HG.2', 'HG', 'Data & technology capabilities', NULL),
    ('HG.3', 'HG', 'Workforce recruitment & retention', NULL),
    ('HG.4', 'HG', 'Equitable outreach & engagement', NULL),
    ('HH.1', 'HH', 'Complete communities', NULL),
    ('HH.2', 'HH', 'Affordable housing', NULL),
    ('HH.3', 'HH', 'Reduce homelessness', NULL),
    ('MC.1', 'MC', 'Mobility safety', NULL),
    ('MC.2', 'MC', 'Transit & airport expansion', NULL),
    ('MC.3', 'MC', 'Sustainable transportation', NULL),
    ('MC.4', 'MC', 'Safe, resilient facilities', NULL),
    ('MC.5', 'MC', 'Utility infrastructure', NULL),
    ('PS.1', 'PS', 'Community relationships', NULL),
    ('PS.2', 'PS', 'Fair public safety delivery', NULL),
    ('PS.3', 'PS', 'Hazard & disaster partnerships', NULL);
```

### anchors

```sql
CREATE TABLE anchors (
    name TEXT PRIMARY KEY
);

INSERT INTO anchors VALUES
    ('Equity'),
    ('Affordability'),
    ('Innovation'),
    ('Sustainability & Resiliency'),
    ('Proactive Prevention'),
    ('Community Trust & Relationships');
```

### top25_priorities

```sql
CREATE TABLE top25_priorities (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    pillar_code TEXT REFERENCES pillars(code),
    description TEXT
);

-- Insert all 24 priorities...
```

---

## Views

### v_card_feed

Optimized view for the discovery feed.

```sql
CREATE VIEW v_card_feed AS
SELECT
    c.id,
    c.name,
    c.slug,
    c.summary,
    c.horizon,
    c.stage,
    c.pillars,
    c.velocity_score,
    c.follower_count,
    c.source_count,
    c.updated_at,
    COALESCE(
        (SELECT COUNT(*) FROM sources s
         WHERE s.card_id = c.id
         AND s.ingested_at > NOW() - INTERVAL '24 hours'),
        0
    ) AS new_sources_24h
FROM cards c
WHERE c.is_archived = FALSE
ORDER BY c.updated_at DESC;
```

### v_user_feed

User-specific feed based on workstreams.

```sql
CREATE VIEW v_user_feed AS
SELECT
    cf.id AS card_feed_id,
    cf.*,
    cf.user_id,
    cf.workstream_id,
    w.name AS workstream_name
FROM card_follows cf
JOIN v_card_feed vf ON vf.id = cf.card_id
LEFT JOIN workstreams w ON w.id = cf.workstream_id;
```

---

## Functions & Triggers

### Update follower count

```sql
CREATE OR REPLACE FUNCTION update_follower_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE cards SET follower_count = follower_count + 1
        WHERE id = NEW.card_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE cards SET follower_count = follower_count - 1
        WHERE id = OLD.card_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_follower_count
AFTER INSERT OR DELETE ON card_follows
FOR EACH ROW EXECUTE FUNCTION update_follower_count();
```

### Update source count

```sql
CREATE OR REPLACE FUNCTION update_source_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE cards SET source_count = source_count + 1
        WHERE id = NEW.card_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE cards SET source_count = source_count - 1
        WHERE id = OLD.card_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_source_count
AFTER INSERT OR DELETE ON sources
FOR EACH ROW EXECUTE FUNCTION update_source_count();
```

### Log timeline events

```sql
CREATE OR REPLACE FUNCTION log_card_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.stage != NEW.stage THEN
        INSERT INTO card_timeline (card_id, event_type, event_description, previous_value, new_value)
        VALUES (NEW.id, 'stage_change',
                'Stage changed from ' || OLD.stage || ' to ' || NEW.stage,
                jsonb_build_object('stage', OLD.stage),
                jsonb_build_object('stage', NEW.stage));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_card_timeline
AFTER UPDATE ON cards
FOR EACH ROW EXECUTE FUNCTION log_card_change();
```

---

## Row Level Security (RLS)

```sql
-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE workstreams ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_notes ENABLE ROW LEVEL SECURITY;

-- Users can read/update their own profile
CREATE POLICY users_own ON users
    FOR ALL USING (auth.uid() = id);

-- Workstreams are private to user
CREATE POLICY workstreams_own ON workstreams
    FOR ALL USING (auth.uid() = user_id);

-- Follows are private to user
CREATE POLICY follows_own ON card_follows
    FOR ALL USING (auth.uid() = user_id);

-- Notes: private notes only visible to owner, public notes visible to all
CREATE POLICY notes_read ON card_notes
    FOR SELECT USING (
        NOT is_private OR auth.uid() = user_id
    );

CREATE POLICY notes_write ON card_notes
    FOR ALL USING (auth.uid() = user_id);

-- Cards, sources, analyses are public read
-- (no RLS needed, or permissive policy)
```

---

_Document Version: 1.0_
_Last Updated: December 2024_
