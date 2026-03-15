"""
CompliAI - Compliance Context Configuration

This module provides a centralized, configurable context for all LLM operations
related to clause extraction, semantic analysis, and gap analysis.

Designed by compliance professionals for compliance professionals.

Architecture:
┌────────────────────────────────────────────────────────────────────────┐
│                     COMPLIANCE CONTEXT CONFIG                           │
├────────────────────────────────────────────────────────────────────────┤
│  Domain Knowledge  │  Regulatory Taxonomy  │  Prompt Templates          │
│  ─────────────────  │  ──────────────────── │  ─────────────────         │
│  • Regulator info   │  • Subject categories │  • Extraction prompts      │
│  • Entity types     │  • Requirement types  │  • Enrichment prompts      │
│  • Document types   │  • Criticality levels │  • Gap analysis prompts    │
│  • Compliance areas │  • Obligation patterns│  • Custom use cases        │
└────────────────────────────────────────────────────────────────────────┘

Usage:
    from config.compliance_context import ComplianceContext
    
    ctx = ComplianceContext()
    system_prompt = ctx.get_system_prompt("clause_extraction")
    user_prompt = ctx.build_extraction_prompt(chunk, document_type="regulation")
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json


# =============================================================================
# ENUMS - Controlled Vocabularies for Classification
# =============================================================================

class DocumentType(str, Enum):
    """Types of documents processed by CompliAI"""
    REGULATION = "regulation"
    POLICY = "policy"
    CIRCULAR = "circular"
    MASTER_DIRECTION = "master_direction"
    GUIDELINE = "guideline"
    NOTIFICATION = "notification"
    SOP = "sop"  # Standard Operating Procedure
    INTERNAL_MEMO = "internal_memo"


class RequirementType(str, Enum):
    """Classification of clause requirements"""
    MANDATORY = "mandatory"          # MUST do - shall, must, required
    RECOMMENDED = "recommended"      # SHOULD do - should, may, expected
    PROHIBITION = "prohibition"      # MUST NOT do - prohibited, forbidden
    INFORMATIONAL = "informational"  # Definitions, context, explanations
    CONDITIONAL = "conditional"      # IF-THEN requirements
    PERMISSIVE = "permissive"       # MAY do - allowed, permitted
    EXCEPTION = "exception"          # Carve-outs, exemptions


class CriticalityLevel(str, Enum):
    """Risk/importance classification"""
    CRITICAL = "critical"  # Immediate regulatory action if violated
    HIGH = "high"          # Regulatory scrutiny, potential penalty
    MEDIUM = "medium"      # Compliance finding, observation
    LOW = "low"           # Best practice, advisory


class Regulator(str, Enum):
    """Indian Financial Regulators"""
    RBI = "RBI"           # Reserve Bank of India
    SEBI = "SEBI"         # Securities & Exchange Board of India
    IRDAI = "IRDAI"       # Insurance Regulatory & Development Authority
    PFRDA = "PFRDA"       # Pension Fund Regulatory & Development Authority
    FIU_IND = "FIU-IND"   # Financial Intelligence Unit
    NPCI = "NPCI"         # National Payments Corporation of India
    MCA = "MCA"           # Ministry of Corporate Affairs
    CERT_IN = "CERT-In"   # Indian Computer Emergency Response Team
    MEITY = "MeitY"       # Ministry of Electronics & IT
    OTHER = "OTHER"


# =============================================================================
# DOMAIN TAXONOMIES - Compliance Officer's Knowledge Base
# =============================================================================

@dataclass
class SubjectCategory:
    """A compliance subject area with metadata"""
    id: str
    name: str
    description: str
    keywords: List[str]
    related_regulations: List[str]
    typical_obligations: List[str]


SUBJECT_CATEGORIES: Dict[str, SubjectCategory] = {
    "kyc_cdd": SubjectCategory(
        id="kyc_cdd",
        name="KYC / Customer Due Diligence",
        description="Customer identification, verification, and ongoing due diligence requirements",
        keywords=["kyc", "know your customer", "cdd", "customer due diligence", "identity verification", 
                  "document verification", "v-cip", "ckyc", "re-kyc", "ckycr", "ovd", "digilocker"],
        related_regulations=["RBI KYC Master Direction 2016", "PML Act 2002", "CKYC Guidelines"],
        typical_obligations=[
            "Verify customer identity before account opening",
            "Perform V-CIP for digital onboarding",
            "Update KYC periodically based on risk category",
            "Upload KYC to CKYCR within stipulated timeframe"
        ]
    ),
    "aml_cft": SubjectCategory(
        id="aml_cft",
        name="AML / CFT",
        description="Anti-Money Laundering and Combating Financing of Terrorism requirements",
        keywords=["aml", "anti-money laundering", "cft", "counter terrorism", "suspicious transaction", 
                  "str", "ctr", "pml", "fatf", "fiu-ind", "risk categorization", "transaction monitoring"],
        related_regulations=["PML Act 2002", "RBI Master Direction on KYC", "FATF Guidelines"],
        typical_obligations=[
            "File STR within 7 days of suspicion",
            "File CTR for cash transactions above threshold",
            "Maintain transaction monitoring systems",
            "Conduct periodic AML risk assessments"
        ]
    ),
    "data_protection": SubjectCategory(
        id="data_protection",
        name="Data Protection & Privacy",
        description="Personal data handling, privacy, consent, and information security",
        keywords=["data protection", "privacy", "personal data", "sensitive data", "consent", 
                  "data breach", "dpdp", "gdpr", "pii", "spdi", "data localization"],
        related_regulations=["DPDP Act 2023", "IT Act 2000", "RBI Data Localization Circular"],
        typical_obligations=[
            "Obtain explicit consent before data collection",
            "Store payment system data only in India",
            "Report data breaches within stipulated time",
            "Maintain data processing records"
        ]
    ),
    "digital_lending": SubjectCategory(
        id="digital_lending",
        name="Digital Lending",
        description="Digital lending guidelines, fair practices code, and disclosure requirements",
        keywords=["digital lending", "fpc", "fair practices", "loan origination", "lsp", 
                  "dlg", "fldg", "disclosure", "cooling off", "key fact statement"],
        related_regulations=["RBI Digital Lending Guidelines 2022", "Fair Practices Code", "Outsourcing Guidelines"],
        typical_obligations=[
            "Disclose all fees upfront in Key Fact Statement",
            "Provide cooling-off period for loan cancellation",
            "Ensure LSP due diligence and agreements",
            "Credit to borrower bank account only"
        ]
    ),
    "outsourcing": SubjectCategory(
        id="outsourcing",
        name="Outsourcing & Third Party Management",
        description="Vendor management, outsourcing risk, and third-party due diligence",
        keywords=["outsourcing", "third party", "vendor", "service provider", "lsp", 
                  "due diligence", "concentration risk", "exit strategy", "sla"],
        related_regulations=["RBI Outsourcing Guidelines", "IRDAI Outsourcing Regulations"],
        typical_obligations=[
            "Conduct due diligence on service providers",
            "Maintain updated vendor agreements",
            "Monitor vendor performance through SLAs",
            "Have exit strategy and business continuity plans"
        ]
    ),
    "information_security": SubjectCategory(
        id="information_security",
        name="Information Security & Cyber Security",
        description="IT security, cyber security, incident management, and technology controls",
        keywords=["information security", "cyber security", "it security", "access control", 
                  "incident response", "vulnerability", "penetration testing", "soc", "vapt"],
        related_regulations=["RBI Cyber Security Framework", "CERT-In Guidelines", "IT Act 2000"],
        typical_obligations=[
            "Conduct periodic VAPT assessments",
            "Implement multi-factor authentication",
            "Report cyber incidents to CERT-In",
            "Maintain SOC operations 24x7"
        ]
    ),
    "fraud_management": SubjectCategory(
        id="fraud_management",
        name="Fraud Management",
        description="Fraud detection, prevention, investigation, and reporting requirements",
        keywords=["fraud", "fraud risk", "fraud prevention", "fraud detection", "investigation", 
                  "internal fraud", "external fraud", "fraudulent transaction"],
        related_regulations=["RBI Framework on Frauds", "RBI Master Direction on Fraud Reporting"],
        typical_obligations=[
            "Report frauds to RBI within stipulated timeframe",
            "Maintain fraud monitoring mechanisms",
            "Conduct staff fraud awareness training",
            "Investigate frauds and take action"
        ]
    ),
    "grievance_redressal": SubjectCategory(
        id="grievance_redressal",
        name="Customer Grievance Redressal",
        description="Complaint handling, dispute resolution, and customer protection",
        keywords=["grievance", "complaint", "dispute", "redressal", "ombudsman", 
                  "customer protection", "cms", "escalation", "resolution"],
        related_regulations=["RBI Integrated Ombudsman Scheme", "RBI Customer Service Guidelines"],
        typical_obligations=[
            "Resolve complaints within TAT",
            "Integrate with RBI CMS portal",
            "Inform customers of ombudsman option",
            "Maintain complaint tracking system"
        ]
    ),
    "governance": SubjectCategory(
        id="governance",
        name="Governance & Oversight",
        description="Board oversight, management responsibilities, and governance framework",
        keywords=["governance", "board", "directors", "committee", "oversight", 
                  "management", "fit and proper", "independent director", "audit committee"],
        related_regulations=["Companies Act 2013", "RBI Corporate Governance Guidelines"],
        typical_obligations=[
            "Board approval for key policies",
            "Quarterly compliance reporting to Board",
            "Maintain Board committee structure",
            "Ensure fit and proper criteria for key officials"
        ]
    ),
    "reporting": SubjectCategory(
        id="reporting",
        name="Regulatory Reporting & Filings",
        description="Statutory filings, returns, and regulatory submissions",
        keywords=["reporting", "returns", "filing", "statutory", "submission", 
                  "periodic", "annual return", "quarterly report", "disclosure"],
        related_regulations=["Various RBI Return Requirements", "Companies Act Filings"],
        typical_obligations=[
            "File periodic returns by due dates",
            "Submit annual compliance certificate",
            "Report material changes to regulator",
            "Maintain accurate reporting data"
        ]
    ),
    "record_keeping": SubjectCategory(
        id="record_keeping",
        name="Record Keeping & Retention",
        description="Document retention, archival, and record maintenance requirements",
        keywords=["record", "retention", "archival", "documentation", "maintenance", 
                  "preservation", "years", "period", "storage"],
        related_regulations=["PML Act Record Keeping", "IT Act Requirements"],
        typical_obligations=[
            "Retain transaction records for 5/10 years",
            "Maintain audit trail of all actions",
            "Preserve KYC records as specified",
            "Enable retrieval of records within stipulated time"
        ]
    ),
    "capital_adequacy": SubjectCategory(
        id="capital_adequacy",
        name="Capital Adequacy & Prudential Norms",
        description="Capital requirements, prudential norms, and financial soundness",
        keywords=["capital", "crar", "tier 1", "tier 2", "npa", "provisioning", 
                  "prudential", "exposure", "leverage", "adequacy"],
        related_regulations=["RBI Prudential Norms", "Basel Guidelines"],
        typical_obligations=[
            "Maintain minimum CRAR as prescribed",
            "Classify assets and make provisions",
            "Report capital adequacy quarterly",
            "Adhere to exposure norms"
        ]
    ),
    "payments": SubjectCategory(
        id="payments",
        name="Payments & Settlement Systems",
        description="Payment system requirements, UPI, cards, and settlement obligations",
        keywords=["payment", "upi", "imps", "neft", "rtgs", "settlement", "card", 
                  "prepaid", "ppi", "acquiring", "pos", "qr"],
        related_regulations=["Payment & Settlement Systems Act", "RBI PA/PG Guidelines", "NPCI Circulars"],
        typical_obligations=[
            "Adhere to payment system timelines",
            "Implement transaction limits as prescribed",
            "Report payment system data to NPCI/RBI",
            "Handle failed transactions as per guidelines"
        ]
    ),
    "licensing": SubjectCategory(
        id="licensing",
        name="Licensing & Authorization",
        description="Regulatory licenses, registrations, and authorization requirements",
        keywords=["license", "registration", "authorization", "approval", "certificate", 
                  "renewal", "application", "eligibility", "coc"],
        related_regulations=["RBI Registration Requirements", "SEBI Registration Regulations"],
        typical_obligations=[
            "Maintain valid regulatory license",
            "Apply for renewal before expiry",
            "Report change in control/ownership",
            "Display license/registration details"
        ]
    ),
    "fair_practices": SubjectCategory(
        id="fair_practices",
        name="Fair Practices & Customer Treatment",
        description="Fair lending, transparent pricing, and ethical customer treatment",
        keywords=["fair practices", "fair lending", "transparency", "ethical", 
                  "customer treatment", "pricing", "terms and conditions", "sanction letter"],
        related_regulations=["RBI Fair Practices Code", "RBI Digital Lending Guidelines"],
        typical_obligations=[
            "Provide loan terms in vernacular language",
            "Disclose all charges and fees upfront",
            "Follow fair collection practices",
            "Give adequate notice for rate changes"
        ]
    ),
    "business_continuity": SubjectCategory(
        id="business_continuity",
        name="Business Continuity & Disaster Recovery",
        description="BCP, disaster recovery, and operational resilience requirements",
        keywords=["bcp", "business continuity", "disaster recovery", "dr", "resilience", 
                  "backup", "recovery", "rpo", "rto", "crisis management"],
        related_regulations=["RBI BCP Guidelines", "SEBI BCP Circular"],
        typical_obligations=[
            "Maintain and test BCP annually",
            "Establish DR site with specified RPO/RTO",
            "Conduct periodic DR drills",
            "Document crisis management procedures"
        ]
    ),
    "internal_audit": SubjectCategory(
        id="internal_audit",
        name="Internal Audit & Review",
        description="Internal audit function, compliance review, and assurance activities",
        keywords=["internal audit", "audit", "review", "inspection", "assurance", 
                  "audit committee", "findings", "observations", "cae"],
        related_regulations=["RBI Internal Audit Guidelines", "Companies Act Requirements"],
        typical_obligations=[
            "Conduct risk-based internal audits",
            "Report audit findings to Audit Committee",
            "Track and close audit observations",
            "Ensure auditor independence"
        ]
    ),
    "general": SubjectCategory(
        id="general",
        name="General Compliance",
        description="General compliance requirements not fitting other categories",
        keywords=["compliance", "regulatory", "requirement", "guideline", "norm"],
        related_regulations=["Various"],
        typical_obligations=["Adhere to applicable regulatory requirements"]
    ),
}


# =============================================================================
# REGULATORY OBLIGATION PATTERNS - For Intelligent Detection
# =============================================================================

OBLIGATION_PATTERNS = {
    "mandatory_action": {
        "patterns": [
            r"\bshall\b", r"\bmust\b", r"\brequired to\b", r"\bis required\b",
            r"\bmandatory\b", r"\bobligatory\b", r"\bensure that\b", r"\bhas to\b"
        ],
        "requirement_type": RequirementType.MANDATORY,
        "criticality": CriticalityLevel.HIGH
    },
    "prohibition": {
        "patterns": [
            r"\bshall not\b", r"\bmust not\b", r"\bprohibited\b", r"\bforbidden\b",
            r"\bnot allowed\b", r"\bnot permitted\b", r"\bshall be barred\b"
        ],
        "requirement_type": RequirementType.PROHIBITION,
        "criticality": CriticalityLevel.CRITICAL
    },
    "recommended_action": {
        "patterns": [
            r"\bshould\b", r"\bmay\b", r"\brecommended\b", r"\bexpected to\b",
            r"\bencouraged\b", r"\badvisable\b", r"\bbest practice\b"
        ],
        "requirement_type": RequirementType.RECOMMENDED,
        "criticality": CriticalityLevel.MEDIUM
    },
    "conditional_action": {
        "patterns": [
            r"\bif\s+.+\s+then\b", r"\bwhere\s+applicable\b", r"\bin case of\b",
            r"\bprovided that\b", r"\bsubject to\b", r"\bwhen\s+.+\s+shall\b"
        ],
        "requirement_type": RequirementType.CONDITIONAL,
        "criticality": CriticalityLevel.MEDIUM
    },
    "timeline_requirement": {
        "patterns": [
            r"\bwithin\s+\d+\s+days?\b", r"\bwithin\s+\d+\s+hours?\b",
            r"\bby\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", r"\bnot later than\b",
            r"\bimmediately\b", r"\bforthwith\b", r"\bwithout delay\b"
        ],
        "requirement_type": RequirementType.MANDATORY,
        "criticality": CriticalityLevel.HIGH
    },
    "penalty_reference": {
        "patterns": [
            r"\bpenalty\b", r"\bfine\b", r"\bpunishable\b", r"\bimprisonment\b",
            r"\bsanction\b", r"\baction will be taken\b", r"\bconsequences\b"
        ],
        "requirement_type": RequirementType.MANDATORY,
        "criticality": CriticalityLevel.CRITICAL
    }
}


# =============================================================================
# ENTITY TAXONOMY - Who is involved?
# =============================================================================

ENTITY_TYPES = {
    "regulated_entities": [
        "Regulated Entity", "RE", "Bank", "NBFC", "HFC", "Payment Aggregator",
        "Payment Gateway", "PPI Issuer", "Account Aggregator", "NBFC-P2P",
        "Digital Lender", "Fintech", "Credit Information Company"
    ],
    "internal_roles": [
        "Board of Directors", "Board", "Audit Committee", "Risk Committee",
        "Managing Director", "CEO", "CFO", "CTO", "Chief Compliance Officer",
        "Principal Nodal Officer", "Nodal Officer", "Compliance Officer",
        "Money Laundering Reporting Officer", "MLRO", "Chief Information Security Officer",
        "CISO", "Data Protection Officer", "DPO", "Internal Auditor"
    ],
    "external_parties": [
        "RBI", "SEBI", "IRDAI", "FIU-IND", "CERT-In", "NPCI", "UIDAI",
        "Customer", "Borrower", "Account Holder", "Data Principal",
        "Third Party", "Service Provider", "LSP", "Outsourcing Partner",
        "Auditor", "Statutory Auditor"
    ]
}


# =============================================================================
# PROMPT TEMPLATES - Compliance Officer Designed
# =============================================================================

@dataclass
class PromptTemplate:
    """A reusable prompt template with variables"""
    id: str
    name: str
    description: str
    use_cases: List[str]
    system_prompt: str
    user_prompt_template: str
    output_schema: Dict[str, Any]
    variables: List[str]


class CompliancePrompts:
    """
    Centralized prompt management for compliance operations.
    
    These prompts are designed by compliance officers to ensure:
    1. Regulatory accuracy in interpretation
    2. Proper classification of obligations
    3. Clear, actionable outputs
    4. Audit-ready documentation
    """
    
    # =========================================================================
    # SYSTEM PROMPTS (Role Definition)
    # =========================================================================
    
    SYSTEM_PROMPTS = {
        "base": """You are an expert compliance analyst for CompliAI, an AI-powered Regulatory Technology (RegTech) platform. Your primary users are:
- Chief Compliance Officers (CCOs)
- Compliance teams at financial institutions
- Internal auditors
- Risk management professionals

You operate with deep knowledge of:
1. Indian financial regulations (RBI, SEBI, IRDAI, FIU-IND, NPCI)
2. Compliance frameworks (PML Act, IT Act, DPDP Act)
3. Industry standards (ISO 27001, COBIT, COSO)

Your outputs directly impact:
- Regulatory examination outcomes
- Penalty avoidance (₹ Crores at stake)
- License continuation
- Organizational reputation

Always prioritize accuracy, completeness, and regulatory alignment in your analysis.""",

        "clause_extraction": """You are an expert legal document analyst specializing in Indian financial services regulations. Your task is to identify and extract individual compliance clauses from regulatory documents and internal policies.

WHAT IS A CLAUSE?
A clause is a distinct, self-contained statement that establishes:
1. A REQUIREMENT - Something that must be done (shall, must)
2. A PROHIBITION - Something that must not be done (shall not, prohibited)
3. A CONDITION - If-then requirements (if X, then Y)
4. A TIMELINE - When something must be done (within X days)
5. A RESPONSIBILITY - Who must do it (the bank shall, CCO must)
6. A DEFINITION - What terms mean (for the purpose of this...)

CLAUSE BOUNDARY RULES:
- Each clause should be complete and understandable on its own
- Do NOT split a single requirement into multiple clauses
- Do NOT merge unrelated requirements into one clause
- Preserve the exact regulatory language (shall, must, etc.)
- Maintain section/paragraph references

CRITICAL: In regulations, every "shall" statement typically indicates a separate clause.""",

        "semantic_enrichment": """You are a senior compliance analyst performing semantic analysis of regulatory and policy clauses. Your analysis powers an automated compliance gap detection system.

YOUR EXPERTISE:
- 15+ years in financial services compliance
- Deep knowledge of RBI regulations and circulars
- Experience with compliance audits and examinations
- Understanding of practical implementation challenges

YOUR TASK:
Extract structured semantic attributes that enable:
1. Accurate matching between policy and regulation clauses
2. Identification of compliance gaps
3. Risk prioritization for remediation
4. Clear communication to business stakeholders

COMPLIANCE OFFICER'S PERSPECTIVE:
- Think about how this clause would be audited
- Consider what evidence would demonstrate compliance
- Identify who in the organization is responsible
- Assess the regulatory risk if not complied with""",

        "gap_analysis": """You are a regulatory examination specialist comparing organizational policies against regulatory requirements. Your role is to identify gaps, weaknesses, and non-compliance.

GAP TYPES:
1. MISSING - Regulation requires X, policy is silent
2. PARTIAL - Policy addresses requirement but incompletely
3. WEAK - Policy exists but uses weaker language (should vs shall)
4. CONFLICTING - Policy contradicts regulation
5. COMPLIANT - Policy fully addresses requirement

ANALYSIS FRAMEWORK:
- Compare requirement types (mandatory vs mandatory)
- Match key obligations point by point
- Identify missing controls or procedures
- Note differences in timelines or thresholds
- Consider practical implementation gaps""",

        "evidence_evaluation": """You are a compliance auditor evaluating evidence against control requirements. Your role is to assess whether the evidence demonstrates compliance.

EVIDENCE ASSESSMENT CRITERIA:
1. RELEVANCE - Does the evidence relate to the requirement?
2. COMPLETENESS - Does it cover all aspects of the requirement?
3. CURRENCY - Is the evidence current and within validity?
4. RELIABILITY - Is the source trustworthy?
5. SUFFICIENCY - Is there enough evidence?

OUTPUT: Provide objective assessment with specific observations.""",

        "regulation_summary": """You are a regulatory intelligence analyst summarizing new circulars and regulatory updates for compliance teams.

SUMMARY REQUIREMENTS:
1. Key changes from previous requirements
2. Affected entities and business lines
3. Implementation timeline and milestones
4. Potential business impact
5. Related circulars and cross-references

Write for a busy compliance officer who needs to quickly understand impact."""
    }
    
    # =========================================================================
    # EXTRACTION PROMPTS
    # =========================================================================
    
    CLAUSE_EXTRACTION_PROMPT = """Extract individual compliance clauses from this {document_type} document section.

DOCUMENT INFORMATION:
- Title: {document_title}
- Regulator/Issuer: {issuer}
- Section: {section_name}
- Page: {page_number}

DOCUMENT TEXT:
{chunk_text}

EXTRACTION INSTRUCTIONS:

1. IDENTIFY each distinct clause that establishes a:
   - Requirement (shall, must, required to)
   - Prohibition (shall not, must not, prohibited)
   - Condition (if, when, where, subject to)
   - Timeline (within X days, by date)
   - Definition (means, refers to, for the purpose of)

2. PRESERVE exactly:
   - Regulatory language (shall, must, may, should)
   - Section/paragraph references (Section 5.2, Para 3)
   - Timelines and dates
   - Thresholds and limits (Rs. 50,000, 10 days)
   - Entity references (RE, Bank, NBFC)

3. DO NOT:
   - Split a single requirement across multiple clauses
   - Merge unrelated requirements
   - Paraphrase or summarize (use verbatim text)
   - Include headers-only without content

OUTPUT FORMAT:
Return a JSON array where each element has:
{{
    "clause_number": <sequential number>,
    "text": "<full verbatim clause text>",
    "type_hint": "<requirement|prohibition|condition|definition|informational>"
}}

Return ONLY the JSON array, no explanation or markdown."""

    POLICY_EXTRACTION_PROMPT = """Extract individual policy statements from this internal policy document.

DOCUMENT INFORMATION:
- Policy Name: {document_title}
- Policy Type: {policy_type}
- Section: {section_name}
- Version: {version}

POLICY TEXT:
{chunk_text}

EXTRACTION FOCUS:

1. CONTROL STATEMENTS - How requirements are implemented
   - "The Bank will verify customer identity using..."
   - "All transactions above Rs. 50,000 shall be..."

2. PROCEDURE STEPS - Specific process requirements
   - "Upon receipt of application, operations team shall..."
   - "The maker-checker process must be followed for..."

3. RESPONSIBILITY ASSIGNMENTS - Who does what
   - "The Compliance Officer is responsible for..."
   - "Branch Manager shall ensure..."

4. STANDARDS & THRESHOLDS - Measurable criteria
   - "Review must be completed within 30 days"
   - "Documentation retention period is 10 years"

5. EXCEPTION HANDLING - When rules don't apply
   - "In exceptional cases, with approval of..."
   - "This does not apply to transactions below..."

OUTPUT FORMAT:
Return a JSON array where each element has:
{{
    "clause_number": <sequential number>,
    "text": "<full policy statement>",
    "type_hint": "<control|procedure|responsibility|standard|exception>"
}}

Return ONLY the JSON array."""

    # =========================================================================
    # SEMANTIC ENRICHMENT PROMPT
    # =========================================================================
    
    SEMANTIC_ENRICHMENT_PROMPT = """Analyze these clauses from a {document_type} document and extract semantic attributes for compliance gap analysis.

DOCUMENT: {document_title}
ISSUER: {issuer}
CONTEXT: {document_context}

CLAUSES TO ANALYZE:
{clauses_text}

═══════════════════════════════════════════════════════════════════════════════
FOR EACH CLAUSE, EXTRACT THESE ATTRIBUTES:
═══════════════════════════════════════════════════════════════════════════════

1. TITLE (string)
   - Extract from CAPITAL LETTERS/numbered headers in the clause
   - Or provide a concise descriptive title (2-6 words)
   - Example: "Customer Verification Requirement" or "STR Filing Timeline"

2. CONTENT (string)
   - Clean, formatted version of the clause text
   - Remove redundant whitespace, fix formatting
   - Preserve all substantive content

3. TAGS (array of 3-7 strings)
   - Lowercase, hyphenated descriptive tags
   - Include: domain tags, action tags, entity tags
   - Examples: "kyc-verification", "mandatory-disclosure", "board-approval"

4. REQUIREMENT_TYPE (string) - ONE of:
   - "mandatory" → Uses shall/must/required - MUST comply
   - "prohibition" → Uses shall not/must not/prohibited - MUST NOT do
   - "recommended" → Uses should/may/expected - SHOULD comply
   - "conditional" → Uses if/when/where - Applies under conditions
   - "permissive" → Uses may/is permitted - CAN do (optional)
   - "informational" → Definitions/explanations - No action required

5. SUBJECT_CATEGORY (string) - Primary compliance area:
   {subject_categories}

6. KEY_OBLIGATIONS (array of 1-3 strings)
   - SPECIFIC, ACTIONABLE requirements
   - What exactly must be done?
   - Include thresholds, timelines, methods
   
   GOOD: "File STR with FIU-IND within 7 days of detection"
   BAD: "Report suspicious activity" (too vague)

7. SEMANTIC_SUMMARY (string, 2-3 sentences)
   - Plain language interpretation for non-experts
   - Explain: What does this require? Why does it matter?
   - Highlight practical implications
   
   Example: "This clause requires banks to file a Suspicious Transaction 
   Report within 7 days of detecting suspicious activity. Failure to comply 
   can result in penalties under PML Act and regulatory action."

8. ENTITIES_INVOLVED (array of strings)
   - Who is responsible for compliance?
   - Who is affected by this clause?
   - Examples: "Board of Directors", "CCO", "Operations Team", "Customers"

9. KEYWORDS (array of 3-5 strings)
   - Key terms for search and matching
   - Include regulatory terms, domain terms, action verbs
   - Lowercase

10. COMPLIANCE_INDICATORS (array of strings)
    - What EVIDENCE demonstrates compliance?
    - What would an auditor look for?
    - Examples: "Board-approved policy exists", "STR filing records", 
      "Training completion certificates"

11. CRITICALITY (string) - ONE of:
    - "critical" → Immediate regulatory action if violated, license risk
    - "high" → Significant regulatory scrutiny, potential penalties
    - "medium" → Compliance finding, observations in audit
    - "low" → Best practice, advisory, minor observation

12. REGULATORY_REFERENCE (string, optional)
    - Specific circular/section reference if mentioned
    - Example: "RBI/2022-23/142" or "Section 12(1) of PML Act"

13. TIMELINE (string, optional)
    - Any deadline or periodic requirement mentioned
    - Example: "Within 7 days", "Quarterly", "Annual review"

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return a JSON array with one object per clause, in order. Each object must have 
all fields above (use null for optional fields if not applicable).

Return ONLY the JSON array, no markdown formatting or explanation."""

    # =========================================================================
    # GAP ANALYSIS PROMPTS
    # =========================================================================
    
    GAP_ANALYSIS_PROMPT = """Analyze the compliance gap between this internal policy clause and the regulatory requirement.

═══════════════════════════════════════════════════════════════════════════════
REGULATORY REQUIREMENT (Source of Truth)
═══════════════════════════════════════════════════════════════════════════════
Regulation: {regulation_title}
Regulator: {regulator}

Clause:
{regulation_clause}

Requirement Type: {regulation_req_type}
Key Obligations: {regulation_obligations}

═══════════════════════════════════════════════════════════════════════════════
INTERNAL POLICY (Implementation)
═══════════════════════════════════════════════════════════════════════════════
Policy: {policy_title}
Version: {policy_version}

Clause:
{policy_clause}

Requirement Type: {policy_req_type}
Key Obligations: {policy_obligations}

═══════════════════════════════════════════════════════════════════════════════
GAP ANALYSIS INSTRUCTIONS
═══════════════════════════════════════════════════════════════════════════════

Compare the POLICY against the REGULATION and identify:

1. GAP_TYPE (string) - ONE of:
   - "fully_compliant" → Policy fully addresses the requirement
   - "partial" → Policy addresses some but not all aspects
   - "missing" → Regulation requires X, policy is completely silent
   - "weak" → Policy uses weaker language (should vs shall)
   - "conflicting" → Policy contradicts or undermines regulation
   - "exceeds" → Policy goes beyond regulatory requirement (positive)

2. SEVERITY (string):
   - "Critical" → License risk, immediate regulatory action needed
   - "High" → Significant gap, penalty exposure, audit finding
   - "Medium" → Moderate gap, observation likely, needs attention
   - "Low" → Minor gap, best practice improvement

3. CONFIDENCE_SCORE (float 0.0-1.0):
   - How confident are you in this assessment?
   - 0.9+ = Very confident, clear evidence
   - 0.7-0.9 = Confident, reasonable interpretation
   - 0.5-0.7 = Moderate, some ambiguity
   - <0.5 = Low confidence, needs human review

4. GAP_DESCRIPTION (string):
   - Specific description of what's missing or weak
   - Reference specific language differences
   - Be precise and actionable

5. MISSING_ELEMENTS (array of strings):
   - Specific requirements not addressed in policy
   - Examples: "Timeline for reporting not specified",
     "Threshold amounts not defined"

6. REGULATORY_RISK (string):
   - What happens if this gap is not addressed?
   - Reference potential consequences

7. REMEDIATION_ACTIONS (array of strings):
   - Specific actions to close the gap
   - Include: policy updates, process changes, system requirements
   - Make actionable for compliance team

8. PRIORITY (string):
   - "Immediate" → Fix within 1 week
   - "Short-term" → Fix within 1 month
   - "Medium-term" → Fix within quarter
   - "Long-term" → Fix within year

9. EVIDENCE_NEEDED (array of strings):
   - What evidence would demonstrate gap closure?
   - For audit/examination purposes

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return a JSON object with all fields above.
Return ONLY the JSON object, no explanation."""

    # =========================================================================
    # ADDITIONAL PROMPTS FOR OTHER USE CASES
    # =========================================================================
    
    REGULATORY_SUMMARY_PROMPT = """Summarize this regulatory circular for compliance officers.

CIRCULAR DETAILS:
- Regulator: {regulator}
- Circular Number: {circular_number}
- Date: {circular_date}
- Title: {circular_title}

CIRCULAR TEXT:
{circular_text}

PROVIDE:
1. EXECUTIVE_SUMMARY (3-4 sentences)
   - What is this circular about?
   - Why is it issued now?

2. KEY_CHANGES (array of strings)
   - What's new or changed from before?
   - What requirements are modified?

3. APPLICABILITY (object)
   - "entities": Which entities does this apply to?
   - "effective_date": When does it come into effect?
   - "compliance_date": Deadline for compliance?

4. IMPACT_ASSESSMENT (object)
   - "business_impact": How does it affect business operations?
   - "technology_impact": System/IT changes needed?
   - "process_impact": Process changes required?
   - "cost_impact": Resource/cost implications?

5. DEPARTMENTS_AFFECTED (array of strings)
   - Which internal departments need to act?

6. ACTION_ITEMS (array of objects)
   - Specific actions with owners and timelines
   - Format: {{"action": "...", "owner": "...", "timeline": "..."}}

7. CROSS_REFERENCES (array of strings)
   - Related circulars, previous directions, superseded circulars

8. COMPLIANCE_CHECKLIST (array of strings)
   - Key compliance checkpoints

Return as JSON object."""

    AUDIT_OBSERVATION_PROMPT = """Generate an audit observation/finding based on this compliance gap.

GAP DETAILS:
{gap_details}

GENERATE:
1. OBSERVATION_TITLE (string)
   - Concise, professional title for audit report

2. OBSERVATION_DESCRIPTION (string)
   - Factual description of the finding
   - What was observed vs what was expected?

3. ROOT_CAUSE (string)
   - Why does this gap exist?

4. RISK_IMPLICATION (string)
   - What are the consequences of this gap?

5. RECOMMENDATION (string)
   - What should management do?

6. MANAGEMENT_RESPONSE (string - template)
   - Suggested response format for management

7. RATING (string)
   - "Critical" / "High" / "Medium" / "Low"

Return as JSON object."""


# =============================================================================
# MAIN CONTEXT CLASS
# =============================================================================

@dataclass
class ComplianceContext:
    """
    Central configuration for compliance-related LLM operations.
    
    This class provides:
    1. Domain knowledge and taxonomies
    2. Prompt templates for various operations
    3. Output schemas for structured responses
    4. Helper methods for building prompts
    
    Usage:
        ctx = ComplianceContext()
        
        # Get system prompt for clause extraction
        system_prompt = ctx.get_system_prompt("clause_extraction")
        
        # Build extraction prompt with variables
        user_prompt = ctx.build_extraction_prompt(
            chunk_text="The bank shall...",
            document_type="regulation",
            document_title="RBI KYC Direction",
            section_name="Customer Identification"
        )
    """
    
    # Configuration options
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 0.1  # Low temperature for consistent compliance outputs
    
    # Domain data
    subject_categories: Dict[str, SubjectCategory] = field(default_factory=lambda: SUBJECT_CATEGORIES)
    obligation_patterns: Dict[str, Dict] = field(default_factory=lambda: OBLIGATION_PATTERNS)
    entity_types: Dict[str, List[str]] = field(default_factory=lambda: ENTITY_TYPES)
    
    # Prompts
    prompts: type = field(default_factory=lambda: CompliancePrompts)
    
    def get_system_prompt(self, prompt_type: str) -> str:
        """Get system prompt for a specific operation type."""
        base = CompliancePrompts.SYSTEM_PROMPTS.get("base", "")
        specific = CompliancePrompts.SYSTEM_PROMPTS.get(prompt_type, "")
        return f"{base}\n\n{specific}".strip()
    
    def get_subject_categories_string(self) -> str:
        """Get formatted string of subject categories for prompts."""
        lines = []
        for cat_id, cat in self.subject_categories.items():
            lines.append(f"   - {cat_id}: {cat.name}")
        return "\n".join(lines)
    
    def get_subject_category_keywords(self, category_id: str) -> List[str]:
        """Get keywords for a subject category."""
        cat = self.subject_categories.get(category_id)
        return cat.keywords if cat else []
    
    def build_extraction_prompt(
        self,
        chunk_text: str,
        document_type: str = "regulation",
        document_title: str = "",
        section_name: str = "",
        page_number: int = 1,
        issuer: str = "",
        policy_type: str = "",
        version: str = ""
    ) -> str:
        """Build a clause extraction prompt with variables filled in."""
        if document_type in ["policy", "sop", "internal_memo"]:
            template = CompliancePrompts.POLICY_EXTRACTION_PROMPT
            return template.format(
                document_title=document_title or "Internal Policy",
                policy_type=policy_type or "Compliance Policy",
                section_name=section_name or "General",
                version=version or "1.0",
                chunk_text=chunk_text
            )
        else:
            template = CompliancePrompts.CLAUSE_EXTRACTION_PROMPT
            return template.format(
                document_type=document_type,
                document_title=document_title or "Regulatory Document",
                issuer=issuer or "Regulator",
                section_name=section_name or "General",
                page_number=page_number,
                chunk_text=chunk_text
            )
    
    def build_enrichment_prompt(
        self,
        clauses_text: str,
        document_type: str = "regulation",
        document_title: str = "",
        issuer: str = "",
        document_context: str = ""
    ) -> str:
        """Build a semantic enrichment prompt with variables filled in."""
        template = CompliancePrompts.SEMANTIC_ENRICHMENT_PROMPT
        return template.format(
            document_type=document_type,
            document_title=document_title or "Regulatory Document",
            issuer=issuer or "Regulator",
            document_context=document_context or "Compliance document for gap analysis",
            clauses_text=clauses_text,
            subject_categories=self.get_subject_categories_string()
        )
    
    def build_gap_analysis_prompt(
        self,
        regulation_clause: str,
        policy_clause: str,
        regulation_title: str = "",
        policy_title: str = "",
        regulator: str = "",
        policy_version: str = "",
        regulation_req_type: str = "",
        policy_req_type: str = "",
        regulation_obligations: List[str] = None,
        policy_obligations: List[str] = None
    ) -> str:
        """Build a gap analysis prompt with variables filled in."""
        template = CompliancePrompts.GAP_ANALYSIS_PROMPT
        return template.format(
            regulation_title=regulation_title or "Regulatory Requirement",
            regulator=regulator or "RBI",
            regulation_clause=regulation_clause,
            regulation_req_type=regulation_req_type or "mandatory",
            regulation_obligations=json.dumps(regulation_obligations or []),
            policy_title=policy_title or "Internal Policy",
            policy_version=policy_version or "1.0",
            policy_clause=policy_clause,
            policy_req_type=policy_req_type or "mandatory",
            policy_obligations=json.dumps(policy_obligations or [])
        )
    
    def build_regulatory_summary_prompt(
        self,
        circular_text: str,
        regulator: str = "",
        circular_number: str = "",
        circular_date: str = "",
        circular_title: str = ""
    ) -> str:
        """Build a regulatory summary prompt."""
        template = CompliancePrompts.REGULATORY_SUMMARY_PROMPT
        return template.format(
            regulator=regulator or "RBI",
            circular_number=circular_number or "",
            circular_date=circular_date or "",
            circular_title=circular_title or "Regulatory Circular",
            circular_text=circular_text
        )
    
    def infer_requirement_type(self, text: str) -> RequirementType:
        """Infer requirement type from text patterns."""
        import re
        text_lower = text.lower()
        
        for pattern_name, pattern_data in self.obligation_patterns.items():
            for pattern in pattern_data["patterns"]:
                if re.search(pattern, text_lower):
                    return pattern_data["requirement_type"]
        
        return RequirementType.INFORMATIONAL
    
    def infer_criticality(self, text: str, requirement_type: RequirementType = None) -> CriticalityLevel:
        """Infer criticality level from text and requirement type."""
        text_lower = text.lower()
        
        # Check for penalty references
        if any(term in text_lower for term in ["penalty", "punishable", "imprisonment", "license"]):
            return CriticalityLevel.CRITICAL
        
        # Check for prohibition
        if requirement_type == RequirementType.PROHIBITION:
            return CriticalityLevel.HIGH
        
        # Check for mandatory with timeline
        if "within" in text_lower and any(term in text_lower for term in ["shall", "must"]):
            return CriticalityLevel.HIGH
        
        # Default based on requirement type
        if requirement_type == RequirementType.MANDATORY:
            return CriticalityLevel.MEDIUM
        
        return CriticalityLevel.LOW
    
    def detect_subject_category(self, text: str) -> str:
        """Detect subject category from text using keyword matching."""
        text_lower = text.lower()
        category_scores = {}
        
        for cat_id, cat in self.subject_categories.items():
            score = sum(1 for keyword in cat.keywords if keyword in text_lower)
            if score > 0:
                category_scores[cat_id] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return "general"
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "subject_categories": {k: v.__dict__ for k, v in self.subject_categories.items()},
            "obligation_patterns": self.obligation_patterns,
            "entity_types": self.entity_types
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComplianceContext":
        """Create context from dictionary."""
        ctx = cls()
        ctx.model = data.get("model", ctx.model)
        ctx.max_tokens = data.get("max_tokens", ctx.max_tokens)
        ctx.temperature = data.get("temperature", ctx.temperature)
        return ctx


# =============================================================================
# OUTPUT SCHEMAS - For Validation
# =============================================================================

EXTRACTION_OUTPUT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "clause_number": {"type": "integer"},
            "text": {"type": "string"},
            "type_hint": {"type": "string", "enum": ["requirement", "prohibition", "condition", "definition", "informational"]}
        },
        "required": ["clause_number", "text"]
    }
}

ENRICHMENT_OUTPUT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "requirement_type": {"type": "string"},
            "subject_category": {"type": "string"},
            "key_obligations": {"type": "array", "items": {"type": "string"}},
            "semantic_summary": {"type": "string"},
            "entities_involved": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "compliance_indicators": {"type": "array", "items": {"type": "string"}},
            "criticality": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            "regulatory_reference": {"type": ["string", "null"]},
            "timeline": {"type": ["string", "null"]}
        },
        "required": ["title", "content", "tags", "requirement_type", "subject_category", 
                    "key_obligations", "semantic_summary", "criticality"]
    }
}

GAP_ANALYSIS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "gap_type": {"type": "string", "enum": ["fully_compliant", "partial", "missing", "weak", "conflicting", "exceeds"]},
        "severity": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
        "gap_description": {"type": "string"},
        "missing_elements": {"type": "array", "items": {"type": "string"}},
        "regulatory_risk": {"type": "string"},
        "remediation_actions": {"type": "array", "items": {"type": "string"}},
        "priority": {"type": "string", "enum": ["Immediate", "Short-term", "Medium-term", "Long-term"]},
        "evidence_needed": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["gap_type", "severity", "confidence_score", "gap_description", "remediation_actions"]
}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_default_context() -> ComplianceContext:
    """Get default compliance context with standard configuration."""
    return ComplianceContext()


def get_all_subject_categories() -> List[str]:
    """Get list of all subject category IDs."""
    return list(SUBJECT_CATEGORIES.keys())


def get_all_requirement_types() -> List[str]:
    """Get list of all requirement type values."""
    return [rt.value for rt in RequirementType]


def get_all_regulators() -> List[str]:
    """Get list of all regulator values."""
    return [r.value for r in Regulator]
