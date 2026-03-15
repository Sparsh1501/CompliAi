@echo off
REM CompliAI - Local Development Setup Script for Windows
REM This script sets up and starts the complete application locally

echo ============================================
echo   CompliAI - Local Setup ^& Start
echo ============================================
echo.

REM Step 1: Check Prerequisites
echo Step 1: Checking prerequisites...

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3 is not installed. Please install Python 3.11 or higher.
    exit /b 1
)
echo [OK] Python 3 found

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed. Please install Node.js 18 or higher.
    exit /b 1
)
echo [OK] Node.js found

REM Check Yarn
yarn --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Yarn not found. Installing yarn...
    npm install -g yarn
)
echo [OK] Yarn found

echo.

REM Step 2: Setup MongoDB
echo Step 2: Setting up MongoDB...
echo Please ensure MongoDB is running on localhost:27017
echo (You can use Docker: docker-compose up -d mongodb)
echo.
pause

REM Step 3: Setup Backend
echo Step 3: Setting up backend...
cd backend

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install Python dependencies
echo Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
echo [OK] Backend dependencies installed

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found in backend/
    set /p copy_env="Do you want to copy from .env.example? (y/n): "
    if "%copy_env%"=="y" (
        copy .env.example .env
        echo [OK] Created .env from .env.example
        echo.
        echo IMPORTANT: Edit backend\.env and add your API keys!
        echo.
        echo Required API Keys:
        echo   - OPENAI_API_KEY (get from platform.openai.com)
        echo   - ANTHROPIC_API_KEY (get from console.anthropic.com)
        echo   - GOOGLE_API_KEY (get from aistudio.google.com)
        echo.
        pause
    )
)

REM Replace old multi_llm_service.py with new one
if exist "services\multi_llm_service_new.py" (
    echo Updating multi_llm_service.py...
    move services\multi_llm_service.py services\multi_llm_service_old.py.backup
    move services\multi_llm_service_new.py services\multi_llm_service.py
    echo [OK] Updated LLM service to use direct SDKs
)

cd ..

echo.

REM Step 4: Setup Frontend
echo Step 4: Setting up frontend...
cd frontend

REM Install frontend dependencies
echo Installing frontend dependencies...
call yarn install
echo [OK] Frontend dependencies installed

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found in frontend/
    set /p copy_frontend_env="Do you want to copy from .env.example? (y/n): "
    if "%copy_frontend_env%"=="y" (
        copy .env.example .env
        echo [OK] Created frontend\.env from .env.example
    )
)

cd ..

echo.

REM Step 5: Start the application
echo Step 5: Starting the application...
echo.
echo [OK] Setup complete! Starting services...
echo.
echo ============================================
echo   Starting CompliAI Services
echo ============================================
echo.
echo Backend will be available at: http://localhost:8000
echo Frontend will be available at: http://localhost:3000
echo API Documentation: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop services
echo.

REM Start backend in new window
cd backend
start "CompliAI Backend" cmd /k "venv\Scripts\activate.bat && python server.py"

REM Wait a bit for backend to start
timeout /t 3 /nobreak

REM Start frontend in new window
cd ..\frontend
start "CompliAI Frontend" cmd /k "yarn start"

echo.
echo [OK] Services started in separate windows
echo Close the windows to stop the services
echo.
pause
