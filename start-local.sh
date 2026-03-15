#!/bin/bash

# CompliAI - Local Development Setup Script
# This script sets up and starts the complete application locally

set -e  # Exit on error

echo "============================================"
echo "  CompliAI - Local Setup & Start"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Step 1: Check Prerequisites
echo "Step 1: Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi
print_success "Python 3 found: $(python3 --version)"

# Check Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js 18 or higher."
    exit 1
fi
print_success "Node.js found: $(node --version)"

# Check Yarn
if ! command -v yarn &> /dev/null; then
    print_error "Yarn is not installed. Installing yarn..."
    npm install -g yarn
fi
print_success "Yarn found: $(yarn --version)"

# Check Docker (optional)
if command -v docker &> /dev/null; then
    print_success "Docker found: $(docker --version)"
    DOCKER_AVAILABLE=true
else
    print_warning "Docker not found. You'll need to install MongoDB separately."
    DOCKER_AVAILABLE=false
fi

echo ""

# Step 2: Setup MongoDB
echo "Step 2: Setting up MongoDB..."

if [ "$DOCKER_AVAILABLE" = true ]; then
    read -p "Do you want to start MongoDB using Docker? (y/n): " start_docker
    if [ "$start_docker" = "y" ]; then
        echo "Starting MongoDB with Docker Compose..."
        docker-compose up -d mongodb
        sleep 5
        print_success "MongoDB started in Docker"
    else
        print_warning "Please ensure MongoDB is running on localhost:27017"
    fi
else
    print_warning "Please ensure MongoDB is running on localhost:27017"
fi

echo ""

# Step 3: Setup Backend
echo "Step 3: Setting up backend..."

cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Backend dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found in backend/"
    read -p "Do you want to copy from .env.example? (y/n): " copy_env
    if [ "$copy_env" = "y" ]; then
        cp .env.example .env
        print_success "Created .env from .env.example"
        print_warning "IMPORTANT: Edit backend/.env and add your API keys!"
        echo ""
        echo "Required API Keys:"
        echo "  - OPENAI_API_KEY (get from platform.openai.com)"
        echo "  - ANTHROPIC_API_KEY (get from console.anthropic.com)"
        echo "  - GOOGLE_API_KEY (get from aistudio.google.com)"
        echo ""
        read -p "Press Enter after you've added your API keys to backend/.env..."
    else
        print_error "Backend .env file is required. Exiting."
        exit 1
    fi
fi

# Replace old multi_llm_service.py with new one
if [ -f "services/multi_llm_service_new.py" ]; then
    echo "Updating multi_llm_service.py..."
    mv services/multi_llm_service.py services/multi_llm_service_old.py.backup
    mv services/multi_llm_service_new.py services/multi_llm_service.py
    print_success "Updated LLM service to use direct SDKs"
fi

cd ..

echo ""

# Step 4: Setup Frontend
echo "Step 4: Setting up frontend..."

cd frontend

# Install frontend dependencies
echo "Installing frontend dependencies..."
yarn install
print_success "Frontend dependencies installed"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found in frontend/"
    read -p "Do you want to copy from .env.example? (y/n): " copy_frontend_env
    if [ "$copy_frontend_env" = "y" ]; then
        cp .env.example .env
        print_success "Created frontend/.env from .env.example"
    fi
fi

cd ..

echo ""

# Step 5: Start the application
echo "Step 5: Starting the application..."
echo ""

print_success "Setup complete! Starting services..."
echo ""
echo "============================================"
echo "  Starting CompliAI Services"
echo "============================================"
echo ""
echo "Backend will be available at: http://localhost:8000"
echo "Frontend will be available at: http://localhost:3000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    print_info "Stopping services..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    print_success "Services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend in background
cd backend
source venv/bin/activate
python server.py &
BACKEND_PID=$!
print_success "Backend started (PID: $BACKEND_PID)"

# Wait a bit for backend to start
sleep 3

# Start frontend in background
cd ../frontend
yarn start &
FRONTEND_PID=$!
print_success "Frontend started (PID: $FRONTEND_PID)"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
