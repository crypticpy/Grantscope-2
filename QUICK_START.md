# 🎯 Foresight System - Quick Start Guide

## 🚀 Local Development Setup

### Prerequisites
- ✅ Python 3.11+ installed
- ✅ Node.js 18+ and pnpm installed  
- ✅ Supabase account created
- ✅ OpenAI API key obtained

### Step 1: Database Setup
1. **Create Supabase Project**
   - Go to [supabase.com](https://supabase.com)
   - Create new project → Name: "foresight-austin"
   - Note your project URL and API keys

2. **Run Database Schema**
   - Go to Supabase SQL Editor
   - Copy and paste the SQL migrations from the documentation
   - Run all migrations to create tables and sample data

### Step 2: Quick Setup
```bash
# Clone/download the Foresight system files
# Navigate to the project directory

# Run the setup script
bash setup_local.sh

# Follow the prompts to enter your API credentials
```

### Step 3: Start the System
```bash
# Start both backend and frontend
bash start_foresight.sh
```

**Frontend**: http://localhost:5173  
**Backend API**: http://localhost:8000  
**API Docs**: http://localhost:8000/docs

### Step 4: Create Test User
```bash
# In a new terminal, create a test user
cd backend
source venv/bin/activate
python create_test_user.py
```

### Step 5: Login and Test
1. Go to http://localhost:5173
2. Use test credentials:
   - Email: `test@foresight.austintexas.gov`
   - Password: `TestPassword123!`

## 🎮 Testing the MVP Features

### ✅ What You Can Test Now

**Dashboard**
- View recent intelligence cards
- See user statistics and following count
- Browse recent activity

**Discovery Page**
- Filter cards by strategic pillar (CH, MC, HS, EC, ES, CE)
- Filter by maturity stage (Concept → Mature)
- Filter by horizon (H1: 0-2yr, H2: 2-5yr, H3: 5+yr)
- Search for specific topics
- View cards in grid or list format
- Follow/unfollow cards

**Card Detail Page**
- View full card information
- See impact metrics (relevance, velocity, novelty, etc.)
- Add personal notes
- View card timeline
- See associated sources

**Workstreams**
- Create custom research streams
- Set filters by pillar, stage, horizon
- Add keywords for targeted research

**Settings**
- Update profile information
- Configure department and role
- Set notification preferences

### 🧪 Design Testing Checklist

**User Experience**
- [ ] Navigation feels intuitive
- [ ] Card information is clear and useful
- [ ] Filtering works as expected
- [ ] Mobile responsive design
- [ ] Loading states feel responsive

**Content Quality**
- [ ] Sample cards show real strategic value
- [ ] Classifications make sense for Austin context
- [ ] Scores (relevance, impact, etc.) are meaningful
- [ ] Timeline tracking is useful

**Workflow**
- [ ] Following system feels natural
- [ ] Workstream creation is straightforward
- [ ] Notes feature adds value
- [ ] Search returns relevant results

**Visual Design**
- [ ] Professional appearance suitable for municipal use
- [ ] Color coding for strategic pillars works well
- [ ] Typography is readable
- [ ] Layout makes good use of screen space

## 🎯 Key Design Decisions to Validate

1. **Card-Based Intelligence**: Does the "Pokémon cards" concept work for strategic research?
2. **Strategic Pillar Filtering**: Do Austin's 6 pillars provide useful categorization?
3. **Scoring System**: Are the 7 metrics (impact, relevance, velocity, etc.) meaningful?
4. **Follow/Unfollow**: Does the personal monitoring system feel valuable?
5. **Workstream Concept**: Do custom research streams serve user needs?

## 🚨 If You Encounter Issues

**Backend won't start**
```bash
# Check Python version
python3 --version

# Reinstall dependencies
cd backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Frontend won't start**
```bash
# Clear node modules and reinstall
cd frontend/foresight-frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

**Database connection issues**
- Verify Supabase URL and keys in both `.env` files
- Check that database migrations were run successfully
- Ensure RLS policies are enabled

**Can't login**
- Run `python create_test_user.py` to create test credentials
- Check that Supabase authentication is enabled

## 🎨 Design Feedback Areas

Please pay special attention to:

1. **Visual Hierarchy**: Does important information stand out?
2. **Information Density**: Is there too much or too little info per screen?
3. **Workflow Efficiency**: Can users find what they need quickly?
4. **Professional Appearance**: Does it look suitable for city government use?
5. **Mobile Experience**: How does it work on tablets/phones?

## 📝 What to Look For

**Strengths to Keep:**
- Features that feel intuitive
- Information that seems genuinely useful
- Workflows that save time

**Areas to Improve:**
- Confusing navigation or terminology
- Missing information or features
- Slow or cumbersome interactions
- Visual design issues

## 🚀 Ready for Export

Once you're satisfied with the design and functionality:
1. All code is ready for HuggingFace Spaces deployment
2. Docker configuration is included
3. Environment variables are documented
4. Database schema is production-ready

The system will seamlessly transfer to cloud deployment when you're ready!
