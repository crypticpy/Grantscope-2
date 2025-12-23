-- Migration: populate_reference_data
-- Created at: 1766434584

-- Insert Austin Strategic Pillars (6 total)
INSERT INTO pillars (id, name, description, color) VALUES
('CH', 'Community Health', 'Promoting physical, mental, and social well-being for all Austinites', '#10B981'),
('MC', 'Mobility & Connectivity', 'Ensuring accessible, sustainable, and efficient transportation options', '#3B82F6'),
('HS', 'Housing & Economic Stability', 'Creating affordable housing and economic opportunities', '#F59E0B'),
('EC', 'Economic Development', 'Fostering innovation, entrepreneurship, and business growth', '#8B5CF6'),
('ES', 'Environmental Sustainability', 'Protecting and enhancing Austin''s natural environment', '#059669'),
('CE', 'Cultural & Entertainment', 'Preserving Austin''s unique culture and creative economy', '#EF4444');

-- Insert Goals under each pillar (23 total)
-- Community Health (5 goals)
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
('CH-01', 'CH', 'Health Equity', 'Eliminate health disparities and ensure equal access to health services', 1),
('CH-02', 'CH', 'Preventive Health', 'Focus on prevention and early intervention to improve health outcomes', 2),
('CH-03', 'CH', 'Mental Health Support', 'Expand access to mental health resources and reduce stigma', 3),
('CH-04', 'CH', 'Healthy Environments', 'Create environments that support physical activity and healthy living', 4),
('CH-05', 'CH', 'Public Health Emergency Response', 'Strengthen preparedness for health emergencies and disasters', 5);

-- Mobility & Connectivity (4 goals)
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
('MC-01', 'MC', 'Transit Accessibility', 'Improve public transportation access for all residents', 1),
('MC-02', 'MC', 'Active Transportation', 'Expand bike lanes, sidewalks, and pedestrian infrastructure', 2),
('MC-03', 'MC', 'Traffic Management', 'Reduce congestion and improve traffic flow', 3),
('MC-04', 'MC', 'Technology Integration', 'Leverage smart technology for transportation solutions', 4);

-- Housing & Economic Stability (4 goals)
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
('HS-01', 'HS', 'Affordable Housing', 'Increase supply of affordable housing units', 1),
('HS-02', 'HS', 'Housing Quality', 'Improve quality and safety of existing housing', 2),
('HS-03', 'HS', 'Economic Mobility', 'Support pathways to economic opportunity', 3),
('HS-04', 'HS', 'Homelessness Solutions', 'Reduce homelessness through comprehensive approaches', 4);

-- Economic Development (4 goals)
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
('EC-01', 'EC', 'Business Growth', 'Support local business development and retention', 1),
('EC-02', 'EC', 'Innovation Ecosystem', 'Foster technology innovation and entrepreneurship', 2),
('EC-03', 'EC', 'Workforce Development', 'Prepare residents for emerging job opportunities', 3),
('EC-04', 'EC', 'Economic Resilience', 'Build economic resilience against external shocks', 4);

-- Environmental Sustainability (3 goals)
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
('ES-01', 'ES', 'Climate Action', 'Reduce greenhouse gas emissions and adapt to climate change', 1),
('ES-02', 'ES', 'Resource Conservation', 'Promote efficient use of water, energy, and materials', 2),
('ES-03', 'ES', 'Green Infrastructure', 'Develop green infrastructure and protect natural resources', 3);

-- Cultural & Entertainment (3 goals)
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
('CE-01', 'CE', 'Arts & Culture', 'Support local arts and preserve Austin''s cultural identity', 1),
('CE-02', 'CE', 'Entertainment Industry', 'Maintain Austin''s position as a premier entertainment destination', 2),
('CE-03', 'CE', 'Public Spaces', 'Create vibrant public spaces for community gathering', 3);

-- Insert Anchors (6 total)
INSERT INTO anchors (id, name, description, color) VALUES
('equity', 'Equity', 'Ensuring fair treatment and access for all residents', '#DC2626'),
('innovation', 'Innovation', 'Embracing new technologies and creative solutions', '#7C3AED'),
('prevention', 'Proactive Prevention', 'Focusing on prevention rather than reaction', '#059669'),
('data_driven', 'Data-Driven Decision Making', 'Using evidence and analytics to guide decisions', '#2563EB'),
('adaptive', 'Adaptive & Resilient Governance', 'Building capacity to adapt to change', '#EA580C'),
('collaboration', 'Collaboration & Partnership', 'Working together across sectors and communities', '#0891B2');

-- Insert Maturity Stages (8 total)
INSERT INTO stages (id, name, description, sort_order) VALUES
('1_concept', '1 - Concept', 'Early idea or observation, minimal evidence', 1),
('2_exploring', '2 - Exploring', 'Initial research and experimentation', 2),
('3_pilot', '3 - Pilot', 'Small-scale testing and validation', 3),
('4_proof', '4 - Proof of Concept', 'Demonstrated viability with evidence', 4),
('5_implementing', '5 - Implementing', 'Full-scale deployment underway', 5),
('6_scaling', '6 - Scaling', 'Expanding reach and impact', 6),
('7_mature', '7 - Mature', 'Established and widely adopted', 7),
('8_declining', '8 - Declining', 'Losing relevance or being replaced', 8);;