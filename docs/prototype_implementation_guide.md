# GrantScope2 Prototype Implementation Guide

## Quick Start: Supabase + HuggingFace + Azure OpenAI

## 🚀 Getting Started (30 minutes)

### Step 1: Supabase Setup

```bash
# 1. Create new Supabase project
# Go to: https://supabase.com/dashboard
# Project name: grantscope-prototype

# 2. Get your project credentials
# Settings > API > Project URL
# Settings > API > anon public key
# Settings > Database > Connection string
```

### Step 2: HuggingFace Space Setup

```bash
# 1. Create new Space
# Go to: https://huggingface.co/spaces
# Name: austin-grantscope-prototype
# License: apache-2.0
# Hardware: CPU basic
# Framework: gradio

# 2. Clone locally
git clone https://huggingface.co/spaces/YOUR_USERNAME/austin-grantscope-prototype
cd austin-grantscope-prototype
```

### Step 3: Azure OpenAI Configuration

```bash
# 1. Get Azure credentials
# Azure Portal > Azure OpenAI Service > Your resource
# Keys and Endpoint > Endpoint
# Keys and Endpoint > Key 1

# 2. Set environment variables in HuggingFace
# Go to: https://huggingface.co/spaces/YOUR_USERNAME/austin-grantscope-prototype/edit
# Add secrets:
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_KEY=your-azure-openai-key
```

## 📁 Project Structure

```
austin-grantscope-prototype/
├── app.py                 # Main Gradio application
├── requirements.txt       # Python dependencies
├── supabase_client.py    # Supabase connection & queries
├── azure_client.py       # Azure OpenAI integration
├── pillar_classifier.py  # Strategic pillar analysis
├── content_processor.py  # Content cleaning & analysis
├── utils/
│   ├── database.py       # Database schema & setup
│   └── mock_data.py      # Sample content for testing
└── static/
    └── styles.css        # Custom styling
```

## 🗄️ Database Schema (Copy-Paste)

Run these SQL commands in Supabase SQL Editor:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Profiles table (extends auth.users)
CREATE TABLE profiles (
  id UUID REFERENCES auth.users PRIMARY KEY,
  email TEXT,
  full_name TEXT,
  department TEXT,
  role TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
  preferences JSONB DEFAULT '{}'
);

-- Strategic pillar preferences
CREATE TABLE pillar_preferences (
  user_id UUID REFERENCES profiles(id),
  pillar TEXT NOT NULL,
  weight FLOAT DEFAULT 1.0,
  PRIMARY KEY (user_id, pillar)
);

-- Research content
CREATE TABLE research_content (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  title TEXT NOT NULL,
  summary TEXT,
  full_text TEXT,
  source_url TEXT,
  source_type TEXT,
  published_date TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

  -- Strategic pillar classification (0-1 scores)
  equity_score FLOAT DEFAULT 0,
  innovation_score FLOAT DEFAULT 0,
  prevention_score FLOAT DEFAULT 0,
  data_driven_score FLOAT DEFAULT 0,
  adaptive_score FLOAT DEFAULT 0,

  -- Relevance and impact scores (0-100)
  relevance_score FLOAT DEFAULT 0,
  impact_score FLOAT DEFAULT 0,
  status TEXT DEFAULT 'new'
);

-- Vector embeddings for semantic search
CREATE TABLE content_embeddings (
  content_id UUID REFERENCES research_content(id) PRIMARY KEY,
  embedding VECTOR(1536),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- User's followed topics (the "cards")
CREATE TABLE user_cards (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id),
  content_id UUID REFERENCES research_content(id),
  priority TEXT DEFAULT 'medium',
  notes TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE(user_id, content_id)
);

-- User workstreams
CREATE TABLE user_workstreams (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id),
  name TEXT NOT NULL,
  description TEXT,
  pillar_selections TEXT[],
  keywords TEXT[],
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Enable real-time
ALTER PUBLICATION supabase_realtime ADD TABLE research_content;
ALTER PUBLICATION supabase_realtime ADD TABLE user_cards;
```

## 🔧 Core Code Files

### app.py (Main Application)

```python
import gradio as gr
from supabase_client import SupabaseClient
from azure_client import AzureOpenAIClient
from pillar_classifier import StrategicPillarClassifier

# Initialize clients
supabase = SupabaseClient()
azure_client = AzureOpenAIClient()
classifier = StrategicPillarClassifier()

def create_demo_dashboard():
    """Main dashboard interface"""
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("# 🎯 Austin GrantScope2 Dashboard")
            gr.Markdown("### Strategic Research & Intelligence")

        with gr.Column(scale=1):
            login_btn = gr.Button("Sign in with Google", variant="primary")

    # Content feed
    with gr.Row():
        content_feed = gr.Dataframe(
            headers=["Title", "Strategic Pillars", "Relevance", "Actions"],
            datatype=["str", "str", "number", "str"],
            row_count=(10, "fixed"),
            col_count=(4, "fixed"),
            interactive=False
        )

    # Card management
    with gr.Row():
        with gr.Column():
            gr.Markdown("## 🃏 My Research Cards")
            card_display = gr.Dataframe(
                headers=["Topic", "Priority", "Last Update", "Actions"],
                datatype=["str", "str", "str", "str"],
                row_count=(5, "fixed")
            )

        with gr.Column():
            gr.Markdown("## 🔄 Workstreams")
            workstream_display = gr.Dataframe(
                headers=["Name", "Pillars", "Items", "Status"],
                datatype=["str", "str", "number", "str"],
                row_count=(3, "fixed")
            )

# Gradio interface
demo = gr.Interface(
    fn=create_demo_dashboard,
    inputs=[],
    outputs=[content_feed, card_display, workstream_display],
    title="Austin GrantScope2 System Prototype",
    description="AI-powered strategic research for municipal governance"
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
```

### supabase_client.py

```python
from supabase import create_client, Client
import os
from typing import List, Dict, Any

class SupabaseClient:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        self.client: Client = create_client(url, key)

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile data"""
        result = self.client.table("profiles").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None

    def get_research_content(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get latest research content"""
        result = self.client.table("research_content").select("*").order("created_at", desc=True).limit(limit).execute()
        return result.data

    def add_user_card(self, user_id: str, content_id: str, priority: str = "medium") -> bool:
        """Add content to user's card collection"""
        result = self.client.table("user_cards").insert({
            "user_id": user_id,
            "content_id": content_id,
            "priority": priority
        }).execute()
        return len(result.data) > 0

    def get_user_cards(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's card collection"""
        query = """
        SELECT uc.*, rc.title, rc.created_at
        FROM user_cards uc
        JOIN research_content rc ON uc.content_id = rc.id
        WHERE uc.user_id = ? AND uc.status = 'active'
        ORDER BY uc.created_at DESC
        """
        result = self.client.rpc('execute_sql', {'sql': query, 'params': [user_id]}).execute()
        return result.data

    def create_workstream(self, user_id: str, name: str, pillars: List[str]) -> str:
        """Create a new workstream"""
        result = self.client.table("user_workstreams").insert({
            "user_id": user_id,
            "name": name,
            "pillar_selections": pillars
        }).execute()
        return result.data[0]['id'] if result.data else None
```

### azure_client.py

```python
import openai
import os
from typing import Dict, List

class AzureOpenAIClient:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            base_url=os.getenv("AZURE_OPENAI_ENDPOINT") + "/openai/deployments"
        )
        self.model_name = "gpt-4"  # or "gpt-35-turbo" for cost savings

    async def analyze_content(self, content: str) -> Dict[str, any]:
        """Analyze content for strategic relevance"""

        # Strategic pillar classification
        classification_prompt = f"""
        Analyze the following content for Austin municipal government relevance.

        Content: {content}

        Classify this content (0-1 scale) for these strategic pillars:
        - Equity: Fairness, accessibility, inclusive services
        - Innovation: Emerging technologies, digital transformation
        - Prevention: Predictive systems, early warning, risk management
        - Data-driven: Analytics, AI, evidence-based approaches
        - Adaptive: Agility, crisis response, resilience

        Return JSON format:
        {{
            "equity_score": 0.0-1.0,
            "innovation_score": 0.0-1.0,
            "prevention_score": 0.0-1.0,
            "data_driven_score": 0.0-1.0,
            "adaptive_score": 0.0-1.0,
            "relevance_score": 0-100,
            "impact_score": 0-100,
            "summary": "Brief 2-3 sentence summary"
        }}
        """

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": classification_prompt}],
            temperature=0.3
        )

        return self._parse_classification(response.choices[0].message.content)

    async def create_embedding(self, text: str) -> List[float]:
        """Create vector embedding for content"""
        response = self.client.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        return response.data[0].embedding

    def _parse_classification(self, content: str) -> Dict[str, any]:
        """Parse AI classification response"""
        try:
            import json
            return json.loads(content)
        except:
            # Fallback parsing if JSON is malformed
            return {
                "equity_score": 0.5,
                "innovation_score": 0.5,
                "prevention_score": 0.5,
                "data_driven_score": 0.5,
                "adaptive_score": 0.5,
                "relevance_score": 50,
                "impact_score": 50,
                "summary": "Analysis temporarily unavailable"
            }
```

## 🎯 Quick Test Data

### Sample Content for Testing

```python
SAMPLE_CONTENT = [
    {
        "title": "AI-Powered Traffic Management Reduces Congestion by 40%",
        "summary": "European cities implementing AI traffic systems show significant improvements in traffic flow and emissions reduction.",
        "source": "MIT Technology Review",
        "pillars": ["innovation", "data_driven"]
    },
    {
        "title": "Digital Equity Programs Bridge Municipal Service Gaps",
        "summary": "Cities using digital inclusion initiatives report improved access to government services for underserved communities.",
        "source": "Government Technology",
        "pillars": ["equity", "prevention"]
    },
    {
        "title": "Predictive Analytics for Public Safety Response",
        "summary": "Machine learning models help police departments anticipate high-risk areas and allocate resources more effectively.",
        "source": "IEEE Spectrum",
        "pillars": ["data_driven", "adaptive", "prevention"]
    }
]
```

## 🔄 Daily Processing Workflow

### Automated Content Collection Script

```python
import asyncio
from datetime import datetime
from azure_client import AzureOpenAIClient
from supabase_client import SupabaseClient

async def daily_content_update():
    """Run daily content processing pipeline"""
    print(f"Starting daily update at {datetime.now()}")

    # 1. Collect new content from sources
    new_content = await collect_content_sources()

    # 2. Process each piece of content
    for content in new_content:
        # AI analysis
        analysis = await azure_client.analyze_content(content['text'])

        # Store in database
        supabase.client.table('research_content').insert({
            'title': content['title'],
            'summary': analysis['summary'],
            'source_url': content['url'],
            'equity_score': analysis['equity_score'],
            'innovation_score': analysis['innovation_score'],
            'prevention_score': analysis['prevention_score'],
            'data_driven_score': analysis['data_driven_score'],
            'adaptive_score': analysis['adaptive_score'],
            'relevance_score': analysis['relevance_score'],
            'impact_score': analysis['impact_score']
        }).execute()

        # Create embedding for search
        embedding = await azure_client.create_embedding(content['text'])
        # Store embedding...

    print("Daily update complete")

# Schedule to run daily at 6 PM Austin time
# You can use a cron job or Azure Functions for this
```

## 📊 Testing & Validation

### Test Cases

1. **User Authentication**: Google OAuth login/logout
2. **Content Display**: Research items appear with correct pillar classifications
3. **Card Management**: Users can add/remove cards from their collection
4. **Workstream Creation**: Users can create custom research streams
5. **Search Functionality**: Vector search returns relevant results
6. **Real-time Updates**: New content appears automatically

### Success Criteria

- [ ] Users can authenticate with Google
- [ ] Dashboard loads with categorized research content
- [ ] Users can add content to their card collection
- [ ] Card collection persists across sessions
- [ ] Search returns semantically relevant results
- [ ] Real-time updates work for multiple users

## 🎯 Next Steps After Prototype

1. **User Testing**: Get Austin team to test with real workflows
2. **Performance Optimization**: Fine-tune AI prompts and database queries
3. **Content Source Expansion**: Add more data sources and APIs
4. **Mobile Interface**: Create responsive design for mobile use
5. **Integration Planning**: Prepare for production Azure deployment
6. **Budget Planning**: Calculate costs for full 30-40 user deployment

This prototype gives you a working system to test with your Austin team while keeping development time and costs minimal. The modular design makes it easy to expand features and eventually migrate to the full Azure architecture when ready for production.
