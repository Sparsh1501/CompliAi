#!/bin/bash
set -e

# CompliAI Development Environment Setup Script
# ===============================================
# This script sets up and starts the complete development environment.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================="
echo "  CompliAI - Development Environment Setup"
echo "============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Check Docker Compose
if ! docker compose version &> /dev/null && ! docker-compose version &> /dev/null; then
    echo -e "${RED}ERROR: Docker Compose is not installed.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose found${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 is not installed. Please install Python 3.11+.${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}ERROR: Node.js is not installed. Please install Node.js 18+.${NC}"
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "${GREEN}✓ Node.js $NODE_VERSION found${NC}"

echo ""
echo "Starting infrastructure services..."
echo "--------------------------------------------"

# Start Docker containers (MongoDB + Qdrant + Mongo Express)
docker compose up -d

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
for i in $(seq 1 30); do
    if docker exec compliai-mongodb mongosh --eval "db.runCommand('ping').ok" --quiet 2>/dev/null | grep -q 1; then
        echo -e "${GREEN}✓ MongoDB is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}ERROR: MongoDB failed to start within 30 seconds${NC}"
        exit 1
    fi
    sleep 1
done

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to be ready..."
for i in $(seq 1 30); do
    if curl -s http://localhost:6333/healthz 2>/dev/null | grep -q "ok\|true"; then
        echo -e "${GREEN}✓ Qdrant is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}WARNING: Qdrant may not be ready yet. Continuing...${NC}"
    fi
    sleep 1
done

echo ""
echo "Setting up backend..."
echo "--------------------------------------------"

# Setup Python virtual environment and install dependencies
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install deps
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}NOTE: Created .env from .env.example. Please update with your API keys.${NC}"
    fi
fi

echo -e "${GREEN}✓ Backend dependencies installed${NC}"

echo ""
echo "Setting up frontend..."
echo "--------------------------------------------"

cd "$SCRIPT_DIR/frontend"

# Install frontend dependencies
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    if command -v yarn &> /dev/null; then
        yarn install --frozen-lockfile 2>/dev/null || yarn install
    else
        npm install
    fi
fi
echo -e "${GREEN}✓ Frontend dependencies installed${NC}"

echo ""
echo "Starting application servers..."
echo "--------------------------------------------"

# Start backend server
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
echo "Starting FastAPI backend on port 8000..."
uvicorn server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Start frontend dev server
cd "$SCRIPT_DIR/frontend"
echo "Starting React frontend on port 3000..."
if command -v yarn &> /dev/null; then
    yarn start &
else
    npm start &
fi
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait for servers to start
echo ""
echo "Waiting for servers to start..."
sleep 5

echo ""
echo "============================================="
echo -e "${GREEN}  CompliAI is starting up!${NC}"
echo "============================================="
echo ""
echo "  Services:"
echo "  -----------------------------------------"
echo "  Frontend:      http://localhost:3000"
echo "  Backend API:   http://localhost:8000"
echo "  API Docs:      http://localhost:8000/docs"
echo "  MongoDB:       localhost:27017"
echo "  Mongo Express: http://localhost:8081"
echo "  Qdrant:        http://localhost:6333"
echo "  Qdrant UI:     http://localhost:6333/dashboard"
echo ""
echo "  Credentials:"
echo "  -----------------------------------------"
echo "  MongoDB:       admin / compliai123"
echo "  Mongo Express: admin / admin123"
echo ""
echo "  Press Ctrl+C to stop all services."
echo "============================================="

# Handle cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "Application servers stopped."
    echo "Note: Docker containers (MongoDB, Qdrant) are still running."
    echo "Run 'docker compose down' to stop them."
}

trap cleanup EXIT INT TERM

# Wait for all background processes
wait
