# Foresight System - Austin Strategic Research & Intelligence

🎯 **Foresight** is an AI-powered strategic horizon scanning system designed for the City of Austin. It automates the discovery, analysis, and tracking of emerging trends, technologies, and issues that could impact municipal operations.

## 🚀 Quick Start

### Prerequisites
- Supabase account
- OpenAI API key
- Node.js 18+ (for frontend)
- Python 3.11+ (for backend)

### 1. Database Setup

1. **Create Supabase Project**
   - Go to [supabase.com](https://supabase.com)
   - Create new project
   - Note your project URL and API keys

2. **Run Database Migrations**
   ```bash
   # Apply the database schema
   # (Run the SQL migrations provided in the supabase folder)
   ```

3. **Configure Authentication**
   - Enable email/password authentication
   - Optionally enable Google OAuth

### 2. Backend Setup

1. **Install Dependencies**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase and OpenAI credentials
   ```

3. **Run Locally**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### 3. Frontend Setup

1. **Install Dependencies**
   ```bash
   cd frontend/foresight-frontend
   pnpm install
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase URL and API key
   ```

3. **Run Locally**
   ```bash
   pnpm dev
   ```

## 🏗️ Architecture

### Technology Stack
- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Backend**: FastAPI + Python
- **Database**: Supabase (PostgreSQL + pgvector)
- **AI**: OpenAI GPT-4 + Embeddings
- **Authentication**: Supabase Auth
- **Deployment**: HuggingFace Spaces

### Key Features
- **Card-Based Intelligence**: Atomic units of strategic information
- **Vector Search**: Semantic search across all content
- **Strategic Classification**: AI-powered categorization against Austin's pillars
- **Workstream Management**: Custom research streams
- **Real-time Updates**: Live collaboration and updates
- **Timeline Tracking**: Evolution of topics over time

## 📊 Database Schema

### Core Tables
- `cards`: Main intelligence cards
- `sources`: Articles and references
- `users`: User profiles and preferences
- `workstreams`: Custom research streams
- `card_follows`: User tracking of cards
- `card_notes`: User annotations

### Reference Tables
- `pillars`: Austin strategic pillars
- `goals`: Goals under each pillar
- `anchors`: Strategic anchors
- `stages`: Maturity stages
- `priorities`: CMO top 25 priorities

## 🔧 API Endpoints

### Authentication
- `GET /api/v1/me` - Get current user profile
- `PATCH /api/v1/me` - Update user profile

### Cards
- `GET /api/v1/cards` - List cards with filtering
- `GET /api/v1/cards/{id}` - Get card details
- `POST /api/v1/cards` - Create new card
- `POST /api/v1/cards/search` - Search cards

### User Interactions
- `GET /api/v1/me/following` - Get followed cards
- `POST /api/v1/cards/{id}/follow` - Follow card
- `DELETE /api/v1/cards/{id}/follow` - Unfollow card

### Workstreams
- `GET /api/v1/me/workstreams` - List user workstreams
- `POST /api/v1/me/workstreams` - Create workstream
- `GET /api/v1/me/workstreams/{id}/feed` - Get workstream feed

## 🚢 Deployment

### Backend (HuggingFace Spaces)
1. Create new Space at [huggingface.co/spaces](https://huggingface.co/spaces)
2. Choose Docker runtime
3. Upload backend code
4. Set environment variables in Space settings
5. Deploy automatically

### Frontend (Vercel/Netlify)
1. Build the frontend: `pnpm build`
2. Deploy to Vercel/Netlify
3. Set environment variables
4. Configure domain and SSL

## 🧪 Testing

### Local Testing
```bash
# Backend
cd backend
pytest

# Frontend
cd frontend/foresight-frontend
pnpm test
```

### API Testing
```bash
# Test health endpoint
curl http://localhost:8000/api/v1/health

# Test authentication
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'
```

## 📈 AI Pipeline

### Nightly Processing (6 PM Austin Time)
1. **Content Discovery**: Fetch from NewsAPI, RSS feeds, academic sources
2. **Triage**: Filter for municipal relevance
3. **Analysis**: AI-powered classification and scoring
4. **Matching**: Vector similarity to existing cards
5. **Storage**: Update database with new intelligence

### Scoring Metrics
- **Impact**: Potential municipal impact (0-100)
- **Relevance**: Austin-specific relevance (0-100)
- **Velocity**: Trending/popularity speed (0-100)
- **Novelty**: Uniqueness/innovation level (0-100)
- **Opportunity**: Positive potential (0-100)
- **Risk**: Potential challenges/risks (0-100)

## 🎯 Strategic Alignment

Foresight aligns with Austin's strategic framework:

### Strategic Pillars
- **CH**: Community Health
- **MC**: Mobility & Connectivity  
- **HS**: Housing & Economic Stability
- **EC**: Economic Development
- **ES**: Environmental Sustainability
- **CE**: Cultural & Entertainment

### Maturity Stages
1. Concept → 2. Exploring → 3. Pilot → 4. Proof of Concept
5. Implementing → 6. Scaling → 7. Mature → 8. Declining

## 🔒 Security

- Row Level Security (RLS) on all database tables
- JWT-based authentication
- Environment variable protection
- CORS configuration for production

## 📞 Support

For technical support or questions:
- Email: contact-foresight@austintexas.gov
- Documentation: [Project Wiki]
- Issues: [GitHub Issues]

## 📝 License

This project is licensed under the MIT License.

---

**Built with ❤️ for the City of Austin**
