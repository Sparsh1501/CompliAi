# CompliAI - AI Compliance Management Platform

**India's First AI-Native Compliance Operating System**

Automate RBI, FIU-IND, NPCI, and Digital Lending compliance for NBFCs, FinTechs, Payment Aggregators, and Digital Lenders.

## 🎯 Overview

CompliAI enables financial institutions to maintain continuous compliance without large compliance teams by automating:
- Policy & regulation interpretation
- Clause-level gap analysis
- Evidence collection & validation
- Audit readiness
- Task management

## 🚀 Features

### Core Modules (MVP)

#### 1. Policy & Document Management
- Upload policies via UI (PDF support)
- Automatic clause extraction using AI
- Version control (Draft → Review → Approve → Archive)
- Policy types: KYC, AML, Digital Lending, InfoSec, Outsourcing, Risk Management, etc.

#### 2. Regulation Repository
- Upload RBI/FIU/NPCI circulars
- Auto-summarization and clause extraction
- Historical archive
- Search and filter capabilities

#### 3. AI Gap Analysis Engine ⭐
- **Semantic clause-to-clause matching** using LLM
- Identifies:
  - Missing clauses
  - Weak clauses
  - Conflicting clauses
  - Compliant sections
- Provides:
  - Severity scores (Critical/High/Medium/Low)
  - Confidence scores
  - AI-suggested remediation
  - Legal citations

#### 4. Task Management
- Auto-generate tasks from gap analysis
- Assign to team members
- SLA tracking
- Priority management
- Status tracking (Open → In Progress → Completed)

#### 5. Dashboard & Analytics
- Compliance score overview
- Critical gaps heatmap
- Policy coverage metrics
- Task completion rates
- Real-time alerts

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: MongoDB (document storage)
- **AI/LLM**: Anthropic LLM Key 
- **Document Processing**: PyPDF2
- **Authentication**: JWT + bcrypt

### Frontend
- **Framework**: React 19
- **UI Components**: Shadcn/UI (Radix UI)
- **Styling**: Tailwind CSS
- **Routing**: React Router v7
- **State Management**: React Context
- **HTTP Client**: Axios

### Deployment
- **Container**: Kubernetes
- **Process Manager**: Supervisor
- **Hot Reload**: Enabled for both frontend & backend

## 📋 Prerequisites

- Node.js 18+ and Yarn
- Python 3.11+
- MongoDB 4.4+
- 4GB+ RAM

## 🔧 Local Setup

### 1. Clone and Navigate
```bash
cd /app
```

### 2. Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Environment variables are already configured in .env
# Key variables:
# - MONGO_URL: MongoDB connection
# - EMERGENT_LLM_KEY: AI model access key
# - JWT_SECRET: Authentication secret

# Start backend (managed by supervisor)
sudo supervisorctl restart backend
```

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies (already done)
yarn install

# Environment variables in .env:
# - REACT_APP_BACKEND_URL: Backend API URL

# Start frontend (managed by supervisor)
sudo supervisorctl restart frontend
```


## 📱 Usage Guide

### Step 1: Register/Login
1. Navigate to the application
2. Register with:
   - Full Name
   - Email
   - Organization (NBFC/FinTech name)
   - Password
3. Or login with existing credentials

### Step 2: Upload Policy Document
1. Go to **Policies** page
2. Click **Upload Policy**
3. Fill in:
   - Policy Title (e.g., "KYC Policy 2025")
   - Policy Type (KYC/AML/Digital Lending/etc.)
   - Upload PDF file
4. System automatically extracts clauses

### Step 3: Upload Regulation
1. Go to **Regulations** page
2. Click **Upload Regulation**
3. Fill in:
   - Regulation Title (e.g., "RBI KYC Master Directions")
   - Regulatory Body (RBI/FIU/NPCI)
   - Circular Number (optional)
   - Upload PDF file
4. System extracts regulation clauses

### Step 4: Run Gap Analysis
1. Go to **Gap Analysis** page
2. Select Policy from dropdown
3. Select Regulation from dropdown
4. Click **Run AI Gap Analysis**
5. Wait 10-30 seconds for AI processing
6. View results:
   - Compliance Score
   - List of gaps with severity
   - AI-suggested fixes for each gap

### Step 5: Create Tasks
1. Go to **Tasks** page
2. Click **Create Task**
3. Fill in:
   - Task Title
   - Description
   - Priority (Critical/High/Medium/Low)
   - Assigned To (optional)
4. Track task status

## 🎨 Design System

### Theme: "Swiss Compliance"
- **Archetype**: High-contrast, precision-focused
- **Palette**: Slate/Monochrome base with functional colors
- **Typography**: 
  - Headings: Outfit (modern, technical)
  - Body: Inter (reliable, readable)
  - Code: JetBrains Mono (for clauses/regulations)

### Colors
- **Success**: Emerald (#10B981)
- **Warning**: Amber (#F59E0B)
- **Error**: Red (#EF4444)
- **AI Magic**: Indigo (#6366F1)

### Theme Configuration
Theme is fully configurable via CSS variables in `/frontend/src/index.css`:
```css
:root {
  --primary: #0F172A;
  --background: #F8FAFC;
  /* ... more variables */
}
```

## 🔐 Security Features

- JWT-based authentication
- bcrypt password hashing
- Multi-tenancy with organization isolation
- Role-based access control (RBAC) ready
- Audit logs for all actions
- Secure file upload handling

## 📊 API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login

### Policies
- `GET /api/policies` - List all policies
- `GET /api/policies/{id}` - Get policy details
- `POST /api/policies/upload` - Upload policy document

### Regulations
- `GET /api/regulations` - List all regulations
- `POST /api/regulations/upload` - Upload regulation document

### Gap Analysis
- `POST /api/gap-analysis/run?policy_id={id}&regulation_id={id}` - Run analysis

### Tasks
- `GET /api/tasks` - List all tasks
- `POST /api/tasks` - Create task
- `PATCH /api/tasks/{id}` - Update task

### Dashboard
- `GET /api/dashboard/stats` - Get dashboard statistics

## 🧪 Testing

Test the API with curl:

```bash
# Get API URL
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Register
curl -X POST "$API_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","full_name":"Test User","organization":"Test Corp"}'

# Login and get token
TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}' | \
  python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Get dashboard stats
curl -X GET "$API_URL/api/dashboard/stats" \
  -H "Authorization: Bearer $TOKEN"
```

## 📁 Project Structure

```
/app/
├── backend/
│   ├── server.py              # Main FastAPI application
│   ├── models.py              # Pydantic models
│   ├── services/
│   │   ├── document_service.py   # PDF processing
│   │   └── llm_service.py        # AI/LLM integration
│   ├── .env                   # Environment variables
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/            # React pages
│   │   │   ├── Login.js
│   │   │   ├── Dashboard.js
│   │   │   ├── Policies.js
│   │   │   ├── Regulations.js
│   │   │   ├── GapAnalysis.js
│   │   │   └── Tasks.js
│   │   ├── components/       # Reusable components
│   │   │   ├── Layout.js
│   │   │   └── ui/          # Shadcn UI components
│   │   ├── context/         # React Context
│   │   │   └── AuthContext.js
│   │   ├── lib/            # Utilities
│   │   │   └── api.js      # API client
│   │   ├── App.js          # Main app component
│   │   ├── App.css         # App styles
│   │   └── index.css       # Global styles + theme
│   ├── .env                # Environment variables
│   └── package.json        # Node dependencies
└── design_guidelines.json  # Design system specs
```

## 🚀 Deployment

### Current Deployment
The application is deployed on Emergent's Kubernetes cluster with:
- Automatic SSL/TLS
- Hot reload for development
- Supervisor for process management
- MongoDB persistence

### Environment Variables

**Backend (.env):**
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=compliance_db
CORS_ORIGINS=*
EMERGENT_LLM_KEY=sk-emergent-xxxx
JWT_SECRET=your-secret-key
```

**Frontend (.env):**
```env
REACT_APP_BACKEND_URL=https://finreg-ai.preview.emergentagent.com
```

## 🔄 Development Workflow

### Hot Reload
Both frontend and backend have hot reload enabled:
- Edit any Python file → Backend auto-reloads
- Edit any React file → Frontend auto-reloads

### Restart Services (Only needed for .env changes)
```bash
# Restart backend
sudo supervisorctl restart backend

# Restart frontend
sudo supervisorctl restart frontend

# Check status
sudo supervisorctl status
```

### View Logs
```bash
# Backend logs
tail -f /var/log/supervisor/backend.err.log

# Frontend logs
tail -f /var/log/supervisor/frontend.err.log
```

## 🎯 Roadmap

### Phase 2 (Next Steps)
- [ ] Evidence Management with OCR
- [ ] LOS/LMS Data Integration
- [ ] Automated RBI circular scraping
- [ ] Vector database (Qdrant) integration
- [ ] Advanced embeddings for semantic search
- [ ] Bulk task creation from gaps
- [ ] Email/Slack notifications
- [ ] Audit report generation (PDF export)
- [ ] Advanced RBAC with team management

### Phase 3 (Future)
- [ ] Real-time regulatory update tracking
- [ ] Chatbot for compliance queries
- [ ] Integration with JIRA/Confluence
- [ ] Mobile app (React Native)
- [ ] Multi-language support
- [ ] Compliance score trends over time
- [ ] Automated policy suggestions


