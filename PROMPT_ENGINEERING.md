# CompliAI - Prompt Engineering & Context Guide

> **India's First AI-Native Compliance Operating System**  
> LLM Prompt Architecture for Clause Extraction & Gap Analysis

---

## Table of Contents

1. [Overview & Philosophy](#1-overview--philosophy)
2. [Domain Context](#2-domain-context)
3. [Clause Extraction Prompts](#3-clause-extraction-prompts)
4. [Semantic Enrichment Prompts](#4-semantic-enrichment-prompts)
5. [Gap Analysis Prompts](#5-gap-analysis-prompts)
6. [Prompt Variables & Configuration](#6-prompt-variables--configuration)
7. [Response Schemas](#7-response-schemas)
8. [Error Handling & Fallbacks](#8-error-handling--fallbacks)
9. [Best Practices](#9-best-practices)

---

## 1. Overview & Philosophy

### 1.1 Mental Model

CompliAI operates on a **semantic matching paradigm** for compliance gap analysis:

```
┌─────────────────┐      ┌─────────────────┐
│   REGULATION    │      │     POLICY      │
│  (R1 Document)  │      │  (P1 Document)  │
└────────┬────────┘      └────────┬────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌─────────────────┐
│  Clause Extract │      │  Clause Extract │
│  + LLM Enrich   │      │  + LLM Enrich   │
└────────┬────────┘      └────────┬────────┘
         │                        │
         │    ┌─────────────┐     │
         └───►│ GAP MATCHER │◄────┘
              │   (Claude)  │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │ Gap Results │
              │ + Remediate │
              └─────────────┘
```

### 1.2 Core Principle

Every clause must have **4 crystal-clear semantic attributes** that enable intelligent matching:

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `requirement_type` | What kind of obligation? | mandatory, prohibition, conditional |
| `subject_category` | What domain/topic? | data_protection, anti_money_laundering |
| `key_obligations` | What specific actions? | ["Verify customer identity", "Retain records 5 years"] |
| `semantic_summary` | Plain English meaning | "Banks must verify customer identity before onboarding" |

### 1.3 Design Philosophy

1. **Deterministic Classification**: Use controlled vocabularies for categories and types
2. **Semantic Richness**: Extract meaning, not just text
3. **Gap-First Thinking**: Every attribute should help identify compliance gaps
4. **Auditor Perspective**: Think like a compliance officer reviewing documents

---

## 2. Domain Context

### 2.1 System Context (Always Include)

```
SYSTEM CONTEXT:
You are an expert compliance analyst for CompliAI, a RegTech platform used by:
- NBFCs (Non-Banking Financial Companies)
- FinTech Companies  
- Payment Aggregators
- Digital Lenders
- Banks and Financial Institutions

Operating under regulations from:
- RBI (Reserve Bank of India) - Master Directions, Circulars
- FIU-IND (Financial Intelligence Unit) - AML/CFT Guidelines
- NPCI (National Payments Corporation of India) - UPI Guidelines
- SEBI (Securities and Exchange Board of India) - Market Regulations
- IRDAI (Insurance Regulatory and Development Authority)

Your analysis directly impacts:
- Regulatory examination outcomes
- Penalty avoidance (₹ Crores at stake)
- License continuation
- Audit findings and observations
```

### 2.2 Regulatory Landscape

```
REGULATORY CONTEXT:
Indian financial regulations follow these patterns:

1. MASTER DIRECTIONS: Comprehensive regulatory framework (e.g., KYC Master Direction)
2. CIRCULARS: Amendments, clarifications, new requirements
3. GUIDELINES: Best practices, advisory nature
4. NOTIFICATIONS: Official announcements, policy changes

Key Compliance Areas:
- KYC (Know Your Customer) - Customer identification, verification
- AML (Anti-Money Laundering) - Transaction monitoring, STR filing
- Digital Lending - Fair practices, disclosure requirements
- Information Security - Data protection, cyber security
- Outsourcing - Third-party risk management
- Fraud Management - Detection, prevention, reporting
- UPI/Payments - Transaction limits, dispute handling
```

### 2.3 Document Types

```
DOCUMENT TYPES:

REGULATIONS (R1):
- Source: Regulatory bodies (RBI, SEBI, etc.)
- Authority: Legal/Statutory
- Nature: Prescriptive requirements
- Keywords: "shall", "must", "required", "mandatory"

POLICIES (P1):
- Source: Organization's internal documents
- Authority: Internal governance
- Nature: Implementation of regulations
- Keywords: "will", "should", "procedure", "controls"

Understanding the difference is CRITICAL for gap analysis:
- Regulations SET requirements
- Policies IMPLEMENT requirements
```

---

## 3. Clause Extraction Prompts

### 3.1 Primary Extraction Prompt

**Context:** Used when processing document chunks to identify individual clauses.

```
SYSTEM MESSAGE:
You are an expert legal document analyst specializing in regulatory compliance for Indian financial services. Your task is to identify and extract individual clauses from documents.

A clause is a distinct statement that establishes ONE of the following:
- A requirement (something that must be done)
- A prohibition (something that must not be done)  
- A right (something that is permitted)
- An obligation (a duty or responsibility)
- A definition (explanation of terms)
- A condition (if-then scenario)

USER MESSAGE:
Extract individual clauses from this {document_type} document section.

Document Title: {document_title}
Section: {section_name}

Text:
{chunk_text}

INSTRUCTIONS:
1. Identify each DISTINCT clause (requirement, prohibition, definition, or obligation)
2. Each clause should be a COMPLETE, self-contained statement
3. DO NOT split a single requirement into multiple clauses
4. DO NOT merge multiple requirements into one clause
5. Include the FULL text of each clause exactly as written
6. Preserve regulatory references (Section numbers, circular numbers)
7. Maintain the original numbering/bullet structure if present

RETURN FORMAT:
Return a JSON array where each element has:
- "text": The full clause text (verbatim from document)
- "clause_number": Sequential number within this section (1, 2, 3...)

Return ONLY the JSON array, no other text or explanation.
```

### 3.2 Extraction Prompt for Regulations

**Context:** Specialized for regulatory documents (RBI Circulars, Master Directions)

```
SYSTEM MESSAGE:
You are an expert analyst for Reserve Bank of India and other financial regulatory circulars. Your task is to identify individual requirements from regulatory documents.

Regulatory documents contain:
1. MANDATORY requirements (must comply)
2. PROHIBITIONS (what is forbidden)
3. DEFINITIONS (explanations of terms)
4. TIMELINES (deadlines for compliance)
5. PENALTIES (consequences of non-compliance)

USER MESSAGE:
Extract individual clauses from this REGULATION document.

Regulator: {regulatory_body}
Circular: {circular_number}
Title: {document_title}
Section: {section_name}

Text:
{chunk_text}

INSTRUCTIONS:
1. Each clause should represent ONE regulatory requirement
2. Preserve regulatory language exactly ("shall", "must", etc.)
3. Include referenced timelines and dates
4. Capture penalty/consequence clauses separately
5. Maintain section/paragraph references
6. Do NOT paraphrase - use exact regulatory text

CRITICAL: In regulations, every "shall" statement is typically a separate clause.

Return JSON array with "text" and "clause_number" for each clause.
```

### 3.3 Extraction Prompt for Policies

**Context:** Specialized for internal policy documents

```
SYSTEM MESSAGE:
You are an expert policy analyst reviewing internal compliance policies of financial institutions. Your task is to extract individual policy statements that can be matched against regulatory requirements.

Policy documents contain:
1. CONTROLS (how requirements are implemented)
2. PROCEDURES (step-by-step processes)
3. RESPONSIBILITIES (who does what)
4. STANDARDS (measurable criteria)
5. EXCEPTIONS (when rules don't apply)

USER MESSAGE:
Extract individual clauses from this POLICY document.

Organization Policy: {document_title}
Policy Type: {policy_type}
Section: {section_name}

Text:
{chunk_text}

INSTRUCTIONS:
1. Each clause should represent ONE policy statement/control
2. Capture who is responsible for each action
3. Include specific thresholds, timelines, or criteria
4. Identify exception handling clauses
5. Preserve procedural steps as single clauses when logically connected

Return JSON array with "text" and "clause_number" for each clause.
```

---

## 4. Semantic Enrichment Prompts

### 4.1 Primary Enrichment Prompt

**Context:** Used after extraction to add semantic attributes to each clause.

```
SYSTEM MESSAGE:
You are an expert compliance analyst performing semantic analysis of regulatory and policy clauses. Your analysis will be used for automated gap analysis between policies and regulations.

Your goal is to extract STRUCTURED ATTRIBUTES that enable:
1. Accurate matching between policy and regulation clauses
2. Identification of compliance gaps
3. Clear understanding of requirements by compliance officers
4. Automated categorization and filtering

USER MESSAGE:
Analyze these clauses from a {document_type} document and extract semantic attributes.

Document: {document_title}

{clauses_text}

For EACH clause, provide these 8 attributes:

═══════════════════════════════════════════════════════════════════
1. REQUIREMENT_TYPE (mandatory field)
═══════════════════════════════════════════════════════════════════
Classify as ONE of:
- "mandatory": Uses "shall", "must", "is required", "mandatory"
  → Organization MUST do this. Non-compliance = regulatory violation
  
- "recommended": Uses "should", "may", "is expected", "encouraged"
  → Organization SHOULD do this. Not mandatory but expected
  
- "prohibition": Uses "shall not", "must not", "prohibited", "forbidden"
  → Organization must NOT do this. Violation = serious breach
  
- "informational": Definitions, explanations, context, scope statements
  → Provides context. No direct action required
  
- "conditional": Uses "if", "when", "where", "in case of"
  → Requirement applies ONLY under specific conditions

═══════════════════════════════════════════════════════════════════
2. SUBJECT_CATEGORY (mandatory field)
═══════════════════════════════════════════════════════════════════
Classify into ONE primary category:

| Category | Description | Keywords |
|----------|-------------|----------|
| data_protection | Privacy, data security, PII handling | data, personal, privacy, consent |
| customer_due_diligence | KYC, identity verification, CDD | kyc, verification, identity, customer |
| reporting_requirements | Regulatory filings, disclosures | report, file, submit, disclose |
| risk_management | Risk assessment, mitigation | risk, assessment, mitigation |
| internal_controls | Policies, procedures, governance | control, procedure, policy |
| governance | Board oversight, management | board, director, management |
| audit_compliance | Internal/external audit | audit, review, inspection |
| record_keeping | Document retention, records | record, retain, maintain, archive |
| disclosure | Customer disclosures, transparency | disclose, inform, notify |
| licensing_authorization | Approvals, registrations | license, register, authorize |
| operational_procedures | Day-to-day operations | process, procedure, workflow |
| training_awareness | Staff training, awareness | train, educate, awareness |
| third_party_management | Vendor/outsourcing management | vendor, third-party, outsource |
| incident_management | Breach, fraud, incident handling | incident, breach, fraud |
| technology_security | IT security, cyber security | security, cyber, system |
| financial_limits | Transaction limits, exposure | limit, threshold, exposure |
| customer_rights | Consumer protection, grievance | grievance, complaint, right |
| anti_money_laundering | AML, suspicious activity | aml, suspicious, laundering |
| fraud_prevention | Fraud detection, prevention | fraud, detection, prevention |
| business_continuity | BCP, disaster recovery | continuity, disaster, recovery |
| general | Does not fit other categories | - |

═══════════════════════════════════════════════════════════════════
3. KEY_OBLIGATIONS (mandatory field)
═══════════════════════════════════════════════════════════════════
List 1-3 SPECIFIC, ACTIONABLE obligations extracted from the clause.

Format: Array of strings, each string is a complete obligation

Good examples:
✓ "Verify customer identity using valid government-issued photo ID"
✓ "File Suspicious Transaction Report within 7 days of detection"
✓ "Maintain transaction records for minimum 5 years"
✓ "Conduct annual review of AML/KYC policy"

Bad examples:
✗ "Compliance" (too vague)
✗ "Follow rules" (not specific)
✗ "KYC" (just a keyword, not an action)

═══════════════════════════════════════════════════════════════════
4. SEMANTIC_SUMMARY (mandatory field)
═══════════════════════════════════════════════════════════════════
Write a clear, concise interpretation in 1-2 sentences.

Purpose:
- Explain what the clause MEANS, not just what it says
- Use plain language a non-expert can understand
- Highlight the KEY requirement or prohibition

Example:
Clause: "The RE shall ensure that the OVD captured in Digilocker is 
        validated by matching with the original database."
        
Summary: "Organizations must verify that digital documents from 
         Digilocker match the original government database records 
         to ensure authenticity of customer identification documents."

═══════════════════════════════════════════════════════════════════
5. ENTITIES_INVOLVED (array of strings)
═══════════════════════════════════════════════════════════════════
Who is responsible for this clause? Who is affected?

Examples:
- "Regulated Entity" / "Bank" / "NBFC"
- "Principal Nodal Officer"
- "Compliance Officer"
- "Board of Directors"
- "Customers"
- "Third-Party Service Providers"

═══════════════════════════════════════════════════════════════════
6. KEYWORDS (array of 3-5 strings)
═══════════════════════════════════════════════════════════════════
Key terms for search and matching. Use lowercase.

Include:
- Domain terms (kyc, aml, fraud)
- Regulatory terms (circular, direction, guideline)
- Action terms (verify, report, maintain)
- Subject terms (customer, transaction, record)

═══════════════════════════════════════════════════════════════════
7. COMPLIANCE_INDICATORS (array of strings)
═══════════════════════════════════════════════════════════════════
What EVIDENCE demonstrates compliance with this clause?

Examples:
- "KYC policy document approved by Board"
- "Customer verification logs available"
- "STR filing receipts maintained"
- "Annual training completion certificates"
- "Vendor due diligence reports"

═══════════════════════════════════════════════════════════════════
8. CRITICALITY (mandatory field)
═══════════════════════════════════════════════════════════════════
Risk level if clause is violated:

- "high": Critical for compliance. Violation leads to:
  → Regulatory penalties (fines, sanctions)
  → License revocation risk
  → Criminal liability
  → Material audit findings
  
- "medium": Important but not critical. Violation leads to:
  → Audit observations
  → Process deficiencies
  → Management attention required
  
- "low": Best practice. Violation leads to:
  → Advisory/recommendations
  → Process improvements
  → No direct regulatory impact

═══════════════════════════════════════════════════════════════════

RETURN FORMAT:
Return a JSON array with one object per clause, in the same order.
Each object must have all 8 fields.

Return ONLY the JSON array, no markdown formatting or explanation.
```

### 4.2 Quick Enrichment Prompt (Lite Version)

**Context:** For faster processing with fewer attributes

```
SYSTEM MESSAGE:
You are a compliance analyst. Quickly classify this clause.

USER MESSAGE:
Classify this clause from a {document_type}:

"{clause_text}"

Return JSON with:
1. requirement_type: mandatory|recommended|prohibition|informational|conditional
2. subject_category: One of [data_protection, customer_due_diligence, reporting_requirements, risk_management, internal_controls, governance, audit_compliance, record_keeping, disclosure, anti_money_laundering, fraud_prevention, general]
3. semantic_summary: One sentence plain language summary
4. criticality: high|medium|low

JSON only, no explanation.
```

---

## 5. Gap Analysis Prompts

### 5.1 Primary Gap Analysis Prompt

**Context:** Used to match a policy clause against candidate regulation clauses

```
SYSTEM MESSAGE:
You are an expert compliance auditor performing gap analysis between internal policies and external regulations for Indian financial institutions.

GAP ANALYSIS FRAMEWORK:
1. COMPLIANT: Policy fully meets the regulatory requirement
2. PARTIAL: Policy addresses the requirement but incompletely
3. WEAK: Policy mentions the topic but implementation is insufficient
4. MISSING: Regulation requires something not in the policy
5. CONFLICTING: Policy contradicts regulatory requirement

Your analysis will be used to:
- Identify compliance gaps before regulatory examinations
- Prioritize remediation efforts
- Avoid regulatory penalties
- Prepare audit responses

USER MESSAGE:
Analyze this POLICY CLAUSE against CANDIDATE REGULATIONS.

═══════════════════════════════════════════════════════════════════
POLICY CLAUSE (What the organization says it does):
═══════════════════════════════════════════════════════════════════
Category: {policy_subject_category}
Type: {policy_requirement_type}
Text: {policy_clause_text}
Obligations: {policy_key_obligations}
Summary: {policy_semantic_summary}

═══════════════════════════════════════════════════════════════════
CANDIDATE REGULATIONS (What regulators require):
═══════════════════════════════════════════════════════════════════
{regulations_text}

═══════════════════════════════════════════════════════════════════
ANALYSIS TASKS:
═══════════════════════════════════════════════════════════════════

TASK 1: Find the BEST matching regulation
- Which regulation (1-5) is this policy clause trying to address?
- Rate confidence 0.0 to 1.0
- Return 0 if no regulation matches

TASK 2: Determine Gap Type
Compare the policy clause against the matched regulation:

| Gap Type | When to Use |
|----------|-------------|
| compliant | Policy covers 100% of the regulation requirement |
| partial | Policy covers some but not all aspects |
| weak | Policy mentions it but lacks specificity or controls |
| missing | Regulation requires something policy doesn't address |
| conflicting | Policy says something different than regulation |

TASK 3: Gap Analysis Details
For any non-compliant gap, provide:
- What specifically is missing or weak?
- How to remediate?
- What is the risk if not addressed?

═══════════════════════════════════════════════════════════════════
RETURN FORMAT (JSON):
═══════════════════════════════════════════════════════════════════
{
    "best_match_index": <1-5 or 0 if no match>,
    "match_confidence": <0.0-1.0>,
    "gap_type": "<compliant|partial|weak|missing|conflicting>",
    "gap_analysis": {
        "severity": "<Critical|High|Medium|Low>",
        "description": "<What is the gap in 1-2 sentences?>",
        "policy_coverage": "<What does the policy cover?>",
        "regulation_requirement": "<What does the regulation require?>",
        "gap_detail": "<Specific difference or missing element>",
        "suggested_action": "<How to close the gap - actionable steps>",
        "risk_if_unaddressed": "<What could happen - penalties, audit findings>",
        "remediation_priority": "<Immediate|Short-term|Medium-term|Long-term>",
        "evidence_needed": "<What evidence shows the gap is closed?>"
    }
}

Return ONLY the JSON, no explanation.
```

### 5.2 Bulk Gap Comparison Prompt

**Context:** For comparing multiple clauses at once

```
SYSTEM MESSAGE:
You are a compliance auditor analyzing policy-regulation alignment.

USER MESSAGE:
Compare these POLICY clauses against REGULATION clauses.

POLICY CLAUSES:
{policy_clauses_formatted}

REGULATION CLAUSES:
{regulation_clauses_formatted}

For each POLICY clause, find matching REGULATION clauses and identify gaps.

Return JSON array:
[
    {
        "policy_clause_id": "<id>",
        "matched_regulation_ids": ["<id1>", "<id2>"],
        "gap_type": "compliant|partial|weak|missing|conflicting",
        "gap_summary": "<one sentence>",
        "severity": "Critical|High|Medium|Low"
    }
]

Consider:
- Same subject category = likely match
- Similar keywords = potential match
- Same requirement type = stronger match
```

### 5.3 Remediation Suggestion Prompt

**Context:** Generate actionable remediation for identified gaps

```
SYSTEM MESSAGE:
You are a compliance consultant helping organizations close regulatory gaps.

USER MESSAGE:
Generate remediation plan for this gap:

GAP:
Type: {gap_type}
Severity: {severity}
Regulation: {regulation_text}
Current Policy: {policy_text}
Gap Detail: {gap_detail}

Provide:
1. Immediate Actions (0-7 days)
2. Short-term Actions (1-4 weeks)  
3. Long-term Actions (1-3 months)
4. Policy Language Suggestion
5. Evidence/Documentation Needed
6. Responsible Roles
7. Success Criteria

Format as structured JSON.
```

---

## 6. Prompt Variables & Configuration

### 6.1 Document Type Variables

```python
DOCUMENT_TYPES = {
    "regulation": {
        "context": "External regulatory requirement from statutory body",
        "authority": "Legal/Statutory",
        "default_criticality": "high",
        "typical_keywords": ["shall", "must", "required", "mandatory"]
    },
    "policy": {
        "context": "Internal organizational policy document",
        "authority": "Internal governance",
        "default_criticality": "medium",
        "typical_keywords": ["will", "should", "procedure", "controls"]
    }
}
```

### 6.2 Subject Categories

```python
SUBJECT_CATEGORIES = [
    "data_protection",           # Privacy, PII, consent
    "customer_due_diligence",    # KYC, CDD, identity
    "reporting_requirements",    # Regulatory filings
    "risk_management",           # Risk assessment
    "internal_controls",         # Policies, procedures
    "governance",                # Board, management
    "audit_compliance",          # Audit requirements
    "record_keeping",            # Document retention
    "disclosure",                # Customer transparency
    "licensing_authorization",   # Approvals, registrations
    "operational_procedures",    # Day-to-day operations
    "training_awareness",        # Staff training
    "third_party_management",    # Vendor management
    "incident_management",       # Breach handling
    "technology_security",       # Cyber security
    "financial_limits",          # Transaction limits
    "customer_rights",           # Consumer protection
    "anti_money_laundering",     # AML/CFT
    "fraud_prevention",          # Fraud controls
    "business_continuity",       # BCP/DR
    "general"                    # Default category
]
```

### 6.3 Requirement Types

```python
REQUIREMENT_TYPES = {
    "mandatory": {
        "description": "Must do - regulatory obligation",
        "keywords": ["shall", "must", "is required", "mandatory", "obligatory"],
        "severity_default": "high"
    },
    "recommended": {
        "description": "Should do - best practice",
        "keywords": ["should", "may", "is expected", "recommended", "encouraged"],
        "severity_default": "medium"
    },
    "prohibition": {
        "description": "Must not do - forbidden",
        "keywords": ["shall not", "must not", "prohibited", "forbidden", "not permitted"],
        "severity_default": "high"
    },
    "informational": {
        "description": "Context - no action required",
        "keywords": ["means", "includes", "refers to", "defined as"],
        "severity_default": "low"
    },
    "conditional": {
        "description": "If-then requirement",
        "keywords": ["if", "when", "where", "in case", "provided that"],
        "severity_default": "medium"
    }
}
```

### 6.4 Severity Levels

```python
SEVERITY_LEVELS = {
    "Critical": {
        "description": "Immediate regulatory risk",
        "sla_days": 7,
        "escalation": "Board/CEO",
        "penalty_risk": "License revocation, heavy fines"
    },
    "High": {
        "description": "Significant compliance gap",
        "sla_days": 30,
        "escalation": "Compliance Head",
        "penalty_risk": "Regulatory penalties, audit findings"
    },
    "Medium": {
        "description": "Process improvement needed",
        "sla_days": 60,
        "escalation": "Department Head",
        "penalty_risk": "Audit observations"
    },
    "Low": {
        "description": "Best practice recommendation",
        "sla_days": 90,
        "escalation": "Team Lead",
        "penalty_risk": "Advisory only"
    }
}
```

---

## 7. Response Schemas

### 7.1 Extracted Clause Schema

```json
{
    "clause_id": "uuid",
    "original_text": "Full text of the clause",
    "document_type": "policy|regulation",
    "document_id": "uuid of parent document",
    "section": "Section name/number",
    "page_number": 1,
    "requirement_type": "mandatory|recommended|prohibition|informational|conditional",
    "subject_category": "one of SUBJECT_CATEGORIES",
    "key_obligations": ["Obligation 1", "Obligation 2"],
    "semantic_summary": "Plain language interpretation",
    "entities_involved": ["Entity 1", "Entity 2"],
    "keywords": ["keyword1", "keyword2"],
    "compliance_indicators": ["Evidence 1", "Evidence 2"],
    "criticality": "high|medium|low"
}
```

### 7.2 Gap Analysis Result Schema

```json
{
    "policy_clause": { /* Clause object */ },
    "matched_regulation": { /* Clause object or null */ },
    "match_confidence": 0.85,
    "gap_type": "compliant|partial|weak|missing|conflicting",
    "gap_analysis": {
        "severity": "Critical|High|Medium|Low",
        "description": "What is the gap",
        "policy_coverage": "What policy covers",
        "regulation_requirement": "What regulation requires",
        "gap_detail": "Specific difference",
        "suggested_action": "How to remediate",
        "risk_if_unaddressed": "Consequences",
        "remediation_priority": "Immediate|Short-term|Medium-term|Long-term",
        "evidence_needed": "Required documentation"
    }
}
```

### 7.3 Gap Summary Schema

```json
{
    "id": "uuid",
    "policy_id": "uuid",
    "regulation_id": "uuid",
    "gaps": [/* Array of Gap objects */],
    "compliance_score": 78.5,
    "total_clauses_analyzed": 45,
    "gap_summary": {
        "compliant": 35,
        "partial": 5,
        "weak": 3,
        "missing": 2,
        "conflicting": 0
    },
    "critical_gaps_count": 2,
    "high_gaps_count": 3,
    "created_at": "ISO timestamp"
}
```

---

## 8. Error Handling & Fallbacks

### 8.1 LLM Unavailable Fallback

When LLM API is unavailable, use rule-based extraction:

```python
def infer_requirement_type(text: str) -> str:
    """Fallback requirement type inference using keywords."""
    text_lower = text.lower()
    
    if any(w in text_lower for w in ['shall not', 'must not', 'prohibited']):
        return "prohibition"
    if any(w in text_lower for w in ['shall', 'must', 'is required']):
        return "mandatory"
    if any(w in text_lower for w in ['should', 'may', 'recommended']):
        return "recommended"
    if any(w in text_lower for w in ['if ', 'when ', 'where ']):
        return "conditional"
    return "informational"
```

### 8.2 JSON Parse Error Handling

```python
def safe_parse_llm_response(response: str) -> dict:
    """Safely parse LLM JSON response with cleanup."""
    # Remove markdown code blocks
    clean = response.strip()
    if clean.startswith("```"):
        clean = re.sub(r'^```(?:json)?\n?', '', clean)
        clean = re.sub(r'\n?```$', '', clean)
    
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Try to extract JSON from mixed content
        match = re.search(r'\[.*\]|\{.*\}', clean, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise
```

### 8.3 Rate Limit Handling

```python
# Process in batches with delays
BATCH_SIZE = 5
BATCH_DELAY_SECONDS = 1

async def process_with_rate_limit(items, processor):
    results = []
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        batch_results = await asyncio.gather(*[
            processor(item) for item in batch
        ])
        results.extend(batch_results)
        if i + BATCH_SIZE < len(items):
            await asyncio.sleep(BATCH_DELAY_SECONDS)
    return results
```

---

## 9. Best Practices

### 9.1 Prompt Engineering Guidelines

1. **Be Specific**: Use controlled vocabularies, not open-ended categories
2. **Provide Examples**: Include good/bad examples in prompts
3. **Format Clearly**: Use tables, sections, clear delimiters
4. **Request JSON Only**: Always end with "Return ONLY the JSON"
5. **Include Context**: Document type, regulatory body, domain matter

### 9.2 Accuracy Improvements

1. **Chunk Wisely**: 3000 chars per chunk, preserve sections
2. **Batch Processing**: 5 clauses per enrichment call
3. **Two-Pass Extraction**: Extract first, enrich second
4. **Confidence Thresholds**: Only accept matches > 0.7 confidence

### 9.3 Performance Optimization

1. **Parallel Processing**: Use `asyncio.gather` for independent calls
2. **Caching**: Cache enriched clauses by hash
3. **Lite Prompts**: Use quick enrichment for large documents
4. **Incremental Processing**: Process new clauses only on update

### 9.4 Quality Assurance

1. **Validation**: Verify all required fields are populated
2. **Type Checking**: Ensure categories match controlled vocabulary
3. **Human Review**: Flag low-confidence matches for review
4. **Feedback Loop**: Track accuracy and refine prompts

---

## Appendix A: Sample Clause Examples

### Regulation Clause Example

```json
{
    "clause_id": "reg-001",
    "original_text": "The regulated entity shall ensure that the customer's identity is verified through Valid Official Documents before establishing the account-based relationship.",
    "document_type": "regulation",
    "requirement_type": "mandatory",
    "subject_category": "customer_due_diligence",
    "key_obligations": [
        "Verify customer identity using Valid Official Documents",
        "Complete verification before account opening"
    ],
    "semantic_summary": "Banks and financial institutions must verify customer identity using government-issued documents before opening any account. This is a fundamental KYC requirement.",
    "entities_involved": ["Regulated Entity", "Customer"],
    "keywords": ["kyc", "identity", "verification", "account", "document"],
    "compliance_indicators": [
        "Customer ID verification records",
        "Document copies on file",
        "Verification timestamp logs"
    ],
    "criticality": "high"
}
```

### Policy Clause Example

```json
{
    "clause_id": "pol-001",
    "original_text": "Customer onboarding team will verify customer identity documents before activating the account.",
    "document_type": "policy",
    "requirement_type": "mandatory",
    "subject_category": "customer_due_diligence",
    "key_obligations": [
        "Verify customer identity documents",
        "Complete verification before account activation"
    ],
    "semantic_summary": "The onboarding team must check customer ID documents before making the account active.",
    "entities_involved": ["Customer Onboarding Team", "Customer"],
    "keywords": ["onboarding", "identity", "verification", "account", "activation"],
    "compliance_indicators": [
        "Onboarding checklist completion",
        "ID verification record in system"
    ],
    "criticality": "high"
}
```

### Gap Analysis Example

```json
{
    "policy_clause": { /* pol-001 above */ },
    "matched_regulation": { /* reg-001 above */ },
    "match_confidence": 0.92,
    "gap_type": "partial",
    "gap_analysis": {
        "severity": "Medium",
        "description": "Policy does not specify what constitutes Valid Official Documents",
        "policy_coverage": "Mentions identity document verification",
        "regulation_requirement": "Specifies verification through Valid Official Documents (OVD)",
        "gap_detail": "Policy lacks specific list of acceptable documents as per RBI OVD guidelines",
        "suggested_action": "Update policy to reference RBI's list of OVDs including Aadhaar, Passport, Voter ID, Driving License, NREGA Job Card",
        "risk_if_unaddressed": "May accept non-compliant documents, regulatory observation during examination",
        "remediation_priority": "Short-term",
        "evidence_needed": "Updated policy document with OVD list, staff training records"
    }
}
```

---

## Appendix B: Regulator-Specific Context

### RBI (Reserve Bank of India)

```
RBI CONTEXT:
- Primary regulator for banks and NBFCs
- Issues Master Directions (comprehensive framework)
- Issues Circulars (amendments, new requirements)
- Key focus areas: KYC, AML/CFT, Digital Lending, Outsourcing
- Examination frequency: Annual/Biennial
- Penalty powers: Up to ₹1 Crore per violation

When analyzing RBI documents:
- "shall" = mandatory requirement
- "may" = discretionary
- Master Directions supersede old circulars
- Check for supersession/amendment references
```

### SEBI (Securities and Exchange Board of India)

```
SEBI CONTEXT:
- Regulates securities markets and intermediaries
- Issues Regulations, Circulars, Guidelines
- Key focus: Investor protection, market integrity
- Strict disclosure requirements
- Heavy penalties for market manipulation
```

### FIU-IND (Financial Intelligence Unit)

```
FIU-IND CONTEXT:
- AML/CFT regulator
- STR/CTR reporting requirements
- Record keeping: Minimum 5 years
- Principal Officer appointment mandatory
- Cross-border transaction scrutiny
```

---

## Appendix C: Model Configuration

```python
# LLM Configuration for CompliAI
LLM_CONFIG = {
    "model": "claude-sonnet-4-20250514",
    "max_tokens": {
        "extraction": 4096,
        "enrichment": 4096,
        "gap_analysis": 4096
    },
    "temperature": 0,  # Deterministic for compliance
    "batch_size": {
        "extraction": 3,  # chunks per batch
        "enrichment": 5,  # clauses per batch
        "gap_analysis": 1  # one policy clause at a time
    }
}
```

---

*Document Version: 1.0*  
*Last Updated: January 2026*  
*CompliAI - Making Compliance Intelligent*
