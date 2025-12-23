-- Migration: seed_additional_cards
-- Created at: 1766434700
-- Description: Adds 20 sample intelligence cards featuring real emerging technologies

-- ============================================================================
-- CARD 1: Virtual Twin Cities for Urban Planning
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Virtual Twin Cities for Urban Planning',
    'virtual-twin-cities-urban-planning',
    'Cities deploying digital replicas integrating real-time data to simulate infrastructure changes and predict climate impacts.',
    'Digital twin technology is revolutionizing urban planning by creating comprehensive virtual replicas of entire cities. These platforms integrate IoT sensor data, GIS mapping, and predictive analytics to simulate the effects of infrastructure changes before implementation. Cities like Singapore, Helsinki, and Las Vegas are using digital twins to model traffic flow, energy consumption, emergency response scenarios, and climate adaptation strategies. The technology enables planners to test interventions virtually, reducing costly mistakes and accelerating sustainable development.',
    'MC',
    'MC-04',
    'innovation',
    '5_implementing',
    'H1',
    75, 65, 90, 95, 85, 25, 92,
    '["smart_city_infrastructure", "climate_adaptation"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 2: Urban Air Mobility and Drone Corridor Planning
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Urban Air Mobility and Drone Corridor Planning',
    'urban-air-mobility-drone-corridors',
    'Cities establishing low-altitude airspace management and vertiport infrastructure for drone delivery and air taxi services.',
    'Urban Air Mobility (UAM) represents a paradigm shift in metropolitan transportation, requiring cities to develop entirely new infrastructure frameworks. Municipalities are working with FAA and private operators to establish designated drone corridors, vertiport locations, and noise management protocols. Companies like Joby Aviation, Archer, and Amazon Prime Air are driving demand for regulatory clarity. Cities including Los Angeles, Dallas, and Miami are actively planning vertiport networks integrated with existing transit hubs, while addressing community concerns about noise, privacy, and equitable access to these emerging transportation options.',
    'MC',
    'MC-02',
    'innovation',
    '4_proof',
    'H2',
    92, 35, 85, 80, 88, 45, 88,
    '["transportation_innovation", "infrastructure_modernization"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 3: Subsurface Solar Microgrids
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Subsurface Solar Microgrids',
    'subsurface-solar-microgrids',
    'Distributed subsurface solar powering emergency services, ensuring operation during grid failures.',
    'Underground microgrid installations with surface-level solar collection are emerging as critical infrastructure for municipal resilience. These systems power essential services including emergency operations centers, water treatment facilities, and communication hubs during grid outages. The subsurface components protect battery storage and power electronics from extreme weather events, while modular designs allow scalable deployment. Cities in hurricane and wildfire-prone regions are prioritizing these installations, with pilot projects demonstrating 72+ hour autonomous operation capabilities during recent natural disasters.',
    'ES',
    'ES-01',
    'prevention',
    '4_proof',
    'H2',
    88, 40, 88, 85, 75, 30, 90,
    '["climate_resilience", "emergency_preparedness"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 4: Perovskite Solar Cells for Buildings
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Perovskite Solar Cells for Buildings',
    'perovskite-solar-cells-buildings',
    'Ultra-thin flexible solar cells achieving 25%+ efficiency on building facades and windows.',
    'Perovskite solar technology is transforming building-integrated photovoltaics (BIPV) with cells that can be printed onto flexible substrates and applied to windows, facades, and curved surfaces. Recent breakthroughs have pushed efficiency above 25% while dramatically reducing manufacturing costs compared to traditional silicon. Tandem perovskite-silicon cells are achieving record 33%+ efficiencies in lab settings. Major building material manufacturers are partnering with solar startups to develop commercial products, with several municipal buildings now serving as pilot sites for this next-generation technology.',
    'ES',
    'ES-02',
    'innovation',
    '4_proof',
    'H2',
    90, 38, 92, 88, 82, 35, 94,
    '["renewable_energy", "sustainable_buildings"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 5: Floating Solar Systems for Reservoirs
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Floating Solar Systems for Reservoirs',
    'floating-solar-reservoirs',
    'Solar on water bodies reducing land use while improving efficiency 15% through cooling.',
    'Floating photovoltaic (FPV) systems deployed on municipal reservoirs, water treatment ponds, and irrigation canals are gaining traction as cities seek renewable energy without consuming valuable land. The water cooling effect improves panel efficiency by 10-15% compared to ground-mounted systems, while simultaneously reducing evaporation by up to 70%—a significant benefit for water-stressed regions. California, Texas, and Arizona utilities are expanding FPV installations, with some projects exceeding 100MW capacity. The dual benefit of power generation and water conservation makes this approach particularly attractive for municipal water utilities.',
    'ES',
    'ES-02',
    'innovation',
    '5_implementing',
    'H1',
    70, 60, 85, 90, 78, 20, 88,
    '["renewable_energy", "water_conservation"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 6: Infrastructure Inspection Robots
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Infrastructure Inspection Robots',
    'infrastructure-inspection-robots',
    'Autonomous robots inspecting bridges, pipes, utilities while performing repairs in hazardous environments.',
    'Robotic systems are revolutionizing infrastructure maintenance by performing inspections and repairs in environments too dangerous or inaccessible for human workers. Snake-like robots navigate sewer pipes detecting blockages and structural damage, while climbing robots with magnetic wheels inspect bridges and water towers. Advanced models now incorporate repair capabilities, applying sealants, removing debris, or installing sensors autonomously. Cities including Boston, Pittsburgh, and Denver are deploying these systems to address aging infrastructure backlogs while reducing worker safety risks and inspection costs by up to 50%.',
    'MC',
    'MC-04',
    'innovation',
    '4_proof',
    'H2',
    85, 45, 82, 88, 80, 25, 86,
    '["infrastructure_modernization", "workforce_safety"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 7: Autonomous Delivery Robots
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Autonomous Delivery Robots',
    'autonomous-delivery-robots',
    'Sidewalk delivery robots for last-mile logistics, reducing congestion and emissions.',
    'Small autonomous delivery robots operating on sidewalks and bike lanes are transforming last-mile logistics in urban areas. Companies like Starship Technologies, Nuro, and Serve Robotics have deployed thousands of units delivering groceries, meals, and packages. Cities are developing permitting frameworks and designated operating zones while studying impacts on pedestrian infrastructure and accessibility. Early data shows these robots can reduce delivery-related vehicle miles by 90% within their service areas, significantly cutting emissions and traffic congestion. Municipal partnerships are expanding to include pharmacy deliveries and food access programs in underserved neighborhoods.',
    'MC',
    'MC-03',
    'innovation',
    '5_implementing',
    'H1',
    72, 58, 75, 85, 82, 30, 80,
    '["sustainable_transportation", "logistics_innovation"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 8: Datacenter Energy Grid Pressure
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Datacenter Energy Grid Pressure',
    'datacenter-energy-grid-pressure',
    'Explosive datacenter growth straining grids, demand tripling by 2030, forcing utility upgrades.',
    'The rapid expansion of AI computing and cloud services is creating unprecedented strain on municipal power grids. Datacenter electricity demand is projected to triple by 2030, with single facilities now requesting 500MW+ connections—equivalent to powering 400,000 homes. Cities including Northern Virginia, Phoenix, and Dallas are facing difficult decisions about prioritizing datacenter growth against residential and commercial needs. Utilities are accelerating grid upgrades while some municipalities are implementing datacenter energy caps or requiring on-site renewable generation. This infrastructure challenge is reshaping regional economic development strategies and utility planning horizons.',
    'MC',
    'MC-04',
    'adaptive',
    '7_mature',
    'H1',
    65, 80, 95, 92, 90, 70, 75,
    '["infrastructure_strain", "economic_development"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 9: AI-Powered Water Pressure Management
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'AI-Powered Water Pressure Management',
    'ai-water-pressure-management',
    'Smart water systems using IoT and AI reducing water loss by 30% through leak detection.',
    'Artificial intelligence is transforming municipal water distribution through intelligent pressure management and predictive leak detection. IoT sensors throughout pipe networks feed data to AI systems that optimize pressure zones in real-time, reducing stress on aging infrastructure while maintaining service quality. Machine learning algorithms analyze flow patterns to detect leaks within hours rather than weeks, with some systems achieving 95% detection accuracy. Cities implementing these technologies report 20-30% reductions in non-revenue water loss and significant decreases in main breaks. The cost savings typically achieve payback within 2-3 years while extending infrastructure lifespan.',
    'MC',
    'MC-04',
    'data_driven',
    '5_implementing',
    'H1',
    78, 55, 85, 92, 75, 20, 88,
    '["water_infrastructure", "smart_city"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 10: Demand Response Management Systems
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Demand Response Management Systems',
    'demand-response-management-systems',
    'Advanced utility load management integrating distributed energy resources via AI.',
    'Next-generation demand response systems are evolving beyond simple load shedding to become sophisticated grid orchestration platforms. These AI-driven systems coordinate millions of distributed energy resources including smart thermostats, EV chargers, battery storage, and industrial loads to balance supply and demand in real-time. Utilities are partnering with municipalities to deploy residential programs that automatically adjust consumption during peak periods, offering bill credits to participants. Advanced platforms now predict demand patterns 24-48 hours ahead, enabling proactive resource positioning. Cities with aggressive renewable energy goals are finding demand response essential for managing intermittent solar and wind generation.',
    'ES',
    'ES-02',
    'data_driven',
    '5_implementing',
    'H1',
    70, 62, 88, 90, 78, 25, 85,
    '["grid_modernization", "renewable_integration"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 11: IoT Smart Waste Management
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'IoT Smart Waste Management',
    'iot-smart-waste-management',
    'Sensor-equipped bins with AI route optimization reducing collection costs 30%.',
    'Smart waste management systems combining IoT sensors with AI route optimization are delivering significant operational and environmental benefits for municipalities. Ultrasonic fill-level sensors in bins transmit data to central platforms that dynamically generate collection routes, eliminating unnecessary pickups while preventing overflows. Computer vision systems at material recovery facilities are improving recycling sorting accuracy to 95%+. Cities implementing comprehensive smart waste programs report 25-30% reductions in collection costs, 40% decreases in truck emissions, and measurable improvements in recycling contamination rates. The data collected also enables better bin placement decisions and service level optimization.',
    'ES',
    'ES-03',
    'data_driven',
    '5_implementing',
    'H1',
    68, 65, 78, 88, 72, 15, 82,
    '["operational_efficiency", "sustainability"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 12: Vehicle-to-Grid Bidirectional Charging
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Vehicle-to-Grid Bidirectional Charging',
    'vehicle-to-grid-bidirectional-charging',
    'EVs serving as mobile grid batteries, storing renewable energy for peak demand.',
    'Vehicle-to-grid (V2G) technology is transforming electric vehicles from simple transportation assets into distributed energy storage resources. Bidirectional chargers enable EVs to discharge power back to homes, buildings, or the grid during peak demand periods, with owners compensated for the service. A single EV battery can power an average home for 2-3 days, while fleet aggregation can provide utility-scale storage capacity. California, Texas, and several European utilities are launching V2G programs, with municipal fleets often serving as early adopters. Standards development and battery warranty concerns are being addressed as the technology matures toward mainstream deployment.',
    'ES',
    'ES-02',
    'innovation',
    '4_proof',
    'H2',
    85, 42, 90, 88, 80, 35, 92,
    '["grid_resilience", "ev_infrastructure"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 13: AI Adaptive Traffic Signals
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'AI Adaptive Traffic Signals',
    'ai-adaptive-traffic-signals',
    'AI traffic lights reducing congestion 30-40% and emissions 21% through real-time adaptation.',
    'Advanced AI traffic signal systems are moving beyond simple timing optimization to true real-time adaptation based on comprehensive situational awareness. These systems integrate data from cameras, radar, connected vehicles, and transit systems to dynamically adjust signal timing across entire corridors. Machine learning models continuously improve by analyzing millions of intersection interactions. Pittsburgh''s Surtrac system demonstrated 25% travel time reductions and 21% emission decreases, spurring adoption in dozens of cities. Newer deployments incorporate pedestrian and cyclist detection, emergency vehicle preemption, and transit signal priority, creating more equitable and multimodal intersection management.',
    'MC',
    'MC-03',
    'data_driven',
    '5_implementing',
    'H1',
    75, 60, 88, 94, 82, 20, 90,
    '["traffic_management", "emissions_reduction"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 14: Predictive Policing AI Ethics
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Predictive Policing AI Ethics',
    'predictive-policing-ai-ethics',
    'AI crime analytics requiring robust oversight frameworks balancing safety and civil liberties.',
    'The deployment of AI-powered crime prediction and resource allocation tools is forcing municipalities to develop comprehensive governance frameworks balancing public safety with civil liberties. While these systems can identify patterns invisible to human analysts, concerns about algorithmic bias, feedback loops, and disparate community impacts have led several cities to pause or ban certain applications. Progressive approaches emerging include mandatory algorithmic audits, community oversight boards, and transparency requirements for AI-assisted decisions. Cities like Seattle, San Francisco, and New York are pioneering governance models that other municipalities are studying as they consider their own policies.',
    'CH',
    'CH-05',
    'equity',
    '5_implementing',
    'H1',
    72, 55, 85, 90, 70, 60, 75,
    '["public_safety_innovation", "algorithmic_governance"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 15: Cool Pavement Technologies
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Cool Pavement Technologies',
    'cool-pavement-technologies',
    'Reflective pavements reducing surface temperatures 10-20F and offsetting city emissions.',
    'Cool pavement technologies using reflective coatings, lighter-colored aggregates, or permeable materials are emerging as cost-effective tools for combating urban heat islands. These surfaces can reduce pavement temperatures by 10-20 degrees Fahrenheit compared to traditional asphalt, lowering ambient air temperatures and reducing building cooling loads. Phoenix has coated over 100 miles of streets, documenting measurable neighborhood cooling effects. While initial costs are 10-20% higher than conventional paving, lifecycle analyses show positive returns through reduced maintenance and energy savings. Some formulations also improve nighttime visibility and extend pavement lifespan by reducing thermal stress.',
    'ES',
    'ES-01',
    'prevention',
    '4_proof',
    'H2',
    78, 48, 82, 88, 75, 25, 85,
    '["climate_adaptation", "urban_heat_mitigation"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 16: Blockchain Government Transparency
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Blockchain Government Transparency',
    'blockchain-government-transparency',
    'Blockchain for public procurement, property titles, permits reducing fraud.',
    'Distributed ledger technology is being applied to government operations where transparency, immutability, and auditability are paramount. Municipal implementations include procurement systems with tamper-proof bid records, property registries with complete ownership histories, and permit systems with automatic compliance verification. Dubai, Estonia, and several US cities have deployed production blockchain systems reducing fraud, accelerating processing, and increasing public trust. While enterprise blockchain has moved past initial hype, practical applications in government are demonstrating measurable benefits including 50%+ reductions in title search times and significant decreases in procurement disputes.',
    'EC',
    'EC-01',
    'data_driven',
    '4_proof',
    'H2',
    75, 45, 78, 82, 68, 35, 80,
    '["government_modernization", "transparency"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 17: Private 5G for Public Safety
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Private 5G for Public Safety',
    'private-5g-public-safety',
    'Dedicated 5G ensuring first responder communications during disasters.',
    'Private 5G networks dedicated to public safety are providing first responders with reliable, high-bandwidth communications that remain operational when commercial networks are overwhelmed. These systems support real-time video from body cameras and drones, AR-enhanced situational awareness, and IoT sensor networks for hazmat detection. Cities are deploying private 5G at critical facilities including emergency operations centers, hospitals, and transit hubs. Integration with FirstNet is enabling seamless interoperability while maintaining priority access. Early deployments have proven invaluable during large events and natural disasters when commercial cell networks experienced congestion failures.',
    'CH',
    'CH-05',
    'prevention',
    '5_implementing',
    'H1',
    72, 58, 88, 92, 80, 30, 85,
    '["emergency_communications", "first_responder_technology"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 18: Digital Participatory Budgeting
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Digital Participatory Budgeting',
    'digital-participatory-budgeting',
    'Platforms enabling citizen proposals and votes on municipal budget allocations.',
    'Digital platforms are transforming participatory budgeting from a niche experiment into a scalable civic engagement tool. Modern systems enable residents to submit project proposals, deliberate in online forums, and vote on allocation of designated municipal funds through accessible mobile interfaces. AI moderation and translation features are expanding participation beyond traditional engagement demographics. Cities including New York, Paris, and Madrid have allocated hundreds of millions through these platforms, with digital tools increasing participation rates 3-5x compared to in-person only processes. Analytics dashboards help officials understand community priorities while building trust through transparent implementation tracking.',
    'EC',
    'EC-01',
    'equity',
    '5_implementing',
    'H1',
    68, 62, 80, 88, 72, 20, 85,
    '["civic_engagement", "budget_transparency"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 19: Climate Resilience Bonds
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Climate Resilience Bonds',
    'climate-resilience-bonds',
    'Municipal green bonds funding climate adaptation, $1 invested generates $10 benefits.',
    'Climate resilience bonds are emerging as a powerful financial instrument for funding adaptation infrastructure with measurable co-benefits. These municipal securities fund projects including flood barriers, stormwater systems, urban forestry, and building retrofits, with returns tied to avoided damage costs and insurance savings. Studies show resilience investments generate $6-10 in avoided losses per dollar spent. Rating agencies are increasingly factoring climate risk into municipal credit assessments, making adaptation investments financially prudent. Cities including Miami, New York, and San Francisco have issued hundreds of millions in resilience bonds, with institutional investors demonstrating strong appetite for these instruments.',
    'ES',
    'ES-01',
    'adaptive',
    '5_implementing',
    'H1',
    72, 55, 90, 92, 78, 25, 88,
    '["climate_finance", "infrastructure_investment"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- CARD 20: Municipal Broadband Digital Equity
-- ============================================================================
INSERT INTO cards (
    id, name, slug, summary, description, pillar_id, goal_id, anchor_id, stage_id, horizon,
    novelty_score, maturity_score, impact_score, relevance_score, velocity_score, risk_score, opportunity_score,
    top25_relevance, created_by, created_at
) VALUES (
    gen_random_uuid(),
    'Municipal Broadband Digital Equity',
    'municipal-broadband-digital-equity',
    'City-owned fiber improving internet access 14% in minority communities.',
    'Municipal broadband networks are proving effective at closing digital divides that commercial providers have failed to address. City-owned fiber networks in Chattanooga, Fort Collins, and dozens of other municipalities are providing gigabit service at competitive rates to underserved neighborhoods. Studies show municipal broadband increases internet adoption 8-14% in minority communities and correlates with improved educational outcomes and small business formation. Federal infrastructure funding is enabling new deployments, while legal challenges from incumbent providers are being resolved in favor of municipal authority. These networks also provide critical infrastructure for smart city applications and government operations.',
    'HS',
    'HS-03',
    'equity',
    '5_implementing',
    'H1',
    65, 60, 88, 94, 75, 30, 90,
    '["digital_equity", "broadband_access"]'::jsonb,
    (SELECT id FROM auth.users LIMIT 1),
    NOW()
);

-- ============================================================================
-- SOURCES FOR CARDS
-- ============================================================================

-- Sources for Virtual Twin Cities
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Digital Twins Transform Urban Planning Worldwide',
    'https://smartcitiesworld.net/digital-twins-urban-planning-2024',
    'Major cities are investing billions in digital twin platforms that create living virtual replicas of urban environments, enabling planners to simulate changes before implementation...',
    'Comprehensive analysis of digital twin adoption in urban planning, with case studies from Singapore, Helsinki, and Las Vegas.',
    'article',
    'Dr. James Chen',
    'Smart Cities World',
    NOW() - INTERVAL '5 days',
    92
FROM cards c WHERE c.slug = 'virtual-twin-cities-urban-planning';

INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'The Economic Case for Urban Digital Twins',
    'https://mckinsey.com/industries/public-sector/digital-twins-roi',
    'McKinsey analysis shows digital twin investments deliver 10-15% savings in infrastructure project costs through improved planning and reduced change orders...',
    'ROI analysis demonstrating cost savings and efficiency gains from municipal digital twin implementations.',
    'report',
    'McKinsey Global Institute',
    'McKinsey & Company',
    NOW() - INTERVAL '12 days',
    88
FROM cards c WHERE c.slug = 'virtual-twin-cities-urban-planning';

-- Sources for Urban Air Mobility
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'FAA Releases Urban Air Mobility Corridor Guidelines',
    'https://faa.gov/uas/advanced_operations/urban-air-mobility-framework',
    'The Federal Aviation Administration has released comprehensive guidelines for establishing low-altitude airspace corridors in metropolitan areas, addressing noise, safety, and integration with existing air traffic...',
    'Official FAA framework for UAM corridor establishment and vertiport requirements.',
    'government',
    'Federal Aviation Administration',
    'FAA',
    NOW() - INTERVAL '8 days',
    95
FROM cards c WHERE c.slug = 'urban-air-mobility-drone-corridors';

-- Sources for Subsurface Solar Microgrids
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Underground Microgrids Prove Value During Hurricane Season',
    'https://utilitydive.com/news/underground-microgrids-hurricane-resilience',
    'Municipal emergency facilities powered by subsurface microgrid installations maintained operations throughout recent hurricane events while surrounding areas lost power for days...',
    'Case studies of underground microgrid performance during recent natural disasters.',
    'article',
    'Sarah Williams',
    'Utility Dive',
    NOW() - INTERVAL '3 days',
    90
FROM cards c WHERE c.slug = 'subsurface-solar-microgrids';

-- Sources for Perovskite Solar
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Perovskite-Silicon Tandem Cells Break 33% Efficiency Barrier',
    'https://nature.com/articles/energy-perovskite-record-2024',
    'Researchers have achieved record 33.7% efficiency in tandem perovskite-silicon solar cells, bringing building-integrated photovoltaics closer to commercial viability...',
    'Scientific breakthrough in perovskite solar efficiency with implications for building integration.',
    'academic',
    'Dr. Emily Zhang et al.',
    'Nature Energy',
    NOW() - INTERVAL '15 days',
    94
FROM cards c WHERE c.slug = 'perovskite-solar-cells-buildings';

-- Sources for Floating Solar
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'California Utilities Expand Floating Solar on Reservoirs',
    'https://greentechmedia.com/articles/read/california-floating-solar-expansion',
    'California water utilities are scaling floating photovoltaic deployments, with new installations planned for 15 reservoirs totaling 500MW capacity while reducing evaporation losses...',
    'Analysis of floating solar expansion in California with capacity and water savings data.',
    'article',
    'Michael Torres',
    'Greentech Media',
    NOW() - INTERVAL '7 days',
    88
FROM cards c WHERE c.slug = 'floating-solar-reservoirs';

-- Sources for Infrastructure Robots
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Boston Deploys Pipe Inspection Robots Across Sewer System',
    'https://govtech.com/infrastructure/boston-sewer-inspection-robots',
    'Boston Water and Sewer Commission has deployed autonomous inspection robots throughout the city''s aging sewer infrastructure, achieving 200% increase in inspection coverage while reducing confined space entries...',
    'Municipal case study of robotic infrastructure inspection deployment and outcomes.',
    'article',
    'Jennifer Adams',
    'Government Technology',
    NOW() - INTERVAL '10 days',
    90
FROM cards c WHERE c.slug = 'infrastructure-inspection-robots';

-- Sources for Delivery Robots
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Autonomous Delivery Robots Complete 10 Million Deliveries',
    'https://techcrunch.com/2024/delivery-robots-milestone',
    'Sidewalk delivery robot companies have collectively completed over 10 million commercial deliveries, with data showing 90% reduction in vehicle miles for last-mile logistics in service areas...',
    'Industry milestone report on autonomous delivery robot adoption and environmental impact.',
    'article',
    'Ryan Mitchell',
    'TechCrunch',
    NOW() - INTERVAL '4 days',
    85
FROM cards c WHERE c.slug = 'autonomous-delivery-robots';

-- Sources for Datacenter Grid Pressure
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Datacenter Power Demand Threatens Grid Stability in Key Markets',
    'https://wsj.com/articles/datacenter-power-demand-grid-crisis',
    'Utilities in Northern Virginia, Texas, and Arizona are struggling to meet explosive datacenter power demands, with some facilities requesting connections equivalent to entire cities...',
    'Analysis of datacenter energy demand impact on regional power grids and utility planning.',
    'article',
    'Katherine Newman',
    'Wall Street Journal',
    NOW() - INTERVAL '2 days',
    92
FROM cards c WHERE c.slug = 'datacenter-energy-grid-pressure';

INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'IEA: Global Datacenter Electricity Use to Double by 2030',
    'https://iea.org/reports/electricity-2024/data-centres',
    'International Energy Agency projects datacenter electricity consumption will more than double by 2030, driven by AI computing growth and cloud services expansion...',
    'Authoritative projection of global datacenter energy demand trends.',
    'report',
    'International Energy Agency',
    'IEA',
    NOW() - INTERVAL '20 days',
    95
FROM cards c WHERE c.slug = 'datacenter-energy-grid-pressure';

-- Sources for AI Water Management
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'AI Leak Detection Saves Cities Billions in Water Loss',
    'https://waterworld.com/articles/ai-leak-detection-municipal-savings',
    'Municipalities implementing AI-powered water pressure management and leak detection systems are reporting 20-30% reductions in non-revenue water loss, with some achieving ROI within 18 months...',
    'Survey of municipal AI water management deployments and documented savings.',
    'article',
    'David Park',
    'WaterWorld',
    NOW() - INTERVAL '9 days',
    90
FROM cards c WHERE c.slug = 'ai-water-pressure-management';

-- Sources for Demand Response
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'FERC Order 2222 Opens Markets to Distributed Energy Aggregation',
    'https://utilitydive.com/news/ferc-2222-distributed-energy-demand-response',
    'Federal Energy Regulatory Commission Order 2222 implementation is enabling distributed energy resource aggregators to participate in wholesale markets, creating new opportunities for municipal demand response programs...',
    'Regulatory analysis of federal policy enabling advanced demand response participation.',
    'article',
    'Lisa Thompson',
    'Utility Dive',
    NOW() - INTERVAL '14 days',
    88
FROM cards c WHERE c.slug = 'demand-response-management-systems';

-- Sources for Smart Waste
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Smart Waste Management Delivers 30% Cost Reduction for Cities',
    'https://wastedive.com/news/smart-waste-iot-municipal-savings',
    'Cities implementing IoT-enabled waste management with AI route optimization are achieving 25-30% reductions in collection costs while improving service levels and recycling rates...',
    'Industry analysis of smart waste management ROI and operational improvements.',
    'article',
    'Mark Stevens',
    'Waste Dive',
    NOW() - INTERVAL '6 days',
    88
FROM cards c WHERE c.slug = 'iot-smart-waste-management';

-- Sources for V2G
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'California Approves Vehicle-to-Grid Standards for Utility Programs',
    'https://caiso.com/documents/vehicle-to-grid-standards-2024',
    'California Independent System Operator has approved technical standards enabling vehicle-to-grid participation in wholesale energy markets, clearing a major barrier to V2G adoption...',
    'Regulatory approval of V2G technical standards in California market.',
    'government',
    'California ISO',
    'CAISO',
    NOW() - INTERVAL '11 days',
    92
FROM cards c WHERE c.slug = 'vehicle-to-grid-bidirectional-charging';

-- Sources for AI Traffic Signals
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Pittsburgh AI Traffic System Reduces Travel Times 25%',
    'https://cmu.edu/research/surtrac-results-2024',
    'Carnegie Mellon''s Surtrac adaptive signal control system has documented 25% reductions in travel times and 21% decreases in emissions across Pittsburgh deployment corridors...',
    'Academic research on AI traffic signal performance in Pittsburgh deployment.',
    'academic',
    'Dr. Stephen Smith',
    'Carnegie Mellon University',
    NOW() - INTERVAL '18 days',
    94
FROM cards c WHERE c.slug = 'ai-adaptive-traffic-signals';

-- Sources for Predictive Policing Ethics
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Cities Develop AI Governance Frameworks for Public Safety Tools',
    'https://brookings.edu/articles/municipal-ai-governance-public-safety',
    'Municipalities including Seattle, San Francisco, and New York are pioneering governance frameworks for AI-assisted public safety tools, balancing effectiveness with civil liberties protections...',
    'Policy analysis of municipal AI governance approaches for law enforcement applications.',
    'report',
    'Dr. Rashida Richardson',
    'Brookings Institution',
    NOW() - INTERVAL '13 days',
    90
FROM cards c WHERE c.slug = 'predictive-policing-ai-ethics';

-- Sources for Cool Pavement
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Phoenix Cool Pavement Program Shows Measurable Heat Reduction',
    'https://phoenix.gov/streets/cool-pavement-results',
    'Phoenix''s cool pavement program has documented 10-15 degree surface temperature reductions across coated streets, with preliminary data suggesting measurable ambient air temperature decreases in treated neighborhoods...',
    'Municipal results from largest cool pavement deployment in United States.',
    'government',
    'City of Phoenix',
    'Phoenix Streets Department',
    NOW() - INTERVAL '8 days',
    92
FROM cards c WHERE c.slug = 'cool-pavement-technologies';

-- Sources for Blockchain Government
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Estonia''s Blockchain Government Services: Lessons for US Cities',
    'https://govtech.com/applications/estonia-blockchain-government-model',
    'Estonia''s decade-long experience with blockchain-based government services offers lessons for US municipalities considering distributed ledger implementations for property records, procurement, and permits...',
    'Case study of Estonian blockchain government services with lessons for US implementation.',
    'article',
    'Anna Kowalski',
    'Government Technology',
    NOW() - INTERVAL '16 days',
    85
FROM cards c WHERE c.slug = 'blockchain-government-transparency';

-- Sources for Private 5G Public Safety
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'FirstNet Integration Enables Private 5G for First Responders',
    'https://firstnet.gov/newsroom/blog/private-5g-integration-2024',
    'FirstNet Authority has announced integration protocols enabling municipalities to deploy private 5G networks that seamlessly interoperate with the nationwide public safety broadband network...',
    'Official FirstNet guidance on private 5G integration for public safety applications.',
    'government',
    'FirstNet Authority',
    'First Responder Network Authority',
    NOW() - INTERVAL '7 days',
    94
FROM cards c WHERE c.slug = 'private-5g-public-safety';

-- Sources for Digital Participatory Budgeting
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Digital Participatory Budgeting Increases Civic Engagement 3-5x',
    'https://participedia.net/method/digital-participatory-budgeting-outcomes',
    'Analysis of digital participatory budgeting platforms shows 3-5x increases in participation rates compared to in-person only processes, with significant gains in underrepresented demographic engagement...',
    'Research on digital participatory budgeting participation rates and demographic reach.',
    'academic',
    'Participedia Research Network',
    'Participedia',
    NOW() - INTERVAL '21 days',
    88
FROM cards c WHERE c.slug = 'digital-participatory-budgeting';

-- Sources for Climate Resilience Bonds
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'NIBS Study: Resilience Investments Return $6 for Every $1 Spent',
    'https://nibs.org/projects/natural-hazard-mitigation-saves-2024',
    'National Institute of Building Sciences research shows federal resilience investments generate $6 in avoided losses for every dollar spent, with some categories achieving 10:1 or higher returns...',
    'Authoritative cost-benefit analysis of resilience infrastructure investments.',
    'report',
    'National Institute of Building Sciences',
    'NIBS',
    NOW() - INTERVAL '25 days',
    92
FROM cards c WHERE c.slug = 'climate-resilience-bonds';

-- Sources for Municipal Broadband
INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Municipal Broadband Closes Digital Divide in Underserved Communities',
    'https://ilsr.org/reports/municipal-broadband-digital-equity-2024',
    'Institute for Local Self-Reliance research documents 8-14% increases in internet adoption in minority communities served by municipal broadband networks, with correlated improvements in educational and economic outcomes...',
    'Research on municipal broadband impact on digital equity and community outcomes.',
    'report',
    'Christopher Mitchell',
    'Institute for Local Self-Reliance',
    NOW() - INTERVAL '19 days',
    90
FROM cards c WHERE c.slug = 'municipal-broadband-digital-equity';

INSERT INTO sources (card_id, title, url, content, summary, source_type, author, publisher, published_date, relevance_score)
SELECT
    c.id,
    'Chattanooga Fiber Network Generates $2.7 Billion Economic Impact',
    'https://utc.edu/research/chattanooga-fiber-economic-impact',
    'University of Tennessee at Chattanooga study shows the city''s municipal fiber network has generated $2.69 billion in economic benefits over a decade, including 9,500 new jobs and increased property values...',
    'Economic impact study of Chattanooga municipal broadband network.',
    'academic',
    'Dr. Bento Lobo',
    'University of Tennessee at Chattanooga',
    NOW() - INTERVAL '30 days',
    88
FROM cards c WHERE c.slug = 'municipal-broadband-digital-equity';

-- ============================================================================
-- TIMELINE EVENTS FOR ALL CARDS
-- ============================================================================

INSERT INTO card_timeline (card_id, event_type, title, description, created_by)
SELECT
    c.id,
    'created',
    'Card created via emerging technology research',
    'Intelligence card generated from comprehensive scan of emerging municipal technology trends and real-world deployments',
    (SELECT id FROM auth.users LIMIT 1)
FROM cards c
WHERE c.slug IN (
    'virtual-twin-cities-urban-planning',
    'urban-air-mobility-drone-corridors',
    'subsurface-solar-microgrids',
    'perovskite-solar-cells-buildings',
    'floating-solar-reservoirs',
    'infrastructure-inspection-robots',
    'autonomous-delivery-robots',
    'datacenter-energy-grid-pressure',
    'ai-water-pressure-management',
    'demand-response-management-systems',
    'iot-smart-waste-management',
    'vehicle-to-grid-bidirectional-charging',
    'ai-adaptive-traffic-signals',
    'predictive-policing-ai-ethics',
    'cool-pavement-technologies',
    'blockchain-government-transparency',
    'private-5g-public-safety',
    'digital-participatory-budgeting',
    'climate-resilience-bonds',
    'municipal-broadband-digital-equity'
);
