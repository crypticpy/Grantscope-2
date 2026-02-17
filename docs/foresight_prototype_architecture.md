# GrantScope2 System Prototype Architecture

## Supabase + HuggingFace + Azure OpenAI

### Prototype Overview

A simplified but fully functional version of the GrantScope2 system using cost-effective, developer-friendly tools for rapid prototyping and user testing.

### Architecture Components

```
┌─────────────────────────────────────────────────────────┐
│                HUGGINGFACE SPACE                        │
│  Frontend: React + Tailwind CSS                         │
│  State: React Context + localStorage                    │
│  Hosting: HuggingFace Spaces (Gradio Interface)         │
├─────────────────────────────────────────────────────────┤
│                  SUPABASE BACKEND                       │
│  ├─ PostgreSQL (Traditional Data)                       │
│  ├─ pgvector (Vector Embeddings)                        │
│  ├─ Real-time (Live Updates)                           │
│  └─ Auth (Google OAuth)                                │
├─────────────────────────────────────────────────────────┤
│                  AZURE OPENAI                          │
│  ├─ GPT-4 (Content Analysis)                           │
│  ├─ Embeddings (Vector Creation)                       │
│  └─ Classification Models                              │
└─────────────────────────────────────────────────────────┘
```

## 1. Supabase Database Schema

### Users & Authentication

```sql
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
  pillar TEXT NOT NULL, -- 'equity', 'innovation', 'prevention', 'data_driven', 'adaptive'
  weight FLOAT DEFAULT 1.0,
  PRIMARY KEY (user_id, pillar)
);
```

### Content & Classification

```sql
-- Research articles/topics
CREATE TABLE research_content (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  title TEXT NOT NULL,
  summary TEXT,
  full_text TEXT,
  source_url TEXT,
  source_type TEXT, -- 'academic', 'government', 'industry', 'news'
  published_date TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

  -- Strategic pillar classification
  equity_score FLOAT DEFAULT 0,
  innovation_score FLOAT DEFAULT 0,
  prevention_score FLOAT DEFAULT 0,
  data_driven_score FLOAT DEFAULT 0,
  adaptive_score FLOAT DEFAULT 0,

  -- Relevance and impact
  relevance_score FLOAT DEFAULT 0,
  impact_score FLOAT DEFAULT 0,
  status TEXT DEFAULT 'new' -- 'new', 'reviewed', 'followed', 'archived'
);

-- Vector embeddings for semantic search
CREATE TABLE content_embeddings (
  content_id UUID REFERENCES research_content(id) PRIMARY KEY,
  embedding VECTOR(1536), -- OpenAI embedding dimension
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### User Collections & Workstreams

```sql
-- User's followed topics (the "cards")
CREATE TABLE user_cards (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id),
  content_id UUID REFERENCES research_content(id),
  priority TEXT DEFAULT 'medium', -- 'high', 'medium', 'low'
  notes TEXT,
  status TEXT DEFAULT 'active', -- 'active', 'archived', 'completed'
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE(user_id, content_id)
);

-- User workstreams
CREATE TABLE user_workstreams (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id),
  name TEXT NOT NULL,
  description TEXT,
  pillar_selections TEXT[], -- Array of selected pillars
  keywords TEXT[],
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### Real-time Updates

```sql
-- Enable real-time for live dashboard updates
ALTER PUBLICATION supabase_realtime ADD TABLE research_content;
ALTER PUBLICATION supabase_realtime ADD TABLE user_cards;
```

## 2. HuggingFace Space Implementation

### Frontend Structure

```
grantscope-prototype/
├── app.py (Gradio interface)
├── components/
│   ├── dashboard.py
│   ├── workstream_manager.py
│   └── card_system.py
├── supabase_client.py
├── azure_openai_client.py
└── utils/
    ├── pillar_classifier.py
    └── content_processor.py
```

### Key Features for Prototype

1. **Daily Dashboard**: Browse new research with pillar filters
2. **Card Management**: Save topics for continued monitoring
3. **Workstream Creator**: Define custom research streams
4. **Search Interface**: Vector + keyword search
5. **Google Auth**: Simple login/logout

## 3. Azure OpenAI Integration

### Content Analysis Pipeline

```python
class AzureOpenAIClient:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            base_url=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

    async def analyze_content(self, text):
        # Strategic pillar classification
        classification = await self.classify_strategic_pillars(text)

        # Relevance scoring
        relevance = await self.score_municipal_relevance(text)

        # Generate summary
        summary = await self.generate_summary(text)

        return {
            'classification': classification,
            'relevance': relevance,
            'summary': summary
        }

    async def create_embedding(self, text):
        response = self.client.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        return response.data[0].embedding
```

## 4. Prototype Data Sources

### Simplified Content Sources

```python
CONTENT_SOURCES = {
    'technology_news': [
        'https://feeds.feedburner.com/venturebeat/SZYF',
        'https://feeds.feedburner.com/oreilly/radar'
    ],
    'government_tech': [
        'https://www.federalregister.gov/documents/search.rss',
        'https://www.govtech.com/rss.xml'
    ],
    'academic': [
        'https://rss.sciencedirect.com/publication/science',
        'https://ieeexplore.ieee.org/rss'
    ]
}
```

### Daily Processing Workflow

1. **6 PM Austin Time**: Trigger content collection
2. **Clean & Deduplicate**: Remove duplicates and low-quality content
3. **AI Analysis**: Azure OpenAI classification and summarization
4. **Vector Storage**: Store embeddings in Supabase
5. **Real-time Update**: Push new content to user dashboards

## 5. Prototype User Interface

### Main Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  🎯 GrantScope2 Dashboard - Austin Strategic Research     │
│  [Sign in with Google] [Profile] [Settings]            │
├─────────────────────────────────────────────────────────┤
│  Filter: [All Pillars ▼] [Last 24h] [Relevance ▼]     │
│  📊 Today's Research: 23 items | High Priority: 5      │
├─────────────────────────────────────────────────────────┤
│  ┌─ INNOVATION (Score: 87%)                           │
│  │ • AI-Powered Traffic Management Results in 40%     │
│  │   Efficiency Gain in European Cities               │
│  │   [Read Summary] [Add to Cards] [Follow Topic]     │
│  ├─ EQUITY (Score: 92%)                               │
│  │ • Digital Inclusion Program Reduces Service Gaps   │
│  │   [Full Analysis] [Relevant to Your Workstreams]   │
│  └─ DATA-DRIVEN (Score: 78%)                          │
│    • Real-time Analytics Dashboard Deployments        │
│    [Comparative Study] [Share with Team]              │
└─────────────────────────────────────────────────────────┘
```

### Card Management Interface

```
┌─────────────────────────────────────────────────────────┐
│  🃏 My Research Cards (12 active)                       │
├─────────────────────────────────────────────────────────┤
│  🔥 High Priority (3) 📊 Queue (5) 📚 Archive (4)      │
│                                                         │
│  ┌─ AI Traffic Management                              │
│  │   📈 Trending Up | Last Update: 2h ago             │
│  │   💡 Innovation + Data-Driven                       │
│  │   [📊 Analytics] [📝 Notes] [❌ Unfollow]          │
│  ├─ Digital Inclusion Programs                         │
│  │   📊 Stable | Last Update: 6h ago                  │
│  │   💡 Equity + Proactive Prevention                  │
│  │   [🔔 Alerts] [📤 Share] [⭐ Archive]              │
│  └─ Crisis Response AI                                 │
│     🔥 Urgent | Last Update: 1h ago                   │
│     💡 Adaptive Governance + Public Safety            │
│     [📋 Full Report] [👥 Collaborate] [📈 Trends]     │
└─────────────────────────────────────────────────────────┘
```

## 6. Prototype Implementation Plan

### Week 1-2: Foundation

- [ ] Set up Supabase project with schema
- [ ] Create HuggingFace Space structure
- [ ] Implement Google OAuth authentication
- [ ] Basic dashboard with sample data

### Week 3-4: Core Features

- [ ] Azure OpenAI integration for content analysis
- [ ] Strategic pillar classification system
- [ ] Card collection and management
- [ ] Real-time updates via Supabase

### Week 5-6: Intelligence Features

- [ ] Vector search implementation
- [ ] Workstream management
- [ ] Content source integration
- [ ] Mobile-responsive design

### Week 7-8: Polish & Testing

- [ ] Performance optimization
- [ ] User experience refinement
- [ ] Stakeholder testing and feedback
- [ ] Documentation and deployment

## 7. Cost Estimate (Prototype)

**Monthly Costs (Estimated)**:

- **Supabase Pro**: $25/month (for 50K API requests)
- **Azure OpenAI**: $50-100/month (depending on usage)
- **HuggingFace Spaces**: Free (public) or $9/month (private)
- **Content Sources**: $0-20/month (API access)

**Total**: ~$75-150/month for prototype

**Full Production Estimate**: $500-1000/month (with 30-40 users)

## 8. Prototype Success Metrics

### Technical KPIs

- **Response Time**: <2 seconds for dashboard loading
- **Content Processing**: <5 minutes for daily analysis
- **Search Accuracy**: 85%+ relevance in user testing
- **Uptime**: 99%+ availability

### User Experience KPIs

- **Daily Active Users**: 60%+ of invited users
- **Content Engagement**: 3+ cards added per user per week
- **Time Savings**: 2+ hours per user per week vs. manual research
- **User Satisfaction**: 4.5+ out of 5 rating

This prototype architecture gives you a fully functional system to test with your Austin team while keeping costs low and implementation time reasonable. The modular design also makes it easy to scale up to the full Azure architecture when you're ready for production deployment.
