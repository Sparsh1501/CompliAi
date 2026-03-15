# Task #25: Build Client Profile Management (Bank vs Non-bank PA)

## Implementation Specification

---

## 1. OBJECTIVE

Build a client (organization) profile system that captures the entity type of each organization — bank PA, non-bank PA, PA-P, PG, NBFC, etc. — so that the platform can:

1. **Filter applicable requirements** (Task #4) to only those relevant to the entity type
2. **Scope gap analysis** appropriately (e.g., capital requirements differ for bank vs non-bank PAs)
3. **Tailor dashboard** metrics to entity-specific KPIs
4. **Pre-fill compliance checklists** based on entity type

**Current State:** The `User` model has a simple `organization: str = "Default Org"` field. The `ComplianceCharter` model provides product-level grouping but not entity-level classification. There is no concept of entity type, license status, or organizational profile.

---

## 2. ARCHITECTURE OVERVIEW

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend: Organization Settings                              │
│  Settings.js → new "Organization Profile" tab                │
├──────────────────────────────────────────────────────────────┤
│  Fields:                                                      │
│  - Organization name                                          │
│  - Entity type (Bank PA / Non-bank PA / PA-P / PG / NBFC)    │
│  - License status (Applied / Authorized / Conditional)        │
│  - Bank type (if Bank PA: scheduled commercial / cooperative) │
│  - Authorized activities (online / physical / both)           │
│  - RBI registration number                                    │
│  - Net worth (for capital compliance checks)                  │
│  - Business commencement date                                 │
│  - Key personnel (MD, CCO, CTO, CISO)                        │
└──────────────┬───────────────────────────────────────────────┘
               │ PUT /api/organization/profile
               ▼
┌──────────────────────────────────────────────────────────────┐
│  Backend: Organization Profile Service                        │
│  services/organization_profile_service.py                     │
├──────────────────────────────────────────────────────────────┤
│  1. CRUD organization profile                                 │
│  2. Determine applicable regulatory scope                     │
│  3. Provide entity_type to RequirementMappingService          │
│  4. License timeline tracking                                 │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
          MongoDB (organizations collection)
```

---

## 3. FILES TO CREATE

### 3.1 `backend/services/organization_profile_service.py` (NEW)

**Purpose:** Manage organization profiles, entity type classification, and regulatory scope determination.

```python
"""
Organization Profile Service for CompliAI

Manages organization profiles including entity classification (bank PA,
non-bank PA, etc.), license tracking, and regulatory scope determination.

Key Features:
- Entity type classification with PA/PG-specific attributes
- License status tracking (applied → authorized → renewal)
- Regulatory scope determination (which regulations apply)
- Key personnel tracking (MD, CCO, CTO, CISO)
"""

import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class OrganizationProfileService:
    """
    CRUD + business logic for organization profiles.

    Central source of truth for "what kind of entity is this organization?"
    Used by:
    - RequirementMappingService (entity_type filtering)
    - Gap analysis (scope determination)
    - Dashboard (entity-specific KPIs)
    - Compliance checklists (pre-fill based on entity type)
    """

    def __init__(self, db=None):
        """
        Args:
            db: Motor async MongoDB database instance
        """
        self.db = db

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================

    async def create_profile(
        self,
        organization_name: str,
        entity_type: str,
        created_by_user_id: str,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new organization profile.

        Called during:
        1. First-time organization setup (after registration)
        2. Admin manually creating a profile

        Args:
            organization_name: Name of the organization (matches User.organization)
            entity_type: One of EntityType enum values
            created_by_user_id: ID of the user creating the profile
            profile_data: Additional profile fields (see OrganizationProfile model)

        Returns:
            Created profile dict
        """
        pass

    async def get_profile(
        self,
        organization: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get organization profile by organization name.

        Returns None if no profile exists (backward compatible —
        organizations without profiles use defaults).
        """
        pass

    async def update_profile(
        self,
        organization: str,
        update_data: Dict[str, Any],
        updated_by_user_id: str
    ) -> Dict[str, Any]:
        """
        Update organization profile fields.

        Records an audit entry in profile_history for compliance.
        Only updates fields present in update_data (partial update).
        """
        pass

    async def get_or_create_default_profile(
        self,
        organization: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get existing profile or create a minimal default one.

        Default entity_type is "unknown" — user must complete setup.
        Used to ensure every organization has at least a stub profile.
        """
        pass

    # =========================================================================
    # REGULATORY SCOPE DETERMINATION
    # =========================================================================

    async def get_applicable_entity_scope(
        self,
        organization: str
    ) -> str:
        """
        Determine the ApplicabilityScope value for this organization.

        Maps entity_type to requirement filtering scope:
          bank_pa       → "bank_pa"
          non_bank_pa   → "non_bank_pa"
          pa_p          → "pa_p"
          pg_only       → "pg_only"
          nbfc          → "all"  (NBFC regulations, not PA/PG)
          unknown       → "all"  (show everything until classified)

        Returns:
            ApplicabilityScope string value
        """
        pass

    async def get_applicable_regulations(
        self,
        organization: str
    ) -> List[str]:
        """
        Determine which regulation types apply to this entity.

        Returns list of regulation identifiers/types that should
        be shown and used in gap analysis for this organization.

        Examples:
          bank_pa → ["rbi_pa_pg", "kyc_master", "it_governance"]
          non_bank_pa → ["rbi_pa_pg", "kyc_master", "it_governance", "capital_adequacy"]
          nbfc → ["nbfc_master", "kyc_master", "digital_lending"]
        """
        pass

    def get_entity_specific_thresholds(
        self,
        entity_type: str
    ) -> Dict[str, Any]:
        """
        Return entity-specific compliance thresholds.

        Examples:
          non_bank_pa: { "min_net_worth_crore": 15, "escrow_required": True,
                         "nodal_account_required": True }
          bank_pa:     { "min_net_worth_crore": null, "escrow_required": True,
                         "nodal_account_required": True }
          pa_p:        { "min_net_worth_crore": 15, "escrow_required": True,
                         "physical_inspection_required": True }
        """
        pass

    # =========================================================================
    # KEY PERSONNEL MANAGEMENT
    # =========================================================================

    async def update_key_personnel(
        self,
        organization: str,
        personnel: List[Dict[str, Any]],
        updated_by_user_id: str
    ) -> Dict[str, Any]:
        """
        Update key personnel list for the organization.

        Each personnel entry:
        {
            "role": "cco",  # md, cco, cto, ciso, cfo, cs
            "name": "Jane Doe",
            "email": "jane@example.com",
            "appointment_date": "2024-01-15",
            "is_fit_and_proper": true
        }

        Regulatory requirement: PA/PGs must have designated CCO, CISO, etc.
        """
        pass

    # =========================================================================
    # LICENSE TRACKING
    # =========================================================================

    async def update_license_status(
        self,
        organization: str,
        license_data: Dict[str, Any],
        updated_by_user_id: str
    ) -> Dict[str, Any]:
        """
        Update license/authorization status.

        Tracks:
        - Application date (PRAVAAH submission)
        - In-principle authorization date
        - Final authorization date
        - Authorization number
        - Validity period
        - Renewal due date
        """
        pass

    async def get_license_timeline(
        self,
        organization: str
    ) -> List[Dict[str, Any]]:
        """
        Get license status history as timeline events.

        Returns chronological list:
        [
            {"date": "2024-03-15", "event": "application_submitted", "details": "..."},
            {"date": "2024-06-01", "event": "in_principle_granted", "details": "..."},
            {"date": "2024-12-01", "event": "final_authorization", "details": "..."}
        ]
        """
        pass

    # =========================================================================
    # PROFILE HISTORY / AUDIT
    # =========================================================================

    async def get_profile_history(
        self,
        organization: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail of profile changes.

        Each entry: { "timestamp", "changed_by", "field", "old_value", "new_value" }
        Stored in organization_profile_history collection.
        """
        pass
```

---

## 4. FILES TO MODIFY

### 4.1 `backend/models.py`

**Add new enums and models** (after `ComplianceCharterCreate` at ~line 279):

```python
# --- Organization Profile Models ---

class EntityType(str, Enum):
    """Type of regulated entity."""
    BANK_PA = "bank_pa"              # Bank Payment Aggregator
    NON_BANK_PA = "non_bank_pa"      # Non-bank Payment Aggregator
    PA_P = "pa_p"                    # PA-P (physical POS aggregator)
    PG_ONLY = "pg_only"             # Payment Gateway (not PA)
    NBFC = "nbfc"                    # NBFC
    DIGITAL_LENDER = "digital_lender"  # Digital Lending entity
    FINTECH = "fintech"              # FinTech (generic)
    UNKNOWN = "unknown"              # Not yet classified

class BankType(str, Enum):
    """Sub-type for bank PAs."""
    SCHEDULED_COMMERCIAL = "scheduled_commercial"
    COOPERATIVE = "cooperative"
    SMALL_FINANCE = "small_finance"
    PAYMENTS_BANK = "payments_bank"
    NOT_APPLICABLE = "not_applicable"

class LicenseStatus(str, Enum):
    """Authorization/license status with RBI."""
    NOT_APPLIED = "not_applied"
    APPLICATION_SUBMITTED = "application_submitted"   # Via PRAVAAH
    IN_PRINCIPLE = "in_principle"                      # In-principle authorization
    AUTHORIZED = "authorized"                          # Final authorization
    CONDITIONAL = "conditional"                        # With conditions
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    RENEWAL_PENDING = "renewal_pending"

class KeyPersonnel(BaseModel):
    """Key management personnel for regulatory compliance."""
    model_config = ConfigDict(extra="ignore")
    role: str           # md, cco, cto, ciso, cfo, cs, nodal_officer
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    appointment_date: Optional[str] = None    # ISO date
    is_fit_and_proper: bool = True            # RBI fit-and-proper criteria
    din_number: Optional[str] = None          # Director Identification Number

class OrganizationProfile(BaseModel):
    """
    Organization profile with entity classification and regulatory attributes.
    One profile per organization. Linked to User.organization field.
    """
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization: str              # Must match User.organization (linking key)

    # Entity Classification
    entity_type: str = EntityType.UNKNOWN.value
    bank_type: Optional[str] = None          # Only for bank_pa
    authorized_activities: List[str] = []    # ["online", "physical", "both"]
    business_categories: List[str] = []      # ["e-commerce", "utilities", "education"]

    # License / Authorization
    license_status: str = LicenseStatus.NOT_APPLIED.value
    rbi_registration_number: Optional[str] = None
    authorization_date: Optional[str] = None       # ISO date
    authorization_validity: Optional[str] = None   # ISO date (expiry)
    pravaah_application_id: Optional[str] = None

    # Financial
    net_worth_crore: Optional[float] = None        # Latest audited net worth in crore
    net_worth_as_of: Optional[str] = None          # Date of net worth certificate
    escrow_bank_name: Optional[str] = None
    escrow_account_number: Optional[str] = None
    nodal_account_bank: Optional[str] = None
    nodal_account_number: Optional[str] = None

    # Key Personnel
    key_personnel: List[Dict[str, Any]] = []   # Serialised KeyPersonnel list

    # Business Info
    business_commencement_date: Optional[str] = None
    registered_address: Optional[str] = None
    cin_number: Optional[str] = None               # Corporate Identity Number
    website: Optional[str] = None
    merchant_count: Optional[int] = None           # Approximate merchant base
    annual_transaction_volume: Optional[float] = None  # In crore per annum

    # Compliance Metadata
    applicable_regulations: List[str] = []   # Auto-populated regulation type IDs
    compliance_charters: List[str] = []      # Linked ComplianceCharter IDs
    last_rbi_inspection_date: Optional[str] = None
    next_audit_due_date: Optional[str] = None

    # Profile completeness
    setup_completed: bool = False   # True when all required fields are filled
    setup_completion_pct: int = 0   # 0–100

    # Audit
    created_by: str = ""
    updated_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OrganizationProfileCreate(BaseModel):
    """Input model for creating organization profile."""
    organization: str
    entity_type: str
    bank_type: Optional[str] = None
    authorized_activities: List[str] = []
    license_status: str = "not_applied"
    rbi_registration_number: Optional[str] = None
    net_worth_crore: Optional[float] = None
    business_commencement_date: Optional[str] = None
    key_personnel: List[Dict[str, Any]] = []

class OrganizationProfileUpdate(BaseModel):
    """Input model for updating organization profile (all fields optional)."""
    entity_type: Optional[str] = None
    bank_type: Optional[str] = None
    authorized_activities: Optional[List[str]] = None
    license_status: Optional[str] = None
    rbi_registration_number: Optional[str] = None
    authorization_date: Optional[str] = None
    authorization_validity: Optional[str] = None
    pravaah_application_id: Optional[str] = None
    net_worth_crore: Optional[float] = None
    net_worth_as_of: Optional[str] = None
    escrow_bank_name: Optional[str] = None
    escrow_account_number: Optional[str] = None
    nodal_account_bank: Optional[str] = None
    nodal_account_number: Optional[str] = None
    key_personnel: Optional[List[Dict[str, Any]]] = None
    business_commencement_date: Optional[str] = None
    registered_address: Optional[str] = None
    cin_number: Optional[str] = None
    website: Optional[str] = None
    merchant_count: Optional[int] = None
    annual_transaction_volume: Optional[float] = None
    business_categories: Optional[List[str]] = None
```

### 4.2 `backend/server.py`

#### 4.2a Import & initialise service (~line 40–44)

```python
from services.organization_profile_service import OrganizationProfileService
```

After other service initialisations:

```python
org_profile_service = OrganizationProfileService(db=db)
```

#### 4.2b New API endpoints (add in a logical section, e.g. after user/auth endpoints)

```python
# ========== ORGANIZATION PROFILE ENDPOINTS ==========

@api_router.get("/organization/profile")
async def get_organization_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Get the organization profile for the current user's organization.
    Auto-creates a default profile if none exists.
    """
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')

    profile = await org_profile_service.get_or_create_default_profile(
        organization=organization,
        user_id=current_user['user_id']
    )
    return profile

@api_router.put("/organization/profile")
async def update_organization_profile(
    update: OrganizationProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the organization profile.
    Only admin/compliance_head roles can update.
    Partial update — only fields present in request body are changed.
    """
    # Role check
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can update org profile")

    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')

    update_data = update.model_dump(exclude_none=True)
    profile = await org_profile_service.update_profile(
        organization=organization,
        update_data=update_data,
        updated_by_user_id=current_user['user_id']
    )
    return profile

@api_router.post("/organization/profile")
async def create_organization_profile(
    profile_data: OrganizationProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create an organization profile (first-time setup).
    Only admin/compliance_head roles can create.
    """
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can create org profile")

    profile = await org_profile_service.create_profile(
        organization_name=profile_data.organization,
        entity_type=profile_data.entity_type,
        created_by_user_id=current_user['user_id'],
        profile_data=profile_data.model_dump()
    )
    return profile

@api_router.get("/organization/profile/entity-scope")
async def get_entity_scope(
    current_user: dict = Depends(get_current_user)
):
    """
    Get the applicable entity scope for the current organization.
    Used by gap analysis and requirement filtering to know which
    requirements apply.

    Returns: { "entity_type": "non_bank_pa", "scope": "non_bank_pa",
               "thresholds": {...} }
    """
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
    personnel: List[Dict[str, Any]],
    current_user: dict = Depends(get_current_user)
):
    """
    Update key personnel for the organization.
    Validates required roles: at least CCO and one of CTO/CISO.
    """
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can update personnel")

    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')

    result = await org_profile_service.update_key_personnel(
        organization=organization,
        personnel=personnel,
        updated_by_user_id=current_user['user_id']
    )
    return result

@api_router.put("/organization/profile/license")
async def update_license_status(
    license_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Update license/authorization status.
    Records a license timeline event.
    """
    if current_user.get('role') not in ['admin', 'compliance_head']:
        raise HTTPException(status_code=403, detail="Only admin or compliance head can update license")

    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')

    result = await org_profile_service.update_license_status(
        organization=organization,
        license_data=license_data,
        updated_by_user_id=current_user['user_id']
    )
    return result

@api_router.get("/organization/profile/license-timeline")
async def get_license_timeline(
    current_user: dict = Depends(get_current_user)
):
    """Get license status timeline events."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')

    timeline = await org_profile_service.get_license_timeline(organization)
    return {"timeline": timeline}

@api_router.get("/organization/profile/history")
async def get_profile_history(
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get audit trail of organization profile changes."""
    user_doc = await db.users.find_one({"id": current_user['user_id']}, {"organization": 1, "_id": 0})
    organization = (user_doc or {}).get('organization', 'Default Org')

    history = await org_profile_service.get_profile_history(organization, limit)
    return {"history": history}
```

#### 4.2c Inject entity_type into gap analysis (~line 3981)

In `run_gap_analysis()`, after fetching user_organization, add:

```python
# Get entity scope for requirement filtering
org_profile = await db.organizations.find_one(
    {"organization": user_organization}, {"entity_type": 1, "_id": 0}
)
entity_type = (org_profile or {}).get('entity_type', 'all')

# Pass entity_type to requirement mapping (if catalog exists)
# See Task #4 spec for full integration
```

### 4.3 `frontend/src/lib/api.js`

Add organization profile API methods:

```javascript
// --- Organization Profile API ---
export const organizationApi = {
  getProfile: () =>
    api.get('/organization/profile'),

  updateProfile: (data) =>
    api.put('/organization/profile', data),

  createProfile: (data) =>
    api.post('/organization/profile', data),

  getEntityScope: () =>
    api.get('/organization/profile/entity-scope'),

  updatePersonnel: (personnel) =>
    api.put('/organization/profile/personnel', personnel),

  updateLicense: (data) =>
    api.put('/organization/profile/license', data),

  getLicenseTimeline: () =>
    api.get('/organization/profile/license-timeline'),

  getProfileHistory: (limit = 50) =>
    api.get('/organization/profile/history', { params: { limit } }),
};
```

### 4.4 `frontend/src/pages/Settings.js`

**Add new "Organization Profile" tab** to the existing 3-tab Settings structure:

Currently the Settings page has 3 tabs (from recent refactor):
- General
- Compliance
- Security & AI

Add a 4th tab: **"Organization"** (insert as 2nd tab, after General).

This tab renders the `OrganizationProfileForm` component (see Section 5).

### 4.5 `frontend/src/components/CharterManagement.jsx`

**Link charters to organization profile:**

When creating/editing a charter, auto-populate `regulatory_bodies` from the organization profile's `applicable_regulations` list. Add a visual indicator showing which charters are linked to the org profile.

---

## 5. FRONTEND COMPONENTS

### 5.1 `frontend/src/components/OrganizationProfileForm.jsx` (NEW)

**Purpose:** Form for viewing and editing the organization profile.

```
┌─────────────────────────────────────────────────────────────┐
│  Organization Profile                           [Save]       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ Entity Classification ─────────────────────────────┐    │
│  │  Entity Type: [Non-bank PA ▼]                       │    │
│  │  Authorized Activities: [✓ Online] [✓ Physical]     │    │
│  │  Business Categories: [e-commerce, utilities]        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ License & Authorization ───────────────────────────┐    │
│  │  Status: ● Authorized                               │    │
│  │  RBI Registration: PA-XYZ-2024-001                  │    │
│  │  Authorization Date: 2024-12-01                     │    │
│  │  Validity: 2027-12-01                               │    │
│  │  PRAVAAH ID: PRV-2024-00123                         │    │
│  │  [View License Timeline →]                          │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ Financial ─────────────────────────────────────────┐    │
│  │  Net Worth: ₹18.5 crore (as of 2024-03-31)         │    │
│  │  Escrow Bank: SBI | A/c: ****1234                   │    │
│  │  Nodal Account: HDFC | A/c: ****5678                │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ Key Personnel ─────────────────────────────────────┐    │
│  │  MD:   Rajesh Kumar          Appointed: 2024-01-15  │    │
│  │  CCO:  Priya Sharma    ✓ F&P Appointed: 2024-03-01  │    │
│  │  CISO: Amit Singh      ✓ F&P Appointed: 2024-02-01  │    │
│  │  [+ Add Personnel]                                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ Business Information ──────────────────────────────┐    │
│  │  CIN: U74999MH2020PTC345678                         │    │
│  │  Commencement: 2020-06-15                           │    │
│  │  Website: https://example.com                       │    │
│  │  Merchants: ~5,000                                  │    │
│  │  Annual Volume: ₹2,500 crore                        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  Profile Completeness: ████████████░░ 85%                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**UI Library:** Shadcn/UI components:
- `Select` for entity type, bank type, license status dropdowns
- `Input` for text fields (registration number, CIN, etc.)
- `Checkbox` group for authorized activities
- `Badge` components for status indicators
- `Card` for each section grouping
- `Progress` bar for profile completeness
- `Dialog` for key personnel add/edit modal
- `Table` for personnel list

**Conditional Rendering:**
- Bank type dropdown only shows when entity_type = "bank_pa"
- Escrow/nodal account fields only show for PA entity types
- PA-P-specific fields (physical inspection dates) only for entity_type = "pa_p"

### 5.2 `frontend/src/components/LicenseTimeline.jsx` (NEW)

**Purpose:** Visual timeline of license status changes.

Uses a vertical timeline layout:
- Each event is a node with date, event type, and description
- Color-coded by event type (green=authorization, yellow=renewal, red=suspension)
- Expandable details per event

### 5.3 `frontend/src/components/EntityScopeBadge.jsx` (NEW)

**Purpose:** Small reusable badge showing the organization's entity type.

Displayed on:
- Dashboard header
- Gap analysis page (to show which entity scope is applied)
- Regulation list (to show applicability)

```jsx
// Example usage:
<EntityScopeBadge entityType="non_bank_pa" />
// Renders: [Non-bank PA] badge with appropriate color
```

---

## 6. MONGODB SCHEMA CHANGES

### 6.1 New Collection: `organizations`

```javascript
// Index definitions
db.organizations.createIndex({ "organization": 1 }, { unique: true })
db.organizations.createIndex({ "entity_type": 1 })
db.organizations.createIndex({ "license_status": 1 })

// Sample document
{
  "id": "uuid",
  "organization": "Acme Payments Pvt Ltd",

  "entity_type": "non_bank_pa",
  "bank_type": null,
  "authorized_activities": ["online"],
  "business_categories": ["e-commerce", "utilities", "education"],

  "license_status": "authorized",
  "rbi_registration_number": "PA-XYZ-2024-001",
  "authorization_date": "2024-12-01",
  "authorization_validity": "2027-12-01",
  "pravaah_application_id": "PRV-2024-00123",

  "net_worth_crore": 18.5,
  "net_worth_as_of": "2024-03-31",
  "escrow_bank_name": "State Bank of India",
  "escrow_account_number": "XXXX1234",
  "nodal_account_bank": "HDFC Bank",
  "nodal_account_number": "XXXX5678",

  "key_personnel": [
    {
      "role": "md",
      "name": "Rajesh Kumar",
      "email": "rajesh@acme.com",
      "appointment_date": "2024-01-15",
      "is_fit_and_proper": true,
      "din_number": "01234567"
    },
    {
      "role": "cco",
      "name": "Priya Sharma",
      "email": "priya@acme.com",
      "appointment_date": "2024-03-01",
      "is_fit_and_proper": true
    },
    {
      "role": "ciso",
      "name": "Amit Singh",
      "email": "amit@acme.com",
      "appointment_date": "2024-02-01",
      "is_fit_and_proper": true
    }
  ],

  "business_commencement_date": "2020-06-15",
  "registered_address": "123, Tech Park, Mumbai 400001",
  "cin_number": "U74999MH2020PTC345678",
  "website": "https://acmepayments.com",
  "merchant_count": 5000,
  "annual_transaction_volume": 2500.0,

  "applicable_regulations": ["rbi_pa_pg", "kyc_master", "it_governance"],
  "compliance_charters": ["charter-uuid-1"],
  "last_rbi_inspection_date": "2024-06-15",
  "next_audit_due_date": "2025-06-15",

  "setup_completed": true,
  "setup_completion_pct": 85,

  "created_by": "user-uuid",
  "updated_by": "user-uuid",
  "created_at": "2024-03-15T10:00:00Z",
  "updated_at": "2025-01-10T14:30:00Z"
}
```

### 6.2 New Collection: `organization_profile_history`

```javascript
// Index definitions
db.organization_profile_history.createIndex({ "organization": 1, "timestamp": -1 })

// Sample document (one per field change)
{
  "id": "uuid",
  "organization": "Acme Payments Pvt Ltd",
  "timestamp": "2025-01-10T14:30:00Z",
  "changed_by": "user-uuid",
  "changed_by_name": "Priya Sharma",
  "field": "net_worth_crore",
  "old_value": 15.0,
  "new_value": 18.5,
  "change_reason": "Annual audit update"
}
```

### 6.3 New Collection: `license_timeline`

```javascript
// Index definitions
db.license_timeline.createIndex({ "organization": 1, "date": -1 })

// Sample document
{
  "id": "uuid",
  "organization": "Acme Payments Pvt Ltd",
  "date": "2024-12-01",
  "event": "final_authorization",
  "title": "Final Authorization Granted",
  "description": "RBI granted final authorization for online PA operations",
  "details": {
    "registration_number": "PA-XYZ-2024-001",
    "conditions": [],
    "validity": "2027-12-01"
  },
  "recorded_by": "user-uuid",
  "created_at": "2024-12-01T09:00:00Z"
}
```

---

## 7. INTEGRATION POINTS

### 7.1 With Task #4 (Requirement Mapping Engine)

The organization profile's `entity_type` is the key input for requirement filtering:

```python
# In RequirementMappingService.map_requirements_to_policy():
# 1. Get organization profile
org_profile = await db.organizations.find_one({"organization": organization})
entity_type = org_profile.get('entity_type', 'all') if org_profile else 'all'

# 2. Filter requirements by entity applicability
requirements = await self.get_requirements_for_regulation(
    regulation_id=regulation_id,
    entity_type=entity_type  # Only show applicable requirements
)
```

### 7.2 With Gap Analysis

```python
# In run_gap_analysis() (server.py):
# After getting user_organization, fetch entity scope
org_profile = await db.organizations.find_one(
    {"organization": user_organization}, {"_id": 0}
)
entity_type = (org_profile or {}).get('entity_type', 'all')

# Pass to gap analysis for requirement filtering
gap_report = await semantic_gap_service.analyze(
    # ... existing params ...
    entity_type=entity_type  # NEW parameter
)
```

### 7.3 With Dashboard

Entity-specific dashboard KPIs:

| Entity Type | Specific KPIs |
|------------|---------------|
| non_bank_pa | Net worth compliance (>=₹15cr), escrow reconciliation, PRAVAAH renewal |
| bank_pa | Escrow compliance, nodal account, IT audit compliance |
| pa_p | Physical inspection status, terminal compliance, location audit |
| nbfc | Capital adequacy ratio, NPA levels, ALM compliance |

### 7.4 With Registration / Onboarding

When a new user registers, the first-time setup flow should include:
1. Organization name (existing)
2. **Entity type selection** (new — from this task)
3. **Basic profile fields** (new)

This can be a wizard-style onboarding dialog shown after first login.

---

## 8. ENTITY-SPECIFIC THRESHOLDS

```python
ENTITY_THRESHOLDS = {
    "non_bank_pa": {
        "min_net_worth_crore": 15,
        "escrow_account_required": True,
        "nodal_account_required": True,
        "min_key_personnel": ["cco", "ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": True,
        "physical_inspection": False,
    },
    "bank_pa": {
        "min_net_worth_crore": None,  # Per bank's existing norms
        "escrow_account_required": True,
        "nodal_account_required": True,
        "min_key_personnel": ["cco", "ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": False,  # Banks apply via existing channel
        "physical_inspection": False,
    },
    "pa_p": {
        "min_net_worth_crore": 15,
        "escrow_account_required": True,
        "nodal_account_required": True,
        "min_key_personnel": ["cco", "ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": True,
        "physical_inspection": True,
        "terminal_compliance_check": True,
    },
    "pg_only": {
        "min_net_worth_crore": None,
        "escrow_account_required": False,
        "nodal_account_required": False,
        "min_key_personnel": ["ciso"],
        "system_audit_frequency": "annual",
        "pravaah_required": False,
        "physical_inspection": False,
    },
}
```

---

## 9. PROFILE COMPLETENESS CALCULATION

```python
def calculate_profile_completeness(profile: Dict[str, Any]) -> int:
    """
    Calculate profile completion percentage based on required fields.

    Weighted sections:
    - Entity classification (20%): entity_type, authorized_activities
    - License (20%): license_status, registration_number
    - Financial (20%): net_worth, escrow details
    - Personnel (20%): CCO + CISO at minimum
    - Business (20%): CIN, commencement date, website

    Returns 0–100 integer.
    """
    score = 0

    # Entity classification (20 points)
    if profile.get('entity_type') and profile['entity_type'] != 'unknown':
        score += 10
    if profile.get('authorized_activities'):
        score += 10

    # License (20 points)
    if profile.get('license_status') and profile['license_status'] != 'not_applied':
        score += 10
    if profile.get('rbi_registration_number'):
        score += 10

    # Financial (20 points)
    if profile.get('net_worth_crore') is not None:
        score += 10
    if profile.get('escrow_bank_name') or profile.get('entity_type') in ['pg_only', 'bank_pa']:
        score += 10

    # Personnel (20 points)
    personnel = profile.get('key_personnel', [])
    roles = {p.get('role') for p in personnel}
    if 'cco' in roles:
        score += 10
    if 'ciso' in roles or 'cto' in roles:
        score += 10

    # Business (20 points)
    if profile.get('cin_number'):
        score += 10
    if profile.get('business_commencement_date'):
        score += 10

    return min(score, 100)
```

---

## 10. TESTING CHECKLIST

### Unit Tests (`tests/test_organization_profile.py`)

- [ ] `test_create_profile_basic` — Create profile with required fields
- [ ] `test_entity_type_validation` — Invalid entity type rejected
- [ ] `test_update_partial` — Partial update only changes specified fields
- [ ] `test_profile_completeness_empty` — Empty profile → 0%
- [ ] `test_profile_completeness_full` — Full profile → 100%
- [ ] `test_entity_scope_bank_pa` — Bank PA → scope "bank_pa"
- [ ] `test_entity_scope_non_bank_pa` — Non-bank PA → scope "non_bank_pa"
- [ ] `test_entity_scope_unknown` — Unknown → scope "all"
- [ ] `test_thresholds_non_bank` — Non-bank PA thresholds include min net worth ₹15cr
- [ ] `test_thresholds_bank` — Bank PA thresholds have null min net worth
- [ ] `test_key_personnel_crud` — Add, update, remove personnel
- [ ] `test_license_timeline_creation` — License update creates timeline event
- [ ] `test_profile_history_audit` — Profile change recorded in history

### Integration Tests

- [ ] GET /organization/profile → auto-creates default for new org
- [ ] PUT /organization/profile → updates profile, records audit history
- [ ] GET /organization/profile/entity-scope → returns correct scope + thresholds
- [ ] Non-admin user gets 403 on PUT/POST endpoints
- [ ] Entity type change propagates to applicable_regulations list
- [ ] Profile completeness recalculated on each update
- [ ] License timeline endpoint returns chronological events

### Manual Verification

- [ ] Settings page shows "Organization" tab
- [ ] Entity type dropdown works, conditional fields appear/hide correctly
- [ ] Bank type sub-dropdown only visible when entity_type = bank_pa
- [ ] Key personnel table editable with add/remove
- [ ] Profile completeness bar updates in real-time
- [ ] License timeline displays correctly with color-coded events
- [ ] EntityScopeBadge appears on dashboard and gap analysis pages

---

## 11. DEPENDENCIES

| Dependency | Status | Notes |
|-----------|--------|-------|
| Task #4 (Requirement Mapping) | Spec complete | Consumes entity_type for filtering |
| Existing User model | Available | Links via `organization` string field |
| Existing ComplianceCharter | Available | Links via `compliance_charters` array |
| Settings.js page | Available | Add new "Organization" tab |
| Shadcn/UI components | Available | Select, Input, Badge, Card, Table, Dialog, Progress |

---

## 12. OPEN DESIGN DECISIONS

1. **Organization as a first-class entity vs User field:** Currently `organization` is just a string on User. Should we create a formal `Organization` collection that users belong to (with org-level settings, billing, etc.)? **Recommendation:** Yes — this task effectively creates that collection (`organizations`). Future work can migrate the User.organization string to a foreign key reference.

2. **Multi-organization support:** Should a user be able to belong to multiple organizations? **Recommendation:** Not for MVP. Keep the current 1:1 user→org relationship. Support multi-org in Phase 2 via an `org_memberships` collection.

3. **Onboarding wizard:** Should first login force a profile setup wizard? **Recommendation:** Show a "Complete your organization profile" banner on the dashboard instead of blocking. Required for gap analysis features to work with entity filtering, but not a hard gate.

4. **Profile field sensitivity:** Financial fields (net worth, account numbers) may need encryption at rest. **Recommendation:** Phase 2 — use field-level encryption for `escrow_account_number`, `nodal_account_number`. For MVP, mask in API responses (show only last 4 digits).
