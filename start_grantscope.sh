#!/bin/bash

echo "Starting GrantScope2 System..."
echo "=============================="

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "ERROR: Please run this script from the project root directory"
    exit 1
fi

# Check Docker infrastructure is running
if ! docker compose ps --status running 2>/dev/null | grep -q "grantscope-gateway"; then
    echo "Docker infrastructure not running. Starting it..."
    docker compose up -d
    echo "Waiting for services to be healthy..."
    sleep 10
fi

# Start backend in background
echo "Starting backend on port 8000..."
cd backend

# Activate virtual environment and start backend
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: Virtual environment not found. Run setup_local.sh first."
    exit 1
fi

# Start backend in background
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

# Start worker in background (executes long-running jobs like deep research)
echo "Starting background worker..."
nohup python -m app.worker > ../worker.log 2>&1 &
WORKER_PID=$!
echo "Worker started with PID: $WORKER_PID"

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Check if backend is responding
if curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo "Backend is running successfully"
else
    echo "Backend failed to start. Check backend.log for errors."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Start frontend
echo "Starting frontend on port 5173..."
cd ../frontend/foresight-frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "ERROR: Node.js dependencies not found. Run setup_local.sh first."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "GrantScope2 System Started!"
echo "==========================="
echo ""
echo "Access Points:"
echo "   Frontend:    http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo "   API Docs:    http://localhost:8000/docs"
echo "   API Gateway: http://localhost:3000 (PostgREST + GoTrue)"
echo "   SearXNG:     http://localhost:8888"
echo ""
echo "Test User Credentials:"
echo "   Email: test@grantscope.austintexas.gov"
echo "   Password: TestPassword123!"
echo ""
echo "Press Ctrl+C to stop backend and frontend"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $WORKER_PID 2>/dev/null
    echo "All services stopped"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Start frontend (this will block)
pnpm dev

# Cleanup will be called when frontend stops
cleanup
