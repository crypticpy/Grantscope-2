#!/bin/bash

echo "🎯 Starting Foresight System..."
echo "=============================="

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Start backend in background
echo "🐍 Starting backend on port 8000..."
cd backend

# Activate virtual environment and start backend
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run setup_local.sh first."
    exit 1
fi

# Start backend in background
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 5

# Check if backend is responding
if curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo "✅ Backend is running successfully"
else
    echo "❌ Backend failed to start. Check backend.log for errors."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Start frontend
echo "⚛️  Starting frontend on port 5173..."
cd ../frontend/foresight-frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "❌ Node.js dependencies not found. Run setup_local.sh first."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "🚀 Foresight System Started!"
echo "==========================="
echo ""
echo "🔗 Access Points:"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "👤 Test User Credentials:"
echo "   Email: test@foresight.austintexas.gov"
echo "   Password: TestPassword123!"
echo ""
echo "🛑 Press Ctrl+C to stop both services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Start frontend (this will block)
npm run dev

# Cleanup will be called when frontend stops
cleanup
