-- Migration: seed_sample_data
-- Created at: 1766434603

-- Create sample cards for testing
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    created_by, created_at
) VALUES 
(
    gen_random_uuid(),
    'AI-Powered Traffic Management',
    'ai-powered-traffic-management',
    'Cities implementing AI systems to optimize traffic flow in real-time, reducing congestion by up to 40% and improving air quality.',
    'Advanced traffic management systems using machine learning to analyze traffic patterns, adjust signal timing, and predict congestion before it occurs.',
    'MC',
    'MC-03',
    'innovation',
    '4_proof',
    'H2',
    85, 45, 75, 90, 80, 20, 85,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
),
(
    gen_random_uuid(),
    'Digital Equity Programs',
    'digital-equity-programs',
    'Municipal programs providing internet access and digital literacy training to underserved communities, improving access to government services.',
    'Comprehensive digital inclusion initiatives including free WiFi zones, device lending programs, and community tech centers.',
    'CH',
    'CH-01',
    'equity',
    '5_implementing',
    'H1',
    65, 75, 85, 95, 70, 15, 90,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
),
(
    gen_random_uuid(),
    'Predictive Public Safety Analytics',
    'predictive-public-safety-analytics',
    'Machine learning models helping police departments anticipate high-risk areas and allocate resources more effectively.',
    'Data-driven approaches to public safety using historical crime data, environmental factors, and real-time analytics for proactive resource deployment.',
    'CH',
    'CH-05',
    'data_driven',
    '3_pilot',
    'H2',
    90, 35, 80, 75, 85, 60, 70,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
),
(
    gen_random_uuid(),
    'Green Infrastructure Networks',
    'green-infrastructure-networks',
    'Urban planning approach using natural systems like green roofs, rain gardens, and permeable surfaces to manage stormwater and reduce urban heat.',
    'Integrated network of natural and engineered systems that provide environmental benefits while addressing urban infrastructure challenges.',
    'ES',
    'ES-03',
    'prevention',
    '4_proof',
    'H2',
    70, 50, 90, 85, 75, 25, 95,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
),
(
    gen_random_uuid(),
    'Remote Work Economic Impact',
    'remote-work-economic-impact',
    'Long-term economic implications of widespread remote work on municipal tax revenue, commercial real estate, and urban development patterns.',
    'Analysis of how permanent shift to remote work affects city budgets, infrastructure needs, and economic development strategies.',
    'EC',
    'EC-04',
    'adaptive',
    '2_exploring',
    'H3',
    95, 20, 95, 80, 90, 80, 85,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- Add sample sources for each card
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT 
    c.id,
    'AI Traffic Systems Show 40% Efficiency Gains in European Cities',
    'https://example.com/ai-traffic-study',
    'European cities using AI-powered traffic management have achieved significant improvements in traffic flow and reduced emissions...',
    'Study shows AI traffic management systems can reduce congestion by 40% while improving air quality.',
    'article',
    'Dr. Sarah Johnson',
    'MIT Technology Review',
    NOW() - INTERVAL '2 days',
    85
FROM cards c WHERE c.slug = 'ai-powered-traffic-management';

INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT 
    c.id,
    'Digital Inclusion Programs Bridge Municipal Service Gaps',
    'https://example.com/digital-inclusion',
    'Cities implementing comprehensive digital inclusion programs report improved access to government services...',
    'Digital equity initiatives successfully reduce barriers to municipal services for underserved communities.',
    'article',
    'Maria Rodriguez',
    'Government Technology',
    NOW() - INTERVAL '1 day',
    90
FROM cards c WHERE c.slug = 'digital-equity-programs';

-- Add timeline events
INSERT INTO card_timeline (card_id, event_type, title, description, created_by)
SELECT 
    c.id,
    'created',
    'Card created via AI analysis',
    'Initial card generated from news analysis and relevance scoring',
    (SELECT id FROM auth.users LIMIT 1)
FROM cards c;

-- Add sample user follows (if we have a user)
-- This will be populated when users actually use the system;