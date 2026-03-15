# Gap Analysis Architecture: Regulation as Source of Truth

## Overview

CompliAI's Gap Analysis system treats **REGULATIONS as the Source of Truth (Bible)**. This means:

1. **Regulations are immutable benchmarks** - they define what compliance looks like
2. **Policies are implementations** - they must align with regulation requirements
3. **Every policy clause is evaluated against ALL relevant regulation clauses**
4. **Gaps identify where policy implementation differs from regulation requirements**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         GAP ANALYSIS WORKFLOW                                   │
│                                                                                 │
│  ┌─────────────────┐     ┌─────────────────────────────────────────────────┐   │
│  │   REGULATIONS   │     │                   POLICIES                      │   │
│  │ (Source of Truth)│     │             (Implementations)                   │   │
│  │                 │     │                                                 │   │
│  │ • RBI KYC Master│     │ • Internal KYC Policy                          │   │
│  │ • PMLA Act      │     │ • AML Policy                                   │   │
│  │ • DL Norms 2.0  │     │ • Digital Lending Policy                       │   │
│  │ • DPDP Act      │     │ • Data Privacy Policy                          │   │
│  └────────┬────────┘     └─────────────────────┬───────────────────────────┘   │
│           │                                     │                               │
│           │         ┌──────────────────────────────────────┐                   │
│           └────────►│     ENHANCED GAP ANALYSIS SERVICE    │◄──────────────────┘
│                     │                                      │                    │
│                     │  1. Index regulations by category    │                    │
│                     │  2. For each policy clause:          │                    │
│                     │     → Find ALL relevant regulations  │                    │
│                     │     → Analyze compliance using LLM   │                    │
│                     │     → Identify gap type & severity   │                    │
│                     │  3. Track unaddressed regulations    │                    │
│                     │  4. Generate executive summary       │                    │
│                     └──────────────────────────────────────┘                    │
│                                      │                                          │
│                                      ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         GAP ANALYSIS REPORT                              │  │
│  │                                                                          │  │
│  │  Compliance Score: 67.3%                                                 │  │
│  │                                                                          │  │
│  │  Gap Summary:                                                            │  │
│  │  ├── Critical: 2 (Identity verification specifics missing)              │  │
│  │  ├── High: 5 (Weaker language, partial coverage)                        │  │
│  │  ├── Medium: 8 (Minor observations, best practices)                     │  │
│  │  └── Low: 3 (Documentation, formatting)                                 │  │
│  │                                                                          │  │
│  │  Unaddressed Regulations: 4 (No policy coverage found)                  │  │
│  │                                                                          │  │
│  │  Executive Summary: [For Board presentation]                            │  │
│  │  Priority Actions: [Top 5 actionable items]                             │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Gap Types

| Gap Type | Description | Example |
|----------|-------------|---------|
| `missing` | Regulation requires X, policy is silent | Regulation: "Bank SHALL verify using photo ID" → Policy: No mention of verification |
| `partial` | Policy addresses regulation but misses key elements | Regulation: "Verify using Aadhaar, PAN, Voter ID" → Policy: "Verify using ID documents" |
| `weak` | Policy uses weaker language | Regulation: "SHALL" → Policy: "should" or "may" |
| `conflicting` | Policy contradicts regulation | Regulation: "Within 7 days" → Policy: "Within 30 days" |
| `compliant` | Policy fully meets regulation | Perfect alignment |
| `exceeds` | Policy goes beyond regulation (positive) | Regulation: "Annual review" → Policy: "Quarterly review" |
| `not_applicable` | No corresponding regulation found | Internal policy not covered by regulation |

## Gap Severities

| Severity | Description | Action Timeline |
|----------|-------------|-----------------|
| `Critical` | License risk, immediate regulatory action | Immediate (24-48 hours) |
| `High` | Significant penalty exposure, audit finding | Short-term (1-2 weeks) |
| `Medium` | Moderate gap, observation likely | Medium-term (1-3 months) |
| `Low` | Minor gap, best practice improvement | Long-term (Quarterly planning) |

## Files Structure

```
backend/
├── config/
│   ├── __init__.py
│   └── compliance_context.py          # Domain knowledge, prompts, taxonomies
│
├── services/
│   ├── anthropic_document_service.py  # OCR using Claude Vision
│   ├── clause_extraction_service.py   # Clause extraction & enrichment
│   ├── enhanced_gap_analysis_service.py  # ⭐ NEW: Gap analysis engine
│   └── document_service.py            # Document handling
│
└── server.py                          # API endpoints
```

## API Endpoint

### POST `/api/gap-analysis/run`

**Request:**
```json
{
  "policy_id": "policy-uuid",
  "regulation_id": "regulation-uuid"
}
```

**Response:**
```json
{
  "message": "Enhanced gap analysis completed (Regulation as Source of Truth)",
  "result_id": "result-uuid",
  "compliance_score": 67.3,
  "total_policy_clauses": 45,
  "total_regulation_clauses": 62,
  "critical_gaps": 2,
  "high_gaps": 5,
  "medium_gaps": 8,
  "low_gaps": 3,
  "compliant_clauses": 27,
  "unaddressed_regulations": 4,
  "executive_summary": "The policy has been analyzed against...",
  "priority_actions": [
    "Update KYC verification clause to specify photo ID requirement",
    "Strengthen AML monitoring language from 'should' to 'shall'",
    "Add explicit reference to PMLA Section 12A requirements",
    "Include timeline specifications matching regulatory deadlines",
    "Add provisions for digital lending disclosure requirements"
  ],
  "gaps": [...],
  "enhanced_report": {...}
}
```

## Usage Example

```python
from services.enhanced_gap_analysis_service import run_enhanced_gap_analysis

# Policy and regulation clauses (from clause extraction)
policy_clauses = [...]
regulation_clauses = [...]

# Run enhanced gap analysis
report = await run_enhanced_gap_analysis(
    policy_clauses=policy_clauses,
    regulation_clauses=regulation_clauses,
    policy_id="policy-123",
    policy_title="Internal KYC Policy",
    regulation_id="reg-456",
    regulation_title="RBI KYC Master Direction 2016"
)

# Results
print(f"Compliance Score: {report.compliance_score}%")
print(f"Critical Gaps: {report.critical_gaps}")
print(f"Executive Summary: {report.executive_summary}")
```

## Key Classes

### `EnhancedGapAnalysisService`
Main service class that orchestrates gap analysis.

**Methods:**
- `analyze_policy_against_regulation()` - Main entry point
- `_index_regulations_by_category()` - Index regulations for efficient lookup
- `_analyze_policy_clause()` - Analyze single policy clause against regulations
- `_analyze_gap_with_llm()` - Use Claude for detailed gap analysis
- `_generate_executive_summary()` - Generate Board-ready summary

### `GapDetail`
Detailed gap analysis result for a policy clause.

**Fields:**
- `gap_type` - Type of gap (missing, weak, partial, etc.)
- `severity` - Critical, High, Medium, Low
- `confidence_score` - 0.0 to 1.0
- `policy_clause` - The policy clause being evaluated
- `regulation_benchmarks` - All relevant regulations
- `primary_regulation` - Best matching regulation
- `gap_description` - Specific description
- `missing_elements` - What's missing from policy
- `weak_elements` - What's weaker than required
- `remediation_actions` - How to fix
- `evidence_needed` - What demonstrates compliance

### `GapAnalysisReport`
Complete gap analysis report.

**Fields:**
- `compliance_score` - Overall score (0-100)
- `gaps` - List of GapDetail objects
- `unaddressed_regulations` - Regulations with no policy coverage
- `executive_summary` - Board-ready summary
- `priority_actions` - Top actionable items

## Integration with ComplianceContext

The Enhanced Gap Analysis Service uses the `ComplianceContext` from `config/compliance_context.py` for:

1. **Subject Categories** - 18 compliance domains (KYC, AML, Digital Lending, etc.)
2. **Requirement Types** - Mandatory, Prohibition, Conditional, etc.
3. **Criticality Levels** - High, Medium, Low
4. **Prompts** - Compliance-aware prompts for LLM
5. **Output Schemas** - Structured JSON output formats

## Future Enhancements

1. **Regulation-First Analysis** - Also iterate over regulations to find policy coverage gaps
2. **Historical Tracking** - Track compliance score trends over time
3. **Automated Remediation** - AI-suggested policy language fixes
4. **Multi-Regulation Analysis** - Analyze policy against multiple regulations simultaneously
5. **Evidence Linking** - Connect gaps to supporting evidence documents
