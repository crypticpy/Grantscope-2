-- Migration: seed_domain_reputation
-- Created at: 1766739010
-- Task: 1.5 from DEV_PLAN_Information_Quality.md
--
-- PURPOSE:
--   Populates the domain_reputation table with curated seed data for 100+
--   known source domains. Each domain is assigned to a credibility tier,
--   organization name, and category based on the Domain Reputation Tier
--   Reference in the PRD (Section 10).
--
-- TIER DEFINITIONS:
--   Tier 1 (Authoritative, composite_score = 85):
--     Primary authoritative sources -- original research producers, government
--     agencies, and organizations whose data and analysis are the foundation
--     of municipal decision-making.
--
--   Tier 2 (Credible, composite_score = 60):
--     Well-respected organizations with strong track records in municipal/
--     government research, policy, and reporting.
--
--   Tier 3 (General, composite_score = 35):
--     Credible organizations producing relevant content, but either more
--     specialized, newer, or covering municipal topics as a secondary focus.
--
-- TEXAS RELEVANCE BONUS:
--   Texas-specific domains receive a +10 bonus added to composite_score,
--   boosting their visibility for Austin-focused strategic scanning.
--
-- SOURCE OF CURATED LIST:
--   PRD_Information_Quality_and_User_Generated_Content.md, Section 10:
--   "Domain Reputation Tier Reference" (Sections 10.2, 10.3, 10.4).
--
-- IDEMPOTENCY:
--   Uses INSERT ... ON CONFLICT (domain_pattern) DO NOTHING so this
--   migration can be re-run safely without duplicating rows.
--
-- DEPENDS ON:
--   - Migration 1766739001_domain_reputation.sql (table must exist)
--
-- ROLLBACK:
--   DELETE FROM domain_reputation WHERE curated_tier IS NOT NULL;
-- ============================================================================


-- ============================================================================
-- TIER 1: AUTHORITATIVE (composite_score = 85)
-- ============================================================================

-- --------------------------------------------------------------------------
-- Management Consulting & Advisory
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('gartner.com', 'Gartner', 'consulting', 1, 85, 0),
    ('mckinsey.com', 'McKinsey & Company', 'consulting', 1, 85, 0),
    ('deloitte.com', 'Deloitte Center for Government Insights', 'consulting', 1, 85, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Government Research & Advisory
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('rand.org', 'RAND Corporation', 'research', 1, 85, 0),
    ('brookings.edu', 'Brookings Institution', 'research', 1, 85, 0),
    ('urban.org', 'Urban Institute', 'research', 1, 85, 0),
    ('pewtrusts.org', 'Pew Charitable Trusts', 'research', 1, 85, 0),
    ('pewresearch.org', 'Pew Research Center', 'research', 1, 85, 0),
    ('nap.edu', 'National Academies Press', 'research', 1, 85, 0),
    ('lincolninst.edu', 'Lincoln Institute of Land Policy', 'research', 1, 85, 0),
    ('uli.org', 'Urban Land Institute', 'research', 1, 85, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Government Technology Media
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('govtech.com', 'Government Technology', 'gov_tech_media', 1, 85, 0),
    ('governing.com', 'Governing Magazine', 'gov_tech_media', 1, 85, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Academic Institutions (Tier 1 - named schools)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('*.harvard.edu', 'Harvard University', 'academic', 1, 85, 0),
    ('*.mit.edu', 'Massachusetts Institute of Technology', 'academic', 1, 85, 0),
    ('*.stanford.edu', 'Stanford University', 'academic', 1, 85, 0),
    ('*.berkeley.edu', 'UC Berkeley', 'academic', 1, 85, 0),
    ('*.utexas.edu', 'University of Texas at Austin', 'academic', 1, 85, 10)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Federal/State Government
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    -- Federal agencies (specific domains listed first for priority matching)
    ('gao.gov', 'U.S. Government Accountability Office', 'federal_state_gov', 1, 85, 0),
    ('cbo.gov', 'Congressional Budget Office', 'federal_state_gov', 1, 85, 0),
    ('bls.gov', 'Bureau of Labor Statistics', 'federal_state_gov', 1, 85, 0),
    ('census.gov', 'U.S. Census Bureau', 'federal_state_gov', 1, 85, 0),
    ('epa.gov', 'U.S. Environmental Protection Agency', 'federal_state_gov', 1, 85, 0),
    ('hud.gov', 'U.S. Dept. of Housing and Urban Development', 'federal_state_gov', 1, 85, 0),
    ('dot.gov', 'U.S. Department of Transportation', 'federal_state_gov', 1, 85, 0),
    ('fema.gov', 'Federal Emergency Management Agency', 'federal_state_gov', 1, 85, 0),
    ('crsreports.congress.gov', 'Congressional Research Service', 'federal_state_gov', 1, 85, 0),
    ('fhwa.dot.gov', 'Federal Highway Administration', 'federal_state_gov', 1, 85, 0),
    -- Texas state agencies
    ('texas.gov', 'State of Texas', 'federal_state_gov', 1, 85, 10),
    ('austintexas.gov', 'City of Austin', 'federal_state_gov', 1, 85, 10),
    ('txcourts.gov', 'Texas Courts', 'federal_state_gov', 1, 85, 10),
    ('twc.texas.gov', 'Texas Workforce Commission', 'federal_state_gov', 1, 85, 10),
    ('tceq.texas.gov', 'Texas Commission on Environmental Quality', 'federal_state_gov', 1, 85, 10),
    ('comptroller.texas.gov', 'Texas Comptroller of Public Accounts', 'federal_state_gov', 1, 85, 10),
    ('txdot.gov', 'Texas Department of Transportation', 'federal_state_gov', 1, 85, 10),
    -- Wildcard for all .gov domains not individually listed (lower priority matching)
    ('*.gov', 'U.S. Government (general)', 'federal_state_gov', 1, 85, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Municipal Innovation Networks (Tier 1)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('bloomberg.org', 'Bloomberg Philanthropies', 'innovation_network', 1, 85, 0),
    ('whatworkscities.bloomberg.org', 'What Works Cities (Bloomberg)', 'innovation_network', 1, 85, 0),
    ('bloombergcities.jhu.edu', 'Bloomberg Cities Network (JHU)', 'innovation_network', 1, 85, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Professional Associations (Tier 1)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('icma.org', 'International City/County Management Association', 'professional_association', 1, 85, 0),
    ('nlc.org', 'National League of Cities', 'professional_association', 1, 85, 0),
    ('usmayors.org', 'U.S. Conference of Mayors', 'professional_association', 1, 85, 0),
    ('gfoa.org', 'Government Finance Officers Association', 'professional_association', 1, 85, 0),
    ('planning.org', 'American Planning Association', 'professional_association', 1, 85, 0),
    ('nacto.org', 'National Association of City Transportation Officials', 'professional_association', 1, 85, 0),
    ('tml.org', 'Texas Municipal League', 'professional_association', 1, 85, 10)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- International (Tier 1)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('oecd.org', 'Organisation for Economic Co-operation and Development', 'international', 1, 85, 0)
ON CONFLICT (domain_pattern) DO NOTHING;


-- ============================================================================
-- TIER 2: CREDIBLE (composite_score = 60)
-- ============================================================================

-- --------------------------------------------------------------------------
-- Consulting (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('accenture.com', 'Accenture', 'consulting', 2, 60, 0),
    ('bcg.com', 'Boston Consulting Group', 'consulting', 2, 60, 0),
    ('pwc.com', 'PricewaterhouseCoopers', 'consulting', 2, 60, 0),
    ('kpmg.com', 'KPMG', 'consulting', 2, 60, 0),
    ('ey.com', 'Ernst & Young', 'consulting', 2, 60, 0),
    ('bain.com', 'Bain & Company', 'consulting', 2, 60, 0),
    ('forrester.com', 'Forrester Research', 'consulting', 2, 60, 0),
    ('idc.com', 'International Data Corporation', 'consulting', 2, 60, 0),
    ('guidehouse.com', 'Guidehouse', 'consulting', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Government Research (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('naco.org', 'National Association of Counties', 'research', 2, 60, 0),
    ('napawash.org', 'National Academy of Public Administration', 'research', 2, 60, 0),
    ('ncsl.org', 'National Conference of State Legislatures', 'research', 2, 60, 0),
    ('nga.org', 'National Governors Association', 'research', 2, 60, 0),
    ('csg.org', 'Council of State Governments', 'research', 2, 60, 0),
    ('results4america.org', 'Results for America', 'research', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Government Technology Media (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('statescoop.com', 'StateScoop', 'gov_tech_media', 2, 60, 0),
    ('route-fifty.com', 'Route Fifty', 'gov_tech_media', 2, 60, 0),
    ('routefifty.com', 'Route Fifty (alternate domain)', 'gov_tech_media', 2, 60, 0),
    ('fedscoop.com', 'FedScoop', 'gov_tech_media', 2, 60, 0),
    ('fcw.com', 'Federal Computer Week', 'gov_tech_media', 2, 60, 0),
    ('govexec.com', 'Government Executive', 'gov_tech_media', 2, 60, 0),
    ('gcn.com', 'Government Computer News', 'gov_tech_media', 2, 60, 0),
    ('smartcitiesdive.com', 'Smart Cities Dive', 'gov_tech_media', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Academic Institutions (Tier 2 - named schools)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('dusp.mit.edu', 'MIT Dept. of Urban Studies & Planning', 'academic', 2, 60, 0),
    ('beeckcenter.georgetown.edu', 'Georgetown Beeck Center', 'academic', 2, 60, 0),
    ('urbaninnovation.asu.edu', 'ASU Center for Urban Innovation', 'academic', 2, 60, 0),
    ('cuppa.uic.edu', 'UIC College of Urban Planning & Public Affairs', 'academic', 2, 60, 0),
    ('*.tamu.edu', 'Texas A&M University', 'academic', 2, 60, 10),
    ('*.uh.edu', 'University of Houston', 'academic', 2, 60, 10),
    -- General .edu wildcard (lowest priority matching for academic domains)
    ('*.edu', 'Academic Institution (general)', 'academic', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Federal Agencies (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('energy.gov', 'U.S. Department of Energy', 'federal_state_gov', 2, 60, 0),
    ('cisa.gov', 'Cybersecurity & Infrastructure Security Agency', 'federal_state_gov', 2, 60, 0),
    ('nist.gov', 'National Institute of Standards and Technology', 'federal_state_gov', 2, 60, 0),
    ('fcc.gov', 'Federal Communications Commission', 'federal_state_gov', 2, 60, 0),
    ('gov.texas.gov', 'Texas Governor''s Office', 'federal_state_gov', 2, 60, 10)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Professional Associations (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('apwa.org', 'American Public Works Association', 'professional_association', 2, 60, 0),
    ('awwa.org', 'American Water Works Association', 'professional_association', 2, 60, 0),
    ('theiacp.org', 'International Association of Chiefs of Police', 'professional_association', 2, 60, 0),
    ('nfpa.org', 'National Fire Protection Association', 'professional_association', 2, 60, 0),
    ('nascio.org', 'National Association of State CIOs', 'professional_association', 2, 60, 0),
    ('centerdigitalgov.com', 'Center for Digital Government', 'professional_association', 2, 60, 0),
    ('nrpa.org', 'National Recreation and Park Association', 'professional_association', 2, 60, 0),
    ('asce.org', 'American Society of Civil Engineers', 'professional_association', 2, 60, 0),
    ('aspa.org', 'American Society for Public Administration', 'professional_association', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Innovation Networks (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('bloombergcities.org', 'Bloomberg Cities (legacy domain)', 'innovation_network', 2, 60, 0),
    ('newurbanmechanics.org', 'New Urban Mechanics', 'innovation_network', 2, 60, 0),
    ('whatworkscities.com', 'What Works Cities', 'innovation_network', 2, 60, 0),
    ('cities-today.com', 'Cities Today', 'innovation_network', 2, 60, 0),
    ('smartcitiesworld.net', 'Smart Cities World', 'innovation_network', 2, 60, 0),
    ('codeforamerica.org', 'Code for America', 'innovation_network', 2, 60, 0),
    ('nesta.org.uk', 'Nesta', 'innovation_network', 2, 60, 0),
    ('smartgrowthamerica.org', 'Smart Growth America', 'innovation_network', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Think Tanks (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('newamerica.org', 'New America', 'think_tank', 2, 60, 0),
    ('volckeralliance.org', 'Volcker Alliance', 'think_tank', 2, 60, 0),
    ('milkeninstitute.org', 'Milken Institute', 'think_tank', 2, 60, 0),
    ('bipartisanpolicy.org', 'Bipartisan Policy Center', 'think_tank', 2, 60, 0),
    ('cbpp.org', 'Center on Budget and Policy Priorities', 'think_tank', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- International (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('weforum.org', 'World Economic Forum', 'international', 2, 60, 0),
    ('unhabitat.org', 'UN-Habitat', 'international', 2, 60, 0),
    ('worldbank.org', 'World Bank', 'international', 2, 60, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Texas-specific Media (Tier 2)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('texastribune.org', 'The Texas Tribune', 'gov_tech_media', 2, 60, 10)
ON CONFLICT (domain_pattern) DO NOTHING;


-- ============================================================================
-- TIER 3: GENERAL (composite_score = 35)
-- ============================================================================

-- --------------------------------------------------------------------------
-- Tech/Business Media
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('techcrunch.com', 'TechCrunch', 'tech_business_media', 3, 35, 0),
    ('wired.com', 'Wired', 'tech_business_media', 3, 35, 0),
    ('arstechnica.com', 'Ars Technica', 'tech_business_media', 3, 35, 0),
    ('theverge.com', 'The Verge', 'tech_business_media', 3, 35, 0),
    ('reuters.com', 'Reuters', 'tech_business_media', 3, 35, 0),
    ('bloomberg.com', 'Bloomberg News', 'tech_business_media', 3, 35, 0),
    ('ft.com', 'Financial Times', 'tech_business_media', 3, 35, 0),
    ('statetechmagazine.com', 'StateTech Magazine', 'tech_business_media', 3, 35, 0),
    ('cyberscoop.com', 'CyberScoop', 'tech_business_media', 3, 35, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Think Tanks (Tier 3)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('heritage.org', 'Heritage Foundation', 'think_tank', 3, 35, 0),
    ('cato.org', 'Cato Institute', 'think_tank', 3, 35, 0),
    ('aei.org', 'American Enterprise Institute', 'think_tank', 3, 35, 0),
    ('cfr.org', 'Council on Foreign Relations', 'think_tank', 3, 35, 0),
    ('carnegieendowment.org', 'Carnegie Endowment for International Peace', 'think_tank', 3, 35, 0),
    ('taxfoundation.org', 'Tax Foundation', 'think_tank', 3, 35, 0),
    ('reason.org', 'Reason Foundation', 'think_tank', 3, 35, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- International (Tier 3)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('undp.org', 'United Nations Development Programme', 'international', 3, 35, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Consulting (Tier 3)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('capgemini.com', 'Capgemini', 'consulting', 3, 35, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Academic (Tier 3 - named schools)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('cssh.northeastern.edu', 'Northeastern University CSSH', 'academic', 3, 35, 0),
    ('oneill.indiana.edu', 'Indiana University O''Neill School', 'academic', 3, 35, 0),
    ('penniur.upenn.edu', 'Penn Institute for Urban Research', 'academic', 3, 35, 0)
ON CONFLICT (domain_pattern) DO NOTHING;

-- --------------------------------------------------------------------------
-- Professional Associations (Tier 3)
-- --------------------------------------------------------------------------
INSERT INTO domain_reputation (domain_pattern, organization_name, category, curated_tier, composite_score, texas_relevance_bonus)
VALUES
    ('cnu.org', 'Congress for the New Urbanism', 'professional_association', 3, 35, 0),
    ('strongtowns.org', 'Strong Towns', 'professional_association', 3, 35, 0),
    ('enterprisecommunity.org', 'Enterprise Community Partners', 'professional_association', 3, 35, 0),
    ('texaspolicechiefs.org', 'Texas Police Chiefs Association', 'professional_association', 3, 35, 10),
    ('iafc.org', 'International Association of Fire Chiefs', 'professional_association', 3, 35, 0),
    ('nar.realtor', 'National Association of Realtors', 'professional_association', 3, 35, 0),
    ('uscm.org', 'U.S. Conference of Mayors (alternate)', 'professional_association', 3, 35, 0)
ON CONFLICT (domain_pattern) DO NOTHING;


-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Report counts by tier and category for validation
SELECT
    curated_tier,
    category,
    COUNT(*) AS domain_count,
    COUNT(*) FILTER (WHERE texas_relevance_bonus > 0) AS texas_specific_count
FROM domain_reputation
WHERE curated_tier IS NOT NULL
GROUP BY curated_tier, category
ORDER BY curated_tier, category;

SELECT
    'Seed data loaded: ' || COUNT(*) || ' domains ('
    || COUNT(*) FILTER (WHERE curated_tier = 1) || ' Tier 1, '
    || COUNT(*) FILTER (WHERE curated_tier = 2) || ' Tier 2, '
    || COUNT(*) FILTER (WHERE curated_tier = 3) || ' Tier 3, '
    || COUNT(*) FILTER (WHERE texas_relevance_bonus > 0) || ' Texas-specific)'
    AS status
FROM domain_reputation
WHERE curated_tier IS NOT NULL;
