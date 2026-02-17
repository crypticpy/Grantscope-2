-- Migration: grant_schema
-- Created at: 20260216000002
-- Purpose: Add grant discovery tables and columns to transform GrantScope2 from
--          a horizon scanning system into a grant discovery platform.
--          All changes are ADDITIVE — no existing columns dropped or renamed.

-- ============================================================================
-- 1. REFERENCE TABLES: grant_categories, departments
-- ============================================================================

-- Grant funding categories (8 categories aligned to City of Austin domains)
CREATE TABLE IF NOT EXISTS grant_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT,
    icon TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE grant_categories IS 'Eight grant funding categories aligned to City of Austin strategic domains';
COMMENT ON COLUMN grant_categories.id IS 'Short code (e.g. HS, PS, HD) used as primary key';
COMMENT ON COLUMN grant_categories.color IS 'Hex color for UI rendering';
COMMENT ON COLUMN grant_categories.icon IS 'Lucide icon name for UI rendering';

-- City of Austin departments (43 departments)
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    abbreviation TEXT NOT NULL UNIQUE,
    category_ids TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE departments IS 'City of Austin departments (43 total). ID is the department abbreviation.';
COMMENT ON COLUMN departments.category_ids IS 'Array of grant_categories.id values this department is associated with';

-- ============================================================================
-- 2. GRANT APPLICATION TRACKING TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS grant_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID NOT NULL REFERENCES cards(id),
    workstream_id UUID NOT NULL REFERENCES workstreams(id),
    department_id TEXT REFERENCES departments(id),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    status TEXT DEFAULT 'draft' CHECK (status IN (
        'draft', 'in_progress', 'submitted', 'awarded', 'declined', 'withdrawn'
    )),
    proposal_content JSONB DEFAULT '{}',
    awarded_amount NUMERIC,
    submitted_at TIMESTAMPTZ,
    decision_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE grant_applications IS 'Tracks grant applications from draft through award/decline lifecycle';
COMMENT ON COLUMN grant_applications.card_id IS 'The grant opportunity card this application is for';
COMMENT ON COLUMN grant_applications.workstream_id IS 'The workstream (grant program) managing this application';
COMMENT ON COLUMN grant_applications.proposal_content IS 'Structured proposal data as JSON (sections, drafts, attachments metadata)';
COMMENT ON COLUMN grant_applications.awarded_amount IS 'Final awarded amount (NULL until awarded)';

-- ============================================================================
-- 3. ALTER cards TABLE — Grant-specific columns
-- ============================================================================

-- Grant classification
ALTER TABLE cards ADD COLUMN IF NOT EXISTS grant_type TEXT
    CHECK (grant_type IN ('federal', 'state', 'foundation', 'local', 'other'));

-- Funding range
ALTER TABLE cards ADD COLUMN IF NOT EXISTS funding_amount_min NUMERIC;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS funding_amount_max NUMERIC;

-- Deadline and grantor
ALTER TABLE cards ADD COLUMN IF NOT EXISTS deadline TIMESTAMPTZ;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS grantor TEXT;

-- Federal grant identifiers
ALTER TABLE cards ADD COLUMN IF NOT EXISTS cfda_number TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS grants_gov_id TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS sam_opportunity_id TEXT;

-- Eligibility and matching
ALTER TABLE cards ADD COLUMN IF NOT EXISTS eligibility_text TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS match_requirement TEXT;

-- Category link
ALTER TABLE cards ADD COLUMN IF NOT EXISTS category_id TEXT REFERENCES grant_categories(id);

-- Source URL for the original grant listing
ALTER TABLE cards ADD COLUMN IF NOT EXISTS source_url TEXT;

-- Grant-specific AI scores (0-100)
ALTER TABLE cards ADD COLUMN IF NOT EXISTS alignment_score INTEGER
    CHECK (alignment_score BETWEEN 0 AND 100);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS readiness_score INTEGER
    CHECK (readiness_score BETWEEN 0 AND 100);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS competition_score INTEGER
    CHECK (competition_score BETWEEN 0 AND 100);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS urgency_score INTEGER
    CHECK (urgency_score BETWEEN 0 AND 100);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS probability_score INTEGER
    CHECK (probability_score BETWEEN 0 AND 100);

COMMENT ON COLUMN cards.grant_type IS 'Grant funding source type: federal, state, foundation, local, other';
COMMENT ON COLUMN cards.funding_amount_min IS 'Minimum available funding amount in USD';
COMMENT ON COLUMN cards.funding_amount_max IS 'Maximum available funding amount in USD';
COMMENT ON COLUMN cards.deadline IS 'Application deadline for the grant opportunity';
COMMENT ON COLUMN cards.grantor IS 'Name of the granting organization or agency';
COMMENT ON COLUMN cards.cfda_number IS 'Catalog of Federal Domestic Assistance number';
COMMENT ON COLUMN cards.grants_gov_id IS 'Grants.gov opportunity identifier';
COMMENT ON COLUMN cards.sam_opportunity_id IS 'SAM.gov opportunity identifier';
COMMENT ON COLUMN cards.eligibility_text IS 'Raw eligibility criteria text from the grant listing';
COMMENT ON COLUMN cards.match_requirement IS 'Match/cost-share requirements description';
COMMENT ON COLUMN cards.category_id IS 'FK to grant_categories for thematic classification';
COMMENT ON COLUMN cards.source_url IS 'Original URL of the grant listing or announcement';
COMMENT ON COLUMN cards.alignment_score IS 'AI score: how well this grant aligns with city priorities (0-100)';
COMMENT ON COLUMN cards.readiness_score IS 'AI score: how ready the city is to apply (0-100)';
COMMENT ON COLUMN cards.competition_score IS 'AI score: estimated competitiveness / likelihood of award (0-100)';
COMMENT ON COLUMN cards.urgency_score IS 'AI score: time-sensitivity based on deadline proximity (0-100)';
COMMENT ON COLUMN cards.probability_score IS 'AI score: composite probability of successful award (0-100)';

-- ============================================================================
-- 4. ALTER workstreams TABLE — Grant program columns
-- ============================================================================

ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS program_type TEXT;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS department_id TEXT REFERENCES departments(id);
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS budget NUMERIC;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS fiscal_year TEXT;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS total_awarded NUMERIC DEFAULT 0;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS total_pending NUMERIC DEFAULT 0;
ALTER TABLE workstreams ADD COLUMN IF NOT EXISTS category_ids TEXT[] DEFAULT '{}';

COMMENT ON COLUMN workstreams.program_type IS 'Type of grant program this workstream represents';
COMMENT ON COLUMN workstreams.department_id IS 'City department that owns this grant workstream';
COMMENT ON COLUMN workstreams.budget IS 'Budget allocation for this grant program';
COMMENT ON COLUMN workstreams.fiscal_year IS 'Fiscal year this workstream is associated with (e.g. FY2026)';
COMMENT ON COLUMN workstreams.total_awarded IS 'Running total of awarded grant amounts in this workstream';
COMMENT ON COLUMN workstreams.total_pending IS 'Running total of pending application amounts in this workstream';
COMMENT ON COLUMN workstreams.category_ids IS 'Array of grant_categories.id values for filtering';

-- ============================================================================
-- 5. ALTER users TABLE — Department and title
-- ============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS department_id TEXT REFERENCES departments(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS title TEXT;

COMMENT ON COLUMN users.department_id IS 'FK to departments table for structured department assignment';
COMMENT ON COLUMN users.title IS 'Job title within the department';

-- ============================================================================
-- 6. EXPAND workstream_cards STATUS CHECK CONSTRAINT
-- ============================================================================

-- The status column was added in 1766437000_workstream_kanban.sql with an inline
-- CHECK constraint. PostgreSQL names inline CHECK constraints as
-- "<table>_<column>_check". We drop the old one and add a new one that includes
-- both the original kanban statuses and the new grant-lifecycle statuses.
DO $$
BEGIN
    -- Drop the existing constraint (may be named workstream_cards_status_check)
    ALTER TABLE workstream_cards DROP CONSTRAINT IF EXISTS workstream_cards_status_check;

    -- Add the expanded constraint with all old + new values
    ALTER TABLE workstream_cards ADD CONSTRAINT workstream_cards_status_check
        CHECK (status IN (
            -- Original kanban statuses
            'inbox', 'screening', 'research', 'brief', 'watching', 'archived',
            -- New grant-lifecycle statuses
            'discovered', 'evaluating', 'applying', 'submitted', 'awarded', 'declined', 'expired'
        ));
END $$;

COMMENT ON COLUMN workstream_cards.status IS 'Card status in workstream. Kanban: inbox, screening, research, brief, watching, archived. Grant lifecycle: discovered, evaluating, applying, submitted, awarded, declined, expired';

-- ============================================================================
-- 7. ROW LEVEL SECURITY
-- ============================================================================

-- departments: read-only reference data for authenticated users
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view departments"
    ON departments FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access to departments"
    ON departments FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- grant_categories: read-only reference data for authenticated users
ALTER TABLE grant_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view grant_categories"
    ON grant_categories FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Service role full access to grant_categories"
    ON grant_categories FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- grant_applications: users manage their own, service_role sees all
ALTER TABLE grant_applications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own grant_applications"
    ON grant_applications FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own grant_applications"
    ON grant_applications FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own grant_applications"
    ON grant_applications FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own grant_applications"
    ON grant_applications FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access to grant_applications"
    ON grant_applications FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- 8. INDEXES
-- ============================================================================

-- Cards: grant-specific indexes
CREATE INDEX IF NOT EXISTS idx_cards_deadline
    ON cards(deadline) WHERE deadline IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cards_grants_gov_id
    ON cards(grants_gov_id) WHERE grants_gov_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cards_sam_opportunity_id
    ON cards(sam_opportunity_id) WHERE sam_opportunity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cards_category_id
    ON cards(category_id);

CREATE INDEX IF NOT EXISTS idx_cards_grant_type
    ON cards(grant_type) WHERE grant_type IS NOT NULL;

-- Grant applications indexes
CREATE INDEX IF NOT EXISTS idx_grant_applications_card_id
    ON grant_applications(card_id);

CREATE INDEX IF NOT EXISTS idx_grant_applications_workstream_id
    ON grant_applications(workstream_id);

CREATE INDEX IF NOT EXISTS idx_grant_applications_user_id
    ON grant_applications(user_id);

CREATE INDEX IF NOT EXISTS idx_grant_applications_status
    ON grant_applications(status);

-- Workstreams: department lookup
CREATE INDEX IF NOT EXISTS idx_workstreams_department_id
    ON workstreams(department_id);

-- Users: department lookup
CREATE INDEX IF NOT EXISTS idx_users_department_id
    ON users(department_id) WHERE department_id IS NOT NULL;

-- ============================================================================
-- 9. TRIGGERS
-- ============================================================================

-- Reuse existing update_updated_at() function for grant_applications
DROP TRIGGER IF EXISTS trigger_grant_applications_updated_at ON grant_applications;

CREATE TRIGGER trigger_grant_applications_updated_at
    BEFORE UPDATE ON grant_applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- 10. SEED DATA: grant_categories
-- ============================================================================

INSERT INTO grant_categories (id, name, description, color, icon) VALUES
    ('HS', 'Health & Social Services', 'Public health, behavioral health, social services, youth development', '#22c55e', 'heart-pulse'),
    ('PS', 'Public Safety', 'Law enforcement, fire, EMS, emergency management, justice', '#ef4444', 'shield'),
    ('HD', 'Housing & Development', 'Affordable housing, homelessness, community development, planning', '#ec4899', 'home'),
    ('IN', 'Infrastructure', 'Transportation, water, energy, facilities, telecommunications', '#f59e0b', 'building-2'),
    ('EN', 'Environment', 'Climate, sustainability, parks, conservation, resilience', '#10b981', 'leaf'),
    ('CE', 'Culture & Education', 'Libraries, museums, arts, education, workforce development', '#8b5cf6', 'graduation-cap'),
    ('TG', 'Technology & Government', 'IT modernization, data, cybersecurity, innovation, e-government', '#3b82f6', 'cpu'),
    ('EQ', 'Equity & Engagement', 'Civil rights, accessibility, language access, civic participation', '#f97316', 'users')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- 11. SEED DATA: departments (43 City of Austin departments)
-- ============================================================================

INSERT INTO departments (id, name, abbreviation, category_ids, is_active) VALUES
    ('APH',  'Austin Public Health',                       'APH',   ARRAY['HS'],           true),
    ('APD',  'Austin Police Department',                   'APD',   ARRAY['PS'],           true),
    ('AFD',  'Austin Fire Department',                     'AFD',   ARRAY['PS'],           true),
    ('EMS',  'Austin-Travis County EMS',                   'EMS',   ARRAY['PS'],           true),
    ('HSEM', 'Homeland Security & Emergency Management',   'HSEM',  ARRAY['PS'],           true),
    ('AWU',  'Austin Water',                               'AWU',   ARRAY['IN', 'EN'],     true),
    ('ATD',  'Austin Transportation',                      'ATD',   ARRAY['IN'],           true),
    ('AE',   'Austin Energy',                              'AE',    ARRAY['IN', 'EN'],     true),
    ('ARR',  'Austin Resource Recovery',                   'ARR',   ARRAY['EN', 'IN'],     true),
    ('PARD', 'Parks & Recreation',                         'PARD',  ARRAY['EN', 'CE'],     true),
    ('APL',  'Austin Public Library',                      'APL',   ARRAY['CE'],           true),
    ('EDD',  'Economic Development',                       'EDD',   ARRAY['CE', 'HD'],     true),
    ('NHCD', 'Housing & Planning',                         'NHCD',  ARRAY['HD'],           true),
    ('DSD',  'Development Services',                       'DSD',   ARRAY['HD', 'IN'],     true),
    ('WPD',  'Watershed Protection',                       'WPD',   ARRAY['EN'],           true),
    ('CTM',  'Communications & Technology Management',     'CTM',   ARRAY['TG'],           true),
    ('OOI',  'Office of Innovation',                       'OOI',   ARRAY['TG'],           true),
    ('FSD',  'Financial Services',                         'FSD',   ARRAY['TG'],           true),
    ('HRD',  'Human Resources',                            'HRD',   ARRAY['TG'],           true),
    ('LAW',  'Law Department',                             'LAW',   ARRAY['TG'],           true),
    ('CMO',  'City Manager Office',                        'CMO',   ARRAY['TG', 'EQ'],     true),
    ('OPM',  'Office of Performance Management',           'OPM',   ARRAY['TG'],           true),
    ('CCC',  'Combined Communications Center (911)',       'CCC',   ARRAY['PS', 'TG'],     true),
    ('BSD',  'Building Services',                          'BSD',   ARRAY['IN'],           true),
    ('FMD',  'Fleet Mobility Services',                    'FMD',   ARRAY['IN'],           true),
    ('PWD',  'Public Works',                               'PWD',   ARRAY['IN'],           true),
    ('AAR',  'Aviation',                                   'AAR',   ARRAY['IN'],           true),
    ('OEQ',  'Office of Equity',                           'OEQ',   ARRAY['EQ'],           true),
    ('OII',  'Office of Immigrant Integration',            'OII',   ARRAY['EQ'],           true),
    ('CRA',  'Civil Rights Office',                        'CRA',   ARRAY['EQ'],           true),
    ('ODA',  'Office of Disability Affairs',               'ODA',   ARRAY['EQ', 'HS'],     true),
    ('CPIO', 'Communications & Public Information',        'CPIO',  ARRAY['TG'],           true),
    ('COS',  'Office of Sustainability',                   'COS',   ARRAY['EN'],           true),
    ('CC',   'Austin Convention Center',                   'CC',    ARRAY['CE'],           true),
    ('MOS',  'Municipal Court',                            'MOS',   ARRAY['PS'],           true),
    ('ACD',  'Animal Services',                            'ACD',   ARRAY['HS'],           true),
    ('COA311', '311 / Austin 3-1-1',                       'COA311', ARRAY['TG', 'EQ'],    true),
    ('OSPB', 'Office of Small & Minority Business',        'OSPB',  ARRAY['EQ', 'CE'],     true),
    ('CPTD', 'Capital Planning & Transportation',          'CPTD',  ARRAY['IN'],           true),
    ('OCOS', 'Office of the City Clerk',                   'OCOS',  ARRAY['TG'],           true),
    ('IAO',  'Internal Audit Office',                      'IAO',   ARRAY['TG'],           true),
    ('FPD',  'Financial Policy Division',                  'FPD',   ARRAY['TG'],           true),
    ('CRO',  'Community Registry Office',                  'CRO',   ARRAY['EQ'],           true)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- 12. VERIFICATION
-- ============================================================================

SELECT 'grant_categories' AS table_name, COUNT(*) AS row_count FROM grant_categories
UNION ALL
SELECT 'departments', COUNT(*) FROM departments
UNION ALL
SELECT 'grant_applications', COUNT(*) FROM grant_applications;
