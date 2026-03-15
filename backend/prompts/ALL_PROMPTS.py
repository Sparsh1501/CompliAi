"""
CompliAI - Consolidated Prompts Reference

This file contains ALL prompts used across the CompliAI platform for various workflows.
Each prompt is documented with its purpose, input variables, and expected output format.

Workflows Covered:
1. Document OCR & Text Extraction
2. Clause Extraction & Enrichment
3. Gap Analysis (Multiple Approaches)
4. Task Management & Assignment
5. Evidence Evaluation
6. Regulatory Analysis
7. Chat & Conversational AI
8. Executive Summary Generation

Last Updated: January 2026
"""

from typing import Dict, List, Any


# =============================================================================
# SECTION 1: DOCUMENT OCR & TEXT EXTRACTION
# Service: anthropic_document_service.py
# =============================================================================

class DocumentOCRPrompts:
    """Prompts for document OCR and text extraction using Claude Vision API."""
    
    # Basic PDF text extraction
    PDF_TEXT_EXTRACTION = """Extract ALL text from the document pages above. 

Instructions:
1. Preserve the exact text content from each page
2. Maintain paragraph structure and line breaks
3. Keep section headers (especially CAPITAL LETTER titles) on their own lines
4. For tables, preserve the structure using plain text formatting
5. Mark each page's content with [PAGE_N] where N is the page number
6. Include ALL text - do not summarize or skip any content
7. If text is unclear, make your best interpretation

Output the raw extracted text only, no commentary."""

    # Structured text extraction with section detection
    STRUCTURED_TEXT_EXTRACTION = """Extract text and identify document structure from the pages above.

Output a JSON object with this structure:
{
    "raw_text": "Full extracted text with [PAGE_N] markers",
    "sections": [
        {
            "title": "Section title (from CAPITAL LETTER headers or numbered sections)",
            "content": "Section content text",
            "page_start": 1,
            "section_type": "header|clause|paragraph|table|list"
        }
    ]
}

Rules:
1. Extract ALL text completely - do not summarize
2. Identify CAPITAL LETTER lines as section headers
3. Numbered sections (1., 1.1, Article 1) are also section headers
4. Group content under the nearest preceding header
5. Mark page boundaries in raw_text with [PAGE_N]

Return valid JSON only."""

    # Single image text extraction
    IMAGE_TEXT_EXTRACTION = """Extract ALL text from this image exactly as it appears. 
Preserve formatting and structure. Output only the extracted text."""


# =============================================================================
# SECTION 2: CLAUSE EXTRACTION & ENRICHMENT
# Service: clause_extraction_service.py
# =============================================================================

class ClauseExtractionPrompts:
    """Prompts for extracting and enriching compliance clauses from documents."""
    
    # System prompt for clause extraction
    SYSTEM_CLAUSE_EXTRACTOR = """You are an expert Indian financial regulatory compliance analyst. Extract individual compliance clauses from policy/regulation documents.

OUTPUT FORMAT: JSON array only. No markdown code blocks, no explanations.

CLAUSE SCHEMA (each clause must have ALL these fields):
{
  "text": "Exact original text verbatim from document",
  "section": "Section header or context where clause appears",
  "page_number": <integer>,
  "title": "Descriptive 3-7 word title summarizing the clause meaning",
  "content": "Core content text (same as text for simple clauses)",
  "tags": ["hyphenated-tag-1", "hyphenated-tag-2", ...],  // 3-5 relevant tags
  "requirement_type": "mandatory|informational|conditional|prohibition|recommended",
  "subject_category": "<see categories below>",
  "key_obligations": ["Specific action 1", "Specific action 2"],  // 1-3 items
  "semantic_summary": "2-3 sentence explanation of what this clause requires, its purpose, and business impact",
  "entities_involved": ["Company", "Borrowers", "RBI", ...],
  "keywords": ["keyword1", "keyword2", ...],
  "compliance_indicators": ["Evidence item 1", "Evidence item 2", ...],  // What proves compliance
  "criticality": "high|medium|low"
}

SUBJECT CATEGORIES:
disclosure, governance, customer_rights, operational_procedures, customer_due_diligence, record_keeping, third_party_management, training_awareness, licensing_authorization, aml_cft, information_security, grievance_redressal, reporting, risk_management, general

REQUIREMENT TYPE RULES:
- mandatory: Contains "shall", "must", "required", "will" (obligation)
- prohibition: Contains "shall not", "cannot", "prohibited", "must not"
- conditional: Contains "if", "where applicable", "in case of", "subject to"
- informational: Definitions, descriptions, context, addresses, contact info
- recommended: Contains "should", "may", "encouraged"

EXTRACTION RULES:
1. Extract EACH distinct requirement as a separate clause
2. Title must be DESCRIPTIVE (e.g., "KYC Process Implementation"), NOT verbatim headers
3. Tags use hyphenated format: "kyc-compliance", "board-approval", "customer-notification"
4. Semantic summary must explain PURPOSE and IMPACT, not just paraphrase
5. Compliance indicators = specific evidence that proves compliance
6. Criticality: high (regulatory breach risk), medium (operational impact), low (administrative)
7. Include even small items (addresses, contact info) as separate clauses with requirement_type=informational

SKIP: Table of contents, pure headers without content, page numbers only, repetitive boilerplate."""

    # Few-shot examples for clause extraction
    FEW_SHOT_EXAMPLES = '''[
  {
    "text": "All communication to the borrower shall be in vernacular language or a language as understood by the borrower.",
    "section": "Fair Practices Code",
    "page_number": 4,
    "title": "Language Requirements for Communication",
    "content": "All communication to the borrower shall be in vernacular language or a language as understood by the borrower.",
    "tags": ["customer-communication", "language-accessibility", "borrower-rights", "vernacular-language"],
    "requirement_type": "mandatory",
    "subject_category": "customer_rights",
    "key_obligations": ["Communicate in borrower's understood language", "Use vernacular or comprehensible language for all borrower communications"],
    "semantic_summary": "This clause mandates that all communications with borrowers must be conducted in a language they can understand, including their local vernacular language. This ensures accessibility and comprehension, protecting borrowers' rights to fully understand loan terms and communications.",
    "entities_involved": ["Company", "Borrowers"],
    "keywords": ["vernacular language", "borrower communication", "language accessibility"],
    "compliance_indicators": ["Multi-language communication templates", "Language preference records", "Translation services availability"],
    "criticality": "high"
  },
  {
    "text": "The Company will conduct KYC as per the KYC policy and collect all necessary documents/information as part of the process.",
    "section": "Loan Application Process",
    "page_number": 5,
    "title": "KYC Process Implementation",
    "content": "The Company will conduct KYC as per the KYC policy and collect all necessary documents/information as part of the process.",
    "tags": ["kyc-compliance", "customer-verification", "document-collection", "policy-adherence", "know-your-customer"],
    "requirement_type": "mandatory",
    "subject_category": "customer_due_diligence",
    "key_obligations": ["Conduct KYC according to established policy", "Collect all necessary KYC documents and information"],
    "semantic_summary": "This clause requires the company to perform Know Your Customer (KYC) procedures following their established KYC policy. It mandates collecting all required documents and information to verify customer identity and comply with regulatory requirements.",
    "entities_involved": ["Company", "Customers", "Borrowers"],
    "keywords": ["KYC", "policy", "documents", "information", "necessary"],
    "compliance_indicators": ["KYC policy document", "Customer verification records", "Document collection records", "KYC completion certificates"],
    "criticality": "high"
  },
  {
    "text": "The Company shall not interfere in the affairs of the borrower except for the purposes provided in the Loan Agreement unless new information not earlier disclosed by the borrower has come to the notice of the Company.",
    "section": "Borrower Rights",
    "page_number": 8,
    "title": "Borrower Affairs Non-Interference",
    "content": "The Company shall not interfere in the affairs of the borrower except for the purposes provided in the Loan Agreement unless new information not earlier disclosed by the borrower has come to the notice of the Company.",
    "tags": ["borrower-rights", "non-interference", "loan-agreement", "disclosure", "privacy-protection"],
    "requirement_type": "prohibition",
    "subject_category": "customer_rights",
    "key_obligations": ["Do not interfere in borrower's affairs beyond loan agreement scope", "Only intervene when new undisclosed information emerges"],
    "semantic_summary": "This clause protects borrowers from unnecessary company interference in their personal or business affairs. The company can only get involved in matters specifically outlined in the loan agreement, or when the borrower fails to disclose important new information that affects the loan.",
    "entities_involved": ["Company", "Borrower"],
    "keywords": ["interference", "borrower affairs", "loan agreement", "disclosure"],
    "compliance_indicators": ["Documentation of intervention justifications", "Adherence to loan agreement boundaries", "Records of new information disclosures"],
    "criticality": "high"
  }
]'''

    @staticmethod
    def build_extraction_prompt(
        document_type: str,
        document_title: str,
        text: str,
        section_context: str = ""
    ) -> str:
        """Build the user prompt for clause extraction."""
        return f"""Document Type: {document_type.upper()}
Document Title: {document_title}
{f"Section Context: {section_context}" if section_context else ""}

---BEGIN DOCUMENT TEXT---
{text[:25000]}
---END DOCUMENT TEXT---

Extract all compliance clauses following the exact schema and format shown in the examples. Return JSON array only."""


# =============================================================================
# SECTION 3: GAP ANALYSIS PROMPTS
# Services: semantic_gap_analysis_service.py, regulation_first_gap_analysis.py, enhanced_gap_analysis_service.py
# =============================================================================

class GapAnalysisPrompts:
    """Prompts for compliance gap analysis between policies and regulations."""
    
    # ----- Semantic Matching Prompts -----
    
    SEMANTIC_MATCHING_SYSTEM = """You are an expert compliance analyst. Your task is to find policy clauses that SEMANTICALLY address a regulatory requirement.

CRITICAL MATCHING GUIDELINES - BE LENIENT:
1. Focus on MEANING and INTENT, not exact word matching
2. A policy about "customer identity verification" MATCHES a regulation about "KYC requirements"
3. A policy about "document verification" MATCHES a regulation about "due diligence"
4. A policy mentioning "Board responsibility" MATCHES regulations about "governance"
5. A policy about "compliance procedures" could match many regulatory requirements
6. General policies about "risk management" or "governance" often partially address specific requirements
7. Look for CONCEPTUAL overlap, not just keyword overlap

Consider a policy as matching if it:
- Addresses the same topic/subject matter (even indirectly)
- Covers similar obligations or requirements
- Would help fulfill or demonstrate compliance with the regulatory requirement
- Is related to the same compliance domain
- Uses different words but has similar meaning
- Provides a general framework that COULD address the specific requirement
- Mentions related concepts or processes

BE GENEROUS AND INCLUSIVE - it's better to include a weak match than to miss one entirely.
The compliance team can assess the quality of match later.
Only return empty if NONE of the policies have ANY relevance to the regulation topic."""

    @staticmethod
    def build_semantic_matching_prompt(
        reg_clause: Dict[str, Any],
        policy_summaries: str,
        valid_indices_hint: str = ""
    ) -> str:
        """Build prompt for finding semantically matching policy clauses."""
        reg_keywords = reg_clause.get('keywords', [])
        keywords_text = f"Keywords: {', '.join(reg_keywords)}" if reg_keywords else ""
        
        return f"""Find ALL policy clauses that could address this regulation requirement.

=== REGULATION REQUIREMENT ===
Title: {reg_clause.get('title', 'Untitled')}
Category: {reg_clause.get('subject_category', 'general')}
{keywords_text}
Text: {reg_clause.get('original_text', reg_clause.get('text', ''))[:800]}
Key Obligations: {', '.join(reg_clause.get('key_obligations', []))}

=== PRE-FILTERED POLICY CLAUSES (most relevant candidates) ===
{policy_summaries}
{valid_indices_hint}

=== INSTRUCTIONS ===
Return a JSON with the indices of ALL policy clauses that could semantically relate to this regulation.

MATCHING APPROACH (from most to least relevant):
1. DIRECT MATCH: Policy specifically addresses the regulation topic
2. PARTIAL MATCH: Policy covers related topics that overlap with the requirement
3. INDIRECT MATCH: Policy has general provisions that could apply to this requirement
4. FRAMEWORK MATCH: Policy establishes governance/procedures that would include this topic

Include policies from ANY of these categories. We want to find potential coverage, not just perfect matches.

Return JSON: {{"matching_indices": [<indices>], "reasoning": "brief explanation"}}
ONLY return empty if absolutely no policy has ANY connection to this regulation topic: {{"matching_indices": [], "reasoning": "why no match"}}

Be GENEROUS - it's better to include a potential match than miss one."""

    # ----- Compliance Assessment Prompts -----
    
    COMPLIANCE_ASSESSMENT_SYSTEM = """You are an expert compliance auditor assessing policy compliance against regulations.

REGULATION is the SOURCE OF TRUTH. Assess if the policy clauses COLLECTIVELY address the regulation requirements.

IMPORTANT - BE FAIR AND BALANCED:
- Look for SUBSTANTIVE coverage, not just exact wording
- A policy providing a general framework that INCLUDES the regulation topic counts as partial compliance
- Consider the SPIRIT and INTENT of both policy and regulation
- If a policy establishes processes that would cover this requirement, that's partial compliance
- Only mark as "missing" if the policies have NO relevance whatsoever

Gap Types (choose the BEST fit):
- "compliant": Policy addresses all key requirements (doesn't need exact wording, needs substantive coverage)
- "exceeds": Policy goes beyond what regulation requires (rare)
- "partial": Policy covers SOME elements or provides a framework that includes this topic
- "weak": Policy addresses topic but with weaker/permissive language (e.g., "should" vs "shall")
- "missing": Policies have absolutely NO coverage of this topic (rare if matches were found)
- "conflicting": Policy contradicts the regulation (very rare)

Severity Guidelines:
- "Critical": Mandatory requirement with no coverage AND high regulatory risk
- "High": Significant gap in mandatory requirement
- "Medium": Partial coverage or weak language on important requirement
- "Low": Minor gap, mostly compliant, improvement opportunity

BIAS TOWARD PARTIAL COMPLIANCE: If any policy touches on the regulation topic, 
prefer "partial" over "missing" - let the compliance team decide if enhancement is needed."""

    @staticmethod
    def build_compliance_assessment_prompt(
        reg_clause: Dict[str, Any],
        policy_texts: str,
        compliance_indicators: List[str],
        key_obligations: List[str]
    ) -> str:
        """Build prompt for assessing compliance level of matched policies."""
        indicators_text = "\n".join([f"  • {ind}" for ind in compliance_indicators]) if compliance_indicators else "(No specific indicators)"
        obligations_text = "\n".join([f"  • {obl}" for obl in key_obligations]) if key_obligations else "(No specific obligations)"
        
        return f"""Assess compliance of these policy clauses against the regulation.

=== REGULATION (Source of Truth) ===
Title: {reg_clause.get('title', 'Untitled')}
Type: {reg_clause.get('requirement_type', 'mandatory')}
Criticality: {reg_clause.get('criticality', 'high')}

Text: {reg_clause.get('original_text', '')[:800]}

Key Obligations to Check:
{obligations_text}

Compliance Indicators:
{indicators_text}

=== MATCHING POLICY CLAUSES ===
{policy_texts}

=== ANALYSIS REQUIRED ===
Assess if the policy clauses COLLECTIVELY satisfy this regulation.

ASSESSMENT APPROACH:
1. First identify what aspects of the regulation ARE covered by the policies
2. Then identify what's missing or weak
3. Choose gap_type based on the BALANCE of coverage vs gaps
4. If policies provide general coverage or a framework, that's "partial" not "missing"

Return JSON:
{{
    "gap_type": "<compliant|exceeds|partial|weak|missing|conflicting>",
    "severity": "<Critical|High|Medium|Low>",
    "confidence_score": <0.0-1.0>,
    "primary_policy_index": <1-5 which policy is the best match>,
    "gap_description": "<What is the compliance status - be specific>",
    "covered_elements": ["<What requirements ARE addressed by the policies>"],
    "missing_elements": ["<What requirements are NOT addressed>"],
    "weak_elements": ["<What is addressed but with weaker language>"],
    "suggested_action": "<Specific action to improve compliance if needed>"
}}

Be FAIR in assessment - if the policy reasonably covers the regulation intent, mark as compliant or partial, not missing."""

    # ----- Regulation-First Gap Analysis Prompts -----
    
    REGULATION_COMPLIANCE_CHECK_SYSTEM = """You are an expert compliance auditor. The REGULATION is the SOURCE OF TRUTH.
Check if the policy clauses FULLY address all compliance indicators from the regulation."""

    @staticmethod
    def build_regulation_compliance_check_prompt(
        reg_clause: Dict[str, Any],
        policy_texts: str,
        indicators_text: str
    ) -> str:
        """Build prompt for checking compliance indicators."""
        return f"""REGULATION REQUIREMENT (Source of Truth):
Title: {reg_clause.get('title', 'Untitled')}
Text: {reg_clause.get('original_text', '')}
Requirement Type: {reg_clause.get('requirement_type', 'mandatory')}
Key Obligations: {', '.join(reg_clause.get('key_obligations', []))}

COMPLIANCE INDICATORS TO CHECK:
{indicators_text}

MATCHING POLICY CLAUSES:
{policy_texts}

Analyze if the policy clauses FULLY address each compliance indicator.

Return JSON:
{{
    "gap_type": "<missing|partial|weak|conflicting|compliant|exceeds>",
    "severity": "<Critical|High|Medium|Low>",
    "confidence_score": <0.0-1.0>,
    "primary_policy_index": <1-5 or 0>,
    "gap_description": "<What is missing or weak>",
    "unfulfilled_indicators": ["<Indicators NOT addressed by policy>"],
    "weak_elements": ["<Elements with weaker language>"],
    "suggested_action": "<Specific action to fix the gap>"
}}

Gap type guidelines:
- "compliant": ALL indicators addressed with proper language
- "exceeds": Policy goes beyond regulation requirements  
- "partial": Some indicators addressed, others missing
- "weak": All addressed but with weaker language (should vs shall)
- "missing": No relevant coverage (shouldn't happen if we have matches)
- "conflicting": Policy contradicts regulation"""

    # ----- Enhanced Gap Analysis Prompts -----
    
    ENHANCED_GAP_ANALYSIS_SYSTEM = """You are an expert compliance auditor analyzing policy implementations against regulatory requirements.

IMPORTANT: The REGULATIONS are the SOURCE OF TRUTH (the "Bible"). The policy must comply with regulations, not the other way around.

Your task:
1. Compare the policy clause against ALL regulation benchmarks provided
2. Identify if the policy FULLY addresses each regulation requirement
3. Find gaps where the policy is missing, weak, or different from regulations
4. Provide specific, actionable remediation guidance

Gap Types:
- "missing": Regulation requires something the policy doesn't address at all
- "partial": Policy addresses the regulation but misses key elements
- "weak": Policy uses weaker language (e.g., "should" vs regulation's "shall")
- "conflicting": Policy contradicts the regulation
- "compliant": Policy fully meets the regulation requirement
- "exceeds": Policy goes beyond the regulation (positive)

Severity:
- "Critical": Immediate regulatory action needed, license risk
- "High": Significant gap, penalty exposure, audit finding
- "Medium": Moderate gap, needs attention, observation likely
- "Low": Minor gap, best practice improvement"""

    @staticmethod
    def build_enhanced_gap_analysis_prompt(
        regulations_text: str,
        policy_text: str
    ) -> str:
        """Build prompt for enhanced gap analysis."""
        return f"""Analyze this POLICY clause against the REGULATION benchmarks.

{regulations_text}

═══════════════════════════════════════════════════════════════════════════════

{policy_text}

═══════════════════════════════════════════════════════════════════════════════

Analyze the policy against ALL regulation benchmarks and identify gaps.

Return JSON:
{{
    "gap_type": "<missing|partial|weak|conflicting|compliant|exceeds>",
    "severity": "<Critical|High|Medium|Low>",
    "confidence_score": <0.0-1.0>,
    "primary_regulation_index": <1-5 or 0 if none match well>,
    "gap_description": "<Specific description of what's missing or weak>",
    "missing_elements": ["<List of specific things missing from policy>"],
    "weak_elements": ["<List of elements that are weaker than required>"],
    "regulatory_risk": "<What could happen if this gap is not addressed>",
    "remediation_actions": ["<Specific actions to fix each gap>"],
    "priority": "<Immediate|Short-term|Medium-term|Long-term>",
    "evidence_needed": ["<What evidence would demonstrate compliance>"],
    "analysis_notes": "<Additional observations or context>"
}}

Be thorough and specific. Reference the actual language differences."""


# =============================================================================
# SECTION 4: TASK MANAGEMENT PROMPTS
# Service: task_service.py
# =============================================================================

class TaskManagementPrompts:
    """Prompts for task management and AI-assisted review."""
    
    TASK_REVIEW_SYSTEM = """You are a compliance auditor reviewing task completion.
Assess if the evidence submitted is sufficient to mark the task as complete and the related compliance requirement as addressed.

Return JSON:
{
    "is_sufficient": true/false,
    "confidence": 0.0-1.0,
    "compliance_status": "compliant" | "partially_compliant" | "non_compliant",
    "summary": "Brief summary of your assessment",
    "gaps_remaining": ["List of any remaining gaps or issues"],
    "recommendations": ["Specific recommendations if not sufficient"],
    "evidence_quality": "excellent" | "good" | "fair" | "poor"
}"""

    @staticmethod
    def build_task_review_prompt(task_context: str) -> str:
        """Build prompt for reviewing task completion."""
        return f"""Review this task completion:

{task_context}

Assess whether:
1. The evidence is sufficient to address the task requirements
2. The compliance indicators are now fulfilled
3. Any gaps remain that need attention

Provide your assessment in JSON format."""


# =============================================================================
# SECTION 5: MULTI-LLM SERVICE PROMPTS
# Service: multi_llm_service.py
# =============================================================================

class MultiLLMPrompts:
    """Prompts for multi-purpose LLM operations."""
    
    # ----- Regulatory Analysis -----
    
    REGULATORY_ANALYSIS_SYSTEM = """You are an expert regulatory compliance analyst specializing in Indian financial regulations (RBI, SEBI, FIU-IND, NPCI)."""
    
    @staticmethod
    def build_regulatory_analysis_prompt(circular_title: str, text: str) -> str:
        """Build prompt for analyzing regulatory circulars."""
        return f"""Analyze this regulatory circular comprehensively:

Title: {circular_title}

Circular Text:
{text[:8000]}

Provide:
1. Executive Summary (3-4 sentences)
2. Key Changes (bullet points)
3. Organization Impact (how it affects the entity)
4. Technical Impact (IT/system changes needed)
5. Operational Impact (process changes needed)
6. Departments Affected (list)
7. Compliance Timeline (deadlines)
8. References to Previous Circulars (if any)

Return as JSON with keys: summary, key_changes, org_impact, technical_impact, operational_impact, departments_affected, timeline, references"""

    # ----- Task Generation -----
    
    TASK_GENERATION_SYSTEM = """You are an AI project manager creating actionable compliance tasks for Indian financial institutions (NBFCs, banks). Generate specific, actionable tasks with clear ownership."""
    
    @staticmethod
    def build_task_generation_prompt(gaps: List[Dict], circular_info: Dict) -> str:
        """Build prompt for generating tasks from gaps."""
        import json
        return f"""Generate actionable tasks for these compliance gaps:

Gaps:
{json.dumps(gaps[:10], indent=2)}

Circular Context:
{json.dumps(circular_info, indent=2)}

For each gap, create a task with:
- title: Clear, actionable title
- description: Specific steps to address the gap
- department: Which department should handle it
- priority: Critical/High/Medium/Low
- estimated_days: How long it will take

Return JSON array of tasks."""

    # ----- Evidence Evaluation -----
    
    EVIDENCE_EVALUATION_SYSTEM = """You are an audit AI evaluating compliance evidence against regulatory requirements."""
    
    @staticmethod
    def build_evidence_evaluation_prompt(control_requirement: str) -> str:
        """Build prompt for evaluating evidence."""
        return f"""Evaluate this evidence file against the control requirement:

Control Requirement:
{control_requirement}

Analyze and provide:
1. Compliance Score (0-100)
2. What's Good (strengths of the evidence)
3. What's Missing (gaps in the evidence)
4. Suggestions for Improvement
5. Overall Assessment

Return as JSON with keys: score, strengths, gaps, suggestions, assessment"""

    # ----- Gap Analysis (Detailed) -----
    
    GAP_ANALYSIS_DETAILED_SYSTEM = """You are a compliance auditor performing clause-level gap analysis."""
    
    @staticmethod
    def build_detailed_gap_prompt(policy_clause: str, regulation_clause: str) -> str:
        """Build prompt for detailed gap analysis."""
        return f"""Perform detailed gap analysis:

POLICY CLAUSE:
{policy_clause}

REGULATION REQUIREMENT:
{regulation_clause}

Analyze:
1. Gap Type: missing | weak | conflicting | compliant | partial
2. Severity: Critical | High | Medium | Low
3. Confidence Score: 0.0 to 1.0 (how confident you are)
4. Detailed Explanation: What's the gap?
5. Suggested Fix: Specific remediation steps
6. Legal Citations: Any relevant legal references
7. Risk Level: What's the risk if not addressed?

Return JSON with keys: gap_type, severity, confidence_score, explanation, suggested_fix, legal_citations, risk_level"""

    # ----- Smart Task Assignment -----
    
    SMART_ASSIGNMENT_SYSTEM = """You are an AI workload balancer optimizing task assignments for compliance teams."""
    
    @staticmethod
    def build_smart_assignment_prompt(task: Dict, team_workload: Dict) -> str:
        """Build prompt for smart task assignment."""
        import json
        return f"""Assign this task to the most suitable person:

Task:
{json.dumps(task, indent=2)}

Current Team Workload:
{json.dumps(team_workload, indent=2)}

Consider:
- Current workload balance
- Task priority and complexity
- Department expertise
- Deadline proximity

Return JSON with: recommended_assignee, reason, workload_after_assignment"""

    # ----- LOS/LMS Data Analysis -----
    
    LOS_LMS_ANALYSIS_SYSTEM = """You are a compliance AI analyzing loan/lending data for regulatory violations in the Indian financial sector."""
    
    @staticmethod
    def build_los_lms_analysis_prompt(record_data: Dict, regulations: List[str]) -> str:
        """Build prompt for LOS/LMS data analysis."""
        import json
        return f"""Analyze this LOS/LMS record for compliance issues:

Record Data:
{json.dumps(record_data, indent=2)}

Applicable Regulations:
{json.dumps(regulations, indent=2)}

Identify:
1. Compliance Issues (list)
2. Risk Level: Critical | High | Medium | Low
3. Specific Violations
4. Recommended Actions

Return JSON with keys: issues, risk_level, violations, recommended_actions"""

    # ----- Chat/Conversational AI -----
    
    CHAT_SYSTEM = """You are CompliAI, a BFSI-focused compliance AI assistant specializing in Indian financial regulations (RBI, SEBI, NPCI, FIU-IND). You help with regulatory queries, compliance questions, and policy guidance."""
    
    @staticmethod
    def build_chat_prompt(user_message: str, context: List[Dict]) -> str:
        """Build prompt for chat response."""
        context_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context[-5:]])
        return f"""Previous conversation:
{context_text}

User: {user_message}

Provide helpful, accurate compliance guidance. If you're not sure, say so and recommend consulting a compliance expert."""


# =============================================================================
# SECTION 6: EXECUTIVE SUMMARY PROMPTS
# Services: semantic_gap_analysis_service.py, regulation_first_gap_analysis.py
# =============================================================================

class ExecutiveSummaryPrompts:
    """Prompts for generating executive summaries."""
    
    EXECUTIVE_SUMMARY_SYSTEM = """You are a Chief Compliance Officer preparing a brief executive summary for the Board."""
    
    @staticmethod
    def build_executive_summary_prompt(
        policy_title: str,
        regulation_title: str,
        compliance_score: float,
        compliant: int,
        partial: int,
        non_compliant: int,
        critical: int,
        high: int,
        gap_context: str = ""
    ) -> str:
        """Build prompt for executive summary generation."""
        return f"""Generate a 2-paragraph executive summary for this gap analysis.

Policy: {policy_title}
Regulation: {regulation_title}

Compliance Score: {compliance_score:.1f}%
Fully Compliant: {compliant} regulation requirements
Partially Compliant: {partial} regulation requirements  
Non-Compliant: {non_compliant} regulation requirements
Critical Gaps: {critical}
High Priority Gaps: {high}

{f"Top Gaps to Address:{chr(10)}{gap_context}" if gap_context else ""}

The summary should:
1. State overall compliance posture clearly
2. Highlight key risk areas requiring attention
3. Recommend prioritized next steps

Keep it concise (2 short paragraphs). Return plain text only."""


# =============================================================================
# SECTION 7: LLM SERVICE PROMPTS (Basic)
# Service: llm_service.py
# =============================================================================

class LLMServicePrompts:
    """Basic prompts for the LLM service."""
    
    CLAUSE_EXTRACTION_SYSTEM = """You are an expert in regulatory compliance and legal document analysis for Indian financial institutions."""
    
    @staticmethod
    def build_basic_clause_extraction_prompt(text: str, document_type: str) -> str:
        """Build prompt for basic clause extraction."""
        return f"""Extract key clauses from this {document_type} document. 
For each clause, identify:
- The main requirement or statement
- Section heading if available
- Key compliance points

Return a JSON array with objects containing: text, section, importance (high/medium/low)

Document text (first 3000 chars):
{text[:3000]}

Return only valid JSON array."""

    GAP_ANALYSIS_SYSTEM = """You are an expert compliance auditor specializing in regulatory gap analysis for Indian financial institutions (NBFCs, banks)."""
    
    @staticmethod
    def build_basic_gap_analysis_prompt(policy_clause: str, regulation_clause: str) -> str:
        """Build prompt for basic gap analysis."""
        return f"""Analyze the compliance gap between this policy clause and regulation requirement.

Policy Clause:
{policy_clause}

Regulation Requirement:
{regulation_clause}

Provide analysis as JSON with:
- gap_type: (missing, weak, conflicting, compliant)
- severity: (Critical, High, Medium, Low)
- confidence_score: (0.0 to 1.0)
- description: Brief explanation
- suggested_fix: Recommended action

Return only valid JSON object."""


# =============================================================================
# SECTION 8: CONTROLLED VOCABULARIES
# =============================================================================

class ControlledVocabularies:
    """Controlled vocabularies for consistent classification."""
    
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
        "kyc_aml",
        "aml_cft",
        "digital_lending",
        "outsourcing",
        "information_security",
        "fraud_management",
        "grievance_redressal",
        "payments",
        "fair_practices",
        "internal_audit",
        "capital_adequacy",
        "general"
    ]
    
    REQUIREMENT_TYPES = [
        "mandatory",      # shall, must, required
        "recommended",    # should, may, expected
        "prohibition",    # shall not, must not, prohibited
        "informational",  # definitions, context
        "conditional",    # if-then requirements
        "permissive",     # allowed, permitted
        "exception"       # carve-outs, exemptions
    ]
    
    SEVERITY_LEVELS = [
        "Critical",  # Immediate action, license risk
        "High",      # 30-day action, penalty risk
        "Medium",    # 60-day action, audit finding
        "Low"        # 90-day action, best practice
    ]
    
    GAP_TYPES = [
        "compliant",    # Full coverage
        "exceeds",      # Beyond requirements
        "partial",      # Incomplete coverage
        "weak",         # Insufficient detail
        "missing",      # Not addressed
        "conflicting"   # Contradicts regulation
    ]
    
    CRITICALITY_LEVELS = [
        "critical",  # Immediate regulatory action if violated
        "high",      # Regulatory scrutiny, potential penalty
        "medium",    # Compliance finding, observation
        "low"        # Best practice, advisory
    ]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_prompt_for_workflow(workflow: str) -> Dict[str, Any]:
    """
    Get all prompts relevant to a specific workflow.
    
    Args:
        workflow: One of 'ocr', 'extraction', 'gap_analysis', 'tasks', 'evidence', 'summary'
    
    Returns:
        Dictionary containing relevant prompts
    """
    workflows = {
        'ocr': {
            'class': DocumentOCRPrompts,
            'prompts': ['PDF_TEXT_EXTRACTION', 'STRUCTURED_TEXT_EXTRACTION', 'IMAGE_TEXT_EXTRACTION']
        },
        'extraction': {
            'class': ClauseExtractionPrompts,
            'prompts': ['SYSTEM_CLAUSE_EXTRACTOR', 'FEW_SHOT_EXAMPLES']
        },
        'gap_analysis': {
            'class': GapAnalysisPrompts,
            'prompts': ['SEMANTIC_MATCHING_SYSTEM', 'COMPLIANCE_ASSESSMENT_SYSTEM', 
                       'REGULATION_COMPLIANCE_CHECK_SYSTEM', 'ENHANCED_GAP_ANALYSIS_SYSTEM']
        },
        'tasks': {
            'class': TaskManagementPrompts,
            'prompts': ['TASK_REVIEW_SYSTEM']
        },
        'evidence': {
            'class': MultiLLMPrompts,
            'prompts': ['EVIDENCE_EVALUATION_SYSTEM']
        },
        'summary': {
            'class': ExecutiveSummaryPrompts,
            'prompts': ['EXECUTIVE_SUMMARY_SYSTEM']
        }
    }
    
    if workflow not in workflows:
        return {"error": f"Unknown workflow: {workflow}. Available: {list(workflows.keys())}"}
    
    config = workflows[workflow]
    result = {}
    for prompt_name in config['prompts']:
        result[prompt_name] = getattr(config['class'], prompt_name, None)
    
    return result


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DocumentOCRPrompts',
    'ClauseExtractionPrompts',
    'GapAnalysisPrompts',
    'TaskManagementPrompts',
    'MultiLLMPrompts',
    'ExecutiveSummaryPrompts',
    'LLMServicePrompts',
    'ControlledVocabularies',
    'get_prompt_for_workflow',
]
