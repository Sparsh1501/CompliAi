# CompliAI Backend Server - with RAG-powered chat
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends, Header, Body, WebSocket, WebSocketDisconnect, BackgroundTasks, Request, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
import asyncio
import json
from contextlib import asynccontextmanager

from models import *
from services.document_service import DocumentService
from services.multi_llm_service_new import MultiLLMService
from services.llm_provider import get_llm_provider, is_using_local_llm, ClaudeProvider, OllamaProvider
from services.audit_service import AuditService
from services.evidence_service import EvidenceService
from services.clause_extraction_service import ClauseExtractionService, GapAnalysisMatcher
from services.enhanced_gap_analysis_service import EnhancedGapAnalysisService, run_enhanced_gap_analysis, gap_report_to_dict
from services.regulation_first_gap_analysis import (
    RegulationFirstGapAnalysisService,
    run_regulation_first_gap_analysis,
    gap_report_to_dict as regulation_gap_report_to_dict
)
from services.semantic_gap_analysis_service import (
    SemanticGapAnalysisService,
    run_semantic_gap_analysis,
    semantic_gap_report_to_dict
)
from services.task_service import TaskService
from services.upload_job_service import UploadJobService, connection_manager
from services.vector_service import VectorService
from services.npci_scraper_service import NPCIScraper, NPCI_PRODUCTS, NPCI_PRODUCT_LABELS
from services.npci_scheduler_service import NPCISchedulerService
from services.npci_processing_service import NPCIProcessingService
from services.organization_profile_service import OrganizationProfileService
from services.requirement_mapping_service import RequirementMappingService
from services.batch_upload_service import BatchUploadService
from config.pa_pg_requirements import PA_PG_REQUIREMENTS, get_all_requirements, get_requirements_by_applicability, get_requirement_stats
from services.gap_scoring_service import GapScoringService
from services.compliance_checks_service import ComplianceChecksService
from services.remediation_service import RemediationService
from services.policy_drafting_service import PolicyDraftingService
from services.sop_templates_service import SOPTemplatesService
from services.approval_workflow_service import ApprovalWorkflowService
from services.policy_version_service import PolicyVersionService
from services.gap_report_service import GapReportService
from services.audit_trail_service import AuditTrailService
from services.regulatory_feed_service import RegulatoryFeedService
from services.report_export_service import ReportExportService
from services.i18n_service import I18nService
from services.document_encryption_service import DocumentEncryptionService
from services.confluence_integration_service import ConfluenceIntegrationService
from services.document_optimization_service import DocumentOptimizationService
from services.success_metrics_service import SuccessMetricsService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'compli-ai')]

# Qdrant Vector Database Client
qdrant_url = os.environ.get('QDRANT_URL', 'http://localhost:6333')
qdrant_mode = os.environ.get('QDRANT_MODE', 'server')  # 'server' or 'memory'

if QDRANT_AVAILABLE:
    try:
        if qdrant_mode == 'memory':
            # Use in-memory Qdrant for development/testing when Docker unavailable
            qdrant_client = QdrantClient(":memory:")
            logging.info("Qdrant client connected successfully (in-memory mode)")
        else:
            # Use Qdrant server (Docker or standalone)
            qdrant_client = QdrantClient(url=qdrant_url, timeout=5)
            logging.info("Qdrant client connected successfully")
    except Exception as e:
        qdrant_client = None
        logging.warning(f"Qdrant client connection failed: {e} - vector search features will be disabled")
else:
    qdrant_client = None
    logging.warning("Qdrant client not available - vector search features will be disabled")

JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for FastAPI - replaces deprecated on_event."""
    # Startup
    print("=" * 80)
    print("LIFESPAN STARTUP BEGINNING")
    print("=" * 80)
    global regulation_first_gap_service, semantic_gap_service, task_service, upload_job_service, vector_service, npci_scraper, npci_scheduler, npci_processing_service, org_profile_service, requirement_mapping_service, batch_upload_service, gap_scoring_service, compliance_checks_service, remediation_service, policy_drafting_service, sop_templates_service, approval_workflow_service, policy_version_service, gap_report_service, audit_trail_service, regulatory_feed_service, report_export_service, i18n_service, document_encryption_service, confluence_integration_service, document_optimization_service, success_metrics_service

    # Initialize MongoDB collections and indexes
    logger.info(f"Connecting to MongoDB at {mongo_url}, database: {db.name}")
    print(f"Connecting to MongoDB at {mongo_url}, database: {db.name}")
    try:
        result = await client.admin.command('ping')
        logger.info(f"MongoDB connection successful (ping ok={result.get('ok')})")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")

    await initialize_mongodb_collections()

    # Initialize Qdrant collections
    logger.info(f"Connecting to Qdrant at {qdrant_url}")
    initialize_qdrant_collections()

    # Initialize services
    regulation_first_gap_service = RegulationFirstGapAnalysisService(db=db)
    vector_service = VectorService(qdrant_client=qdrant_client, llm_service=llm_service)
    semantic_gap_service = SemanticGapAnalysisService(db=db, vector_service=vector_service, llm_service=llm_service)
    task_service = TaskService(db=db)
    upload_job_service = UploadJobService(db=db)
    logger.info("Initialized SemanticGapAnalysisService with database connection, vector service, and LLM service")
    logger.info("Initialized RegulationFirstGapAnalysisService with database connection")
    logger.info("Initialized TaskService with database connection")
    logger.info("Initialized UploadJobService with database connection")
    logger.info("Initialized VectorService with Qdrant client")

    # Initialize Organization Profile, Requirement Mapping, and Batch Upload services
    org_profile_service = OrganizationProfileService(db=db)
    requirement_mapping_service = RequirementMappingService(db=db, vector_service=vector_service)
    batch_upload_service = BatchUploadService(db=db, connection_manager=connection_manager)
    gap_scoring_service = GapScoringService(db=db)
    compliance_checks_service = ComplianceChecksService(db=db, org_profile_service=org_profile_service)
    remediation_service = RemediationService(db=db)
    policy_drafting_service = PolicyDraftingService(db=db)
    sop_templates_service = SOPTemplatesService(db=db, policy_drafting_service=policy_drafting_service)
    approval_workflow_service = ApprovalWorkflowService(db=db)
    policy_version_service = PolicyVersionService(db=db)
    gap_report_service = GapReportService(db=db, gap_scoring_service=gap_scoring_service)
    audit_trail_service = AuditTrailService(db=db)
    regulatory_feed_service = RegulatoryFeedService(db=db)
    report_export_service = ReportExportService(db=db, gap_report_service=gap_report_service)
    i18n_service = I18nService(db=db)
    document_encryption_service = DocumentEncryptionService(db=db)
    confluence_integration_service = ConfluenceIntegrationService(db=db)
    document_optimization_service = DocumentOptimizationService(db=db)
    success_metrics_service = SuccessMetricsService(db=db)
    logger.info("Initialized all PA/PG compliance services (21 services total)")

    # Create indexes for new collections
    try:
        await db.organizations.create_index("organization", unique=True)
        await db.organizations.create_index("entity_type")
        await db.organization_profile_history.create_index([("organization", 1), ("timestamp", -1)])
        await db.license_timeline.create_index([("organization", 1), ("date", -1)])
        await db.requirements.create_index([("regulation_id", 1), ("status", 1)])
        await db.requirements.create_index("requirement_id", unique=True, sparse=True)
        await db.requirements.create_index("category")
        await db.requirements.create_index("entity_applicability")
        await db.requirement_maps.create_index([("regulation_id", 1), ("policy_id", 1)])
        await db.requirement_maps.create_index([("user_id", 1), ("organization", 1)])
        await db.batch_uploads.create_index([("user_id", 1), ("organization", 1)])
        await db.batch_uploads.create_index("created_at")
        await db.policy_drafts.create_index([("organization", 1), ("created_at", -1)])
        await db.policy_drafts.create_index("status")
        await db.approval_workflows.create_index([("organization", 1), ("status", 1)])
        await db.approval_workflows.create_index("document_id")
        await db.policy_versions.create_index([("draft_id", 1), ("version_major", -1), ("version_minor", -1)])
        await db.gap_reports.create_index([("organization", 1), ("generated_at", -1)])
        await db.gap_reports.create_index("analysis_id")
        await db.audit_trail.create_index([("organization", 1), ("timestamp", -1)])
        await db.audit_trail.create_index([("user_id", 1), ("timestamp", -1)])
        await db.audit_trail.create_index([("resource_type", 1), ("resource_id", 1)])
        await db.regulatory_amendments.create_index([("source_key", 1), ("created_at", -1)])
        await db.regulatory_amendments.create_index("status")
        await db.regulatory_subscriptions.create_index([("user_id", 1), ("organization", 1)], unique=True)
        logger.info("Created indexes for all PA/PG compliance collections")
    except Exception as e:
        logger.warning(f"Index creation warning (may already exist): {e}")

    # Feature #215: Initialize NPCI Scraper Service
    npci_scraper = NPCIScraper(db=db)
    await npci_scraper.ensure_indexes()
    logger.info("Initialized NPCIScraper with database connection")

    # Feature #216: Initialize NPCI Processing Service
    try:
        npci_processing_service = NPCIProcessingService(db=db, qdrant_client=qdrant_client)
        await npci_processing_service.ensure_indexes()
        logger.info("Initialized NPCIProcessingService")
    except Exception as e:
        logger.error(f"Error initializing NPCIProcessingService: {e}")

    # Feature #220: Initialize NPCI Scheduler Service
    try:
        npci_scheduler = NPCISchedulerService(db=db, npci_scraper=npci_scraper)
        await npci_scheduler.start()
        logger.info("Initialized NPCISchedulerService")
    except Exception as e:
        logger.error(f"Error initializing NPCISchedulerService: {e}")

    # Feature #213: Restore persisted LLM mode from MongoDB
    try:
        saved_mode = await db.app_settings.find_one({"key": "llm_mode"})
        if saved_mode and saved_mode.get("value"):
            mode_val = saved_mode["value"]
            if mode_val == "local":
                os.environ["USE_LOCAL_LLM"] = "true"
                logger.info("Restored LLM mode from MongoDB: local (Ollama)")
            else:
                os.environ["USE_LOCAL_LLM"] = "false"
                logger.info("Restored LLM mode from MongoDB: cloud (Claude)")
            # Clear cached singletons to pick up restored mode
            import services.llm_provider as llm_mod
            llm_mod._claude_provider = None
            llm_mod._ollama_provider = None
        else:
            logger.info(f"No saved LLM mode found in MongoDB, using env default: USE_LOCAL_LLM={os.getenv('USE_LOCAL_LLM', 'false')}")
    except Exception as e:
        logger.warning(f"Could not restore LLM mode from MongoDB: {e}")

    logger.info("CompliAI startup complete - all services initialized")

    yield

    # Shutdown
    # Feature #220: Stop NPCI scheduler
    if npci_scheduler:
        await npci_scheduler.stop()
    client.close()
    try:
        qdrant_client.close()
    except Exception:
        pass
    logger.info("Database connections closed")

app = FastAPI(lifespan=lifespan)

# Add CORS middleware FIRST (before routes)
# Note: When using allow_credentials=True, cannot use "*" for allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for Pydantic validation errors.
    Returns user-friendly error messages in a consistent format.
    """
    errors = []
    for error in exc.errors():
        field = '.'.join(str(loc) for loc in error['loc'][1:])  # Skip 'body' prefix
        message = error['msg']
        error_type = error['type']

        # Create user-friendly error messages
        if error_type == 'value_error':
            # Custom validator error messages
            errors.append({
                "field": field,
                "message": message,
                "type": error_type
            })
        elif error_type == 'missing':
            errors.append({
                "field": field,
                "message": f"{field} is required",
                "type": error_type
            })
        elif error_type.startswith('string_'):
            errors.append({
                "field": field,
                "message": message,
                "type": error_type
            })
        else:
            errors.append({
                "field": field,
                "message": message,
                "type": error_type
            })

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )

doc_service = DocumentService()
llm_service = MultiLLMService()
audit_service = AuditService()
evidence_service = EvidenceService()
clause_extractor = ClauseExtractionService()
gap_matcher = GapAnalysisMatcher()
enhanced_gap_service = EnhancedGapAnalysisService()
semantic_gap_service = None  # Initialized after db is ready
regulation_first_gap_service = None  # Initialized after db is ready
task_service = None  # Initialized after db is ready
upload_job_service = None  # Initialized after db is ready
vector_service = None  # Initialized after Qdrant client is ready
npci_scraper = None  # Initialized after db is ready
npci_scheduler = None  # Initialized after db is ready (Feature #220)
npci_processing_service = None  # Initialized after db is ready (Feature #216)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# Health Check Endpoint
# ==========================================
@api_router.get("/health")
async def health_check():
    """Health check endpoint that reports MongoDB and Qdrant connectivity status."""
    # Force reload for in-memory Qdrant mode
    mongodb_status = "disconnected"
    mongodb_version = None
    qdrant_status = "disconnected"

    # Check MongoDB
    try:
        result = await client.admin.command('ping')
        if result.get('ok') == 1.0:
            mongodb_status = "connected"
            server_info = await client.server_info()
            mongodb_version = server_info.get('version')
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        mongodb_status = "disconnected"

    # Check Qdrant
    try:
        if qdrant_client:
            qdrant_info = qdrant_client.get_collections()
            qdrant_status = "connected"
        else:
            qdrant_status = "not_installed"
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        qdrant_status = "disconnected"

    overall = "healthy" if mongodb_status == "connected" and qdrant_status == "connected" else "degraded"

    return {
        "status": overall,
        "mongodb_status": mongodb_status,
        "mongodb_version": mongodb_version,
        "qdrant_status": qdrant_status,
        "database_name": db.name,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/collections")
async def verify_collections():
    """Verify all required MongoDB and Qdrant collections exist."""
    # Check MongoDB collections
    try:
        existing_mongo = await db.list_collection_names()
        mongo_collections = {
            "required": REQUIRED_COLLECTIONS,
            "existing": existing_mongo,
            "missing": [c for c in REQUIRED_COLLECTIONS if c not in existing_mongo],
            "count": len(existing_mongo)
        }
    except Exception as e:
        mongo_collections = {"error": str(e)}

    # Check Qdrant collections
    try:
        existing_qdrant = [c.name for c in qdrant_client.get_collections().collections]
        qdrant_collections = {
            "required": list(QDRANT_COLLECTIONS.keys()),
            "existing": existing_qdrant,
            "missing": [c for c in QDRANT_COLLECTIONS.keys() if c not in existing_qdrant],
            "count": len(existing_qdrant)
        }
    except Exception as e:
        qdrant_collections = {"error": str(e)}

    all_ok = (
        mongo_collections.get("missing", []) == [] and
        qdrant_collections.get("missing", []) == []
    )

    return {
        "status": "ok" if all_ok else "incomplete",
        "mongodb": mongo_collections,
        "qdrant": qdrant_collections,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ==========================================
# Database Initialization (Collections + Indexes)
# ==========================================
REQUIRED_COLLECTIONS = [
    "users", "policies", "policy_versions", "approval_workflows",
    "regulations", "regulation_updates", "clauses", "gap_analyses",
    "tasks", "task_dependencies", "escalation_rules",
    "evidence", "evidence_audit_log", "evidence_templates",
    "departments", "department_members", "audit_sessions",
    "calendar_events", "chat_threads", "chat_messages",
    "los_lms_data", "los_lms_mappings", "los_lms_exceptions",
    "notification_preferences", "notifications",
    "checklists", "npci_circulars", "npci_circular_clauses"
]

QDRANT_COLLECTIONS = {
    "policy_clauses": 384,   # Embedding dimension for OpenAI text-embedding-3-small (384 dimensions)
    "regulation_clauses": 384,
}

async def initialize_mongodb_collections():
    """Create all required MongoDB collections and indexes if they don't exist."""
    existing = await db.list_collection_names()
    for collection_name in REQUIRED_COLLECTIONS:
        if collection_name not in existing:
            await db.create_collection(collection_name)
            logger.info(f"Created MongoDB collection: {collection_name}")

    # Create indexes
    try:
        # Users - unique email index
        await db.users.create_index("email", unique=True, sparse=True)
        # Policies - indexes for common queries
        await db.policies.create_index("organization")
        await db.policies.create_index("type")
        await db.policies.create_index("status")
        await db.policies.create_index("uploaded_by")
        # Policy versions
        await db.policy_versions.create_index("policy_id")
        # Approval workflows
        await db.approval_workflows.create_index("policy_id")
        # Regulations
        await db.regulations.create_index("regulatory_body")
        await db.regulations.create_index("category")
        # Regulation updates
        await db.regulation_updates.create_index("regulation_id")
        # Clauses
        await db.clauses.create_index("source_type")
        await db.clauses.create_index("source_id")
        await db.clauses.create_index([("source_type", 1), ("source_id", 1)])
        # Gap analyses
        await db.gap_analyses.create_index("policy_id")
        await db.gap_analyses.create_index("regulation_id")
        # Tasks
        await db.tasks.create_index("assignee")
        await db.tasks.create_index("status")
        await db.tasks.create_index("priority")
        await db.tasks.create_index("sla_deadline")
        # Task dependencies
        await db.task_dependencies.create_index("task_id")
        await db.task_dependencies.create_index("depends_on_task_id")
        # Evidence
        await db.evidence.create_index("linked_task_id")
        await db.evidence.create_index("linked_clause_id")
        await db.evidence.create_index("uploaded_by")
        # Evidence audit log
        await db.evidence_audit_log.create_index("evidence_id")
        await db.evidence_audit_log.create_index("timestamp")
        # Departments
        await db.departments.create_index("organization")
        # Department members
        await db.department_members.create_index("department_id")
        await db.department_members.create_index("user_id")
        # Audit sessions
        await db.audit_sessions.create_index("created_by")
        # Calendar events
        await db.calendar_events.create_index("date")
        await db.calendar_events.create_index("assigned_to")
        # Chat
        await db.chat_threads.create_index("created_by")
        await db.chat_messages.create_index("thread_id")
        # LOS/LMS
        await db.los_lms_data.create_index("source_type")
        await db.los_lms_mappings.create_index("source_system")
        await db.los_lms_exceptions.create_index("los_lms_data_id")
        # Notifications
        await db.notifications.create_index("user_id")
        await db.notifications.create_index([("user_id", 1), ("read", 1)])
        await db.notification_preferences.create_index("user_id", unique=True, sparse=True)
        # NPCI Circulars
        await db.npci_circulars.create_index("npci_id", unique=True, sparse=True)
        await db.npci_circulars.create_index("product")
        await db.npci_circulars.create_index("year")
        await db.npci_circulars.create_index([("product", 1), ("year", 1)])
        await db.npci_circulars.create_index("scraped_at")
        await db.npci_circulars.create_index("processed_at")

        logger.info("MongoDB indexes created/verified successfully")
    except Exception as e:
        logger.error(f"Error creating MongoDB indexes: {e}")


def initialize_qdrant_collections():
    """Create Qdrant collections for vector search if they don't exist."""
    if not qdrant_client:
        logger.warning("Skipping Qdrant initialization - client not available")
        return
    try:
        existing = [c.name for c in qdrant_client.get_collections().collections]
        for name, dim in QDRANT_COLLECTIONS.items():
            if name not in existing:
                qdrant_client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {name}")
            else:
                logger.info(f"Qdrant collection already exists: {name}")
    except Exception as e:
        logger.error(f"Error initializing Qdrant collections: {e}")


def create_token(user_id: str, email: str, role: str = "user") -> str:
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
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

async def check_not_auditor(current_user: dict = Depends(get_current_user)):
    """Verify user is not an auditor (auditors have read-only access to most modules)."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0, "role": 1})
    if user_doc and user_doc.get('role') == 'auditor':
        raise HTTPException(
            status_code=403,
            detail="Auditors have read-only access. Cannot modify policies, regulations, or tasks."
        )
    return current_user

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
        department=user_data.department,
        role=user_data.role
    )
    
    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    await db.users.insert_one(user_dict)
    
    token = create_token(user.id, user.email, user.role)
    
    return {
        "message": "User registered successfully",
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "organization": user.organization,
            "role": user.role
        }
    }

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(credentials.password.encode('utf-8'), user_doc['password_hash'].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user_doc['id'], user_doc['email'], user_doc.get('role', 'user'))
    
    return {
        "token": token,
        "user": {
            "id": user_doc['id'],
            "email": user_doc['email'],
            "full_name": user_doc['full_name'],
            "organization": user_doc['organization'],
            "role": user_doc.get('role', 'compliance_head'),
            "preferred_theme": user_doc.get('preferred_theme', 'charcoal-pro')
        }
    }

# ========== USER PREFERENCES ENDPOINTS ==========
@api_router.get("/user/theme")
async def get_user_theme(current_user: dict = Depends(get_current_user)):
    """Get user's preferred theme."""
    user_doc = await db.users.find_one({"id": current_user['id']}, {"_id": 0, "preferred_theme": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"preferred_theme": user_doc.get('preferred_theme', 'charcoal-pro')}

@api_router.put("/user/theme")
async def update_user_theme(theme_data: dict, current_user: dict = Depends(get_current_user)):
    """Update user's preferred theme."""
    theme_id = theme_data.get('theme_id')
    if not theme_id:
        raise HTTPException(status_code=400, detail="theme_id is required")
    
    result = await db.users.update_one(
        {"id": current_user['id']},
        {"$set": {"preferred_theme": theme_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found or theme not updated")
    
    return {"message": "Theme updated successfully", "preferred_theme": theme_id}

# ========== VECTOR SEARCH ENDPOINTS ==========
@api_router.get("/vector/stats")
async def get_vector_stats(current_user: dict = Depends(get_current_user)):
    """Get Qdrant vector database statistics."""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not available")

    stats = await vector_service.get_collection_stats()
    return stats


@api_router.post("/vector/search")
async def search_clauses(
    query: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Search for similar clauses using semantic similarity.

    Request body:
    {
        "query_text": "string",
        "limit": 10,
        "score_threshold": 0.7,
        "policy_id": "optional"
    }
    """
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not available")

    # Get user's organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    results = await vector_service.search_similar_clauses(
        query_text=query.get('query_text', ''),
        organization=organization,
        limit=query.get('limit', 10),
        score_threshold=query.get('score_threshold', 0.7),
        policy_id=query.get('policy_id')
    )

    return {"results": results, "count": len(results)}


@api_router.get("/vector/regulation-clauses/stats")
async def get_regulation_clause_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get statistics about the regulation_clauses Qdrant collection.
    Returns vector count, point count, and collection status.
    """
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not available")

    stats = await vector_service.get_regulation_collection_stats()
    return stats


@api_router.post("/vector/regulation-clauses/search")
async def search_regulation_clauses(
    query: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Search for similar regulation clauses using semantic similarity.

    Request body:
    {
        "query_text": "string",
        "limit": 10,
        "score_threshold": 0.3,
        "regulation_id": "optional"
    }
    """
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not available")

    # Get user's organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    results = await vector_service.search_regulation_clauses(
        query_text=query.get('query_text', ''),
        organization=organization,
        limit=query.get('limit', 10),
        score_threshold=query.get('score_threshold', 0.3),
        regulation_id=query.get('regulation_id')
    )

    return {"results": results, "count": len(results)}


@api_router.get("/vector/regulation-clauses/points")
async def get_regulation_clause_points(
    regulation_id: str = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    Get regulation clause vector points directly from Qdrant.
    Used for verification that embeddings exist with proper payload.
    """
    if not vector_service or not vector_service.qdrant_client:
        raise HTTPException(status_code=503, detail="Qdrant not available")

    try:
        collection_name = "regulation_clauses"

        # Scroll through points with optional regulation_id filter
        filter_condition = None
        if regulation_id:
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="regulation_id",
                        match=MatchValue(value=regulation_id)
                    )
                ]
            )

        points, next_offset = vector_service.qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=filter_condition,
            limit=limit,
            with_payload=True,
            with_vectors=False  # Don't return full vectors to keep response small
        )

        results = []
        for point in points:
            results.append({
                'point_id': str(point.id),
                'payload': point.payload
            })

        return {
            "collection": collection_name,
            "count": len(results),
            "points": results,
            "has_more": next_offset is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query Qdrant: {str(e)}")


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


@api_router.get("/departments/{department_id}/members")
async def get_department_members(department_id: str, current_user: dict = Depends(get_current_user)):
    """Get all members of a specific department."""
    members = await db.department_members.find({"department_id": department_id}, {"_id": 0}).to_list(100)
    return members


@api_router.get("/department-members")
async def get_all_department_members(current_user: dict = Depends(get_current_user)):
    """Get all department members with their department info."""
    members = await db.department_members.find({}, {"_id": 0}).to_list(200)

    # Enrich with department info
    for member in members:
        dept = await db.departments.find_one({"id": member.get('department_id')}, {"_id": 0, "name": 1})
        if dept:
            member['department_name'] = dept.get('name')

    return members


@api_router.put("/departments/{department_id}")
async def update_department(
    department_id: str,
    updates: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Update department details."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})

    # Verify department exists and belongs to user's organization
    dept = await db.departments.find_one(
        {"id": department_id, "organization": user_doc.get('organization')},
        {"_id": 0}
    )

    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Update department
    result = await db.departments.update_one(
        {"id": department_id},
        {"$set": updates}
    )

    return {"status": "updated", "matched": result.matched_count}


@api_router.delete("/departments/{department_id}")
async def delete_department(department_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a department."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})

    # Verify department exists and belongs to user's organization
    dept = await db.departments.find_one(
        {"id": department_id, "organization": user_doc.get('organization')},
        {"_id": 0}
    )

    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Delete all members of this department
    await db.department_members.delete_many({"department_id": department_id})

    # Delete the department
    result = await db.departments.delete_one({"id": department_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Department not found")

    return {"status": "deleted"}


@api_router.post("/departments/{department_id}/members")
async def add_department_member(
    department_id: str,
    member_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Add a member to a department."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})

    # Verify department exists and belongs to user's organization
    dept = await db.departments.find_one(
        {"id": department_id, "organization": user_doc.get('organization')},
        {"_id": 0}
    )

    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Create member
    member = DepartmentMember(
        name=member_data.get('name'),
        email=member_data.get('email'),
        title=member_data.get('title', ''),
        role=member_data.get('role', 'analyst'),
        department_id=department_id,
        can_be_assigned_tasks=member_data.get('can_be_assigned_tasks', True),
        expertise_areas=member_data.get('expertise_areas', [])
    )

    member_dict = member.model_dump()
    member_dict['created_at'] = member_dict['created_at'].isoformat()

    await db.department_members.insert_one(member_dict)

    # Update department members list
    await db.departments.update_one(
        {"id": department_id},
        {"$addToSet": {"members": member.id}}
    )

    return member


@api_router.delete("/departments/{department_id}/members/{member_id}")
async def remove_department_member(
    department_id: str,
    member_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove a member from a department."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})

    # Verify department exists and belongs to user's organization
    dept = await db.departments.find_one(
        {"id": department_id, "organization": user_doc.get('organization')},
        {"_id": 0}
    )

    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Delete member
    result = await db.department_members.delete_one({
        "id": member_id,
        "department_id": department_id
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")

    # Remove from department members list
    await db.departments.update_one(
        {"id": department_id},
        {"$pull": {"members": member_id}}
    )

    return {"status": "deleted"}


# ========== COMPLIANCE CHARTER ENDPOINTS ==========

@api_router.post("/charters", response_model=ComplianceCharter)
async def create_charter(charter_data: ComplianceCharterCreate, current_user: dict = Depends(get_current_user)):
    """Create a new compliance charter/product category."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    # Check if charter with same code already exists
    existing = await db.compliance_charters.find_one({
        "organization": user_doc.get('organization', 'Default'),
        "code": charter_data.code
    })
    if existing:
        raise HTTPException(status_code=400, detail="Charter with this code already exists")
    
    charter = ComplianceCharter(
        name=charter_data.name,
        code=charter_data.code,
        description=charter_data.description,
        regulatory_bodies=charter_data.regulatory_bodies,
        organization=user_doc.get('organization', 'Default')
    )
    
    charter_dict = charter.model_dump()
    charter_dict['created_at'] = charter_dict['created_at'].isoformat()
    charter_dict['updated_at'] = charter_dict['updated_at'].isoformat()
    
    await db.compliance_charters.insert_one(charter_dict)
    return charter


@api_router.get("/charters", response_model=List[ComplianceCharter])
async def list_charters(current_user: dict = Depends(get_current_user)):
    """List all compliance charters for the organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    charters = await db.compliance_charters.find({
        "organization": user_doc.get('organization', 'Default'),
        "is_active": True
    }, {"_id": 0}).to_list(length=None)
    
    return charters


@api_router.get("/charters/{charter_id}", response_model=ComplianceCharter)
async def get_charter(charter_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific compliance charter."""
    charter = await db.compliance_charters.find_one({"id": charter_id}, {"_id": 0})
    if not charter:
        raise HTTPException(status_code=404, detail="Charter not found")
    return charter


@api_router.put("/charters/{charter_id}", response_model=ComplianceCharter)
async def update_charter(
    charter_id: str,
    charter_data: ComplianceCharterCreate,
    current_user: dict = Depends(get_current_user)
):
    """Update a compliance charter."""
    charter = await db.compliance_charters.find_one({"id": charter_id}, {"_id": 0})
    if not charter:
        raise HTTPException(status_code=404, detail="Charter not found")
    
    # Check if code is being changed and if new code already exists
    if charter_data.code != charter['code']:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        existing = await db.compliance_charters.find_one({
            "organization": user_doc.get('organization', 'Default'),
            "code": charter_data.code,
            "id": {"$ne": charter_id}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Charter with this code already exists")
    
    update_data = {
        "name": charter_data.name,
        "code": charter_data.code,
        "description": charter_data.description,
        "regulatory_bodies": charter_data.regulatory_bodies,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.compliance_charters.update_one(
        {"id": charter_id},
        {"$set": update_data}
    )
    
    updated_charter = await db.compliance_charters.find_one({"id": charter_id}, {"_id": 0})
    return updated_charter


@api_router.delete("/charters/{charter_id}")
async def delete_charter(charter_id: str, current_user: dict = Depends(get_current_user)):
    """Soft delete a compliance charter."""
    charter = await db.compliance_charters.find_one({"id": charter_id}, {"_id": 0})
    if not charter:
        raise HTTPException(status_code=404, detail="Charter not found")
    
    # Soft delete by setting is_active to False
    await db.compliance_charters.update_one(
        {"id": charter_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Charter deleted successfully"}


# ========== END COMPLIANCE CHARTER ENDPOINTS ==========


# ========== ORGANIZATION PROFILE ENDPOINTS ==========

@api_router.get("/organization/profile")
async def get_organization_profile(current_user: dict = Depends(get_current_user)):
    """Get the organization profile for the current user's organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    profile = await org_profile_service.get_or_create_default_profile(
        organization=organization, user_id=current_user['user_id']
    )
    return profile

@api_router.put("/organization/profile")
async def update_organization_profile(
    update: OrganizationProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update the organization profile. Only admin/compliance_head roles."""
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can update org profile")
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    update_data = update.model_dump(exclude_none=True)
    try:
        profile = await org_profile_service.update_profile(
            organization=organization, update_data=update_data, updated_by_user_id=current_user['user_id']
        )
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/organization/profile")
async def create_organization_profile(
    profile_data: OrganizationProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create an organization profile (first-time setup)."""
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can create org profile")
    try:
        profile = await org_profile_service.create_profile(
            organization_name=profile_data.organization,
            entity_type=profile_data.entity_type,
            created_by_user_id=current_user['user_id'],
            profile_data=profile_data.model_dump()
        )
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/organization/profile/entity-scope")
async def get_entity_scope(current_user: dict = Depends(get_current_user)):
    """Get the applicable entity scope for requirement filtering."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    scope = await org_profile_service.get_applicable_entity_scope(organization)
    profile = await org_profile_service.get_profile(organization)
    entity_type = (profile or {}).get('entity_type', 'unknown')
    thresholds = org_profile_service.get_entity_specific_thresholds(entity_type)
    return {
        "entity_type": entity_type,
        "scope": scope,
        "thresholds": thresholds,
        "applicable_regulations": (profile or {}).get('applicable_regulations', [])
    }

@api_router.put("/organization/profile/personnel")
async def update_key_personnel(
    personnel: List[Dict] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Update key personnel for the organization."""
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can update personnel")
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    result = await org_profile_service.update_key_personnel(
        organization=organization, personnel=personnel, updated_by_user_id=current_user['user_id']
    )
    return result

@api_router.put("/organization/profile/license")
async def update_license_status(
    license_data: Dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Update license/authorization status and record timeline event."""
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can update license")
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    result = await org_profile_service.update_license_status(
        organization=organization, license_data=license_data, updated_by_user_id=current_user['user_id']
    )
    return result

@api_router.get("/organization/profile/license-timeline")
async def get_license_timeline(current_user: dict = Depends(get_current_user)):
    """Get license status timeline events."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    timeline = await org_profile_service.get_license_timeline(organization)
    return {"timeline": timeline}

@api_router.get("/organization/profile/history")
async def get_profile_history(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get audit trail of organization profile changes."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    history = await org_profile_service.get_profile_history(organization, limit)
    return {"history": history}

# ========== END ORGANIZATION PROFILE ENDPOINTS ==========


# ========== REQUIREMENT MAPPING ENDPOINTS ==========

@api_router.get("/requirements/catalog")
async def get_pa_pg_requirement_catalog(current_user: dict = Depends(get_current_user)):
    """Get the built-in PA/PG requirement catalog with stats."""
    stats = get_requirement_stats()
    return {"requirements": get_all_requirements(), "stats": stats}

@api_router.get("/requirements/catalog/by-entity/{entity_type}")
async def get_requirements_by_entity(entity_type: str, current_user: dict = Depends(get_current_user)):
    """Get requirements filtered by entity type (e.g. non_bank_pa)."""
    reqs = get_requirements_by_applicability(entity_type)
    return {"entity_type": entity_type, "count": len(reqs), "requirements": reqs}

@api_router.get("/requirements/{regulation_id}")
async def get_requirements(
    regulation_id: str,
    entity_type: Optional[str] = None,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get extracted requirements for a regulation."""
    reqs = await requirement_mapping_service.get_requirements_for_regulation(
        regulation_id=regulation_id, entity_type=entity_type, category=category
    )
    return {"regulation_id": regulation_id, "count": len(reqs), "requirements": reqs}

@api_router.get("/requirements/{regulation_id}/stats")
async def get_requirement_stats_for_regulation(
    regulation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get requirement statistics for a specific regulation."""
    reqs = await requirement_mapping_service.get_requirements_for_regulation(regulation_id)
    stats = {"total": len(reqs), "by_category": {}, "by_criticality": {"high": 0, "medium": 0, "low": 0}}
    for r in reqs:
        cat = r.get("category", "general")
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        crit = r.get("criticality", "medium")
        stats["by_criticality"][crit] = stats["by_criticality"].get(crit, 0) + 1
    return stats

@api_router.post("/requirements/map")
async def map_requirements(
    regulation_id: str,
    policy_id: str,
    entity_type: str = "all",
    current_user: dict = Depends(get_current_user)
):
    """Run requirement mapping: maps regulation requirements against policy clauses."""
    policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    regulation = await db.regulations.find_one({
        "id": regulation_id,
        "$or": [{"user_id": current_user['user_id']}, {"user_id": "system"}]
    }, {"_id": 0})
    if not policy or not regulation:
        raise HTTPException(status_code=404, detail="Policy or regulation not found")

    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'default')

    result = await requirement_mapping_service.map_requirements_to_policy(
        regulation_id=regulation_id,
        policy_id=policy_id,
        policy_clauses=policy.get("clauses", []),
        entity_type=entity_type,
        organization=organization,
        user_id=current_user['user_id']
    )
    return result

@api_router.get("/requirement-maps/{map_id}")
async def get_requirement_map(map_id: str, current_user: dict = Depends(get_current_user)):
    """Get a previously computed requirement map by ID."""
    result = await db.requirement_maps.find_one({"id": map_id}, {"_id": 0})
    if not result:
        raise HTTPException(status_code=404, detail="Requirement map not found")
    return result

@api_router.get("/requirement-maps/history")
async def get_requirement_map_history(
    regulation_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List requirement mapping history."""
    query = {"user_id": current_user['user_id']}
    if regulation_id:
        query["regulation_id"] = regulation_id
    if policy_id:
        query["policy_id"] = policy_id
    cursor = db.requirement_maps.find(query, {"_id": 0, "matches": 0}).sort("created_at", -1).limit(50)
    results = await cursor.to_list(length=50)
    return {"history": results}

# ========== END REQUIREMENT MAPPING ENDPOINTS ==========


# ========== BATCH UPLOAD ENDPOINTS ==========

@api_router.post("/regulations/batch-upload")
async def batch_upload_regulations(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user)
):
    """Batch upload multiple regulation files for processing."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default Org')

    files_metadata = [{"file_name": f.filename, "file_size": f.size or 0} for f in files]
    batch_result = await batch_upload_service.create_batch(
        files_metadata=files_metadata,
        upload_type="regulation",
        user_id=current_user['user_id'],
        organization=organization
    )
    return {"message": f"Batch created with {len(files)} files", **batch_result}

@api_router.post("/policies/batch-upload")
async def batch_upload_policies(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user)
):
    """Batch upload multiple policy files for processing."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default Org')

    files_metadata = [{"file_name": f.filename, "file_size": f.size or 0} for f in files]
    batch_result = await batch_upload_service.create_batch(
        files_metadata=files_metadata,
        upload_type="policy",
        user_id=current_user['user_id'],
        organization=organization
    )
    return {"message": f"Batch created with {len(files)} files", **batch_result}

@api_router.get("/batch-uploads/{batch_id}")
async def get_batch_status(batch_id: str, current_user: dict = Depends(get_current_user)):
    """Get batch upload status with all child file statuses."""
    batch = await batch_upload_service.get_batch_status(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch

@api_router.post("/batch-uploads/{batch_id}/cancel")
async def cancel_batch(batch_id: str, current_user: dict = Depends(get_current_user)):
    """Cancel a batch upload."""
    result = await batch_upload_service.cancel_batch(batch_id)
    return {"message": "Batch cancelled", "success": result}

@api_router.get("/batch-uploads/history")
async def get_batch_history(current_user: dict = Depends(get_current_user)):
    """Get batch upload history for current user."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    history = await batch_upload_service.get_batch_history(
        user_id=current_user['user_id'], organization=organization
    )
    return {"history": history}

# ========== END BATCH UPLOAD ENDPOINTS ==========


# ========== GAP SCORING & COMPLIANCE ENDPOINTS ==========

@api_router.get("/compliance/score/{analysis_id}")
async def get_compliance_score(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed compliance scoring breakdown for a gap analysis."""
    analysis = await db.gap_analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    gaps = analysis.get("gaps", [])
    summary = gap_scoring_service.generate_compliance_summary(
        gaps, analysis.get("policy_title", ""), analysis.get("regulation_title", "")
    )
    summary["analysis_id"] = analysis_id
    return summary

@api_router.get("/compliance/trend")
async def get_compliance_trend(
    policy_id: Optional[str] = None,
    regulation_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get compliance score trend over time."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'default')
    trend = await gap_scoring_service.get_compliance_trend(
        policy_id=policy_id, regulation_id=regulation_id, organization=organization
    )
    return {"trend": trend}

@api_router.get("/compliance/overview")
async def get_compliance_overview(current_user: dict = Depends(get_current_user)):
    """Get organization-wide compliance overview for dashboard."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'default')
    overview = await gap_scoring_service.get_organization_compliance_overview(organization)
    return overview

@api_router.get("/compliance/category-breakdown/{analysis_id}")
async def get_category_breakdown(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Get per-category compliance breakdown for a gap analysis."""
    analysis = await db.gap_analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    gaps = analysis.get("gaps", [])
    category_scores = gap_scoring_service.calculate_category_scores(gaps)
    return {"analysis_id": analysis_id, "categories": category_scores}

# ========== END GAP SCORING ENDPOINTS ==========


# ========== PA/PG COMPLIANCE CHECK ENDPOINTS ==========

@api_router.get("/compliance-checks/authorisation")
async def check_authorisation_compliance(current_user: dict = Depends(get_current_user)):
    """Check authorisation compliance status for the organization. (Task #5)"""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    profile = await org_profile_service.get_profile(organization)
    if not profile:
        return {"status": "incomplete", "message": "Organization profile not set up"}

    entity_type = profile.get('entity_type', 'unknown')
    checks = []
    # CoA check
    checks.append({
        "requirement_id": "RBI-PAPG-AUTH-001",
        "title": "Certificate of Authorisation",
        "status": "compliant" if profile.get('license_status') in ('authorized', 'conditional') else "non_compliant",
        "details": f"License status: {profile.get('license_status', 'unknown')}",
        "criticality": "high",
    })
    # PRAVAAH check for non-bank PAs
    if entity_type in ('non_bank_pa', 'pa_p'):
        checks.append({
            "requirement_id": "RBI-PAPG-AUTH-002",
            "title": "PRAVAAH Application",
            "status": "compliant" if profile.get('pravaah_application_id') else "non_compliant",
            "details": f"PRAVAAH ID: {profile.get('pravaah_application_id', 'Not submitted')}",
            "criticality": "high",
        })
    # Fit and proper
    personnel = profile.get('key_personnel', [])
    fit_proper_ok = all(p.get('is_fit_and_proper', False) for p in personnel) if personnel else False
    checks.append({
        "requirement_id": "RBI-PAPG-AUTH-003",
        "title": "Fit and Proper Criteria",
        "status": "compliant" if fit_proper_ok else ("partial" if personnel else "non_compliant"),
        "details": f"{len(personnel)} personnel on record",
        "criticality": "high",
    })

    compliant = len([c for c in checks if c['status'] == 'compliant'])
    return {
        "category": "authorisation",
        "total_checks": len(checks),
        "compliant": compliant,
        "score": round((compliant / len(checks)) * 100, 1) if checks else 0,
        "checks": checks,
    }

@api_router.get("/compliance-checks/capital")
async def check_capital_compliance(current_user: dict = Depends(get_current_user)):
    """Check capital and financial compliance. (Task #8)"""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    profile = await org_profile_service.get_profile(organization)
    if not profile:
        return {"status": "incomplete", "message": "Organization profile not set up"}

    entity_type = profile.get('entity_type', 'unknown')
    thresholds = org_profile_service.get_entity_specific_thresholds(entity_type)
    checks = []

    min_nw = thresholds.get('min_net_worth_crore')
    actual_nw = profile.get('net_worth_crore')
    if min_nw is not None:
        checks.append({
            "requirement_id": "RBI-PAPG-CAP-001",
            "title": f"Minimum Net Worth (₹{min_nw} Cr)",
            "status": "compliant" if (actual_nw and actual_nw >= min_nw) else "non_compliant",
            "details": f"Current net worth: ₹{actual_nw or 'Not reported'} Cr",
            "criticality": "high",
        })

    if thresholds.get('escrow_account_required'):
        checks.append({
            "requirement_id": "RBI-PAPG-ESC-001",
            "title": "Escrow Account Maintenance",
            "status": "compliant" if profile.get('escrow_bank_name') else "non_compliant",
            "details": f"Escrow bank: {profile.get('escrow_bank_name', 'Not configured')}",
            "criticality": "high",
        })

    if thresholds.get('nodal_account_required'):
        checks.append({
            "requirement_id": "RBI-PAPG-ESC-003",
            "title": "Nodal Account",
            "status": "compliant" if profile.get('nodal_account_bank') else "non_compliant",
            "details": f"Nodal bank: {profile.get('nodal_account_bank', 'Not configured')}",
            "criticality": "medium",
        })

    compliant = len([c for c in checks if c['status'] == 'compliant'])
    return {
        "category": "capital_and_financial",
        "total_checks": len(checks),
        "compliant": compliant,
        "score": round((compliant / len(checks)) * 100, 1) if checks else 0,
        "checks": checks,
    }

@api_router.get("/compliance-checks/governance")
async def check_governance_compliance(current_user: dict = Depends(get_current_user)):
    """Check governance and personnel compliance. (Tasks #5, #6)"""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    profile = await org_profile_service.get_profile(organization)
    if not profile:
        return {"status": "incomplete", "message": "Organization profile not set up"}

    personnel = profile.get('key_personnel', [])
    roles = {p.get('role') for p in personnel}
    checks = []

    checks.append({
        "requirement_id": "RBI-PAPG-GOV-002",
        "title": "Chief Compliance Officer (CCO)",
        "status": "compliant" if 'cco' in roles else "non_compliant",
        "details": next((p.get('name') for p in personnel if p.get('role') == 'cco'), 'Not appointed'),
        "criticality": "high",
    })
    checks.append({
        "requirement_id": "RBI-PAPG-TEC-001",
        "title": "Chief Information Security Officer (CISO)",
        "status": "compliant" if 'ciso' in roles else "non_compliant",
        "details": next((p.get('name') for p in personnel if p.get('role') == 'ciso'), 'Not appointed'),
        "criticality": "high",
    })
    checks.append({
        "requirement_id": "RBI-PAPG-GOV-001",
        "title": "Board Compliance Oversight",
        "status": "partial",  # Needs gap analysis data
        "details": "Requires Board minutes and compliance reports evidence",
        "criticality": "high",
    })

    compliant = len([c for c in checks if c['status'] == 'compliant'])
    return {
        "category": "governance",
        "total_checks": len(checks),
        "compliant": compliant,
        "score": round((compliant / len(checks)) * 100, 1) if checks else 0,
        "checks": checks,
    }

@api_router.get("/compliance-checks/all")
async def get_all_compliance_checks(current_user: dict = Depends(get_current_user)):
    """Run all compliance checks and return aggregate result."""
    auth = await check_authorisation_compliance(current_user)
    capital = await check_capital_compliance(current_user)
    governance = await check_governance_compliance(current_user)

    categories = [auth, capital, governance]
    all_checks = []
    for cat in categories:
        all_checks.extend(cat.get("checks", []))

    total = len(all_checks)
    compliant = len([c for c in all_checks if c.get('status') == 'compliant'])

    return {
        "overall_score": round((compliant / total) * 100, 1) if total else 0,
        "total_checks": total,
        "compliant": compliant,
        "categories": {
            "authorisation": auth,
            "capital_and_financial": capital,
            "governance": governance,
        },
    }

# ========== DOMAIN-SPECIFIC COMPLIANCE CHECKS (Tasks #6, #7, #24, #27, #28) ==========

@api_router.get("/compliance-checks/merchant-onboarding")
async def check_merchant_onboarding(current_user: dict = Depends(get_current_user)):
    """Check merchant onboarding compliance (Task #6)."""
    return await compliance_checks_service.check_merchant_onboarding(current_user['user_id'])

@api_router.get("/compliance-checks/settlement")
async def check_settlement_compliance(current_user: dict = Depends(get_current_user)):
    """Check settlement operations compliance (Task #7)."""
    return await compliance_checks_service.check_settlement_operations(current_user['user_id'])

@api_router.get("/compliance-checks/escrow")
async def check_escrow_compliance(current_user: dict = Depends(get_current_user)):
    """Check escrow and nodal account compliance (Task #27)."""
    return await compliance_checks_service.check_escrow_compliance(current_user['user_id'])

@api_router.get("/compliance-checks/fraud-monitoring")
async def check_fraud_monitoring_compliance(current_user: dict = Depends(get_current_user)):
    """Check fraud monitoring compliance (Task #28)."""
    return await compliance_checks_service.check_fraud_monitoring(current_user['user_id'])

@api_router.get("/compliance-checks/pa-p")
async def check_pa_p_compliance(current_user: dict = Depends(get_current_user)):
    """Check PA-P physical terminal compliance (Task #24)."""
    return await compliance_checks_service.check_pa_p_compliance(current_user['user_id'])

@api_router.get("/compliance-checks/comprehensive")
async def run_comprehensive_compliance_checks(current_user: dict = Depends(get_current_user)):
    """Run ALL compliance checks (auth + capital + governance + domain) and aggregate."""
    # Basic checks
    auth = await check_authorisation_compliance(current_user)
    capital = await check_capital_compliance(current_user)
    governance = await check_governance_compliance(current_user)
    # Domain checks
    domain = await compliance_checks_service.run_all_checks(current_user['user_id'])

    all_checks = []
    for cat in [auth, capital, governance]:
        all_checks.extend(cat.get("checks", []))
    for cat_result in domain.get("categories", {}).values():
        all_checks.extend(cat_result.get("checks", []))

    total = len(all_checks)
    compliant = len([c for c in all_checks if c.get('status') == 'compliant'])

    return {
        "overall_score": round((compliant / total) * 100, 1) if total else 0,
        "total_checks": total,
        "compliant": compliant,
        "needs_evidence": len([c for c in all_checks if c.get('status') == 'needs_evidence']),
        "non_compliant": len([c for c in all_checks if c.get('status') == 'non_compliant']),
        "categories": {
            "authorisation": auth,
            "capital_and_financial": capital,
            "governance": governance,
            **domain.get("categories", {}),
        },
    }

# ========== END DOMAIN-SPECIFIC COMPLIANCE CHECKS ==========


# ========== END PA/PG COMPLIANCE CHECK ENDPOINTS ==========


# ========== COMPLIANCE DEADLINE TRACKER ENDPOINTS (Task #26) ==========

@api_router.get("/compliance/deadlines")
async def get_compliance_deadlines(current_user: dict = Depends(get_current_user)):
    """Get upcoming compliance deadlines based on entity type and regulations."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    profile = await org_profile_service.get_profile(organization)

    deadlines = []
    # Standard RBI deadlines for PAs
    if profile and profile.get('entity_type') in ('non_bank_pa', 'bank_pa', 'pa_p'):
        # System audit
        deadlines.append({
            "id": "deadline-sys-audit",
            "title": "Annual System Audit (CERT-In empanelled)",
            "requirement_id": "RBI-PAPG-TEC-003",
            "frequency": "annual",
            "next_due": profile.get('next_audit_due_date', 'Not set'),
            "criticality": "high",
            "status": "pending",
        })
        # Net worth certification
        if profile.get('entity_type') != 'bank_pa':
            deadlines.append({
                "id": "deadline-networth",
                "title": "Net Worth Certificate Submission",
                "requirement_id": "RBI-PAPG-CAP-001",
                "frequency": "annual",
                "next_due": "Within 6 months of financial year end",
                "criticality": "high",
                "status": "pending",
            })
        # Compliance report to Board
        deadlines.append({
            "id": "deadline-board-report",
            "title": "Quarterly Compliance Report to Board",
            "requirement_id": "RBI-PAPG-GOV-001",
            "frequency": "quarterly",
            "next_due": "End of current quarter",
            "criticality": "medium",
            "status": "pending",
        })

    # Task-based deadlines
    task_cursor = db.tasks.find(
        {"organization": organization, "due_date": {"$ne": None}, "status": {"$nin": ["Completed", "Closed"]}},
        {"_id": 0, "id": 1, "title": 1, "due_date": 1, "priority": 1, "status": 1}
    ).sort("due_date", 1).limit(20)
    tasks = await task_cursor.to_list(length=20)

    for t in tasks:
        deadlines.append({
            "id": f"task-{t['id']}",
            "title": t.get("title", ""),
            "type": "task",
            "next_due": t.get("due_date", ""),
            "criticality": t.get("priority", "Medium").lower(),
            "status": t.get("status", "Open"),
        })

    return {"deadlines": deadlines, "total": len(deadlines)}

# ========== END COMPLIANCE DEADLINE TRACKER ENDPOINTS ==========


# ========== REMEDIATION ENDPOINTS (Task #10) ==========

@api_router.get("/remediation/{analysis_id}")
async def get_remediation_list(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Generate prioritized remediation list from a gap analysis."""
    result = await remediation_service.generate_remediation_list(analysis_id, current_user['user_id'])
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@api_router.post("/remediation/{analysis_id}/create-tasks")
async def create_remediation_tasks(analysis_id: str, max_tasks: int = 20, current_user: dict = Depends(get_current_user)):
    """Auto-create tasks from top remediation items."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    result = await remediation_service.create_remediation_tasks(
        analysis_id, current_user['user_id'], organization, max_tasks
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# ========== END REMEDIATION ENDPOINTS ==========


# ========== POLICY DRAFTING ENDPOINTS (Tasks #11, #12) ==========

@api_router.post("/policy-drafts/generate")
async def generate_policy_draft(
    title: str = Body(...),
    policy_type: str = Body(...),
    instructions: str = Body(""),
    gap_analysis_id: str = Body(None),
    current_user: dict = Depends(get_current_user)
):
    """Generate an AI policy draft based on requirements and gaps."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    profile = await org_profile_service.get_profile(organization)
    entity_type = (profile or {}).get('entity_type', 'non_bank_pa')

    requirements = []
    gaps = []

    if gap_analysis_id:
        analysis = await db.gap_analyses.find_one({"id": gap_analysis_id}, {"_id": 0})
        if analysis:
            gaps = [g for g in analysis.get("gaps", []) if g.get("gap_type") not in ("compliant", "exceeds")][:10]
            # Also fetch linked requirements
            reg_id = analysis.get("regulation_id")
            if reg_id:
                req_cursor = db.requirements.find(
                    {"regulation_id": reg_id},
                    {"_id": 0}
                ).limit(15)
                requirements = await req_cursor.to_list(length=15)

    result = await policy_drafting_service.generate_policy_draft(
        title=title,
        policy_type=policy_type,
        requirements=requirements,
        gaps=gaps,
        entity_type=entity_type,
        organization=organization,
        user_id=current_user['user_id'],
        instructions=instructions,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@api_router.get("/policy-drafts")
async def list_policy_drafts(current_user: dict = Depends(get_current_user)):
    """List all policy drafts for the user's organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    drafts = await policy_drafting_service.list_drafts(current_user['user_id'], organization)
    return {"drafts": drafts, "total": len(drafts)}

@api_router.get("/policy-drafts/{draft_id}")
async def get_policy_draft(draft_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific policy draft by ID."""
    draft = await policy_drafting_service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft

@api_router.put("/policy-drafts/{draft_id}/status")
async def update_draft_status(
    draft_id: str,
    status: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Update policy draft status (draft → review → approved → published)."""
    valid_statuses = ["draft", "review", "approved", "published", "rejected"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    result = await policy_drafting_service.update_draft_status(draft_id, status, current_user['user_id'])
    if not result:
        raise HTTPException(status_code=404, detail="Draft not found")
    return result

@api_router.post("/policy-drafts/sop/{requirement_id}")
async def generate_sop(
    requirement_id: str,
    regulation_id: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Generate a Standard Operating Procedure from a requirement."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    result = await policy_drafting_service.generate_sop_from_requirement(
        requirement_id=requirement_id,
        regulation_id=regulation_id,
        user_id=current_user['user_id'],
        organization=organization,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# ========== END POLICY DRAFTING ENDPOINTS ==========


# ========== SOP TEMPLATES ENDPOINTS (Task #12) ==========

@api_router.get("/sop-templates")
async def list_sop_templates(
    entity_type: str = None,
    category: str = None,
    current_user: dict = Depends(get_current_user)
):
    """List available SOP templates, optionally filtered."""
    templates = sop_templates_service.list_templates(entity_type=entity_type, category=category)
    return {"templates": templates, "total": len(templates)}

@api_router.get("/sop-templates/{template_key}")
async def get_sop_template(template_key: str, current_user: dict = Depends(get_current_user)):
    """Get a full SOP template by key."""
    template = sop_templates_service.get_template(template_key)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@api_router.post("/sop-templates/{template_key}/instantiate")
async def instantiate_sop_template(
    template_key: str,
    customizations: Dict[str, Any] = Body(default={}),
    current_user: dict = Depends(get_current_user)
):
    """Create a policy draft from an SOP template."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    result = await sop_templates_service.instantiate_template(
        template_key=template_key,
        organization=organization,
        user_id=current_user['user_id'],
        customizations=customizations,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.post("/sop-templates/generate-custom")
async def generate_custom_sop(
    topic: str = Body(...),
    instructions: str = Body(""),
    current_user: dict = Depends(get_current_user)
):
    """Generate a custom SOP using AI."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    profile = await org_profile_service.get_profile(organization)
    entity_type = (profile or {}).get('entity_type', 'non_bank_pa')
    result = await sop_templates_service.generate_custom_sop(
        topic=topic, entity_type=entity_type,
        organization=organization, user_id=current_user['user_id'],
        instructions=instructions,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

# ========== END SOP TEMPLATES ENDPOINTS ==========


# ========== APPROVAL WORKFLOW ENDPOINTS (Task #13) ==========

@api_router.post("/approvals/create")
async def create_approval(
    document_id: str = Body(...),
    document_type: str = Body(...),
    document_title: str = Body(""),
    chain_type: str = Body(None),
    current_user: dict = Depends(get_current_user)
):
    """Create an approval workflow for a document."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    result = await approval_workflow_service.create_approval_request(
        document_id=document_id,
        document_type=document_type,
        document_title=document_title,
        organization=organization,
        requested_by=current_user['user_id'],
        chain_type=chain_type,
    )
    return result

@api_router.post("/approvals/{approval_id}/decide")
async def submit_approval_decision(
    approval_id: str,
    decision: str = Body(...),
    comments: str = Body(""),
    current_user: dict = Depends(get_current_user)
):
    """Submit an approval or rejection decision."""
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0, "role": 1})
    user_role = (user_doc or {}).get('role', 'user')
    result = await approval_workflow_service.submit_decision(
        approval_id=approval_id,
        user_id=current_user['user_id'],
        user_role=user_role,
        decision=decision,
        comments=comments,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.get("/approvals/{approval_id}")
async def get_approval_workflow(approval_id: str, current_user: dict = Depends(get_current_user)):
    """Get approval workflow details."""
    workflow = await approval_workflow_service.get_workflow(approval_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@api_router.get("/approvals/pending/list")
async def list_pending_approvals(
    role: str = None,
    current_user: dict = Depends(get_current_user)
):
    """List pending approval requests."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    approvals = await approval_workflow_service.list_pending_approvals(organization, user_role=role)
    return {"approvals": approvals, "total": len(approvals)}

@api_router.get("/approvals/document/{document_id}/history")
async def get_document_approval_history(document_id: str, current_user: dict = Depends(get_current_user)):
    """Get approval history for a document."""
    history = await approval_workflow_service.get_document_approval_history(document_id)
    return {"history": history, "total": len(history)}

# ========== END APPROVAL WORKFLOW ENDPOINTS ==========


# ========== POLICY VERSION CONTROL ENDPOINTS (Task #14) ==========

@api_router.post("/policy-versions/{draft_id}/create")
async def create_policy_version(
    draft_id: str,
    change_summary: str = Body(""),
    bump_type: str = Body("minor"),
    current_user: dict = Depends(get_current_user)
):
    """Create a new version snapshot of a policy draft."""
    result = await policy_version_service.create_version(
        draft_id=draft_id,
        user_id=current_user['user_id'],
        change_summary=change_summary,
        bump_type=bump_type,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.get("/policy-versions/{draft_id}")
async def list_policy_versions(draft_id: str, current_user: dict = Depends(get_current_user)):
    """List all versions of a policy draft."""
    versions = await policy_version_service.list_versions(draft_id)
    return {"versions": versions, "total": len(versions)}

@api_router.get("/policy-versions/detail/{version_id}")
async def get_policy_version(version_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific version with full content."""
    version = await policy_version_service.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version

@api_router.post("/policy-versions/compare")
async def compare_policy_versions(
    version_id_a: str = Body(...),
    version_id_b: str = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Compare two versions and return differences."""
    result = await policy_version_service.compare_versions(version_id_a, version_id_b)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.post("/policy-versions/{draft_id}/rollback")
async def rollback_policy_version(
    draft_id: str,
    version_id: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Rollback a draft to a previous version."""
    result = await policy_version_service.rollback_to_version(
        draft_id=draft_id, version_id=version_id, user_id=current_user['user_id']
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# ========== END POLICY VERSION CONTROL ENDPOINTS ==========


# ========== GAP ANALYSIS REPORT ENDPOINTS (Task #15) ==========

@api_router.get("/gap-reports/{analysis_id}")
async def get_gap_report(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Get or generate a gap analysis report."""
    report = await gap_report_service.get_report(analysis_id)
    if not report:
        report = await gap_report_service.generate_report(analysis_id)
        if "error" in report:
            raise HTTPException(status_code=404, detail=report["error"])
    return report

@api_router.post("/gap-reports/{analysis_id}/generate")
async def generate_gap_report(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Force regenerate a gap analysis report."""
    report = await gap_report_service.generate_report(analysis_id)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return report

@api_router.get("/gap-reports")
async def list_gap_reports(current_user: dict = Depends(get_current_user)):
    """List all gap analysis reports for the organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    reports = await gap_report_service.list_reports(organization)
    return {"reports": reports, "total": len(reports)}

# ========== END GAP ANALYSIS REPORT ENDPOINTS ==========


# ========== AUDIT TRAIL ENDPOINTS (Task #16) ==========

@api_router.get("/audit-trail")
async def get_audit_trail(
    category: str = None,
    resource_type: str = None,
    resource_id: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Query audit trail with filters."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    return await audit_trail_service.get_trail(
        organization=organization,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

@api_router.get("/audit-trail/resource/{resource_type}/{resource_id}")
async def get_resource_audit_history(
    resource_type: str, resource_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get full audit history for a specific resource."""
    history = await audit_trail_service.get_resource_history(resource_type, resource_id)
    return {"history": history, "total": len(history)}

@api_router.get("/audit-trail/user/{user_id}")
async def get_user_activity(user_id: str, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get recent activity for a specific user."""
    activity = await audit_trail_service.get_user_activity(user_id, limit)
    return {"activity": activity, "total": len(activity)}

@api_router.get("/audit-trail/summary")
async def get_activity_summary(days: int = 30, current_user: dict = Depends(get_current_user)):
    """Get activity summary for the organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    return await audit_trail_service.get_activity_summary(organization, days)

# ========== END AUDIT TRAIL ENDPOINTS ==========


# ========== REGULATORY FEED ENDPOINTS (Task #2) ==========

@api_router.get("/regulatory-feed")
async def get_regulatory_feed(
    source_key: str = None,
    change_type: str = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get regulatory amendment feed."""
    return await regulatory_feed_service.get_feed(
        source_key=source_key, change_type=change_type,
        limit=limit, offset=offset,
    )

@api_router.get("/regulatory-feed/sources")
async def list_regulatory_sources(current_user: dict = Depends(get_current_user)):
    """List all known regulatory sources."""
    sources = regulatory_feed_service.list_sources()
    return {"sources": sources}

@api_router.get("/regulatory-feed/{amendment_id}")
async def get_amendment_detail(amendment_id: str, current_user: dict = Depends(get_current_user)):
    """Get full details of a regulatory amendment."""
    amendment = await regulatory_feed_service.get_amendment(amendment_id)
    if not amendment:
        raise HTTPException(status_code=404, detail="Amendment not found")
    return amendment

@api_router.post("/regulatory-feed/amendments")
async def create_amendment(
    source_key: str = Body(...),
    title: str = Body(...),
    summary: str = Body(...),
    effective_date: str = Body(...),
    change_type: str = Body("amendment"),
    impact_areas: List[str] = Body(default=[]),
    full_text: str = Body(""),
    url: str = Body(""),
    current_user: dict = Depends(get_current_user)
):
    """Record a new regulatory amendment."""
    result = await regulatory_feed_service.create_amendment(
        source_key=source_key, title=title, summary=summary,
        effective_date=effective_date, change_type=change_type,
        impact_areas=impact_areas, full_text=full_text, url=url,
        created_by=current_user['user_id'],
    )
    return result

@api_router.post("/regulatory-feed/subscribe")
async def subscribe_to_feed(
    source_keys: List[str] = Body(default=None),
    alert_types: List[str] = Body(default=None),
    current_user: dict = Depends(get_current_user)
):
    """Subscribe to regulatory amendment alerts."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    return await regulatory_feed_service.subscribe(
        organization=organization,
        user_id=current_user['user_id'],
        source_keys=source_keys,
        alert_types=alert_types,
    )

@api_router.get("/regulatory-feed/subscription/me")
async def get_my_subscription(current_user: dict = Depends(get_current_user)):
    """Get current user's subscription preferences."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    sub = await regulatory_feed_service.get_subscription(current_user['user_id'], organization)
    return sub or {"active": False, "source_keys": [], "alert_types": []}

@api_router.get("/regulatory-feed/{amendment_id}/impact")
async def get_amendment_impact(amendment_id: str, current_user: dict = Depends(get_current_user)):
    """Assess impact of an amendment on the organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    return await regulatory_feed_service.get_impact_assessment(amendment_id, organization)

# ========== END REGULATORY FEED ENDPOINTS ==========


# ========== REPORT EXPORT ENDPOINTS (Task #17) ==========

@api_router.get("/reports/{analysis_id}/export/docx")
async def export_report_docx(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Export gap analysis report as Word document."""
    buffer = await report_export_service.export_gap_report_docx(analysis_id)
    if not buffer:
        raise HTTPException(status_code=404, detail="Report not found or export failed (python-docx may not be installed)")
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=gap-report-{analysis_id[:8]}.docx"}
    )

@api_router.get("/reports/{analysis_id}/export/pdf")
async def export_report_pdf(analysis_id: str, current_user: dict = Depends(get_current_user)):
    """Export gap analysis report as PDF."""
    buffer = await report_export_service.export_gap_report_pdf(analysis_id)
    if not buffer:
        raise HTTPException(status_code=404, detail="Report not found or export failed (reportlab may not be installed)")
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=gap-report-{analysis_id[:8]}.pdf"}
    )

@api_router.get("/policy-drafts/{draft_id}/export/docx")
async def export_policy_docx(draft_id: str, current_user: dict = Depends(get_current_user)):
    """Export a policy draft as Word document."""
    buffer = await report_export_service.export_policy_draft_docx(draft_id)
    if not buffer:
        raise HTTPException(status_code=404, detail="Draft not found or export failed")
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=policy-{draft_id[:8]}.docx"}
    )

# ========== END REPORT EXPORT ENDPOINTS ==========


# ========== i18n ENDPOINTS (Task #20) ==========

@api_router.get("/i18n/translations/{language}")
async def get_translations(language: str, current_user: dict = Depends(get_current_user)):
    """Get all translations for a language."""
    translations = i18n_service.get_all_translations(language)
    return {"language": language, "translations": translations}

@api_router.get("/i18n/glossary/{language}")
async def get_glossary(language: str, current_user: dict = Depends(get_current_user)):
    """Get compliance glossary in specified language."""
    glossary = i18n_service.get_glossary(language)
    return {"language": language, "glossary": glossary}

@api_router.get("/i18n/languages")
async def get_supported_languages(current_user: dict = Depends(get_current_user)):
    """Get list of supported languages."""
    return {"languages": i18n_service.get_supported_languages()}

@api_router.get("/i18n/preference")
async def get_language_preference(current_user: dict = Depends(get_current_user)):
    """Get current user's language preference."""
    lang = await i18n_service.get_user_language(current_user['user_id'])
    return {"language": lang}

@api_router.put("/i18n/preference")
async def set_language_preference(
    language: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Set user's language preference."""
    result = await i18n_service.set_user_language(current_user['user_id'], language)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# ========== END i18n ENDPOINTS ==========


# ========== DOCUMENT ENCRYPTION ENDPOINTS (Task #21) ==========

@api_router.get("/security/encryption-status")
async def get_encryption_status(current_user: dict = Depends(get_current_user)):
    """Get encryption configuration status."""
    return await document_encryption_service.get_encryption_status()

@api_router.get("/security/data-localization")
async def check_data_localization(current_user: dict = Depends(get_current_user)):
    """Check data localization compliance status."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    return await document_encryption_service.check_data_localization(organization)

# ========== END DOCUMENT ENCRYPTION ENDPOINTS ==========


# ========== CONFLUENCE INTEGRATION ENDPOINTS (Task #22) ==========

@api_router.get("/confluence/status")
async def get_confluence_status(current_user: dict = Depends(get_current_user)):
    """Get Confluence integration configuration status."""
    return await confluence_integration_service.get_config_status()

@api_router.post("/confluence/test")
async def test_confluence_connection(current_user: dict = Depends(get_current_user)):
    """Test Confluence API connection."""
    return await confluence_integration_service.test_connection()

@api_router.post("/confluence/publish/{draft_id}")
async def publish_to_confluence(
    draft_id: str,
    parent_page_id: str = Body(None, embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Publish an approved policy to Confluence."""
    result = await confluence_integration_service.publish_policy(draft_id, parent_page_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.post("/confluence/import/{page_id}")
async def import_from_confluence(page_id: str, current_user: dict = Depends(get_current_user)):
    """Import a Confluence page as a policy document."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    result = await confluence_integration_service.import_page(
        page_id, current_user['user_id'], organization
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@api_router.get("/confluence/pages")
async def list_confluence_pages(limit: int = 25, current_user: dict = Depends(get_current_user)):
    """List pages in the Confluence compliance space."""
    result = await confluence_integration_service.list_space_pages(limit)
    if "error" in result and not result.get("pages"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# ========== END CONFLUENCE INTEGRATION ENDPOINTS ==========


# ========== DOCUMENT OPTIMIZATION ENDPOINTS (Task #23) ==========

@api_router.get("/processing/stats")
async def get_processing_stats(current_user: dict = Depends(get_current_user)):
    """Get document processing performance statistics."""
    return await document_optimization_service.get_processing_stats()

@api_router.post("/processing/clear-cache")
async def clear_processing_cache(current_user: dict = Depends(get_current_user)):
    """Clear the document processing cache."""
    return document_optimization_service.clear_cache()

# ========== END DOCUMENT OPTIMIZATION ENDPOINTS ==========


# ========== SUCCESS METRICS ENDPOINTS (Task #29) ==========

@api_router.get("/metrics/compliance")
async def get_compliance_metrics(current_user: dict = Depends(get_current_user)):
    """Get comprehensive compliance success metrics."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')
    return await success_metrics_service.get_compliance_metrics(organization)

# ========== END SUCCESS METRICS ENDPOINTS ==========


# ========== TEAM MANAGEMENT ENDPOINTS ==========

@api_router.post("/team-members", response_model=TeamMember)
async def create_team_member(member_data: TeamMemberCreate, current_user: dict = Depends(get_current_user)):
    """Create a new team member."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    # Check if member with same email already exists
    existing = await db.team_members.find_one({
        "organization": user_doc.get('organization', 'Default'),
        "email": member_data.email
    })
    if existing:
        raise HTTPException(status_code=400, detail="Team member with this email already exists")
    
    member = TeamMember(
        name=member_data.name,
        team=member_data.team,
        email=member_data.email,
        role=member_data.role,
        organization=user_doc.get('organization', 'Default')
    )
    
    member_dict = member.model_dump()
    member_dict['created_at'] = member_dict['created_at'].isoformat()
    member_dict['updated_at'] = member_dict['updated_at'].isoformat()
    
    await db.team_members.insert_one(member_dict)
    return member


@api_router.get("/team-members", response_model=List[TeamMember])
async def list_team_members(team: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """List all team members, optionally filtered by team."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    query = {
        "organization": user_doc.get('organization', 'Default'),
        "is_active": True
    }
    if team:
        query["team"] = team
    
    members = await db.team_members.find(query, {"_id": 0}).to_list(length=None)
    return members


@api_router.get("/team-members/{member_id}", response_model=TeamMember)
async def get_team_member(member_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific team member."""
    member = await db.team_members.find_one({"id": member_id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    return member


@api_router.put("/team-members/{member_id}", response_model=TeamMember)
async def update_team_member(
    member_id: str,
    member_data: TeamMemberCreate,
    current_user: dict = Depends(get_current_user)
):
    """Update a team member."""
    member = await db.team_members.find_one({"id": member_id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Check if email is being changed and if new email already exists
    if member_data.email != member['email']:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        existing = await db.team_members.find_one({
            "organization": user_doc.get('organization', 'Default'),
            "email": member_data.email,
            "id": {"$ne": member_id}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Team member with this email already exists")
    
    update_data = {
        "name": member_data.name,
        "team": member_data.team,
        "email": member_data.email,
        "role": member_data.role,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.team_members.update_one(
        {"id": member_id},
        {"$set": update_data}
    )
    
    updated_member = await db.team_members.find_one({"id": member_id}, {"_id": 0})
    return updated_member


@api_router.delete("/team-members/{member_id}")
async def delete_team_member(member_id: str, current_user: dict = Depends(get_current_user)):
    """Soft delete a team member."""
    member = await db.team_members.find_one({"id": member_id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Soft delete by setting is_active to False
    await db.team_members.update_one(
        {"id": member_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Team member deleted successfully"}


@api_router.post("/team-members/upload-csv")
async def upload_team_csv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload team members via CSV file. Expected columns: Name, Team, Email, Role"""
    import csv
    import io
    
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')
    
    # Read CSV file
    contents = await file.read()
    decoded = contents.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(decoded))
    
    # Validate headers
    required_headers = {'Name', 'Team', 'Email', 'Role'}
    headers = set(csv_reader.fieldnames or [])
    if not required_headers.issubset(headers):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain columns: {', '.join(required_headers)}"
        )
    
    created_count = 0
    updated_count = 0
    errors = []
    
    for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (1 is header)
        try:
            name = row['Name'].strip()
            team = row['Team'].strip()
            email = row['Email'].strip().lower()
            role = row['Role'].strip()
            
            if not all([name, team, email, role]):
                errors.append(f"Row {row_num}: Missing required fields")
                continue
            
            # Check if member exists
            existing = await db.team_members.find_one({
                "organization": organization,
                "email": email
            })
            
            if existing:
                # Update existing member
                await db.team_members.update_one(
                    {"id": existing['id']},
                    {"$set": {
                        "name": name,
                        "team": team,
                        "role": role,
                        "is_active": True,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                updated_count += 1
            else:
                # Create new member
                member = TeamMember(
                    name=name,
                    team=team,
                    email=email,
                    role=role,
                    organization=organization
                )
                member_dict = member.model_dump()
                member_dict['created_at'] = member_dict['created_at'].isoformat()
                member_dict['updated_at'] = member_dict['updated_at'].isoformat()
                await db.team_members.insert_one(member_dict)
                created_count += 1
                
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
    
    return {
        "message": "CSV upload completed",
        "created": created_count,
        "updated": updated_count,
        "errors": errors
    }


@api_router.get("/team-members/download/sample-csv")
async def download_sample_csv():
    """Download a sample CSV template for team member upload."""
    import io
    import csv
    
    # Create sample CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Team', 'Email', 'Role'])
    writer.writerow(['John Doe', 'Tech', 'john.doe@example.com', 'SPOC'])
    writer.writerow(['Jane Smith', 'Product', 'jane.smith@example.com', 'Lead'])
    writer.writerow(['Bob Johnson', 'Infosec', 'bob.johnson@example.com', 'Member'])
    
    csv_content = output.getvalue()
    
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=team_members_sample.csv"}
    )


# ========== END TEAM MANAGEMENT ENDPOINTS ==========


# ========== ORGANIZATION INVITE ENDPOINTS ==========

@api_router.post("/invites", response_model=UserInvite)
async def create_invite(invite_data: UserInviteCreate, current_user: dict = Depends(get_current_user)):
    """Send an invitation to join the organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')
    inviter_email = user_doc.get('email', '')
    
    # Validate email format
    email = invite_data.email.lower().strip()
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    
    # Email domain validation - invited email must match inviter's domain
    inviter_domain = inviter_email.split('@')[1] if '@' in inviter_email else ''
    invited_domain = email.split('@')[1] if '@' in email else ''
    
    if inviter_domain and invited_domain != inviter_domain:
        raise HTTPException(
            status_code=400, 
            detail=f"Can only invite users from the same email domain (@{inviter_domain})"
        )
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Check if there's already a pending invite
    existing_invite = await db.user_invites.find_one({
        "email": email,
        "organization": organization,
        "status": "pending"
    })
    if existing_invite:
        raise HTTPException(status_code=400, detail="Pending invite already exists for this email")
    
    # Create invite
    invite = UserInvite(
        email=email,
        organization=organization,
        invited_by=current_user['user_id'],
        invited_by_name=user_doc.get('full_name', 'Unknown'),
        role=invite_data.role
    )
    
    invite_dict = invite.model_dump()
    invite_dict['created_at'] = invite_dict['created_at'].isoformat()
    invite_dict['expires_at'] = invite_dict['expires_at'].isoformat()
    if invite_dict.get('accepted_at'):
        invite_dict['accepted_at'] = invite_dict['accepted_at'].isoformat()
    
    await db.user_invites.insert_one(invite_dict)
    
    # TODO: Send email notification with invite link
    # For now, just return the invite
    
    return invite


@api_router.get("/invites", response_model=List[UserInvite])
async def list_invites(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """List all invites for the organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')
    
    query = {"organization": organization}
    if status:
        query["status"] = status
    
    invites = await db.user_invites.find(query, {"_id": 0}).sort("created_at", -1).to_list(length=None)
    return invites


@api_router.get("/invites/{invite_id}", response_model=UserInvite)
async def get_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific invite."""
    invite = await db.user_invites.find_one({"id": invite_id}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    return invite


@api_router.post("/invites/{invite_id}/resend")
async def resend_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Resend an invitation email."""
    invite = await db.user_invites.find_one({"id": invite_id}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Can only resend pending invites")
    
    # Update expiration
    new_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_invites.update_one(
        {"id": invite_id},
        {"$set": {"expires_at": new_expires_at.isoformat()}}
    )
    
    # TODO: Send email notification
    
    return {"message": "Invite resent successfully"}


@api_router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke an invitation."""
    invite = await db.user_invites.find_one({"id": invite_id}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Can only revoke pending invites")
    
    # Update status to revoked
    await db.user_invites.update_one(
        {"id": invite_id},
        {"$set": {"status": "revoked"}}
    )
    
    return {"message": "Invite revoked successfully"}


@api_router.get("/invites/check/{token}")
async def check_invite_token(token: str):
    """Check if an invite token is valid (public endpoint)."""
    invite = await db.user_invites.find_one({"invite_token": token}, {"_id": 0})
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite token")
    
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Invite is no longer valid")
    
    # Check expiration
    expires_at = datetime.fromisoformat(invite['expires_at'])
    if datetime.now(timezone.utc) > expires_at:
        # Mark as expired
        await db.user_invites.update_one(
            {"id": invite['id']},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    return {
        "email": invite['email'],
        "organization": invite['organization'],
        "invited_by_name": invite['invited_by_name'],
        "role": invite['role']
    }


@api_router.post("/invites/accept/{token}")
async def accept_invite(token: str, password: str):
    """Accept an invitation and create user account (public endpoint)."""
    invite = await db.user_invites.find_one({"invite_token": token}, {"_id": 0})
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite token")
    
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Invite is no longer valid")
    
    # Check expiration
    expires_at = datetime.fromisoformat(invite['expires_at'])
    if datetime.now(timezone.utc) > expires_at:
        await db.user_invites.update_one(
            {"id": invite['id']},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(status_code=400, detail="Invite has expired")
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": invite['email']})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = User(
        email=invite['email'],
        password_hash=pwd_context.hash(password),
        full_name=invite['email'].split('@')[0],  # Default name from email
        organization=invite['organization'],
        role=invite['role']
    )
    
    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    
    await db.users.insert_one(user_dict)
    
    # Mark invite as accepted
    await db.user_invites.update_one(
        {"id": invite['id']},
        {"$set": {
            "status": "accepted",
            "accepted_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message": "Account created successfully", "email": invite['email']}


# ========== END ORGANIZATION INVITE ENDPOINTS ==========


# ========== POLICY ENDPOINTS ==========
@api_router.get("/policies")
async def get_policies(current_user: dict = Depends(get_current_user)):
    # Get user details to check role
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    # Role-based access:
    # - compliance_head and auditor: see ALL policies in organization
    # - user: see only own policies
    if user_role in ['compliance_head', 'auditor']:
        query = {"organization": organization}
    else:
        query = {"user_id": current_user['user_id']}

    policies = await db.policies.find(query, {"_id": 0}).to_list(1000)
    for policy in policies:
        if isinstance(policy.get('created_at'), str):
            try:
                policy['created_at'] = datetime.fromisoformat(policy['created_at']).isoformat()
            except (ValueError, TypeError):
                policy['created_at'] = datetime.now(timezone.utc).isoformat()
        elif isinstance(policy.get('created_at'), datetime):
            policy['created_at'] = policy['created_at'].isoformat()
        if isinstance(policy.get('updated_at'), str):
            try:
                policy['updated_at'] = datetime.fromisoformat(policy['updated_at']).isoformat()
            except (ValueError, TypeError):
                policy['updated_at'] = datetime.now(timezone.utc).isoformat()
        elif isinstance(policy.get('updated_at'), datetime):
            policy['updated_at'] = policy['updated_at'].isoformat()
    return policies


async def process_policy_upload_background(
    job_id: str,
    file_content: bytes,
    file_name: str,
    policy_info: dict,
    user_id: str,
    organization: str
):
    """Background task for processing policy upload with progress updates."""
    import time
    import uuid as uuid_module
    import asyncio
    
    upload_start = time.time()
    
    try:
        logger.info("="*70)
        logger.info("[POLICY UPLOAD] ========== STARTING ==========")
        logger.info(f"  Job: {job_id}")
        logger.info(f"  File: {file_name} ({len(file_content)} bytes)")
        logger.info(f"  Title: {policy_info.get('title', file_name)}")
        logger.info(f"  User: {user_id}")
        logger.info("="*70)
        
        # Step 1: Save file (10%)
        step_start = time.time()
        await upload_job_service.update_progress(
            job_id, 10, "Saving file...", 1, status="uploading"
        )
        
        file_path = await doc_service.save_file(file_content, file_name)
        logger.info(f"  [Step 1/7] File saved in {time.time()-step_start:.1f}s → {file_path}")

        # Step 2: Text Extraction via Anthropic OCR (20-30%)
        step_start = time.time()
        file_extension = os.path.splitext(file_name)[1].lower()
        file_type = "PDF" if file_extension == ".pdf" else "DOCX" if file_extension in [".docx", ".doc"] else "TXT"

        await upload_job_service.update_progress(
            job_id, 15, f"OCR: Extracting text from {file_type} using Claude Vision...", 2, status="processing"
        )

        text = await doc_service.extract_text(file_path)
        ocr_time = time.time() - step_start
        
        await upload_job_service.update_progress(
            job_id, 25, f"OCR complete: {len(text)} chars in {ocr_time:.0f}s", 2
        )
        logger.info(f"  [Step 2/7] Text extraction: {len(text)} chars in {ocr_time:.1f}s")
        
        document_title = policy_info.get('title', file_name)
        
        # Step 3: LLM Policy Analysis (Sonnet 4 — fast impact analysis)
        step_start = time.time()
        await upload_job_service.update_progress(
            job_id, 30, "AI analyzing policy impact (Sonnet 4)...", 3, status="analyzing"
        )
        
        try:
            analysis = await llm_service.analyze_policy_document(text, document_title)
            analysis_time = time.time() - step_start
            logger.info(f"  [Step 3/7] Policy analysis: {len(analysis)} fields in {analysis_time:.1f}s")
        except Exception as e:
            analysis_time = time.time() - step_start
            logger.warning(f"  [Step 3/7] Policy analysis FAILED in {analysis_time:.1f}s: {e}")
            analysis = {}
        
        await upload_job_service.update_progress(
            job_id, 40, f"Impact analysis complete ({analysis_time:.0f}s)", 3
        )
        
        # Step 4: LLM Clause Extraction (Sonnet 4 — streaming)
        step_start = time.time()
        await upload_job_service.update_progress(
            job_id, 45, "AI extracting policy clauses (Sonnet 4)...", 4, status="extracting"
        )
        
        document_id = str(uuid_module.uuid4())
        
        try:
            clauses_data = await asyncio.wait_for(
                clause_extractor.extract_clauses_from_document(
                    text=text,
                    document_type="policy",
                    document_id=document_id,
                    document_title=document_title
                ),
                timeout=300  # 5 minute timeout for LLM extraction
            )
        except asyncio.TimeoutError:
            logger.warning(f"  [Step 4/7] Clause extraction TIMEOUT after 300s, using fallback")
            clauses_data = clause_extractor._fallback_clause_extraction_with_enrichment(
                clause_extractor._split_into_chunks(text),
                "policy", document_id
            )
        
        extraction_time = time.time() - step_start
        logger.info(f"  [Step 4/7] Clause extraction: {len(clauses_data)} clauses in {extraction_time:.1f}s")
        
        await upload_job_service.update_progress(
            job_id, 70, f"Extracted {len(clauses_data)} clauses ({extraction_time:.0f}s)", 4,
            clauses_extracted=len(clauses_data)
        )
        
        # Step 5: Creating Clause Objects (80%)
        step_start = time.time()
        await upload_job_service.update_progress(
            job_id, 75, "Building clause objects...", 5, status="analyzing"
        )
        
        clauses = []
        for clause_data in clauses_data:
            clause = Clause(
                clause_id=clause_data.get('clause_id', str(uuid_module.uuid4())),
                text=clause_data.get('original_text', ''),
                original_text=clause_data.get('original_text', ''),
                section=clause_data.get('section'),
                page_number=clause_data.get('page_number'),
                title=clause_data.get('title'),
                content=clause_data.get('content'),
                tags=clause_data.get('tags', []),
                requirement_type=clause_data.get('requirement_type', 'informational'),
                subject_category=clause_data.get('subject_category', 'general'),
                key_obligations=clause_data.get('key_obligations', []),
                semantic_summary=clause_data.get('semantic_summary'),
                entities_involved=clause_data.get('entities_involved', []),
                keywords=clause_data.get('keywords', []),
                compliance_indicators=clause_data.get('compliance_indicators', []),
                criticality=clause_data.get('criticality', 'medium')
            )
            clauses.append(clause)
        
        await upload_job_service.update_progress(
            job_id, 85, "Saving to database...", 6
        )
        
        logger.info(f"  [Step 5/7] Clause objects built: {len(clauses)} in {time.time()-step_start:.1f}s")
        
        # Feature #27: Auto-detect policy type from content if not explicitly specified
        user_specified_type = policy_info.get('policy_type', 'Other')
        detected_type = user_specified_type
        if user_specified_type in ('Other', 'OTHER', '', None):
            # Auto-detect from extracted text content
            text_lower = text.lower() if text else ""
            clause_text_combined = " ".join([c.get('original_text', '') for c in clauses_data]).lower()
            combined_text = text_lower + " " + clause_text_combined

            # Policy type detection rules based on keyword frequency
            type_scores = {
                'KYC': 0,
                'AML': 0,
                'DIGITAL_LENDING': 0,
                'INFOSEC': 0,
                'OUTSOURCING': 0,
                'RISK_MANAGEMENT': 0,
                'FRAUD': 0,
                'UPI': 0,
                'FAIR_PRACTICE_CODE': 0,
            }

            # KYC keywords
            kyc_keywords = ['know your customer', 'kyc', 'customer identification', 'cdd', 'customer due diligence', 'identity verification', 'ckyc', 'e-kyc', 'video kyc', 'v-kyc', 'beneficial owner', 'pep', 'politically exposed']
            for kw in kyc_keywords:
                type_scores['KYC'] += combined_text.count(kw) * 3

            # AML keywords
            aml_keywords = ['anti-money laundering', 'aml', 'money laundering', 'suspicious transaction', 'str', 'ctr', 'cash transaction', 'terrorist financing', 'cft', 'fiu', 'pmla', 'prevention of money laundering', 'hawala', 'structuring']
            for kw in aml_keywords:
                type_scores['AML'] += combined_text.count(kw) * 3

            # Digital Lending keywords
            dl_keywords = ['digital lending', 'digital loan', 'nbfc', 'lending service', 'loan origination', 'lms', 'los', 'key fact statement', 'kfs', 'annual percentage rate', 'apr', 'fair practice code for digital', 'digital lending app', 'dsa', 'direct selling agent', 'penal charges']
            for kw in dl_keywords:
                type_scores['DIGITAL_LENDING'] += combined_text.count(kw) * 3

            # InfoSec keywords
            infosec_keywords = ['information security', 'infosec', 'cybersecurity', 'cyber security', 'data protection', 'data privacy', 'encryption', 'access control', 'incident response', 'vulnerability', 'penetration testing', 'iso 27001', 'isms', 'firewall', 'intrusion detection']
            for kw in infosec_keywords:
                type_scores['INFOSEC'] += combined_text.count(kw) * 3

            # Outsourcing keywords
            outsourcing_keywords = ['outsourcing', 'outsourced', 'third party', 'third-party', 'vendor management', 'service provider', 'sub-contracting', 'subcontracting', 'managed services', 'it outsourcing', 'bpo']
            for kw in outsourcing_keywords:
                type_scores['OUTSOURCING'] += combined_text.count(kw) * 3

            # Risk Management keywords
            risk_keywords = ['risk management', 'risk assessment', 'operational risk', 'credit risk', 'market risk', 'liquidity risk', 'risk appetite', 'risk framework', 'risk committee', 'risk mitigation', 'enterprise risk', 'erm']
            for kw in risk_keywords:
                type_scores['RISK_MANAGEMENT'] += combined_text.count(kw) * 3

            # Fraud keywords
            fraud_keywords = ['fraud', 'fraud prevention', 'fraud detection', 'fraudulent', 'phishing', 'social engineering', 'account takeover', 'identity theft', 'card fraud', 'wire fraud']
            for kw in fraud_keywords:
                type_scores['FRAUD'] += combined_text.count(kw) * 3

            # UPI keywords
            upi_keywords = ['upi', 'unified payment interface', 'npci', 'imps', 'neft', 'rtgs', 'payment system', 'upi mandate', 'autopay', 'bhim']
            for kw in upi_keywords:
                type_scores['UPI'] += combined_text.count(kw) * 3

            # Fair Practice Code keywords
            fpc_keywords = ['fair practice', 'fair practices code', 'customer grievance', 'grievance redressal', 'transparency', 'loan agreement', 'penal interest', 'prepayment', 'foreclosure', 'privacy of customer']
            for kw in fpc_keywords:
                type_scores['FAIR_PRACTICE_CODE'] += combined_text.count(kw) * 3

            # Find the highest scoring type
            max_score = max(type_scores.values())
            if max_score >= 6:  # At least 2 keyword matches
                detected_type = max(type_scores, key=type_scores.get)
                logger.info(f"[POLICY UPLOAD] Auto-detected policy type: {detected_type} (score: {max_score})")
            else:
                detected_type = user_specified_type  # Keep original if no strong signal

        # Step 6: Save to Database
        step_start = time.time()
        policy = Policy(
            title=policy_info.get('title', file_name),
            policy_type=detected_type,
            file_url=file_path,
            file_name=file_name,
            clauses=clauses,
            summary=analysis.get('summary'),
            impact_organization=analysis.get('org_impact'),
            impact_technical=analysis.get('technical_impact'),
            impact_operational=analysis.get('operational_impact'),
            key_areas=analysis.get('key_areas', []),
            user_id=user_id,
            organization=organization,
            department=policy_info.get('department') or analysis.get('department')
        )
        # Store auto-detection info
        policy_dict_extra = {"auto_detected_type": detected_type if detected_type != user_specified_type else None,
                             "user_specified_type": user_specified_type}
        
        policy_dict = policy.model_dump()
        policy_dict['created_at'] = policy_dict['created_at'].isoformat()
        policy_dict['updated_at'] = policy_dict['updated_at'].isoformat()
        # Feature #27: Store auto-detection metadata
        policy_dict.update(policy_dict_extra)
        policy_dict['audit_trail'] = []  # Initialize audit trail

        await db.policies.insert_one(policy_dict)
        logger.info(f"  [Step 6/7] Saved to MongoDB in {time.time()-step_start:.1f}s (type: {detected_type})")

        # Step 7: Store clause embeddings in Qdrant (95%)
        step_start = time.time()
        await upload_job_service.update_progress(
            job_id, 90, "Generating vector embeddings (local model)...", 7, status="vectorizing"
        )

        if vector_service:
            # Convert clauses to dict format for vector service
            clauses_for_vector = []
            for clause in clauses:
                clauses_for_vector.append({
                    'clause_id': clause.clause_id,
                    'text': clause.text,
                    'original_text': clause.original_text,
                    'section': clause.section,
                    'page_number': clause.page_number,
                    'title': clause.title,
                    'requirement_type': clause.requirement_type,
                    'subject_category': clause.subject_category,
                    'criticality': clause.criticality,
                    'tags': clause.tags,
                    'keywords': clause.keywords
                })

            stored_count = await vector_service.store_policy_clauses(
                policy_id=policy.id,
                clauses=clauses_for_vector,
                organization=organization,
                user_id=user_id
            )
            embed_time = time.time() - step_start
            logger.info(f"  [Step 7/7] Vector embeddings: {stored_count} stored in {embed_time:.1f}s")

        # Mark as completed
        total_time = time.time() - upload_start
        await upload_job_service.complete_job(
            job_id=job_id,
            result_id=policy.id,
            result_title=policy.title,
            clauses_extracted=len(clauses)
        )

        logger.info("="*70)
        logger.info(f"[POLICY UPLOAD] ========== COMPLETE ==========")
        logger.info(f"  Title: {policy.title}")
        logger.info(f"  Type: {detected_type}")
        logger.info(f"  Clauses: {len(clauses)}")
        logger.info(f"  Summary: {(analysis.get('summary') or 'N/A')[:100]}...")
        logger.info(f"  Total Time: {total_time:.1f}s ({total_time/60:.1f} min)")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"[POLICY UPLOAD] Failed job {job_id}: {str(e)}", exc_info=True)
        await upload_job_service.fail_job(job_id, str(e), str(e.__class__.__name__))


@api_router.post("/policies/reindex-vectors")
async def reindex_policy_vectors(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Re-embed all policy clauses from MongoDB into Qdrant vector store.
    Useful when switching from in-memory to server mode or after data migration."""
    try:
        if not vector_service or not vector_service.qdrant_client:
            raise HTTPException(status_code=503, detail="Vector service not available")

        # Get user info for organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default') if user_doc else 'Default'

        # Get all policies with clauses
        policies_cursor = db.policies.find(
            {"organization": organization},
            {"_id": 0}
        )
        policies = await policies_cursor.to_list(1000)

        total_clauses = 0
        total_policies = 0

        for policy_doc in policies:
            clauses = policy_doc.get('clauses', [])
            if not clauses:
                continue

            policy_id = policy_doc.get('id', '')
            clauses_for_vector = []
            for clause in clauses:
                clause_text = clause.get('text', '') or clause.get('original_text', '')
                if not clause_text:
                    continue
                clauses_for_vector.append({
                    'clause_id': clause.get('clause_id', ''),
                    'text': clause_text,
                    'original_text': clause.get('original_text', clause_text),
                    'section': clause.get('section', ''),
                    'page_number': clause.get('page_number', 0),
                    'title': clause.get('title', ''),
                    'requirement_type': clause.get('requirement_type', ''),
                    'subject_category': clause.get('subject_category', ''),
                    'criticality': clause.get('criticality', 'medium'),
                    'tags': clause.get('tags', []),
                    'keywords': clause.get('keywords', [])
                })

            if clauses_for_vector:
                stored_count = await vector_service.store_policy_clauses(
                    policy_id=policy_id,
                    clauses=clauses_for_vector,
                    organization=organization,
                    user_id=current_user['user_id']
                )
                total_clauses += stored_count
                total_policies += 1
                logger.info(f"[REINDEX] Stored {stored_count} clauses for policy '{policy_doc.get('title', 'unknown')}'")

        return {
            "message": f"Re-indexed {total_clauses} clauses from {total_policies} policies into Qdrant",
            "policies_processed": total_policies,
            "clauses_embedded": total_clauses
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reindex policy vectors: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reindex failed: {str(e)}")


@api_router.post("/policies/upload")
async def upload_policy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    policy_data: str = Form(None),
    current_user: dict = Depends(check_not_auditor)
):
    """Upload a policy document for background processing. Auditors cannot upload."""
    import json

    try:
        # Validate file type before processing
        ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}
        ALLOWED_MIME_TYPES = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
            'text/plain',
        }

        if file.filename:
            file_ext = os.path.splitext(file.filename)[1].lower()
        else:
            file_ext = ''

        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: '{file_ext or 'unknown'}'. Only PDF, DOCX, and TXT files are supported for policy upload."
            )

        # Also check MIME type if available (defense in depth)
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES and file.content_type != 'application/octet-stream':
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: '{file.content_type}'. Only PDF, DOCX, and TXT documents are supported for policy upload."
            )

        policy_info = json.loads(policy_data) if policy_data else {}

        # Read file content immediately (before background task)
        file_content = await file.read()
        file_size = len(file_content)

        # Enforce file size limit (50MB)
        MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
        if file_size > MAX_FILE_SIZE_BYTES:
            file_size_mb = round(file_size / (1024 * 1024), 1)
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({file_size_mb}MB). Maximum file size is 50MB. Please reduce the file size and try again."
            )

        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Create job for tracking
        job = await upload_job_service.create_job(
            user_id=current_user['user_id'],
            organization=organization,
            job_type="policy",
            file_name=file.filename,
            file_size=file_size,
            metadata=policy_info
        )
        
        # Start background processing
        background_tasks.add_task(
            process_policy_upload_background,
            job['id'],
            file_content,
            file.filename,
            policy_info,
            current_user['user_id'],
            organization
        )
        
        logger.info(f"[POLICY UPLOAD] Started job {job['id']} for {file.filename}")
        
        return {
            "message": "Upload started",
            "job_id": job['id'],
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting policy upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.get("/policies/{policy_id}")
async def get_policy(policy_id: str, current_user: dict = Depends(get_current_user)):
    # Get user details to check role and organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    # Role-based access:
    # - compliance_head and auditor: can view any policy in their organization
    # - user: can only view their own policies
    if user_role in ['compliance_head', 'auditor']:
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if isinstance(policy.get('created_at'), str):
        policy['created_at'] = datetime.fromisoformat(policy['created_at'])
    if isinstance(policy.get('updated_at'), str):
        policy['updated_at'] = datetime.fromisoformat(policy['updated_at'])

    # Ensure approval_history is present for frontend
    if 'approval_history' not in policy:
        policy['approval_history'] = []

    return policy

@api_router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, updates: dict, current_user: dict = Depends(get_current_user)):
    """Update policy metadata (title, department, status, policy_type, etc.)."""
    # Get user details to check role and organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    # Check if user has permission to update this policy
    # - compliance_head: can update any policy in their organization
    # - auditor: read-only (should be blocked by check_not_auditor if applied)
    # - user: can only update their own policies
    if user_role == 'compliance_head':
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Auditors should not be able to update (read-only)
    if user_role == 'auditor':
        raise HTTPException(status_code=403, detail="Auditors have read-only access. Cannot modify policies.")

    # Feature #23: Save version snapshot BEFORE applying changes
    now = datetime.now(timezone.utc).isoformat()
    # Determine the current version number from existing versions
    existing_versions = await db.policy_versions.count_documents({"policy_id": policy_id})
    version_number = existing_versions + 1

    # Build change description
    allowed_fields = {"title", "department", "status", "policy_type", "version", "owner", "effective_date", "review_date"}
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}

    changed_fields = []
    for field, new_val in update_data.items():
        old_val = policy.get(field)
        if str(old_val) != str(new_val):
            changed_fields.append({"field": field, "old_value": old_val, "new_value": new_val})

    if changed_fields or update_data:
        version_snapshot = {
            "id": str(uuid.uuid4()),
            "policy_id": policy_id,
            "version_number": version_number,
            "clauses": policy.get("clauses", []),
            "metadata_snapshot": {
                "title": policy.get("title"),
                "policy_type": policy.get("policy_type"),
                "status": policy.get("status"),
                "department": policy.get("department"),
                "owner": policy.get("owner"),
                "version": policy.get("version"),
                "effective_date": policy.get("effective_date"),
                "review_date": policy.get("review_date"),
            },
            "changes_summary": ", ".join([f"{c['field']}: {c['old_value']} → {c['new_value']}" for c in changed_fields]) if changed_fields else "Metadata update",
            "changed_fields": changed_fields,
            "created_by": current_user['user_id'],
            "created_at": now,
            "change_type": "metadata_update"
        }
        await db.policy_versions.insert_one(version_snapshot)

    update_data["updated_at"] = now

    # Build audit trail entry
    audit_entries = []
    for change in changed_fields:
        audit_entries.append({
            "action": f"Updated {change['field']}",
            "field": change['field'],
            "old_value": change['old_value'],
            "new_value": change['new_value'],
            "user": current_user['user_id'],
            "timestamp": now
        })

    update_ops = {"$set": update_data}
    if audit_entries:
        update_ops["$push"] = {"audit_trail": {"$each": audit_entries}}

    await db.policies.update_one({"id": policy_id}, update_ops)

    updated = await db.policies.find_one({"id": policy_id}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    if isinstance(updated.get('updated_at'), str):
        updated['updated_at'] = datetime.fromisoformat(updated['updated_at'])
    return updated

@api_router.delete("/policies/bulk")
async def bulk_delete_policies(policy_ids: List[str], current_user: dict = Depends(get_current_user)):
    """Delete multiple policies at once with full cascade cleanup. Feature #30."""
    # Get user details to check role and organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    # Auditors should not be able to delete (read-only)
    if user_role == 'auditor':
        raise HTTPException(status_code=403, detail="Auditors have read-only access. Cannot delete policies.")

    # Build query based on role
    if user_role == 'compliance_head':
        query = {"id": {"$in": policy_ids}, "organization": organization}
    else:
        query = {"id": {"$in": policy_ids}, "user_id": current_user['user_id']}

    # Get matching policies
    matching_policies = await db.policies.find(query, {"id": 1, "_id": 0}).to_list(None)
    matching_ids = [p["id"] for p in matching_policies]

    if not matching_ids:
        raise HTTPException(status_code=404, detail="No matching policies found")

    # Full cascade cleanup for each policy
    for pid in matching_ids:
        # Collect clause IDs from the policy before deleting
        policy_doc = await db.policies.find_one({"id": pid}, {"clauses": 1})
        clause_ids = []
        if policy_doc and policy_doc.get("clauses"):
            clause_ids = [c.get("clause_id") for c in policy_doc["clauses"] if c.get("clause_id")]
        # Also collect clause IDs from the clauses collection
        clause_docs = await db.clauses.find({"source_type": "policy", "source_id": pid}, {"id": 1}).to_list(None)
        clause_ids.extend([c["id"] for c in clause_docs if c.get("id")])
        clause_ids = list(set(clause_ids))  # deduplicate

        # Collect task IDs linked to this policy
        task_docs = await db.tasks.find({"policy_id": pid}, {"id": 1}).to_list(None)
        task_ids = [t["id"] for t in task_docs if t.get("id")]

        # 1. Delete associated clauses
        await db.clauses.delete_many({"source_type": "policy", "source_id": pid})
        # 2. Delete policy versions
        await db.policy_versions.delete_many({"policy_id": pid})
        # 3. Delete approval workflows
        await db.approval_workflows.delete_many({"policy_id": pid})
        # 4. Delete gap analyses
        await db.gap_analyses.delete_many({"policy_id": pid})
        # 5. Update tasks linked to this policy
        await db.tasks.update_many(
            {"policy_id": pid},
            {"$set": {"policy_id": None, "policy_deleted": True}}
        )
        # 6. Update tasks referencing this policy's clauses
        await db.tasks.update_many(
            {"linked_clauses.policy_id": pid},
            {"$pull": {"linked_clauses": {"policy_id": pid}}}
        )
        # 7. Update evidence linked to this policy's clauses (by clause ID)
        if clause_ids:
            await db.evidence.update_many(
                {"linked_clause_id": {"$in": clause_ids}},
                {"$set": {"linked_clause_id": None, "policy_deleted": True}}
            )
        # 7b. Update evidence linked to tasks of this policy
        if task_ids:
            await db.evidence.update_many(
                {"linked_task_id": {"$in": task_ids}},
                {"$set": {"policy_deleted": True}}
            )
        # 8. Remove from regulation links
        await db.regulations.update_many(
            {"linked_policies": pid},
            {"$pull": {"linked_policies": pid}}
        )

    # Delete all matching policies
    result = await db.policies.delete_many({"id": {"$in": matching_ids}})

    return {
        "message": f"Deleted {result.deleted_count} policies",
        "deleted_count": result.deleted_count,
        "deleted_ids": matching_ids,
        "cascaded": True
    }

@api_router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a policy and cascade cleanup."""
    # Get user details to check role and organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    # Check if user has permission to delete this policy
    # - compliance_head: can delete any policy in their organization
    # - auditor: read-only (cannot delete)
    # - user: can only delete their own policies
    if user_role == 'compliance_head':
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Auditors should not be able to delete (read-only)
    if user_role == 'auditor':
        raise HTTPException(status_code=403, detail="Auditors have read-only access. Cannot delete policies.")

    # Full cascade cleanup for policy deletion
    # Collect clause IDs from the policy before deleting
    clause_ids = []
    if policy.get("clauses"):
        clause_ids = [c.get("clause_id") for c in policy["clauses"] if c.get("clause_id")]
    # Also collect clause IDs from the clauses collection
    clause_docs = await db.clauses.find({"source_type": "policy", "source_id": policy_id}, {"id": 1}).to_list(None)
    clause_ids.extend([c["id"] for c in clause_docs if c.get("id")])
    clause_ids = list(set(clause_ids))  # deduplicate

    # Collect task IDs linked to this policy
    task_docs = await db.tasks.find({"policy_id": policy_id}, {"id": 1}).to_list(None)
    task_ids = [t["id"] for t in task_docs if t.get("id")]

    # 1. Delete associated clauses (source_type="policy")
    await db.clauses.delete_many({"source_type": "policy", "source_id": policy_id})

    # 2. Delete policy versions
    await db.policy_versions.delete_many({"policy_id": policy_id})

    # 3. Delete approval workflows
    await db.approval_workflows.delete_many({"policy_id": policy_id})

    # 4. Delete gap analyses referencing this policy
    await db.gap_analyses.delete_many({"policy_id": policy_id})

    # 5. Update tasks linked to this policy (mark as orphaned, don't delete)
    await db.tasks.update_many(
        {"policy_id": policy_id},
        {"$set": {"policy_id": None, "policy_deleted": True}}
    )

    # 6. Update tasks that reference this policy's clauses via linked_clauses
    await db.tasks.update_many(
        {"linked_clauses.policy_id": policy_id},
        {"$pull": {"linked_clauses": {"policy_id": policy_id}}}
    )

    # 7. Update evidence linked to this policy's clauses (by clause ID)
    if clause_ids:
        await db.evidence.update_many(
            {"linked_clause_id": {"$in": clause_ids}},
            {"$set": {"linked_clause_id": None, "policy_deleted": True}}
        )
    # 7b. Update evidence linked to tasks of this policy
    if task_ids:
        await db.evidence.update_many(
            {"linked_task_id": {"$in": task_ids}},
            {"$set": {"policy_deleted": True}}
        )

    # 8. Remove from regulation_links in regulations that reference this policy
    await db.regulations.update_many(
        {"linked_policies": policy_id},
        {"$pull": {"linked_policies": policy_id}}
    )

    # 9. Delete the policy itself
    await db.policies.delete_one({"id": policy_id})

    return {"message": "Policy deleted successfully", "id": policy_id, "cascaded": True}

@api_router.post("/policies/{policy_id}/clauses")
async def add_clause_to_policy(policy_id: str, clause_data: dict, current_user: dict = Depends(get_current_user)):
    """Add a new clause to a policy."""
    # Role-based access: compliance_head can modify any policy in their org
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user') if user_doc else 'user'
    organization = user_doc.get('organization') if user_doc else None
    if user_role in ['compliance_head', 'auditor']:
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Feature #23: Save version snapshot BEFORE adding clause
    now = datetime.now(timezone.utc).isoformat()
    existing_versions = await db.policy_versions.count_documents({"policy_id": policy_id})
    version_number = existing_versions + 1
    version_snapshot = {
        "id": str(uuid.uuid4()),
        "policy_id": policy_id,
        "version_number": version_number,
        "clauses": policy.get("clauses", []),
        "metadata_snapshot": {
            "title": policy.get("title"),
            "policy_type": policy.get("policy_type"),
            "status": policy.get("status"),
            "department": policy.get("department"),
            "owner": policy.get("owner"),
            "version": policy.get("version"),
        },
        "changes_summary": f"Added clause: {clause_data.get('text', '')[:80]}...",
        "changed_fields": [],
        "created_by": current_user['user_id'],
        "created_at": now,
        "change_type": "clause_added"
    }
    await db.policy_versions.insert_one(version_snapshot)

    new_clause = Clause(
        clause_id=clause_data.get('clause_id', str(uuid.uuid4())),
        text=clause_data.get('text', ''),
        original_text=clause_data.get('text', ''),
        section=clause_data.get('section'),
        page_number=clause_data.get('page_number'),
        title=clause_data.get('title'),
        content=clause_data.get('content'),
        tags=clause_data.get('tags', []),
        requirement_type=clause_data.get('requirement_type', 'informational'),
        subject_category=clause_data.get('subject_category', 'general'),
        key_obligations=clause_data.get('key_obligations', []),
        keywords=clause_data.get('keywords', []),
        criticality=clause_data.get('criticality', 'medium')
    )

    clause_dict = new_clause.model_dump()
    await db.policies.update_one(
        {"id": policy_id},
        {
            "$push": {
                "clauses": clause_dict,
                "audit_trail": {
                    "action": "Added clause",
                    "field": "clauses",
                    "old_value": None,
                    "new_value": clause_data.get('text', '')[:100],
                    "user": current_user['user_id'],
                    "timestamp": now
                }
            },
            "$set": {"updated_at": now}
        }
    )

    return {"message": "Clause added", "clause": clause_dict}

@api_router.put("/policies/{policy_id}/clauses/{clause_id}")
async def update_clause(policy_id: str, clause_id: str, clause_data: dict, current_user: dict = Depends(get_current_user)):
    """Update an existing clause (human-in-the-loop editing)."""
    # Role-based access: compliance_head can modify any policy in their org
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user') if user_doc else 'user'
    organization = user_doc.get('organization') if user_doc else None
    if user_role in ['compliance_head', 'auditor']:
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Feature #23: Save version snapshot BEFORE editing clause
    now = datetime.now(timezone.utc).isoformat()
    existing_versions = await db.policy_versions.count_documents({"policy_id": policy_id})
    version_number = existing_versions + 1
    version_snapshot = {
        "id": str(uuid.uuid4()),
        "policy_id": policy_id,
        "version_number": version_number,
        "clauses": policy.get("clauses", []),
        "metadata_snapshot": {
            "title": policy.get("title"),
            "policy_type": policy.get("policy_type"),
            "status": policy.get("status"),
            "department": policy.get("department"),
            "owner": policy.get("owner"),
            "version": policy.get("version"),
        },
        "changes_summary": f"Edited clause {clause_id}",
        "changed_fields": [],
        "created_by": current_user['user_id'],
        "created_at": now,
        "change_type": "clause_edited"
    }
    await db.policy_versions.insert_one(version_snapshot)

    clauses = policy.get('clauses', [])
    clause_found = False
    original_text = None
    for i, c in enumerate(clauses):
        if c.get('clause_id') == clause_id:
            original_text = c.get('text', '')
            # Update allowed fields
            for key in ['text', 'title', 'section', 'page_number', 'requirement_type', 'subject_category', 'criticality', 'content', 'tags', 'key_obligations', 'keywords']:
                if key in clause_data:
                    clauses[i][key] = clause_data[key]
            clause_found = True
            break

    if not clause_found:
        raise HTTPException(status_code=404, detail="Clause not found")

    # Log the edit in audit trail
    audit_entry = {
        "id": str(uuid.uuid4()),
        "policy_id": policy_id,
        "clause_id": clause_id,
        "action": "clause_edited",
        "original_value": original_text,
        "new_value": clause_data.get('text', original_text),
        "user_id": current_user['user_id'],
        "timestamp": now
    }
    await db.audit_trail.insert_one(audit_entry)

    await db.policies.update_one(
        {"id": policy_id},
        {
            "$set": {"clauses": clauses, "updated_at": now},
            "$push": {"audit_trail": {
                "action": "Edited clause",
                "field": "clauses",
                "old_value": (original_text or "")[:100],
                "new_value": clause_data.get('text', '')[:100],
                "user": current_user['user_id'],
                "timestamp": now
            }}
        }
    )

    return {"message": "Clause updated", "audit_id": audit_entry["id"]}

@api_router.delete("/policies/{policy_id}/clauses/{clause_id}")
async def delete_clause(policy_id: str, clause_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a clause from a policy."""
    # Role-based access: compliance_head can modify any policy in their org
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user') if user_doc else 'user'
    organization = user_doc.get('organization') if user_doc else None
    if user_role in ['compliance_head', 'auditor']:
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Feature #23: Save version snapshot BEFORE deleting clause
    now = datetime.now(timezone.utc).isoformat()
    existing_versions = await db.policy_versions.count_documents({"policy_id": policy_id})
    version_number = existing_versions + 1
    deleted_clause_text = ""
    for c in policy.get("clauses", []):
        if c.get("clause_id") == clause_id:
            deleted_clause_text = c.get("text", "")[:80]
            break
    version_snapshot = {
        "id": str(uuid.uuid4()),
        "policy_id": policy_id,
        "version_number": version_number,
        "clauses": policy.get("clauses", []),
        "metadata_snapshot": {
            "title": policy.get("title"),
            "policy_type": policy.get("policy_type"),
            "status": policy.get("status"),
            "department": policy.get("department"),
            "owner": policy.get("owner"),
            "version": policy.get("version"),
        },
        "changes_summary": f"Deleted clause: {deleted_clause_text}...",
        "changed_fields": [],
        "created_by": current_user['user_id'],
        "created_at": now,
        "change_type": "clause_deleted"
    }
    await db.policy_versions.insert_one(version_snapshot)

    clauses = policy.get('clauses', [])
    new_clauses = [c for c in clauses if c.get('clause_id') != clause_id]

    if len(new_clauses) == len(clauses):
        raise HTTPException(status_code=404, detail="Clause not found")

    await db.policies.update_one(
        {"id": policy_id},
        {
            "$set": {"clauses": new_clauses, "updated_at": now},
            "$push": {"audit_trail": {
                "action": "Deleted clause",
                "field": "clauses",
                "old_value": deleted_clause_text,
                "new_value": None,
                "user": current_user['user_id'],
                "timestamp": now
            }}
        }
    )

    return {"message": "Clause deleted", "clause_id": clause_id}

@api_router.post("/policies/{policy_id}/link-regulation")
async def link_regulation(policy_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    """Link a regulation to a policy (manual or AI-suggested)."""
    regulation_id = body.get("regulation_id")
    if not regulation_id:
        raise HTTPException(status_code=400, detail="regulation_id is required")

    # Role-based access
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user') if user_doc else 'user'
    organization = user_doc.get('organization') if user_doc else None
    if user_role in ['compliance_head', 'auditor']:
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Verify regulation exists
    regulation = await db.regulations.find_one({"id": regulation_id}, {"_id": 0})
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found")

    linked = policy.get("linked_regulations", [])
    if regulation_id in linked:
        return {"message": "Regulation already linked", "linked_regulations": linked}

    linked.append(regulation_id)
    now = datetime.now(timezone.utc).isoformat()
    await db.policies.update_one(
        {"id": policy_id},
        {
            "$set": {"linked_regulations": linked, "updated_at": now},
            "$push": {"audit_trail": {
                "action": "Linked regulation",
                "field": "linked_regulations",
                "old_value": None,
                "new_value": regulation.get("title", regulation_id),
                "user": current_user['user_id'],
                "timestamp": now
            }}
        }
    )
    return {"message": "Regulation linked", "linked_regulations": linked}

@api_router.delete("/policies/{policy_id}/link-regulation/{regulation_id}")
async def unlink_regulation(policy_id: str, regulation_id: str, current_user: dict = Depends(get_current_user)):
    """Unlink a regulation from a policy."""
    # Role-based access
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user') if user_doc else 'user'
    organization = user_doc.get('organization') if user_doc else None
    if user_role in ['compliance_head', 'auditor']:
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    linked = policy.get("linked_regulations", [])
    if regulation_id not in linked:
        raise HTTPException(status_code=404, detail="Regulation not linked")

    linked.remove(regulation_id)
    now = datetime.now(timezone.utc).isoformat()
    await db.policies.update_one(
        {"id": policy_id},
        {
            "$set": {"linked_regulations": linked, "updated_at": now},
            "$push": {"audit_trail": {
                "action": "Unlinked regulation",
                "field": "linked_regulations",
                "old_value": regulation_id,
                "new_value": None,
                "user": current_user['user_id'],
                "timestamp": now
            }}
        }
    )
    return {"message": "Regulation unlinked", "linked_regulations": linked}

@api_router.post("/policies/{policy_id}/submit-review")
async def submit_policy_for_review(policy_id: str, current_user: dict = Depends(get_current_user)):
    """Submit a draft policy for review."""
    policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    now = datetime.now(timezone.utc).isoformat()

    # Record in approval_history on the policy itself
    history_entry = {
        "action": "submitted_for_review",
        "decision": "submit",
        "user": current_user.get('email', current_user['user_id']),
        "user_id": current_user['user_id'],
        "timestamp": now
    }

    await db.policies.update_one(
        {"id": policy_id},
        {
            "$set": {"status": "review", "updated_at": now},
            "$push": {"approval_history": history_entry}
        }
    )

    # Create approval workflow
    workflow = {
        "id": str(uuid.uuid4()),
        "policy_id": policy_id,
        "status": "pending",
        "submitted_by": current_user['user_id'],
        "submitted_at": now,
        "reviewers": [],
        "decisions": []
    }
    await db.approval_workflows.insert_one(workflow)

    return {"message": "Policy submitted for review", "workflow_id": workflow["id"]}

@api_router.post("/policies/{policy_id}/approve")
async def approve_policy(policy_id: str, decision: dict, current_user: dict = Depends(get_current_user)):
    """Approve or reject a policy."""
    # Support both frontend formats: {decision: 'approve'/'reject', reason: '...'} and {approved: true/false, notes: '...'}
    if 'decision' in decision:
        approved = decision['decision'] == 'approve'
        notes = decision.get('reason', '') or decision.get('notes', '')
    else:
        approved = decision.get('approved', True)
        notes = decision.get('notes', '') or decision.get('reason', '')

    now = datetime.now(timezone.utc).isoformat()
    new_status = "approved" if approved else "draft"

    # Record in approval_history on the policy itself
    history_entry = {
        "action": "approve" if approved else "reject",
        "decision": "approve" if approved else "reject",
        "user": current_user.get('email', current_user['user_id']),
        "user_id": current_user['user_id'],
        "reason": notes,
        "timestamp": now
    }

    await db.policies.update_one(
        {"id": policy_id},
        {
            "$set": {"status": new_status, "updated_at": now},
            "$push": {"approval_history": history_entry}
        }
    )

    # Record decision in approval_workflows collection
    await db.approval_workflows.update_one(
        {"policy_id": policy_id, "status": "pending"},
        {"$set": {"status": "approved" if approved else "rejected"},
         "$push": {"decisions": {
             "user_id": current_user['user_id'],
             "approved": approved,
             "notes": notes,
             "timestamp": now
         }}}
    )

    return {"message": f"Policy {'approved' if approved else 'rejected'}", "status": new_status}

# Bulk delete moved before /policies/{policy_id} to avoid route conflict


# ========== POLICY VERSION ENDPOINTS (Features #23, #24) ==========

@api_router.get("/policies/{policy_id}/versions")
async def get_policy_versions(policy_id: str, current_user: dict = Depends(get_current_user)):
    """Feature #23: Get version history for a policy."""
    # Verify policy exists and user has access
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    if user_role in ('compliance_head', 'auditor'):
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Get all versions from policy_versions collection
    versions_cursor = db.policy_versions.find(
        {"policy_id": policy_id},
        {"_id": 0}
    ).sort("version_number", 1)
    versions = await versions_cursor.to_list(500)

    # Also include the "current" version as the latest entry
    current_version = {
        "id": "current",
        "policy_id": policy_id,
        "version_number": len(versions) + 1,
        "clauses_count": len(policy.get("clauses", [])),
        "metadata_snapshot": {
            "title": policy.get("title"),
            "policy_type": policy.get("policy_type"),
            "status": policy.get("status"),
            "department": policy.get("department"),
            "owner": policy.get("owner"),
            "version": policy.get("version"),
        },
        "changes_summary": "Current version",
        "created_by": policy.get("user_id"),
        "created_at": policy.get("updated_at") or policy.get("created_at"),
        "change_type": "current",
        "is_current": True
    }

    # Format version entries for response
    formatted_versions = []
    for v in versions:
        formatted_versions.append({
            "id": v.get("id"),
            "version_number": v.get("version_number"),
            "clauses_count": len(v.get("clauses", [])),
            "changes_summary": v.get("changes_summary", ""),
            "change_type": v.get("change_type", "update"),
            "created_by": v.get("created_by"),
            "created_at": v.get("created_at"),
        })

    formatted_versions.append(current_version)

    return {
        "policy_id": policy_id,
        "versions": formatted_versions,
        "total_versions": len(formatted_versions)
    }


@api_router.get("/policies/{policy_id}/versions/{version_id}/diff")
async def compare_policy_versions(
    policy_id: str,
    version_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Feature #24: Compare two versions of a policy and return diff.
    Compares the specified version against the current policy state."""
    # Verify policy exists and user has access
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    if user_role in ('compliance_head', 'auditor'):
        policy = await db.policies.find_one({"id": policy_id, "organization": organization}, {"_id": 0})
    else:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Fetch the version to compare
    version_doc = await db.policy_versions.find_one({"id": version_id, "policy_id": policy_id}, {"_id": 0})
    if not version_doc:
        raise HTTPException(status_code=404, detail="Version not found")

    # Current clauses vs version clauses
    current_clauses = policy.get("clauses", [])
    version_clauses = version_doc.get("clauses", [])

    # Build clause maps for comparison
    current_clause_map = {c.get("clause_id", str(i)): c for i, c in enumerate(current_clauses)}
    version_clause_map = {c.get("clause_id", str(i)): c for i, c in enumerate(version_clauses)}

    additions = []
    deletions = []
    modifications = []
    unchanged = []

    # Find additions (in current but not in version)
    for clause_id, clause in current_clause_map.items():
        if clause_id not in version_clause_map:
            additions.append({
                "clause_id": clause_id,
                "section": clause.get("section", ""),
                "text": clause.get("text", ""),
                "type": "addition"
            })

    # Find deletions (in version but not in current)
    for clause_id, clause in version_clause_map.items():
        if clause_id not in current_clause_map:
            deletions.append({
                "clause_id": clause_id,
                "section": clause.get("section", ""),
                "text": clause.get("text", ""),
                "type": "deletion"
            })

    # Find modifications (in both but text changed)
    for clause_id in current_clause_map:
        if clause_id in version_clause_map:
            current_text = current_clause_map[clause_id].get("text", "").strip()
            version_text = version_clause_map[clause_id].get("text", "").strip()
            if current_text != version_text:
                modifications.append({
                    "clause_id": clause_id,
                    "section": current_clause_map[clause_id].get("section", ""),
                    "old_text": version_text,
                    "new_text": current_text,
                    "type": "modification"
                })
            else:
                unchanged.append({
                    "clause_id": clause_id,
                    "section": current_clause_map[clause_id].get("section", ""),
                    "text": current_text,
                    "type": "unchanged"
                })

    # Metadata diff
    version_meta = version_doc.get("metadata_snapshot", {})
    current_meta = {
        "title": policy.get("title"),
        "policy_type": policy.get("policy_type"),
        "status": policy.get("status"),
        "department": policy.get("department"),
        "owner": policy.get("owner"),
        "version": policy.get("version"),
    }
    metadata_changes = []
    for key in current_meta:
        old_val = version_meta.get(key)
        new_val = current_meta.get(key)
        if str(old_val) != str(new_val):
            metadata_changes.append({
                "field": key,
                "old_value": old_val,
                "new_value": new_val
            })

    # Generate a summary
    changes_description = []
    if additions:
        changes_description.append(f"{len(additions)} clause(s) added")
    if deletions:
        changes_description.append(f"{len(deletions)} clause(s) removed")
    if modifications:
        changes_description.append(f"{len(modifications)} clause(s) modified")
    if metadata_changes:
        changes_description.append(f"{len(metadata_changes)} metadata field(s) changed")

    summary = ", ".join(changes_description) if changes_description else "No changes detected"

    return {
        "policy_id": policy_id,
        "version_id": version_id,
        "version_number": version_doc.get("version_number"),
        "version_date": version_doc.get("created_at"),
        "additions": additions,
        "deletions": deletions,
        "modifications": modifications,
        "unchanged": unchanged,
        "metadata_changes": metadata_changes,
        "changes_summary": summary,
        "stats": {
            "additions_count": len(additions),
            "deletions_count": len(deletions),
            "modifications_count": len(modifications),
            "unchanged_count": len(unchanged),
            "total_current_clauses": len(current_clauses),
            "total_version_clauses": len(version_clauses)
        }
    }


# ========== REGULATION ENDPOINTS ==========
@api_router.get("/regulations", response_model=List[Regulation])
async def get_regulations(
    regulator: Optional[str] = None,
    include_npci: Optional[bool] = Query(False, description="Include NPCI circulars as regulations"),
    current_user: dict = Depends(get_current_user)
):
    # Include both user's own regulations and system-wide shared regulations
    query = {"$or": [
        {"user_id": current_user['user_id']},
        {"user_id": "system"}  # Shared regulations from RBI scraper and NPCI auto-conversion
    ]}
    if regulator:
        query["regulatory_body"] = regulator

    regulations = await db.regulations.find(query, {"_id": 0}).to_list(1000)
    for reg in regulations:
        if isinstance(reg.get('created_at'), str):
            reg['created_at'] = datetime.fromisoformat(reg['created_at'])
        for date_field in ['issued_date', 'effective_date', 'due_date']:
            if reg.get(date_field) and isinstance(reg[date_field], str):
                reg[date_field] = datetime.fromisoformat(reg[date_field])

    # Legacy fallback: include NPCI circulars on-the-fly only if no regulation records exist for NPCI
    # (for circulars processed before the auto-conversion feature was added)
    if include_npci or regulator == "NPCI":
        existing_npci_ids = set()
        for reg in regulations:
            if reg.get("regulatory_body") == "NPCI" and reg.get("source_circular_id"):
                existing_npci_ids.add(reg["source_circular_id"])

        try:
            npci_query = {"processed_at": {"$ne": None}}
            npci_circulars = await db.npci_circulars.find(npci_query, {"_id": 0}).to_list(500)
            for circ in npci_circulars:
                circ_npci_id = str(circ.get("npci_id", ""))
                # Skip if already converted to a regulation record
                if circ_npci_id in existing_npci_ids:
                    continue
                npci_reg = _npci_circular_to_regulation(circ)
                regulations.append(npci_reg)
        except Exception as e:
            logger.warning(f"Failed to include NPCI circulars in regulations list: {e}")

    return regulations


def _npci_circular_to_regulation(circ: dict) -> dict:
    """Feature #219: Convert an NPCI circular document to a regulation-compatible dict."""
    from services.npci_scraper_service import NPCI_PRODUCT_LABELS
    circular_id = f"npci_{circ.get('npci_id', circ.get('_id', ''))}"
    product = circ.get('product', '')
    product_label = NPCI_PRODUCT_LABELS.get(product, product)

    # Convert NPCI clauses to regulation clause format
    reg_clauses = []
    for idx, clause in enumerate(circ.get("clauses", [])):
        reg_clauses.append({
            "clause_id": clause.get("clause_id", f"NPCI-C{idx+1}"),
            "title": clause.get("title", clause.get("clause_id", f"Clause {idx+1}")),
            "text": clause.get("text", clause.get("clause_text", "")),
            "original_text": clause.get("text", clause.get("clause_text", "")),
            "section": f"NPCI {product_label}",
            "keywords": [],
            "tags": [product, "npci"],
            "subject_category": clause.get("category", "general").lower().replace(" ", "_"),
            "requirement_type": "mandatory",
            "criticality": clause.get("compliance_impact", "medium"),
            "compliance_indicators": clause.get("key_requirements", []),
            "key_obligations": clause.get("key_requirements", []),
            "semantic_summary": clause.get("text", clause.get("clause_text", ""))[:200],
        })

    return {
        "id": circular_id,
        "title": f"[NPCI {product_label}] {circ.get('title', 'Unknown')}",
        "regulatory_body": "NPCI",
        "circular_number": str(circ.get("npci_id", "")),
        "issued_date": circ.get("scraped_at", datetime.now(timezone.utc).isoformat()),
        "effective_date": circ.get("scraped_at", datetime.now(timezone.utc).isoformat()),
        "file_url": circ.get("pdf_url", ""),
        "clauses": reg_clauses,
        "user_id": "system",
        "organization": "NPCI",
        "is_master_circular": False,
        "chapters": [],
        "version": "1.0",
        "source": "npci_scraper",
        "npci_product": product,
        "npci_product_label": product_label,
        "created_at": circ.get("scraped_at", datetime.now(timezone.utc).isoformat()),
    }


# Feature #176: Crawl status - MUST be before /regulations/{regulation_id} to avoid route conflict
@api_router.get("/regulations/crawl-status")
async def get_crawl_status_early(
    current_user: dict = Depends(get_current_user)
):
    """Feature #176: Get latest crawl status (early route to avoid path param conflict)."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')

    latest_crawl = await db.regulation_crawls.find_one(
        {"organization": org},
        {"_id": 0},
        sort=[("started_at", -1)]
    )

    if not latest_crawl:
        return {"status": "no_crawls", "message": "No crawls have been run yet"}

    return latest_crawl


@api_router.get("/regulations/{regulation_id}", response_model=Regulation)
async def get_regulation(regulation_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single regulation by ID with all its clauses and semantic attributes"""
    # Get user details to check role and organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    # Role-based access:
    # - compliance_head and auditor: can view any regulation in their organization + system regulations
    # - user: can view their own regulations + system regulations
    if user_role in ['compliance_head', 'auditor']:
        regulation = await db.regulations.find_one({
            "id": regulation_id,
            "$or": [
                {"organization": organization},
                {"user_id": "system"}
            ]
        }, {"_id": 0})
    else:
        regulation = await db.regulations.find_one({
            "id": regulation_id,
            "$or": [
                {"user_id": current_user['user_id']},
                {"user_id": "system"}
            ]
        }, {"_id": 0})

    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found")

    if isinstance(regulation.get('created_at'), str):
        regulation['created_at'] = datetime.fromisoformat(regulation['created_at'])
    for date_field in ['issued_date', 'effective_date', 'due_date']:
        if regulation.get(date_field) and isinstance(regulation[date_field], str):
            regulation[date_field] = datetime.fromisoformat(regulation[date_field])

    return regulation


@api_router.get("/regulations/{regulation_id}/versions")
async def get_regulation_versions(
    regulation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #34 & #35: Get all versions of a regulation.
    Returns version history for a specific regulation.
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization')

    # Find all versions of this regulation (by following previous_version_id chain)
    versions = []
    current_reg_id = regulation_id

    # Start with the current/latest version
    current_reg = await db.regulations.find_one(
        {"id": current_reg_id},
        {"_id": 0}
    )

    if not current_reg:
        raise HTTPException(status_code=404, detail="Regulation not found")

    # Build version history by traversing backward through previous_version_id
    while current_reg:
        versions.append({
            "id": current_reg.get("id"),
            "version": current_reg.get("version", "1.0"),
            "title": current_reg.get("title"),
            "created_at": current_reg.get("created_at"),
            "clauses_count": len(current_reg.get("clauses", [])),
            "previous_version_id": current_reg.get("previous_version_id")
        })

        # Get previous version if it exists
        prev_id = current_reg.get("previous_version_id")
        if prev_id:
            current_reg = await db.regulations.find_one({"id": prev_id}, {"_id": 0})
        else:
            break

    return {
        "regulation_id": regulation_id,
        "versions": versions,
        "total_versions": len(versions)
    }


@api_router.get("/regulations/{regulation_id}/diff/{compare_version_id}")
async def compare_regulation_versions(
    regulation_id: str,
    compare_version_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #35: Compare two versions of a regulation and return diff.
    Returns additions, deletions, modifications, and AI-generated summary.
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization')

    # Fetch both versions
    current_version = await db.regulations.find_one({"id": regulation_id}, {"_id": 0})
    compare_version = await db.regulations.find_one({"id": compare_version_id}, {"_id": 0})

    if not current_version or not compare_version:
        raise HTTPException(status_code=404, detail="One or both regulation versions not found")

    # Extract clauses from both versions
    current_clauses = current_version.get("clauses", [])
    compare_clauses = compare_version.get("clauses", [])

    # Build clause maps for comparison
    current_clause_map = {c.get("clause_id", c.get("clause_number", str(i))): c for i, c in enumerate(current_clauses)}
    compare_clause_map = {c.get("clause_id", c.get("clause_number", str(i))): c for i, c in enumerate(compare_clauses)}

    # Identify additions, deletions, and modifications
    additions = []
    deletions = []
    modifications = []

    # Find additions (in current but not in compare)
    for clause_id, clause in current_clause_map.items():
        if clause_id not in compare_clause_map:
            additions.append({
                "clause_id": clause_id,
                "clause_number": clause.get("clause_number", ""),
                "text": clause.get("text", ""),
                "type": "addition"
            })

    # Find deletions (in compare but not in current)
    for clause_id, clause in compare_clause_map.items():
        if clause_id not in current_clause_map:
            deletions.append({
                "clause_id": clause_id,
                "clause_number": clause.get("clause_number", ""),
                "text": clause.get("text", ""),
                "type": "deletion"
            })

    # Find modifications (in both but text changed)
    for clause_id in current_clause_map:
        if clause_id in compare_clause_map:
            current_text = current_clause_map[clause_id].get("text", "").strip()
            compare_text = compare_clause_map[clause_id].get("text", "").strip()
            if current_text != compare_text:
                modifications.append({
                    "clause_id": clause_id,
                    "clause_number": current_clause_map[clause_id].get("clause_number", ""),
                    "old_text": compare_text,
                    "new_text": current_text,
                    "type": "modification"
                })

    # Generate AI summary of changes
    try:
        llm_service = MultiLLMService()
        changes_description = []
        if additions:
            changes_description.append(f"{len(additions)} clause(s) added")
        if deletions:
            changes_description.append(f"{len(deletions)} clause(s) removed")
        if modifications:
            changes_description.append(f"{len(modifications)} clause(s) modified")

        if not changes_description:
            changes_summary = "No significant changes detected between versions."
        else:
            # Create summary prompt
            summary_prompt = f"""Analyze the following changes between two regulation versions:

**Changes:**
- {', '.join(changes_description)}

**Sample Modifications:**
{chr(10).join([f"- Clause {m['clause_number']}: Text changed" for m in modifications[:3]])}

**Sample Additions:**
{chr(10).join([f"- Clause {a['clause_number']}: {a['text'][:100]}..." for a in additions[:3]])}

**Sample Deletions:**
{chr(10).join([f"- Clause {d['clause_number']}: {d['text'][:100]}..." for d in deletions[:3]])}

Provide a concise 2-3 sentence summary of the regulatory changes and their potential impact on compliance."""

            changes_summary = llm_service.generate_text(summary_prompt)
    except Exception as e:
        logging.error(f"Failed to generate AI summary: {e}")
        changes_summary = f"Changes detected: {', '.join(changes_description) if changes_description else 'None'}"

    return {
        "current_version": {
            "id": current_version.get("id"),
            "version": current_version.get("version", "1.0"),
            "title": current_version.get("title"),
            "created_at": current_version.get("created_at")
        },
        "compare_version": {
            "id": compare_version.get("id"),
            "version": compare_version.get("version", "1.0"),
            "title": compare_version.get("title"),
            "created_at": compare_version.get("created_at")
        },
        "diff": {
            "additions": additions,
            "deletions": deletions,
            "modifications": modifications,
            "total_changes": len(additions) + len(deletions) + len(modifications)
        },
        "changes_summary": changes_summary
    }


async def process_regulation_upload_background(
    job_id: str,
    file_content: bytes,
    file_name: str,
    reg_info: dict,
    user_id: str,
    organization: str
):
    """Background task for processing regulation upload with progress updates."""
    import uuid as uuid_module
    import asyncio
    
    try:
        # Step 1: Uploading (10%)
        await upload_job_service.update_progress(
            job_id, 10, "Saving file...", 1, status="uploading"
        )
        
        file_path = await doc_service.save_file(file_content, file_name)

        # Step 2: Text Extraction (25%)
        file_extension = os.path.splitext(file_name)[1].lower()
        file_type = "PDF" if file_extension == ".pdf" else "DOCX" if file_extension in [".docx", ".doc"] else "TXT"

        await upload_job_service.update_progress(
            job_id, 20, f"Extracting text from {file_type}...", 2, status="processing"
        )

        text = await doc_service.extract_text(file_path)
        
        await upload_job_service.update_progress(
            job_id, 25, f"Extracted {len(text)} characters", 2
        )
        
        document_title = reg_info.get('title', file_name)
        
        # Step 3: LLM Analysis (40%)
        await upload_job_service.update_progress(
            job_id, 30, "AI analyzing regulatory impact...", 3, status="analyzing"
        )
        
        analysis = await llm_service.analyze_regulatory_circular_claude(text, document_title)
        
        await upload_job_service.update_progress(
            job_id, 40, "Impact analysis complete", 3
        )
        
        # Step 4: Clause Extraction (70%)
        await upload_job_service.update_progress(
            job_id, 45, "AI extracting regulatory clauses...", 4, status="extracting"
        )
        
        document_id = str(uuid_module.uuid4())
        try:
            clauses_data = await asyncio.wait_for(
                clause_extractor.extract_clauses_from_document(
                    text=text,
                    document_type="regulation",
                    document_id=document_id,
                    document_title=document_title
                ),
                timeout=300  # 5 minute timeout for LLM extraction
            )
        except asyncio.TimeoutError:
            logger.warning(f"[REG UPLOAD] LLM extraction timed out for job {job_id}, using fallback")
            clauses_data = clause_extractor._fallback_clause_extraction_with_enrichment(
                clause_extractor._split_into_chunks(text),
                "regulation", document_id
            )
        
        await upload_job_service.update_progress(
            job_id, 70, f"Extracted {len(clauses_data)} clauses", 4,
            clauses_extracted=len(clauses_data)
        )
        
        # Step 5: Processing Clauses (85%)
        await upload_job_service.update_progress(
            job_id, 75, "Processing extracted clauses...", 5
        )
        
        clauses = []
        for clause_data in clauses_data:
            clause = Clause(
                clause_id=clause_data.get('clause_id', str(uuid_module.uuid4())),
                text=clause_data.get('original_text', ''),
                original_text=clause_data.get('original_text', ''),
                section=clause_data.get('section'),
                page_number=clause_data.get('page_number'),
                title=clause_data.get('title'),
                content=clause_data.get('content'),
                tags=clause_data.get('tags', []),
                requirement_type=clause_data.get('requirement_type', 'mandatory'),
                subject_category=clause_data.get('subject_category', 'general'),
                key_obligations=clause_data.get('key_obligations', []),
                semantic_summary=clause_data.get('semantic_summary'),
                entities_involved=clause_data.get('entities_involved', []),
                keywords=clause_data.get('keywords', []),
                compliance_indicators=clause_data.get('compliance_indicators', []),
                criticality=clause_data.get('criticality', 'high')
            )
            clauses.append(clause)
        
        await upload_job_service.update_progress(
            job_id, 85, "Saving to database...", 6
        )
        
        # Step 6: Save to Database (100%)
        # Ensure impact fields are strings (LLM may return dicts)
        def _ensure_str(val):
            if val is None:
                return None
            if isinstance(val, dict):
                import json as json_mod
                return json_mod.dumps(val)
            return str(val)

        regulation = Regulation(
            title=reg_info.get('title', file_name),
            regulatory_body=reg_info.get('regulatory_body', 'RBI'),
            circular_number=reg_info.get('circular_number'),
            file_url=file_path,
            file_name=file_name,
            clauses=clauses,
            summary=_ensure_str(analysis.get('summary')),
            impact_organization=_ensure_str(analysis.get('org_impact')),
            impact_technical=_ensure_str(analysis.get('technical_impact')),
            impact_operational=_ensure_str(analysis.get('operational_impact')),
            user_id=user_id,
            organization=organization,
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
                    user_id=user_id,
                    organization=organization,
                    auto_assigned=True
                )
                task_dict = task.model_dump()
                task_dict['created_at'] = task_dict['created_at'].isoformat()
                task_dict['updated_at'] = task_dict['updated_at'].isoformat()
                if task_dict.get('due_date'):
                    task_dict['due_date'] = task_dict['due_date'].isoformat()
                await db.tasks.insert_one(task_dict)

        # Store regulation clause embeddings in Qdrant
        if vector_service:
            # Convert clauses to dict format for vector service
            clauses_for_vector = []
            for clause in clauses:
                clauses_for_vector.append({
                    'clause_id': clause.clause_id,
                    'text': clause.text,
                    'original_text': clause.original_text,
                    'section': clause.section,
                    'page_number': clause.page_number,
                    'title': clause.title,
                    'requirement_type': clause.requirement_type,
                    'subject_category': clause.subject_category,
                    'criticality': clause.criticality,
                    'tags': clause.tags,
                    'keywords': clause.keywords
                })

            # Store in regulation_clauses collection with proper regulation_id
            stored_count = await vector_service.store_regulation_clauses(
                regulation_id=regulation.id,
                clauses=clauses_for_vector,
                organization=organization,
                user_id=user_id
            )
            logger.info(f"[REGULATION UPLOAD] Stored {stored_count} clause embeddings in Qdrant regulation_clauses collection")

            # Also store in policy_clauses collection for backward compatibility with gap analysis
            stored_count_policy = await vector_service.store_policy_clauses(
                policy_id=f"regulation_{regulation.id}",
                clauses=clauses_for_vector,
                organization=organization,
                user_id=user_id
            )
            logger.info(f"[REGULATION UPLOAD] Also stored {stored_count_policy} embeddings in policy_clauses for gap analysis compatibility")

        # Mark as completed
        await upload_job_service.complete_job(
            job_id=job_id,
            result_id=regulation.id,
            result_title=regulation.title,
            clauses_extracted=len(clauses)
        )

        logger.info(f"[REGULATION UPLOAD] Completed job {job_id}: {len(clauses)} clauses extracted")
        
    except Exception as e:
        logger.error(f"[REGULATION UPLOAD] Failed job {job_id}: {str(e)}", exc_info=True)
        await upload_job_service.fail_job(job_id, str(e), str(e.__class__.__name__))


@api_router.post("/regulations/parse-filename")
async def parse_regulation_filename(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Parse a regulation filename to extract title, regulatory body, and circular number."""
    import re
    
    body = await request.json()
    filename = body.get("filename", "")
    
    # Remove file extension
    name = re.sub(r'\.(pdf|docx?|txt)$', '', filename, flags=re.IGNORECASE).strip()
    
    # Known regulatory bodies and their variations
    regulator_patterns = {
        'RBI': [r'\bRBI\b', r'\bReserve\s+Bank\b', r'\bReserve\s+Bank\s+of\s+India\b'],
        'SEBI': [r'\bSEBI\b', r'\bSecurities\s+and\s+Exchange\s+Board\b'],
        'NSE': [r'\bNSE\b', r'\bNational\s+Stock\s+Exchange\b'],
        'BSE': [r'\bBSE\b', r'\bBombay\s+Stock\s+Exchange\b'],
        'IRDAI': [r'\bIRDAI\b', r'\bIRDA\b', r'\bInsurance\s+Regulatory\b'],
        'FIU_IND': [r'\bFIU[\-_\s]?IND\b', r'\bFinancial\s+Intelligence\s+Unit\b'],
        'NPCI': [r'\bNPCI\b', r'\bNational\s+Payments\s+Corporation\b'],
        'FINRA': [r'\bFINRA\b'],
        'SEC': [r'\bSEC\b', r'\bSecurities\s+and\s+Exchange\s+Commission\b'],
        'FCA': [r'\bFCA\b', r'\bFinancial\s+Conduct\s+Authority\b'],
        'MAS': [r'\bMAS\b', r'\bMonetary\s+Authority\s+of\s+Singapore\b'],
    }
    
    # Detect regulatory body from filename
    detected_body = None
    for body_name, patterns in regulator_patterns.items():
        for pattern in patterns:
            if re.search(pattern, name, re.IGNORECASE):
                detected_body = body_name
                break
        if detected_body:
            break
    
    # Detect circular number patterns
    # Matches patterns like: RBI/2025-26/01, SEBI/HO/2024/001, CIR/2024/123, 
    # DNBR.PD.No.123, FEMA.1R/2024-RB, No.RBI/2024-25/100, SEBI/LAD-NRO/GN/2024/100
    circular_patterns = [
        r'(?:(?:RBI|SEBI|NSE|BSE|IRDAI|NPCI|FIU)[\s/._-]*(?:[A-Z/.]+[\s/._-]*)*\d{4}(?:[/-]\d{2,4})?(?:[/._-]\d+)+)',
        r'(?:(?:CIR|CIRC|Circular)[\s/._-]*(?:No\.?\s*)?[\w/._-]*\d+)',
        r'(?:(?:DNBR|FEMA|DBOD|DOR|DoR|DoS|DPSS|FIDD|RPCD)[\s./_-]*[\w./_-]*\d+[\w./_-]*)',
        r'(?:No\.?\s*(?:RBI|SEBI|NSE|BSE|IRDAI|NPCI|FIU)[\s/._-]*[\w/._-]+)',
        r'(?:[A-Z]{2,6}[/._-]\d{4}[/._-]\d+(?:[/._-]\w+)*)',
        r'(?:[A-Z]{2,}[/._-][A-Z]+[/._-]\d{4}[/._-]\d+)',
    ]
    
    detected_circular = None
    for pattern in circular_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            detected_circular = match.group(0).strip()
            break
    
    # Build title from filename
    # Clean up common separators and formatting
    title = name
    # Replace underscores and hyphens with spaces (but preserve those in circular numbers)
    title = re.sub(r'[_]', ' ', title)
    # Replace multiple hyphens used as separators (but keep single hyphens in words)
    title = re.sub(r'\s*-\s*', ' - ', title)
    # Clean up multiple spaces
    title = re.sub(r'\s+', ' ', title).strip()
    # Title case if all uppercase or all lowercase
    if title == title.upper() or title == title.lower():
        title = title.title()
    
    result = {
        "title": title,
        "regulatory_body": detected_body,
        "circular_number": detected_circular,
        "parsed": True
    }
    
    return result


@api_router.post("/regulations/upload")
async def upload_regulation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    regulation_data: str = None,
    current_user: dict = Depends(check_not_auditor)
):
    """Upload a regulation document for background processing. Auditors cannot upload."""
    import json
    
    try:
        reg_info = json.loads(regulation_data) if regulation_data else {}

        # Read file content immediately (before background task)
        file_content = await file.read()
        file_size = len(file_content)

        # Enforce file size limit (50MB)
        MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
        if file_size > MAX_FILE_SIZE_BYTES:
            file_size_mb = round(file_size / (1024 * 1024), 1)
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({file_size_mb}MB). Maximum file size is 50MB. Please reduce the file size and try again."
            )

        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Create job for tracking
        job = await upload_job_service.create_job(
            user_id=current_user['user_id'],
            organization=organization,
            job_type="regulation",
            file_name=file.filename,
            file_size=file_size,
            metadata=reg_info
        )
        
        # Start background processing
        background_tasks.add_task(
            process_regulation_upload_background,
            job['id'],
            file_content,
            file.filename,
            reg_info,
            current_user['user_id'],
            organization
        )
        
        logger.info(f"[REGULATION UPLOAD] Started job {job['id']} for {file.filename}")
        
        return {
            "message": "Upload started",
            "job_id": job['id'],
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting regulation upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.post("/regulations/{regulation_id}/embed")
async def embed_regulation_clauses(
    regulation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Embed (or re-embed) regulation clauses into Qdrant regulation_clauses collection.
    This is useful for regulations already in MongoDB that need their Qdrant vectors updated.
    """
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not available")

    # Get user's organization
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    # Find the regulation in MongoDB
    regulation = await db.regulations.find_one({"id": regulation_id}, {"_id": 0})
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found")

    clauses = regulation.get('clauses', [])
    if not clauses:
        return {"message": "No clauses found for this regulation", "stored": 0}

    # Convert clauses to dict format for vector service
    clauses_for_vector = []
    for clause in clauses:
        clause_text = clause.get('text') or clause.get('original_text', '')
        if clause_text:
            clauses_for_vector.append({
                'clause_id': clause.get('clause_id', str(uuid.uuid4())),
                'text': clause_text,
                'original_text': clause.get('original_text', clause_text),
                'section': clause.get('section'),
                'page_number': clause.get('page_number'),
                'title': clause.get('title'),
                'requirement_type': clause.get('requirement_type', 'mandatory'),
                'subject_category': clause.get('subject_category', 'general'),
                'criticality': clause.get('criticality', 'high'),
                'tags': clause.get('tags', []),
                'keywords': clause.get('keywords', [])
            })

    # Store in regulation_clauses collection
    stored_count = await vector_service.store_regulation_clauses(
        regulation_id=regulation_id,
        clauses=clauses_for_vector,
        organization=organization,
        user_id=current_user['user_id']
    )

    return {
        "message": f"Embedded {stored_count} clauses for regulation '{regulation.get('title')}'",
        "regulation_id": regulation_id,
        "stored": stored_count,
        "total_clauses": len(clauses)
    }


# ========== REGULATORY UPDATES ENDPOINTS ==========
@api_router.get("/regulation-updates")
async def get_regulation_updates(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """
    Get regulatory updates feed (timeline of new circulars).
    Returns updates sorted by date (newest first).
    """
    try:
        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Build query - filter by organization or system-wide
        query = {"$or": [
            {"organization": organization},
            {"organization": "system"}  # System-wide regulatory updates
        ]}

        if status:
            query["status"] = status

        # Fetch updates sorted by date (newest first)
        updates = await db.regulation_updates.find(query, {"_id": 0}).sort("crawl_date", -1).limit(limit).to_list(limit)

        # Get associated regulation details
        for update in updates:
            if update.get('regulation_id'):
                regulation = await db.regulations.find_one(
                    {"id": update['regulation_id']},
                    {"_id": 0, "id": 1, "title": 1, "regulatory_body": 1}
                )
                if regulation:
                    update['regulation'] = regulation

        return {"updates": updates, "count": len(updates)}

    except Exception as e:
        logger.error(f"Error fetching regulation updates: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/regulation-updates/{update_id}")
async def get_regulation_update_detail(
    update_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed impact package for a specific regulatory update.
    Includes: impact analysis, affected policies, affected clauses,
    remediation effort, priority, and auto-created tasks.
    """
    try:
        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Fetch the update (organization-specific or system-wide)
        update = await db.regulation_updates.find_one({
            "id": update_id,
            "$or": [
                {"organization": organization},
                {"organization": "system"}
            ]
        }, {"_id": 0})

        if not update:
            raise HTTPException(status_code=404, detail="Regulatory update not found")

        # Get associated regulation details
        if update.get('regulation_id'):
            regulation = await db.regulations.find_one(
                {"id": update['regulation_id']},
                {"_id": 0}
            )
            if regulation:
                update['regulation'] = regulation

        # Get affected policies (full details)
        affected_policy_ids = update.get('affected_policies', [])
        if affected_policy_ids:
            policies = await db.policies.find(
                {"id": {"$in": affected_policy_ids}},
                {"_id": 0, "id": 1, "title": 1, "type": 1, "status": 1}
            ).to_list(100)
            update['affected_policies_details'] = policies

        # Get affected clauses (full details)
        affected_clause_ids = update.get('affected_clauses', [])
        if affected_clause_ids:
            clauses = await db.clauses.find(
                {"clause_id": {"$in": affected_clause_ids}},
                {"_id": 0}
            ).to_list(100)
            update['affected_clauses_details'] = clauses

        # Get auto-created tasks
        auto_task_ids = update.get('auto_created_tasks', [])
        if auto_task_ids:
            tasks = await db.tasks.find(
                {"id": {"$in": auto_task_ids}},
                {"_id": 0}
            ).to_list(100)
            update['auto_created_tasks_details'] = tasks

        return update

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching regulation update detail: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/regulation-updates")
async def create_regulation_update(
    update_data: RegulationUpdateCreate,
    current_user: dict = Depends(check_not_auditor)
):
    """
    Create a new regulatory update and auto-generate review tasks.
    This simulates ingestion of a new regulatory amendment or update.
    """
    try:
        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Verify the regulation exists
        regulation = await db.regulations.find_one(
            {"id": update_data.regulation_id, "organization": organization},
            {"_id": 0}
        )
        if not regulation:
            raise HTTPException(status_code=404, detail="Parent regulation not found")

        # Create the regulation update
        reg_update = RegulationUpdate(
            regulation_id=update_data.regulation_id,
            title=update_data.title,
            regulatory_body=update_data.regulatory_body,
            circular_number=update_data.circular_number,
            effective_date=update_data.effective_date,
            summary=update_data.summary,
            impact_analysis=update_data.impact_analysis,
            affected_policies=update_data.affected_policies,
            departments_affected=update_data.departments_affected,
            priority=update_data.priority,
            organization=organization,
            user_id=current_user['user_id']
        )

        # Auto-create review tasks for affected departments
        auto_created_task_ids = []

        for dept in update_data.departments_affected:
            task = Task(
                title=f"Review regulatory update: {update_data.title}",
                description=f"Impact: {update_data.impact_analysis or 'Regulatory change requires review'}\n\nSummary: {update_data.summary or 'Please review the update and assess impact on current policies.'}",
                department=dept,
                priority=update_data.priority,
                regulation_id=update_data.regulation_id,
                regulation_update_id=reg_update.id,
                source_type="regulatory_update",
                user_id=current_user['user_id'],
                organization=organization,
                auto_assigned=True
            )

            task_dict = task.model_dump()
            task_dict['created_at'] = task_dict['created_at'].isoformat()
            task_dict['updated_at'] = task_dict['updated_at'].isoformat()
            if task_dict.get('due_date'):
                task_dict['due_date'] = task_dict['due_date'].isoformat()

            await db.tasks.insert_one(task_dict)
            auto_created_task_ids.append(task.id)

            # Create notification for new task
            notification = {
                "id": str(uuid.uuid4()),
                "user_id": current_user['user_id'],
                "type": "task_created",
                "title": "New Regulatory Review Task",
                "message": f"A new task has been auto-created for {dept}: {task.title}",
                "link": f"/tasks/{task.id}",
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.notifications.insert_one(notification)

        # Update the regulation update with task IDs
        reg_update.auto_created_tasks = auto_created_task_ids

        # Save to database
        update_dict = reg_update.model_dump()
        update_dict['created_at'] = update_dict['created_at'].isoformat()
        update_dict['crawl_date'] = update_dict['crawl_date'].isoformat()
        if update_dict.get('effective_date'):
            update_dict['effective_date'] = update_dict['effective_date'].isoformat()
        if update_dict.get('reviewed_at'):
            update_dict['reviewed_at'] = update_dict['reviewed_at'].isoformat()

        await db.regulation_updates.insert_one(update_dict)

        logger.info(f"[REGULATION UPDATE] Created {reg_update.id} with {len(auto_created_task_ids)} auto-tasks")

        return {
            "message": "Regulatory update created successfully",
            "update_id": reg_update.id,
            "tasks_created": len(auto_created_task_ids),
            "task_ids": auto_created_task_ids
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating regulation update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/regulation-updates/{update_id}/review")
async def mark_regulation_update_reviewed(
    update_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a regulatory update as reviewed.
    Changes status from 'pending_review' to 'reviewed'.
    """
    try:
        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Update the status
        result = await db.regulation_updates.update_one(
            {
                "id": update_id,
                "$or": [
                    {"organization": organization},
                    {"organization": "system"}
                ]
            },
            {
                "$set": {
                    "status": "reviewed",
                    "reviewed_by": current_user['user_id'],
                    "reviewed_at": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Regulatory update not found")

        return {"message": "Regulatory update marked as reviewed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking update as reviewed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/regulation-updates/{update_id}/adjust-impact-score")
async def adjust_impact_score(
    update_id: str,
    adjustment: ImpactScoreAdjustment,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually adjust the impact score of a regulatory update.
    Tracks correction history with user and justification.
    (Human-in-the-loop correction on impact scores)
    """
    try:
        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Fetch the update
        update = await db.regulation_updates.find_one({
            "id": update_id,
            "$or": [
                {"organization": organization},
                {"organization": "system"}
            ]
        }, {"_id": 0})

        if not update:
            raise HTTPException(status_code=404, detail="Regulatory update not found")

        # Create correction record
        correction_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": current_user['user_id'],
            "user_email": current_user.get('email', 'unknown'),
            "old_score": update.get('impact_score'),
            "new_score": adjustment.new_score,
            "justification": adjustment.justification
        }

        # Update the impact score and add correction to history
        result = await db.regulation_updates.update_one(
            {"id": update_id},
            {
                "$set": {
                    "impact_score": adjustment.new_score
                },
                "$push": {
                    "impact_score_corrections": correction_record
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Regulatory update not found")

        logger.info(f"[IMPACT SCORE ADJUSTED] Update {update_id}: {update.get('impact_score')} -> {adjustment.new_score} by {current_user['user_id']}")

        return {
            "message": "Impact score adjusted successfully",
            "old_score": update.get('impact_score'),
            "new_score": adjustment.new_score,
            "correction_tracked": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adjusting impact score: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== GAP ANALYSIS ENDPOINTS ==========
@api_router.post("/gap-analysis/run")
async def run_gap_analysis(
    policy_id: str,
    regulation_id: str,
    analysis_mode: str = "deep_analysis",
    current_user: dict = Depends(get_current_user)
):
    """
    Semantic Gap Analysis: LLM-First, Regulation as Source of Truth.
    
    Philosophy:
    - REGULATIONS are the SOURCE OF TRUTH (iterate over regulations)
    - LLM SEMANTIC MATCHING is PRIMARY (not keyword-based)
    - For each regulation clause, find semantically matching policy clauses
    - Assess compliance based on MEANING, not exact word matching
    
    This endpoint:
    1. Retrieves policy and regulation with their enriched clauses
    2. For EACH regulation clause, uses LLM to find matching policies
    3. Uses LLM to assess compliance level (compliant, partial, weak, missing)
    4. Generates executive summary and compliance score
    """
    try:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
        # Regulations can be user-specific OR system-wide (user_id: "system")
        regulation = await db.regulations.find_one({
            "id": regulation_id,
            "$or": [{"user_id": current_user['user_id']}, {"user_id": "system"}]
        }, {"_id": 0})

        # Feature #219: If not found in regulations, check NPCI circulars
        if not regulation and regulation_id.startswith("npci_"):
            npci_id_str = regulation_id.replace("npci_", "")
            try:
                npci_id_int = int(npci_id_str)
                npci_circ = await db.npci_circulars.find_one({"npci_id": npci_id_int}, {"_id": 0})
            except (ValueError, TypeError):
                npci_circ = None
            if npci_circ:
                regulation = _npci_circular_to_regulation(npci_circ)

        if not policy or not regulation:
            raise HTTPException(status_code=404, detail="Policy or regulation not found")
        
        # Fetch user's organization from DB (JWT doesn't include it)
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
        user_organization = (user_doc or {}).get('organization', 'default')
        
        policy_clauses = policy.get('clauses', [])
        regulation_clauses = regulation.get('clauses', [])
        
        logger.info(f"Starting SEMANTIC gap analysis (LLM-First, Regulation-Based)")
        logger.info(f"Regulation: {regulation.get('title')} ({len(regulation_clauses)} clauses) - SOURCE OF TRUTH")
        logger.info(f"Policy: {policy.get('title')} ({len(policy_clauses)} clauses)")
        
        # Use NEW Semantic Gap Analysis Service - LLM-First approach with Qdrant vector search
        gap_report = await semantic_gap_service.analyze(
            policy_clauses=policy_clauses,
            regulation_clauses=regulation_clauses,
            policy_id=policy_id,
            policy_title=policy.get('title', 'Untitled Policy'),
            regulation_id=regulation_id,
            regulation_title=regulation.get('title', 'Untitled Regulation'),
            organization=user_organization
        )
        
        # Convert report to dict for storage
        report_dict = semantic_gap_report_to_dict(gap_report)
        
        # Create Gap objects for storage (regulation-centric)
        gaps = []
        for gap_result in gap_report.gap_results:
            gap = Gap(
                gap_type=gap_result.gap_type.value,
                severity=gap_result.severity.value,
                confidence_score=gap_result.confidence_score,
                policy_clause=Clause(
                    id=gap_result.primary_policy_match.get('clause_id', '') if gap_result.primary_policy_match else '',
                    title=gap_result.primary_policy_match.get('title', 'No Match') if gap_result.primary_policy_match else 'No Match',
                    text=gap_result.primary_policy_match.get('text', '') if gap_result.primary_policy_match else '',
                    keywords=[]
                ) if gap_result.primary_policy_match else None,
                regulation_clause=Clause(
                    id=gap_result.regulation_clause_id,
                    title=gap_result.regulation_title,
                    text=gap_result.regulation_text,
                    keywords=[]
                ),
                description=gap_result.gap_description,
                suggested_fix=gap_result.suggested_action,
                metadata={
                    "covered_elements": gap_result.covered_elements,
                    "missing_elements": gap_result.missing_elements,
                    "weak_elements": gap_result.weak_elements,
                    "subject_category": gap_result.subject_category,
                    "requirement_type": gap_result.requirement_type,
                    "criticality": gap_result.criticality,
                    "matched_policy_count": len(gap_result.matched_policy_clauses),
                    "assigned_department": gap_result.assigned_department,
                    "deadline": gap_result.remediation_deadline,
                    "evidence_map": gap_result.evidence_map
                },
                evidence_map=gap_result.evidence_map
            )
            gaps.append(gap)
        
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        result = GapAnalysisResult(
            policy_id=policy_id,
            regulation_id=regulation_id,
            gaps=gaps,
            compliance_score=gap_report.compliance_score,
            total_clauses_analyzed=gap_report.total_regulation_clauses,  # Now regulation-based
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default')
        )
        
        result_dict = result.model_dump()
        result_dict['created_at'] = result_dict['created_at'].isoformat()
        # Add semantic report data
        result_dict['semantic_report'] = report_dict
        result_dict['executive_summary'] = gap_report.executive_summary
        result_dict['fully_compliant_count'] = gap_report.fully_compliant_count
        result_dict['partially_compliant_count'] = gap_report.partially_compliant_count
        result_dict['non_compliant_count'] = gap_report.non_compliant_count
        result_dict['analysis_type'] = 'semantic_llm_first'
        
        await db.gap_analyses.insert_one(result_dict)
        
        # Auto-generate tasks for critical/high severity gaps
        non_compliant_gaps = [g for g in gaps if g.gap_type != 'compliant' and g.severity in ['Critical', 'High']]
        if non_compliant_gaps:
            generated_tasks = await llm_service.generate_tasks_gpt(
                [g.model_dump() for g in non_compliant_gaps[:10]],
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
                    regulation_id=regulation_id,
                    gap_analysis_id=result.id,
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
        else:
            tasks_created = 0
        
        return {
            "message": "Semantic gap analysis completed (LLM-First, Regulation as Source of Truth)",
            "result_id": result.id,
            "compliance_score": gap_report.compliance_score,
            "total_regulation_clauses": gap_report.total_regulation_clauses,
            "total_policy_clauses": gap_report.total_policy_clauses,
            "fully_compliant_count": gap_report.fully_compliant_count,
            "partially_compliant_count": gap_report.partially_compliant_count,
            "non_compliant_count": gap_report.non_compliant_count,
            "critical_gaps": gap_report.critical_gaps,
            "high_gaps": gap_report.high_gaps,
            "medium_gaps": gap_report.medium_gaps,
            "low_gaps": gap_report.low_gaps,
            "executive_summary": gap_report.executive_summary,
            "gaps": [gap.model_dump() for gap in gaps],
            "semantic_report": report_dict,
            "tasks_created": tasks_created
        }
    except Exception as e:
        logger.error(f"Error in semantic gap analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@api_router.post("/gap-analysis/run-stream")
async def run_gap_analysis_stream(
    policy_id: str,
    regulation_id: str,
    analysis_mode: str = "deep_analysis",
    current_user: dict = Depends(get_current_user)
):
    """
    Streaming version of gap analysis with real-time progress updates.
    Returns Server-Sent Events (SSE) with progress information.
    Supports analysis_mode: 'quick_scan' or 'deep_analysis' (default).
    """
    async def generate_events():
        progress_queue = asyncio.Queue()
        
        async def progress_callback(step: str, progress: int, message: str, details: dict):
            """Send progress updates to the queue."""
            event_data = {
                "step": step,
                "progress": progress,
                "message": message,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await progress_queue.put(event_data)
        
        try:
            # Fetch policy and regulation
            policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
            regulation = await db.regulations.find_one({
                "id": regulation_id,
                "$or": [{"user_id": current_user['user_id']}, {"user_id": "system"}]
            }, {"_id": 0})

            # Feature #219: Check NPCI circulars if not found in regulations
            if not regulation and regulation_id.startswith("npci_"):
                npci_id_str = regulation_id.replace("npci_", "")
                try:
                    npci_id_int = int(npci_id_str)
                    npci_circ = await db.npci_circulars.find_one({"npci_id": npci_id_int}, {"_id": 0})
                except (ValueError, TypeError):
                    npci_circ = None
                if npci_circ:
                    regulation = _npci_circular_to_regulation(npci_circ)

            if not policy or not regulation:
                yield f"data: {json.dumps({'error': 'Policy or regulation not found', 'step': 'error'})}\n\n"
                return

            policy_clauses = policy.get('clauses', [])
            regulation_clauses = regulation.get('clauses', [])
            
            # Fetch user's organization from DB (JWT doesn't include it)
            user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
            user_organization = (user_doc or {}).get('organization', 'default')
            
            # Initial event
            mode_label = "Deep Analysis" if analysis_mode == "deep_analysis" else "Quick Scan"
            yield f"data: {json.dumps({'step': 'start', 'progress': 0, 'message': f'Starting {mode_label}...', 'details': {'policy': policy.get('title'), 'regulation': regulation.get('title'), 'regulation_clauses': len(regulation_clauses), 'policy_clauses': len(policy_clauses), 'analysis_mode': analysis_mode}})}\n\n"
            
            # Run analysis with progress callback
            async def run_analysis():
                return await semantic_gap_service.analyze(
                    policy_clauses=policy_clauses,
                    regulation_clauses=regulation_clauses,
                    policy_id=policy_id,
                    policy_title=policy.get('title', 'Untitled Policy'),
                    regulation_id=regulation_id,
                    regulation_title=regulation.get('title', 'Untitled Regulation'),
                    organization=user_organization,
                    progress_callback=progress_callback
                )
            
            # Create task for analysis
            analysis_task = asyncio.create_task(run_analysis())
            
            # Stream progress events while analysis runs
            while not analysis_task.done():
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=2.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
                except Exception as stream_err:
                    logger.warning(f"Error streaming progress event: {stream_err}")
                    yield f": heartbeat\n\n"
            
            # Get the result — if the task raised, we catch it below in the outer try
            gap_report = await analysis_task
            
            # Drain any remaining events
            while not progress_queue.empty():
                try:
                    event = await progress_queue.get()
                    yield f"data: {json.dumps(event)}\n\n"
                except Exception:
                    pass
            
            # Store results (same as regular endpoint)
            report_dict = semantic_gap_report_to_dict(gap_report)
            
            gaps = []
            for gap_result in gap_report.gap_results:
                gap = Gap(
                    gap_type=gap_result.gap_type.value,
                    severity=gap_result.severity.value,
                    confidence_score=gap_result.confidence_score,
                    policy_clause=Clause(
                        id=gap_result.primary_policy_match.get('clause_id', '') if gap_result.primary_policy_match else '',
                        title=gap_result.primary_policy_match.get('title', 'No Match') if gap_result.primary_policy_match else 'No Match',
                        text=gap_result.primary_policy_match.get('text', '') if gap_result.primary_policy_match else '',
                        keywords=[]
                    ) if gap_result.primary_policy_match else None,
                    regulation_clause=Clause(
                        id=gap_result.regulation_clause_id,
                        title=gap_result.regulation_title,
                        text=gap_result.regulation_text,
                        keywords=[]
                    ),
                    description=gap_result.gap_description,
                    suggested_fix=gap_result.suggested_action,
                    metadata={
                        "covered_elements": gap_result.covered_elements,
                        "missing_elements": gap_result.missing_elements,
                        "weak_elements": getattr(gap_result, 'weak_elements', []),
                        "subject_category": gap_result.subject_category,
                        "requirement_type": getattr(gap_result, 'requirement_type', 'mandatory'),
                        "criticality": getattr(gap_result, 'criticality', 'medium'),
                        "assigned_department": gap_result.assigned_department,
                        "deadline": getattr(gap_result, 'remediation_deadline', '1 month'),
                        "evidence_map": gap_result.evidence_map
                    },
                    evidence_map=gap_result.evidence_map
                )
                gaps.append(gap)
            
            user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
            
            result = GapAnalysisResult(
                policy_id=policy_id,
                regulation_id=regulation_id,
                gaps=gaps,
                compliance_score=gap_report.compliance_score,
                total_clauses_analyzed=gap_report.total_regulation_clauses,
                user_id=current_user['user_id'],
                organization=user_doc.get('organization', 'Default')
            )
            
            result_dict = result.model_dump()
            result_dict['created_at'] = result_dict['created_at'].isoformat()
            result_dict['semantic_report'] = report_dict
            result_dict['executive_summary'] = gap_report.executive_summary
            result_dict['fully_compliant_count'] = gap_report.fully_compliant_count
            result_dict['partially_compliant_count'] = gap_report.partially_compliant_count
            result_dict['non_compliant_count'] = gap_report.non_compliant_count
            result_dict['analysis_type'] = 'semantic_llm_first'
            result_dict['analysis_mode'] = analysis_mode

            await db.gap_analyses.insert_one(result_dict)
            
            # Auto-generate tasks for critical/high severity gaps (same as regular endpoint)
            tasks_created = 0
            non_compliant_gaps = [g for g in gaps if g.gap_type != 'compliant' and g.severity in ['Critical', 'High']]
            if non_compliant_gaps:
                task_msg = f"Generating tasks for {len(non_compliant_gaps)} critical/high gaps..."
                yield f"data: {json.dumps({'step': 'generating_tasks', 'progress': 95, 'message': task_msg, 'details': {}})}\n\n"
                
                try:
                    generated_tasks = await llm_service.generate_tasks_gpt(
                        [g.model_dump() for g in non_compliant_gaps[:10]],
                        {"policy": policy.get('title'), "regulation": regulation.get('title')}
                    )
                    
                    for task_data in generated_tasks[:5]:
                        task = Task(
                            title=task_data.get('title', 'Address compliance gap'),
                            description=task_data.get('description', 'Review and resolve'),
                            priority=task_data.get('priority', SeverityLevel.MEDIUM),
                            department=task_data.get('department'),
                            policy_id=policy_id,
                            regulation_id=regulation_id,
                            gap_analysis_id=result.id,
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
                except Exception as task_error:
                    logger.error(f"Task generation failed: {str(task_error)}")
            
            # Send final result
            final_result = {
                "step": "done",
                "progress": 100,
                "message": "Analysis complete!",
                "result": {
                    "id": result.id,
                    "result_id": result.id,
                    "compliance_score": gap_report.compliance_score,
                    "total_regulation_clauses": gap_report.total_regulation_clauses,
                    "total_policy_clauses": gap_report.total_policy_clauses,
                    "fully_compliant_count": gap_report.fully_compliant_count,
                    "partially_compliant_count": gap_report.partially_compliant_count,
                    "non_compliant_count": gap_report.non_compliant_count,
                    "critical_gaps": gap_report.critical_gaps,
                    "high_gaps": gap_report.high_gaps,
                    "medium_gaps": gap_report.medium_gaps,
                    "low_gaps": gap_report.low_gaps,
                    "executive_summary": gap_report.executive_summary,
                    "gaps": [g.model_dump() for g in gaps],
                    "tasks_created": tasks_created,
                    "analysis_mode": analysis_mode
                }
            }
            yield f"data: {json.dumps(final_result)}\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming gap analysis: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'step': 'error', 'progress': 0, 'message': str(e), 'error': True})}\n\n"
    
    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@api_router.get("/gap-analysis/history")
async def get_gap_analysis_history(
    current_user: dict = Depends(get_current_user)
):
    """Get all gap analysis results. Compliance_head and auditor see all in org, users see own."""
    try:
        # Get user details to check role
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        user_role = user_doc.get('role', 'user')
        organization = user_doc.get('organization')

        # Role-based access
        if user_role in ['compliance_head', 'auditor']:
            query = {"organization": organization}
        else:
            query = {"user_id": current_user['user_id']}

        analyses = await db.gap_analyses.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        # Enrich with policy and regulation titles and calculate severity counts
        for analysis in analyses:
            policy = await db.policies.find_one({"id": analysis.get("policy_id")}, {"_id": 0, "title": 1})
            regulation = await db.regulations.find_one({"id": analysis.get("regulation_id")}, {"_id": 0, "title": 1})
            analysis["policy_title"] = policy.get("title", "Unknown Policy") if policy else "Unknown Policy"
            analysis["regulation_title"] = regulation.get("title", "Unknown Regulation") if regulation else "Unknown Regulation"
            
            # Calculate severity counts from gaps array
            gaps = analysis.get("gaps", [])
            analysis["total_gaps"] = len(gaps)
            analysis["critical_gaps"] = sum(1 for g in gaps if g.get("severity") == "Critical")
            analysis["high_gaps"] = sum(1 for g in gaps if g.get("severity") == "High")
            analysis["medium_gaps"] = sum(1 for g in gaps if g.get("severity") == "Medium")
            analysis["low_gaps"] = sum(1 for g in gaps if g.get("severity") == "Low")
        
        return analyses
    except Exception as e:
        logger.error(f"Error fetching gap analysis history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")


@api_router.get("/gap-analysis/{analysis_id}")
async def get_gap_analysis_detail(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed gap analysis result by ID."""
    try:
        # Role-based access: compliance_head and auditor see all org analyses
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        user_role = user_doc.get('role', 'user') if user_doc else 'user'
        organization = user_doc.get('organization', 'Default') if user_doc else 'Default'

        if user_role in ['compliance_head', 'auditor']:
            query = {"id": analysis_id, "organization": organization}
        else:
            query = {"id": analysis_id, "user_id": current_user['user_id']}

        analysis = await db.gap_analyses.find_one(query, {"_id": 0})

        if not analysis:
            raise HTTPException(status_code=404, detail="Gap analysis not found")
        
        # Enrich with policy and regulation titles
        policy = await db.policies.find_one({"id": analysis.get("policy_id")}, {"_id": 0, "title": 1})
        regulation = await db.regulations.find_one({"id": analysis.get("regulation_id")}, {"_id": 0, "title": 1})
        analysis["policy_title"] = policy.get("title", "Unknown Policy") if policy else "Unknown Policy"
        analysis["regulation_title"] = regulation.get("title", "Unknown Regulation") if regulation else "Unknown Regulation"
        
        # Calculate severity counts from gaps
        gaps = analysis.get("gaps", [])
        analysis["critical_gaps"] = sum(1 for g in gaps if g.get("severity") == "Critical")
        analysis["high_gaps"] = sum(1 for g in gaps if g.get("severity") == "High")
        analysis["medium_gaps"] = sum(1 for g in gaps if g.get("severity") == "Medium")
        analysis["low_gaps"] = sum(1 for g in gaps if g.get("severity") == "Low")
        
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching gap analysis detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch analysis: {str(e)}")


@api_router.get("/gap-analysis/{analysis_id}/source-reference/{gap_index}")
async def get_gap_source_reference(
    analysis_id: str,
    gap_index: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get source reference for a specific gap in a gap analysis.
    Returns PDF page image with the relevant clause text highlighted.
    Renders the actual PDF page as a base64 image and provides text context.
    """
    try:
        # Get the gap analysis
        analysis = await db.gap_analyses.find_one(
            {"id": analysis_id, "user_id": current_user['user_id']},
            {"_id": 0}
        )
        if not analysis:
            raise HTTPException(status_code=404, detail="Gap analysis not found")

        gaps = analysis.get("gaps", [])
        if gap_index < 0 or gap_index >= len(gaps):
            raise HTTPException(status_code=404, detail="Gap index out of range")

        gap = gaps[gap_index]

        # Get policy and regulation documents to find file paths
        policy_id = analysis.get("policy_id")
        regulation_id = analysis.get("regulation_id")

        policy = await db.policies.find_one({"id": policy_id}, {"_id": 0})
        regulation = await db.regulations.find_one({"id": regulation_id}, {"_id": 0})

        result = {
            "gap_index": gap_index,
            "gap_type": gap.get("gap_type"),
            "severity": gap.get("severity"),
            "description": gap.get("description"),
            "policy_source": None,
            "regulation_source": None
        }

        # Extract source reference for policy clause
        policy_clause = gap.get("policy_clause")
        if policy_clause and policy:
            page_num = policy_clause.get("page_number") or None
            clause_text = policy_clause.get("text", "") or policy_clause.get("original_text", "")
            clause_id = policy_clause.get("clause_id", "")
            clause_title = policy_clause.get("title", "")
            clause_section = policy_clause.get("section", "")
            file_url = policy.get("file_url", "")

            # Look up page_number from the original clause in the policy document if not in gap data
            if not page_num and clause_id:
                for orig_clause in policy.get("clauses", []):
                    if orig_clause.get("clause_id") == clause_id:
                        page_num = orig_clause.get("page_number")
                        if not clause_title:
                            clause_title = orig_clause.get("title", "")
                        if not clause_section:
                            clause_section = orig_clause.get("section", "")
                        if not clause_text:
                            clause_text = orig_clause.get("text", "") or orig_clause.get("original_text", "")
                        break
            
            # Try matching by title if clause_id lookup failed
            if not page_num and clause_title:
                for orig_clause in policy.get("clauses", []):
                    if orig_clause.get("title", "").strip().lower() == clause_title.strip().lower():
                        page_num = orig_clause.get("page_number")
                        if not clause_section:
                            clause_section = orig_clause.get("section", "")
                        break

            page_num = page_num or 1

            # Determine clause number from position in document
            clause_number = None
            for idx, orig_clause in enumerate(policy.get("clauses", []), 1):
                if orig_clause.get("clause_id") == clause_id:
                    clause_number = idx
                    break

            page_image = None
            if file_url and file_url.endswith('.pdf'):
                if os.path.exists(file_url) or file_url.startswith('http://') or file_url.startswith('https://'):
                    page_image = await _render_pdf_page_base64(file_url, page_num, clause_text)

            result["policy_source"] = {
                "document_title": policy.get("title", "Unknown Policy"),
                "document_id": policy_id,
                "page_number": page_num,
                "clause_id": clause_id,
                "clause_number": clause_number,
                "clause_text": clause_text,
                "clause_title": clause_title,
                "section": clause_section,
                "page_image": page_image,
                "file_type": os.path.splitext(file_url)[-1].lower() if file_url else ""
            }

        # Extract source reference for regulation clause
        regulation_clause = gap.get("regulation_clause")
        if regulation_clause and regulation:
            page_num = regulation_clause.get("page_number") or None
            clause_text = regulation_clause.get("text", "") or regulation_clause.get("original_text", "")
            clause_id = regulation_clause.get("clause_id", "")
            clause_title = regulation_clause.get("title", "")
            clause_section = regulation_clause.get("section", "")
            file_url = regulation.get("file_url", "")

            # Look up from original regulation clauses (including chapters)
            all_reg_clauses = regulation.get("clauses", [])
            for chapter in regulation.get("chapters", []):
                all_reg_clauses.extend(chapter.get("sub_clauses", []))

            if not page_num and clause_id:
                for orig_clause in all_reg_clauses:
                    if orig_clause.get("clause_id") == clause_id:
                        page_num = orig_clause.get("page_number")
                        if not clause_title:
                            clause_title = orig_clause.get("title", "")
                        if not clause_section:
                            clause_section = orig_clause.get("section", "")
                        if not clause_text:
                            clause_text = orig_clause.get("text", "") or orig_clause.get("original_text", "")
                        break

            if not page_num and clause_title:
                for orig_clause in all_reg_clauses:
                    if orig_clause.get("title", "").strip().lower() == clause_title.strip().lower():
                        page_num = orig_clause.get("page_number")
                        if not clause_section:
                            clause_section = orig_clause.get("section", "")
                        break

            page_num = page_num or 1

            # Determine clause number from position
            clause_number = None
            for idx, orig_clause in enumerate(all_reg_clauses, 1):
                if orig_clause.get("clause_id") == clause_id:
                    clause_number = idx
                    break

            page_image = None
            if file_url and file_url.endswith('.pdf'):
                if os.path.exists(file_url) or file_url.startswith('http://') or file_url.startswith('https://'):
                    page_image = await _render_pdf_page_base64(file_url, page_num, clause_text)

            result["regulation_source"] = {
                "document_title": regulation.get("title", "Unknown Regulation"),
                "document_id": regulation_id,
                "page_number": page_num,
                "clause_id": clause_id,
                "clause_number": clause_number,
                "clause_text": clause_text,
                "clause_title": clause_title,
                "section": clause_section,
                "page_image": page_image,
                "file_type": os.path.splitext(file_url)[-1].lower() if file_url else ""
            }

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching source reference: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch source reference: {str(e)}")


# ========== GAP ANALYSIS HUMAN-IN-THE-LOOP CORRECTIONS (Feature #40) ==========

class GapCorrectionRequest(BaseModel):
    action: str  # "approve", "reject", "modify"
    reason: Optional[str] = None  # Required for reject
    severity: Optional[str] = None  # For modify
    suggested_fix: Optional[str] = None  # For modify
    description: Optional[str] = None  # For modify


@api_router.post("/gap-analysis/{analysis_id}/gaps/{gap_index}/correct")
async def correct_gap_finding(
    analysis_id: str,
    gap_index: int,
    correction: GapCorrectionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #40: Human-in-the-loop corrections for gap findings.
    Allows users to approve, reject, or modify individual gap findings.
    All corrections are logged with timestamp and user for audit trail.
    """
    try:
        if correction.action not in ("approve", "reject", "modify"):
            raise HTTPException(status_code=400, detail="Action must be 'approve', 'reject', or 'modify'")

        if correction.action == "reject" and not correction.reason:
            raise HTTPException(status_code=400, detail="Reason is required when rejecting a gap")

        # Get user details
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default') if user_doc else 'Default'
        role = user_doc.get('role', 'user') if user_doc else 'user'
        user_email = user_doc.get('email', current_user.get('email', 'unknown')) if user_doc else 'unknown'

        # Build query based on role
        if role in ['compliance_head', 'auditor']:
            query = {"id": analysis_id, "organization": organization}
        else:
            query = {"id": analysis_id, "user_id": current_user['user_id']}

        analysis = await db.gap_analyses.find_one(query, {"_id": 0})
        if not analysis:
            raise HTTPException(status_code=404, detail="Gap analysis not found")

        gaps = analysis.get("gaps", [])
        if gap_index < 0 or gap_index >= len(gaps):
            raise HTTPException(status_code=404, detail="Gap index out of range")

        gap = gaps[gap_index]

        # Build the correction record
        correction_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": current_user['user_id'],
            "user_email": user_email,
            "user_name": user_doc.get('full_name', 'Unknown') if user_doc else 'Unknown',
            "action": correction.action,
        }

        # Track old values for audit
        if correction.action == "modify":
            correction_record["changes"] = {}
            if correction.severity and correction.severity != gap.get("severity"):
                correction_record["changes"]["severity"] = {
                    "old": gap.get("severity"),
                    "new": correction.severity
                }
            if correction.suggested_fix is not None and correction.suggested_fix != gap.get("suggested_fix"):
                correction_record["changes"]["suggested_fix"] = {
                    "old": gap.get("suggested_fix"),
                    "new": correction.suggested_fix
                }
            if correction.description is not None and correction.description != gap.get("description"):
                correction_record["changes"]["description"] = {
                    "old": gap.get("description"),
                    "new": correction.description
                }
            if not correction_record["changes"]:
                raise HTTPException(status_code=400, detail="No changes provided for modification")

        elif correction.action == "reject":
            correction_record["reason"] = correction.reason

        # Apply the correction
        update_ops = {}

        # Set the review status on the gap
        status_map = {"approve": "approved", "reject": "rejected", "modify": "modified"}
        update_ops[f"gaps.{gap_index}.review_status"] = status_map[correction.action]
        update_ops[f"gaps.{gap_index}.reviewed_at"] = datetime.now(timezone.utc).isoformat()
        update_ops[f"gaps.{gap_index}.reviewed_by"] = user_email

        # Apply modifications
        if correction.action == "modify":
            if correction.severity:
                update_ops[f"gaps.{gap_index}.severity"] = correction.severity
            if correction.suggested_fix is not None:
                update_ops[f"gaps.{gap_index}.suggested_fix"] = correction.suggested_fix
            if correction.description is not None:
                update_ops[f"gaps.{gap_index}.description"] = correction.description

        # Update the document
        result = await db.gap_analyses.update_one(
            {"id": analysis_id},
            {
                "$set": update_ops,
                "$push": {
                    f"gaps.{gap_index}.corrections": correction_record
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to save correction")

        # Return the updated gap
        updated_analysis = await db.gap_analyses.find_one({"id": analysis_id}, {"_id": 0})
        updated_gap = updated_analysis["gaps"][gap_index] if updated_analysis else gap

        return {
            "message": f"Gap {status_map[correction.action]} successfully",
            "gap_index": gap_index,
            "action": correction.action,
            "review_status": updated_gap.get("review_status"),
            "correction": correction_record,
            "gap": updated_gap
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error correcting gap finding: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save correction: {str(e)}")


@api_router.get("/gap-analysis/{analysis_id}/gaps/{gap_index}/corrections")
async def get_gap_corrections(
    analysis_id: str,
    gap_index: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #40: Get correction history for a specific gap finding.
    Returns all corrections with timestamps and user info for audit trail.
    """
    try:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default') if user_doc else 'Default'
        role = user_doc.get('role', 'user') if user_doc else 'user'

        if role in ['compliance_head', 'auditor']:
            query = {"id": analysis_id, "organization": organization}
        else:
            query = {"id": analysis_id, "user_id": current_user['user_id']}

        analysis = await db.gap_analyses.find_one(query, {"_id": 0})
        if not analysis:
            raise HTTPException(status_code=404, detail="Gap analysis not found")

        gaps = analysis.get("gaps", [])
        if gap_index < 0 or gap_index >= len(gaps):
            raise HTTPException(status_code=404, detail="Gap index out of range")

        gap = gaps[gap_index]
        corrections = gap.get("corrections", [])

        return {
            "gap_index": gap_index,
            "review_status": gap.get("review_status"),
            "reviewed_at": gap.get("reviewed_at"),
            "reviewed_by": gap.get("reviewed_by"),
            "corrections": corrections,
            "total_corrections": len(corrections)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching gap corrections: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch corrections: {str(e)}")


async def _render_pdf_page_base64(file_path: str, page_number: int, highlight_text: str = "") -> str:
    """
    Render a specific page of a PDF as a base64 encoded image.
    Optionally highlights the given text on the page.
    Supports both local file paths and remote URLs.
    Returns base64 string suitable for embedding in <img src="data:image/png;base64,...">.
    """
    import base64
    import io

    # Handle remote URLs — download to temp cache
    actual_path = file_path
    if file_path.startswith('http://') or file_path.startswith('https://'):
        import hashlib, tempfile, httpx
        url_hash = hashlib.md5(file_path.encode()).hexdigest()
        cache_dir = os.path.join(tempfile.gettempdir(), 'compliai_pdf_cache')
        os.makedirs(cache_dir, exist_ok=True)
        cached_path = os.path.join(cache_dir, f'{url_hash}.pdf')
        if not os.path.exists(cached_path):
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(file_path)
                    resp.raise_for_status()
                    with open(cached_path, 'wb') as f:
                        f.write(resp.content)
                logger.info(f"Downloaded PDF to cache: {cached_path}")
            except Exception as e:
                logger.warning(f"Failed to download PDF from {file_path}: {e}")
                return None
        actual_path = cached_path

    try:
        # Try using pdf2image first (higher quality)
        if PDF2IMAGE_AVAILABLE:
            images = convert_from_path(
                actual_path,
                first_page=page_number,
                last_page=page_number,
                dpi=150,
                fmt='png'
            )
            if images:
                img = images[0]

                # If highlight text provided, draw a highlight overlay
                if highlight_text and len(highlight_text) > 20:
                    try:
                        from PIL import ImageDraw, ImageFont
                        draw = ImageDraw.Draw(img, 'RGBA')
                        # Add a subtle highlight banner at the top indicating the source reference
                        banner_height = 40
                        draw.rectangle(
                            [(0, 0), (img.width, banner_height)],
                            fill=(5, 150, 105, 200)  # Emerald green semi-transparent
                        )
                        try:
                            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
                        except Exception:
                            font = ImageFont.load_default()
                        draw.text(
                            (10, 10),
                            f"Source Reference - Page {page_number}",
                            fill=(255, 255, 255, 255),
                            font=font
                        )
                    except ImportError:
                        pass  # PIL drawing not available, skip highlighting

                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format='PNG', optimize=True)
                buffer.seek(0)
                return base64.b64encode(buffer.read()).decode('utf-8')

        # Fallback: Use PyPDF2 to extract text and create a text-based image
        from PyPDF2 import PdfReader
        reader = PdfReader(actual_path)
        if page_number <= 0 or page_number > len(reader.pages):
            page_number = min(max(1, page_number), len(reader.pages))

        page = reader.pages[page_number - 1]
        page_text = page.extract_text() or "No text could be extracted from this page."

        # Create an image from the text
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create image with white background
            img_width, img_height = 800, 1100
            img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)

            # Draw header
            draw.rectangle([(0, 0), (img_width, 45)], fill=(5, 150, 105))
            try:
                font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
                font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
            except Exception:
                font_header = ImageFont.load_default()
                font_body = ImageFont.load_default()

            draw.text((10, 12), f"Source Reference - Page {page_number}", fill=(255, 255, 255), font=font_header)

            # Draw page text with word-wrapping
            y_pos = 60
            max_width = img_width - 40
            lines = page_text.split('\n')

            for line in lines:
                if y_pos > img_height - 30:
                    break
                # Simple word wrap
                words = line.split()
                current_line = ""
                for word in words:
                    test_line = current_line + " " + word if current_line else word
                    if len(test_line) * 7 < max_width:  # Approximate char width
                        current_line = test_line
                    else:
                        if current_line:
                            # Check if this text should be highlighted
                            text_color = (17, 24, 39)  # Default dark color
                            if highlight_text and len(highlight_text) > 20:
                                # Check if any portion of the clause text appears on this line
                                clause_words = set(highlight_text.lower().split()[:10])
                                line_words = set(current_line.lower().split())
                                if len(clause_words & line_words) >= 3:
                                    # Highlight this line
                                    draw.rectangle(
                                        [(15, y_pos - 2), (img_width - 15, y_pos + 16)],
                                        fill=(254, 243, 199)  # Light yellow highlight
                                    )
                                    text_color = (146, 64, 14)  # Amber text
                            draw.text((20, y_pos), current_line, fill=text_color, font=font_body)
                            y_pos += 18
                        current_line = word
                if current_line and y_pos < img_height - 30:
                    text_color = (17, 24, 39)
                    if highlight_text and len(highlight_text) > 20:
                        clause_words = set(highlight_text.lower().split()[:10])
                        line_words = set(current_line.lower().split())
                        if len(clause_words & line_words) >= 3:
                            draw.rectangle(
                                [(15, y_pos - 2), (img_width - 15, y_pos + 16)],
                                fill=(254, 243, 199)
                            )
                            text_color = (146, 64, 14)
                    draw.text((20, y_pos), current_line, fill=text_color, font=font_body)
                    y_pos += 18
                y_pos += 4  # Extra spacing between paragraphs

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode('utf-8')
        except ImportError:
            logger.warning("PIL not available for image rendering")
            return None

    except Exception as e:
        logger.error(f"Error rendering PDF page: {str(e)}", exc_info=True)
        return None


@api_router.post("/gap-analysis/regulation-first")
async def run_regulation_first_analysis(
    policy_id: str,
    regulation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Regulation-First Gap Analysis: Regulations are the absolute Source of Truth.
    
    Philosophy:
    - Each REGULATION clause is iterated and checked against policies
    - For each regulation, we find matching policy clauses via multi-level matching
    - LLM checks if policy clauses fulfill compliance_indicators
    - Tasks are auto-assigned to department members based on subject_category
    
    Matching hierarchy:
    1. Tag matching (most specific)
    2. Keyword matching
    3. Subject category matching
    4. LLM semantic matching (fallback)
    """
    try:
        policy = await db.policies.find_one({"id": policy_id, "user_id": current_user['user_id']}, {"_id": 0})
        regulation = await db.regulations.find_one({
            "id": regulation_id,
            "$or": [{"user_id": current_user['user_id']}, {"user_id": "system"}]
        }, {"_id": 0})

        # Feature #219: If not found in regulations, check NPCI circulars
        if not regulation and regulation_id.startswith("npci_"):
            npci_id_str = regulation_id.replace("npci_", "")
            try:
                npci_id_int = int(npci_id_str)
                npci_circ = await db.npci_circulars.find_one({"npci_id": npci_id_int}, {"_id": 0})
            except (ValueError, TypeError):
                npci_circ = None
            if npci_circ:
                regulation = _npci_circular_to_regulation(npci_circ)

        if not policy or not regulation:
            raise HTTPException(status_code=404, detail="Policy or regulation not found")

        policy_clauses = policy.get('clauses', [])
        regulation_clauses = regulation.get('clauses', [])

        logger.info(f"Starting REGULATION-FIRST gap analysis")
        logger.info(f"Regulation (Source of Truth): {regulation.get('title')} ({len(regulation_clauses)} clauses)")
        logger.info(f"Policy: {policy.get('title')} ({len(policy_clauses)} clauses)")
        
        # Use Regulation-First Gap Analysis Service
        gap_report = await regulation_first_gap_service.analyze(
            policy_clauses=policy_clauses,
            regulation_clauses=regulation_clauses,
            policy_id=policy_id,
            policy_title=policy.get('title', 'Untitled Policy'),
            regulation_id=regulation_id,
            regulation_title=regulation.get('title', 'Untitled Regulation')
        )
        
        # Convert report to dict for storage and response
        report_dict = regulation_gap_report_to_dict(gap_report)
        
        # Store the analysis result
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        analysis_record = {
            "id": gap_report.report_id,
            "policy_id": policy_id,
            "regulation_id": regulation_id,
            "user_id": current_user['user_id'],
            "organization": user_doc.get('organization', 'Default'),
            "analysis_type": "regulation_first",
            "compliance_score": gap_report.compliance_score,
            "total_regulation_clauses": gap_report.total_regulation_clauses,
            "total_policy_clauses": gap_report.total_policy_clauses,
            "fully_covered_count": gap_report.fully_covered_count,
            "partially_covered_count": gap_report.partially_covered_count,
            "not_covered_count": gap_report.not_covered_count,
            "critical_gaps": gap_report.critical_gaps,
            "high_gaps": gap_report.high_gaps,
            "medium_gaps": gap_report.medium_gaps,
            "low_gaps": gap_report.low_gaps,
            "executive_summary": gap_report.executive_summary,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "report": report_dict
        }
        
        await db.gap_analyses.insert_one(analysis_record)
        
        # Create tasks from priority actions
        tasks_created = 0
        for action in gap_report.priority_actions[:10]:  # Top 10 priority actions
            task = Task(
                title=f"[{action.severity}] {action.regulation_title[:50]}",
                description=action.action_description,
                priority=SeverityLevel(action.severity.lower()) if action.severity.lower() in ['critical', 'high', 'medium', 'low'] else SeverityLevel.MEDIUM,
                department=action.assigned_department,
                policy_id=policy_id,
                user_id=current_user['user_id'],
                organization=user_doc.get('organization', 'Default'),
                auto_assigned=True,
                assigned_to=action.assigned_member_name or None,
                metadata={
                    "regulation_clause_id": action.regulation_clause_id,
                    "gap_type": action.gap_type,
                    "unfulfilled_indicators": action.unfulfilled_indicators,
                    "deadline": action.deadline,
                    "priority_rank": action.priority_rank,
                    "assigned_member_id": action.assigned_member_id
                }
            )
            task_dict = task.model_dump()
            task_dict['created_at'] = task_dict['created_at'].isoformat()
            task_dict['updated_at'] = task_dict['updated_at'].isoformat()
            if task_dict.get('due_date'):
                task_dict['due_date'] = task_dict['due_date'].isoformat()
            await db.tasks.insert_one(task_dict)
            tasks_created += 1
        
        return {
            "message": "Regulation-First gap analysis completed",
            "report_id": gap_report.report_id,
            "compliance_score": gap_report.compliance_score,
            "total_regulation_clauses": gap_report.total_regulation_clauses,
            "total_policy_clauses": gap_report.total_policy_clauses,
            "coverage": {
                "fully_covered": gap_report.fully_covered_count,
                "partially_covered": gap_report.partially_covered_count,
                "not_covered": gap_report.not_covered_count
            },
            "gaps_by_severity": {
                "critical": gap_report.critical_gaps,
                "high": gap_report.high_gaps,
                "medium": gap_report.medium_gaps,
                "low": gap_report.low_gaps
            },
            "executive_summary": gap_report.executive_summary,
            "priority_actions": report_dict['priority_actions'][:15],
            "gap_results": report_dict['gap_results'][:30],
            "policy_only_clauses_count": report_dict['policy_only_clauses_count'],
            "tasks_created": tasks_created
        }
    except Exception as e:
        logger.error(f"Error in regulation-first gap analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ========== GAP ANALYSIS EXPORT ENDPOINT (Feature #42) ==========
@api_router.get("/gap-analysis/{analysis_id}/export")
async def export_gap_analysis(
    analysis_id: str,
    format: str = "json",
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #42: Export gap analysis report in PDF, Excel, or JSON formats.
    Supports: json, excel, pdf
    """
    try:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')
        role = user_doc.get('role', 'user')

        # Build query - compliance_head and auditor see all org analyses
        if role in ['compliance_head', 'auditor']:
            query = {"id": analysis_id, "organization": organization}
        else:
            query = {"id": analysis_id, "user_id": current_user['user_id']}

        analysis = await db.gap_analyses.find_one(query, {"_id": 0})
        if not analysis:
            raise HTTPException(status_code=404, detail="Gap analysis not found")

        gaps = analysis.get('gaps', [])
        # Enrich titles from actual policy/regulation documents for accuracy
        policy_doc = await db.policies.find_one({"id": analysis.get("policy_id")}, {"_id": 0, "title": 1})
        regulation_doc = await db.regulations.find_one({"id": analysis.get("regulation_id")}, {"_id": 0, "title": 1})
        policy_title = (policy_doc.get("title") if policy_doc else None) or analysis.get('policy_title', analysis.get('policy_name', 'Unknown Policy'))
        regulation_title = (regulation_doc.get("title") if regulation_doc else None) or analysis.get('regulation_title', analysis.get('regulation_name', 'Unknown Regulation'))
        compliance_score = analysis.get('compliance_score', 0)
        created_at = analysis.get('created_at', '')
        executive_summary = analysis.get('executive_summary', '')

        if format == "json":
            # Calculate severity counts from gaps for accuracy
            critical_count = sum(1 for g in gaps if g.get('severity') == 'Critical')
            high_count = sum(1 for g in gaps if g.get('severity') == 'High')
            medium_count = sum(1 for g in gaps if g.get('severity') == 'Medium')
            low_count = sum(1 for g in gaps if g.get('severity') == 'Low')

            # Return JSON with ALL fields for round-trip data integrity
            export_data = {
                "id": analysis_id,
                "policy_id": analysis.get('policy_id', ''),
                "regulation_id": analysis.get('regulation_id', ''),
                "policy": policy_title,
                "policy_title": policy_title,
                "regulation": regulation_title,
                "regulation_title": regulation_title,
                "compliance_score": compliance_score,
                "analysis_mode": analysis.get('analysis_mode', 'deep_analysis'),
                "executive_summary": executive_summary,
                "total_gaps": len(gaps),
                "critical_gaps": critical_count,
                "high_gaps": high_count,
                "medium_gaps": medium_count,
                "low_gaps": low_count,
                "compliant_clauses": analysis.get('compliant_clauses', 0),
                "priority_actions": analysis.get('priority_actions', []),
                "gaps": gaps,
                "checklist": analysis.get('checklist', []),
                "created_at": str(created_at),
                "exported_at": datetime.now(timezone.utc).isoformat()
            }
            json_bytes = json.dumps(export_data, indent=2, default=str).encode('utf-8')
            filename = f"gap_analysis_{analysis_id[:8]}_{datetime.now().strftime('%Y%m%d')}.json"
            return StreamingResponse(
                iter([json_bytes]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        elif format == "excel":
            import io
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            except ImportError:
                raise HTTPException(status_code=500, detail="openpyxl not installed")

            wb = openpyxl.Workbook()

            # Summary sheet
            ws_summary = wb.active
            ws_summary.title = "Summary"
            header_font = Font(bold=True, size=14, color="047857")
            subheader_font = Font(bold=True, size=11)
            emerald_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
            white_font = Font(bold=True, color="FFFFFF", size=11)

            ws_summary.append(["Gap Analysis Report"])
            ws_summary['A1'].font = header_font
            ws_summary.append([])
            ws_summary.append(["Policy:", policy_title])
            ws_summary.append(["Regulation:", regulation_title])
            ws_summary.append(["Compliance Score:", f"{compliance_score:.1f}%"])
            ws_summary.append(["Date:", str(created_at)[:19]])
            ws_summary.append([])
            ws_summary.append(["Gap Summary"])
            ws_summary['A8'].font = subheader_font
            ws_summary.append(["Critical Gaps:", analysis.get('critical_gaps', 0)])
            ws_summary.append(["High Gaps:", analysis.get('high_gaps', 0)])
            ws_summary.append(["Medium Gaps:", analysis.get('medium_gaps', 0)])
            ws_summary.append(["Low Gaps:", analysis.get('low_gaps', 0)])
            ws_summary.append(["Total Gaps:", len(gaps)])
            ws_summary.append([])
            ws_summary.append(["Executive Summary"])
            ws_summary['A15'].font = subheader_font
            ws_summary.append([executive_summary])

            ws_summary.column_dimensions['A'].width = 20
            ws_summary.column_dimensions['B'].width = 80

            # Gaps detail sheet
            ws_gaps = wb.create_sheet("Gaps Detail")
            gap_headers = ["#", "Type", "Severity", "Confidence", "Description", "Suggested Fix",
                          "Policy Clause", "Regulation Clause", "Department", "Deadline"]
            for col_idx, header in enumerate(gap_headers, 1):
                cell = ws_gaps.cell(row=1, column=col_idx, value=header)
                cell.font = white_font
                cell.fill = emerald_fill
                cell.alignment = Alignment(horizontal="center")

            for row_idx, gap in enumerate(gaps, 2):
                ws_gaps.cell(row=row_idx, column=1, value=row_idx - 1)
                ws_gaps.cell(row=row_idx, column=2, value=gap.get('gap_type', ''))
                ws_gaps.cell(row=row_idx, column=3, value=gap.get('severity', ''))
                ws_gaps.cell(row=row_idx, column=4, value=f"{(gap.get('confidence_score', 0) * 100):.0f}%")
                ws_gaps.cell(row=row_idx, column=5, value=gap.get('description', gap.get('gap_description', '')))
                ws_gaps.cell(row=row_idx, column=6, value=gap.get('suggested_fix', ''))
                policy_clause = gap.get('policy_clause', {}) or {}
                ws_gaps.cell(row=row_idx, column=7, value=policy_clause.get('text', policy_clause.get('title', 'N/A'))[:500])
                reg_clause = gap.get('regulation_clause', {}) or {}
                ws_gaps.cell(row=row_idx, column=8, value=reg_clause.get('text', reg_clause.get('title', 'N/A'))[:500])
                metadata = gap.get('metadata', {}) or {}
                ws_gaps.cell(row=row_idx, column=9, value=metadata.get('assigned_department', ''))
                ws_gaps.cell(row=row_idx, column=10, value=metadata.get('deadline', ''))

                # Color severity cells
                severity_colors = {
                    "Critical": "FFCCCC", "High": "FFE0B2",
                    "Medium": "BBDEFB", "Low": "C8E6C9"
                }
                sev = gap.get('severity', '')
                if sev in severity_colors:
                    ws_gaps.cell(row=row_idx, column=3).fill = PatternFill(
                        start_color=severity_colors[sev], end_color=severity_colors[sev], fill_type="solid"
                    )

            for col in range(1, 11):
                ws_gaps.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 25

            # Priority Actions sheet
            ws_actions = wb.create_sheet("Priority Actions")
            ws_actions.cell(row=1, column=1, value="#").font = white_font
            ws_actions.cell(row=1, column=1).fill = emerald_fill
            ws_actions.cell(row=1, column=2, value="Action").font = white_font
            ws_actions.cell(row=1, column=2).fill = emerald_fill
            for idx, action in enumerate(analysis.get('priority_actions', []), 2):
                ws_actions.cell(row=idx, column=1, value=idx - 1)
                ws_actions.cell(row=idx, column=2, value=action)
            ws_actions.column_dimensions['A'].width = 5
            ws_actions.column_dimensions['B'].width = 100

            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            filename = f"gap_analysis_{analysis_id[:8]}_{datetime.now().strftime('%Y%m%d')}.xlsx"
            return StreamingResponse(
                iter([buffer.getvalue()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        elif format == "pdf":
            import io
            try:
                from fpdf import FPDF
            except ImportError:
                raise HTTPException(status_code=500, detail="fpdf2 not installed")

            def _clean(text):
                if not text:
                    return ""
                return text.encode('latin-1', 'replace').decode('latin-1')

            W = 190

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            pdf.set_font('Helvetica', 'B', 18)
            pdf.set_text_color(4, 120, 87)
            pdf.cell(W, 12, 'Gap Analysis Report', ln=True, align='C')
            pdf.ln(5)

            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(W, 6, _clean(f'Policy: {policy_title}'), ln=True)
            pdf.cell(W, 6, _clean(f'Regulation: {regulation_title}'), ln=True)
            pdf.cell(W, 6, f'Compliance Score: {compliance_score:.1f}%', ln=True)
            pdf.cell(W, 6, f'Date: {str(created_at)[:19]}', ln=True)
            pdf.ln(5)

            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(4, 120, 87)
            pdf.cell(W, 8, 'Gap Summary', ln=True)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(W, 6, f'Critical: {analysis.get("critical_gaps", 0)} | High: {analysis.get("high_gaps", 0)} | Medium: {analysis.get("medium_gaps", 0)} | Low: {analysis.get("low_gaps", 0)} | Total: {len(gaps)}', ln=True)
            pdf.ln(5)

            if executive_summary:
                pdf.set_font('Helvetica', 'B', 12)
                pdf.set_text_color(4, 120, 87)
                pdf.cell(W, 8, 'Executive Summary', ln=True)
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(0, 0, 0)
                pdf.set_x(10)
                pdf.multi_cell(W, 5, _clean(executive_summary[:2000]))
                pdf.ln(5)

            priority_actions = analysis.get('priority_actions', [])
            if priority_actions:
                pdf.set_font('Helvetica', 'B', 12)
                pdf.set_text_color(4, 120, 87)
                pdf.cell(W, 8, 'Priority Actions', ln=True)
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(0, 0, 0)
                for i, action in enumerate(priority_actions[:10], 1):
                    pdf.set_x(10)
                    pdf.multi_cell(W, 5, _clean(f'{i}. {action}'))
                pdf.ln(5)

            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(4, 120, 87)
            pdf.cell(W, 8, 'Gap Details', ln=True)
            pdf.ln(3)

            for i, gap in enumerate(gaps, 1):
                if pdf.get_y() > 250:
                    pdf.add_page()

                severity = gap.get('severity', 'Unknown')
                gap_type = gap.get('gap_type', 'unknown')
                confidence = gap.get('confidence_score', 0)

                pdf.set_font('Helvetica', 'B', 10)
                severity_colors_pdf = {
                    "Critical": (239, 68, 68), "High": (245, 158, 11),
                    "Medium": (59, 130, 246), "Low": (16, 185, 129)
                }
                r, g, b = severity_colors_pdf.get(severity, (0, 0, 0))
                pdf.set_text_color(r, g, b)
                pdf.cell(W, 6, _clean(f'Gap #{i} - {gap_type.title()} ({severity}) - Confidence: {confidence*100:.0f}%'), ln=True)

                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(0, 0, 0)
                desc = gap.get('description', gap.get('gap_description', 'No description'))
                pdf.set_x(10)
                pdf.multi_cell(W, 4, _clean(f'Description: {desc[:500]}'))

                fix = gap.get('suggested_fix', '')
                if fix:
                    pdf.set_font('Helvetica', 'I', 9)
                    pdf.set_x(10)
                    pdf.multi_cell(W, 4, _clean(f'Fix: {fix[:300]}'))

                pdf.ln(3)

            buffer = io.BytesIO()
            pdf.output(buffer)
            buffer.seek(0)
            filename = f"gap_analysis_{analysis_id[:8]}_{datetime.now().strftime('%Y%m%d')}.pdf"
            return StreamingResponse(
                iter([buffer.getvalue()]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use json, excel, or pdf.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting gap analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ========== CHECKLIST ENDPOINTS ==========
@api_router.post("/checklists/generate")
async def generate_checklist_from_gap_analysis(
    request: ChecklistCreate,
    current_user: dict = Depends(check_not_auditor)
):
    """Generate a compliance checklist from a gap analysis. Auditors cannot create."""
    try:
        # Get user's organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Get the gap analysis
        gap_analysis = await db.gap_analyses.find_one(
            {"id": request.gap_analysis_id, "organization": organization},
            {"_id": 0}
        )

        if not gap_analysis:
            raise HTTPException(status_code=404, detail="Gap analysis not found")

        # Build checklist items from gaps
        items = []
        for gap in gap_analysis.get('gaps', []):
            item = ChecklistItem(
                text=gap.get('description', 'Address compliance gap'),
                description=gap.get('suggested_fix', ''),
                gap_id=gap.get('gap_id'),
                severity=SeverityLevel[gap.get('severity', 'MEDIUM').upper()],
                completed=False
            )
            items.append(item)

        # Create checklist
        title = request.title or f"Checklist for {gap_analysis.get('policy_name', '')} vs {gap_analysis.get('regulation_name', '')}"
        checklist = Checklist(
            title=title,
            description=request.description,
            gap_analysis_id=request.gap_analysis_id,
            policy_id=gap_analysis.get('policy_id'),
            regulation_id=gap_analysis.get('regulation_id'),
            items=items,
            user_id=current_user['user_id'],
            organization=organization
        )

        # Save to database
        checklist_dict = checklist.model_dump()
        checklist_dict['created_at'] = checklist_dict['created_at'].isoformat()
        checklist_dict['updated_at'] = checklist_dict['updated_at'].isoformat()

        # Convert item timestamps
        for item in checklist_dict['items']:
            if item.get('completed_at'):
                item['completed_at'] = item['completed_at'].isoformat()

        await db.checklists.insert_one(checklist_dict)

        logger.info(f"[CHECKLIST] Created checklist {checklist.id} with {len(items)} items")
        return checklist.model_dump()

    except Exception as e:
        logger.error(f"Failed to generate checklist: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/checklists")
async def get_checklists(current_user: dict = Depends(get_current_user)):
    """Get all checklists for the current user's organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')
    role = user_doc.get('role', 'user')

    # Build query filter
    if role == 'compliance_head':
        # Compliance heads see all org checklists
        filter_query = {"organization": organization}
    else:
        # Regular users see only their own
        filter_query = {"organization": organization, "user_id": current_user['user_id']}

    checklists = await db.checklists.find(filter_query, {"_id": 0}).to_list(1000)
    return checklists


@api_router.get("/checklists/{checklist_id}")
async def get_checklist(
    checklist_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific checklist by ID."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    checklist = await db.checklists.find_one(
        {"id": checklist_id, "organization": organization},
        {"_id": 0}
    )

    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    return checklist


@api_router.put("/checklists/{checklist_id}/items/{item_id}")
async def update_checklist_item(
    checklist_id: str,
    item_id: str,
    update: ChecklistItemUpdate,
    current_user: dict = Depends(check_not_auditor)
):
    """Update a checklist item's completion status. Auditors cannot update."""
    try:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

        # Get the checklist
        checklist = await db.checklists.find_one(
            {"id": checklist_id, "organization": organization},
            {"_id": 0}
        )

        if not checklist:
            raise HTTPException(status_code=404, detail="Checklist not found")

        # Find and update the item
        items = checklist.get('items', [])
        item_found = False

        for item in items:
            if item['id'] == item_id:
                item['completed'] = update.completed
                if update.completed:
                    item['completed_at'] = datetime.now(timezone.utc).isoformat()
                    item['completed_by'] = current_user['user_id']
                else:
                    item['completed_at'] = None
                    item['completed_by'] = None

                if update.notes is not None:
                    item['notes'] = update.notes

                if update.evidence_ids is not None:
                    item['evidence_ids'] = update.evidence_ids

                item_found = True
                break

        if not item_found:
            raise HTTPException(status_code=404, detail="Checklist item not found")

        # Update the checklist
        await db.checklists.update_one(
            {"id": checklist_id},
            {
                "$set": {
                    "items": items,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )

        logger.info(f"[CHECKLIST] Updated item {item_id} in checklist {checklist_id}")

        # Return updated checklist
        updated_checklist = await db.checklists.find_one(
            {"id": checklist_id, "organization": organization},
            {"_id": 0}
        )
        return updated_checklist

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update checklist item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/checklists/{checklist_id}")
async def delete_checklist(
    checklist_id: str,
    current_user: dict = Depends(check_not_auditor)
):
    """Delete a checklist. Auditors cannot delete."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    result = await db.checklists.delete_one(
        {"id": checklist_id, "organization": organization}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Checklist not found")

    logger.info(f"[CHECKLIST] Deleted checklist {checklist_id}")
    return {"message": "Checklist deleted successfully"}


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

        # Read file content
        file_content = await file.read()

        # Enforce file size limit (50MB)
        MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
        file_size_check = len(file_content)
        if file_size_check > MAX_FILE_SIZE_BYTES:
            file_size_mb = round(file_size_check / (1024 * 1024), 1)
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({file_size_mb}MB). Maximum file size is 50MB. Please reduce the file size and try again."
            )

        # Feature #54: Compute SHA-256 hash
        sha256_hash = evidence_service.compute_sha256(file_content)
        logger.info(f"Computed SHA-256 hash for {file.filename}: {sha256_hash[:16]}...")

        # Save file
        file_path = await doc_service.save_file(file_content, file.filename)
        file_size = len(file_content)

        # Determine MIME type
        mime_type = file.content_type or 'application/octet-stream'

        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})

        # Feature #54: Run OCR and field extraction
        logger.info(f"Starting OCR and field extraction for {file.filename}")
        ocr_result = await evidence_service.extract_fields_with_ocr(file_path, file_content, mime_type)
        logger.info(f"OCR complete. Extracted {len(ocr_result.get('ocr_text', ''))} characters")

        evidence = Evidence(
            title=ev_info.get('title', file.filename),
            description=ev_info.get('description'),
            file_url=file_path,
            file_name=file.filename,
            file_type=mime_type,
            file_size=file_size,
            sha256_hash=sha256_hash,
            ocr_text=ocr_result.get('ocr_text', ''),
            extracted_fields=ocr_result.get('extracted_fields', {}),
            policy_id=ev_info.get('policy_id'),
            clause_id=ev_info.get('clause_id'),
            control_id=ev_info.get('control_id'),
            task_id=ev_info.get('task_id'),
            user_id=current_user['user_id'],
            organization=user_doc.get('organization', 'Default')
        )

        ev_dict = evidence.model_dump()
        ev_dict['created_at'] = ev_dict['created_at'].isoformat()

        await db.evidence.insert_one(ev_dict)

        logger.info(f"Evidence uploaded successfully: {evidence.id}")

        return {
            "message": "Evidence uploaded successfully",
            "evidence_id": evidence.id,
            "sha256_hash": sha256_hash,
            "ocr_complete": bool(ocr_result.get('ocr_text')),
            "fields_extracted": ocr_result.get('extracted_fields', {})
        }
    except HTTPException:
        raise
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

@api_router.get("/evidence/{evidence_id}")
async def get_evidence_detail(evidence_id: str, current_user: dict = Depends(get_current_user)):
    evidence = await db.evidence.find_one({"id": evidence_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if isinstance(evidence.get('created_at'), str):
        evidence['created_at'] = datetime.fromisoformat(evidence['created_at'])
    return evidence

@api_router.get("/evidence/{evidence_id}/audit-log")
async def get_evidence_audit_log(evidence_id: str, current_user: dict = Depends(get_current_user)):
    evidence = await db.evidence.find_one({"id": evidence_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    audit_log = evidence.get('audit_log', [])
    return audit_log

@api_router.post("/evidence/{evidence_id}/validate")
async def validate_evidence(
    evidence_id: str,
    requirement: Optional[str] = Body(None, embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Feature #55: AI validation of evidence with confidence-based routing."""
    try:
        evidence = await db.evidence.find_one({"id": evidence_id, "user_id": current_user['user_id']}, {"_id": 0})
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")

        # Run AI validation with confidence scoring
        logger.info(f"Validating evidence {evidence_id} with AI")
        validation_result = await evidence_service.validate_evidence_with_confidence(
            evidence,
            requirement
        )

        validation_status = validation_result['validation_status']
        confidence = validation_result['confidence']
        ai_score = validation_result['ai_score']
        explanation = validation_result['explanation']
        audit_notes = validation_result.get('audit_notes', '')  # Feature #172

        # Determine display status
        if validation_status == 'auto_approved':
            status = "Approved"
        elif validation_status == 'pending_human_review':
            status = "Pending Review"
        else:
            status = "Failed"

        # Create audit log entry
        audit_entry = {
            "action": "ai_validated",
            "user_id": current_user['user_id'],
            "user_name": current_user.get('full_name', 'System'),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": f"AI validation: confidence={confidence:.2f}, status={validation_status}, score={ai_score}"
        }

        # Update evidence with validation results
        await db.evidence.update_one(
            {"id": evidence_id},
            {"$set": {
                "validation_status": validation_status,
                "status": status,
                "ai_confidence": round(confidence, 3),
                "ai_compliance_score": ai_score,
                "ai_explanation": explanation,
                "ai_audit_notes": audit_notes,  # Feature #172
                "feedback_good": validation_result.get('strengths', []),
                "feedback_improvements": validation_result.get('weaknesses', [])
            },
            "$push": {"audit_log": audit_entry}}
        )

        logger.info(f"Validation complete: {validation_status} (confidence: {confidence:.2f})")

        return {
            "validation_status": validation_status,
            "confidence": round(confidence, 3),
            "status": status,
            "ai_score": ai_score,
            "explanation": explanation,
            "audit_notes": audit_notes,  # Feature #172
            "strengths": validation_result.get('strengths', []),
            "weaknesses": validation_result.get('weaknesses', [])
        }

    except Exception as e:
        logger.error(f"Error in validate_evidence: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@api_router.post("/evidence/{evidence_id}/approve")
async def approve_evidence(evidence_id: str, decision: dict = Body(...), current_user: dict = Depends(get_current_user)):
    evidence = await db.evidence.find_one({"id": evidence_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    approved = decision.get('approved', True)
    reason = decision.get('reason', '')
    new_status = "Approved" if approved else "Rejected"
    
    audit_entry = {
        "action": "human_review",
        "user_id": current_user['user_id'],
        "user_name": current_user.get('full_name', 'Reviewer'),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": f"{'Approved' if approved else 'Rejected'}: {reason}"
    }
    
    await db.evidence.update_one(
        {"id": evidence_id},
        {"$set": {"status": new_status, "validation_status": "human_approved" if approved else "human_rejected"},
         "$push": {"audit_log": audit_entry}}
    )
    
    return {"message": f"Evidence {new_status.lower()}", "status": new_status}

@api_router.post("/evidence/{evidence_id}/override")
async def override_evidence(evidence_id: str, override_data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Human override of AI validation result."""
    evidence = await db.evidence.find_one({"id": evidence_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    reason = override_data.get('reason', 'Manual override')

    audit_entry = {
        "action": "human_override",
        "user_id": current_user['user_id'],
        "user_name": current_user.get('full_name', 'Reviewer'),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": f"Override reason: {reason}"
    }

    await db.evidence.update_one(
        {"id": evidence_id},
        {"$set": {"status": "Approved", "validation_status": "human_override"},
         "$push": {"audit_log": audit_entry}}
    )

    return {"message": "Evidence overridden to approved", "status": "Approved"}

@api_router.post("/evidence/{evidence_id}/correct-validation")
async def correct_evidence_validation(
    evidence_id: str,
    correction_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #197: Human-in-the-loop correction of AI validation results.
    Allows correcting validation status, score, and explanation with full audit trail.
    """
    evidence = await db.evidence.find_one({"id": evidence_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    # Extract correction fields
    corrected_status = correction_data.get('corrected_status')  # e.g., "Approved", "Rejected", "Needs Review"
    corrected_score = correction_data.get('corrected_score')  # 0-100
    corrected_explanation = correction_data.get('corrected_explanation', '')
    correction_reason = correction_data.get('reason', '')

    if not correction_reason or len(correction_reason.strip()) < 10:
        raise HTTPException(status_code=400, detail="Correction reason must be at least 10 characters")

    # Capture original values for audit trail
    original_validation = {
        "status": evidence.get('status', 'Unknown'),
        "validation_status": evidence.get('validation_status', 'Unknown'),
        "ai_compliance_score": evidence.get('ai_compliance_score', 0),
        "ai_explanation": evidence.get('ai_explanation', ''),
        "ai_confidence": evidence.get('ai_confidence', 0)
    }

    # Create comprehensive audit log entry
    audit_entry = {
        "action": "validation_corrected",
        "user_id": current_user['user_id'],
        "user_name": current_user.get('full_name', 'Reviewer'),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correction_reason": correction_reason,
        "original_values": original_validation,
        "corrected_values": {
            "status": corrected_status,
            "validation_status": "human_corrected",
            "corrected_score": corrected_score,
            "corrected_explanation": corrected_explanation
        },
        "details": f"Validation corrected by {current_user.get('full_name', 'User')}: {correction_reason}"
    }

    # Prepare update fields
    update_fields = {
        "status": corrected_status,
        "validation_status": "human_corrected",
        "human_corrected_at": datetime.now(timezone.utc).isoformat(),
        "human_corrected_by": current_user['user_id'],
        "human_corrected_by_name": current_user.get('full_name', 'Reviewer'),
        "correction_reason": correction_reason
    }

    if corrected_score is not None:
        update_fields["corrected_score"] = int(corrected_score)

    if corrected_explanation:
        update_fields["corrected_explanation"] = corrected_explanation

    # Update evidence with correction
    await db.evidence.update_one(
        {"id": evidence_id},
        {
            "$set": update_fields,
            "$push": {"audit_log": audit_entry}
        }
    )

    logger.info(f"Evidence {evidence_id} validation corrected by {current_user.get('full_name', 'User')}")

    return {
        "message": "Validation correction applied successfully",
        "status": corrected_status,
        "audit_entry": audit_entry
    }

# ========== EVIDENCE TEMPLATE ENDPOINTS (Feature #61) ==========
@api_router.get("/evidence-templates", response_model=List[EvidenceTemplate])
async def get_evidence_templates(current_user: dict = Depends(get_current_user)):
    """Get all evidence templates for the user's organization."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    templates = await db.evidence_templates.find(
        {"organization": organization},
        {"_id": 0}
    ).to_list(1000)

    for template in templates:
        if isinstance(template.get('created_at'), str):
            template['created_at'] = datetime.fromisoformat(template['created_at'])
        if isinstance(template.get('updated_at'), str):
            template['updated_at'] = datetime.fromisoformat(template['updated_at'])

    return templates


@api_router.get("/evidence-templates/{template_id}", response_model=EvidenceTemplate)
async def get_evidence_template(template_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific evidence template by ID."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    template = await db.evidence_templates.find_one(
        {"id": template_id, "organization": organization},
        {"_id": 0}
    )

    if not template:
        raise HTTPException(status_code=404, detail="Evidence template not found")

    if isinstance(template.get('created_at'), str):
        template['created_at'] = datetime.fromisoformat(template['created_at'])
    if isinstance(template.get('updated_at'), str):
        template['updated_at'] = datetime.fromisoformat(template['updated_at'])

    return template


@api_router.post("/evidence-templates", response_model=EvidenceTemplate)
async def create_evidence_template(
    template_data: EvidenceTemplateCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new evidence template."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    template = EvidenceTemplate(
        template_name=template_data.template_name,
        regulation_type=template_data.regulation_type,
        description=template_data.description,
        required_documents=template_data.required_documents,
        required_fields=template_data.required_fields,
        validation_criteria=template_data.validation_criteria,
        minimum_score=template_data.minimum_score,
        auto_approve_threshold=template_data.auto_approve_threshold,
        organization=organization,
        created_by=current_user['user_id']
    )

    template_dict = template.model_dump()
    template_dict['created_at'] = template_dict['created_at'].isoformat()
    template_dict['updated_at'] = template_dict['updated_at'].isoformat()

    await db.evidence_templates.insert_one(template_dict)

    logger.info(f"Evidence template created: {template.id} by {current_user['user_id']}")

    return template


@api_router.put("/evidence-templates/{template_id}", response_model=EvidenceTemplate)
async def update_evidence_template(
    template_id: str,
    template_data: EvidenceTemplateUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing evidence template."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    # Check template exists and belongs to organization
    existing = await db.evidence_templates.find_one(
        {"id": template_id, "organization": organization},
        {"_id": 0}
    )

    if not existing:
        raise HTTPException(status_code=404, detail="Evidence template not found")

    # Build update document
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if template_data.template_name is not None:
        update_fields["template_name"] = template_data.template_name
    if template_data.description is not None:
        update_fields["description"] = template_data.description
    if template_data.required_documents is not None:
        update_fields["required_documents"] = template_data.required_documents
    if template_data.required_fields is not None:
        update_fields["required_fields"] = template_data.required_fields
    if template_data.validation_criteria is not None:
        update_fields["validation_criteria"] = template_data.validation_criteria
    if template_data.minimum_score is not None:
        update_fields["minimum_score"] = template_data.minimum_score
    if template_data.auto_approve_threshold is not None:
        update_fields["auto_approve_threshold"] = template_data.auto_approve_threshold

    await db.evidence_templates.update_one(
        {"id": template_id},
        {"$set": update_fields}
    )

    # Fetch and return updated template
    updated_template = await db.evidence_templates.find_one(
        {"id": template_id},
        {"_id": 0}
    )

    if isinstance(updated_template.get('created_at'), str):
        updated_template['created_at'] = datetime.fromisoformat(updated_template['created_at'])
    if isinstance(updated_template.get('updated_at'), str):
        updated_template['updated_at'] = datetime.fromisoformat(updated_template['updated_at'])

    logger.info(f"Evidence template updated: {template_id} by {current_user['user_id']}")

    return updated_template


@api_router.delete("/evidence-templates/{template_id}")
async def delete_evidence_template(template_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an evidence template."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    # Check template exists and belongs to organization
    existing = await db.evidence_templates.find_one(
        {"id": template_id, "organization": organization},
        {"_id": 0}
    )

    if not existing:
        raise HTTPException(status_code=404, detail="Evidence template not found")

    await db.evidence_templates.delete_one({"id": template_id})

    logger.info(f"Evidence template deleted: {template_id} by {current_user['user_id']}")

    return {"message": "Evidence template deleted successfully"}


# ========== EVIDENCE FILE ACCESS WITH SHA-256 VERIFICATION (Feature #58) ==========
@api_router.get("/evidence/{evidence_id}/file")
async def download_evidence_file(evidence_id: str, current_user: dict = Depends(get_current_user)):
    """
    Download evidence file with SHA-256 integrity verification.
    Returns file with warning if hash mismatch detected.
    """
    from fastapi.responses import FileResponse
    import os

    # Get evidence document
    evidence = await db.evidence.find_one(
        {"id": evidence_id, "user_id": current_user['user_id']},
        {"_id": 0}
    )

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    file_path = evidence.get('file_url')
    stored_hash = evidence.get('sha256_hash')

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Physical file not found")

    # Feature #58: Verify SHA-256 hash integrity
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Compute current hash
        current_hash = evidence_service.compute_sha256(file_content)

        # Compare hashes
        if stored_hash and current_hash != stored_hash:
            # Hash mismatch - file has been tampered with or corrupted
            logger.error(f"SHA-256 hash mismatch for evidence {evidence_id}!")
            logger.error(f"  Stored:  {stored_hash}")
            logger.error(f"  Current: {current_hash}")

            # Log to audit trail
            audit_entry = {
                "action": "file_integrity_check_failed",
                "user_id": current_user['user_id'],
                "user_name": current_user.get('full_name', 'System'),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": f"SHA-256 mismatch detected. Stored: {stored_hash[:16]}..., Current: {current_hash[:16]}..."
            }

            await db.evidence.update_one(
                {"id": evidence_id},
                {"$push": {"audit_log": audit_entry}}
            )

            raise HTTPException(
                status_code=409,
                detail={
                    "error": "File integrity check failed",
                    "message": "SHA-256 hash mismatch detected - file may be corrupted or tampered with",
                    "stored_hash": stored_hash,
                    "current_hash": current_hash
                }
            )

        # Hash matches or no hash stored - log successful access
        audit_entry = {
            "action": "file_accessed",
            "user_id": current_user['user_id'],
            "user_name": current_user.get('full_name', 'User'),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": f"File downloaded successfully. SHA-256 verified: {current_hash[:16]}..."
        }

        await db.evidence.update_one(
            {"id": evidence_id},
            {"$push": {"audit_log": audit_entry}}
        )

        logger.info(f"Evidence file accessed: {evidence_id}, SHA-256 verified")

        # Return file
        return FileResponse(
            path=file_path,
            filename=evidence.get('file_name', 'evidence_file'),
            media_type=evidence.get('file_type', 'application/octet-stream')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accessing evidence file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error accessing file: {str(e)}")

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

        # Get user details for task creation
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default')

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

        # Feature #94: Auto-create tasks from audit gap findings
        created_tasks = []
        for i, control_eval in enumerate(controls_evaluation):
            control = audit['controls'][i]

            # Create task for non-compliant or missing evidence controls
            should_create_task = (
                control_eval.get('status') in ['No Evidence', 'Non-Compliant', 'Partially Compliant'] or
                control_eval.get('compliance_score', 100) < 60
            )

            if should_create_task:
                import uuid
                task_id = str(uuid.uuid4())

                # Determine priority based on compliance score and status
                if control_eval.get('status') == 'No Evidence' or control_eval.get('compliance_score', 0) < 40:
                    priority = "critical"
                elif control_eval.get('compliance_score', 0) < 60:
                    priority = "high"
                else:
                    priority = "medium"

                task_data = {
                    "id": task_id,
                    "title": f"Remediate Audit Gap: {control.get('control_name', 'Control')}",
                    "description": f"Audit Finding: {control_eval.get('findings', 'Gap identified')}\n\nRecommendations: {control_eval.get('recommendations', 'Address identified gaps')}",
                    "priority": priority,
                    "status": "open",
                    "source_type": "audit_gap",
                    "source_id": audit_id,
                    "assigned_to": current_user['user_id'],
                    "assigned_by": current_user['user_id'],
                    "assignment_method": "auto",
                    "organization": organization,
                    "department_id": user_doc.get('department_id'),
                    "linked_clauses": [],
                    "linked_evidence": [],
                    "sla_deadline": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "audit_id": audit_id,
                        "audit_type": audit.get('audit_type', 'internal'),
                        "control_id": control.get('id'),
                        "control_name": control.get('control_name'),
                        "control_category": control.get('category'),
                        "compliance_score": control_eval.get('compliance_score', 0),
                        "status": control_eval.get('status'),
                        "evidence_count": len(evidence_list)
                    }
                }

                await db.tasks.insert_one(task_data)
                created_tasks.append({
                    "task_id": task_id,
                    "title": task_data["title"],
                    "priority": priority,
                    "control_name": control.get('control_name')
                })

        # Update audit session
        await db.audit_sessions.update_one(
            {"id": audit_id},
            {"$set": {
                "overall_score": report['overall_score'],
                "status": "Completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "tasks_created": len(created_tasks)
            }}
        )

        # Include created tasks in response
        report["created_tasks"] = created_tasks
        report["tasks_created_count"] = len(created_tasks)

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

@api_router.get("/audit/sessions/{audit_id}")
async def get_audit_session_detail(audit_id: str, current_user: dict = Depends(get_current_user)):
    audit = await db.audit_sessions.find_one({"id": audit_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit session not found")
    if isinstance(audit.get('created_at'), str):
        audit['created_at'] = datetime.fromisoformat(audit['created_at'])
    if audit.get('completed_at') and isinstance(audit['completed_at'], str):
        audit['completed_at'] = datetime.fromisoformat(audit['completed_at'])
    return audit

@api_router.get("/audit/{audit_id}/artefact-status")
async def get_audit_artefact_status(audit_id: str, current_user: dict = Depends(get_current_user)):
    """Get expected vs uploaded artefact status per control with Red/Amber/Green indicators."""
    audit = await db.audit_sessions.find_one({"id": audit_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit session not found")

    controls = audit.get('controls', [])
    artefact_statuses = []

    for control in controls:
        control_id = control.get('id', '')
        evidence_required = control.get('evidence_required', [])
        total_required = len(evidence_required)

        # Find uploaded evidence for this control
        evidence_list = await db.evidence.find({
            "control_id": control_id,
            "user_id": current_user['user_id']
        }, {"_id": 0}).to_list(100)

        uploaded_count = len(evidence_list)
        approved_count = sum(1 for e in evidence_list if e.get('lifecycle_status') in ['approved', 'auto_approved'])
        pending_count = sum(1 for e in evidence_list if e.get('lifecycle_status') in ['uploaded', 'ai_validated', 'pending_human_review'])
        rejected_count = sum(1 for e in evidence_list if e.get('lifecycle_status') == 'rejected')

        # Determine RAG status based on evidence completeness and approval
        compliance_score = control.get('compliance_score')
        control_status = control.get('status', 'Pending')

        if control_status in ['Compliant', 'Passed'] or (compliance_score is not None and compliance_score >= 75):
            rag_status = "green"
            rag_label = "Complete/Approved"
        elif control_status in ['Partially Compliant', 'Requires Review'] or (compliance_score is not None and compliance_score >= 50):
            rag_status = "amber"
            rag_label = "Pending/Partial"
        elif control_status in ['No Evidence', 'Non-Compliant'] or (compliance_score is not None and compliance_score < 50):
            rag_status = "red"
            rag_label = "Missing/Failed"
        elif uploaded_count == 0 and total_required > 0:
            rag_status = "red"
            rag_label = "Missing/Failed"
        elif approved_count >= total_required and total_required > 0:
            rag_status = "green"
            rag_label = "Complete/Approved"
        elif uploaded_count > 0:
            rag_status = "amber"
            rag_label = "Pending/Partial"
        else:
            rag_status = "red"
            rag_label = "Missing/Failed"

        artefact_statuses.append({
            "control_id": control_id,
            "control_name": control.get('control_name', f'Control'),
            "category": control.get('category', 'General'),
            "evidence_required": evidence_required,
            "total_required": total_required,
            "uploaded_count": uploaded_count,
            "approved_count": approved_count,
            "pending_count": pending_count,
            "rejected_count": rejected_count,
            "compliance_score": compliance_score,
            "control_status": control_status,
            "rag_status": rag_status,
            "rag_label": rag_label
        })

    # Summary counts
    green_count = sum(1 for a in artefact_statuses if a['rag_status'] == 'green')
    amber_count = sum(1 for a in artefact_statuses if a['rag_status'] == 'amber')
    red_count = sum(1 for a in artefact_statuses if a['rag_status'] == 'red')

    return {
        "audit_id": audit_id,
        "total_controls": len(controls),
        "summary": {
            "green": green_count,
            "amber": amber_count,
            "red": red_count,
        },
        "legend": {
            "green": {"label": "Complete/Approved", "description": "All required artefacts uploaded and approved. Control is fully compliant."},
            "amber": {"label": "Pending/Partial", "description": "Some artefacts uploaded but pending review, or partial compliance identified."},
            "red": {"label": "Missing/Failed", "description": "Required artefacts missing or control found non-compliant. Immediate action needed."}
        },
        "controls": artefact_statuses
    }

@api_router.post("/audit/{audit_id}/sign-off")
async def sign_off_audit(audit_id: str, sign_off_data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Complete sign-off for an audit session."""
    audit = await db.audit_sessions.find_one({"id": audit_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit session not found")
    
    await db.audit_sessions.update_one(
        {"id": audit_id},
        {"$set": {
            "signed_off": True,
            "signed_off_by": current_user.get('full_name', current_user['user_id']),
            "signed_off_at": datetime.now(timezone.utc).isoformat(),
            "sign_off_notes": sign_off_data.get('notes', ''),
            "status": "Signed Off"
        }}
    )
    
    return {"message": "Audit session signed off successfully"}

@api_router.post("/audit/{audit_id}/export")
async def export_audit_report(audit_id: str, current_user: dict = Depends(get_current_user)):
    """Generate PDF report for audit session."""
    audit = await db.audit_sessions.find_one({"id": audit_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit session not found")
    
    # Return audit data as a structured report (PDF generation would be done client-side)
    return {
        "report": {
            "audit_id": audit_id,
            "audit_type": audit.get('audit_type', 'internal'),
            "scope": audit.get('scope', ''),
            "status": audit.get('status', 'In Progress'),
            "overall_score": audit.get('overall_score', 0),
            "controls": audit.get('controls', []),
            "created_at": audit.get('created_at'),
            "completed_at": audit.get('completed_at'),
            "signed_off": audit.get('signed_off', False),
            "signed_off_by": audit.get('signed_off_by'),
            "sign_off_notes": audit.get('sign_off_notes', ''),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    }

# ========== TASK ENDPOINTS (Enhanced) ==========

@api_router.get("/tasks")
async def get_tasks(
    department: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    overdue_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get all tasks with optional filters. Compliance_head sees all org tasks, users see own/assigned."""
    # Get user details to check role
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    user_role = user_doc.get('role', 'user')
    organization = user_doc.get('organization')

    # Role-based access
    if user_role == 'compliance_head':
        # Compliance head sees all tasks in organization
        query = {"organization": organization}
    elif user_role == 'auditor':
        # Auditor sees all tasks in organization (read-only)
        query = {"organization": organization}
    else:
        # Regular user sees own tasks or tasks assigned to them
        query = {"user_id": current_user['user_id']}
    if department:
        query["department"] = department
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if assigned_to:
        query["assigned_member_id"] = assigned_to
    if overdue_only:
        query["is_overdue"] = True
    
    tasks = await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Normalize status and priority to lowercase for frontend compatibility
    for task in tasks:
        if task.get('status'):
            task['status'] = task['status'].lower().replace(' ', '_')
        if task.get('priority'):
            task['priority'] = task['priority'].lower()
    
    # Parse dates for response (handle ISO format with Z suffix)
    def parse_date(date_str):
        if not date_str:
            return None
        if isinstance(date_str, datetime):
            return date_str
        # Handle Z suffix for UTC timezone
        if date_str.endswith('Z'):
            date_str = date_str[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(date_str)
        except:
            return None
    
    # Collect department IDs to fetch department names
    dept_ids = set()
    for task in tasks:
        if isinstance(task.get('created_at'), str):
            task['created_at'] = parse_date(task['created_at'])
        if isinstance(task.get('updated_at'), str):
            task['updated_at'] = parse_date(task['updated_at'])
        if task.get('due_date') and isinstance(task['due_date'], str):
            task['due_date'] = parse_date(task['due_date'])
        if task.get('department_id'):
            dept_ids.add(task['department_id'])
        # Also check 'department' field which might store department name or id
        if task.get('department') and not task.get('department_name'):
            task['department_name'] = task.get('department')
    
    # Fetch department names for tasks with department_id
    if dept_ids:
        depts = await db.departments.find(
            {"id": {"$in": list(dept_ids)}},
            {"_id": 0, "id": 1, "name": 1}
        ).to_list(100)
        dept_map = {d["id"]: d["name"] for d in depts}
        for task in tasks:
            if task.get('department_id') and not task.get('department_name'):
                task['department_name'] = dept_map.get(task['department_id'], task.get('department'))
    
    return tasks


@api_router.get("/tasks/stats")
async def get_task_stats(current_user: dict = Depends(get_current_user)):
    """Get task statistics for dashboard."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    stats = await task_service.get_task_stats(
        user_id=current_user['user_id'],
        organization=user_doc.get('organization')
    )
    return stats


@api_router.get("/tasks/{task_id}")
async def get_task_detail(task_id: str, current_user: dict = Depends(get_current_user)):
    """Get full task details including evidence and comments."""
    task = await db.tasks.find_one(
        {"id": task_id, "user_id": current_user['user_id']},
        {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Enrich department_name
    if task.get('department_id') and not task.get('department_name'):
        dept = await db.departments.find_one({"id": task['department_id']}, {"_id": 0, "name": 1})
        if dept:
            task['department_name'] = dept.get('name')
    if task.get('department') and not task.get('department_name'):
        task['department_name'] = task.get('department')

    # Get linked evidence
    evidence = []
    for eid in task.get("evidence_ids", []):
        ev = await db.evidence.find_one({"id": eid}, {"_id": 0})
        if ev:
            evidence.append(ev)

    # Get comments
    comments = await task_service.get_comments(task_id)

    # Get source gap info if available
    source_info = None
    if task.get("gap_id"):
        gap = await db.gap_analyses.find_one({"id": task["gap_id"]}, {"_id": 0, "compliance_score": 1})
        if gap:
            source_info = {"type": "gap_analysis", "id": task["gap_id"]}

    if task.get("regulation_id"):
        reg = await db.regulations.find_one({"id": task["regulation_id"]}, {"_id": 0, "title": 1})
        if reg:
            source_info = source_info or {}
            source_info["regulation"] = {"id": task["regulation_id"], "title": reg.get("title")}

    # Get linked clauses from policy and regulation
    linked_clauses = []
    if task.get("clause_id"):
        # Try to find the clause in the policy document
        if task.get("policy_id"):
            policy = await db.policies.find_one(
                {"id": task["policy_id"]},
                {"_id": 0, "title": 1, "clauses": 1}
            )
            if policy:
                for clause in policy.get("clauses", []):
                    if clause.get("clause_id") == task["clause_id"] or clause.get("id") == task["clause_id"]:
                        linked_clauses.append({
                            "clause_id": task["clause_id"],
                            "text": clause.get("text", clause.get("original_text", "")),
                            "section": clause.get("section", ""),
                            "source_type": "policy",
                            "source_id": task["policy_id"],
                            "source_title": policy.get("title", "Unknown Policy")
                        })
                        break

        # Try to find the clause in the regulation document
        if task.get("regulation_id"):
            regulation = await db.regulations.find_one(
                {"id": task["regulation_id"]},
                {"_id": 0, "title": 1, "clauses": 1}
            )
            if regulation:
                for clause in regulation.get("clauses", []):
                    if clause.get("clause_id") == task["clause_id"] or clause.get("id") == task["clause_id"]:
                        linked_clauses.append({
                            "clause_id": task["clause_id"],
                            "text": clause.get("text", clause.get("original_text", "")),
                            "section": clause.get("section", ""),
                            "source_type": "regulation",
                            "source_id": task["regulation_id"],
                            "source_title": regulation.get("title", "Unknown Regulation")
                        })
                        break

    # Also get gap analysis linked clauses if task came from gap analysis
    if task.get("gap_id") or task.get("gap_analysis_id"):
        gap_id = task.get("gap_id") or task.get("gap_analysis_id")
        gap_analysis = await db.gap_analyses.find_one(
            {"id": gap_id},
            {"_id": 0, "gaps": 1, "policy_id": 1, "regulation_id": 1}
        )
        if gap_analysis:
            gap_policy_id = gap_analysis.get("policy_id")
            gap_regulation_id = gap_analysis.get("regulation_id")
            # Find gaps related to this task's clause
            for gap in gap_analysis.get("gaps", []):
                gap_clause_id = gap.get("regulation_clause_id") or gap.get("clause_id")
                if gap_clause_id and (not task.get("clause_id") or gap_clause_id == task.get("clause_id")):
                    # Add regulation clause from gap
                    if gap.get("regulation_clause_text") or gap.get("requirement"):
                        already_exists = any(c.get("clause_id") == gap_clause_id for c in linked_clauses)
                        if not already_exists:
                            linked_clauses.append({
                                "clause_id": gap_clause_id,
                                "text": gap.get("regulation_clause_text", gap.get("requirement", "")),
                                "section": gap.get("section", gap.get("regulation_clause_section", "")),
                                "source_type": "regulation",
                                "source_id": gap_regulation_id or task.get("regulation_id", ""),
                                "source_title": gap.get("regulation_title", "Regulation"),
                                "gap_status": gap.get("status", gap.get("compliance_status", ""))
                            })
                    # Add matched policy clauses from gap
                    for matched in gap.get("matched_policy_clauses", []):
                        pc_id = matched.get("clause_id") or matched.get("id")
                        if pc_id:
                            already_exists = any(c.get("clause_id") == pc_id for c in linked_clauses)
                            if not already_exists:
                                linked_clauses.append({
                                    "clause_id": pc_id,
                                    "text": matched.get("text", matched.get("original_text", "")),
                                    "section": matched.get("section", ""),
                                    "source_type": "policy",
                                    "source_id": gap_policy_id or task.get("policy_id", ""),
                                    "source_title": matched.get("policy_title", "Policy"),
                                    "similarity_score": matched.get("similarity_score")
                                })
                    # Only include first relevant gap to avoid overwhelming the response
                    if linked_clauses:
                        break

    # Get timeline/activities from the task itself
    timeline = task.get("activities", [])

    return {
        "task": task,
        "evidence": evidence,
        "comments": comments,
        "source_info": source_info,
        "linked_clauses": linked_clauses,
        "timeline": timeline
    }


@api_router.post("/tasks")
async def create_task(task_data: TaskCreate, current_user: dict = Depends(check_not_auditor)):
    """Create a new task. Auditors cannot create tasks."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    task = Task(
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        assigned_to=task_data.assigned_to,
        assigned_member_id=task_data.assigned_member_id,
        department=task_data.department,
        department_id=task_data.department_id,
        source_type=task_data.source_type or "manual",
        gap_id=task_data.gap_id,
        gap_analysis_id=task_data.gap_analysis_id,
        policy_id=task_data.policy_id,
        regulation_id=task_data.regulation_id,
        circular_id=task_data.circular_id,
        clause_id=task_data.clause_id,
        due_date=task_data.due_date,
        estimated_hours=task_data.estimated_hours,
        reminder_days=task_data.reminder_days,
        is_recurring=task_data.is_recurring,
        recurrence_type=task_data.recurrence_type,
        recurrence_config=task_data.recurrence_config,
        tags=task_data.tags,
        user_id=current_user['user_id'],
        organization=user_doc.get('organization', 'Default')
    )
    
    # Add creation activity
    task.activities = [{
        "id": str(uuid.uuid4()),
        "type": "created",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": current_user['user_id'],
        "user_name": user_doc.get('name', current_user.get('email', 'User')),
        "details": {}
    }]
    
    task_dict = task.model_dump()
    task_dict['created_at'] = task_dict['created_at'].isoformat()
    task_dict['updated_at'] = task_dict['updated_at'].isoformat()
    if task_dict.get('due_date'):
        task_dict['due_date'] = task_dict['due_date'].isoformat()
    
    await db.tasks.insert_one(task_dict)
    # Remove MongoDB's _id field to avoid ObjectId serialization error
    task_dict.pop('_id', None)
    return task_dict


@api_router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    task_data: TaskCreate,
    current_user: dict = Depends(check_not_auditor)
):
    """Update an existing task. Implements last-write-wins for concurrent edits."""
    # Find existing task
    existing_task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check authorization - user must be owner or assigned to task
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    if existing_task.get('user_id') != current_user['user_id'] and existing_task.get('assigned_member_id') != current_user['user_id']:
        # Allow if user is admin/compliance_head
        if user_doc.get('role') not in ['admin', 'compliance_head']:
            raise HTTPException(status_code=403, detail="Not authorized to update this task")

    # Build update dict with only editable fields
    update_dict = {
        "title": task_data.title,
        "description": task_data.description,
        "priority": task_data.priority.value if hasattr(task_data.priority, 'value') else task_data.priority,
        "assigned_to": task_data.assigned_to,
        "assigned_member_id": task_data.assigned_member_id,
        "department": task_data.department,
        "department_id": task_data.department_id,
        "due_date": task_data.due_date.isoformat() if task_data.due_date else None,
        "estimated_hours": task_data.estimated_hours,
        "reminder_days": task_data.reminder_days,
        "tags": task_data.tags,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    # Add activity log entry
    activity = {
        "id": str(uuid.uuid4()),
        "type": "updated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": current_user['user_id'],
        "user_name": user_doc.get('name', current_user.get('email', 'User')),
        "details": {
            "fields_updated": ["title", "description", "priority", "assigned_to", "department", "due_date"]
        }
    }

    # Update task in database (last-write-wins strategy)
    result = await db.tasks.update_one(
        {"id": task_id},
        {
            "$set": update_dict,
            "$push": {"activities": activity}
        }
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update task")

    # Fetch and return updated task
    updated_task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return updated_task


@api_router.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    status: TaskStatus,
    notes: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Update task status with validation."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    success, message = await task_service.change_status(
        task_id=task_id,
        new_status=status.value,
        user_id=current_user['user_id'],
        user_name=user_doc.get('name', current_user.get('email', 'User')),
        notes=notes
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message}


@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a task. Only the task owner or compliance_head can delete."""
    task = await db.tasks.find_one(
        {"id": task_id, "user_id": current_user['user_id']},
        {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete the task
    await db.tasks.delete_one({"id": task_id, "user_id": current_user['user_id']})

    # Clean up related data
    await db.task_comments.delete_many({"task_id": task_id})
    await db.task_timeline.delete_many({"task_id": task_id})
    await db.task_dependencies.delete_many({
        "$or": [{"task_id": task_id}, {"depends_on_id": task_id}]
    })

    return {"message": "Task deleted successfully", "id": task_id}


@api_router.post("/tasks/{task_id}/assign")
async def assign_task(
    task_id: str,
    assignment: TaskAssignRequest,
    current_user: dict = Depends(get_current_user)
):
    """Assign task to a team member."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    success, message = await task_service.assign_task(
        task_id=task_id,
        member_id=assignment.member_id,
        member_name=assignment.member_name,
        department_id=assignment.department_id,
        department_name=assignment.department_name,
        assigner_id=current_user['user_id'],
        assigner_name=user_doc.get('name', current_user.get('email', 'User'))
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message}


@api_router.post("/tasks/{task_id}/suggest-assignment")
async def suggest_task_assignment(
    task_id: str,
    department_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Use AI to suggest the best team member for task assignment.

    Considers:
    - Current workload of team members
    - Expertise match with task requirements
    - Role suitability
    - Fair workload distribution

    Returns:
    - suggested_member: Member details with current workload
    - reasoning: AI explanation for the suggestion
    - workload_comparison: All members sorted by workload
    - confidence: AI confidence score (0-1)
    """
    try:
        suggestion = await task_service.suggest_task_assignment(
            task_id=task_id,
            department_id=department_id
        )

        return suggestion

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error suggesting assignment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Assignment suggestion failed: {str(e)}")


@api_router.post("/tasks/{task_id}/timer/start")
async def start_task_timer(task_id: str, current_user: dict = Depends(get_current_user)):
    """Start the timer for a task."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    success, message = await task_service.start_timer(
        task_id=task_id,
        user_id=current_user['user_id'],
        user_name=user_doc.get('name', current_user.get('email', 'User'))
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message, "timer_running": True}


@api_router.post("/tasks/{task_id}/timer/stop")
async def stop_task_timer(task_id: str, current_user: dict = Depends(get_current_user)):
    """Stop the timer for a task."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    success, result = await task_service.stop_timer(
        task_id=task_id,
        user_id=current_user['user_id'],
        user_name=user_doc.get('name', current_user.get('email', 'User'))
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to stop timer"))
    
    return result


@api_router.post("/tasks/{task_id}/evidence")
async def add_evidence_to_task(
    task_id: str,
    evidence_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Link evidence to a task."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    success, message = await task_service.add_evidence(
        task_id=task_id,
        evidence_id=evidence_id,
        user_id=current_user['user_id'],
        user_name=user_doc.get('name', current_user.get('email', 'User'))
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message}


@api_router.post("/tasks/{task_id}/submit-review")
async def submit_task_for_review(
    task_id: str,
    request: TaskSubmitReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """Submit task for AI review."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    success, message = await task_service.submit_for_review(
        task_id=task_id,
        user_id=current_user['user_id'],
        user_name=user_doc.get('name', current_user.get('email', 'User')),
        evidence_ids=request.evidence_ids,
        notes=request.notes
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Return updated task
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return {
        "message": message,
        "task": task
    }


@api_router.post("/tasks/{task_id}/approve")
async def approve_task(
    task_id: str,
    request: TaskApprovalRequest,
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject a task after manual review."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    if request.approved:
        success, message = await task_service.approve_task(
            task_id=task_id,
            reviewer_id=current_user['user_id'],
            reviewer_name=user_doc.get('name', current_user.get('email', 'User')),
            notes=request.notes
        )
    else:
        if not request.rejection_reason:
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        success, message = await task_service.reject_task(
            task_id=task_id,
            reviewer_id=current_user['user_id'],
            reviewer_name=user_doc.get('name', current_user.get('email', 'User')),
            reason=request.rejection_reason
        )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"message": message}


@api_router.get("/tasks/{task_id}/comments")
async def get_task_comments(task_id: str, current_user: dict = Depends(get_current_user)):
    """Get all comments for a task."""
    comments = await task_service.get_comments(task_id)
    return comments


@api_router.post("/tasks/{task_id}/comments")
async def add_task_comment(
    task_id: str,
    comment_data: TaskCommentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a comment to a task."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    
    comment = await task_service.add_comment(
        task_id=task_id,
        content=comment_data.content,
        user_id=current_user['user_id'],
        user_name=user_doc.get('name', current_user.get('email', 'User')),
        user_email=current_user.get('email'),
        mentions=comment_data.mentions
    )
    
    return comment


@api_router.get("/tasks/{task_id}/timeline")
async def get_task_timeline(task_id: str, current_user: dict = Depends(get_current_user)):
    """Get full activity timeline for a task."""
    task = await db.tasks.find_one(
        {"id": task_id, "user_id": current_user['user_id']},
        {"_id": 0, "activities": 1}
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task.get("activities", [])


@api_router.get("/tasks/reminders/pending")
async def get_pending_reminders(current_user: dict = Depends(get_current_user)):
    """Get pending email reminders (for UI display or email service)."""
    reminders = await task_service.get_pending_reminders()
    return reminders


@api_router.post("/tasks/escalation/run")
async def run_escalation_check(current_user: dict = Depends(get_current_user)):
    """Manually trigger escalation check (normally run by cron)."""
    escalated = await task_service.check_and_escalate()
    return {"escalated_count": len(escalated), "tasks": escalated}


@api_router.post("/tasks/recurring/generate")
async def generate_recurring_tasks(current_user: dict = Depends(get_current_user)):
    """Manually generate recurring task instances (normally run by cron)."""
    generated = await task_service.generate_recurring_tasks()
    return {"generated_count": len(generated), "tasks": generated}

@api_router.get("/tasks/export")
async def export_tasks(
    format: str = "excel",
    status: Optional[str] = None,
    priority: Optional[str] = None,
    department: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Feature #53: Export tasks to Excel/CSV or PDF format."""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    from datetime import datetime

    # Build query
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    query = {"organization": user_doc.get('organization', 'Default')}

    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if department:
        query["department_id"] = department

    # Fetch tasks
    tasks = await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)

    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found to export")

    if format.lower() in ["excel", "csv"]:
        # Generate CSV (works as Excel too)
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Title", "Description", "Status", "Priority", "Department",
            "Assigned To", "Due Date", "Created At", "Is Overdue",
            "SLA Hours", "Time Spent", "Compliance Requirement"
        ])

        # Data rows
        for task in tasks:
            writer.writerow([
                task.get("title", ""),
                task.get("description", ""),
                task.get("status", ""),
                task.get("priority", ""),
                task.get("department_name", ""),
                task.get("assigned_to_name", ""),
                task.get("due_date", ""),
                task.get("created_at", ""),
                "Yes" if task.get("is_overdue", False) else "No",
                task.get("sla_hours", ""),
                task.get("time_spent_seconds", 0) / 3600 if task.get("time_spent_seconds") else 0,
                task.get("compliance_requirement", "")
            ])

        output.seek(0)
        filename = f"tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    elif format.lower() == "pdf":
        # Generate simple text-based PDF content (HTML that can be printed to PDF)
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Task Export</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #666; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .overdue {{ color: red; font-weight: bold; }}
        .priority-critical {{ color: #dc2626; }}
        .priority-high {{ color: #ea580c; }}
        .priority-medium {{ color: #2563eb; }}
        .priority-low {{ color: #16a34a; }}
    </style>
</head>
<body>
    <h1>Task Export Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>Total Tasks: {len(tasks)}</p>

    <table>
        <thead>
            <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Department</th>
                <th>Assigned To</th>
                <th>Due Date</th>
                <th>Overdue</th>
            </tr>
        </thead>
        <tbody>
"""

        for task in tasks:
            priority_class = f"priority-{task.get('priority', 'medium').lower()}"
            overdue_class = "overdue" if task.get("is_overdue", False) else ""

            html_content += f"""
            <tr>
                <td>{task.get('title', '')}</td>
                <td>{task.get('status', '')}</td>
                <td class="{priority_class}">{task.get('priority', '')}</td>
                <td>{task.get('department_name', '')}</td>
                <td>{task.get('assigned_to_name', '')}</td>
                <td>{task.get('due_date', '')}</td>
                <td class="{overdue_class}">{'Yes' if task.get('is_overdue', False) else 'No'}</td>
            </tr>
"""

        html_content += """
        </tbody>
    </table>
</body>
</html>
"""

        filename = f"tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        return StreamingResponse(
            io.BytesIO(html_content.encode('utf-8')),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'excel', 'csv', or 'pdf'")


# ========== BULK TASK OPERATIONS ==========
@api_router.post("/tasks/bulk-create")
async def bulk_create_tasks(
    tasks_data: List[TaskCreate],
    current_user: dict = Depends(check_not_auditor)
):
    """Feature #170: Bulk create multiple tasks at once."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')
    created_tasks = []

    for task_data in tasks_data:
        task = Task(
            title=task_data.title,
            description=task_data.description,
            priority=task_data.priority,
            assigned_to=task_data.assigned_to,
            assigned_member_id=task_data.assigned_member_id,
            department=task_data.department,
            department_id=task_data.department_id,
            source_type=task_data.source_type or "manual",
            gap_id=task_data.gap_id,
            gap_analysis_id=task_data.gap_analysis_id,
            policy_id=task_data.policy_id,
            regulation_id=task_data.regulation_id,
            circular_id=task_data.circular_id,
            clause_id=task_data.clause_id,
            due_date=task_data.due_date,
            estimated_hours=task_data.estimated_hours,
            reminder_days=task_data.reminder_days,
            is_recurring=task_data.is_recurring,
            recurrence_type=task_data.recurrence_type,
            recurrence_config=task_data.recurrence_config,
            tags=task_data.tags,
            user_id=current_user['user_id'],
            organization=org
        )

        task.activities = [{
            "id": str(uuid.uuid4()),
            "type": "created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": current_user['user_id'],
            "user_name": user_doc.get('name', current_user.get('email', 'User')),
            "details": {"bulk_create": True}
        }]

        task_dict = task.model_dump()
        task_dict['created_at'] = task_dict['created_at'].isoformat()
        task_dict['updated_at'] = task_dict['updated_at'].isoformat()
        if task_dict.get('due_date'):
            task_dict['due_date'] = task_dict['due_date'].isoformat()

        await db.tasks.insert_one(task_dict)
        task_dict.pop('_id', None)
        created_tasks.append(task_dict)

    return {"created": len(created_tasks), "tasks": created_tasks}


class BulkAssignRequest(BaseModel):
    task_ids: List[str]
    member_id: str
    member_name: str
    department_id: Optional[str] = None
    department_name: Optional[str] = None


@api_router.post("/tasks/bulk-assign")
async def bulk_assign_tasks(
    request: BulkAssignRequest,
    current_user: dict = Depends(check_not_auditor)
):
    """Feature #170: Bulk assign multiple tasks to a team member."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    assigner_name = user_doc.get('name', current_user.get('email', 'User'))

    updated_count = 0
    for task_id in request.task_ids:
        success, _ = await task_service.assign_task(
            task_id=task_id,
            member_id=request.member_id,
            member_name=request.member_name,
            department_id=request.department_id,
            department_name=request.department_name,
            assigner_id=current_user['user_id'],
            assigner_name=assigner_name
        )
        if success:
            updated_count += 1

    return {"updated": updated_count, "total": len(request.task_ids)}


# ========== REGULATION CRAWL TRIGGER ==========
@api_router.post("/regulations/trigger-crawl")
async def trigger_regulation_crawl(
    current_user: dict = Depends(get_current_user)
):
    """Feature #176: Manually trigger regulation crawler."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')

    # Create crawl status record
    crawl_id = str(uuid.uuid4())
    crawl_record = {
        "id": crawl_id,
        "status": "running",
        "triggered_by": current_user['user_id'],
        "triggered_by_name": user_doc.get('name', current_user.get('email', 'User')),
        "organization": org,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "results": {
            "new_circulars": 0,
            "updated_regulations": 0,
            "sources_checked": ["RBI", "FIU-IND", "NPCI"],
            "findings": []
        },
        "error": None
    }

    await db.regulation_crawls.insert_one(crawl_record)
    crawl_record.pop('_id', None)

    # Simulate crawl completion in background (in production this would be a real crawler)
    async def complete_crawl():
        await asyncio.sleep(3)  # Simulate crawl time

        # Check for recent regulation updates to simulate findings
        recent_updates = await db.regulation_updates.find(
            {"organization": org}
        ).sort("created_at", -1).limit(5).to_list(5)

        findings = []
        for update in recent_updates:
            findings.append({
                "title": update.get("title", "Regulatory Update"),
                "source": update.get("regulatory_body", "RBI"),
                "type": update.get("change_type", "new"),
                "date": update.get("created_at", datetime.now(timezone.utc).isoformat())
            })

        await db.regulation_crawls.update_one(
            {"id": crawl_id},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "results.new_circulars": len(findings),
                "results.findings": findings
            }}
        )

    asyncio.create_task(complete_crawl())

    return crawl_record


@api_router.get("/regulations/crawl-status")
async def get_crawl_status(
    current_user: dict = Depends(get_current_user)
):
    """Feature #176: Get latest crawl status."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')

    latest_crawl = await db.regulation_crawls.find_one(
        {"organization": org},
        {"_id": 0},
        sort=[("started_at", -1)]
    )

    if not latest_crawl:
        return {"status": "no_crawls", "message": "No crawls have been run yet"}

    return latest_crawl


# ========== TASK DEPENDENCY ENDPOINTS ==========
@api_router.post("/tasks/{task_id}/dependencies")
async def create_task_dependency(
    task_id: str,
    dependency: TaskDependencyCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #50: Create a dependency relationship between tasks.
    Supports blocking, blocked_by, related, parent, and child relationships.
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    # Verify both tasks exist and belong to same organization
    task = await db.tasks.find_one({"id": task_id, "organization": organization}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    depends_on_task = await db.tasks.find_one(
        {"id": dependency.depends_on_task_id, "organization": organization},
        {"_id": 0}
    )
    if not depends_on_task:
        raise HTTPException(status_code=404, detail="Dependent task not found")

    # Prevent self-dependency
    if task_id == dependency.depends_on_task_id:
        raise HTTPException(status_code=400, detail="Task cannot depend on itself")

    # Check if dependency already exists
    existing = await db.task_dependencies.find_one({
        "task_id": task_id,
        "depends_on_task_id": dependency.depends_on_task_id,
        "dependency_type": dependency.dependency_type
    })
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")

    # Create dependency
    from models import TaskDependency
    dep_obj = TaskDependency(
        task_id=task_id,
        depends_on_task_id=dependency.depends_on_task_id,
        dependency_type=dependency.dependency_type,
        created_by=current_user['user_id'],
        user_id=current_user['user_id'],
        organization=organization
    )

    await db.task_dependencies.insert_one(dep_obj.model_dump())

    # Update task's dependency fields
    if dependency.dependency_type == "blocked_by":
        await db.tasks.update_one(
            {"id": task_id},
            {"$addToSet": {"blocked_by_ids": dependency.depends_on_task_id}}
        )
        await db.tasks.update_one(
            {"id": dependency.depends_on_task_id},
            {"$addToSet": {"blocks_ids": task_id}}
        )
    elif dependency.dependency_type == "blocks":
        await db.tasks.update_one(
            {"id": task_id},
            {"$addToSet": {"blocks_ids": dependency.depends_on_task_id}}
        )
        await db.tasks.update_one(
            {"id": dependency.depends_on_task_id},
            {"$addToSet": {"blocked_by_ids": task_id}}
        )
    elif dependency.dependency_type in ["related", "parent", "child"]:
        await db.tasks.update_one(
            {"id": task_id},
            {"$addToSet": {"related_task_ids": dependency.depends_on_task_id}}
        )
        await db.tasks.update_one(
            {"id": dependency.depends_on_task_id},
            {"$addToSet": {"related_task_ids": task_id}}
        )

    # Update is_blocked status if task has blocking dependencies
    blocked_by_tasks = await db.task_dependencies.find({
        "task_id": task_id,
        "dependency_type": "blocked_by"
    }).to_list(100)

    is_blocked = False
    for dep in blocked_by_tasks:
        blocking_task = await db.tasks.find_one({"id": dep["depends_on_task_id"]}, {"_id": 0})
        if blocking_task and blocking_task.get("status") != "Completed":
            is_blocked = True
            break

    await db.tasks.update_one(
        {"id": task_id},
        {"$set": {"is_blocked": is_blocked}}
    )

    return {
        "message": "Dependency created successfully",
        "dependency": dep_obj.model_dump()
    }


@api_router.get("/tasks/{task_id}/dependencies")
async def get_task_dependencies(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #50: Get all dependencies for a task.
    Returns dependencies organized by type (blocks, blocked_by, related).
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    # Verify task exists
    task = await db.tasks.find_one({"id": task_id, "organization": organization}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Fetch all dependencies for this task
    dependencies = await db.task_dependencies.find({
        "task_id": task_id
    }, {"_id": 0}).to_list(1000)

    # Also fetch reverse dependencies (tasks that depend on this task)
    reverse_dependencies = await db.task_dependencies.find({
        "depends_on_task_id": task_id
    }, {"_id": 0}).to_list(1000)

    # Fetch task details for each dependency
    blocks = []
    blocked_by = []
    related = []

    for dep in dependencies:
        dep_task = await db.tasks.find_one(
            {"id": dep["depends_on_task_id"]},
            {"_id": 0, "id": 1, "title": 1, "status": 1, "priority": 1}
        )
        if dep_task:
            dep_info = {
                "dependency_id": dep["id"],
                "task": dep_task,
                "dependency_type": dep["dependency_type"],
                "created_at": dep["created_at"]
            }
            if dep["dependency_type"] == "blocked_by":
                blocked_by.append(dep_info)
            elif dep["dependency_type"] == "blocks":
                blocks.append(dep_info)
            else:
                related.append(dep_info)

    for dep in reverse_dependencies:
        dep_task = await db.tasks.find_one(
            {"id": dep["task_id"]},
            {"_id": 0, "id": 1, "title": 1, "status": 1, "priority": 1}
        )
        if dep_task:
            dep_info = {
                "dependency_id": dep["id"],
                "task": dep_task,
                "dependency_type": "blocks" if dep["dependency_type"] == "blocked_by" else "blocked_by",
                "created_at": dep["created_at"]
            }
            if dep["dependency_type"] == "blocked_by":
                blocks.append(dep_info)
            elif dep["dependency_type"] == "blocks":
                blocked_by.append(dep_info)

    return {
        "task_id": task_id,
        "blocks": blocks,
        "blocked_by": blocked_by,
        "related": related,
        "is_blocked": task.get("is_blocked", False)
    }


@api_router.delete("/tasks/{task_id}/dependencies/{dependency_id}")
async def delete_task_dependency(
    task_id: str,
    dependency_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #50: Delete a task dependency relationship.
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    # Find the dependency
    dependency = await db.task_dependencies.find_one({"id": dependency_id}, {"_id": 0})
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")

    # Verify task ownership
    task = await db.tasks.find_one(
        {"id": task_id, "organization": organization},
        {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Remove dependency from database
    await db.task_dependencies.delete_one({"id": dependency_id})

    # Update task dependency fields
    if dependency["dependency_type"] == "blocked_by":
        await db.tasks.update_one(
            {"id": task_id},
            {"$pull": {"blocked_by_ids": dependency["depends_on_task_id"]}}
        )
        await db.tasks.update_one(
            {"id": dependency["depends_on_task_id"]},
            {"$pull": {"blocks_ids": task_id}}
        )
    elif dependency["dependency_type"] == "blocks":
        await db.tasks.update_one(
            {"id": task_id},
            {"$pull": {"blocks_ids": dependency["depends_on_task_id"]}}
        )
        await db.tasks.update_one(
            {"id": dependency["depends_on_task_id"]},
            {"$pull": {"blocked_by_ids": task_id}}
        )
    elif dependency["dependency_type"] in ["related", "parent", "child"]:
        await db.tasks.update_one(
            {"id": task_id},
            {"$pull": {"related_task_ids": dependency["depends_on_task_id"]}}
        )
        await db.tasks.update_one(
            {"id": dependency["depends_on_task_id"]},
            {"$pull": {"related_task_ids": task_id}}
        )

    # Update is_blocked status
    blocked_by_tasks = await db.task_dependencies.find({
        "task_id": task_id,
        "dependency_type": "blocked_by"
    }).to_list(100)

    is_blocked = False
    for dep in blocked_by_tasks:
        blocking_task = await db.tasks.find_one({"id": dep["depends_on_task_id"]}, {"_id": 0})
        if blocking_task and blocking_task.get("status") != "Completed":
            is_blocked = True
            break

    await db.tasks.update_one(
        {"id": task_id},
        {"$set": {"is_blocked": is_blocked}}
    )

    return {"message": "Dependency deleted successfully"}


@api_router.get("/tasks/{task_id}/dependency-graph")
async def get_task_dependency_graph(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #50: Get dependency graph data for visualization.
    Returns nodes and edges for rendering a dependency graph.
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    organization = user_doc.get('organization', 'Default')

    # Verify task exists
    task = await db.tasks.find_one({"id": task_id, "organization": organization}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build graph data using BFS to find all connected tasks
    visited = set()
    nodes = {}
    edges = []

    async def traverse(current_task_id, depth=0, max_depth=3):
        if current_task_id in visited or depth > max_depth:
            return

        visited.add(current_task_id)

        # Get task details
        task_doc = await db.tasks.find_one(
            {"id": current_task_id, "organization": organization},
            {"_id": 0, "id": 1, "title": 1, "status": 1, "priority": 1, "is_blocked": 1}
        )

        if not task_doc:
            return

        nodes[current_task_id] = task_doc

        # Get dependencies
        dependencies = await db.task_dependencies.find({
            "$or": [
                {"task_id": current_task_id},
                {"depends_on_task_id": current_task_id}
            ]
        }, {"_id": 0}).to_list(1000)

        for dep in dependencies:
            edge = {
                "from": dep["task_id"] if dep["dependency_type"] in ["blocks", "related"] else dep["depends_on_task_id"],
                "to": dep["depends_on_task_id"] if dep["dependency_type"] in ["blocks", "related"] else dep["task_id"],
                "type": dep["dependency_type"]
            }

            if edge not in edges:
                edges.append(edge)

            # Traverse connected task
            next_task_id = dep["depends_on_task_id"] if dep["task_id"] == current_task_id else dep["task_id"]
            await traverse(next_task_id, depth + 1, max_depth)

    await traverse(task_id)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "root_task_id": task_id
    }


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

@api_router.put("/calendar/events/{event_id}")
async def update_calendar_event(event_id: str, updates: dict = Body(...), current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    event = await db.calendar_events.find_one({"id": event_id, "organization": user_doc.get('organization')}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    allowed_fields = ['title', 'description', 'event_type', 'regulator', 'due_date', 'responsible_department', 'status']
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    
    if update_data:
        await db.calendar_events.update_one({"id": event_id}, {"$set": update_data})
    
    updated = await db.calendar_events.find_one({"id": event_id}, {"_id": 0})
    return updated

@api_router.delete("/calendar/events/{event_id}")
async def delete_calendar_event(event_id: str, current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    result = await db.calendar_events.delete_one({"id": event_id, "organization": user_doc.get('organization')})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"message": "Event deleted"}

# ========== NOTIFICATION ENDPOINTS ==========
@api_router.get("/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    notifications = await db.notifications.find(
        {"user_id": current_user['user_id']},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    for n in notifications:
        if isinstance(n.get('created_at'), str):
            n['created_at'] = datetime.fromisoformat(n['created_at'])
    
    return notifications

@api_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.notifications.update_one(
        {"id": notification_id, "user_id": current_user['user_id']},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Notification marked as read"}

@api_router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    await db.notifications.update_many(
        {"user_id": current_user['user_id'], "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "All notifications marked as read"}

@api_router.get("/notifications/preferences")
async def get_notification_preferences(current_user: dict = Depends(get_current_user)):
    prefs = await db.notification_preferences.find_one({"user_id": current_user['user_id']}, {"_id": 0})
    if not prefs:
        prefs = {
            "user_id": current_user['user_id'],
            "in_app": True,
            "email": False,
            "email_frequency": "daily",
            "categories": {
                "gap_analysis": True,
                "task_updates": True,
                "policy_changes": True,
                "audit_alerts": True,
                "regulatory_updates": True,
                "evidence_reviews": True,
                "sla_warnings": True
            }
        }
    return prefs

@api_router.put("/notifications/preferences")
async def update_notification_preferences(prefs: dict = Body(...), current_user: dict = Depends(get_current_user)):
    prefs['user_id'] = current_user['user_id']
    await db.notification_preferences.update_one(
        {"user_id": current_user['user_id']},
        {"$set": prefs},
        upsert=True
    )
    return prefs

@api_router.get("/notifications/unread-count")
async def get_unread_notification_count(current_user: dict = Depends(get_current_user)):
    count = await db.notifications.count_documents({"user_id": current_user['user_id'], "read": False})
    return {"count": count}

# ========== ANALYTICS ENDPOINTS ==========
@api_router.get("/analytics/compliance-score")
async def get_analytics_compliance_score(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')
    
    # Overall score from latest gap analysis
    latest = await db.gap_analyses.find_one(
        {"organization": org}, {"_id": 0}, sort=[('created_at', -1)]
    )
    overall_score = latest.get('compliance_score', 0) if latest else 0
    
    # Per-regulation breakdown
    analyses = await db.gap_analyses.find({"organization": org}, {"_id": 0}).to_list(100)
    regulation_scores = {}
    for a in analyses:
        reg_name = a.get('regulation_name', 'Unknown')
        regulation_scores[reg_name] = a.get('compliance_score', 0)
    
    # Per-policy breakdown
    policy_scores = {}
    for a in analyses:
        pol_name = a.get('policy_name', 'Unknown')
        policy_scores[pol_name] = a.get('compliance_score', 0)
    
    # Trend
    trend = []
    sorted_analyses = sorted(analyses, key=lambda x: x.get('created_at', ''))
    for a in sorted_analyses[-12:]:
        created = a.get('created_at')
        date_str = created.strftime("%Y-%m-%d") if isinstance(created, datetime) else str(created)[:10]
        trend.append({"date": date_str, "score": a.get('compliance_score', 0)})
    
    return {
        "overall_score": overall_score,
        "regulation_scores": regulation_scores,
        "policy_scores": policy_scores,
        "trend": trend
    }

@api_router.get("/analytics/sla-performance")
async def get_analytics_sla(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')
    
    total_tasks = await db.tasks.count_documents({"organization": org})
    completed = await db.tasks.count_documents({"organization": org, "status": {"$in": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}})
    overdue = await db.tasks.count_documents({
        "organization": org,
        "due_date": {"$lt": datetime.now(timezone.utc)},
        "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
    })
    on_time = completed
    
    # By priority
    by_priority = {}
    for p in SeverityLevel:
        p_total = await db.tasks.count_documents({"organization": org, "priority": p})
        p_completed = await db.tasks.count_documents({"organization": org, "priority": p, "status": {"$in": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}})
        p_overdue = await db.tasks.count_documents({
            "organization": org, "priority": p,
            "due_date": {"$lt": datetime.now(timezone.utc)},
            "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
        })
        by_priority[p.value] = {"total": p_total, "completed": p_completed, "overdue": p_overdue}
    
    # By department
    departments = await db.departments.find({"organization": org}, {"_id": 0}).to_list(100)
    by_team = []
    for dept in departments:
        d_total = await db.tasks.count_documents({"organization": org, "department_id": dept.get('id')})
        d_completed = await db.tasks.count_documents({"organization": org, "department_id": dept.get('id'), "status": {"$in": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}})
        d_overdue = await db.tasks.count_documents({
            "organization": org, "department_id": dept.get('id'),
            "due_date": {"$lt": datetime.now(timezone.utc)},
            "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
        })
        by_team.append({"department": dept.get('name'), "total": d_total, "completed": d_completed, "overdue": d_overdue})
    
    return {
        "total_tasks": total_tasks,
        "on_time": on_time,
        "overdue": overdue,
        "sla_rate": round((on_time / total_tasks * 100) if total_tasks > 0 else 100, 1),
        "by_priority": by_priority,
        "by_team": by_team
    }

@api_router.get("/analytics/gaps-heatmap")
async def get_analytics_gaps_heatmap(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')
    
    analyses = await db.gap_analyses.find({"organization": org}, {"_id": 0}).to_list(100)
    
    heatmap_data = []
    for a in analyses:
        gaps = a.get('gaps', [])
        severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for g in gaps:
            sev = g.get('severity', 'Medium')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Look up policy and regulation names if not stored
        policy_name = a.get('policy_name', '')
        if not policy_name and a.get('policy_id'):
            policy_doc = await db.policies.find_one({"id": a['policy_id']}, {"title": 1, "_id": 0})
            policy_name = policy_doc.get('title', 'Unknown') if policy_doc else 'Unknown'

        regulation_name = a.get('regulation_name', '')
        if not regulation_name and a.get('regulation_id'):
            reg_doc = await db.regulations.find_one({"id": a['regulation_id']}, {"title": 1, "_id": 0})
            regulation_name = reg_doc.get('title', 'Unknown') if reg_doc else 'Unknown'

        heatmap_data.append({
            "analysis_id": a.get('id', ''),
            "policy": policy_name or 'Unknown',
            "regulation": regulation_name or 'Unknown',
            "total_gaps": len(gaps),
            "severity_distribution": severity_counts,
            "compliance_score": a.get('compliance_score', 0),
            "gaps": [{"type": g.get("type", ""), "severity": g.get("severity", ""), "description": g.get("description", g.get("gap_description", "")), "remediation": g.get("remediation_text", g.get("remediation", ""))} for g in gaps[:20]]
        })

    return {"heatmap": heatmap_data}


@api_router.get("/analytics/evidence-progress")
async def get_analytics_evidence_progress(current_user: dict = Depends(get_current_user)):
    """
    Get evidence collection progress analytics per policy and regulation.
    Shows completion percentages and Red/Amber/Green status indicators.
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
    org = user_doc.get('organization', 'Default')
    role = user_doc.get('role', 'user')

    # Build query filter
    if role == 'compliance_head':
        # Compliance heads see all org data
        filter_query = {"organization": org}
    else:
        # Regular users see only their own
        filter_query = {"organization": org, "user_id": current_user['user_id']}

    # Get all policies and regulations
    policies = await db.policies.find(filter_query, {"_id": 0}).to_list(1000)
    regulations = await db.regulations.find(filter_query, {"_id": 0}).to_list(1000)

    # Get all gap analyses to determine required evidence
    gap_analyses = await db.gap_analyses.find(filter_query, {"_id": 0}).to_list(1000)

    # Get all evidence documents
    evidence_docs = await db.evidence.find(filter_query, {"_id": 0}).to_list(5000)

    # Build evidence index by policy_id and regulation_id
    evidence_by_policy = {}
    evidence_by_regulation = {}

    for ev in evidence_docs:
        policy_id = ev.get('policy_id')
        regulation_id = ev.get('regulation_id')

        if policy_id:
            if policy_id not in evidence_by_policy:
                evidence_by_policy[policy_id] = []
            evidence_by_policy[policy_id].append(ev)

        if regulation_id:
            if regulation_id not in evidence_by_regulation:
                evidence_by_regulation[regulation_id] = []
            evidence_by_regulation[regulation_id].append(ev)

    # Calculate progress per policy
    policy_progress = []
    for policy in policies:
        policy_id = policy.get('id')
        policy_name = policy.get('title', 'Unknown Policy')

        # Count gaps for this policy (required evidence items)
        policy_gaps = [ga for ga in gap_analyses if ga.get('policy_id') == policy_id]
        total_gaps = sum(len(ga.get('gaps', [])) for ga in policy_gaps)

        # Count evidence submitted for this policy
        evidence_count = len(evidence_by_policy.get(policy_id, []))

        # Calculate completion percentage
        if total_gaps > 0:
            completion = min(100, int((evidence_count / total_gaps) * 100))
        else:
            completion = 100 if evidence_count > 0 else 0

        # Determine RAG status (Red/Amber/Green)
        if completion >= 80:
            rag_status = "green"
        elif completion >= 50:
            rag_status = "amber"
        else:
            rag_status = "red"

        policy_progress.append({
            "policy_id": policy_id,
            "policy_name": policy_name,
            "required_items": total_gaps,
            "submitted_items": evidence_count,
            "completion_percentage": completion,
            "rag_status": rag_status
        })

    # Calculate progress per regulation
    regulation_progress = []
    for regulation in regulations:
        regulation_id = regulation.get('id')
        regulation_name = regulation.get('title', 'Unknown Regulation')

        # Count gaps for this regulation
        regulation_gaps = [ga for ga in gap_analyses if ga.get('regulation_id') == regulation_id]
        total_gaps = sum(len(ga.get('gaps', [])) for ga in regulation_gaps)

        # Count evidence submitted for this regulation
        evidence_count = len(evidence_by_regulation.get(regulation_id, []))

        # Calculate completion percentage
        if total_gaps > 0:
            completion = min(100, int((evidence_count / total_gaps) * 100))
        else:
            completion = 100 if evidence_count > 0 else 0

        # Determine RAG status
        if completion >= 80:
            rag_status = "green"
        elif completion >= 50:
            rag_status = "amber"
        else:
            rag_status = "red"

        regulation_progress.append({
            "regulation_id": regulation_id,
            "regulation_name": regulation_name,
            "required_items": total_gaps,
            "submitted_items": evidence_count,
            "completion_percentage": completion,
            "rag_status": rag_status
        })

    # Overall summary
    total_required = sum(p['required_items'] for p in policy_progress) + sum(r['required_items'] for r in regulation_progress)
    total_submitted = sum(p['submitted_items'] for p in policy_progress) + sum(r['submitted_items'] for r in regulation_progress)
    overall_completion = int((total_submitted / total_required) * 100) if total_required > 0 else 0

    return {
        "summary": {
            "total_required_items": total_required,
            "total_submitted_items": total_submitted,
            "overall_completion": overall_completion
        },
        "policies": policy_progress,
        "regulations": regulation_progress
    }


@api_router.get("/analytics/regulation-coverage")
async def get_analytics_regulation_coverage(current_user: dict = Depends(get_current_user)):
    """
    Get regulation coverage metrics - which regulations are mapped to policies
    and which are unmapped.
    """
    org = current_user.get("organization", "")

    # Get all regulations for this organization
    regulations = []
    async for reg in db.regulations.find({"organization": org}):
        regulations.append(reg)

    # Get all policies for this organization
    policies = []
    async for pol in db.policies.find({"organization": org}):
        policies.append(pol)

    # Get all gap analyses to determine regulation-policy mappings
    gap_analyses = []
    async for gap in db.gap_analyses.find({"organization": org}):
        gap_analyses.append(gap)

    # Build a set of regulation IDs that are mapped to at least one policy
    mapped_regulation_ids = set()
    regulation_policy_map = {}  # regulation_id -> list of policy names

    for gap in gap_analyses:
        reg_id = gap.get("regulation_id", "")
        pol_id = gap.get("policy_id", "")
        if reg_id:
            mapped_regulation_ids.add(reg_id)
            if reg_id not in regulation_policy_map:
                regulation_policy_map[reg_id] = []
            # Find policy name
            policy_name = "Unknown Policy"
            for p in policies:
                if p.get("id") == pol_id or str(p.get("_id")) == pol_id:
                    policy_name = p.get("title", "Untitled")
                    break
            if policy_name not in regulation_policy_map[reg_id]:
                regulation_policy_map[reg_id].append(policy_name)

    # Also check linked_regulations in policies
    for pol in policies:
        for linked_reg in pol.get("linked_regulations", []):
            reg_id = linked_reg if isinstance(linked_reg, str) else linked_reg.get("id", "")
            if reg_id:
                mapped_regulation_ids.add(reg_id)
                if reg_id not in regulation_policy_map:
                    regulation_policy_map[reg_id] = []
                pol_name = pol.get("title", "Untitled")
                if pol_name not in regulation_policy_map[reg_id]:
                    regulation_policy_map[reg_id].append(pol_name)

    total_regulations = len(regulations)
    mapped_count = 0
    regulation_details = []

    for reg in regulations:
        reg_id = reg.get("id", str(reg.get("_id", "")))
        is_mapped = reg_id in mapped_regulation_ids
        if is_mapped:
            mapped_count += 1

        regulation_details.append({
            "id": reg_id,
            "name": reg.get("title", reg.get("name", "Untitled Regulation")),
            "regulator": reg.get("regulator", "Unknown"),
            "is_mapped": is_mapped,
            "mapped_policies": regulation_policy_map.get(reg_id, []),
            "policy_count": len(regulation_policy_map.get(reg_id, [])),
        })

    # Sort: unmapped first (highlighted), then by name
    regulation_details.sort(key=lambda r: (r["is_mapped"], r["name"]))

    coverage_percentage = int((mapped_count / total_regulations) * 100) if total_regulations > 0 else 0

    return {
        "total_regulations": total_regulations,
        "mapped_regulations": mapped_count,
        "unmapped_regulations": total_regulations - mapped_count,
        "coverage_percentage": coverage_percentage,
        "total_policies": len(policies),
        "regulations": regulation_details
    }


# ========== ANALYTICS EXPORT ENDPOINT (Feature #83) ==========
@api_router.get("/analytics/export")
async def export_analytics(
    format: str = "pdf",
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #83: Export analytics data as PDF or Excel.
    Aggregates compliance score, SLA performance, gaps heatmap, and evidence progress.
    """
    try:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        org = user_doc.get('organization', 'Default')

        # Gather all analytics data
        # 1. Compliance score
        latest = await db.gap_analyses.find_one(
            {"organization": org}, {"_id": 0}, sort=[('created_at', -1)]
        )
        overall_score = latest.get('compliance_score', 0) if latest else 0
        analyses = await db.gap_analyses.find({"organization": org}, {"_id": 0}).to_list(100)
        regulation_scores = {}
        policy_scores = {}
        for a in analyses:
            reg_name = a.get('regulation_title', a.get('regulation_name', 'Unknown'))
            pol_name = a.get('policy_title', a.get('policy_name', 'Unknown'))
            regulation_scores[reg_name] = a.get('compliance_score', 0)
            policy_scores[pol_name] = a.get('compliance_score', 0)

        # 2. SLA data
        total_tasks = await db.tasks.count_documents({"organization": org})
        completed_tasks = await db.tasks.count_documents({"organization": org, "status": {"$in": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}})
        overdue_tasks = await db.tasks.count_documents({
            "organization": org,
            "due_date": {"$lt": datetime.now(timezone.utc)},
            "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
        })
        sla_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 100, 1)

        # 3. Gaps heatmap
        heatmap_data = []
        for a in analyses:
            gaps = a.get('gaps', [])
            severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
            for g in gaps:
                sev = g.get('severity', 'Medium')
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            heatmap_data.append({
                "policy": a.get('policy_title', a.get('policy_name', 'Unknown')),
                "regulation": a.get('regulation_title', a.get('regulation_name', 'Unknown')),
                "total_gaps": len(gaps),
                "severity": severity_counts,
                "compliance_score": a.get('compliance_score', 0)
            })

        # 4. Evidence progress
        total_evidence = await db.evidence.count_documents({"organization": org})
        approved_evidence = await db.evidence.count_documents({"organization": org, "lifecycle_status": {"$in": ["approved", "auto_approved"]}})

        export_timestamp = datetime.now(timezone.utc).isoformat()

        if format == "excel":
            import io
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment
            except ImportError:
                raise HTTPException(status_code=500, detail="openpyxl not installed")

            wb = openpyxl.Workbook()
            emerald_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
            white_font = Font(bold=True, color="FFFFFF", size=11)
            header_font = Font(bold=True, size=14, color="047857")
            subheader_font = Font(bold=True, size=11)

            # Compliance Overview sheet
            ws = wb.active
            ws.title = "Compliance Overview"
            ws.append(["CompliAI Analytics Report"])
            ws['A1'].font = header_font
            ws.append([f"Generated: {export_timestamp[:19]}"])
            ws.append([])
            ws.append(["Overall Compliance Score", f"{overall_score:.1f}%"])
            ws['A4'].font = subheader_font
            ws.append(["Total Tasks", total_tasks])
            ws.append(["Completed Tasks", completed_tasks])
            ws.append(["Overdue Tasks", overdue_tasks])
            ws.append(["SLA Rate", f"{sla_rate}%"])
            ws.append(["Total Evidence", total_evidence])
            ws.append(["Approved Evidence", approved_evidence])
            ws.column_dimensions['A'].width = 30
            ws.column_dimensions['B'].width = 40

            # Regulation Scores sheet
            ws2 = wb.create_sheet("Regulation Scores")
            headers = ["Regulation", "Compliance Score"]
            for col_idx, h in enumerate(headers, 1):
                cell = ws2.cell(row=1, column=col_idx, value=h)
                cell.font = white_font
                cell.fill = emerald_fill
            for row_idx, (name, score) in enumerate(regulation_scores.items(), 2):
                ws2.cell(row=row_idx, column=1, value=name)
                ws2.cell(row=row_idx, column=2, value=f"{score:.1f}%")
            ws2.column_dimensions['A'].width = 60
            ws2.column_dimensions['B'].width = 20

            # Policy Scores sheet
            ws3 = wb.create_sheet("Policy Scores")
            headers = ["Policy", "Compliance Score"]
            for col_idx, h in enumerate(headers, 1):
                cell = ws3.cell(row=1, column=col_idx, value=h)
                cell.font = white_font
                cell.fill = emerald_fill
            for row_idx, (name, score) in enumerate(policy_scores.items(), 2):
                ws3.cell(row=row_idx, column=1, value=name)
                ws3.cell(row=row_idx, column=2, value=f"{score:.1f}%")
            ws3.column_dimensions['A'].width = 60
            ws3.column_dimensions['B'].width = 20

            # Gaps Heatmap sheet
            ws4 = wb.create_sheet("Gaps Heatmap")
            hm_headers = ["Policy", "Regulation", "Score", "Total Gaps", "Critical", "High", "Medium", "Low"]
            for col_idx, h in enumerate(hm_headers, 1):
                cell = ws4.cell(row=1, column=col_idx, value=h)
                cell.font = white_font
                cell.fill = emerald_fill
            for row_idx, item in enumerate(heatmap_data, 2):
                ws4.cell(row=row_idx, column=1, value=item['policy'])
                ws4.cell(row=row_idx, column=2, value=item['regulation'])
                ws4.cell(row=row_idx, column=3, value=f"{item['compliance_score']:.1f}%")
                ws4.cell(row=row_idx, column=4, value=item['total_gaps'])
                ws4.cell(row=row_idx, column=5, value=item['severity'].get('Critical', 0))
                ws4.cell(row=row_idx, column=6, value=item['severity'].get('High', 0))
                ws4.cell(row=row_idx, column=7, value=item['severity'].get('Medium', 0))
                ws4.cell(row=row_idx, column=8, value=item['severity'].get('Low', 0))
            for col in range(1, 9):
                ws4.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20

            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            filename = f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            return StreamingResponse(
                iter([buffer.getvalue()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        elif format == "pdf":
            import io
            try:
                from fpdf import FPDF
            except ImportError:
                raise HTTPException(status_code=500, detail="fpdf2 not installed")

            def _clean_a(text):
                if not text:
                    return ""
                return text.encode('latin-1', 'replace').decode('latin-1')

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            pdf.set_font('Helvetica', 'B', 18)
            pdf.set_text_color(4, 120, 87)
            pdf.cell(0, 12, 'CompliAI Analytics Report', ln=True, align='C')
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 6, f'Generated: {export_timestamp[:19]}', ln=True, align='C')
            pdf.ln(8)

            pdf.set_font('Helvetica', 'B', 14)
            pdf.set_text_color(4, 120, 87)
            pdf.cell(0, 8, 'Compliance Overview', ln=True)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 6, f'Overall Compliance Score: {overall_score:.1f}%', ln=True)
            pdf.cell(0, 6, f'Total Tasks: {total_tasks} | Completed: {completed_tasks} | Overdue: {overdue_tasks}', ln=True)
            pdf.cell(0, 6, f'SLA Rate: {sla_rate}%', ln=True)
            pdf.cell(0, 6, f'Evidence: {approved_evidence} approved of {total_evidence} total', ln=True)
            pdf.ln(5)

            if regulation_scores:
                pdf.set_font('Helvetica', 'B', 12)
                pdf.set_text_color(4, 120, 87)
                pdf.cell(0, 8, 'Regulation Compliance Scores', ln=True)
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(0, 0, 0)
                for name, score in regulation_scores.items():
                    pdf.cell(0, 5, _clean_a(f'  {name}: {score:.1f}%'), ln=True)
                pdf.ln(5)

            if policy_scores:
                pdf.set_font('Helvetica', 'B', 12)
                pdf.set_text_color(4, 120, 87)
                pdf.cell(0, 8, 'Policy Compliance Scores', ln=True)
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(0, 0, 0)
                for name, score in policy_scores.items():
                    pdf.cell(0, 5, _clean_a(f'  {name}: {score:.1f}%'), ln=True)
                pdf.ln(5)

            if heatmap_data:
                pdf.set_font('Helvetica', 'B', 12)
                pdf.set_text_color(4, 120, 87)
                pdf.cell(0, 8, 'Gaps Heatmap', ln=True)
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(0, 0, 0)
                for item in heatmap_data:
                    if pdf.get_y() > 260:
                        pdf.add_page()
                    pdf.cell(0, 5, _clean_a(f'{item["policy"]} vs {item["regulation"]}'), ln=True)
                    pdf.cell(0, 5, f'  Score: {item["compliance_score"]:.1f}% | Gaps: {item["total_gaps"]} (Critical: {item["severity"].get("Critical", 0)}, High: {item["severity"].get("High", 0)}, Medium: {item["severity"].get("Medium", 0)}, Low: {item["severity"].get("Low", 0)})', ln=True)
                    pdf.ln(2)

            buffer = io.BytesIO()
            pdf.output(buffer)
            buffer.seek(0)
            filename = f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            return StreamingResponse(
                iter([buffer.getvalue()]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use pdf or excel.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting analytics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ========== CHAT THREAD ENDPOINTS ==========
@api_router.get("/chat/threads")
async def get_chat_threads(current_user: dict = Depends(get_current_user)):
    """Get all chat threads/sessions for the user."""
    pipeline = [
        {"$match": {"user_id": current_user['user_id']}},
        {"$group": {
            "_id": "$session_id",
            "last_message": {"$last": "$content"},
            "last_role": {"$last": "$role"},
            "message_count": {"$sum": 1},
            "created_at": {"$min": "$created_at"},
            "updated_at": {"$max": "$created_at"}
        }},
        {"$sort": {"updated_at": -1}}
    ]
    threads = await db.chat_messages.aggregate(pipeline).to_list(100)
    
    result = []
    for t in threads:
        result.append({
            "session_id": t['_id'],
            "last_message": t['last_message'][:100] if t['last_message'] else '',
            "message_count": t['message_count'],
            "created_at": t.get('created_at'),
            "updated_at": t.get('updated_at')
        })
    
    return result

@api_router.get("/chat/insights")
async def get_chat_insights(current_user: dict = Depends(get_current_user)):
    """Generate proactive AI insights based on actual platform data for the chat welcome message."""
    try:
        user_id = current_user['user_id']
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
        org = user_doc.get('organization', 'Default') if user_doc else 'Default'

        policy_count = await db.policies.count_documents({"user_id": user_id})
        regulation_count = await db.regulations.count_documents({
            "$or": [{"user_id": user_id}, {"user_id": "system"}]
        })

        recent_analyses = await db.gap_analyses.find(
            {"user_id": user_id},
            {"_id": 0, "compliance_score": 1, "created_at": 1, "gaps": 1,
             "fully_compliant_count": 1, "non_compliant_count": 1, "partially_compliant_count": 1}
        ).sort("created_at", -1).limit(5).to_list(5)

        total_tasks = await db.tasks.count_documents({"user_id": user_id})
        open_tasks = await db.tasks.count_documents({"user_id": user_id, "status": {"$in": ["Open", "open", "pending"]}})
        overdue_tasks_list = await db.tasks.find(
            {"user_id": user_id, "status": {"$nin": ["Completed", "completed", "done"]},
             "due_date": {"$lt": datetime.now(timezone.utc).isoformat()}},
            {"_id": 0, "title": 1, "priority": 1}
        ).limit(5).to_list(5)
        overdue_count = len(overdue_tasks_list)

        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        new_regulations = await db.regulations.find(
            {"$or": [{"user_id": user_id}, {"user_id": "system"}],
             "created_at": {"$gte": thirty_days_ago}},
            {"_id": 0, "title": 1, "id": 1}
        ).limit(10).to_list(10)
        new_reg_count = len(new_regulations)

        insights_parts = []
        insights_parts.append("👋 **Welcome back!** Here's your compliance overview:\n")

        if recent_analyses:
            latest = recent_analyses[0]
            score = latest.get('compliance_score', 0)
            score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
            insights_parts.append(f"{score_emoji} **Compliance Score: {score:.1f}%** (latest analysis)")
            critical_gaps = sum(1 for g in (latest.get('gaps') or []) if g.get('severity') in ['Critical', 'critical'])
            high_gaps = sum(1 for g in (latest.get('gaps') or []) if g.get('severity') in ['High', 'high'])
            if critical_gaps > 0 or high_gaps > 0:
                insights_parts.append(f"⚠️ **{critical_gaps} critical** and **{high_gaps} high** severity gaps need attention → [View Gap Analysis](/gap-analysis)")
        else:
            insights_parts.append("📊 No gap analyses run yet → [Run your first analysis](/gap-analysis)")

        if new_reg_count > 0:
            affected_policies = min(policy_count, new_reg_count * 2)
            insights_parts.append(f"📋 **You have {new_reg_count} new circulars** affecting up to **{affected_policies} policies** → [View Regulations](/regulations)")

        if overdue_count > 0:
            insights_parts.append(f"🔴 **{overdue_count} overdue tasks** require immediate action → [View Tasks](/tasks)")
        elif open_tasks > 0:
            insights_parts.append(f"📌 **{open_tasks} open tasks** pending completion → [View Tasks](/tasks)")

        insights_parts.append(f"\n📈 **Platform Summary:** {policy_count} policies · {regulation_count} regulations · {total_tasks} tasks")

        suggestions = []
        if not recent_analyses:
            suggestions.append("Run a gap analysis to assess compliance posture")
        elif recent_analyses[0].get('compliance_score', 100) < 70:
            suggestions.append("Address critical gaps to improve compliance score")
        if overdue_count > 0:
            suggestions.append("Clear overdue tasks to maintain regulatory standing")
        if new_reg_count > 0:
            suggestions.append("Review new regulations for potential policy impacts")

        if suggestions:
            insights_parts.append("\n💡 **Suggested Actions:**")
            for s in suggestions:
                insights_parts.append(f"  • {s}")

        return {
            "insight": "\n".join(insights_parts),
            "data": {
                "compliance_score": recent_analyses[0].get('compliance_score') if recent_analyses else None,
                "policy_count": policy_count,
                "regulation_count": regulation_count,
                "new_regulation_count": new_reg_count,
                "open_tasks": open_tasks,
                "overdue_tasks": overdue_count,
                "total_tasks": total_tasks,
                "has_analyses": len(recent_analyses) > 0
            }
        }
    except Exception as e:
        logger.error(f"Error generating chat insights: {str(e)}")
        return {"insight": "👋 Welcome! I'm NeoGPT, your BFSI compliance assistant. How can I help you today?", "data": {}}

@api_router.get("/chat/threads/{session_id}")
async def get_chat_thread_messages(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get all messages in a chat thread."""
    messages = await db.chat_messages.find(
        {"session_id": session_id, "user_id": current_user['user_id']},
        {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    
    for m in messages:
        if isinstance(m.get('created_at'), str):
            m['created_at'] = datetime.fromisoformat(m['created_at'])
    
    return messages

@api_router.get("/chat/search")
async def search_chat_messages(q: str, current_user: dict = Depends(get_current_user)):
    """Search through chat messages."""
    # Sanitize search query: trim whitespace, escape regex special chars, limit length
    sanitized_q = q.strip()
    if not sanitized_q:
        return []  # Return empty for whitespace-only or empty queries
    # Limit query length to prevent abuse
    sanitized_q = sanitized_q[:500]
    # Escape regex special characters to prevent regex injection
    escaped_q = re.escape(sanitized_q)

    messages = await db.chat_messages.find(
        {
            "user_id": current_user['user_id'],
            "content": {"$regex": escaped_q, "$options": "i"}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    for m in messages:
        if isinstance(m.get('created_at'), str):
            m['created_at'] = datetime.fromisoformat(m['created_at'])

    return messages

# ========== LOS/LMS ENDPOINTS ==========
@api_router.post("/los-lms/upload")
async def upload_los_lms_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload CSV/Excel file with loan data."""
    try:
        import json
        file_content = await file.read()
        file_path = await doc_service.save_file(file_content, file.filename)
        
        # Parse file for preview
        records = []
        if file.filename.endswith('.csv'):
            import csv, io
            text = file_content.decode('utf-8', errors='ignore')
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                records.append(dict(row))
                if len(records) >= 100:
                    break
        
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        
        upload_record = {
            "id": str(uuid.uuid4()),
            "file_name": file.filename,
            "file_path": file_path,
            "record_count": len(records),
            "preview": records[:10],
            "columns": list(records[0].keys()) if records else [],
            "user_id": current_user['user_id'],
            "organization": user_doc.get('organization', 'Default'),
            "status": "uploaded",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.los_lms_uploads.insert_one(upload_record)
        
        return {
            "message": "File uploaded and parsed",
            "upload_id": upload_record['id'],
            "record_count": len(records),
            "columns": upload_record['columns'],
            "preview": records[:10]
        }
    except Exception as e:
        logger.error(f"Error uploading LOS/LMS file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.get("/los-lms/uploads")
async def get_los_lms_uploads(current_user: dict = Depends(get_current_user)):
    uploads = await db.los_lms_uploads.find({"user_id": current_user['user_id']}, {"_id": 0}).to_list(100)
    return uploads

@api_router.post("/los-lms/suggest-mapping")
async def suggest_field_mapping(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Use AI (Claude Sonnet) to suggest field mappings from uploaded file columns to compliance fields."""
    try:
        columns = request.get("columns", [])
        if not columns:
            raise HTTPException(status_code=400, detail="No columns provided")

        # Required compliance fields
        required_fields = {
            "borrower_name": "Full name of the borrower",
            "loan_amount": "Principal loan amount",
            "interest_rate": "Annual interest rate (%)",
            "tenure_months": "Loan tenure in months",
            "disbursement_date": "Loan disbursement date",
            "processing_fee": "Processing fee charged",
            "insurance": "Insurance amount",
            "emi_amount": "EMI amount",
            "annual_income": "Borrower annual income",
            "credit_score": "CIBIL/credit score",
            "kyc_status": "KYC verification status",
            "cibil_consent": "CIBIL consent",
            "sanction_letter": "Sanction letter issued",
            "loan_agreement": "Loan agreement signed"
        }

        # Build prompt
        prompt = f"""Analyze column names and map to compliance fields.

Uploaded columns: {', '.join(columns)}

Required fields:
{chr(10).join([f'- {f}: {d}' for f, d in required_fields.items()])}

Output JSON:
{{
  "mappings": [
    {{"source_column": "col", "target_field": "field_or_unmapped", "confidence": 0.95, "reasoning": "match type"}}
  ]
}}

Be smart: "Customer Name" → borrower_name, "Loan Amt" → loan_amount, "ROI" → interest_rate."""

        # Try AI mapping
        from services.anthropic_utils import create_anthropic_client
        client = create_anthropic_client()

        if client:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            result_text = response.content[0].text
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)
            return {"mappings": result.get("mappings", []), "ai_used": True}

        # Fallback: simple string matching
        mappings = []
        for col in columns:
            normalized = col.lower().replace(' ', '_').replace('-', '_')
            target = "unmapped"
            confidence = 0.0
            reasoning = "No match"

            if normalized in required_fields:
                target = normalized
                confidence = 1.0
                reasoning = "Exact match"
            else:
                for req_field in required_fields.keys():
                    if req_field in normalized or normalized in req_field:
                        target = req_field
                        confidence = 0.7
                        reasoning = "Partial match"
                        break

            mappings.append({
                "source_column": col,
                "target_field": target,
                "confidence": confidence,
                "reasoning": reasoning
            })

        return {"mappings": mappings, "ai_used": False}

    except Exception as e:
        logger.error(f"Error in suggest_field_mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/los-lms/save-mapping")
async def save_field_mapping(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Save field mapping configuration for reuse."""
    try:
        mapping_name = request.get("mapping_name", "Default Mapping")
        field_mappings = request.get("field_mappings", {})

        mapping_record = {
            "id": str(uuid.uuid4()),
            "user_id": current_user['user_id'],
            "mapping_name": mapping_name,
            "field_mappings": field_mappings,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        await db.los_lms_mappings.insert_one(mapping_record)
        return {"message": "Mapping saved successfully", "mapping_id": mapping_record['id']}

    except Exception as e:
        logger.error(f"Error saving field mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/los-lms/mappings")
async def get_saved_mappings(current_user: dict = Depends(get_current_user)):
    """Get all saved field mapping configurations."""
    try:
        mappings = await db.los_lms_mappings.find(
            {"user_id": current_user['user_id']},
            {"_id": 0}
        ).to_list(100)
        return mappings
    except Exception as e:
        logger.error(f"Error getting saved mappings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/los-lms/{upload_id}/scan")
async def scan_los_lms_compliance(upload_id: str, current_user: dict = Depends(get_current_user)):
    """Run compliance scanning on uploaded LOS/LMS data with real RBI regulation checks."""
    upload = await db.los_lms_uploads.find_one({"id": upload_id, "user_id": current_user['user_id']}, {"_id": 0})
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Real compliance scanning based on RBI regulations
    records = upload.get('preview', [])
    loan_level_results = []
    exceptions = []
    compliant_count = 0
    non_compliant_count = 0

    # Portfolio-level metrics
    total_loan_amount = 0
    avg_interest_rate = 0
    kyc_compliant_count = 0
    cibil_consent_count = 0

    for i, record in enumerate(records):
        record_exceptions = []
        is_compliant = True

        # Required field checks
        if not record.get('kyc_status') or str(record.get('kyc_status', '')).strip().lower() not in ['completed', 'verified', 'yes', 'true', '1']:
            record_exceptions.append({
                "field": "kyc_status",
                "issue": "KYC not completed or missing",
                "severity": "Critical",
                "regulation_ref": "RBI KYC Master Direction 2016",
                "recommendation": "Complete KYC verification before loan disbursement"
            })
            is_compliant = False
        else:
            kyc_compliant_count += 1

        if not record.get('cibil_consent') or str(record.get('cibil_consent', '')).strip().lower() not in ['yes', 'true', '1', 'obtained']:
            record_exceptions.append({
                "field": "cibil_consent",
                "issue": "CIBIL consent not obtained",
                "severity": "High",
                "regulation_ref": "RBI Fair Practices Code",
                "recommendation": "Obtain explicit consent for credit bureau check"
            })
            is_compliant = False
        else:
            cibil_consent_count += 1

        if not record.get('sanction_letter') or str(record.get('sanction_letter', '')).strip().lower() not in ['issued', 'yes', 'true', '1']:
            record_exceptions.append({
                "field": "sanction_letter",
                "issue": "Sanction letter not issued",
                "severity": "High",
                "regulation_ref": "RBI Fair Practices Code",
                "recommendation": "Issue sanction letter with all terms before disbursement"
            })
            is_compliant = False

        if not record.get('loan_agreement') or str(record.get('loan_agreement', '')).strip().lower() not in ['signed', 'yes', 'true', '1']:
            record_exceptions.append({
                "field": "loan_agreement",
                "issue": "Loan agreement not signed",
                "severity": "Critical",
                "regulation_ref": "RBI Lending Guidelines",
                "recommendation": "Obtain signed loan agreement before disbursement"
            })
            is_compliant = False

        # Numerical validations
        try:
            interest_rate = float(record.get('interest_rate', 0))
            if interest_rate > 36:  # RBI cap for NBFCs
                record_exceptions.append({
                    "field": "interest_rate",
                    "issue": f"Interest rate {interest_rate}% exceeds RBI cap of 36%",
                    "severity": "Critical",
                    "regulation_ref": "RBI NBFC Directions 2024",
                    "recommendation": "Reduce interest rate to comply with RBI cap"
                })
                is_compliant = False
            avg_interest_rate += interest_rate
        except (ValueError, TypeError):
            record_exceptions.append({
                "field": "interest_rate",
                "issue": "Interest rate is missing or invalid",
                "severity": "High",
                "regulation_ref": "RBI Fair Practices Code",
                "recommendation": "Specify valid interest rate"
            })
            is_compliant = False

        try:
            loan_amount = float(record.get('loan_amount', 0))
            total_loan_amount += loan_amount
            processing_fee = float(record.get('processing_fee', 0))
            # Processing fee should not exceed 2% of loan amount (industry standard)
            if loan_amount > 0 and processing_fee > (loan_amount * 0.02):
                record_exceptions.append({
                    "field": "processing_fee",
                    "issue": f"Processing fee ₹{processing_fee} exceeds 2% of loan amount",
                    "severity": "Medium",
                    "regulation_ref": "RBI Fair Practices Code",
                    "recommendation": "Reduce processing fee to reasonable levels"
                })
                is_compliant = False
        except (ValueError, TypeError):
            pass  # Optional fee validation

        try:
            credit_score = float(record.get('credit_score', 0))
            if credit_score > 0 and credit_score < 300:  # Minimum CIBIL score
                record_exceptions.append({
                    "field": "credit_score",
                    "issue": f"Credit score {credit_score} below minimum threshold",
                    "severity": "High",
                    "regulation_ref": "RBI Credit Assessment Guidelines",
                    "recommendation": "Require minimum credit score of 300 or additional collateral"
                })
                is_compliant = False
        except (ValueError, TypeError):
            pass  # Credit score validation

        # Add to loan-level results
        loan_level_results.append({
            "record_index": i,
            "borrower_name": record.get('borrower_name', f'Record {i+1}'),
            "loan_amount": record.get('loan_amount'),
            "is_compliant": is_compliant,
            "exceptions_count": len(record_exceptions),
            "exceptions": record_exceptions
        })

        # Track exceptions and counts
        if is_compliant:
            compliant_count += 1
        else:
            non_compliant_count += 1
            for exc in record_exceptions:
                exceptions.append({
                    "record_index": i,
                    "borrower_name": record.get('borrower_name', f'Record {i+1}'),
                    **exc
                })

    # Calculate portfolio-level metrics
    total_records = len(records)
    compliance_score = (compliant_count / total_records * 100) if total_records > 0 else 0
    avg_interest_rate = (avg_interest_rate / total_records) if total_records > 0 else 0

    portfolio_metrics = {
        "total_records": total_records,
        "compliant_records": compliant_count,
        "non_compliant_records": non_compliant_count,
        "compliance_score": round(compliance_score, 2),
        "total_loan_amount": total_loan_amount,
        "average_interest_rate": round(avg_interest_rate, 2),
        "kyc_compliance_rate": round((kyc_compliant_count / total_records * 100) if total_records > 0 else 0, 2),
        "cibil_consent_rate": round((cibil_consent_count / total_records * 100) if total_records > 0 else 0, 2),
        "total_exceptions": len(exceptions),
        "critical_exceptions": len([e for e in exceptions if e.get('severity') == 'Critical']),
        "high_exceptions": len([e for e in exceptions if e.get('severity') == 'High']),
        "medium_exceptions": len([e for e in exceptions if e.get('severity') == 'Medium'])
    }

    scan_result = {
        "upload_id": upload_id,
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "loan_level_results": loan_level_results,
        "portfolio_metrics": portfolio_metrics,
        "exceptions": exceptions,
        # Legacy fields for backward compatibility
        "total_records": total_records,
        "compliant": compliant_count,
        "non_compliant": non_compliant_count,
        "issues": exceptions
    }

    # Update upload with scan results and compliance score
    await db.los_lms_uploads.update_one(
        {"id": upload_id},
        {"$set": {
            "scan_result": scan_result,
            "scan_status": "scanned",
            "compliance_score": round(compliance_score, 2)
        }}
    )

    # Feature #68: Create remediation tasks for exceptions
    created_tasks = []
    if exceptions:
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        user_name = user_doc.get('full_name', 'System')

        for exception in exceptions:
            # Map severity to priority
            priority_map = {
                "Critical": "High",
                "High": "High",
                "Medium": "Medium"
            }
            priority = priority_map.get(exception.get('severity'), 'Medium')

            # Create task for each exception
            task_id = str(uuid.uuid4())
            task = Task(
                id=task_id,
                title=f"LOS/LMS Compliance: {exception.get('issue')}",
                description=f"""Loan Compliance Exception Detected

**Borrower:** {exception.get('borrower_name', 'Unknown')}
**Field:** {exception.get('field')}
**Issue:** {exception.get('issue')}
**Regulation:** {exception.get('regulation_ref')}

**Remediation Required:**
{exception.get('recommendation')}

**Upload:** {upload.get('filename', 'N/A')}
**Record Index:** {exception.get('record_index', 'N/A')}
""",
                priority=priority,
                status="Open",
                category="LOS/LMS Compliance",
                created_by=user_name,
                user_id=current_user['user_id'],
                organization=user_doc.get('organization', 'Default'),
                metadata={
                    "source": "los_lms_scan",
                    "upload_id": upload_id,
                    "record_index": exception.get('record_index'),
                    "borrower_name": exception.get('borrower_name'),
                    "exception_field": exception.get('field'),
                    "severity": exception.get('severity'),
                    "regulation_ref": exception.get('regulation_ref'),
                    "recommendation": exception.get('recommendation')
                }
            )

            task_dict = task.model_dump()
            task_dict['created_at'] = task_dict['created_at'].isoformat()
            task_dict['updated_at'] = task_dict['updated_at'].isoformat()
            if task_dict.get('due_date'):
                task_dict['due_date'] = task_dict['due_date'].isoformat()

            await db.tasks.insert_one(task_dict)
            created_tasks.append({
                "task_id": task_id,
                "title": task.title,
                "priority": priority,
                "exception_field": exception.get('field')
            })

    # Add created tasks to scan result
    scan_result['created_tasks'] = created_tasks
    scan_result['tasks_created_count'] = len(created_tasks)

    return scan_result

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
        # Get user organization
        user_doc = await db.users.find_one({"id": current_user['user_id']}, {"_id": 0})
        organization = user_doc.get('organization', 'Default') if user_doc else 'Default'

        # Get chat history
        history = await db.chat_messages.find(
            {"session_id": message.session_id, "user_id": current_user['user_id']},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)

        context = [{"role": msg['role'], "content": msg['content']} for msg in reversed(history)]

        # Get AI response with action capabilities and RAG over uploaded policies
        response_text = await llm_service.chat_response(
            message.content,
            context,
            db=db,
            user_id=current_user['user_id'],
            organization=organization,
            vector_service=vector_service
        )
        
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
    gap_severity_distribution = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    if latest_analysis and latest_analysis.get('gaps'):
        for g in latest_analysis['gaps']:
            severity = g.get('severity', 'Medium')
            gap_severity_distribution[severity] = gap_severity_distribution.get(severity, 0) + 1
            if severity == 'Critical':
                critical_gaps += 1
    
    high_priority_tasks = await db.tasks.count_documents({
        "organization": org,
        "priority": SeverityLevel.HIGH
    })
    
    departments = await db.departments.find({"organization": org}, {"_id": 0}).to_list(1000)
    departments_count = len(departments)
    non_compliant_departments = len([d for d in departments if d.get('compliance_status') == ComplianceStatus.NON_COMPLIANT])
    
    pending_actionables = await db.tasks.count_documents({
        "organization": org,
        "status": {"$in": [TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.PENDING_EVIDENCE]}
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
        status = dept.get('compliance_status') or 'Noted for Compliance'
        if status not in compliance_by_status:
            status = 'Noted for Compliance'
        compliance_by_status[status] = compliance_by_status.get(status, 0) + 1
    
    # Compliance by department - include all departments
    compliance_by_department = []
    for dept in departments:
        dept_tasks = await db.tasks.count_documents({"organization": org, "department_id": dept.get('id')})
        dept_completed = await db.tasks.count_documents({"organization": org, "department_id": dept.get('id'), "status": {"$in": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}})
        dept_overdue = await db.tasks.count_documents({
            "organization": org, 
            "department_id": dept.get('id'),
            "due_date": {"$lt": datetime.now(timezone.utc)},
            "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
        })
        dept_score = (dept_completed / dept_tasks * 100) if dept_tasks > 0 else 0
        compliance_by_department.append({
            "department": dept.get('name'),
            "compliance_status": dept.get('compliance_status') or 'Noted for Compliance',
            "total_tasks": dept_tasks,
            "completed_tasks": dept_completed,
            "overdue_tasks": dept_overdue,
            "compliance_score": round(dept_score, 1)
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
            "regulator": reg['_id'] or "RBI",
            "circulars_count": reg['count'],
            "compliance_status": "Review Pending"
        })
    
    # Tasks by status
    tasks_by_status = {}
    for status in TaskStatus:
        count = await db.tasks.count_documents({"organization": org, "status": status})
        tasks_by_status[status.value] = count
    
    # Tasks by priority
    tasks_by_priority = {}
    for priority in SeverityLevel:
        count = await db.tasks.count_documents({"organization": org, "priority": priority})
        tasks_by_priority[priority.value] = count
    
    # Compliance trend (last 6 months simulated from gap analyses)
    compliance_trend = []
    analyses = await db.gap_analyses.find(
        {"organization": org},
        {"_id": 0, "created_at": 1, "compliance_score": 1}
    ).sort("created_at", 1).to_list(100)
    
    if analyses:
        for analysis in analyses[-6:]:
            compliance_trend.append({
                "date": analysis['created_at'].strftime("%b %Y") if isinstance(analysis.get('created_at'), datetime) else "Recent",
                "score": analysis.get('compliance_score', 0)
            })
    else:
        # Generate sample trend data
        months = ["Aug 2025", "Sep 2025", "Oct 2025", "Nov 2025", "Dec 2025", "Jan 2026"]
        scores = [35, 42, 48, 55, 52, compliance_score]
        for month, score in zip(months, scores):
            compliance_trend.append({"date": month, "score": score})
    
    # Recent activities (from tasks, policies, regulations)
    recent_activities = []
    
    # Recent tasks
    recent_tasks = await db.tasks.find(
        {"organization": org},
        {"_id": 0, "title": 1, "status": 1, "updated_at": 1, "priority": 1, "assignee_name": 1}
    ).sort("updated_at", -1).limit(5).to_list(5)
    for task in recent_tasks:
        updated_at = task.get('updated_at')
        time_str = None
        if updated_at:
            time_str = updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at)
        recent_activities.append({
            "type": "task_update",
            "title": task.get('title', 'Task'),
            "status": task.get('status', 'Open'),
            "priority": task.get('priority', 'Medium'),
            "time": time_str,
            "user": task.get('assignee_name', user_doc.get('full_name', 'System'))
        })
    
    # Recent policies
    recent_policies = await db.policies.find(
        {"organization": org},
        {"_id": 0, "title": 1, "status": 1, "updated_at": 1, "created_at": 1}
    ).sort("updated_at", -1).limit(3).to_list(3)
    for pol in recent_policies:
        updated_at = pol.get('updated_at') or pol.get('created_at')
        time_str = None
        if updated_at:
            time_str = updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at)
        recent_activities.append({
            "type": "policy_update",
            "title": f"Policy: {pol.get('title', 'Untitled')}",
            "status": pol.get('status', 'Draft'),
            "priority": "Medium",
            "time": time_str,
            "user": user_doc.get('full_name', 'System')
        })
    
    # Sort all activities by time, most recent first
    recent_activities.sort(key=lambda x: x.get('time') or '', reverse=True)
    recent_activities = recent_activities[:10]
    
    # Upcoming deadlines
    upcoming_deadlines = []
    upcoming_tasks = await db.tasks.find(
        {
            "organization": org,
            "due_date": {"$gte": datetime.now(timezone.utc)},
            "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
        },
        {"_id": 0, "title": 1, "due_date": 1, "priority": 1, "department_id": 1}
    ).sort("due_date", 1).limit(5).to_list(5)
    for task in upcoming_tasks:
        due_date = task.get('due_date')
        due_date_str = None
        days_remaining = 0
        if due_date:
            if hasattr(due_date, 'isoformat'):
                due_date_str = due_date.isoformat()
                days_remaining = (due_date - datetime.now(timezone.utc)).days
            else:
                due_date_str = str(due_date)
                try:
                    parsed = datetime.fromisoformat(str(due_date).replace('Z', '+00:00'))
                    days_remaining = (parsed - datetime.now(timezone.utc)).days
                except:
                    days_remaining = 0
        upcoming_deadlines.append({
            "title": task.get('title', 'Task'),
            "due_date": due_date_str,
            "priority": task.get('priority', 'Medium'),
            "days_remaining": days_remaining
        })
    
    # Monthly task completion (last 6 months)
    monthly_task_completion = []
    months_data = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
    completed_count = await db.tasks.count_documents({"organization": org, "status": {"$in": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}})
    base = max(1, completed_count // 6)
    for i, month in enumerate(months_data):
        monthly_task_completion.append({
            "month": month,
            "completed": base + (i * 2),
            "created": base + 3 + (i % 3)
        })
    
    # Policy coverage
    policy_types_covered = await db.policies.distinct("policy_type", {"organization": org})
    all_policy_types = [pt.value for pt in PolicyType]
    policy_coverage = {
        "covered": len(policy_types_covered),
        "total": len(all_policy_types),
        "percentage": round(len(policy_types_covered) / len(all_policy_types) * 100, 1) if all_policy_types else 0,
        "types_covered": policy_types_covered,
        "types_missing": [pt for pt in all_policy_types if pt not in policy_types_covered]
    }
    
    # Risk metrics
    critical_task_count = await db.tasks.count_documents({"organization": org, "priority": SeverityLevel.CRITICAL})
    high_task_count = await db.tasks.count_documents({"organization": org, "priority": SeverityLevel.HIGH})
    medium_task_count = await db.tasks.count_documents({"organization": org, "priority": SeverityLevel.MEDIUM})
    overdue_count = await db.tasks.count_documents({
        "organization": org,
        "due_date": {"$lt": datetime.now(timezone.utc)},
        "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
    })
    # Open (non-completed) tasks count for risk calculation
    open_risk_tasks = await db.tasks.count_documents({
        "organization": org,
        "status": {"$nin": [TaskStatus.COMPLETED, TaskStatus.CLOSED]}
    })
    # Risk score: weighted percentage of open tasks that are critical/high/overdue
    # Formula: weighted risk items / total tasks, scaled to 0-100
    if total_tasks > 0:
        # Weight: Critical=4, High=2, overdue adds 3 per task
        weighted_risk = (critical_task_count * 4) + (high_task_count * 2) + (overdue_count * 3)
        max_possible = total_tasks * 4  # if every task were critical
        risk_score = min(100, round((weighted_risk / max_possible) * 100))
    else:
        risk_score = 0
    risk_metrics = {
        "high_risk_items": critical_task_count + high_task_count,
        "medium_risk_items": medium_task_count,
        "overdue_tasks": overdue_count,
        "risk_score": risk_score,
        "trend": "improving" if compliance_score > 50 else "needs_attention"
    }
    
    # Feature #219: Include NPCI circular stats in dashboard
    try:
        npci_circular_count = await db.npci_circulars.count_documents({})
        npci_processed_count = await db.npci_circulars.count_documents({"processed_at": {"$ne": None}})
        if npci_circular_count > 0:
            # Add NPCI to regulator overview if not already present
            npci_exists = any(r.get('regulator') == 'NPCI' for r in regulator_overview)
            if not npci_exists:
                regulator_overview.append({
                    "regulator": "NPCI",
                    "circulars_count": npci_circular_count,
                    "compliance_status": "Review Pending" if npci_processed_count < npci_circular_count else "Reviewed"
                })
            # Include NPCI circulars in total regulation count
            total_regulations += npci_circular_count
    except Exception as e:
        logger.warning(f"Failed to include NPCI stats in dashboard: {e}")

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
        regulator_overview=regulator_overview,
        tasks_by_status=tasks_by_status,
        tasks_by_priority=tasks_by_priority,
        compliance_trend=compliance_trend,
        recent_activities=recent_activities,
        upcoming_deadlines=upcoming_deadlines,
        gap_severity_distribution=gap_severity_distribution,
        monthly_task_completion=monthly_task_completion,
        policy_coverage=policy_coverage,
        risk_metrics=risk_metrics
    )

@api_router.get("/")
async def root():
    return {"message": "CompliAI API - Production Ready"}


# ========== WEBSOCKET ENDPOINT ==========
@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time upload progress updates."""
    try:
        # Validate token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload['user_id']
    except jwt.ExpiredSignatureError:
        await websocket.close(code=4001, reason="Token expired")
        return
    except jwt.InvalidTokenError:
        await websocket.close(code=4002, reason="Invalid token")
        return
    
    await connection_manager.connect(websocket, user_id)
    
    try:
        # Send initial list of active jobs
        if upload_job_service:
            active_jobs = await upload_job_service.get_active_jobs(user_id)
            await websocket.send_json({
                "type": "active_jobs",
                "jobs": active_jobs
            })
        
        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle ping/pong for keep-alive
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
    finally:
        await connection_manager.disconnect(websocket, user_id)


# ========== UPLOAD JOB ENDPOINTS ==========
@api_router.get("/upload-jobs")
async def get_upload_jobs(
    include_completed: bool = True,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get upload jobs for the current user."""
    jobs = await upload_job_service.get_user_jobs(
        user_id=current_user['user_id'],
        limit=limit,
        include_completed=include_completed
    )
    return jobs


@api_router.get("/upload-jobs/active")
async def get_active_upload_jobs(current_user: dict = Depends(get_current_user)):
    """Get active (in-progress) upload jobs."""
    jobs = await upload_job_service.get_active_jobs(current_user['user_id'])
    return jobs


@api_router.get("/upload-jobs/{job_id}")
async def get_upload_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific upload job."""
    job = await upload_job_service.get_job(job_id)
    if not job or job.get('user_id') != current_user['user_id']:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@api_router.delete("/upload-jobs/{job_id}")
async def delete_upload_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an upload job from history."""
    success = await upload_job_service.delete_job(job_id, current_user['user_id'])
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted"}


@api_router.post("/upload-jobs/{job_id}/cancel")
async def cancel_upload_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Cancel an in-progress upload job."""
    success = await upload_job_service.cancel_job(job_id, current_user['user_id'])
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel job - either not found or already completed")
    return {"message": "Job cancelled"}


@api_router.delete("/upload-jobs")
async def clear_completed_jobs(current_user: dict = Depends(get_current_user)):
    """Clear all completed/failed jobs."""
    count = await upload_job_service.clear_completed_jobs(current_user['user_id'])
    return {"message": f"Cleared {count} jobs"}


# Test endpoint to simulate server errors (for testing error handling)
@api_router.get("/test/error-500")
async def test_error_500():
    """Simulates a 500 internal server error for testing error handling."""
    raise HTTPException(status_code=500, detail="Internal Server Error")

# Test endpoint to create LOS/LMS upload data for Feature #67 testing
@api_router.post("/test/create-los-upload")
async def test_create_los_upload(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Create test LOS/LMS upload for Feature #67 compliance scanning testing."""
    upload_id = data.get('upload_id', str(uuid.uuid4()))
    filename = data.get('filename', 'test_loans.csv')
    records = data.get('records', [])

    upload_doc = {
        "id": upload_id,
        "upload_id": upload_id,
        "user_id": current_user['user_id'],
        "filename": filename,
        "file_name": filename,
        "record_count": len(records),
        "total_records": len(records),
        "preview": records,
        "headers": list(records[0].keys()) if records else [],
        "columns": list(records[0].keys()) if records else [],
        "status": "uploaded",
        "scan_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await db.los_lms_uploads.insert_one(upload_doc)

    return {
        "message": "Test upload created successfully",
        "upload_id": upload_id,
        "records": len(records)
    }

# ==========================================
# LLM Provider Status & Mode Endpoints
# ==========================================

async def _get_llm_health_and_status():
    """
    Helper: compute current LLM provider status, model, and health.
    Used by both /llm/status and /settings/llm-mode endpoints.
    """
    import httpx as _httpx
    use_local = is_using_local_llm()
    provider = get_llm_provider()
    provider_name = provider.get_provider_name()

    # Determine model name
    if isinstance(provider, OllamaProvider):
        model_name = provider.model
    elif isinstance(provider, ClaudeProvider):
        model_name = provider.model
    else:
        model_name = "unknown"

    # Health check
    health_status = "unknown"
    health_message = ""

    if use_local:
        try:
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            async with _httpx.AsyncClient(timeout=_httpx.Timeout(5.0)) as hc:
                resp = await hc.get(f"{ollama_url}/api/tags")
                if resp.status_code == 200:
                    health_status = "connected"
                    health_message = "Ollama server is running"
                else:
                    health_status = "error"
                    health_message = f"Ollama returned status {resp.status_code}"
        except Exception as e:
            health_status = "disconnected"
            health_message = f"Cannot connect to Ollama: {str(e)}"
    else:
        api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('EMERGENT_LLM_KEY')
        if api_key:
            health_status = "connected"
            health_message = "Anthropic API key configured"
        else:
            health_status = "error"
            health_message = "No Anthropic API key found"

    return {
        "mode": "local" if use_local else "cloud",
        "provider": provider_name,
        "model": model_name,
        "health": health_status,
        "health_message": health_message,
        "ollama_url": os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434') if use_local else None,
    }


async def _apply_llm_mode(mode: str, user_id: str = "unknown", persist: bool = True):
    """
    Helper: apply a new LLM mode ('local' or 'cloud') at runtime.
    - Updates env var
    - Clears singleton caches
    - Optionally persists to MongoDB user_settings collection
    Returns fresh status dict.
    """
    # Update environment variable
    if mode == "local":
        os.environ["USE_LOCAL_LLM"] = "true"
    else:
        os.environ["USE_LOCAL_LLM"] = "false"

    # Clear cached provider singletons to force re-initialization
    import services.llm_provider as llm_mod
    llm_mod._claude_provider = None
    llm_mod._ollama_provider = None

    # Persist to MongoDB so it survives server restart
    if persist:
        try:
            await db.app_settings.update_one(
                {"key": "llm_mode"},
                {"$set": {
                    "key": "llm_mode",
                    "value": mode,
                    "updated_by": user_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Failed to persist LLM mode to MongoDB: {e}")

    # Get fresh status
    provider = get_llm_provider()
    provider_name = provider.get_provider_name()

    if isinstance(provider, OllamaProvider):
        model_name = provider.model
    elif isinstance(provider, ClaudeProvider):
        model_name = provider.model
    else:
        model_name = "unknown"

    logger.info(f"LLM mode switched to '{mode}' by user {user_id}")

    return {
        "message": f"LLM mode switched to {mode}",
        "mode": mode,
        "provider": provider_name,
        "model": model_name,
    }


def _get_service_llm_status():
    """
    Feature #213: Get per-service LLM mode status.
    Reports which provider each service would use right now.
    """
    use_local = is_using_local_llm()
    mode = "local" if use_local else "cloud"
    services_status = {}

    # Check each known AI-powered service
    service_names = [
        "clause_extraction",
        "gap_analysis",
        "task_service",
        "multi_llm_service",
        "chat_copilot",
        "regulatory_analysis",
        "evidence_validation",
    ]
    for svc in service_names:
        services_status[svc] = {
            "mode": mode,
            "provider": "ollama" if use_local else "claude",
        }

    return services_status


@api_router.get("/llm/status")
async def get_llm_status(current_user: dict = Depends(get_current_user)):
    """
    Feature #210 + #213: Get current LLM provider status including mode, provider, model,
    health, and per-service status.
    """
    status = await _get_llm_health_and_status()
    status["services"] = _get_service_llm_status()
    return status


@api_router.post("/llm/mode")
async def toggle_llm_mode(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #210 + #213: Toggle between local and cloud LLM mode.
    Accepts {"mode": "local"} or {"mode": "cloud"}.
    Updates all services at runtime and persists to MongoDB.
    """
    mode = body.get("mode", "").lower()
    if mode not in ("local", "cloud"):
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'local' or 'cloud'.")

    user_id = current_user.get("user_id", "unknown")
    result = await _apply_llm_mode(mode, user_id=user_id, persist=True)
    result["services"] = _get_service_llm_status()
    return result


# ==========================================
# Settings-based LLM Mode Endpoints (Feature #213)
# ==========================================

@api_router.get("/settings/llm-mode")
async def get_settings_llm_mode(current_user: dict = Depends(get_current_user)):
    """
    Feature #213: GET /api/settings/llm-mode
    Returns current LLM mode, per-service status, and health.
    """
    status = await _get_llm_health_and_status()
    status["services"] = _get_service_llm_status()
    return status


@api_router.post("/settings/llm-mode")
async def set_settings_llm_mode(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Feature #213: POST /api/settings/llm-mode
    Updates the global LLM state for ALL services at once.
    Accepts {"mode": "local"} or {"mode": "cloud"}.
    Persists to MongoDB so the preference survives server restart.
    """
    mode = body.get("mode", "").lower()
    if mode not in ("local", "cloud"):
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'local' or 'cloud'.")

    user_id = current_user.get("user_id", "unknown")
    result = await _apply_llm_mode(mode, user_id=user_id, persist=True)
    result["services"] = _get_service_llm_status()
    return result


@api_router.get("/llm/cost-summary")
async def get_llm_cost_summary(current_user: dict = Depends(get_current_user)):
    """
    Feature #212: Get LLM cost tracking summary.
    Shows cost breakdown by provider with cumulative savings metric.
    """
    # Query cost tracking collection
    pipeline = [
        {"$group": {
            "_id": "$provider",
            "total_cost": {"$sum": "$cost"},
            "total_operations": {"$sum": 1},
            "total_input_tokens": {"$sum": "$input_tokens"},
            "total_output_tokens": {"$sum": "$output_tokens"},
        }},
    ]

    cost_data = []
    try:
        async for doc in db.llm_cost_tracking.aggregate(pipeline):
            cost_data.append({
                "provider": doc["_id"],
                "total_cost": round(doc["total_cost"], 6),
                "total_operations": doc["total_operations"],
                "total_input_tokens": doc["total_input_tokens"],
                "total_output_tokens": doc["total_output_tokens"],
            })
    except Exception:
        pass

    # Calculate savings (cloud cost estimate for local operations)
    cloud_cost = sum(d["total_cost"] for d in cost_data if d["provider"] in ("claude", "anthropic"))
    local_ops = sum(d["total_operations"] for d in cost_data if d["provider"] in ("ollama", "local"))
    # Estimate: average cloud cost per operation * local operations = savings
    avg_cloud_cost = (cloud_cost / max(sum(d["total_operations"] for d in cost_data if d["provider"] in ("claude", "anthropic")), 1))
    estimated_savings = round(avg_cloud_cost * local_ops, 6)

    return {
        "providers": cost_data,
        "total_cost": round(sum(d["total_cost"] for d in cost_data), 6),
        "cloud_cost": round(cloud_cost, 6),
        "local_cost": 0.0,  # Local LLM operations are always zero cost
        "estimated_savings": estimated_savings,
        "current_mode": "local" if is_using_local_llm() else "cloud",
    }


# Feature #217: Register NPCI Circulars router
from routers.npci_router import npci_router
api_router.include_router(npci_router)

app.include_router(api_router)

# Startup and shutdown now handled by lifespan context manager above

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    host = os.environ.get('HOST', '0.0.0.0')
    uvicorn.run(app, host=host, port=port)
