from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
from enum import Enum

class PolicyType(str, Enum):
    KYC = "KYC"
    AML = "AML"
    DIGITAL_LENDING = "Digital Lending"
    INFOSEC = "InfoSec"
    OUTSOURCING = "Outsourcing"
    RISK_MANAGEMENT = "Risk Management"
    FRAUD = "Fraud Management"
    UPI = "UPI/Payments"
    OTHER = "Other"

class PolicyStatus(str, Enum):
    DRAFT = "Draft"
    REVIEW = "Review"
    APPROVED = "Approved"
    ARCHIVED = "Archived"

class SeverityLevel(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class TaskStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    PENDING_EVIDENCE = "Pending Evidence"
    AI_REVIEW = "AI Review"
    MANUAL_REVIEW = "Manual Review"
    COMPLETED = "Completed"
    REJECTED = "Rejected"
    CLOSED = "Closed"


class RecurrenceType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ActivityType(str, Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    COMMENT_ADDED = "comment_added"
    EVIDENCE_ADDED = "evidence_added"
    TIMER_STARTED = "timer_started"
    TIMER_STOPPED = "timer_stopped"
    AI_REVIEWED = "ai_reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    DEADLINE_REMINDED = "deadline_reminded"


class UploadJobStatus(str, Enum):
    """Status of a background upload/processing job."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadJobType(str, Enum):
    """Type of upload job."""
    POLICY = "policy"
    REGULATION = "regulation"
    EVIDENCE = "evidence"


class UploadJob(BaseModel):
    """
    Tracks background upload and processing jobs.
    Used for real-time progress updates via WebSocket.
    """
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    organization: str
    job_type: str  # policy, regulation, evidence
    status: str = UploadJobStatus.PENDING.value
    
    # File info
    file_name: str
    file_size: int = 0  # bytes
    
    # Progress tracking
    progress: int = 0  # 0-100
    current_step: str = "Initializing..."
    total_steps: int = 5
    current_step_number: int = 0
    
    # Result info
    result_id: Optional[str] = None  # ID of created policy/regulation
    result_title: Optional[str] = None
    clauses_extracted: int = 0
    pages_processed: int = 0
    
    # Error handling
    error_message: Optional[str] = None
    error_details: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = {}
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RegulatorType(str, Enum):
    SEBI = "SEBI"
    RBI = "RBI"
    NSE = "NSE"
    BSE = "BSE"
    IRDAI = "IRDAI"
    FIU_IND = "FIU-IND"
    NPCI = "NPCI"
    ICCL = "ICCL"
    NSDL = "NSDL"
    FINRA = "FINRA"
    SEC = "SEC"
    FCA = "FCA"
    MAS = "MAS"
    OTHER = "Other"

class ComplianceStatus(str, Enum):
    COMPLIANT = "Compliant"
    PARTIALLY_COMPLIANT = "Partially Compliant"
    NON_COMPLIANT = "Non-Compliant"
    NOTED_FOR_COMPLIANCE = "Noted for Compliance"

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    full_name: str
    role: str = "compliance_head"
    organization: str = "Default Org"
    department: Optional[str] = None
    preferred_theme: Optional[str] = "charcoal-pro"  # Default theme
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "compliance_head"
    organization: str = "Default Org"
    department: Optional[str] = None
    role: str = "compliance_head"

class UserLogin(BaseModel):
    email: str
    password: str

class InviteStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"

class UserInvite(BaseModel):
    """
    User invitation for organization members.
    Supports email domain-based auto-approval.
    """
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    organization: str
    invited_by: str  # User ID of inviter
    invited_by_name: str  # Name for display
    role: str = "user"  # Role to assign when accepted
    status: InviteStatus = InviteStatus.PENDING
    invite_token: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=7))
    accepted_at: Optional[datetime] = None

class UserInviteCreate(BaseModel):
    email: str
    role: str = "user"

class DepartmentMember(BaseModel):
    """Member of a department with role and title for task assignment."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    title: str  # e.g., "Chief Compliance Officer", "Risk Analyst"
    role: str   # e.g., "head", "manager", "analyst", "officer"
    department_id: str
    can_be_assigned_tasks: bool = True
    expertise_areas: List[str] = []  # e.g., ["kyc", "aml", "risk_management"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TeamMember(BaseModel):
    """
    Team member for task assignment and notifications.
    Uploaded via CSV with fields: Name, Team, Email, Role
    """
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    team: str  # e.g., "Tech", "Product", "Infosec", "Legal", "Compliance"
    email: str
    role: str  # e.g., "SPOC", "Member", "Lead"
    organization: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TeamMemberCreate(BaseModel):
    name: str
    team: str
    email: str
    role: str


class Department(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: str = ""  # Short code like "COMP", "RISK", "LEGAL"
    description: Optional[str] = None
    head_of_department: Optional[str] = None  # Member ID of the head
    head_name: Optional[str] = None  # Name of the head for display
    members: List[str] = []  # List of member IDs
    organization: str
    total_tasks: int = 0
    overdue_tasks: int = 0
    compliance_status: ComplianceStatus = ComplianceStatus.NOTED_FOR_COMPLIANCE
    # Subject categories this department handles
    handles_categories: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DepartmentCreate(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    head_of_department: Optional[str] = None

class ComplianceCharter(BaseModel):
    """
    Compliance Charter/Product categorization for policies and regulations.
    Examples: NBFC Compliance, UPI TPAP, Online Payment Aggregator, etc.
    """
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # e.g., "NBFC Compliance", "UPI TPAP", "Online Payment Aggregator"
    code: str  # Short code like "NBFC", "UPI_TPAP", "OPA"
    description: Optional[str] = None
    organization: str
    regulatory_bodies: List[str] = []  # e.g., ["RBI", "NPCI"]
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ComplianceCharterCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    regulatory_bodies: List[str] = []

class Clause(BaseModel):
    """
    Enhanced Clause model with semantic attributes for gap analysis.
    
    Display Attributes (NEW):
    - title: Section title (detected from CAPITAL LETTERS / Block Letters)
    - content: Plain text content of the clause
    - tags: List of relevant tags matching the clause content
    
    Core Matching Attributes:
    - requirement_type: Nature of requirement (mandatory/recommended/prohibition/informational/conditional)
    - subject_category: Domain area for matching (data_protection, reporting, risk_management, etc.)
    - key_obligations: Specific actions/controls required
    - semantic_summary: Clear interpretation of what the clause means (from Anthropic LLM)
    """
    model_config = ConfigDict(extra="ignore")
    clause_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str  # Original clause text (kept as 'text' for backward compatibility)
    original_text: Optional[str] = None  # Full original text (alias)
    section: Optional[str] = None
    page_number: Optional[int] = None
    reference_circulars: List[str] = []
    metadata: Optional[Dict[str, Any]] = None
    
    # ========== NEW STRUCTURED DISPLAY ATTRIBUTES ==========
    # These provide better structure for displaying clauses
    
    title: Optional[str] = None
    # Section title extracted from CAPITAL LETTERS / Block Letters
    # e.g., "CUSTOMER DUE DILIGENCE", "REPORTING REQUIREMENTS"
    
    content: Optional[str] = None
    # Plain text content of the clause (cleaned and formatted)
    
    tags: List[str] = []
    # List of relevant tags matching the clause content
    # e.g., ["mandatory", "customer-verification", "identity-proof", "risk-assessment"]
    
    # ========== CORE ATTRIBUTES FOR GAP ANALYSIS ==========
    # These are the 4 main attributes used for matching P1 ↔ R1 clauses
    
    requirement_type: Optional[str] = "informational"
    # Values: mandatory, recommended, prohibition, informational, conditional
    # - mandatory: Uses "shall", "must", "is required"
    # - recommended: Uses "should", "may", "is expected"  
    # - prohibition: Uses "shall not", "must not", "prohibited"
    # - informational: Definitions, explanations, context
    # - conditional: "If X, then Y" requirements
    
    subject_category: Optional[str] = "general"
    # Domain area for matching. Values include:
    # data_protection, customer_due_diligence, reporting_requirements,
    # risk_management, internal_controls, governance, audit_compliance,
    # record_keeping, disclosure, licensing_authorization, operational_procedures,
    # training_awareness, third_party_management, incident_management,
    # technology_security, financial_limits, customer_rights, anti_money_laundering,
    # fraud_prevention, business_continuity, general
    
    key_obligations: List[str] = []
    # List of specific actions/requirements extracted from the clause
    # e.g., ["Maintain transaction records for 5 years", "Report suspicious activity within 24 hours"]
    
    semantic_summary: Optional[str] = None
    # Clear, concise interpretation of what the clause means (1-2 sentences)
    # This enables human understanding and better LLM matching
    
    # ========== SUPPORTING ATTRIBUTES ==========
    
    entities_involved: List[str] = []
    # Who is responsible/affected: ["Bank", "Compliance Officer", "Customers"]
    
    keywords: List[str] = []
    # Key terms for search/matching: ["kyc", "verification", "customer", "identity"]
    
    compliance_indicators: List[str] = []
    # What evidence shows compliance: ["Policy document exists", "Annual review conducted"]
    
    criticality: Optional[str] = "medium"
    # Risk level: high, medium, low
    # high = Critical for compliance, legal penalties if violated
    # medium = Important but not critical
    # low = Best practice, informational
    
    # ========== DOCUMENT-TYPE-SPECIFIC ATTRIBUTES ==========
    
    # Policy-specific: What the policy ACTUALLY implements (concrete evidence of action)
    implementation_evidence: List[str] = []
    # E.g., ["Dedicated KYC team operational", "Digital KYC platform deployed"]
    
    # Policy-specific: Processes/procedures described in the clause
    processes_described: List[str] = []
    # E.g., ["Customer identity verification", "Document collection and scanning"]
    
    # Policy-specific: Which regulation this policy clause likely addresses
    regulatory_references: List[str] = []
    # E.g., ["RBI KYC Master Direction 2016", "PML Act Section 11"]
    
    # Regulation-specific: Structured checklist for verifying compliance
    compliance_checklist: List[Dict[str, Any]] = []
    # Each item: {"item": "...", "evidence_type": "document|process|record|control|training|report",
    #             "mandatory": true/false, "verification_method": "How auditor verifies"}

class Policy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    policy_type: PolicyType
    status: PolicyStatus = PolicyStatus.DRAFT
    version: str = "1.0"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    clauses: List[Clause] = []
    summary: Optional[str] = None
    impact_organization: Optional[str] = None
    impact_technical: Optional[str] = None
    impact_operational: Optional[str] = None
    key_areas: Optional[List[str]] = None
    user_id: str
    organization: str
    department: Optional[str] = None
    charter_id: Optional[str] = None  # Link to ComplianceCharter
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PolicyCreate(BaseModel):
    title: str
    policy_type: PolicyType
    version: str = "1.0"
    department: Optional[str] = None
    charter_id: Optional[str] = None

class Chapter(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chapter_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chapter_number: str
    title: str
    sub_clauses: List[Clause] = []

class Regulation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    regulatory_body: RegulatorType = RegulatorType.RBI
    circular_number: Optional[str] = None
    issued_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    clauses: List[Clause] = []
    summary: Optional[str] = None
    impact_organization: Optional[str] = None
    impact_technical: Optional[str] = None
    impact_operational: Optional[str] = None
    user_id: str
    organization: str
    is_master_circular: bool = False
    chapters: List[Chapter] = []
    version: str = "1.0"
    previous_version_id: Optional[str] = None
    charter_id: Optional[str] = None  # Link to ComplianceCharter
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RegulationCreate(BaseModel):
    title: str
    regulatory_body: RegulatorType = RegulatorType.RBI
    circular_number: Optional[str] = None
    is_master_circular: bool = False
    charter_id: Optional[str] = None

class CircularVersion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    circular_id: str
    version: str
    changes_summary: str
    additions: List[str] = []
    deletions: List[str] = []
    modifications: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Gap(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_type: str
    severity: SeverityLevel
    confidence_score: float
    policy_clause: Optional[Clause] = None
    regulation_clause: Optional[Clause] = None
    description: str
    suggested_fix: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # NEW: Evidence-level compliance map
    evidence_map: List[Dict[str, Any]] = []
    # Each item: {
    #   "indicator": "KYC policy document",
    #   "status": "found|missing|partial",
    #   "evidence_type": "document|process|record|control|training|report",
    #   "mandatory": true/false,
    #   "source_policy_clause_id": "clause_id or null",
    #   "source_text": "excerpt from policy that proves this",
    #   "source_page": 5,
    #   "source_section": "KYC Process",
    #   "verification_method": "How to verify"
    # }

class GapAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str
    regulation_id: str
    gaps: List[Gap] = []
    compliance_score: float
    total_clauses_analyzed: int
    user_id: str
    organization: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Task(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    status: TaskStatus = TaskStatus.OPEN
    priority: SeverityLevel = SeverityLevel.MEDIUM
    
    # Assignment
    assigned_to: Optional[str] = None  # Member name
    assigned_member_id: Optional[str] = None  # Member ID
    department: Optional[str] = None
    department_id: Optional[str] = None
    
    # Source linking
    source_type: str = "manual"  # manual, gap_analysis, regulatory_update, audit_gap
    gap_id: Optional[str] = None
    gap_analysis_id: Optional[str] = None  # Link to gap analysis result
    policy_id: Optional[str] = None
    regulation_id: Optional[str] = None
    circular_id: Optional[str] = None
    clause_id: Optional[str] = None  # Specific clause this task addresses
    charter_id: Optional[str] = None  # Link to compliance charter/product
    assigned_team: Optional[str] = None  # Team name (e.g., Tech, Product, Infosec)
    
    # Compliance indicators from gap analysis
    compliance_indicators: List[str] = []
    unfulfilled_indicators: List[str] = []
    
    # Due date and reminders
    due_date: Optional[datetime] = None
    reminder_days: List[int] = [1, 0]  # Days before due date to send reminders
    last_reminder_sent: Optional[datetime] = None
    
    # Time tracking
    time_entries: List[Dict[str, Any]] = []  # [{start, end, duration_minutes, user}]
    total_time_minutes: int = 0
    estimated_hours: Optional[float] = None
    timer_running: bool = False
    timer_started_at: Optional[datetime] = None
    
    # Evidence
    evidence_ids: List[str] = []  # Links to Evidence collection
    
    # Review workflow
    ai_review_result: Optional[Dict[str, Any]] = None  # {is_sufficient, confidence, explanation, compliance_status}
    ai_reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None  # Manual reviewer
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Activity log
    activities: List[Dict[str, Any]] = []  # [{type, timestamp, user, details}]
    
    # Recurring
    is_recurring: bool = False
    recurrence_type: Optional[str] = None  # daily, weekly, monthly, quarterly, yearly
    recurrence_config: Optional[Dict[str, Any]] = None  # {interval, day_of_week, day_of_month, etc.}
    parent_task_id: Optional[str] = None  # For recurring instances
    next_occurrence: Optional[datetime] = None
    
    # Escalation
    original_priority: Optional[str] = None
    escalation_history: List[Dict[str, Any]] = []  # [{from, to, reason, timestamp}]
    
    # Flags
    auto_assigned: bool = False
    is_overdue: bool = False
    
    # Metadata
    tags: List[str] = []
    metadata: Optional[Dict[str, Any]] = None
    
    user_id: str
    organization: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TaskCreate(BaseModel):
    title: str
    description: str
    priority: SeverityLevel = SeverityLevel.MEDIUM
    assigned_to: Optional[str] = None
    assigned_member_id: Optional[str] = None
    department: Optional[str] = None
    department_id: Optional[str] = None
    source_type: Optional[str] = None  # manual, gap_analysis, regulatory_update, audit_gap
    gap_id: Optional[str] = None
    gap_analysis_id: Optional[str] = None  # Link to gap analysis result
    policy_id: Optional[str] = None
    regulation_id: Optional[str] = None
    circular_id: Optional[str] = None
    clause_id: Optional[str] = None
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    reminder_days: List[int] = [1, 0]
    is_recurring: bool = False
    recurrence_type: Optional[str] = None
    recurrence_config: Optional[Dict[str, Any]] = None
    tags: List[str] = []


class TaskComment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    content: str
    user_id: str
    user_name: str
    user_email: Optional[str] = None
    mentions: List[str] = []  # User IDs mentioned
    attachments: List[str] = []  # File URLs
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskCommentCreate(BaseModel):
    content: str
    mentions: List[str] = []


class TaskAssignRequest(BaseModel):
    member_id: str
    member_name: str
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class TaskSubmitReviewRequest(BaseModel):
    evidence_ids: List[str] = []
    notes: Optional[str] = None


class TaskApprovalRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    file_url: str
    file_name: str
    file_type: str
    uploaded_by: str
    charter_id: Optional[str] = None  # Link to compliance charter/product
    assigned_team: Optional[str] = None  # Team that submitted this evidence
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization: str = "Default Org"
    status: str = "pending"  # pending, approved, rejected
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    comments: Optional[str] = None
    task_id: Optional[str] = None  # Link to task
    gap_id: Optional[str] = None
    regulation_id: Optional[str] = None
    
    # Validation
    validation_status: str = "Pending"  # Pending, AI Reviewed, Approved, Rejected
    ai_compliance_score: Optional[float] = None
    ai_validation_notes: Optional[str] = None
    ai_review_details: Optional[Dict[str, Any]] = None  # Detailed AI analysis
    
    # Feedback
    feedback_good: List[str] = []
    feedback_improvements: List[str] = []
    
    # Metadata
    tags: List[str] = []
    user_id: str
    organization: str
    uploaded_by_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EvidenceCreate(BaseModel):
    title: str
    description: Optional[str] = None
    policy_id: Optional[str] = None
    clause_id: Optional[str] = None
    control_id: Optional[str] = None

class AuditControl(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str
    control_description: str
    category: str
    weightage: float = 1.0
    evidence_required: List[str] = []
    compliance_score: Optional[float] = None
    status: str = "Pending"
    findings: Optional[str] = None
    recommendations: Optional[str] = None

class AuditSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_type: str
    scope: str
    controls: List[AuditControl] = []
    overall_score: Optional[float] = None
    status: str = "In Progress"
    user_id: str
    organization: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class AuditSessionCreate(BaseModel):
    audit_type: str
    scope: str

class ComplianceCalendarEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    event_type: str
    regulator: RegulatorType
    due_date: datetime
    recurrence: Optional[str] = None
    responsible_department: Optional[str] = None
    responsible_person: Optional[str] = None
    status: str = "Upcoming"
    organization: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ComplianceCalendarEventCreate(BaseModel):
    title: str
    description: str
    event_type: str
    regulator: RegulatorType
    due_date: datetime
    recurrence: Optional[str] = None
    responsible_department: Optional[str] = None

class LOSLMSData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_source: str
    record_type: str
    record_data: Dict[str, Any]
    compliance_issues: List[str] = []
    risk_level: SeverityLevel = SeverityLevel.LOW
    reviewed: bool = False
    organization: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LOSLMSDataCreate(BaseModel):
    data_source: str
    record_type: str
    record_data: Dict[str, Any]

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str
    content: str
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatMessageCreate(BaseModel):
    session_id: str
    content: str

class DashboardStats(BaseModel):
    total_policies: int
    total_regulations: int
    total_tasks: int
    open_tasks: int
    compliance_score: float
    critical_gaps: int
    high_priority_tasks: int
    departments_count: int
    non_compliant_departments: int
    pending_actionables: int
    regulatory_communications: int
    compliance_by_status: Dict[str, int] = {}
    compliance_by_department: List[Dict[str, Any]] = []
    regulator_overview: List[Dict[str, Any]] = []
    # Extended dashboard data
    tasks_by_status: Dict[str, int] = {}
    tasks_by_priority: Dict[str, int] = {}
    compliance_trend: List[Dict[str, Any]] = []
    recent_activities: List[Dict[str, Any]] = []
    upcoming_deadlines: List[Dict[str, Any]] = []
    gap_severity_distribution: Dict[str, int] = {}
    monthly_task_completion: List[Dict[str, Any]] = []
    policy_coverage: Dict[str, Any] = {}
    risk_metrics: Dict[str, Any] = {}


# ==========================================
# Regulation Update Models
# ==========================================
class RegulationUpdate(BaseModel):
    id: str = ""
    regulation_id: str = ""
    title: str = ""
    regulatory_body: str = ""
    circular_number: str = ""
    effective_date: Optional[datetime] = None
    summary: str = ""
    impact_analysis: str = ""
    affected_policies: List[str] = []
    departments_affected: List[str] = []
    priority: str = "medium"
    status: str = "pending_review"
    organization: str = "Default"
    user_id: str = ""
    auto_created_tasks: List[str] = []
    crawl_date: datetime = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.crawl_date is None:
            self.crawl_date = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class RegulationUpdateCreate(BaseModel):
    regulation_id: str
    title: str
    regulatory_body: str = ""
    circular_number: str = ""
    effective_date: Optional[str] = None
    summary: str = ""
    impact_analysis: str = ""
    affected_policies: List[str] = []
    departments_affected: List[str] = []
    priority: str = "medium"


# ==========================================
# Impact Score Adjustment Model
# ==========================================
class ImpactScoreAdjustment(BaseModel):
    new_score: float
    justification: str = ""


# ==========================================
# Checklist Models
# ==========================================
class ChecklistItem(BaseModel):
    id: str = ""
    text: str = ""
    description: str = ""
    gap_id: Optional[str] = None
    severity: SeverityLevel = SeverityLevel.MEDIUM
    completed: bool = False
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    notes: Optional[str] = None
    evidence_ids: List[str] = []

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())


class Checklist(BaseModel):
    id: str = ""
    title: str = ""
    description: str = ""
    gap_analysis_id: str = ""
    policy_id: Optional[str] = None
    regulation_id: Optional[str] = None
    items: List[ChecklistItem] = []
    user_id: str = ""
    organization: str = "Default"
    created_at: datetime = None
    updated_at: datetime = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)


class ChecklistCreate(BaseModel):
    gap_analysis_id: str
    title: Optional[str] = None
    description: str = ""


class ChecklistItemUpdate(BaseModel):
    completed: bool = False
    notes: Optional[str] = None
    evidence_ids: Optional[List[str]] = None


# ==========================================
# Evidence Template Models
# ==========================================
class EvidenceTemplate(BaseModel):
    id: str = ""
    template_name: str = ""
    regulation_type: str = ""
    description: str = ""
    required_documents: List[str] = []
    required_fields: List[Dict[str, Any]] = []
    validation_criteria: List[Dict[str, Any]] = []
    minimum_score: float = 0.0
    auto_approve_threshold: float = 0.0
    organization: str = "Default"
    created_by: str = ""
    created_at: datetime = None
    updated_at: datetime = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)


class EvidenceTemplateCreate(BaseModel):
    template_name: str
    regulation_type: str = ""
    description: str = ""
    required_documents: List[str] = []
    required_fields: List[Dict[str, Any]] = []
    validation_criteria: List[Dict[str, Any]] = []
    minimum_score: float = 0.0
    auto_approve_threshold: float = 0.0


class EvidenceTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    description: Optional[str] = None
    required_documents: Optional[List[str]] = None
    required_fields: Optional[List[Dict[str, Any]]] = None
    validation_criteria: Optional[List[Dict[str, Any]]] = None
    minimum_score: Optional[float] = None
    auto_approve_threshold: Optional[float] = None


# ==========================================
# Task Dependency Models
# ==========================================
class TaskDependency(BaseModel):
    id: str = ""
    task_id: str = ""
    depends_on_task_id: str = ""
    dependency_type: str = "blocked_by"
    created_by: str = ""
    user_id: str = ""
    organization: str = "Default"
    created_at: datetime = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: str
    dependency_type: str = "blocked_by"

class OrganizationProfileCreate(BaseModel):
    organization: str
    description: Optional[str] = None
    jurisdiction: Optional[str] = None
    industry: Optional[str] = None
    primary_contact: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OrganizationProfileUpdate(BaseModel):
    description: Optional[str] = None
    jurisdiction: Optional[str] = None
    industry: Optional[str] = None
    primary_contact: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None