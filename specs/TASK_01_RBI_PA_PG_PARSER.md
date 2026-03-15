# Task #1: Parse and Ingest RBI PA/PG Master Direction (Sep 2025)

## Implementation Specification

---

## 1. OBJECTIVE

Build a specialized parser/service for the RBI Master Direction on Regulation of Payment Aggregators (September 2025 consolidated). Extract ~50 regulatory requirements into structured format with PA/PG-specific semantic enrichment, store in MongoDB + Qdrant, and integrate with the existing regulation upload pipeline.

---

## 2. ARCHITECTURE OVERVIEW

```
                     ┌─────────────────────────────┐
                     │  Existing Upload Pipeline     │
                     │  POST /api/regulations        │
                     └──────────┬──────────────────┘
                                │
                                ▼
                     ┌─────────────────────────────┐
                     │  DocumentService              │
                     │  (3-tier OCR: Claude→PyPDF2   │
                     │   →Mistral)                   │
                     └──────────┬──────────────────┘
                                │
                                ▼
               ┌────────────────────────────────────┐
               │  NEW: PA/PG Regulation Service      │
               │  services/pa_pg_regulation_service.py│
               ├────────────────────────────────────┤
               │  1. Detect PA/PG Master Direction   │
               │  2. PA/PG-specific clause extraction│
               │  3. Map to ~50 RBI requirements     │
               │  4. Enrich with PA/PG taxonomy      │
               │  5. Set deadlines & applicability   │
               └────────┬──────────┬────────────────┘
                        │          │
                        ▼          ▼
                   MongoDB     Qdrant
              (regulations)  (regulation_clauses)
```

---

## 3. FILES TO CREATE

### 3.1 `backend/services/pa_pg_regulation_service.py` (NEW)

**Purpose:** Specialized service for RBI PA/PG Master Direction parsing

**Class: `PAPGRegulationService`**

```python
class PAPGRegulationService:
    """
    Specialized parser for RBI Master Direction on Payment Aggregators.
    Handles the Sep 2025 consolidated PA/PG directions including PA-P.
    """

    # ~50 RBI PA/PG requirements organized by category
    PA_PG_REQUIREMENTS: Dict[str, List[Dict]] = {
        "authorisation": [...],
        "capital_requirements": [...],
        "merchant_onboarding": [...],
        "settlement_operations": [...],
        "pa_p_physical": [...],
        "escrow_accounts": [...],
        "fraud_monitoring": [...],
        "governance_compliance": [...],
        "technology_security": [...],
        "customer_protection": [...]
    }

    async def detect_pa_pg_regulation(self, text: str, metadata: dict) -> bool:
        """
        Detect if uploaded regulation is an RBI PA/PG Master Direction.
        Uses keyword scoring: "payment aggregator", "payment gateway",
        "PA-P", "PRAVAAH", "escrow account", "merchant onboarding",
        "settlement", "nodal account" etc.
        Returns True if confidence > 0.7
        """

    async def extract_pa_pg_requirements(
        self,
        full_text: str,
        clauses: List[dict]
    ) -> List[dict]:
        """
        Map extracted clauses to the ~50 known PA/PG requirements.
        For each requirement:
          - requirement_id: "PA_PG_AUTH_001" format
          - category: authorisation | capital | merchant | settlement | etc.
          - rbi_para_reference: "Para 8.2" or "Section 15(1)"
          - requirement_text: exact RBI text
          - applicability: bank | non_bank | both | pa_p_only
          - deadline: ISO date if applicable
          - criticality: critical | high | medium | low
          - compliance_indicators: what proves compliance
        """

    async def enrich_clauses_for_pa_pg(
        self,
        clauses: List[dict]
    ) -> List[dict]:
        """
        Add PA/PG-specific semantic enrichment to extracted clauses:
        - pa_pg_category (one of the 10 categories above)
        - applicability_profile (bank, non_bank, pa_p)
        - regulatory_deadline (if any)
        - rbi_paragraph_reference
        - linked_requirement_ids (from PA_PG_REQUIREMENTS)
        """

    async def build_requirement_index(
        self,
        regulation_id: str,
        requirements: List[dict]
    ) -> dict:
        """
        Create a structured index of all ~50 requirements for this regulation.
        Stored as a sub-document in the regulation record.
        Used by gap analysis to check client docs against each requirement.
        """
```

**Key Methods Detail:**

| Method | Input | Output | LLM Usage |
|--------|-------|--------|-----------|
| `detect_pa_pg_regulation` | Raw text + metadata | bool (is PA/PG) | None (keyword scoring) |
| `extract_pa_pg_requirements` | Full text + clauses | List[PARequirement] | Claude Sonnet for mapping |
| `enrich_clauses_for_pa_pg` | Clause list | Enriched clause list | Claude Sonnet for categorization |
| `build_requirement_index` | regulation_id + requirements | Indexed requirement map | None |

---

### 3.2 `backend/config/pa_pg_requirements.py` (NEW)

**Purpose:** Static definition of ~50 RBI PA/PG requirements

```python
"""
RBI PA/PG Master Direction - Requirement Catalog
Based on: Master Direction on Regulation of Payment Aggregators (Sep 2025)

Each requirement has:
  - id: Unique identifier (PA_PG_XXX_NNN)
  - category: Requirement category
  - title: Short title
  - rbi_para: RBI paragraph reference
  - description: Full requirement text
  - applicability: Who this applies to
  - deadline: Compliance deadline (if any)
  - criticality: Risk level
  - compliance_indicators: How to verify compliance
  - gap_check_prompt: LLM prompt for gap analysis
"""

PA_PG_REQUIREMENT_CATALOG = [
    # ═══════════════════════════════════════════════════
    # CATEGORY 1: AUTHORISATION (8 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_AUTH_001",
        "category": "authorisation",
        "title": "Certificate of Authorisation (CoA)",
        "rbi_para": "Para 4",
        "description": "Non-bank entities providing PA services must obtain CoA from RBI. Banks are exempt but must intimate RBI.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "CoA certificate from RBI",
            "Application receipt/acknowledgment",
            "RBI correspondence confirming authorisation"
        ],
        "gap_check_prompt": "Check if client has RBI Certificate of Authorisation for PA operations or evidence of application submission."
    },
    {
        "id": "PA_PG_AUTH_002",
        "category": "authorisation",
        "title": "PRAVAAH Portal Application",
        "rbi_para": "Para 4.2",
        "description": "New PA applicants must apply through PRAVAAH portal.",
        "applicability": "non_bank",
        "deadline": "2025-12-31",
        "criticality": "critical",
        "compliance_indicators": [
            "PRAVAAH portal application submission receipt",
            "Application reference number",
            "Supporting documents submitted"
        ],
        "gap_check_prompt": "Check if the entity has submitted application through RBI PRAVAAH portal for PA authorisation."
    },
    {
        "id": "PA_PG_AUTH_003",
        "category": "authorisation",
        "title": "PA-P Notification to RBI",
        "rbi_para": "Para 8.2",
        "description": "Entities conducting physical POS PA activities must notify RBI of PA-P operations.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "RBI notification letter for PA-P",
            "Acknowledgment from RBI",
            "PA-P activity documentation"
        ],
        "gap_check_prompt": "Check if entity has notified RBI about PA-P (physical POS) operations."
    },
    {
        "id": "PA_PG_AUTH_004",
        "category": "authorisation",
        "title": "Bank Exemption Intimation",
        "rbi_para": "Para 4.1",
        "description": "Banks providing PA services are exempt from CoA but must intimate RBI.",
        "applicability": "bank",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Intimation letter to RBI",
            "RBI acknowledgment",
            "Board approval for PA activity"
        ],
        "gap_check_prompt": "For bank PAs: check if intimation has been sent to RBI about PA services."
    },
    {
        "id": "PA_PG_AUTH_005",
        "category": "authorisation",
        "title": "Non-Compliant Entity Cessation",
        "rbi_para": "Para 4.5",
        "description": "Entities operating without authorisation must cease PA operations by Feb 28, 2026.",
        "applicability": "non_bank",
        "deadline": "2026-02-28",
        "criticality": "critical",
        "compliance_indicators": [
            "Authorisation status documentation",
            "Transition plan if unauthorized",
            "Cessation plan or CoA evidence"
        ],
        "gap_check_prompt": "Check if entity has valid authorisation or a plan to cease operations by February 28, 2026."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 2: CAPITAL REQUIREMENTS (5 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_CAP_001",
        "category": "capital_requirements",
        "title": "Minimum Net Worth - Existing PAs",
        "rbi_para": "Para 6.1",
        "description": "Existing PAs must maintain minimum net worth of INR 15 crore.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "Audited financial statements",
            "Net worth certificate from statutory auditor",
            "Annual net worth computation"
        ],
        "gap_check_prompt": "Check for evidence of minimum net worth of INR 15 crore for existing PA."
    },
    {
        "id": "PA_PG_CAP_002",
        "category": "capital_requirements",
        "title": "Minimum Net Worth - New PAs",
        "rbi_para": "Para 6.2",
        "description": "New PA applicants must have minimum net worth of INR 25 crore.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "CA certificate of net worth >= 25 crore",
            "Audited balance sheet",
            "Capital infusion plan if below threshold"
        ],
        "gap_check_prompt": "For new PA applicants: check for evidence of minimum net worth of INR 25 crore."
    },
    {
        "id": "PA_PG_CAP_003",
        "category": "capital_requirements",
        "title": "Net Worth Maintenance",
        "rbi_para": "Para 6.3",
        "description": "PA must maintain prescribed net worth on an ongoing basis with annual certification.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Annual net worth certificate",
            "Quarterly monitoring reports",
            "Board resolution on capital maintenance"
        ],
        "gap_check_prompt": "Check for ongoing net worth maintenance and annual certification process."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 3: MERCHANT ONBOARDING (7 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_MER_001",
        "category": "merchant_onboarding",
        "title": "Merchant KYC - New Onboarding",
        "rbi_para": "Para 15.1",
        "description": "PAs must perform KYC on all merchants at the time of onboarding including identity verification and business verification.",
        "applicability": "both",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "Merchant KYC policy document",
            "KYC checklist for onboarding",
            "Identity verification process",
            "Business verification process"
        ],
        "gap_check_prompt": "Check for comprehensive merchant KYC policy covering identity and business verification at onboarding."
    },
    {
        "id": "PA_PG_MER_002",
        "category": "merchant_onboarding",
        "title": "Physical Merchant Verification",
        "rbi_para": "Para 15.2",
        "description": "Physical verification of merchant premises must be conducted for higher-risk merchants.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Physical verification policy",
            "Risk-based verification criteria",
            "Verification report templates",
            "Photo documentation requirements"
        ],
        "gap_check_prompt": "Check if policy includes physical verification of merchant premises for high-risk merchants."
    },
    {
        "id": "PA_PG_MER_003",
        "category": "merchant_onboarding",
        "title": "Pre-2026 Merchant Enhanced DD",
        "rbi_para": "Para 15.4",
        "description": "Merchants onboarded before 2026 must undergo enhanced due diligence by September 15, 2026.",
        "applicability": "both",
        "deadline": "2026-09-15",
        "criticality": "high",
        "compliance_indicators": [
            "Legacy merchant remediation plan",
            "Enhanced DD checklist for pre-2026 merchants",
            "Timeline for completing re-KYC",
            "Progress tracking mechanism"
        ],
        "gap_check_prompt": "Check if there is a plan for enhanced due diligence on pre-2026 onboarded merchants with Sep 2026 deadline."
    },
    {
        "id": "PA_PG_MER_004",
        "category": "merchant_onboarding",
        "title": "Financial Due Diligence",
        "rbi_para": "Para 15.3",
        "description": "Financial KYC of merchants including assessment of business viability and financial health.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Financial assessment criteria",
            "Bank statement verification process",
            "Business viability assessment",
            "Credit score checks"
        ],
        "gap_check_prompt": "Check for financial due diligence process in merchant onboarding including business viability assessment."
    },
    {
        "id": "PA_PG_MER_005",
        "category": "merchant_onboarding",
        "title": "Ongoing Merchant Monitoring",
        "rbi_para": "Para 15.5",
        "description": "Continuous monitoring of merchant activities including transaction patterns and risk indicators.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Merchant monitoring policy",
            "Transaction pattern analysis",
            "Periodic merchant review schedule",
            "Risk scoring methodology"
        ],
        "gap_check_prompt": "Check for ongoing merchant monitoring process covering transaction patterns and periodic reviews."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 4: SETTLEMENT & OPERATIONS (8 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_SET_001",
        "category": "settlement_operations",
        "title": "T+1 Settlement - Digital",
        "rbi_para": "Para 10.1",
        "description": "Digital payment transactions must be settled to merchants within T+1 business days.",
        "applicability": "both",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "Settlement policy stating T+1",
            "Settlement SLA in merchant agreements",
            "Settlement monitoring reports",
            "Exception handling process"
        ],
        "gap_check_prompt": "Check if settlement policy mandates T+1 settlement for digital transactions."
    },
    {
        "id": "PA_PG_SET_002",
        "category": "settlement_operations",
        "title": "T+0 Settlement - Physical POS",
        "rbi_para": "Para 10.2",
        "description": "Physical POS (PA-P) transactions must be settled within T+0 (same business day).",
        "applicability": "pa_p",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "T+0 settlement policy for PA-P",
            "Same-day settlement infrastructure",
            "PA-P settlement monitoring"
        ],
        "gap_check_prompt": "For PA-P operations: check if T+0 (same-day) settlement is mandated for physical POS transactions."
    },
    {
        "id": "PA_PG_SET_003",
        "category": "settlement_operations",
        "title": "Escrow Account Maintenance",
        "rbi_para": "Para 9.1",
        "description": "PA must maintain escrow account with a scheduled commercial bank for holding merchant funds.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "Escrow account agreement",
            "Scheduled bank confirmation",
            "Escrow account operational procedures",
            "Daily reconciliation process"
        ],
        "gap_check_prompt": "Check for escrow account with scheduled bank for merchant funds."
    },
    {
        "id": "PA_PG_SET_004",
        "category": "settlement_operations",
        "title": "Nodal Account Restrictions",
        "rbi_para": "Para 9.2",
        "description": "Nodal/escrow accounts must only be used for payment aggregation; no other business funds co-mingled.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "Nodal account usage policy",
            "Fund segregation procedures",
            "Audit trail for nodal account"
        ],
        "gap_check_prompt": "Check for nodal account fund segregation policy preventing co-mingling of business funds."
    },
    {
        "id": "PA_PG_SET_005",
        "category": "settlement_operations",
        "title": "Daily Reconciliation",
        "rbi_para": "Para 9.3",
        "description": "Daily reconciliation of escrow/nodal accounts with transaction records.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Daily reconciliation process",
            "Reconciliation templates",
            "Exception handling procedures",
            "Escalation for mismatches"
        ],
        "gap_check_prompt": "Check for daily reconciliation process between escrow accounts and transaction records."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 5: PA-P PHYSICAL POS (5 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_PAP_001",
        "category": "pa_p_physical",
        "title": "PA-P Registration",
        "rbi_para": "Para 8.1",
        "description": "Entities conducting PA-P (physical POS aggregation) must register with RBI.",
        "applicability": "pa_p",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "PA-P registration with RBI",
            "Registration acknowledgment",
            "PA-P operations documentation"
        ],
        "gap_check_prompt": "Check if PA-P registration with RBI has been completed."
    },
    {
        "id": "PA_PG_PAP_002",
        "category": "pa_p_physical",
        "title": "POS Device Security",
        "rbi_para": "Para 8.3",
        "description": "Physical POS devices must comply with PCI-DSS and EMV standards.",
        "applicability": "pa_p",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "PCI-DSS compliance certificate",
            "EMV compliance documentation",
            "Device security audit reports",
            "Tamper detection mechanisms"
        ],
        "gap_check_prompt": "Check for POS device security compliance with PCI-DSS and EMV standards."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 6: ESCROW & FUND FLOW (4 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_ESC_001",
        "category": "escrow_accounts",
        "title": "Interest on Escrow Balances",
        "rbi_para": "Para 9.4",
        "description": "Interest earned on escrow balances must be handled as per RBI directions.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "medium",
        "compliance_indicators": [
            "Interest handling policy",
            "Interest accounting procedures",
            "Bank agreement on interest terms"
        ],
        "gap_check_prompt": "Check for policy on handling interest earned on escrow account balances."
    },
    {
        "id": "PA_PG_ESC_002",
        "category": "escrow_accounts",
        "title": "Bank Guarantee / FDR",
        "rbi_para": "Para 9.5",
        "description": "PA must maintain bank guarantee or FDR as security for escrow operations.",
        "applicability": "non_bank",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Bank guarantee document",
            "FDR evidence",
            "Security maintenance policy",
            "Annual renewal process"
        ],
        "gap_check_prompt": "Check for bank guarantee or FDR maintained as security for PA escrow operations."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 7: FRAUD & TRANSACTION MONITORING (5 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_FRD_001",
        "category": "fraud_monitoring",
        "title": "Transaction Monitoring System",
        "rbi_para": "Para 12.1",
        "description": "PA must implement real-time transaction monitoring with velocity checks and amount thresholds.",
        "applicability": "both",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "Transaction monitoring system documentation",
            "Velocity check configuration",
            "Amount threshold policies",
            "Real-time alert mechanisms"
        ],
        "gap_check_prompt": "Check for real-time transaction monitoring system with velocity checks and amount thresholds."
    },
    {
        "id": "PA_PG_FRD_002",
        "category": "fraud_monitoring",
        "title": "Suspicious Transaction Reporting",
        "rbi_para": "Para 12.2",
        "description": "PA must file STRs with FIU-IND for suspicious transactions.",
        "applicability": "both",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "STR filing process",
            "FIU-IND registration",
            "Suspicious transaction identification criteria",
            "STR filing timeline compliance"
        ],
        "gap_check_prompt": "Check for STR filing process with FIU-IND for suspicious transactions."
    },
    {
        "id": "PA_PG_FRD_003",
        "category": "fraud_monitoring",
        "title": "Merchant Risk Scoring",
        "rbi_para": "Para 12.3",
        "description": "Implement risk scoring methodology for merchants based on transaction patterns and behavior.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Merchant risk scoring model",
            "Risk score calculation methodology",
            "Periodic risk review process",
            "Action triggers for high-risk scores"
        ],
        "gap_check_prompt": "Check for merchant risk scoring methodology based on transaction patterns."
    },
    {
        "id": "PA_PG_FRD_004",
        "category": "fraud_monitoring",
        "title": "Chargeback Management",
        "rbi_para": "Para 12.4",
        "description": "Establish chargeback handling procedures and merchant blacklisting for excessive chargebacks.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Chargeback policy",
            "Merchant blacklisting criteria",
            "Chargeback dispute resolution process",
            "Chargeback monitoring reports"
        ],
        "gap_check_prompt": "Check for chargeback handling and merchant blacklisting procedures."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 8: GOVERNANCE & COMPLIANCE (5 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_GOV_001",
        "category": "governance_compliance",
        "title": "Board-Approved Compliance Framework",
        "rbi_para": "Para 14.1",
        "description": "Board must approve PA compliance framework including policies, procedures, and reporting.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Board resolution approving compliance framework",
            "Compliance framework document",
            "Annual board review of compliance"
        ],
        "gap_check_prompt": "Check for board-approved compliance framework for PA operations."
    },
    {
        "id": "PA_PG_GOV_002",
        "category": "governance_compliance",
        "title": "Compliance Officer Appointment",
        "rbi_para": "Para 14.2",
        "description": "Designated compliance officer for PA regulatory compliance.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Compliance officer appointment letter",
            "CO responsibilities document",
            "Reporting structure documentation"
        ],
        "gap_check_prompt": "Check for designated compliance officer for PA operations."
    },
    {
        "id": "PA_PG_GOV_003",
        "category": "governance_compliance",
        "title": "Audit Trail Requirements",
        "rbi_para": "Para 14.3",
        "description": "Maintain complete audit trail of all PA transactions and compliance activities.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Audit trail policy",
            "Transaction logging system",
            "Audit trail retention period",
            "Audit trail accessibility for regulators"
        ],
        "gap_check_prompt": "Check for comprehensive audit trail of PA transactions and compliance activities."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 9: TECHNOLOGY & SECURITY (4 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_TEC_001",
        "category": "technology_security",
        "title": "Data Security Standards",
        "rbi_para": "Para 13.1",
        "description": "PA must comply with PCI-DSS and implement encryption for all payment data.",
        "applicability": "both",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "PCI-DSS compliance certificate",
            "Encryption standards documentation",
            "Annual security audit report",
            "Vulnerability assessment reports"
        ],
        "gap_check_prompt": "Check for PCI-DSS compliance and encryption standards for payment data."
    },
    {
        "id": "PA_PG_TEC_002",
        "category": "technology_security",
        "title": "Data Localisation",
        "rbi_para": "Para 13.2",
        "description": "All payment data must be stored only in India as per RBI data localisation requirements.",
        "applicability": "both",
        "deadline": None,
        "criticality": "critical",
        "compliance_indicators": [
            "Data localisation policy",
            "India-based server documentation",
            "Data residency audit reports",
            "Third-party hosting compliance"
        ],
        "gap_check_prompt": "Check for data localisation compliance ensuring all payment data stored in India."
    },

    # ═══════════════════════════════════════════════════
    # CATEGORY 10: CUSTOMER PROTECTION (4 requirements)
    # ═══════════════════════════════════════════════════
    {
        "id": "PA_PG_CUS_001",
        "category": "customer_protection",
        "title": "Grievance Redressal Mechanism",
        "rbi_para": "Para 16.1",
        "description": "PA must establish grievance redressal mechanism for customers and merchants.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Grievance redressal policy",
            "Complaint handling SLA",
            "Escalation matrix",
            "Customer helpline/portal"
        ],
        "gap_check_prompt": "Check for customer and merchant grievance redressal mechanism with defined SLAs."
    },
    {
        "id": "PA_PG_CUS_002",
        "category": "customer_protection",
        "title": "Refund Processing",
        "rbi_para": "Para 16.2",
        "description": "Failed transactions must be refunded within stipulated timeframe.",
        "applicability": "both",
        "deadline": None,
        "criticality": "high",
        "compliance_indicators": [
            "Refund policy",
            "Auto-refund mechanism",
            "Refund timeline SLAs",
            "Failed transaction monitoring"
        ],
        "gap_check_prompt": "Check for refund processing policy for failed transactions with defined timelines."
    },
]

# Category metadata for dashboard & reporting
PA_PG_CATEGORIES = {
    "authorisation": {
        "name": "Authorisation & Registration",
        "icon": "shield-check",
        "description": "CoA, PRAVAAH portal, PA-P notification",
        "weight": 1.5  # Higher weight for critical categories
    },
    "capital_requirements": {
        "name": "Capital Requirements",
        "icon": "banknote",
        "description": "Net worth INR 15-25 crore, capital maintenance",
        "weight": 1.3
    },
    "merchant_onboarding": {
        "name": "Merchant Due Diligence",
        "icon": "user-check",
        "description": "KYC, physical verification, enhanced DD",
        "weight": 1.4
    },
    "settlement_operations": {
        "name": "Settlement & Operations",
        "icon": "clock",
        "description": "T+1 digital, T+0 physical, escrow",
        "weight": 1.5
    },
    "pa_p_physical": {
        "name": "PA-P Physical POS",
        "icon": "credit-card",
        "description": "Physical POS regulation, device security",
        "weight": 1.2
    },
    "escrow_accounts": {
        "name": "Escrow & Fund Flow",
        "icon": "vault",
        "description": "Escrow account, fund segregation, reconciliation",
        "weight": 1.3
    },
    "fraud_monitoring": {
        "name": "Fraud & Transaction Monitoring",
        "icon": "alert-triangle",
        "description": "Real-time monitoring, STR, merchant risk",
        "weight": 1.4
    },
    "governance_compliance": {
        "name": "Governance & Compliance",
        "icon": "building",
        "description": "Board approval, compliance officer, audit trail",
        "weight": 1.1
    },
    "technology_security": {
        "name": "Technology & Security",
        "icon": "lock",
        "description": "PCI-DSS, data localisation, encryption",
        "weight": 1.3
    },
    "customer_protection": {
        "name": "Customer Protection",
        "icon": "heart-handshake",
        "description": "Grievance redressal, refunds, dispute resolution",
        "weight": 1.1
    }
}

# Key regulatory deadlines
PA_PG_DEADLINES = {
    "pravaah_application": {
        "date": "2025-12-31",
        "description": "PRAVAAH portal application deadline for new PAs",
        "criticality": "critical"
    },
    "non_compliant_cessation": {
        "date": "2026-02-28",
        "description": "Non-compliant entities must cease PA operations",
        "criticality": "critical"
    },
    "pre_2026_merchant_kyc": {
        "date": "2026-09-15",
        "description": "Enhanced DD for pre-2026 onboarded merchants",
        "criticality": "high"
    }
}
```

---

### 3.3 Extend `backend/config/compliance_context.py`

**Add PA/PG-specific subject categories to `SUBJECT_CATEGORIES` dict:**

```python
# Add to SUBJECT_CATEGORIES dict:

"payment_aggregation": SubjectCategory(
    id="payment_aggregation",
    name="Payment Aggregation (PA/PG)",
    description="Payment Aggregator and Payment Gateway regulatory requirements",
    keywords=["payment aggregator", "payment gateway", "pa/pg", "pa-p",
              "merchant acquiring", "escrow account", "nodal account",
              "settlement", "pravaah", "certificate of authorisation"],
    related_regulations=["RBI Master Direction on PA 2025", "PA/PG Guidelines"],
    typical_obligations=[
        "Obtain Certificate of Authorisation from RBI",
        "Maintain escrow account with scheduled bank",
        "Settle merchant payments within T+1",
        "Conduct merchant due diligence"
    ]
),

"merchant_due_diligence": SubjectCategory(
    id="merchant_due_diligence",
    name="Merchant Due Diligence (PA/PG)",
    description="Merchant onboarding, KYC, and ongoing monitoring for PA/PG",
    keywords=["merchant onboarding", "merchant kyc", "merchant verification",
              "physical verification", "merchant monitoring", "merchant risk",
              "merchant blacklisting", "enhanced due diligence"],
    related_regulations=["RBI PA Master Direction Para 15"],
    typical_obligations=[
        "Perform merchant KYC at onboarding",
        "Physical verification for high-risk merchants",
        "Enhanced DD for pre-2026 merchants by Sep 2026",
        "Ongoing merchant risk monitoring"
    ]
),

"settlement_escrow": SubjectCategory(
    id="settlement_escrow",
    name="Settlement & Escrow (PA/PG)",
    description="Settlement timelines, escrow account management, fund flow",
    keywords=["t+1 settlement", "t+0 settlement", "escrow", "nodal account",
              "fund flow", "reconciliation", "bank guarantee", "fdr"],
    related_regulations=["RBI PA Master Direction Para 9-10"],
    typical_obligations=[
        "T+1 settlement for digital, T+0 for PA-P",
        "Maintain escrow with scheduled bank",
        "Daily reconciliation",
        "Fund segregation from business accounts"
    ]
),
```

---

### 3.4 Extend `backend/models.py`

**Add to models.py:**

```python
class PARequirementStatus(str, Enum):
    NOT_ASSESSED = "Not Assessed"
    COMPLIANT = "Compliant"
    PARTIAL = "Partial"
    NON_COMPLIANT = "Non-Compliant"
    NOT_APPLICABLE = "Not Applicable"

class ClientProfile(str, Enum):
    BANK_PA = "bank_pa"
    NON_BANK_PA = "non_bank_pa"
    PA_P_OPERATOR = "pa_p_operator"
    MARKETPLACE_PA = "marketplace_pa"
    DIGITAL_LENDER_PA = "digital_lender_pa"
```

---

## 4. FILES TO MODIFY

### 4.1 `backend/server.py` — Integration Points

**Modify: `process_regulation_upload_background()` (line ~3168)**

After step 4 (clause extraction), add:

```python
# Step 4b: PA/PG-specific enrichment (NEW)
pa_pg_service = PAPGRegulationService()
if await pa_pg_service.detect_pa_pg_regulation(extracted_text, regulation_metadata):
    # Enrich clauses with PA/PG taxonomy
    enriched_clauses = await pa_pg_service.enrich_clauses_for_pa_pg(clauses)

    # Extract ~50 specific requirements
    requirements = await pa_pg_service.extract_pa_pg_requirements(
        extracted_text, enriched_clauses
    )

    # Build requirement index
    requirement_index = await pa_pg_service.build_requirement_index(
        regulation_id, requirements
    )

    # Store requirement index in regulation document
    await db.regulations.update_one(
        {"id": regulation_id},
        {"$set": {
            "pa_pg_requirements": requirement_index,
            "is_pa_pg_regulation": True,
            "pa_pg_deadlines": PA_PG_DEADLINES
        }}
    )
```

### 4.2 `backend/services/regulation_first_gap_analysis.py` — Add PA/PG category mappings

**Add to `CATEGORY_TO_DEPARTMENT` dict:**

```python
"payment_aggregation": {"department_id": "dept-compliance", "department": "Compliance", "role": "head"},
"merchant_due_diligence": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
"settlement_escrow": {"department_id": "dept-finance", "department": "Finance", "role": "manager"},
```

### 4.3 `backend/services/semantic_gap_analysis_service.py` — Same mapping additions

---

## 5. MONGODB SCHEMA CHANGES

### New fields on `regulations` collection:

```javascript
{
  // ... existing fields ...

  // NEW PA/PG fields
  "is_pa_pg_regulation": true,
  "pa_pg_requirements": {
    "total_requirements": 50,
    "categories": {
      "authorisation": { "count": 8, "requirement_ids": ["PA_PG_AUTH_001", ...] },
      "capital_requirements": { "count": 5, "requirement_ids": [...] },
      // ... etc
    },
    "requirements": [
      {
        "id": "PA_PG_AUTH_001",
        "category": "authorisation",
        "title": "Certificate of Authorisation",
        "rbi_para": "Para 4",
        "description": "...",
        "applicability": "non_bank",
        "deadline": null,
        "criticality": "critical",
        "compliance_indicators": [...],
        "matched_clause_ids": ["clause-uuid-1", "clause-uuid-2"],
        "coverage_score": 0.0
      }
    ],
    "deadlines": {
      "pravaah_application": "2025-12-31",
      "non_compliant_cessation": "2026-02-28",
      "pre_2026_merchant_kyc": "2026-09-15"
    }
  }
}
```

---

## 6. QDRANT INTEGRATION

**No new collections needed.** PA/PG regulation clauses stored in existing `regulation_clauses` collection with additional payload fields:

```python
# Additional Qdrant payload fields for PA/PG clauses
{
    "is_pa_pg": True,
    "pa_pg_category": "authorisation",
    "pa_pg_requirement_ids": ["PA_PG_AUTH_001"],
    "applicability": "non_bank",
    "regulatory_deadline": "2026-02-28"
}
```

---

## 7. INTEGRATION WITH EXISTING GAP ANALYSIS

The `pa_pg_requirements` stored on the regulation document enable:
1. **Requirement-by-requirement gap checking** — each of the ~50 requirements checked against client policy
2. **Category-level compliance scoring** — weighted by category importance
3. **Deadline-aware prioritization** — gaps near deadlines flagged as Critical
4. **Applicability filtering** — only check requirements relevant to client profile (bank vs non-bank)

**No changes needed to the gap analysis services themselves** — they already work on clause-level. The PA/PG enrichment simply adds better metadata to clauses for more accurate matching.

---

## 8. TESTING CHECKLIST

- [ ] Upload a sample RBI PA/PG Master Direction PDF
- [ ] Verify `detect_pa_pg_regulation()` returns True
- [ ] Verify ~50 requirements extracted with correct categories
- [ ] Verify each clause has `pa_pg_category` in metadata
- [ ] Verify `is_pa_pg_regulation: true` flag set on regulation document
- [ ] Verify Qdrant payloads include PA/PG fields
- [ ] Run gap analysis against a sample PA policy — verify PA/PG-specific gaps
- [ ] Verify deadline-based prioritization in gap results
- [ ] Verify applicability filtering (bank vs non-bank)
