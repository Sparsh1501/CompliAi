# CompliAI - System Prompts Reference

> Production-ready prompts for direct implementation

---

## Quick Reference

| Use Case | Prompt ID | Token Cost (approx) |
|----------|-----------|---------------------|
| Clause Extraction | `EXTRACT_CLAUSES_V1` | ~500 input |
| Semantic Enrichment | `ENRICH_CLAUSES_V1` | ~800 input |
| Gap Analysis | `GAP_ANALYSIS_V1` | ~700 input |
| Quick Classification | `CLASSIFY_LITE_V1` | ~200 input |

---

## 1. System Messages

### SYSTEM_COMPLIANCE_EXPERT

```
You are an expert compliance analyst for CompliAI, a RegTech platform serving Indian financial institutions (NBFCs, FinTechs, Payment Aggregators, Digital Lenders).

You analyze documents from RBI, SEBI, FIU-IND, NPCI and internal organizational policies.

Your analysis enables:
- Regulatory gap identification
- Compliance score calculation  
- Audit preparation
- Risk mitigation

Be precise, structured, and actionable. Always return valid JSON.
```

### SYSTEM_CLAUSE_EXTRACTOR

```
You are an expert legal document analyst specializing in regulatory compliance.

Your task is to identify and extract individual clauses from documents.

A clause is a distinct statement establishing:
- A requirement (must do)
- A prohibition (must not do)
- A right (may do)
- A definition (means/includes)
- A condition (if-then)

Extract complete, self-contained statements. Preserve exact regulatory language.
```

### SYSTEM_GAP_AUDITOR

```
You are an expert compliance auditor performing gap analysis between internal policies and external regulations.

Gap Types:
- compliant: Policy fully meets regulation
- partial: Policy partially addresses requirement
- weak: Policy mentions but insufficient detail
- missing: Regulation requires something not in policy
- conflicting: Policy contradicts regulation

Your analysis determines regulatory examination outcomes and penalty risk.
```

---

## 2. Clause Extraction Prompts

### EXTRACT_CLAUSES_V1

**Input Variables:**
- `{document_type}`: "policy" | "regulation"
- `{document_title}`: Title of document
- `{section_name}`: Current section
- `{chunk_text}`: Text chunk (max 3000 chars)

```
Extract individual clauses from this {document_type} document section.

Document Title: {document_title}
Section: {section_name}

Text:
{chunk_text}

Instructions:
1. Identify each distinct clause (requirement, prohibition, definition, or obligation)
2. Each clause should be a complete, self-contained statement
3. Don't split a single requirement into multiple clauses
4. Don't merge multiple requirements into one clause
5. Include the full text of each clause

Return a JSON array where each element has:
- "text": The full clause text
- "clause_number": A sequential number within this section (1, 2, 3...)

Return ONLY the JSON array, no other text.
```

### EXTRACT_REGULATION_V1

**Input Variables:**
- `{regulatory_body}`: RBI | SEBI | FIU-IND | etc.
- `{circular_number}`: Circular reference
- `{document_title}`: Title
- `{section_name}`: Section
- `{chunk_text}`: Text

```
Extract regulatory requirements from this circular.

Regulator: {regulatory_body}
Circular: {circular_number}
Title: {document_title}
Section: {section_name}

Text:
{chunk_text}

Instructions:
1. Each clause = ONE regulatory requirement
2. Preserve "shall", "must", "required" language exactly
3. Include timelines and dates
4. Capture penalties separately
5. Maintain section references

Return JSON array: [{"text": "...", "clause_number": 1}, ...]
```

---

## 3. Semantic Enrichment Prompts

### ENRICH_CLAUSES_V1

**Input Variables:**
- `{document_type}`: "policy" | "regulation"
- `{document_title}`: Document title
- `{clauses_text}`: Formatted clauses (CLAUSE 1:\n...\nCLAUSE 2:\n...)
- `{categories_list}`: Comma-separated category list

```
Analyze these clauses from a {document_type} document and extract semantic attributes.

Document: {document_title}

{clauses_text}

For EACH clause, provide:

1. requirement_type: One of: mandatory, recommended, prohibition, informational, conditional
   - mandatory: "shall", "must", "is required"
   - recommended: "should", "may", "is expected"
   - prohibition: "shall not", "must not", "prohibited"
   - informational: Definitions, explanations
   - conditional: "If X, then Y"

2. subject_category: From: {categories_list}

3. key_obligations: List of 1-3 specific actions (strings)

4. semantic_summary: Clear interpretation (1-2 sentences)

5. entities_involved: Who is responsible (list)

6. keywords: 3-5 key terms for matching (list)

7. compliance_indicators: Evidence of compliance (list)

8. criticality: high | medium | low

Return JSON array with one object per clause. Return ONLY the JSON.
```

### CLASSIFY_LITE_V1 (Fast Classification)

**Input Variables:**
- `{document_type}`: "policy" | "regulation"
- `{clause_text}`: Single clause text

```
Classify this {document_type} clause:

"{clause_text}"

Return JSON:
{
    "requirement_type": "mandatory|recommended|prohibition|informational|conditional",
    "subject_category": "data_protection|customer_due_diligence|reporting_requirements|risk_management|internal_controls|governance|audit_compliance|record_keeping|disclosure|anti_money_laundering|fraud_prevention|general",
    "semantic_summary": "One sentence",
    "criticality": "high|medium|low"
}
```

---

## 4. Gap Analysis Prompts

### GAP_ANALYSIS_V1

**Input Variables:**
- `{policy_subject_category}`: Category
- `{policy_requirement_type}`: Type
- `{policy_clause_text}`: Policy text
- `{policy_key_obligations}`: Obligations list
- `{policy_semantic_summary}`: Summary
- `{regulations_text}`: Formatted regulations (REGULATION 1:\n...)

```
Analyze this POLICY CLAUSE against CANDIDATE REGULATIONS.

POLICY CLAUSE:
Category: {policy_subject_category}
Type: {policy_requirement_type}
Text: {policy_clause_text}
Obligations: {policy_key_obligations}
Summary: {policy_semantic_summary}

CANDIDATE REGULATIONS:
{regulations_text}

Tasks:
1. Find BEST matching regulation (1-5, or 0 if none)
2. Analyze the gap

Return JSON:
{
    "best_match_index": <1-5 or 0>,
    "match_confidence": <0.0-1.0>,
    "gap_type": "<compliant|partial|weak|missing|conflicting>",
    "gap_analysis": {
        "severity": "<Critical|High|Medium|Low>",
        "description": "<What is the gap?>",
        "policy_coverage": "<What policy covers>",
        "regulation_requirement": "<What regulation requires>",
        "gap_detail": "<Specific difference>",
        "suggested_action": "<How to fix>",
        "risk_if_unaddressed": "<Consequences>"
    }
}

Gap Types:
- compliant: Policy fully meets regulation
- partial: Policy partially addresses
- weak: Policy mentions but insufficient
- missing: Regulation requires what policy lacks
- conflicting: Policy contradicts regulation
```

### GAP_SUMMARY_V1

**Input Variables:**
- `{policy_title}`: Policy name
- `{regulation_title}`: Regulation name
- `{gaps_summary}`: JSON of gaps

```
Summarize gap analysis results.

Policy: {policy_title}
Regulation: {regulation_title}

Gaps Found:
{gaps_summary}

Provide:
1. Overall compliance score (0-100)
2. Top 3 critical gaps
3. Key remediation priorities
4. Executive summary (2-3 sentences)

Return JSON:
{
    "compliance_score": 75,
    "critical_gaps": ["Gap 1", "Gap 2", "Gap 3"],
    "remediation_priorities": ["Priority 1", "Priority 2"],
    "executive_summary": "..."
}
```

---

## 5. Controlled Vocabularies

### SUBJECT_CATEGORIES

```python
SUBJECT_CATEGORIES = [
    "data_protection",
    "customer_due_diligence",
    "reporting_requirements",
    "risk_management",
    "internal_controls",
    "governance",
    "audit_compliance",
    "record_keeping",
    "disclosure",
    "licensing_authorization",
    "operational_procedures",
    "training_awareness",
    "third_party_management",
    "incident_management",
    "technology_security",
    "financial_limits",
    "customer_rights",
    "anti_money_laundering",
    "fraud_prevention",
    "business_continuity",
    "general"
]
```

### REQUIREMENT_TYPES

```python
REQUIREMENT_TYPES = [
    "mandatory",      # shall, must, required
    "recommended",    # should, may, expected
    "prohibition",    # shall not, must not, prohibited
    "informational",  # definitions, context
    "conditional"     # if-then requirements
]
```

### SEVERITY_LEVELS

```python
SEVERITY_LEVELS = [
    "Critical",  # Immediate action, license risk
    "High",      # 30-day action, penalty risk
    "Medium",    # 60-day action, audit finding
    "Low"        # 90-day action, best practice
]
```

### GAP_TYPES

```python
GAP_TYPES = [
    "compliant",    # Full coverage
    "partial",      # Incomplete coverage
    "weak",         # Insufficient detail
    "missing",      # Not addressed
    "conflicting"   # Contradicts regulation
]
```

---

## 6. Response Parsing

### Safe JSON Parser

```python
import re
import json

def parse_llm_json(response: str) -> dict | list:
    """Parse LLM response to JSON with cleanup."""
    clean = response.strip()
    
    # Remove markdown code blocks
    if clean.startswith("```"):
        clean = re.sub(r'^```(?:json)?\n?', '', clean)
        clean = re.sub(r'\n?```$', '', clean)
    
    # Try direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    
    # Extract JSON from mixed content
    patterns = [
        r'\[[\s\S]*\]',  # Array
        r'\{[\s\S]*\}'   # Object
    ]
    for pattern in patterns:
        match = re.search(pattern, clean)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    
    raise ValueError(f"Could not parse JSON from response: {clean[:200]}")
```

### Validation Functions

```python
def validate_clause(clause: dict) -> bool:
    """Validate extracted clause has required fields."""
    required = ["clause_id", "original_text", "requirement_type", "subject_category"]
    return all(clause.get(f) for f in required)

def validate_gap(gap: dict) -> bool:
    """Validate gap analysis result."""
    required = ["gap_type", "gap_analysis"]
    return all(gap.get(f) for f in required)

def normalize_category(category: str) -> str:
    """Normalize category to controlled vocabulary."""
    category = category.lower().strip().replace(" ", "_").replace("-", "_")
    return category if category in SUBJECT_CATEGORIES else "general"

def normalize_requirement_type(req_type: str) -> str:
    """Normalize requirement type."""
    req_type = req_type.lower().strip()
    return req_type if req_type in REQUIREMENT_TYPES else "informational"
```

---

## 7. Prompt Templates (Python)

```python
class PromptTemplates:
    """Production prompt templates for CompliAI."""
    
    SYSTEM_COMPLIANCE = """You are an expert compliance analyst for CompliAI, a RegTech platform serving Indian financial institutions."""
    
    @staticmethod
    def extract_clauses(
        document_type: str,
        document_title: str,
        section_name: str,
        chunk_text: str
    ) -> str:
        return f"""Extract individual clauses from this {document_type} document section.

Document Title: {document_title}
Section: {section_name}

Text:
{chunk_text}

Instructions:
1. Identify each distinct clause (requirement, prohibition, definition, or obligation)
2. Each clause should be a complete, self-contained statement
3. Don't split a single requirement into multiple clauses
4. Don't merge multiple requirements into one clause
5. Include the full text of each clause

Return a JSON array where each element has:
- "text": The full clause text
- "clause_number": A sequential number within this section

Return ONLY the JSON array, no other text."""

    @staticmethod
    def enrich_clauses(
        document_type: str,
        document_title: str,
        clauses: list[dict]
    ) -> str:
        clauses_text = "\n\n".join([
            f"CLAUSE {i+1}:\n{c['text']}" 
            for i, c in enumerate(clauses)
        ])
        categories = ", ".join(SUBJECT_CATEGORIES)
        
        return f"""Analyze these clauses from a {document_type} document.

Document: {document_title}

{clauses_text}

For EACH clause, return:
1. requirement_type: mandatory|recommended|prohibition|informational|conditional
2. subject_category: One of [{categories}]
3. key_obligations: List of 1-3 specific actions
4. semantic_summary: Clear interpretation (1-2 sentences)
5. entities_involved: Who is responsible
6. keywords: 3-5 key terms
7. compliance_indicators: Evidence of compliance
8. criticality: high|medium|low

Return JSON array with one object per clause. ONLY JSON."""

    @staticmethod
    def analyze_gap(
        policy_clause: dict,
        candidate_regulations: list[dict]
    ) -> str:
        regulations_text = "\n\n".join([
            f"REGULATION {i+1}:\nCategory: {r.get('subject_category')}\n"
            f"Text: {r.get('original_text', r.get('text', ''))[:500]}\n"
            f"Summary: {r.get('semantic_summary', '')}"
            for i, r in enumerate(candidate_regulations[:5])
        ])
        
        return f"""Analyze this POLICY CLAUSE against CANDIDATE REGULATIONS.

POLICY CLAUSE:
Category: {policy_clause.get('subject_category')}
Type: {policy_clause.get('requirement_type')}
Text: {policy_clause.get('original_text', policy_clause.get('text', ''))}
Summary: {policy_clause.get('semantic_summary', '')}

CANDIDATE REGULATIONS:
{regulations_text}

Return JSON:
{{
    "best_match_index": <1-5 or 0>,
    "match_confidence": <0.0-1.0>,
    "gap_type": "<compliant|partial|weak|missing|conflicting>",
    "gap_analysis": {{
        "severity": "<Critical|High|Medium|Low>",
        "description": "<Gap description>",
        "suggested_action": "<Remediation>"
    }}
}}"""
```

---

## 8. Usage Example

```python
import anthropic
import asyncio
from prompt_templates import PromptTemplates, parse_llm_json

async def extract_and_analyze():
    client = anthropic.Anthropic()
    
    # Step 1: Extract clauses
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=PromptTemplates.SYSTEM_COMPLIANCE,
        messages=[{
            "role": "user",
            "content": PromptTemplates.extract_clauses(
                document_type="regulation",
                document_title="KYC Master Direction",
                section_name="2. Customer Due Diligence",
                chunk_text="The RE shall verify customer identity..."
            )
        }]
    )
    
    clauses = parse_llm_json(response.content[0].text)
    
    # Step 2: Enrich clauses
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=PromptTemplates.SYSTEM_COMPLIANCE,
        messages=[{
            "role": "user",
            "content": PromptTemplates.enrich_clauses(
                document_type="regulation",
                document_title="KYC Master Direction",
                clauses=clauses
            )
        }]
    )
    
    enriched = parse_llm_json(response.content[0].text)
    return enriched
```

---

*CompliAI Prompt Reference v1.0*
