-- Migration: seed_top25_aligned_cards
-- Created at: 1766434800
-- Description: Adds cards that specifically align with CMO Top 25 priorities
-- Uses exact Top 25 priority titles for proper badge display

-- ============================================================================
-- CARD: AI-Powered Climate Risk Assessment for Bond Programs
-- Aligned with: 2026 Bond Program Development, Climate Revolving Fund
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'AI-Powered Climate Risk Assessment for Municipal Bonds',
    'ai-climate-risk-bond-assessment',
    'Machine learning models quantifying climate risks for infrastructure bond programs, enabling data-driven prioritization of resilience investments.',
    'Cities are increasingly using AI-powered climate risk assessment tools to inform bond program development and infrastructure prioritization. These platforms integrate climate projection data, asset condition assessments, and financial modeling to quantify risks to municipal infrastructure from flooding, extreme heat, and other climate hazards. The analysis informs which projects to prioritize in bond programs and helps structure climate resilience bonds with measurable outcomes. San Francisco, Miami-Dade, and Austin are among municipalities piloting these tools to ensure bond-funded projects address the most critical climate vulnerabilities while maximizing return on resilience investments.',
    'ES',
    'ES-01',
    'data_driven',
    '4_proof',
    'H2',
    82, 45, 92, 96, 78, 30, 90,
    '["2026 Bond Program Development", "Climate Revolving Fund"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '3 days',
    'active'
);

-- ============================================================================
-- CARD: Light Rail Autonomous Transit Integration
-- Aligned with: Light Rail Interlocal Agreement
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Light Rail Autonomous Transit Integration',
    'light-rail-autonomous-transit',
    'Next-generation light rail systems incorporating autonomous operation, real-time demand response, and multimodal integration hubs.',
    'Emerging light rail deployments are incorporating autonomous train operation (ATO) technologies that enable higher frequency service, reduced operating costs, and improved safety. Cities planning new light rail systems are designing for Grade of Automation 4 (fully automated) from the start, while existing systems are retrofitting ATO capabilities. These systems integrate with autonomous first/last mile shuttles and demand-responsive transit to create seamless multimodal networks. Phoenix, Austin, and Charlotte are evaluating ATO for new light rail corridors, with studies showing 15-25% operational cost reductions and capacity increases of up to 30% through optimized headways.',
    'MC',
    'MC-01',
    'innovation',
    '4_proof',
    'H2',
    85, 48, 94, 98, 82, 35, 92,
    '["Light Rail Interlocal Agreement"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '5 days',
    'active'
);

-- ============================================================================
-- CARD: Shared Services Digital Platform for Municipal Operations
-- Aligned with: Shared Services Implementation, Citywide Technology Strategic Plan
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Shared Services Digital Platform for Municipal Operations',
    'shared-services-digital-platform',
    'Cloud-based platforms enabling shared service delivery across municipal departments, reducing duplication and improving efficiency.',
    'Cities are deploying enterprise shared services platforms that consolidate common functions like HR, procurement, fleet management, and facilities across departments. Modern implementations leverage cloud infrastructure, AI-powered process automation, and self-service portals to dramatically reduce administrative overhead. Early adopters report 20-30% cost savings in shared functions while improving service quality and employee satisfaction. Austin, Denver, and Philadelphia are leading implementations that serve as models for other large municipalities seeking to modernize operations through digital transformation and shared services consolidation.',
    'EC',
    'EC-01',
    'data_driven',
    '5_implementing',
    'H1',
    72, 58, 88, 95, 75, 25, 88,
    '["Shared Services Implementation", "Citywide Technology Strategic Plan"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '7 days',
    'active'
);

-- ============================================================================
-- CARD: Mental Health Co-Response Technology Platforms
-- Aligned with: Austin FIRST EMS Mental Health Pilot, Comprehensive Crime Reduction Plan
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Mental Health Crisis Co-Response Technology Platforms',
    'mental-health-coresponse-technology',
    'Integrated dispatch and data systems enabling mental health professional co-response to 911 calls, reducing emergency department utilization and improving outcomes.',
    'Technology platforms enabling mental health crisis co-response are transforming how cities handle 911 calls involving behavioral health. These systems integrate CAD (Computer-Aided Dispatch) with clinical assessment tools, enabling dispatchers to route appropriate calls to mental health teams rather than police. Real-time data sharing between responders, crisis centers, and hospitals ensures continuity of care. Denver''s STAR program, Portland''s Street Response, and Austin''s FIRST pilot are demonstrating 60-70% reductions in emergency department utilization for diverted calls, with participants reporting higher satisfaction and better outcomes than traditional police response.',
    'CH',
    'CH-03',
    'equity',
    '5_implementing',
    'H1',
    78, 55, 92, 98, 85, 30, 94,
    '["Austin FIRST EMS Mental Health Pilot", "Comprehensive Crime Reduction Plan"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '2 days',
    'active'
);

-- ============================================================================
-- CARD: Modular Affordable Housing Construction Technology
-- Aligned with: 10-Year Housing Blueprint Update, AHFC 5-Year Strategic Plan, Rapid Rehousing Program Model
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Modular and 3D-Printed Affordable Housing',
    'modular-3d-printed-housing',
    'Factory-built modular units and 3D-printed structures cutting affordable housing construction time by 50% and costs by 30%.',
    'Modular construction and 3D printing technologies are accelerating affordable housing development while reducing costs. Factory-built modular units can be assembled on-site in weeks rather than months, with quality control advantages and reduced weather delays. 3D-printed homes using concrete extrusion are achieving costs under $200/sq ft with construction times measured in days. Housing authorities in Los Angeles, Austin, and Houston are partnering with modular builders for rapid deployment of permanent supportive housing and affordable units. These technologies are particularly valuable for rapid rehousing programs where speed is critical to reducing homelessness.',
    'HS',
    'HS-01',
    'innovation',
    '5_implementing',
    'H1',
    80, 52, 94, 96, 88, 25, 92,
    '["10-Year Housing Blueprint Update", "AHFC 5-Year Strategic Plan", "Rapid Rehousing Program Model"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '4 days',
    'active'
);

-- ============================================================================
-- CARD: AI-Powered Permit Review Automation
-- Aligned with: Expedited Site Plan Review Pilot, Development Code/Criteria Streamlining
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'AI-Powered Building Permit Review Automation',
    'ai-permit-review-automation',
    'Machine learning systems automatically reviewing building plans for code compliance, reducing review times from weeks to hours.',
    'Artificial intelligence is transforming building permit review by automatically analyzing submitted plans for code compliance. These systems use computer vision and rule-based AI to check dimensional requirements, setbacks, parking calculations, and accessibility compliance in minutes rather than weeks. Human reviewers focus on complex judgment calls while AI handles routine compliance verification. Jurisdictions piloting these systems report 40-60% reductions in review times for residential permits and significant staff productivity gains. San Jose, Las Vegas, and Austin are implementing AI review tools as part of broader development process streamlining initiatives.',
    'EC',
    'EC-01',
    'innovation',
    '4_proof',
    'H2',
    85, 42, 88, 96, 80, 28, 90,
    '["Expedited Site Plan Review Pilot", "Development Code/Criteria Streamlining"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '6 days',
    'active'
);

-- ============================================================================
-- CARD: Parks and Recreation Alternative Funding Models
-- Aligned with: Alternative Parks Funding Strategies
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Parks and Recreation Alternative Funding Models',
    'parks-alternative-funding-models',
    'Innovative financing mechanisms including conservation easements, health district partnerships, and carbon credit programs for parks.',
    'Cities are developing creative funding strategies for parks beyond traditional tax revenue. Health districts are co-investing in parks near underserved communities as preventive health infrastructure. Conservation easements and land trusts are preserving open space while generating tax benefits. Urban forestry programs are monetizing carbon sequestration through verified carbon credits. Corporate sponsorships and naming rights are funding amenity upgrades. These diversified revenue streams are helping cities expand and maintain parks systems despite budget constraints. Austin, Denver, and Seattle have pioneered multiple alternative funding approaches that other cities are now replicating.',
    'CH',
    'CH-04',
    'adaptive',
    '5_implementing',
    'H1',
    68, 55, 82, 94, 70, 22, 85,
    '["Alternative Parks Funding Strategies"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '8 days',
    'active'
);

-- ============================================================================
-- CARD: Airport Sustainable Aviation Fuel Infrastructure
-- Aligned with: Airline Use & Lease Agreement (Airport), AE Resiliency Plan
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Sustainable Aviation Fuel Airport Infrastructure',
    'sustainable-aviation-fuel-infrastructure',
    'Airport fuel systems adapting for sustainable aviation fuel (SAF) blending, enabling airline emissions reductions while maintaining compatibility.',
    'Airports are investing in infrastructure upgrades to support sustainable aviation fuel (SAF) distribution as airlines commit to emissions reductions. SAF, produced from waste feedstocks and renewable sources, can reduce lifecycle emissions 50-80% compared to conventional jet fuel. Airport fuel systems require modifications for SAF storage, blending, and quality assurance. Airlines are incorporating SAF availability into airport preference decisions and lease negotiations. Los Angeles, San Francisco, and Austin airports are leading SAF infrastructure investments, with the FAA providing grants for system upgrades. Industry projections suggest SAF could comprise 10% of jet fuel by 2030.',
    'MC',
    'MC-02',
    'innovation',
    '4_proof',
    'H2',
    78, 48, 86, 92, 75, 32, 88,
    '["Airline Use & Lease Agreement (Airport)", "AE Resiliency Plan"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '9 days',
    'active'
);

-- ============================================================================
-- CARD: IT Organizational Modernization and Cloud Migration
-- Aligned with: IT Organizational Alignment (Phase 1), Citywide Technology Strategic Plan
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Municipal IT Cloud Transformation Strategies',
    'municipal-it-cloud-transformation',
    'City IT departments migrating legacy systems to cloud platforms while reorganizing around product teams and DevSecOps practices.',
    'Cities are undertaking comprehensive IT transformations that combine cloud migration with organizational restructuring. Legacy on-premise systems are moving to FedRAMP-authorized cloud platforms, enabling scalability and disaster recovery improvements. IT organizations are shifting from siloed application teams to cross-functional product teams aligned with city services. DevSecOps practices are accelerating delivery while improving security posture. Change management and workforce reskilling are critical success factors. Boston, Austin, and San Diego are executing multi-year IT transformation programs that serve as models for other municipalities seeking to modernize technology operations.',
    'EC',
    'EC-02',
    'data_driven',
    '5_implementing',
    'H1',
    70, 60, 85, 95, 72, 30, 86,
    '["IT Organizational Alignment (Phase 1)", "Citywide Technology Strategic Plan"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '10 days',
    'active'
);

-- ============================================================================
-- CARD: Predictive Analytics for Public Safety Deployment
-- Aligned with: Comprehensive Crime Reduction Plan, Police OCM Plan (BerryDunn)
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Predictive Analytics for Evidence-Based Public Safety',
    'predictive-analytics-public-safety',
    'Data-driven deployment models using historical patterns to optimize patrol allocation and proactive intervention strategies.',
    'Police departments are implementing predictive analytics platforms that analyze historical crime data, environmental factors, and temporal patterns to inform resource deployment decisions. Unlike controversial predictive policing tools that target individuals, these systems focus on place-based predictions to guide patrol allocation and community engagement timing. Transparency dashboards allow public oversight of algorithmic recommendations. Departments are pairing analytics with organizational change management to ensure data-driven decision making becomes embedded in operations. Early adopters report 10-15% improvements in response times and measurable reductions in violent crime in focus areas when combined with community policing strategies.',
    'CH',
    'CH-05',
    'data_driven',
    '5_implementing',
    'H1',
    75, 55, 88, 94, 78, 40, 82,
    '["Comprehensive Crime Reduction Plan", "Police OCM Plan (BerryDunn)"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '11 days',
    'active'
);

-- ============================================================================
-- CARD: Economic Development Data Platforms
-- Aligned with: Economic Development Roadmap, First ACME Strategic Plan
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'Real-Time Economic Development Intelligence Platforms',
    'economic-development-intelligence',
    'Integrated data platforms tracking business formation, job creation, investment flows, and economic indicators for strategic decision-making.',
    'Cities are deploying comprehensive economic development intelligence platforms that integrate data from business registrations, commercial real estate, employment statistics, and permit activity. Real-time dashboards enable economic development staff to identify emerging industry clusters, track business expansion signals, and measure program effectiveness. AI-powered lead scoring helps prioritize business attraction and retention outreach. These platforms inform strategic planning, site selection assistance, and incentive program design. Austin, Nashville, and Charlotte are leading implementations that provide unprecedented visibility into local economic dynamics and enable more responsive, data-driven economic development strategies.',
    'EC',
    'EC-01',
    'data_driven',
    '4_proof',
    'H2',
    76, 48, 85, 94, 72, 25, 88,
    '["Economic Development Roadmap", "First ACME Strategic Plan"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '12 days',
    'active'
);

-- ============================================================================
-- CARD: Municipal Workforce Compensation Analytics
-- Aligned with: Phase 2 Compensation Recalibration
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at, status
) VALUES (
    gen_random_uuid(),
    'AI-Powered Municipal Compensation Analytics',
    'municipal-compensation-analytics',
    'Real-time labor market analytics platforms enabling continuous compensation benchmarking and equity analysis across job classifications.',
    'Cities are implementing sophisticated compensation analytics platforms that continuously benchmark municipal pay against regional labor markets. These AI-powered systems aggregate data from job postings, salary surveys, and economic indicators to identify emerging pay gaps before they affect recruitment and retention. Built-in pay equity analysis tools flag potential disparities across demographic groups and job families. Scenario modeling enables HR leaders to evaluate the cost and impact of various compensation strategies. Austin, Seattle, and Denver have deployed these tools to inform compensation recalibration initiatives and maintain competitive positioning in tight labor markets.',
    'EC',
    'EC-03',
    'data_driven',
    '4_proof',
    'H2',
    74, 45, 82, 92, 68, 22, 85,
    '["Phase 2 Compensation Recalibration"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW() - INTERVAL '14 days',
    'active'
);

-- ============================================================================
-- UPDATE EXISTING CARDS with proper Top 25 references
-- ============================================================================

-- Update Virtual Twin Cities to align with Imagine Austin Update
UPDATE cards
SET top25_relevance = '["Imagine Austin Update", "Citywide Technology Strategic Plan"]'::jsonb
WHERE slug = 'virtual-twin-cities-urban-planning';

-- Update Infrastructure Inspection Robots to align with Facility Condition Assessment
UPDATE cards
SET top25_relevance = '["Facility Condition Assessment Contract"]'::jsonb
WHERE slug = 'infrastructure-inspection-robots';

-- Update Climate Resilience Bonds to align with Climate Revolving Fund
UPDATE cards
SET top25_relevance = '["Climate Revolving Fund", "2026 Bond Program Development"]'::jsonb
WHERE slug = 'climate-resilience-bonds';

-- Update Municipal Broadband to align with IT and technology priorities
UPDATE cards
SET top25_relevance = '["Citywide Technology Strategic Plan"]'::jsonb
WHERE slug = 'municipal-broadband-digital-equity';

-- Update AI Adaptive Traffic Signals to align with MC priorities
UPDATE cards
SET top25_relevance = '["Light Rail Interlocal Agreement"]'::jsonb
WHERE slug = 'ai-adaptive-traffic-signals';

-- Update Predictive Policing Ethics to align with PS priorities
UPDATE cards
SET top25_relevance = '["Comprehensive Crime Reduction Plan", "Police OCM Plan (BerryDunn)"]'::jsonb
WHERE slug = 'predictive-policing-ai-ethics';

-- ============================================================================
-- ADD SOURCES FOR NEW CARDS
-- ============================================================================

-- Sources for AI Climate Risk Assessment
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Cities Use AI to Quantify Climate Risks for Bond Programs',
    'https://governing.com/finance/cities-ai-climate-risk-bond-programs',
    'Municipalities are deploying machine learning platforms to assess climate risks to infrastructure assets, informing bond program priorities and resilience investment decisions...',
    'Analysis of AI-powered climate risk assessment tools informing municipal bond programs.',
    'article',
    'Jennifer Walsh',
    'Governing Magazine',
    NOW() - INTERVAL '5 days',
    94
FROM cards c WHERE c.slug = 'ai-climate-risk-bond-assessment';

-- Sources for Light Rail Autonomous Transit
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Next-Generation Light Rail: Autonomous Operations and Multimodal Integration',
    'https://apta.com/research/autonomous-light-rail-2024',
    'American Public Transportation Association report on autonomous train operation technologies for light rail systems, including cost-benefit analysis and implementation considerations...',
    'Industry research on autonomous light rail operation technologies and benefits.',
    'report',
    'APTA Research',
    'American Public Transportation Association',
    NOW() - INTERVAL '8 days',
    92
FROM cards c WHERE c.slug = 'light-rail-autonomous-transit';

-- Sources for Mental Health Co-Response
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Mental Health Crisis Co-Response Programs Show Dramatic Results',
    'https://vera.org/publications/mental-health-crisis-response-evaluation',
    'Comprehensive evaluation of mental health co-response programs in Denver, Portland, and other cities, documenting 60-70% reductions in emergency department utilization...',
    'Research evaluation of mental health co-response program outcomes.',
    'report',
    'Vera Institute of Justice',
    'Vera Institute',
    NOW() - INTERVAL '4 days',
    96
FROM cards c WHERE c.slug = 'mental-health-coresponse-technology';

-- Sources for Modular Housing
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Modular Construction Accelerates Affordable Housing Development',
    'https://nlihc.org/resource/modular-construction-affordable-housing',
    'National Low Income Housing Coalition analysis of modular and prefabricated construction for affordable housing, documenting cost and time savings...',
    'Analysis of modular construction benefits for affordable housing development.',
    'report',
    'National Low Income Housing Coalition',
    'NLIHC',
    NOW() - INTERVAL '6 days',
    90
FROM cards c WHERE c.slug = 'modular-3d-printed-housing';

-- Sources for AI Permit Review
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'AI Permit Review Cuts Processing Times by Half',
    'https://buildingintelligence.com/ai-permit-review-municipal-adoption',
    'Survey of municipalities implementing AI-powered permit review systems, with case studies showing 40-60% reductions in review times...',
    'Industry survey of AI permit review adoption and outcomes.',
    'article',
    'Building Intelligence Staff',
    'Building Intelligence',
    NOW() - INTERVAL '9 days',
    88
FROM cards c WHERE c.slug = 'ai-permit-review-automation';

-- ============================================================================
-- ADD TIMELINE EVENTS FOR NEW CARDS
-- ============================================================================

INSERT INTO card_timeline (card_id, event_type, title, description, created_by)
SELECT
    c.id,
    'created',
    'Card created via Top 25 priority alignment research',
    'Intelligence card generated to track emerging trends aligned with CMO Top 25 priorities',
    (SELECT id FROM auth.users LIMIT 1)
FROM cards c
WHERE c.slug IN (
    'ai-climate-risk-bond-assessment',
    'light-rail-autonomous-transit',
    'shared-services-digital-platform',
    'mental-health-coresponse-technology',
    'modular-3d-printed-housing',
    'ai-permit-review-automation',
    'parks-alternative-funding-models',
    'sustainable-aviation-fuel-infrastructure',
    'municipal-it-cloud-transformation',
    'predictive-analytics-public-safety',
    'economic-development-intelligence',
    'municipal-compensation-analytics'
);
