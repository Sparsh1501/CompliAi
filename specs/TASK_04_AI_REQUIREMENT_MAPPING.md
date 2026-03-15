# Task #4: Build AI Requirement Mapping Engine for Gap Analysis

## Implementation Specification

---

## 1. OBJECTIVE

Build an AI-powered requirement mapping engine that sits between regulation ingestion (Task #1) and gap analysis (existing semantic/regulation-first engines). The engine maps extracted regulation clauses to a structured **requirement catalog**, resolves which requirements apply to a specific entity type (bank PA, non-bank PA, PA-P), and produces a normalised **RequirementMap** that the gap analysis services consume. This replaces the current ad-hoc matching with a deterministic requirement → policy clause → compliance check pipeline.

**Key Problem Solved:** Today, the gap analysis iterates over raw regulation clauses and uses LLM to find matching policy clauses. This works, but:
- No reusable requirement catalog — every analysis re-interprets the same regulation text
- No entity-type filtering — bank PAs and non-bank PAs see the same requirements
- No requirement dependencies or grouping — related requirements aren't linked
- No caching — identical regulation→requirement mapping is repeated per run

The requirement mapping engine creates a **persistent, structured layer** between raw regulation clauses and gap analysis.

---

## 2. ARCHITECTURE OVERVIEW

```
┌──────────────────────────────────────────────────────────────┐
│  Regulation Upload Pipeline (existing)                        │
│  process_regulation_upload_background() → clauses extracted   │
└────────────────────┬─────────────────────────────────────────┘
                     │ trigger after clause enrichment (step 5)
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  NEW: RequirementMappingService                               │
│  services/requirement_mapping_service.py                      │
├──────────────────────────────────────────────────────────────┤
│  Phase 1: Catalog Generation                                  │
│    1. Receive enriched regulation clauses                      │
│    2. LLM: Extract discrete requirements from each clause     │
│    3. Deduplicate & normalise requirements                    │
│    4. Assign requirement IDs (RBI-PAPG-AUTH-001 format)       │
│    5. Classify: category, criticality, entity_applicability   │
│    6. Store in requirements collection                         │
│                                                               │
│  Phase 2: Mapping (at gap analysis time)                      │
│    7. Load requirements for regulation + entity type filter   │
│    8. For each requirement, find matching policy clauses       │
│       (Qdrant pre-filter → LLM semantic match)               │
│    9. Produce RequirementMap with coverage status per req     │
│   10. Feed into existing SemanticGapAnalysisService           │
├──────────────────────────────────────────────────────────────┤
│  Phase 3: Incremental Updates                                 │
│   11. When regulation is re-uploaded (amendment), diff reqs   │
│   12. Mark added/modified/removed requirements                │
│   13. Notify affected gap analyses to re-run                  │
└────────────┬──────────────────┬──────────────────────────────┘
             │                  │
             ▼                  ▼
        MongoDB             Qdrant
   (requirements)     (requirement_embeddings)
```

---

## 3. FILES TO CREATE

### 3.1 `backend/services/requirement_mapping_service.py` (NEW)

**Purpose:** Core service for extracting, cataloging, and mapping regulatory requirements.

```python
"""
Requirement Mapping Service for CompliAI

Extracts discrete regulatory requirements from regulation clauses,
catalogues them with structured metadata, and maps them to policy
clauses for gap analysis consumption.

Key Concepts:
- Requirement: A single, testable compliance obligation derived from one or more regulation clauses
- RequirementCatalog: Full set of requirements for a regulation, indexed by category
- RequirementMap: Mapping of requirements → matched policy clauses (input for gap analysis)
"""

import anthropic
import os
import re
import json
import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class RequirementStatus(str, Enum):
    ACTIVE = "active"             # Currently enforceable
    UPCOMING = "upcoming"         # Future effective date
    SUPERSEDED = "superseded"     # Replaced by newer requirement
    WITHDRAWN = "withdrawn"       # No longer applicable

class ApplicabilityScope(str, Enum):
    ALL_PA = "all_pa"             # All Payment Aggregators
    BANK_PA = "bank_pa"           # Bank Payment Aggregators only
    NON_BANK_PA = "non_bank_pa"   # Non-bank PA only
    PA_P = "pa_p"                 # PA-P (physical POS) only
    PA_ONLINE = "pa_online"       # Online PA only
    PG_ONLY = "pg_only"           # Payment Gateways only
    ALL = "all"                   # Universal

class RequirementType(str, Enum):
    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    PROHIBITION = "prohibition"
    CONDITIONAL = "conditional"
    INFORMATIONAL = "informational"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Requirement:
    """A single, discrete, testable compliance requirement."""
    requirement_id: str           # e.g. "RBI-PAPG-AUTH-001"
    regulation_id: str            # Parent regulation ID
    source_clause_ids: List[str]  # Clause IDs this was derived from

    # Content
    title: str                    # Short descriptive title
    description: str              # Full requirement text (normalised)
    original_text_excerpts: List[str]  # Relevant snippets from regulation
    rbi_para_reference: str       # e.g. "Para 5.1(a)", "Annex II Item 3"

    # Classification
    category: str                 # Subject category (from compliance_context.py)
    sub_category: Optional[str]   # Finer grouping within category
    requirement_type: RequirementType
    criticality: str              # "high" | "medium" | "low"

    # Applicability
    entity_applicability: List[ApplicabilityScope]  # Who this applies to
    effective_date: Optional[str]   # ISO date when requirement takes effect
    transition_period_days: Optional[int]  # Grace period from effective_date

    # Compliance Indicators (what proves compliance)
    compliance_indicators: List[str]
    evidence_types: List[str]     # document, process, record, control, etc.

    # Dependencies
    depends_on: List[str]         # Other requirement_ids this depends on
    related_requirements: List[str]  # Loosely related requirement_ids

    # Metadata
    status: RequirementStatus = RequirementStatus.ACTIVE
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RequirementMatch:
    """A single requirement → policy clause match with coverage assessment."""
    requirement_id: str
    requirement_title: str

    # Match result
    matched_policy_clause_ids: List[str]   # Policy clauses that address this
    primary_match_clause_id: Optional[str]  # Best single match
    coverage_score: float                   # 0.0–1.0 how well policies cover this

    # Indicator-level assessment
    indicator_coverage: List[Dict[str, Any]]
    # Each: { "indicator": str, "status": "covered"|"partial"|"missing",
    #         "source_clause_id": str|None, "source_text": str|None }

    # Gap assessment (pre-computed for gap analysis)
    gap_type: str       # compliant, exceeds, partial, weak, missing, conflicting
    severity: str       # Critical, High, Medium, Low
    confidence: float   # 0.0–1.0

    # Remediation hints
    missing_elements: List[str]
    weak_elements: List[str]


@dataclass
class RequirementMap:
    """Complete mapping of requirements → policy clauses for one regulation."""
    map_id: str
    regulation_id: str
    regulation_title: str
    policy_id: str
    policy_title: str
    entity_type: str              # Filter applied (e.g. "non_bank_pa")

    # Stats
    total_requirements: int
    applicable_requirements: int  # After entity filter
    covered_count: int
    partial_count: int
    missing_count: int

    # Mappings
    matches: List[RequirementMatch]

    # Aggregated score
    overall_coverage_score: float  # 0–100

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# =============================================================================
# REQUIREMENT MAPPING SERVICE
# =============================================================================

class RequirementMappingService:
    """
    Extracts, catalogs, and maps regulatory requirements.

    Two-phase operation:
    1. CATALOG phase (after regulation upload): Extract requirements from clauses
    2. MAP phase (at gap analysis time): Map requirements to policy clauses
    """

    def __init__(self, db=None, vector_service=None):
        """
        Args:
            db: Motor async MongoDB database instance
            vector_service: VectorService for Qdrant embeddings
        """
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
        self.model = "claude-sonnet-4-20250514"
        self.db = db
        self.vector_service = vector_service

    # =========================================================================
    # PHASE 1: CATALOG — Extract requirements from regulation clauses
    # =========================================================================

    async def extract_requirements(
        self,
        regulation_id: str,
        regulation_title: str,
        clauses: List[Dict[str, Any]],
        regulatory_body: str = "RBI",
        progress_callback: Optional[callable] = None
    ) -> List[Requirement]:
        """
        Extract discrete requirements from regulation clauses using LLM.

        Process:
        1. Batch clauses (5 per batch to stay within context window)
        2. For each batch, ask LLM to extract testable requirements
        3. Deduplicate across batches
        4. Assign structured IDs
        5. Store in MongoDB requirements collection

        Args:
            regulation_id: ID of the regulation document
            regulation_title: Title for context
            clauses: Enriched clause dicts from the regulation
            regulatory_body: "RBI", "NPCI", etc.
            progress_callback: async callback(step, progress, message, details)

        Returns:
            List of extracted Requirement objects
        """
        # Implementation: see Section 5 (LLM Prompts)
        pass

    async def _extract_batch(
        self,
        clauses_batch: List[Dict[str, Any]],
        regulation_title: str,
        regulatory_body: str,
        existing_req_titles: List[str]
    ) -> List[Dict[str, Any]]:
        """
        LLM call to extract requirements from a batch of clauses.

        Returns raw requirement dicts (before Requirement dataclass conversion).
        Prompt instructs LLM to avoid duplicating titles in existing_req_titles.
        """
        pass

    def _assign_requirement_ids(
        self,
        requirements: List[Dict],
        regulatory_body: str,
        regulation_code: str
    ) -> List[Dict]:
        """
        Assign structured IDs like RBI-PAPG-AUTH-001.

        Format: {BODY}-{REG_CODE}-{CATEGORY_SHORT}-{SEQUENCE}

        Category short codes:
          AUTH → authorisation
          CAP  → capital_requirements
          MER  → merchant_onboarding
          SET  → settlement_operations
          ESC  → escrow_accounts
          FRM  → fraud_monitoring
          GOV  → governance_compliance
          TEC  → technology_security
          CUS  → customer_protection
          PAP  → pa_p_physical
        """
        pass

    async def _deduplicate_requirements(
        self,
        requirements: List[Dict]
    ) -> List[Dict]:
        """
        Remove duplicate/overlapping requirements.

        Strategy:
        1. Exact title match → merge (keep richer one)
        2. >0.9 cosine similarity on description → merge
        3. Same source_clause_ids + same category → merge
        """
        pass

    async def store_requirements(
        self,
        requirements: List[Requirement],
        regulation_id: str
    ) -> int:
        """
        Persist requirements to MongoDB and embed in Qdrant.

        MongoDB collection: requirements
        Qdrant collection: requirement_embeddings (new)

        Returns count of requirements stored.
        """
        pass

    async def get_requirements_for_regulation(
        self,
        regulation_id: str,
        entity_type: Optional[str] = None,
        category: Optional[str] = None,
        status: str = "active"
    ) -> List[Dict]:
        """
        Retrieve requirements, optionally filtered by entity type and category.

        Args:
            regulation_id: Filter by regulation
            entity_type: Filter by ApplicabilityScope value (e.g. "non_bank_pa")
            category: Filter by subject category
            status: Filter by RequirementStatus value

        Returns:
            List of requirement dicts from MongoDB
        """
        pass

    # =========================================================================
    # PHASE 2: MAP — Map requirements to policy clauses
    # =========================================================================

    async def map_requirements_to_policy(
        self,
        regulation_id: str,
        policy_id: str,
        policy_clauses: List[Dict[str, Any]],
        entity_type: str = "all",
        progress_callback: Optional[callable] = None
    ) -> RequirementMap:
        """
        Map all applicable requirements for a regulation against policy clauses.

        Process:
        1. Load requirements for regulation (filtered by entity_type)
        2. For each requirement:
           a. Qdrant: Find top-K policy clause candidates by embedding similarity
           b. LLM: Assess which policy clauses address which compliance indicators
           c. Score coverage (0.0–1.0) per requirement
        3. Aggregate into RequirementMap

        This RequirementMap can then be fed directly into the existing
        SemanticGapAnalysisService or RegulationFirstGapAnalysisService.

        Args:
            regulation_id: Source regulation
            policy_id: Target policy to assess
            policy_clauses: Enriched clause dicts from the policy
            entity_type: Entity scope filter (default "all")
            progress_callback: Optional async progress callback

        Returns:
            RequirementMap with per-requirement coverage assessment
        """
        pass

    async def _match_single_requirement(
        self,
        requirement: Dict,
        policy_clauses: List[Dict[str, Any]],
        policy_summaries: str
    ) -> RequirementMatch:
        """
        Match a single requirement against policy clauses.

        1. Qdrant semantic pre-filter: Find top-15 policy clause candidates
           Query: requirement.description + requirement.compliance_indicators
           Collection: policy_clauses
           Filter: organization match

        2. LLM assessment: Send requirement + candidate clauses to Claude
           Ask: Which indicators are covered? What's missing?

        3. Score: coverage_score = covered_indicators / total_indicators
           Map to gap_type using thresholds:
             1.0      → compliant
             0.8–0.99 → partial (some indicators missed)
             0.5–0.79 → weak
             0.0–0.49 → missing

        Returns:
            RequirementMatch with indicator-level coverage
        """
        pass

    # =========================================================================
    # PHASE 3: INCREMENTAL UPDATES
    # =========================================================================

    async def diff_requirements(
        self,
        regulation_id: str,
        new_clauses: List[Dict[str, Any]],
        regulation_title: str,
        regulatory_body: str = "RBI"
    ) -> Dict[str, Any]:
        """
        Compare new clauses against existing requirements to find changes.

        Returns:
            {
                "added": [Requirement],      # New requirements not in catalog
                "modified": [Requirement],   # Changed requirements (text/scope)
                "removed": [str],            # requirement_ids no longer present
                "unchanged": int             # Count of unchanged
            }
        """
        pass

    async def apply_diff(
        self,
        regulation_id: str,
        diff: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        Apply a requirement diff: insert added, update modified, mark removed as superseded.
        Returns counts: {"added": N, "modified": N, "removed": N}
        """
        pass
```

### 3.2 `backend/config/requirement_id_schema.py` (NEW)

**Purpose:** Constants and helpers for generating structured requirement IDs.

```python
"""
Requirement ID Schema for CompliAI

Defines the structured ID format for regulatory requirements.
Format: {BODY}-{REG_CODE}-{CATEGORY}-{SEQUENCE}
Example: RBI-PAPG-AUTH-001, RBI-PAPG-ESC-003

Used by RequirementMappingService to assign deterministic IDs.
"""

# Regulatory body codes (match RegulatorType enum in models.py)
BODY_CODES = {
    "RBI": "RBI",
    "NPCI": "NPCI",
    "FIU-IND": "FIU",
    "SEBI": "SEBI",
    "IRDAI": "IRDAI",
}

# Regulation short codes (manually maintained per regulation type)
REGULATION_CODES = {
    "pa_pg_master_direction": "PAPG",
    "digital_lending": "DL",
    "kyc_master_direction": "KYC",
    "nbfc_master_direction": "NBFC",
    "upi_operating_circular": "UPI",
}

# Category short codes for requirement IDs
CATEGORY_CODES = {
    "authorisation": "AUTH",
    "capital_requirements": "CAP",
    "merchant_onboarding": "MER",
    "settlement_operations": "SET",
    "escrow_accounts": "ESC",
    "fraud_monitoring": "FRM",
    "governance_compliance": "GOV",
    "technology_security": "TEC",
    "customer_protection": "CUS",
    "pa_p_physical": "PAP",
    "kyc_cdd": "KYC",
    "aml_cft": "AML",
    "data_protection": "DAT",
    "outsourcing": "OUT",
    "reporting": "RPT",
    "grievance_redressal": "GRV",
    "risk_management": "RSK",
    "information_security": "ISC",
    "licensing": "LIC",
    "general": "GEN",
}


def generate_requirement_id(
    body: str,
    regulation_code: str,
    category: str,
    sequence: int
) -> str:
    """
    Generate a structured requirement ID.

    Args:
        body: Regulatory body (e.g. "RBI")
        regulation_code: Regulation short code (e.g. "PAPG")
        category: Subject category key (e.g. "authorisation")
        sequence: Sequence number within category

    Returns:
        Formatted ID like "RBI-PAPG-AUTH-001"
    """
    body_code = BODY_CODES.get(body, body[:3].upper())
    cat_code = CATEGORY_CODES.get(category, category[:3].upper())
    return f"{body_code}-{regulation_code}-{cat_code}-{sequence:03d}"
```

---

## 4. FILES TO MODIFY

### 4.1 `backend/models.py`

**Add new Pydantic models** (after `GapAnalysisResult` at ~line 498):

```python
# --- Requirement Mapping Models ---

class RequirementApplicability(str, Enum):
    ALL_PA = "all_pa"
    BANK_PA = "bank_pa"
    NON_BANK_PA = "non_bank_pa"
    PA_P = "pa_p"
    PA_ONLINE = "pa_online"
    PG_ONLY = "pg_only"
    ALL = "all"

class RequirementStatusEnum(str, Enum):
    ACTIVE = "active"
    UPCOMING = "upcoming"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"

class RequirementModel(BaseModel):
    """Persisted regulatory requirement — extracted from regulation clauses."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement_id: str           # Structured ID: RBI-PAPG-AUTH-001
    regulation_id: str
    source_clause_ids: List[str] = []

    title: str
    description: str
    original_text_excerpts: List[str] = []
    rbi_para_reference: str = ""

    category: str
    sub_category: Optional[str] = None
    requirement_type: str = "mandatory"
    criticality: str = "medium"

    entity_applicability: List[str] = ["all"]  # ApplicabilityScope values
    effective_date: Optional[str] = None
    transition_period_days: Optional[int] = None

    compliance_indicators: List[str] = []
    evidence_types: List[str] = []

    depends_on: List[str] = []
    related_requirements: List[str] = []

    status: str = "active"
    version: int = 1
    organization: str = "system"  # "system" for global, org name for custom
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RequirementMapModel(BaseModel):
    """Persisted requirement-to-policy mapping result."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_id: str
    policy_id: str
    entity_type: str = "all"

    total_requirements: int = 0
    applicable_requirements: int = 0
    covered_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    overall_coverage_score: float = 0.0

    matches: List[Dict[str, Any]] = []  # Serialised RequirementMatch list

    user_id: str
    organization: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### 4.2 `backend/server.py`

#### 4.2a Import & initialise service (~line 40–44, alongside other service imports)

```python
from services.requirement_mapping_service import RequirementMappingService
```

After `semantic_gap_service = SemanticGapAnalysisService(...)` initialisation:

```python
requirement_mapping_service = RequirementMappingService(db=db, vector_service=vector_service)
```

#### 4.2b Hook into regulation upload pipeline (~line 3168, `process_regulation_upload_background`)

After clause enrichment succeeds (step 5: "Storing enriched clauses"), add a new step:

```python
# Step 5b: Extract and catalog requirements (NEW)
try:
    await update_job_progress(job_id, 72, "Extracting regulatory requirements...")

    requirements = await requirement_mapping_service.extract_requirements(
        regulation_id=regulation_id,
        regulation_title=title,
        clauses=enriched_clauses,
        regulatory_body=regulatory_body or "RBI",
        progress_callback=None  # Use job-level progress
    )

    stored_count = await requirement_mapping_service.store_requirements(
        requirements=requirements,
        regulation_id=regulation_id
    )

    logger.info(f"Extracted {stored_count} requirements for regulation {regulation_id}")
    await update_job_progress(job_id, 78, f"Cataloged {stored_count} requirements")
except Exception as e:
    logger.warning(f"Requirement extraction failed (non-fatal): {e}")
    # Non-fatal: regulation is still usable without requirements catalog
```

#### 4.2c New API endpoints (add after gap analysis section, ~line 4400)

```python
# ========== REQUIREMENT MAPPING ENDPOINTS ==========

@api_router.get("/requirements/{regulation_id}")
async def get_requirements(
    regulation_id: str,
    entity_type: Optional[str] = None,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get cataloged requirements for a regulation.
    Optional filters: entity_type (e.g. "non_bank_pa"), category (e.g. "escrow_accounts")
    """
    pass  # Delegate to requirement_mapping_service.get_requirements_for_regulation()

@api_router.get("/requirements/{regulation_id}/stats")
async def get_requirement_stats(
    regulation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get requirement statistics: total, by category, by criticality, by entity type.
    """
    pass  # Aggregate from requirements collection

@api_router.post("/requirements/map")
async def map_requirements(
    regulation_id: str,
    policy_id: str,
    entity_type: str = "all",
    current_user: dict = Depends(get_current_user)
):
    """
    Run requirement mapping: maps regulation requirements against policy clauses.
    Returns RequirementMap with per-requirement coverage assessment.

    This is a prerequisite step before running gap analysis — or can be called
    independently to get a quick coverage overview.
    """
    pass  # Delegate to requirement_mapping_service.map_requirements_to_policy()

@api_router.post("/requirements/map-stream")
async def map_requirements_stream(
    regulation_id: str,
    policy_id: str,
    entity_type: str = "all",
    current_user: dict = Depends(get_current_user)
):
    """
    SSE streaming version of requirement mapping.
    Streams progress events as each requirement is mapped.
    """
    pass  # SSE EventSourceResponse wrapper around map_requirements_to_policy()

@api_router.get("/requirement-maps/{map_id}")
async def get_requirement_map(
    map_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a previously computed requirement map by ID."""
    pass  # Fetch from requirement_maps collection

@api_router.get("/requirement-maps/history")
async def get_requirement_map_history(
    regulation_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List requirement mapping history, filtered by regulation and/or policy."""
    pass  # Query requirement_maps collection
```

#### 4.2d Enhance existing gap analysis to use requirement maps (~line 3981)

In `run_gap_analysis()`, after loading policy and regulation, add:

```python
# Check if requirement catalog exists for this regulation
req_count = await db.requirements.count_documents({"regulation_id": regulation_id, "status": "active"})

if req_count > 0:
    # Use requirement-based gap analysis (more structured)
    logger.info(f"Using requirement catalog ({req_count} requirements) for gap analysis")

    # Get or create requirement map
    existing_map = await db.requirement_maps.find_one({
        "regulation_id": regulation_id,
        "policy_id": policy_id,
        "entity_type": entity_type  # from client profile or default "all"
    }, {"_id": 0})

    if not existing_map or force_remap:
        req_map = await requirement_mapping_service.map_requirements_to_policy(
            regulation_id=regulation_id,
            policy_id=policy_id,
            policy_clauses=policy_clauses,
            entity_type=entity_type
        )
        # Store the map
        await db.requirement_maps.insert_one(dataclasses.asdict(req_map))

    # Convert requirement map to regulation clauses format for existing gap engine
    # (backward compatible — existing SemanticGapAnalysisService works unchanged)
    regulation_clauses = _requirement_map_to_virtual_clauses(req_map)
```

### 4.3 `backend/services/semantic_gap_analysis_service.py`

**Add CATEGORY_TO_DEPARTMENT entries** for PA/PG-specific categories:

```python
# Add to CATEGORY_TO_DEPARTMENT dict (line ~71-102):
"merchant_onboarding": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
"settlement_operations": {"department_id": "dept-operations", "department": "Operations", "role": "manager"},
"escrow_accounts": {"department_id": "dept-finance", "department": "Finance & Accounts", "role": "head"},
"pa_p_physical": {"department_id": "dept-operations", "department": "Operations", "role": "manager"},
"authorisation": {"department_id": "dept-compliance", "department": "Compliance", "role": "head"},
"customer_protection": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
```

### 4.4 `backend/services/regulation_first_gap_analysis.py`

**Mirror the same CATEGORY_TO_DEPARTMENT additions** (line ~39-86):

```python
# Add same PA/PG entries as in semantic service
"merchant_onboarding": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
"settlement_operations": {"department_id": "dept-operations", "department": "Operations", "role": "manager"},
"escrow_accounts": {"department_id": "dept-finance", "department": "Finance & Accounts", "role": "head"},
"pa_p_physical": {"department_id": "dept-operations", "department": "Operations", "role": "manager"},
"authorisation": {"department_id": "dept-compliance", "department": "Compliance", "role": "head"},
"customer_protection": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
```

---

## 5. LLM PROMPTS

### 5.1 Requirement Extraction Prompt (Phase 1)

Used in `_extract_batch()`:

```
You are a regulatory compliance expert. Given the following regulation clauses
from "{regulation_title}" issued by {regulatory_body}, extract ALL discrete,
testable compliance requirements.

For EACH requirement, provide:
1. title: Short name (e.g. "Minimum Net Worth Requirement for Non-bank PAs")
2. description: Full requirement text, normalised into clear compliance language
3. rbi_para_reference: Paragraph/section reference (e.g. "Para 5.1(a)")
4. category: One of {VALID_CATEGORIES}
5. requirement_type: mandatory | recommended | prohibition | conditional | informational
6. criticality: high | medium | low
7. entity_applicability: Array from [all_pa, bank_pa, non_bank_pa, pa_p, pa_online, pg_only, all]
8. compliance_indicators: List of specific, verifiable items that prove compliance
   (e.g. ["Board resolution approving KYC policy", "Annual KYC audit report"])
9. evidence_types: What kind of evidence proves this (document, process, record, control, training, report)
10. source_clause_ids: Which clause IDs from the input this requirement derives from

IMPORTANT:
- One regulation clause may contain MULTIPLE requirements (split them)
- Multiple clauses may contribute to ONE requirement (merge them, list all source IDs)
- Do NOT duplicate requirements that already exist: {existing_titles}
- Focus on TESTABLE obligations — skip preamble, definitions, and commentary
- For entity_applicability, be specific: if a para says "non-bank PAs shall...",
  use ["non_bank_pa"], not ["all"]

Return JSON array of requirement objects.

CLAUSES:
{clauses_json}
```

### 5.2 Requirement Mapping Prompt (Phase 2)

Used in `_match_single_requirement()`:

```
You are a compliance assessor. Given a regulatory REQUIREMENT and a set of
POLICY CLAUSE CANDIDATES, determine which policy clauses address this requirement.

REQUIREMENT:
- ID: {requirement_id}
- Title: {title}
- Description: {description}
- Compliance Indicators: {indicators}
- Criticality: {criticality}
- Type: {requirement_type}

POLICY CLAUSE CANDIDATES:
{policy_summaries}

For EACH compliance indicator, determine:
1. Is it COVERED by any policy clause? → status: "covered"
2. Is it PARTIALLY addressed? → status: "partial"
3. Is it completely MISSING? → status: "missing"

For covered/partial indicators, cite the policy clause index [N] and relevant excerpt.

Then provide an overall assessment:
- gap_type: compliant | exceeds | partial | weak | missing | conflicting
- severity: Critical | High | Medium | Low
- confidence: 0.0–1.0
- missing_elements: What's not covered at all
- weak_elements: What's addressed but insufficiently

Return JSON:
{
  "matched_clause_indices": [1, 5, 12],
  "primary_match_index": 5,
  "indicator_coverage": [
    {"indicator": "...", "status": "covered", "source_index": 5, "source_text": "..."},
    {"indicator": "...", "status": "missing", "source_index": null, "source_text": null}
  ],
  "gap_type": "partial",
  "severity": "High",
  "confidence": 0.85,
  "missing_elements": ["..."],
  "weak_elements": ["..."]
}
```

---

## 6. MONGODB SCHEMA CHANGES

### 6.1 New Collection: `requirements`

```javascript
// Index definitions
db.requirements.createIndex({ "regulation_id": 1, "status": 1 })
db.requirements.createIndex({ "requirement_id": 1 }, { unique: true })
db.requirements.createIndex({ "category": 1 })
db.requirements.createIndex({ "entity_applicability": 1 })
db.requirements.createIndex({ "criticality": 1 })

// Sample document
{
  "id": "uuid",
  "requirement_id": "RBI-PAPG-AUTH-001",
  "regulation_id": "reg-uuid",
  "source_clause_ids": ["clause-uuid-1", "clause-uuid-2"],
  "title": "Minimum Net Worth for Non-bank PA",
  "description": "Non-bank payment aggregators shall maintain...",
  "original_text_excerpts": ["Para 5.1(a): The minimum net worth..."],
  "rbi_para_reference": "Para 5.1(a)",
  "category": "capital_requirements",
  "sub_category": "net_worth",
  "requirement_type": "mandatory",
  "criticality": "high",
  "entity_applicability": ["non_bank_pa"],
  "effective_date": "2025-09-01",
  "transition_period_days": null,
  "compliance_indicators": [
    "Audited net worth certificate >= ₹15 crore",
    "CA certificate confirming net worth",
    "Board resolution on capital maintenance"
  ],
  "evidence_types": ["document", "record"],
  "depends_on": [],
  "related_requirements": ["RBI-PAPG-AUTH-002"],
  "status": "active",
  "version": 1,
  "organization": "system",
  "created_at": "2025-09-15T10:00:00Z",
  "updated_at": "2025-09-15T10:00:00Z"
}
```

### 6.2 New Collection: `requirement_maps`

```javascript
// Index definitions
db.requirement_maps.createIndex({ "regulation_id": 1, "policy_id": 1 })
db.requirement_maps.createIndex({ "user_id": 1, "organization": 1 })
db.requirement_maps.createIndex({ "created_at": -1 })

// Sample document
{
  "id": "uuid",
  "regulation_id": "reg-uuid",
  "policy_id": "policy-uuid",
  "entity_type": "non_bank_pa",
  "total_requirements": 48,
  "applicable_requirements": 42,
  "covered_count": 28,
  "partial_count": 8,
  "missing_count": 6,
  "overall_coverage_score": 72.5,
  "matches": [ /* RequirementMatch objects serialised */ ],
  "user_id": "user-uuid",
  "organization": "Acme Payments",
  "created_at": "2025-09-20T14:00:00Z"
}
```

### 6.3 New Qdrant Collection: `requirement_embeddings`

```python
# Collection config (384-dim, cosine, same as policy_clauses/regulation_clauses)
{
    "collection_name": "requirement_embeddings",
    "vectors_config": {
        "size": 384,
        "distance": "Cosine"
    }
}

# Payload fields per point:
# - requirement_id: str (structured ID like RBI-PAPG-AUTH-001)
# - regulation_id: str
# - category: str
# - criticality: str
# - entity_applicability: List[str]
# - organization: str
```

---

## 7. FRONTEND CHANGES

### 7.1 `frontend/src/lib/api.js`

Add requirement mapping API methods:

```javascript
// --- Requirement Mapping API ---
export const requirementsApi = {
  getForRegulation: (regulationId, params = {}) =>
    api.get(`/requirements/${regulationId}`, { params }),

  getStats: (regulationId) =>
    api.get(`/requirements/${regulationId}/stats`),

  runMapping: (regulationId, policyId, entityType = 'all') =>
    api.post('/requirements/map', null, {
      params: { regulation_id: regulationId, policy_id: policyId, entity_type: entityType }
    }),

  getMappingHistory: (params = {}) =>
    api.get('/requirement-maps/history', { params }),

  getMappingById: (mapId) =>
    api.get(`/requirement-maps/${mapId}`),
};
```

### 7.2 Gap Analysis Page Enhancement

On the gap analysis run page, add:
- **Entity type selector** dropdown (All, Bank PA, Non-bank PA, PA-P) before running analysis
- **Requirement catalog preview** panel showing count + categories when a regulation is selected
- **Coverage heatmap** after mapping completes (requirements grouped by category, color-coded by coverage)

### 7.3 New Component: `RequirementCatalogView.jsx`

A read-only view of the requirement catalog for a regulation:
- Grouped by category (accordion)
- Each requirement shows: ID, title, criticality badge, entity applicability tags
- Filter bar: by category, criticality, entity type
- Click to expand: full description, compliance indicators, RBI para reference

---

## 8. INTEGRATION WITH EXISTING GAP ANALYSIS

### 8.1 Backward Compatibility

The requirement mapping engine is **additive** — existing gap analysis works unchanged:

1. If a regulation has a requirement catalog (`requirements` collection has docs for that `regulation_id`):
   - Gap analysis uses the requirement map for structured assessment
   - Results include `requirement_id` references alongside clause IDs

2. If no requirement catalog exists:
   - Gap analysis falls back to current behavior (raw clause-to-clause matching)
   - No breaking changes

### 8.2 Conversion Function

```python
def _requirement_map_to_virtual_clauses(req_map: RequirementMap) -> List[Dict[str, Any]]:
    """
    Convert RequirementMap matches into regulation clause format
    that the existing SemanticGapAnalysisService can consume.

    Each RequirementMatch becomes a "virtual" regulation clause with:
    - clause_id = requirement_id
    - text = requirement.description
    - title = requirement.title
    - subject_category = requirement.category
    - criticality = requirement.criticality
    - compliance_indicators = requirement.compliance_indicators
    - key_obligations = derived from compliance_indicators
    - requirement_type = requirement.requirement_type

    This allows the existing gap engine to produce RegulationGapResult objects
    that reference structured requirement IDs instead of raw clause IDs.
    """
    pass
```

### 8.3 Enhanced Gap Report

When requirement mapping is used, the gap analysis result includes additional fields:

```python
# Added to result_dict in run_gap_analysis():
result_dict['requirement_map_id'] = req_map.map_id
result_dict['requirement_coverage'] = {
    "total": req_map.total_requirements,
    "applicable": req_map.applicable_requirements,
    "covered": req_map.covered_count,
    "partial": req_map.partial_count,
    "missing": req_map.missing_count,
    "coverage_score": req_map.overall_coverage_score
}
result_dict['entity_type'] = entity_type
```

---

## 9. PERFORMANCE CONSIDERATIONS

| Concern | Mitigation |
|---------|-----------|
| LLM calls for extraction (Phase 1) | Batch 5 clauses per call, ~10 calls for 50 clauses. One-time cost at upload. |
| LLM calls for mapping (Phase 2) | Batch 3 requirements per call, Qdrant pre-filter reduces policy candidates. ~15 calls for 45 requirements. |
| Qdrant latency | Use batch search for multiple requirements simultaneously. |
| Duplicate extraction on re-upload | `diff_requirements()` only processes changed clauses. |
| Storage | ~50 requirements × 2KB each = ~100KB per regulation. Minimal. |
| Caching | RequirementMap is persisted. Re-run only if policy or regulation changes. |

---

## 10. TESTING CHECKLIST

### Unit Tests (`tests/test_requirement_mapping.py`)

- [ ] `test_extract_requirements_basic` — Extract requirements from 5 sample clauses
- [ ] `test_requirement_id_generation` — Verify ID format: `RBI-PAPG-AUTH-001`
- [ ] `test_deduplication` — Same clause submitted twice → no duplicates
- [ ] `test_entity_filtering` — Filter by `non_bank_pa` excludes `bank_pa`-only requirements
- [ ] `test_map_requirement_full_coverage` — All indicators covered → gap_type=compliant
- [ ] `test_map_requirement_partial` — Some indicators covered → gap_type=partial
- [ ] `test_map_requirement_missing` — No indicators covered → gap_type=missing
- [ ] `test_diff_requirements_added` — New clause → new requirement detected
- [ ] `test_diff_requirements_removed` — Clause removed → requirement marked superseded
- [ ] `test_virtual_clause_conversion` — RequirementMap → virtual clauses format matches expected schema

### Integration Tests

- [ ] Upload regulation → requirements auto-extracted → visible via GET endpoint
- [ ] Run requirement mapping → RequirementMap stored → retrievable by ID
- [ ] Gap analysis with requirement catalog → results reference requirement_ids
- [ ] Gap analysis without requirement catalog → falls back to existing behavior
- [ ] Re-upload regulation → diff detects changes → requirements updated
- [ ] SSE stream endpoint → sends progress events for each requirement mapped

### Manual Verification

- [ ] Upload RBI PA/PG Master Direction → verify ~45-55 requirements extracted
- [ ] Check requirement IDs follow `RBI-PAPG-*-*` pattern
- [ ] Filter by entity_type="non_bank_pa" → only applicable requirements shown
- [ ] Map against a KYC policy → verify indicator-level coverage makes sense
- [ ] Check Qdrant has embeddings in `requirement_embeddings` collection

---

## 11. DEPENDENCIES

| Dependency | Status | Notes |
|-----------|--------|-------|
| Task #1 (PA/PG Parser) | Spec complete | Provides PA/PG-specific clauses + categories |
| Task #25 (Client Profile) | Spec in progress | Provides `entity_type` for filtering |
| Existing `VectorService` | Available | Used for Qdrant embeddings |
| Existing `SemanticGapAnalysisService` | Available | Consumes RequirementMap via virtual clauses |
| Anthropic API | Available | Claude Sonnet for extraction + mapping LLM calls |

---

## 12. OPEN DESIGN DECISIONS

1. **Requirement versioning strategy:** When a requirement changes, should we create a new version (v2) or update in-place? Recommendation: Create new version, mark old as `superseded`, so historical gap analyses remain valid.

2. **Cross-regulation requirement linking:** Some requirements span multiple regulations (e.g., KYC appears in both PA/PG and NBFC directions). Should we support cross-regulation `related_requirements`? Recommendation: Yes, via `related_requirements` field, but Phase 2 — not MVP.

3. **Custom organization requirements:** Should organizations be able to add their own custom requirements on top of the regulatory catalog? Recommendation: Yes, with `organization` field. System requirements have `organization="system"`, custom ones have the org name. Phase 2.
