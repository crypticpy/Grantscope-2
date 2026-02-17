#!/bin/bash

echo "🎯 Starting GrantScope2 System..."
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
