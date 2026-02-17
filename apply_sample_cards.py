#!/usr/bin/env python3
"""
Script to apply sample cards to the GrantScope2 database
Uses Supabase Python client with service key
"""

import os
from supabase import create_client
from datetime import datetime, timedelta
import random

# Load environment variables
from dotenv import load_dotenv

load_dotenv("backend/.env")

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_key:
    print("❌ Missing Supabase configuration")
    exit(1)

supabase = create_client(supabase_url, supabase_key)

# Sample cards data
cards_data = [
    {
        "name": "Virtual Twin Cities for Urban Planning",
        "slug": "virtual-twin-cities-urban-planning",
        "summary": "Cities deploying digital replicas integrating real-time data to simulate infrastructure changes and predict climate impacts.",
        "description": "Over 500 city digital twins are now deployed globally, with cities like Singapore preventing millions in weather-related losses. Boulder has reduced complex 400-hour planning workflows to three steps using digital twin technology. The technology combines IoT sensors, AI analytics, and 3D modeling to create dynamic simulations that inform smarter infrastructure decisions.",
        "pillar_id": "MC",
        "goal_id": "MC-04",
        "anchor_id": "innovation",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 75,
        "maturity_score": 65,
        "impact_score": 90,
        "relevance_score": 85,
        "velocity_score": 80,
        "risk_score": 25,
        "opportunity_score": 90,
        "top25_relevance": [
            "Imagine Austin Update",
            "Citywide Technology Strategic Plan",
        ],
    },
    {
        "name": "Urban Air Mobility and Drone Corridor Planning",
        "slug": "urban-air-mobility-drone-corridors",
        "summary": "Cities establishing low-altitude airspace management and vertiport infrastructure for drone delivery and air taxi services.",
        "description": "Shenzhen has deployed over 120 operational vertiports supporting commercial passenger shuttles and delivery drones. The drone taxi market is projected to reach $3.83 billion by 2032. Cities are implementing Unmanned Traffic Management Systems with dynamic geofencing and air corridor planning.",
        "pillar_id": "MC",
        "goal_id": "MC-02",
        "anchor_id": "innovation",
        "stage_id": "4_proof",
        "horizon": "H2",
        "novelty_score": 90,
        "maturity_score": 35,
        "impact_score": 85,
        "relevance_score": 70,
        "velocity_score": 85,
        "risk_score": 45,
        "opportunity_score": 88,
        "top25_relevance": ["Airline Use & Lease Agreement (Airport)"],
    },
    {
        "name": "Subsurface Solar Microgrids",
        "slug": "subsurface-solar-microgrids",
        "summary": "Distributed subsurface solar powering emergency services, ensuring operation during grid failures.",
        "description": "Urban solar design has shifted toward subsurface installations creating distributed networks that power police, fire departments, and municipal services. These Power to Protect microgrids eliminate dependency on external power during emergencies and enable bidirectional energy management reducing urban consumption by 7%.",
        "pillar_id": "ES",
        "goal_id": "ES-01",
        "anchor_id": "prevention",
        "stage_id": "4_proof",
        "horizon": "H2",
        "novelty_score": 85,
        "maturity_score": 40,
        "impact_score": 80,
        "relevance_score": 75,
        "velocity_score": 70,
        "risk_score": 30,
        "opportunity_score": 85,
        "top25_relevance": ["AE Resiliency Plan", "Climate Revolving Fund"],
    },
    {
        "name": "Perovskite Solar Cells for Buildings",
        "slug": "perovskite-solar-cells-buildings",
        "summary": "Ultra-thin flexible solar cells achieving 25%+ efficiency on building facades and windows.",
        "description": "Japan invested $1.5 billion in 2025 to commercialize perovskite solar cells that rival silicon panels at over 25% efficiency. These flexible modules can be applied to building facades, turning entire structures into power plants. Transparent solar panels are making skyscraper windows into energy sources a near-term reality.",
        "pillar_id": "ES",
        "goal_id": "ES-01",
        "anchor_id": "innovation",
        "stage_id": "4_proof",
        "horizon": "H2",
        "novelty_score": 88,
        "maturity_score": 35,
        "impact_score": 85,
        "relevance_score": 70,
        "velocity_score": 75,
        "risk_score": 35,
        "opportunity_score": 90,
        "top25_relevance": ["Climate Revolving Fund"],
    },
    {
        "name": "Floating Solar Systems for Reservoirs",
        "slug": "floating-solar-reservoirs",
        "summary": "Solar on water bodies reducing land use while improving efficiency 15% through cooling.",
        "description": "Floating solar systems installed on lakes and reservoirs benefit from water cooling that enhances efficiency by up to 15%. These systems eliminate land use conflicts, reduce water evaporation, and can double global installed solar capacity according to World Bank estimates.",
        "pillar_id": "ES",
        "goal_id": "ES-02",
        "anchor_id": "innovation",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 70,
        "maturity_score": 60,
        "impact_score": 75,
        "relevance_score": 80,
        "velocity_score": 65,
        "risk_score": 20,
        "opportunity_score": 80,
        "top25_relevance": ["Climate Revolving Fund"],
    },
    {
        "name": "Infrastructure Inspection Robots",
        "slug": "infrastructure-inspection-robots",
        "summary": "Autonomous robots inspecting bridges, pipes, utilities while performing repairs in hazardous environments.",
        "description": "The UK is investing in self-repairing cities using autonomous robots to fix potholes and streetlights. Municipalities employ robots for infrastructure monitoring, waste management, and autonomous inspections. These systems can inspect bridge integrity, detect water main leaks, and perform basic repairs without exposing workers to dangerous conditions.",
        "pillar_id": "MC",
        "goal_id": "MC-04",
        "anchor_id": "innovation",
        "stage_id": "4_proof",
        "horizon": "H2",
        "novelty_score": 80,
        "maturity_score": 40,
        "impact_score": 85,
        "relevance_score": 85,
        "velocity_score": 75,
        "risk_score": 25,
        "opportunity_score": 88,
        "top25_relevance": ["Facility Condition Assessment Contract"],
    },
    {
        "name": "Autonomous Delivery Robots",
        "slug": "autonomous-delivery-robots",
        "summary": "Sidewalk delivery robots for last-mile logistics, reducing congestion and emissions.",
        "description": "Serve Robotics operates over 100 delivery robots in Los Angeles for Uber Eats and 7-Eleven, with plans to expand to 2,000 units across US cities. These autonomous robots reduce delivery vehicle congestion, lower emissions, and provide last-mile logistics without adding cars to streets.",
        "pillar_id": "MC",
        "goal_id": "MC-03",
        "anchor_id": "innovation",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 75,
        "maturity_score": 55,
        "impact_score": 70,
        "relevance_score": 75,
        "velocity_score": 80,
        "risk_score": 30,
        "opportunity_score": 75,
        "top25_relevance": [],
    },
    {
        "name": "Datacenter Energy Grid Pressure",
        "slug": "datacenter-energy-grid-pressure",
        "summary": "Explosive datacenter growth straining grids, demand tripling by 2030, forcing utility upgrades.",
        "description": "US datacenter grid power demand will increase 22% in 2025 to 61.8 GW and nearly triple to 134.4 GW by 2030. In Virginia, datacenters consumed 26% of total electricity in 2023. Grid operators warn they cannot handle more datacenters without infrastructure upgrades that may raise residential electricity bills.",
        "pillar_id": "MC",
        "goal_id": "MC-05",
        "anchor_id": "adaptive",
        "stage_id": "7_mature",
        "horizon": "H1",
        "novelty_score": 60,
        "maturity_score": 80,
        "impact_score": 95,
        "relevance_score": 90,
        "velocity_score": 90,
        "risk_score": 75,
        "opportunity_score": 65,
        "top25_relevance": ["AE Resiliency Plan", "Economic Development Roadmap"],
    },
    {
        "name": "AI-Powered Water Pressure Management",
        "slug": "ai-water-pressure-management",
        "summary": "Smart water systems using IoT and AI reducing water loss by 30% through leak detection.",
        "description": "The smart water management market will grow from $18.3 billion in 2024 to $50.7 billion by 2033. Shenzhen equipped 80% of households with smart meters, reducing non-revenue water to 6.2%. AI-powered pressure optimization prevents pipe bursts while predictive analytics prioritize repairs.",
        "pillar_id": "MC",
        "goal_id": "MC-05",
        "anchor_id": "data_driven",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 70,
        "maturity_score": 60,
        "impact_score": 85,
        "relevance_score": 90,
        "velocity_score": 75,
        "risk_score": 20,
        "opportunity_score": 88,
        "top25_relevance": ["AE Resiliency Plan"],
    },
    {
        "name": "Demand Response Management Systems",
        "slug": "demand-response-management-systems",
        "summary": "Advanced utility load management integrating distributed energy resources via AI.",
        "description": "With US electricity demand forecast to hit a record 4,186 billion kWh in 2025, utilities are deploying Demand Response Management Systems with 2-way communications managing millions of endpoints. These systems use AI-enabled analytics for real-time monitoring and unified grid planning.",
        "pillar_id": "ES",
        "goal_id": "ES-01",
        "anchor_id": "data_driven",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 65,
        "maturity_score": 65,
        "impact_score": 80,
        "relevance_score": 85,
        "velocity_score": 70,
        "risk_score": 20,
        "opportunity_score": 82,
        "top25_relevance": ["AE Resiliency Plan"],
    },
    {
        "name": "IoT Smart Waste Management",
        "slug": "iot-smart-waste-management",
        "summary": "Sensor-equipped bins with AI route optimization reducing collection costs 30%.",
        "description": "Barcelona's 18,000 IoT sensors save $555,000 annually in waste management costs. Smart bins use ultrasonic and weight sensors to monitor fill levels with 95% accuracy. AI systems achieve 94% accuracy predicting overflows, enabling dynamic routing that reduces missed pickups by 72.7%.",
        "pillar_id": "ES",
        "goal_id": "ES-02",
        "anchor_id": "data_driven",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 60,
        "maturity_score": 70,
        "impact_score": 75,
        "relevance_score": 80,
        "velocity_score": 65,
        "risk_score": 15,
        "opportunity_score": 78,
        "top25_relevance": [],
    },
    {
        "name": "Vehicle-to-Grid Bidirectional Charging",
        "slug": "vehicle-to-grid-bidirectional-charging",
        "summary": "EVs serving as mobile grid batteries, storing renewable energy for peak demand.",
        "description": "China launched V2G pilots in nine cities in 2025, installing at least 30 V2G stations with plans for 5,000 by 2027. Officials predict 100 million EVs could unlock 1 billion kilowatts of grid capacity by 2030. France became the first country to make V2G commercially available.",
        "pillar_id": "ES",
        "goal_id": "ES-01",
        "anchor_id": "innovation",
        "stage_id": "4_proof",
        "horizon": "H2",
        "novelty_score": 82,
        "maturity_score": 40,
        "impact_score": 88,
        "relevance_score": 80,
        "velocity_score": 78,
        "risk_score": 35,
        "opportunity_score": 90,
        "top25_relevance": ["Climate Revolving Fund", "AE Resiliency Plan"],
    },
    {
        "name": "AI Adaptive Traffic Signals",
        "slug": "ai-adaptive-traffic-signals",
        "summary": "AI traffic lights reducing congestion 30-40% and emissions 21% through real-time adaptation.",
        "description": "Los Angeles operates 4,850 adaptive traffic signals that slash intersection delays by 32% and cut emissions by 3%. Pittsburgh's SURTRAC system reduced wait times by 40%, travel times by 25%, and emissions by 21%. The intelligent traffic management market will grow to $27.9 billion by 2030.",
        "pillar_id": "MC",
        "goal_id": "MC-01",
        "anchor_id": "data_driven",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 65,
        "maturity_score": 70,
        "impact_score": 85,
        "relevance_score": 90,
        "velocity_score": 75,
        "risk_score": 20,
        "opportunity_score": 85,
        "top25_relevance": ["Light Rail Interlocal Agreement"],
    },
    {
        "name": "Predictive Policing AI Ethics",
        "slug": "predictive-policing-ai-ethics",
        "summary": "AI crime analytics requiring robust oversight frameworks balancing safety and civil liberties.",
        "description": "McKinsey suggests AI in law enforcement might lower crime by 30-40%, but high-profile retreats by Chicago and Los Angeles highlight bias concerns. The EU AI Act prohibits predictive systems except for major crimes. NAACP recommends independent oversight bodies and transparency mandates.",
        "pillar_id": "CH",
        "goal_id": "CH-05",
        "anchor_id": "equity",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 70,
        "maturity_score": 55,
        "impact_score": 85,
        "relevance_score": 80,
        "velocity_score": 70,
        "risk_score": 65,
        "opportunity_score": 70,
        "top25_relevance": [
            "Comprehensive Crime Reduction Plan",
            "Human Rights Framework",
        ],
    },
    {
        "name": "Cool Pavement Technologies",
        "slug": "cool-pavement-technologies",
        "summary": "Reflective pavements reducing surface temperatures 10-20°F and offsetting city emissions.",
        "description": "Phoenix has deployed over 100 miles of cool pavement in one of the largest US pilots. Research shows reflective pavements lower surface temperatures by 5-20°C while evaporative pavements reduce temperatures by 5-35°C. Additional benefits include reduced stormwater runoff and improved water quality.",
        "pillar_id": "ES",
        "goal_id": "ES-03",
        "anchor_id": "prevention",
        "stage_id": "4_proof",
        "horizon": "H2",
        "novelty_score": 75,
        "maturity_score": 45,
        "impact_score": 80,
        "relevance_score": 85,
        "velocity_score": 65,
        "risk_score": 25,
        "opportunity_score": 82,
        "top25_relevance": ["Climate Revolving Fund"],
    },
    {
        "name": "Blockchain Government Transparency",
        "slug": "blockchain-government-transparency",
        "summary": "Blockchain for public procurement, property titles, permits reducing fraud.",
        "description": "The US Commerce Department launched a blockchain initiative in August 2025 to publish GDP figures on immutable ledgers, backed by $59 million in federal funding. Estonia's e-Estonia platform uses blockchain for mobile ID replacing physical documents. UAE aims to adopt blockchain for government documents by 2025.",
        "pillar_id": "EC",
        "goal_id": "EC-04",
        "anchor_id": "innovation",
        "stage_id": "4_proof",
        "horizon": "H2",
        "novelty_score": 75,
        "maturity_score": 40,
        "impact_score": 75,
        "relevance_score": 70,
        "velocity_score": 60,
        "risk_score": 40,
        "opportunity_score": 75,
        "top25_relevance": ["Citywide Technology Strategic Plan"],
    },
    {
        "name": "Private 5G for Public Safety",
        "slug": "private-5g-public-safety",
        "summary": "Dedicated 5G ensuring first responder communications during disasters.",
        "description": "Private 5G infrastructure spending will exceed $7.2 billion by 2028, with 70% directed toward standalone networks supporting public safety. 2025 disasters exposed public network failures during critical response periods. Ontario's Peel-Halton police maintain uninterrupted data access via private broadband.",
        "pillar_id": "CH",
        "goal_id": "CH-04",
        "anchor_id": "prevention",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 70,
        "maturity_score": 60,
        "impact_score": 90,
        "relevance_score": 85,
        "velocity_score": 75,
        "risk_score": 25,
        "opportunity_score": 88,
        "top25_relevance": ["Austin FIRST EMS Mental Health Pilot"],
    },
    {
        "name": "Digital Participatory Budgeting",
        "slug": "digital-participatory-budgeting",
        "summary": "Platforms enabling citizen proposals and votes on municipal budget allocations.",
        "description": "Barcelona's Decidim and Madrid's Consul platforms enable citizens to submit budget proposals and vote on spending priorities. OECD data shows 69% of citizens who feel they have a say report high trust versus 22% who don't. Research shows participatory budgeting increases government trust.",
        "pillar_id": "EC",
        "goal_id": "EC-01",
        "anchor_id": "collaboration",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 65,
        "maturity_score": 65,
        "impact_score": 80,
        "relevance_score": 85,
        "velocity_score": 60,
        "risk_score": 20,
        "opportunity_score": 82,
        "top25_relevance": ["2026 Bond Program Development"],
    },
    {
        "name": "Climate Resilience Bonds",
        "slug": "climate-resilience-bonds",
        "summary": "Municipal green bonds funding climate adaptation, $1 invested generates $10 benefits.",
        "description": "Tokyo issued the world's first certified resilience bond in October 2025 for flood protection. Green bond issuance reached $1.1 trillion in 2024, enabling cities to independently fund climate projects. WRI analysis shows $1 invested in adaptation generates $10 in benefits over 10 years.",
        "pillar_id": "ES",
        "goal_id": "ES-01",
        "anchor_id": "adaptive",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 70,
        "maturity_score": 60,
        "impact_score": 85,
        "relevance_score": 90,
        "velocity_score": 70,
        "risk_score": 25,
        "opportunity_score": 90,
        "top25_relevance": ["Climate Revolving Fund", "2026 Bond Program Development"],
    },
    {
        "name": "Municipal Broadband Digital Equity",
        "slug": "municipal-broadband-digital-equity",
        "summary": "City-owned fiber improving internet access 14% in minority communities.",
        "description": "331 US municipal broadband networks now operate, growing by 15 annually. Communities with municipal fiber show 85.8% adoption versus 79.2% without, with 14 percentage point higher adoption in majority Black and Hispanic communities. Chattanooga's network generated $2.7 billion in economic benefits.",
        "pillar_id": "HS",
        "goal_id": "HS-01",
        "anchor_id": "equity",
        "stage_id": "5_implementing",
        "horizon": "H1",
        "novelty_score": 60,
        "maturity_score": 65,
        "impact_score": 85,
        "relevance_score": 90,
        "velocity_score": 65,
        "risk_score": 30,
        "opportunity_score": 88,
        "top25_relevance": ["Citywide Technology Strategic Plan"],
    },
]


def main():
    print("🚀 Applying sample cards to GrantScope2 database...")

    # Get a user ID for created_by (use the test user we created earlier)
    user_result = supabase.table("users").select("id").limit(1).execute()
    if not user_result.data:
        print("⚠️ No users found, creating cards without created_by")
        created_by = None
    else:
        created_by = user_result.data[0]["id"]
        print(f"✅ Using user ID: {created_by}")

    # Check existing cards
    existing = supabase.table("cards").select("slug").execute()
    existing_slugs = {c["slug"] for c in existing.data} if existing.data else set()
    print(f"📊 Found {len(existing_slugs)} existing cards")

    cards_inserted = 0
    cards_skipped = 0

    for card in cards_data:
        if card["slug"] in existing_slugs:
            print(f"⏭️ Skipping existing card: {card['name']}")
            cards_skipped += 1
            continue

        # Prepare card data
        card_insert = {
            "name": card["name"],
            "slug": card["slug"],
            "summary": card["summary"],
            "description": card["description"],
            "pillar_id": card["pillar_id"],
            "goal_id": card["goal_id"],
            "anchor_id": card["anchor_id"],
            "stage_id": card["stage_id"],
            "horizon": card["horizon"],
            "novelty_score": card["novelty_score"],
            "maturity_score": card["maturity_score"],
            "impact_score": card["impact_score"],
            "relevance_score": card["relevance_score"],
            "velocity_score": card["velocity_score"],
            "risk_score": card["risk_score"],
            "opportunity_score": card["opportunity_score"],
            "status": "active",
        }

        if created_by:
            card_insert["created_by"] = created_by

        # Note: top25_relevance column doesn't exist in database yet
        # if card.get('top25_relevance'):
        #     card_insert['top25_relevance'] = card['top25_relevance']

        try:
            result = supabase.table("cards").insert(card_insert).execute()
            if result.data:
                print(f"✅ Inserted: {card['name']}")
                cards_inserted += 1

                # Add a timeline event for the card
                card_id = result.data[0]["id"]
                timeline_event = {
                    "card_id": card_id,
                    "event_type": "created",
                    "title": "Card created from emerging technology research",
                    "description": f"Initial card generated from 2025 emerging technology analysis",
                }
                if created_by:
                    timeline_event["created_by"] = created_by

                supabase.table("card_timeline").insert(timeline_event).execute()
            else:
                print(f"❌ Failed to insert: {card['name']}")
        except Exception as e:
            print(f"❌ Error inserting {card['name']}: {e}")

    print(f"\n📊 Summary:")
    print(f"   Inserted: {cards_inserted} cards")
    print(f"   Skipped: {cards_skipped} cards (already exist)")
    print(f"   Total in database: {len(existing_slugs) + cards_inserted}")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
