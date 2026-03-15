from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Header
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List, Optional
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

from models import (
    User, UserCreate, UserLogin, Policy, PolicyCreate, Regulation, RegulationCreate,
    GapAnalysisResult, Task, TaskCreate, Evidence, EvidenceCreate, DashboardStats,
    Clause, Gap, SeverityLevel, TaskStatus, PolicyStatus
)
from services.document_service import DocumentService
from services.llm_service import LLMService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'compliance_db')]

JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'

app = FastAPI()
api_router = APIRouter(prefix="/api")

doc_service = DocumentService()
llm_service = LLMService()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_token(user_id: str, email: str) -> str:
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.split(' ')[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = bcrypt.hashpw(user_data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    user = User(
        email=user_data.email,
        password_hash=password_hash,
        full_name=user_data.full_name,
        organization=user_data.organization
    )
    
    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    await db.users.insert_one(user_dict)
    
    token = create_token(user.id, user.email)
    
    return {
        "message": "User registered successfully",
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "organization": user.organization
        }
    }

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(credentials.password.encode('utf-8'), user_doc['password_hash'].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user_doc['id'], user_doc['email'])
    
    return {
        "token": token,
        "user": {
            "id": user_doc['id'],
            "email": user_doc['email'],
            "full_name": user_doc['full_name'],
            "organization": user_doc['organization']
        }
    }

@api_router.get("/policies", response_model=List[Policy])
async def get_policies(current_user: dict = Depends(get_current_user)):
    policies = await db.policies.find({"user_id": current_user['user_id']}, {"_id": 0}).to_list(1000)
    for policy in policies:
        if isinstance(policy.get('created_at'), str):
            policy['created_at'] = datetime.fromisoformat(policy['created_at'])
        if isinstance(policy.get('updated_at'), str):
            policy['updated_at'] = datetime.fromisoformat(policy['updated_at'])
    return policies

@api_router.post("/policies/upload")
async def upload_policy(
    file: UploadFile = File(...),
    policy_data: str = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        import json
        policy_info = json.loads(policy_data) if policy_data else {}
        
        file_content = await file.read()
        file_path = await doc_service.save_file(file_content, file.filename)
        
        text = await doc_service.extract_text_from_pdf(file_path)
        clauses_data = await doc_service.extract_clauses_simple(text, "policy")
        
        clauses = [Clause(**clause_data) for clause_data in clauses_data]
        
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        policy = Policy(
            title=policy_info.get('title', file.filename),
            policy_type=policy_info.get('policy_type', 'Other'),
            file_url=file_path,
            file_name=file.filename,
            clauses=clauses,
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default')
        )
        
        policy_dict = policy.model_dump()
        policy_dict['created_at'] = policy_dict['created_at'].isoformat()
        policy_dict['updated_at'] = policy_dict['updated_at'].isoformat()
        
        await db.policies.insert_one(policy_dict)
        
        return {
            "message": "Policy uploaded successfully",
            "policy_id": policy.id,
            "clauses_extracted": len(clauses)
        }
    except Exception as e:
        logger.error(f"Error uploading policy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.get("/policies/{policy_id}", response_model=Policy)
async def get_policy(policy_id: str, current_user: dict = Depends(get_current_user)):
    policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    if isinstance(policy.get('created_at'), str):
        policy['created_at'] = datetime.fromisoformat(policy['created_at'])
    if isinstance(policy.get('updated_at'), str):
        policy['updated_at'] = datetime.fromisoformat(policy['updated_at'])
    
    return policy

@api_router.get("/regulations", response_model=List[Regulation])
async def get_regulations(current_user: dict = Depends(get_current_user)):
    regulations = await db.regulations.find({"user_id": current_user['user_id']}, {"_id": 0}).to_list(1000)
    for reg in regulations:
        if isinstance(reg.get('created_at'), str):
            reg['created_at'] = datetime.fromisoformat(reg['created_at'])
        if reg.get('issued_date') and isinstance(reg['issued_date'], str):
            reg['issued_date'] = datetime.fromisoformat(reg['issued_date'])
    return regulations

@api_router.post("/regulations/upload")
async def upload_regulation(
    file: UploadFile = File(...),
    regulation_data: str = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        import json
        reg_info = json.loads(regulation_data) if regulation_data else {}
        
        file_content = await file.read()
        file_path = await doc_service.save_file(file_content, file.filename)
        
        text = await doc_service.extract_text_from_pdf(file_path)
        clauses_data = await doc_service.extract_clauses_simple(text, "regulation")
        
        clauses = [Clause(**clause_data) for clause_data in clauses_data]
        
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        regulation = Regulation(
            title=reg_info.get('title', file.filename),
            regulatory_body=reg_info.get('regulatory_body', 'RBI'),
            circular_number=reg_info.get('circular_number'),
            file_url=file_path,
            file_name=file.filename,
            clauses=clauses,
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default')
        )
        
        reg_dict = regulation.model_dump()
        reg_dict['created_at'] = reg_dict['created_at'].isoformat()
        if reg_dict.get('issued_date'):
            reg_dict['issued_date'] = reg_dict['issued_date'].isoformat()
        
        await db.regulations.insert_one(reg_dict)
        
        return {
            "message": "Regulation uploaded successfully",
            "regulation_id": regulation.id,
            "clauses_extracted": len(clauses)
        }
    except Exception as e:
        logger.error(f"Error uploading regulation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.post("/gap-analysis/run")
async def run_gap_analysis(
    policy_id: str,
    regulation_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
        regulation = await db.regulations.find_one({"id": regulation_id, "user_id": current_user['user_id']}, {"_id": 0})
        
        if not policy or not regulation:
            raise HTTPException(status_code=404, detail="Policy or regulation not found")
        
        policy_clauses = policy.get('clauses', [])
        regulation_clauses = regulation.get('clauses', [])
        
        gaps = []
        total_analyzed = min(len(regulation_clauses), 10)
        
        for i, reg_clause in enumerate(regulation_clauses[:10]):
            if i < len(policy_clauses):
                gap_data = await llm_service.analyze_gap(
                    policy_clauses[i].get('text', ''),
                    reg_clause.get('text', '')
                )
                
                gap = Gap(
                    gap_type=gap_data.get('gap_type', 'unknown'),
                    severity=gap_data.get('severity', 'Medium'),
                    confidence_score=gap_data.get('confidence_score', 0.5),
                    policy_clause=Clause(**policy_clauses[i]) if policy_clauses[i] else None,
                    regulation_clause=Clause(**reg_clause),
                    description=gap_data.get('description', 'Gap identified'),
                    suggested_fix=gap_data.get('suggested_fix', 'Review required')
                )
                gaps.append(gap)
        
        compliant_gaps = [g for g in gaps if g.gap_type == 'compliant']
        compliance_score = (len(compliant_gaps) / total_analyzed * 100) if total_analyzed > 0 else 0
        
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        result = GapAnalysisResult(
            policy_id=policy_id,
            regulation_id=regulation_id,
            gaps=gaps,
            compliance_score=compliance_score,
            total_clauses_analyzed=total_analyzed,
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default')
        )
        
        result_dict = result.model_dump()
        result_dict['created_at'] = result_dict['created_at'].isoformat()
        
        await db.gap_analyses.insert_one(result_dict)
        
        return {
            "message": "Gap analysis completed",
            "result_id": result.id,
            "compliance_score": compliance_score,
            "total_gaps": len(gaps),
            "critical_gaps": len([g for g in gaps if g.severity == SeverityLevel.CRITICAL]),
            "gaps": [gap.model_dump() for gap in gaps]
        }
    except Exception as e:
        logger.error(f"Error in gap analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@api_router.get("/tasks", response_model=List[Task])
async def get_tasks(current_user: dict = Depends(get_current_user)):
    tasks = await db.tasks.find({"user_id": current_user['user_id']}, {"_id": 0}).to_list(1000)
    for task in tasks:
        if isinstance(task.get('created_at'), str):
            task['created_at'] = datetime.fromisoformat(task['created_at'])
        if isinstance(task.get('updated_at'), str):
            task['updated_at'] = datetime.fromisoformat(task['updated_at'])
        if task.get('due_date') and isinstance(task['due_date'], str):
            task['due_date'] = datetime.fromisoformat(task['due_date'])
    return tasks

@api_router.post("/tasks", response_model=Task)
async def create_task(task_data: TaskCreate, current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    task = Task(
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        assigned_to=task_data.assigned_to,
        gap_id=task_data.gap_id,
        policy_id=task_data.policy_id,
        due_date=task_data.due_date,
        user_id=current_user['user_id'],
        organization=user_doc.get('organization', 'Default')
    )
    
    task_dict = task.model_dump()
    task_dict['created_at'] = task_dict['created_at'].isoformat()
    task_dict['updated_at'] = task_dict['updated_at'].isoformat()
    if task_dict.get('due_date'):
        task_dict['due_date'] = task_dict['due_date'].isoformat()
    
    await db.tasks.insert_one(task_dict)
    return task

@api_router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    status: Optional[TaskStatus] = None,
    assigned_to: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    update_data = {}
    if status:
        update_data['status'] = status
    if assigned_to is not None:
        update_data['assigned_to'] = assigned_to
    
    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    result = await db.tasks.update_one(
        {"id": task_id, "user_id": current_user['user_id']},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task updated successfully"}

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    total_policies = await db.policies.count_documents({"user_id": current_user['user_id']})
    total_regulations = await db.regulations.count_documents({"user_id": current_user['user_id']})
    total_tasks = await db.tasks.count_documents({"user_id": current_user['user_id']})
    open_tasks = await db.tasks.count_documents({"user_id": current_user['user_id'], "status": TaskStatus.OPEN})
    
    latest_analysis = await db.gap_analyses.find_one(
        {"user_id": current_user['user_id']},
        {"_id": 0, "compliance_score": 1, "gaps": 1},
        sort=[('created_at', -1)]
    )
    
    compliance_score = latest_analysis.get('compliance_score', 0.0) if latest_analysis else 0.0
    critical_gaps = 0
    if latest_analysis and latest_analysis.get('gaps'):
        critical_gaps = len([g for g in latest_analysis['gaps'] if g.get('severity') == 'Critical'])
    
    high_priority_tasks = await db.tasks.count_documents({
        "user_id": current_user['user_id'],
        "priority": SeverityLevel.HIGH
    })
    
    return DashboardStats(
        total_policies=total_policies,
        total_regulations=total_regulations,
        total_tasks=total_tasks,
        open_tasks=open_tasks,
        compliance_score=compliance_score,
        critical_gaps=critical_gaps,
        high_priority_tasks=high_priority_tasks
    )

@api_router.get("/")
async def root():
    return {"message": "CompliAI API"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
