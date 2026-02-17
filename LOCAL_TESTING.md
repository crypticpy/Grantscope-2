# 🎯 GrantScope2 - Local Testing Guide

## 🚀 Quick Start (5 minutes)

### Step 1: Setup (One-time)

```bash
# Make scripts executable (if needed)
chmod +x setup_local.sh start_grantscope.sh

# Run the setup script
bash setup_local.sh
```

**Follow the prompts** to enter your Supabase and OpenAI credentials.

### Step 2: Start the System

```bash
# Start both backend and frontend
bash start_grantscope.sh
```

### Step 3: Access the System

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Step 4: Login

- **Email**: `test@grantscope.austintexas.gov`
- **Password**: `TestPassword123!`

## 🧪 What You Can Test

### ✅ Core Features

1. **Dashboard** - Recent intelligence, user stats, following overview
2. **Discovery** - Browse cards with filters (pillar, stage, horizon, keywords)
3. **Card Details** - Full information, sources, timeline, notes
4. **Following** - Add/remove cards from personal monitoring
5. **Workstreams** - Create custom research streams
6. **Settings** - Profile management and preferences

### ✅ Design Validation

- **Navigation** - Is the interface intuitive?
- **Information** - Are the cards and metrics meaningful?
- **Workflow** - Does the following/workstream system add value?
- **Visual** - Professional appearance for municipal use?
- **Mobile** - Responsive design on different screen sizes?

## 🔧 Testing Commands

### Check System Status

```bash
# Test if everything is running correctly
python test_system.py
```

### Manual Backend Start (if needed)

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Manual Worker Start (required for deep research / discovery / briefs)

```bash
cd backend
source venv/bin/activate
python -m app.worker
```

### Manual Frontend Start (if needed)

```bash
cd frontend/foresight-frontend
pnpm dev
```

### Create Test User (if needed)

```bash
cd backend
source venv/bin/activate
python create_test_user.py
```

## 📋 Sample Data Included

The system comes with 5 sample intelligence cards:

1. **AI-Powered Traffic Management** (MC + Innovation)
2. **Digital Equity Programs** (CH + Equity)
3. **Predictive Public Safety Analytics** (CH + Data-Driven)
4. **Green Infrastructure Networks** (ES + Prevention)
5. **Remote Work Economic Impact** (EC + Adaptive)

Each card includes:

- Strategic classification (pillar, stage, horizon)
- AI-generated impact metrics (0-100 scores)
- Sample sources and timeline events
- Professional descriptions suitable for Austin context

## 🎨 Design Testing Areas

### User Experience

- **Navigation**: Can users find what they need quickly?
- **Information Hierarchy**: Does important information stand out?
- **Workflow**: Does the card following system feel natural?
- **Search**: Do filters and search work as expected?

### Content Quality

- **Strategic Value**: Do the sample cards show real municipal relevance?
- **Classification**: Do Austin's pillars provide useful categorization?
- **Metrics**: Are the 7 scoring dimensions meaningful?
- **Timeline**: Is the evolution tracking useful?

### Visual Design

- **Professional Appearance**: Suitable for city government use?
- **Color Coding**: Strategic pillar colors work well?
- **Typography**: Readable and professional?
- **Layout**: Good use of screen space?

### Mobile Experience

- **Responsive Design**: Works on tablets and phones?
- **Touch Interface**: Easy to navigate on mobile?
- **Information Density**: Appropriate for smaller screens?

## 🔍 Key Questions to Consider

### Workflow Value

1. Does the "Pokémon cards" concept work for strategic research?
2. Would this save time compared to manual research?
3. Is the workstream concept useful for strategic planning?
4. Do the scoring metrics provide meaningful insights?

### Austin Context

1. Do the strategic pillars align with Austin's priorities?
2. Are the sample cards relevant to municipal operations?
3. Would city staff find this valuable for planning?
4. Does the interface feel appropriate for government use?

### Technical Usability

1. Is the interface intuitive for non-technical users?
2. Do the filters and search work as expected?
3. Is the following system easy to understand?
4. Are there any confusing workflows or terminology?

## 🚨 Common Issues & Solutions

### Backend Won't Start

```bash
# Check Python version
python3 --version

# Recreate virtual environment
cd backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend Won't Start

```bash
# Check Node.js version
node --version
pnpm --version

# Reinstall dependencies
cd frontend/foresight-frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### Can't Connect to Database

- Verify Supabase URL and keys in `.env` files
- Check that database migrations were run
- Ensure Supabase project is active

### Login Issues

- Run `python create_test_user.py` to create credentials
- Check that Supabase authentication is enabled
- Verify environment variables are correct

## 📝 Feedback Collection

As you test, note:

### ✅ What's Working Well

- Intuitive features or workflows
- Useful information or insights
- Professional appearance
- Time-saving functionality

### ❌ Areas for Improvement

- Confusing navigation or terminology
- Missing features or information
- Visual design issues
- Performance problems

### 💡 Enhancement Ideas

- Additional features that would add value
- Improved workflows or processes
- Better visualization of information
- Integration with existing tools

## 🎯 Ready for Production

Once testing is complete:

- All code is production-ready
- Database schema is optimized
- Security policies are in place
- Deployment to HuggingFace Spaces is straightforward

The system is designed to seamlessly transfer from local testing to cloud deployment when you're satisfied with the design and functionality!
