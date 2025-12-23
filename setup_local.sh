#!/bin/bash

# Foresight System - Local Development Setup
# This script sets up the complete system for local testing

echo "🎯 Foresight System - Local Development Setup"
echo "============================================="

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

echo ""
echo "📋 Prerequisites Check:"
echo "- Python 3.11+ installed ✓"
echo "- Node.js 18+ installed ✓" 
echo "- Supabase account created ✓"
echo "- OpenAI API key obtained ✓"
echo ""

# Backend setup
echo "🐍 Setting up Backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "🔑 Setting up environment variables..."
    echo "Please provide your credentials:"
    
    read -p "Supabase Project URL: " SUPABASE_URL
    read -p "Supabase Anon Key: " SUPABASE_ANON_KEY
    read -p "Supabase Service Key: " SUPABASE_SERVICE_KEY
    read -p "OpenAI API Key: " OPENAI_API_KEY
    
    cat > .env << EOF
# Supabase Configuration
SUPABASE_URL=$SUPABASE_URL
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY

# OpenAI Configuration
OPENAI_API_KEY=$OPENAI_API_KEY

# Optional: NewsAPI for content fetching
NEWSAPI_KEY=
EOF
    
    echo "✅ .env file created with your credentials"
fi

echo "✅ Backend setup complete!"
echo ""

# Frontend setup
echo "⚛️  Setting up Frontend..."
cd ../frontend/foresight-frontend

# Install dependencies
echo "Installing Node.js dependencies..."
pnpm install

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "📡 Setting up frontend environment..."
    read -p "Supabase Project URL (same as backend): " SUPABASE_URL
    read -p "Supabase Anon Key (same as backend): " SUPABASE_ANON_KEY
    
    cat > .env << EOF
# Supabase Configuration
VITE_SUPABASE_URL=$SUPABASE_URL
VITE_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY

# API Configuration
VITE_API_URL=http://localhost:8000
EOF
    
    echo "✅ Frontend .env file created"
fi

echo "✅ Frontend setup complete!"
echo ""

# Create start script
echo "🚀 Creating start script..."
cat > start_foresight.sh << 'EOF'
#!/bin/bash

echo "🎯 Starting Foresight System..."
echo "=============================="

# Start backend in background
echo "🐍 Starting backend on port 8000..."
cd backend
source venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# Start frontend
echo "⚛️  Starting frontend on port 5173..."
cd ../frontend/foresight-frontend
echo "Frontend will be available at: http://localhost:5173"
echo ""
echo "🔗 Quick Access Links:"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo "   Backend Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"

# Start frontend (this will block)
npm run dev

# Cleanup: Kill backend when frontend stops
echo "🛑 Stopping backend..."
kill $BACKEND_PID
EOF

chmod +x start_foresight.sh

echo ""
echo "🎉 Setup Complete!"
echo "================="
echo ""
echo "📁 Project Structure:"
echo "   /backend/ - FastAPI backend with AI pipeline"
echo "   /frontend/foresight-frontend/ - React frontend"
echo ""
echo "🚀 To Start the System:"
echo "   ./start_foresight.sh"
echo ""
echo "🔗 After Starting:"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo ""
echo "👤 Test User Credentials:"
echo "   After first run, create a test user using:"
echo "   python create_test_user.py"
echo ""
echo "Happy Testing! 🎯"
