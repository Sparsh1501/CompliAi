from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Header, Body
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

from models import *
from services.document_service import DocumentService
from services.multi_llm_service import MultiLLMService
from services.audit_service import AuditService
from services.evidence_service import EvidenceService

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
llm_service = MultiLLMService()
audit_service = AuditService()
evidence_service = EvidenceService()

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

# ========== AUTH ENDPOINTS ==========
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
        organization=user_data.organization,
        department=user_data.department
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

# ========== DEPARTMENT ENDPOINTS ==========
@api_router.get("/departments", response_model=List[Department])
async def get_departments(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    departments = await db.departments.find({"organization": user_doc.get('organization')}, {"_id": 0}).to_list(1000)
    
    for dept in departments:
        if isinstance(dept.get('created_at'), str):
            dept['created_at'] = datetime.fromisoformat(dept['created_at'])
    
    return departments

@api_router.post("/departments", response_model=Department)
async def create_department(dept_data: DepartmentCreate, current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    department = Department(
        name=dept_data.name,
        head_of_department=dept_data.head_of_department,
        organization=user_doc.get('organization', 'Default')
    )
    
    dept_dict = department.model_dump()
    dept_dict['created_at'] = dept_dict['created_at'].isoformat()
    
    await db.departments.insert_one(dept_dict)
    return department

# ========== POLICY ENDPOINTS ==========
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
            organization=user_doc.get('organization', 'Default'),
            department=policy_info.get('department')
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

# ========== REGULATION ENDPOINTS ==========
@api_router.get("/regulations", response_model=List[Regulation])
async def get_regulations(
    regulator: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {"user_id": current_user['user_id']}
    if regulator:
        query["regulatory_body"] = regulator
    
    regulations = await db.regulations.find(query, {"_id": 0}).to_list(1000)
    for reg in regulations:
        if isinstance(reg.get('created_at'), str):
            reg['created_at'] = datetime.fromisoformat(reg['created_at'])
        for date_field in ['issued_date', 'effective_date', 'due_date']:
            if reg.get(date_field) and isinstance(reg[date_field], str):
                reg[date_field] = datetime.fromisoformat(reg[date_field])
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
        
        # Use Claude for comprehensive analysis
        analysis = await llm_service.analyze_regulatory_circular_claude(text, reg_info.get('title', file.filename))
        
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
            summary=analysis.get('summary'),
            impact_organization=analysis.get('org_impact'),
            impact_technical=analysis.get('technical_impact'),
            impact_operational=analysis.get('operational_impact'),
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default'),
            is_master_circular=reg_info.get('is_master_circular', False)
        )
        
        reg_dict = regulation.model_dump()
        reg_dict['created_at'] = reg_dict['created_at'].isoformat()
        for date_field in ['issued_date', 'effective_date', 'due_date']:
            if reg_dict.get(date_field):
                reg_dict[date_field] = reg_dict[date_field].isoformat()
        
        await db.regulations.insert_one(reg_dict)
        
        # Auto-generate tasks from analysis
        if analysis.get('departments_affected'):
            for dept in analysis['departments_affected'][:3]:
                task = Task(
                    title=f"Review {regulation.title} impact on {dept}",
                    description=f"Assess and implement changes required by {regulation.circular_number or 'circular'}",
                    department=dept,
                    priority=SeverityLevel.HIGH,
                    circular_id=regulation.id,
                    user_id=current_user['user_id'],
                    organization=user_doc.get('organization', 'Default'),
                    auto_assigned=True
                )
                task_dict = task.model_dump()
                task_dict['created_at'] = task_dict['created_at'].isoformat()
                task_dict['updated_at'] = task_dict['updated_at'].isoformat()
                if task_dict.get('due_date'):
                    task_dict['due_date'] = task_dict['due_date'].isoformat()
                await db.tasks.insert_one(task_dict)
        
        return {
            "message": "Regulation uploaded and analyzed successfully",
            "regulation_id": regulation.id,
            "clauses_extracted": len(clauses),
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error uploading regulation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# ========== GAP ANALYSIS ENDPOINTS ==========
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
        total_analyzed = min(len(regulation_clauses), 15)  # Analyze more clauses
        
        for i, reg_clause in enumerate(regulation_clauses[:15]):
            if i < len(policy_clauses):
                # Use Claude for detailed gap analysis
                gap_data = await llm_service.analyze_gap_detailed(
                    policy_clauses[i].get('text', ''),
                    reg_clause.get('text', '')
                )
                
                gap = Gap(
                    gap_type=gap_data.get('gap_type', 'unknown'),
                    severity=gap_data.get('severity', 'Medium'),
                    confidence_score=gap_data.get('confidence_score', 0.5),
                    policy_clause=Clause(**policy_clauses[i]) if policy_clauses[i] else None,
                    regulation_clause=Clause(**reg_clause),
                    description=gap_data.get('explanation', 'Gap identified'),
                    suggested_fix=gap_data.get('suggested_fix', 'Review required'),
                    metadata={
                        "legal_citations": gap_data.get('legal_citations', []),
                        "risk_level": gap_data.get('risk_level', 'Moderate')
                    }
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
        
        # Auto-generate tasks for critical/high severity gaps
        non_compliant_gaps = [g for g in gaps if g.gap_type != 'compliant' and g.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]
        generated_tasks = await llm_service.generate_tasks_gpt(
            [g.model_dump() for g in non_compliant_gaps],
            {"policy": policy.get('title'), "regulation": regulation.get('title')}
        )
        
        tasks_created = 0
        for task_data in generated_tasks[:5]:
            task = Task(
                title=task_data.get('title', 'Address compliance gap'),
                description=task_data.get('description', 'Review and resolve'),
                priority=task_data.get('priority', SeverityLevel.MEDIUM),
                department=task_data.get('department'),
                policy_id=policy_id,
                user_id=current_user['user_id'],
                organization=user_doc.get('organization', 'Default'),
                auto_assigned=True
            )
            task_dict = task.model_dump()
            task_dict['created_at'] = task_dict['created_at'].isoformat()
            task_dict['updated_at'] = task_dict['updated_at'].isoformat()
            if task_dict.get('due_date'):
                task_dict['due_date'] = task_dict['due_date'].isoformat()
            await db.tasks.insert_one(task_dict)
            tasks_created += 1
        
        return {
            "message": "Gap analysis completed",
            "result_id": result.id,
            "compliance_score": compliance_score,
            "total_gaps": len(gaps),
            "critical_gaps": len([g for g in gaps if g.severity == SeverityLevel.CRITICAL]),
            "gaps": [gap.model_dump() for gap in gaps],
            "tasks_created": tasks_created
        }
    except Exception as e:
        logger.error(f"Error in gap analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# ========== EVIDENCE ENDPOINTS ==========
@api_router.post("/evidence/upload")
async def upload_evidence(
    file: UploadFile = File(...),
    evidence_data: str = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        import json
        ev_info = json.loads(evidence_data) if evidence_data else {}
        
        file_content = await file.read()
        file_path = await doc_service.save_file(file_content, file.filename)
        
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        evidence = Evidence(
            title=ev_info.get('title', file.filename),
            description=ev_info.get('description'),
            file_url=file_path,
            file_name=file.filename,
            policy_id=ev_info.get('policy_id'),
            clause_id=ev_info.get('clause_id'),
            control_id=ev_info.get('control_id'),
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default')
        )
        
        ev_dict = evidence.model_dump()
        ev_dict['created_at'] = ev_dict['created_at'].isoformat()
        
        await db.evidence.insert_one(ev_dict)
        
        return {
            "message": "Evidence uploaded successfully",
            "evidence_id": evidence.id
        }
    except Exception as e:
        logger.error(f"Error uploading evidence: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.post("/evidence/{evidence_id}/test")
async def test_evidence(
    evidence_id: str,
    requirement: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    try:
        evidence = await db.evidence.find_one({"id": evidence_id, "user_id": current_user['user_id']}, {"_id": 0})
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")
        
        # Evaluate using Gemini
        evaluation = await evidence_service.evaluate_evidence(evidence['file_url'], requirement)
        
        # Update evidence with evaluation
        await db.evidence.update_one(
            {"id": evidence_id},
            {"$set": {
                "ai_compliance_score": evaluation['compliance_score'],
                "validation_status": evaluation['validation_status'],
                "ai_validation_notes": evaluation['ai_validation_notes'],
                "feedback_good": evaluation['feedback_good'],
                "feedback_improvements": evaluation['feedback_improvements']
            }}
        )
        
        return evaluation
    except Exception as e:
        logger.error(f"Error testing evidence: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

@api_router.get("/evidence", response_model=List[Evidence])
async def get_evidence(current_user: dict = Depends(get_current_user)):
    evidence_list = await db.evidence.find({"user_id": current_user['user_id']}, {"_id": 0}).to_list(1000)
    for ev in evidence_list:
        if isinstance(ev.get('created_at'), str):
            ev['created_at'] = datetime.fromisoformat(ev['created_at'])
    return evidence_list

# ========== AUDIT ENDPOINTS ==========
@api_router.post("/audit/create", response_model=AuditSession)
async def create_audit_session(
    audit_data: AuditSessionCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        # Generate controls based on audit type
        if audit_data.audit_type == "external":
            controls = await audit_service.create_external_audit_controls("RBI", audit_data.scope)
        else:
            controls = await audit_service.create_external_audit_controls("RBI", audit_data.scope)
        
        audit_session = AuditSession(
            audit_type=audit_data.audit_type,
            scope=audit_data.scope,
            controls=controls,
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default')
        )
        
        audit_dict = audit_session.model_dump()
        audit_dict['created_at'] = audit_dict['created_at'].isoformat()
        if audit_dict.get('completed_at'):
            audit_dict['completed_at'] = audit_dict['completed_at'].isoformat()
        
        await db.audit_sessions.insert_one(audit_dict)
        
        return audit_session
    except Exception as e:
        logger.error(f"Error creating audit: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audit creation failed: {str(e)}")

@api_router.post("/audit/{audit_id}/run")
async def run_audit(
    audit_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        audit = await db.audit_sessions.find_one({"id": audit_id, "user_id": current_user['user_id']}, {"_id": 0})
        if not audit:
            raise HTTPException(status_code=404, detail="Audit session not found")
        
        # Get evidence for each control
        controls_evaluation = []
        for control in audit['controls']:
            # Find evidence for this control
            evidence_list = await db.evidence.find({
                "control_id": control['id'],
                "user_id": current_user['user_id']
            }, {"_id": 0}).to_list(100)
            
            evidence_objs = [Evidence(**ev) for ev in evidence_list if isinstance(ev.get('created_at'), str) == False or (ev.update({'created_at': datetime.fromisoformat(ev['created_at'])}) or True)]
            
            # Evaluate control
            eval_result = await audit_service.evaluate_control(AuditControl(**control), evidence_objs)
            controls_evaluation.append(eval_result)
        
        # Generate audit report
        audit_obj = AuditSession(**audit)
        report = await audit_service.generate_audit_report(audit_obj, controls_evaluation)
        
        # Update audit session
        await db.audit_sessions.update_one(
            {"id": audit_id},
            {"$set": {
                "overall_score": report['overall_score'],
                "status": "Completed",
                "completed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return report
    except Exception as e:
        logger.error(f"Error running audit: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audit execution failed: {str(e)}")

@api_router.get("/audit/sessions", response_model=List[AuditSession])
async def get_audit_sessions(current_user: dict = Depends(get_current_user)):
    audits = await db.audit_sessions.find({"user_id": current_user['user_id']}, {"_id": 0}).to_list(1000)
    for audit in audits:
        if isinstance(audit.get('created_at'), str):
            audit['created_at'] = datetime.fromisoformat(audit['created_at'])
        if audit.get('completed_at') and isinstance(audit['completed_at'], str):
            audit['completed_at'] = datetime.fromisoformat(audit['completed_at'])
    return audits

# ========== TASK ENDPOINTS ==========
@api_router.get("/tasks", response_model=List[Task])
async def get_tasks(
    department: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {"user_id": current_user['user_id']}
    if department:
        query["department"] = department
    if status:
        query["status"] = status
    
    tasks = await db.tasks.find(query, {"_id": 0}).to_list(1000)
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
        department=task_data.department,
        gap_id=task_data.gap_id,
        policy_id=task_data.policy_id,
        circular_id=task_data.circular_id,
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

# ========== COMPLIANCE CALENDAR ENDPOINTS ==========
@api_router.get("/calendar/events", response_model=List[ComplianceCalendarEvent])
async def get_calendar_events(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    events = await db.calendar_events.find({"organization": user_doc.get('organization')}, {"_id": 0}).to_list(1000)
    
    for event in events:
        if isinstance(event.get('created_at'), str):
            event['created_at'] = datetime.fromisoformat(event['created_at'])
        if isinstance(event.get('due_date'), str):
            event['due_date'] = datetime.fromisoformat(event['due_date'])
    
    return events

@api_router.post("/calendar/events", response_model=ComplianceCalendarEvent)
async def create_calendar_event(
    event_data: ComplianceCalendarEventCreate,
    current_user: dict = Depends(get_current_user)
):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    event = ComplianceCalendarEvent(
        title=event_data.title,
        description=event_data.description,
        event_type=event_data.event_type,
        regulator=event_data.regulator,
        due_date=event_data.due_date,
        recurrence=event_data.recurrence,
        responsible_department=event_data.responsible_department,
        organization=user_doc.get('organization', 'Default')
    )
    
    event_dict = event.model_dump()
    event_dict['created_at'] = event_dict['created_at'].isoformat()
    event_dict['due_date'] = event_dict['due_date'].isoformat()
    
    await db.calendar_events.insert_one(event_dict)
    return event

# ========== LOS/LMS ENDPOINTS ==========
@api_router.post("/los-lms/analyze")
async def analyze_los_lms_data(
    data: LOSLMSDataCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        # Get applicable regulations
        regulations = await db.regulations.find({"user_id": current_user['user_id']}, {"_id": 0, "title": 1}).to_list(100)
        reg_titles = [r.get('title', '') for r in regulations]
        
        # Analyze using LLM
        analysis = await llm_service.analyze_los_lms_data(data.record_data, reg_titles)
        
        los_data = LOSLMSData(
            data_source=data.data_source,
            record_type=data.record_type,
            record_data=data.record_data,
            compliance_issues=analysis.get('issues', []),
            risk_level=analysis.get('risk_level', SeverityLevel.LOW),
            organization=user_doc.get('organization', 'Default')
        )
        
        los_dict = los_data.model_dump()
        los_dict['created_at'] = los_dict['created_at'].isoformat()
        
        await db.los_lms_data.insert_one(los_dict)
        
        return {
            "message": "LOS/LMS data analyzed",
            "record_id": los_data.id,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error analyzing LOS/LMS data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# ========== CHAT ENDPOINTS ==========
@api_router.post("/chat")
async def chat(
    message: ChatMessageCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Get chat history
        history = await db.chat_messages.find(
            {"session_id": message.session_id, "user_id": current_user['user_id']},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        context = [{"role": msg['role'], "content": msg['content']} for msg in reversed(history)]
        
        # Get AI response
        response_text = await llm_service.chat_response(message.content, context)
        
        # Save user message
        user_msg = ChatMessage(
            session_id=message.session_id,
            role="user",
            content=message.content,
            user_id=current_user['user_id']
        )
        user_msg_dict = user_msg.model_dump()
        user_msg_dict['created_at'] = user_msg_dict['created_at'].isoformat()
        await db.chat_messages.insert_one(user_msg_dict)
        
        # Save assistant message
        assistant_msg = ChatMessage(
            session_id=message.session_id,
            role="assistant",
            content=response_text,
            user_id=current_user['user_id']
        )
        assistant_msg_dict = assistant_msg.model_dump()
        assistant_msg_dict['created_at'] = assistant_msg_dict['created_at'].isoformat()
        await db.chat_messages.insert_one(assistant_msg_dict)
        
        return {"response": response_text}
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# ========== DASHBOARD ENDPOINTS ==========
@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')
    
    total_policies = await db.policies.count_documents({"organization": org})
    total_regulations = await db.regulations.count_documents({"organization": org})
    total_tasks = await db.tasks.count_documents({"organization": org})
    open_tasks = await db.tasks.count_documents({"organization": org, "status": TaskStatus.OPEN})
    
    latest_analysis = await db.gap_analyses.find_one(
        {"organization": org},
        {"_id": 0, "compliance_score": 1, "gaps": 1},
        sort=[('created_at', -1)]
    )
    
    compliance_score = latest_analysis.get('compliance_score', 0.0) if latest_analysis else 0.0
    critical_gaps = 0
    if latest_analysis and latest_analysis.get('gaps'):
        critical_gaps = len([g for g in latest_analysis['gaps'] if g.get('severity') == 'Critical'])
    
    high_priority_tasks = await db.tasks.count_documents({
        "organization": org,
        "priority": SeverityLevel.HIGH
    })
    
    departments = await db.departments.find({"organization": org}, {"_id": 0}).to_list(1000)
    departments_count = len(departments)
    non_compliant_departments = len([d for d in departments if d.get('compliance_status') == ComplianceStatus.NON_COMPLIANT])
    
    pending_actionables = await db.tasks.count_documents({
        "organization": org,
        "status": {"$in": [TaskStatus.OPEN, TaskStatus.PENDING]}
    })
    
    regulatory_communications = await db.regulations.count_documents({"organization": org})
    
    # Compliance by status
    compliance_by_status = {
        "Compliant": 0,
        "Partially Compliant": 0,
        "Non-Compliant": 0,
        "Noted for Compliance": 0
    }
    for dept in departments:
        status = dept.get('compliance_status', 'Noted for Compliance')
        compliance_by_status[status] = compliance_by_status.get(status, 0) + 1
    
    # Compliance by department
    compliance_by_department = []
    for dept in departments[:5]:
        compliance_by_department.append({
            "department": dept.get('name'),
            "compliance_status": dept.get('compliance_status'),
            "total_tasks": dept.get('total_tasks', 0),
            "overdue_tasks": dept.get('overdue_tasks', 0)
        })
    
    # Regulator overview
    regulators = await db.regulations.aggregate([
        {"$match": {"organization": org}},
        {"$group": {
            "_id": "$regulatory_body",
            "count": {"$sum": 1}
        }}
    ]).to_list(100)
    
    regulator_overview = []
    for reg in regulators:
        regulator_overview.append({
            "regulator": reg['_id'],
            "circulars_count": reg['count'],
            "compliance_status": "Review Pending"
        })
    
    return DashboardStats(
        total_policies=total_policies,
        total_regulations=total_regulations,
        total_tasks=total_tasks,
        open_tasks=open_tasks,
        compliance_score=compliance_score,
        critical_gaps=critical_gaps,
        high_priority_tasks=high_priority_tasks,
        departments_count=departments_count,
        non_compliant_departments=non_compliant_departments,
        pending_actionables=pending_actionables,
        regulatory_communications=regulatory_communications,
        compliance_by_status=compliance_by_status,
        compliance_by_department=compliance_by_department,
        regulator_overview=regulator_overview
    )

@api_router.get("/")
async def root():
    return {"message": "CompliAI API - Production Ready"}

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
