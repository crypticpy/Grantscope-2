-- Migration: fix_pillar_codes
-- Created at: 1766739006
--
-- FIX-H4: Fix lossy pillar code mappings
--
-- Previously, the AI classification used 6 canonical pillar codes from Austin's
-- strategic framework (CH, EW, HG, HH, MC, PS), but the database only had 6
-- different codes (CH, MC, HS, EC, ES, CE). A lossy mapping was applied:
--
--   EW (Economic & Workforce)     -> EC (Economic Development)
--   HG (High-Performing Government) -> EC (Economic Development)  ** LOSSY **
--   HH (Homelessness & Housing)    -> HS (Housing Stability)
--   PS (Public Safety)             -> CH (Community Health)       ** LOSSY **
--
-- This migration adds the missing pillar codes so all 6 AI codes can be stored
-- natively without conversion. We cannot reliably reverse the lossy mappings
-- for existing data (we don't know which EC cards were originally HG, or which
-- CH cards were originally PS), so existing data remains as-is.

-- Add the 4 missing pillar codes that were previously mapped away
INSERT INTO pillars (id, name, description, color) VALUES
    ('EW', 'Economic & Workforce Development', 'Economic mobility, small business support, creative economy, and workforce development', '#8B5CF6'),
    ('HG', 'High-Performing Government', 'Fiscal integrity, technology modernization, government workforce, and community engagement', '#6366F1'),
    ('HH', 'Homelessness & Housing', 'Complete communities, affordable housing, and homelessness reduction', '#F59E0B'),
    ('PS', 'Public Safety', 'Community relationships, fair service delivery, and disaster preparedness', '#EF4444')
ON CONFLICT (id) DO NOTHING;

-- Add goals for the new pillar codes so cards classified under them have
-- valid goal foreign keys available.

-- Economic & Workforce Development goals
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
    ('EW-01', 'EW', 'Workforce Development', 'Prepare residents for emerging job opportunities through training and education', 1),
    ('EW-02', 'EW', 'Small Business Support', 'Strengthen support systems for small businesses and entrepreneurs', 2),
    ('EW-03', 'EW', 'Creative Economy', 'Foster and grow Austin''s creative and cultural economy', 3),
    ('EW-04', 'EW', 'Economic Mobility', 'Promote pathways to economic opportunity for all residents', 4)
ON CONFLICT (id) DO NOTHING;

-- High-Performing Government goals
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
    ('HG-01', 'HG', 'Fiscal Responsibility', 'Maintain strong fiscal management and transparency', 1),
    ('HG-02', 'HG', 'Technology Modernization', 'Modernize government technology and data capabilities', 2),
    ('HG-03', 'HG', 'Government Workforce', 'Attract, develop, and retain a high-performing workforce', 3),
    ('HG-04', 'HG', 'Community Engagement', 'Strengthen community engagement and public participation', 4)
ON CONFLICT (id) DO NOTHING;

-- Homelessness & Housing goals
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
    ('HH-01', 'HH', 'Affordable Housing', 'Increase supply of affordable housing units', 1),
    ('HH-02', 'HH', 'Homelessness Reduction', 'Reduce homelessness through comprehensive approaches', 2),
    ('HH-03', 'HH', 'Housing Quality', 'Improve quality and safety of existing housing stock', 3),
    ('HH-04', 'HH', 'Complete Communities', 'Build complete communities with access to services and amenities', 4)
ON CONFLICT (id) DO NOTHING;

-- Public Safety goals
INSERT INTO goals (id, pillar_id, name, description, sort_order) VALUES
    ('PS-01', 'PS', 'Community Relationships', 'Build trust and strong relationships between public safety and communities', 1),
    ('PS-02', 'PS', 'Fair Service Delivery', 'Ensure equitable and fair delivery of public safety services', 2),
    ('PS-03', 'PS', 'Disaster Preparedness', 'Strengthen disaster preparedness and emergency response capabilities', 3),
    ('PS-04', 'PS', 'Violence Prevention', 'Invest in violence prevention and intervention programs', 4)
ON CONFLICT (id) DO NOTHING;

-- NOTE: Existing cards with pillar_id = 'EC' may include cards that were
-- originally classified as 'HG' (High-Performing Government), and cards with
-- pillar_id = 'CH' may include cards originally classified as 'PS' (Public Safety).
-- Similarly, 'HS' cards may have been 'HH'. These cannot be automatically
-- corrected because the original AI classification was discarded during the
-- lossy mapping. Future discovery runs will correctly use all 6 pillar codes.
