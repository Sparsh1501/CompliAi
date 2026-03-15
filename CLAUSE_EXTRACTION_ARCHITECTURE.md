# Enhanced Clause Extraction & Gap Analysis Architecture

## Overview

This document describes the enhanced clause extraction system designed for accurate gap analysis between **Policy Documents (P1)** and **Regulation Documents (R1)**.

## Core Concept

When comparing a Policy against a Regulation for compliance:

```
Policy P1 (Internal)          Regulation R1 (External)
┌─────────────────────┐       ┌─────────────────────┐
│ Clause P1.1         │◄─────►│ Clause R1.1         │
│ Clause P1.2         │◄─────►│ Clause R1.2         │
│ Clause P1.3         │◄─────►│ Clause R1.3         │
│ ...                 │       │ ...                 │
└─────────────────────┘       └─────────────────────┘
         │                             │
         └────────┬────────────────────┘
                  ▼
          ┌──────────────┐
          │ GAP ANALYSIS │
          │  - Match by subject_category
          │  - Compare key_obligations
          │  - Evaluate semantic_summary
          └──────────────┘
```

## Enhanced Clause Structure

Each extracted clause has **4 core attributes** optimized for matching:

### 1. `requirement_type` (string)
What kind of requirement is this?

| Value | Description | Example Keywords |
|-------|-------------|------------------|
| `mandatory` | Must do | "shall", "must", "is required" |
| `recommended` | Should do | "should", "may", "is expected" |
| `prohibition` | Must not do | "shall not", "prohibited", "forbidden" |
| `informational` | Definitions/context | "means", "refers to", "for the purpose of" |
| `conditional` | If-then rules | "if", "when", "where applicable" |

### 2. `subject_category` (string)
What domain/topic does this clause cover?

Categories include:
- `data_protection` - Privacy, data handling, PII
- `customer_due_diligence` - KYC, identity verification
- `reporting_requirements` - Regulatory reports, filings
- `risk_management` - Risk assessment, controls
- `internal_controls` - Policies, procedures, oversight
- `governance` - Board, committees, accountability
- `audit_compliance` - Audits, inspections, reviews
- `record_keeping` - Documentation, retention
- `disclosure` - Transparency, reporting to customers
- `anti_money_laundering` - AML, CTF, suspicious activity
- `fraud_prevention` - Fraud detection, prevention
- `technology_security` - IT security, cyber
- `operational_procedures` - Day-to-day operations
- `training_awareness` - Staff training, awareness
- `third_party_management` - Vendors, outsourcing
- `incident_management` - Breach response, incidents
- `financial_limits` - Thresholds, limits
- `business_continuity` - BCP, disaster recovery
- `general` - Other/uncategorized

### 3. `key_obligations` (list of strings)
What specific actions/requirements are mandated?

Examples:
```json
[
  "Maintain transaction records for 5 years",
  "Report suspicious activity within 24 hours",
  "Conduct customer due diligence before onboarding"
]
```

### 4. `semantic_summary` (string)
Clear, concise interpretation of what the clause means.

Example:
> "This clause requires financial institutions to file Suspicious Transaction Reports (STRs) with FIU-IND within 7 days of detecting suspicious activity, including all supporting documentation."

## Supporting Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| `entities_involved` | list | Who is responsible (Bank, Compliance Officer, etc.) |
| `keywords` | list | Key terms for search/matching |
| `compliance_indicators` | list | What evidence shows compliance |
| `criticality` | string | Risk level: high, medium, low |

## Gap Analysis Matching Logic

### Step 1: Category Matching
```python
# Find candidate regulations with same subject category
candidates = [r for r in regulation_clauses 
              if r.subject_category == policy_clause.subject_category]
```

### Step 2: Keyword Overlap
```python
# If no exact category match, find by keyword similarity
policy_keywords = set(policy_clause.keywords)
for reg in regulation_clauses:
    overlap = policy_keywords & set(reg.keywords)
    if overlap:
        candidates.append(reg)
```

### Step 3: LLM Semantic Comparison
```python
# Use Claude to compare semantically and identify gaps
prompt = f"""
Compare this policy clause against the regulation requirement:

POLICY: {policy_clause.semantic_summary}
REGULATION: {regulation_clause.semantic_summary}

Policy Obligations: {policy_clause.key_obligations}
Regulation Obligations: {regulation_clause.key_obligations}

Identify: Is the policy compliant, partial, weak, missing, or conflicting?
"""
```

### Step 4: Gap Classification

| Gap Type | Description |
|----------|-------------|
| `compliant` | Policy fully meets regulation requirement |
| `partial` | Policy partially addresses requirement |
| `weak` | Policy addresses but is insufficient |
| `missing` | Policy doesn't address requirement at all |
| `conflicting` | Policy contradicts regulation |

## API Endpoints

### Upload Policy
```
POST /api/policies/upload
Content-Type: multipart/form-data

file: <PDF file>
policy_data: {"title": "AML Policy", "policy_type": "AML_CFT"}
```

Response includes enriched clauses with all semantic attributes.

### Upload Regulation
```
POST /api/regulations/upload
Content-Type: multipart/form-data

file: <PDF file>
regulation_data: {"title": "RBI Master Circular", "regulatory_body": "RBI"}
```

### Run Gap Analysis
```
POST /api/gap-analysis/run?policy_id=xxx&regulation_id=yyy
```

Response:
```json
{
  "compliance_score": 72.5,
  "total_gaps": 15,
  "critical_gaps": 2,
  "gaps": [
    {
      "gap_type": "partial",
      "severity": "High",
      "policy_clause": {
        "text": "The Bank shall conduct KYC...",
        "requirement_type": "mandatory",
        "subject_category": "customer_due_diligence",
        "key_obligations": ["Conduct KYC for all customers"],
        "semantic_summary": "Requires KYC for new customers"
      },
      "regulation_clause": {
        "text": "All REs shall conduct periodic KYC review...",
        "requirement_type": "mandatory",
        "subject_category": "customer_due_diligence",
        "key_obligations": ["Conduct periodic KYC review", "Update records every 2 years"],
        "semantic_summary": "Mandates periodic KYC updates every 2 years"
      },
      "description": "Policy covers initial KYC but lacks periodic review requirement",
      "suggested_fix": "Add clause requiring KYC review every 2 years"
    }
  ]
}
```

## Files Modified/Created

| File | Purpose |
|------|---------|
| `services/clause_extraction_service.py` | New LLM-powered extraction service |
| `models.py` | Enhanced Clause model with semantic attributes |
| `server.py` | Updated endpoints to use new extraction |

## LLM Usage

| Model | Use Case |
|-------|----------|
| **GPT-4o-mini** | Fast clause identification and splitting |
| **Claude Sonnet** | Deep semantic analysis and enrichment |
| **Claude Sonnet** | Gap analysis and matching |

## Next Steps for Fine-Tuning

1. **Add industry-specific categories**: Banking, Insurance, Payments, etc.
2. **Improve keyword extraction**: Use NLP for better term identification
3. **Add embedding-based matching**: Use vector similarity for better matching
4. **Custom requirement type detection**: Train on regulatory language patterns
5. **Multi-document comparison**: Compare policy against multiple regulations simultaneously
