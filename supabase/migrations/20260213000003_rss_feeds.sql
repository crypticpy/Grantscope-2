-- RSS Feed Monitoring tables
-- Phase 3, Layer 2.1

-- Feed subscriptions
CREATE TABLE IF NOT EXISTS rss_feeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'general',  -- gov_tech, municipal, academic, news, think_tank, tech, general
    pillar_id TEXT,  -- Optional: lock feed to a strategic pillar (CH, MC, HS, EC, ES, CE)
    check_interval_hours INTEGER DEFAULT 6 CHECK (check_interval_hours BETWEEN 1 AND 168),
    last_checked_at TIMESTAMPTZ,
    next_check_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'error', 'disabled')),
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    feed_title TEXT,  -- Title from the feed itself
    feed_link TEXT,   -- Homepage link from the feed
    articles_found_total INTEGER DEFAULT 0,
    articles_matched_total INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual feed items (articles)
CREATE TABLE IF NOT EXISTS rss_feed_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_id UUID NOT NULL REFERENCES rss_feeds(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    author TEXT,
    published_at TIMESTAMPTZ,
    content_hash TEXT,  -- For dedup within feed
    processed BOOLEAN DEFAULT FALSE,
    triage_result TEXT CHECK (triage_result IN ('matched', 'pending', 'irrelevant')),
    card_id UUID REFERENCES cards(id) ON DELETE SET NULL,  -- Matched signal card
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,  -- Created source record
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_rss_feeds_status ON rss_feeds(status);
CREATE INDEX IF NOT EXISTS idx_rss_feeds_next_check ON rss_feeds(next_check_at) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_rss_feed_items_url_feed ON rss_feed_items(feed_id, url);
CREATE INDEX IF NOT EXISTS idx_rss_feed_items_feed_id ON rss_feed_items(feed_id);
CREATE INDEX IF NOT EXISTS idx_rss_feed_items_processed ON rss_feed_items(processed) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_rss_feed_items_triage ON rss_feed_items(triage_result);

-- Seed with initial curated feeds
INSERT INTO rss_feeds (url, name, category) VALUES
    ('https://www.govtech.com/rss', 'GovTech', 'gov_tech'),
    ('https://statescoop.com/feed/', 'StateScoop', 'gov_tech'),
    ('https://fedscoop.com/feed/', 'FedScoop', 'gov_tech'),
    ('https://www.route-fifty.com/rss/all/', 'Route Fifty', 'gov_tech'),
    ('https://www.brookings.edu/feed/', 'Brookings Institution', 'think_tank'),
    ('https://www.pewtrusts.org/en/rss/all', 'Pew Trusts', 'think_tank'),
    ('https://www.nlc.org/feed/', 'National League of Cities', 'municipal'),
    ('https://icma.org/feed', 'ICMA', 'municipal'),
    ('https://www.nist.gov/news-events/news/rss.xml', 'NIST', 'gov_tech'),
    ('https://www.austintexas.gov/rss.xml', 'City of Austin', 'municipal')
ON CONFLICT (url) DO NOTHING;
