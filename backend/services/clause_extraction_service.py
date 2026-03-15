"""
Enhanced Clause Extraction Service

This service extracts clauses from Policy and Regulation documents using LLM-powered
analysis to create semantically rich clause objects optimized for gap analysis.

Uses the ComplianceContext from config/compliance_context.py for:
- Centralized prompt templates
- Domain taxonomies (subject categories, requirement types)
- Compliance-officer designed context

Each clause contains:
1. Title - Section title (detected from CAPITAL LETTERS / Block Letters)
2. Content - Plain text content of the clause
3. Tags - Relevant tags matching the clause content
4. Requirement Type - What kind of requirement (mandatory, recommended, prohibition, etc.)
5. Subject/Topic - What domain/area the clause covers
6. Key Obligations - Specific actions/controls required
7. Semantic Summary - Clear interpretation of what the clause means (from Anthropic LLM)

This enables accurate matching between Policy clauses (P1) and Regulation clauses (R1)
to identify compliance gaps.
"""

import anthropic
from anthropic import AsyncAnthropic
import os
import re
import uuid
import json
from json_repair import repair_json
from typing import List, Dict, Any, Optional, Tuple
import logging
import asyncio

# Import compliance context for prompts and taxonomies
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.compliance_context import (
    ComplianceContext,
    get_default_context,
    get_all_subject_categories,
    get_all_requirement_types,
    RequirementType,
    CriticalityLevel,
)

# Import local LLM provider
from services.llm_provider import get_llm_provider, is_using_local_llm

logger = logging.getLogger(__name__)


class EnhancedClause:
    """
    Enhanced clause structure optimized for gap analysis.
    
    Key Attributes for Display and Matching:
    - title: Section title (detected from CAPITAL LETTERS / Block Letters)
    - content: Plain text content of the clause
    - tags: List of relevant tags matching the clause content
    
    Analysis Attributes:
    - requirement_type: The nature of the requirement (mandatory/recommended/prohibition/informational)
    - subject_category: Domain area (e.g., data_protection, reporting, risk_management)
    - key_obligations: List of specific obligations/actions required
    - semantic_summary: Clear, concise interpretation of the clause (from Anthropic LLM)
    """
    
    def __init__(
        self,
        clause_id: str,
        original_text: str,
        document_type: str,  # 'policy' or 'regulation'
        document_id: str,
        section: str = "",
        page_number: int = 1
    ):
        self.clause_id = clause_id
        self.original_text = original_text
        self.document_type = document_type
        self.document_id = document_id
        self.section = section
        self.page_number = page_number
        
        # NEW: Structured clause attributes
        self.title: str = ""  # Section title (from CAPITAL LETTERS)
        self.content: str = ""  # Plain text content
        self.tags: List[str] = []  # Relevant tags
        
        # LLM-enriched attributes (populated by analyze_with_llm)
        self.requirement_type: str = ""  # mandatory, recommended, prohibition, informational
        self.subject_category: str = ""  # data_protection, reporting, risk_management, etc.
        self.key_obligations: List[str] = []  # List of specific obligations
        self.semantic_summary: str = ""  # Clear interpretation from Anthropic LLM
        self.entities_involved: List[str] = []  # Who is responsible
        self.keywords: List[str] = []  # For matching/search
        self.compliance_indicators: List[str] = []  # What demonstrates compliance
        self.criticality: str = "medium"  # high, medium, low
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "original_text": self.original_text,
            "document_type": self.document_type,
            "document_id": self.document_id,
            "section": self.section,
            "page_number": self.page_number,
            # NEW: Structured display attributes
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            # Core attributes for gap analysis
            "requirement_type": self.requirement_type,
            "subject_category": self.subject_category,
            "key_obligations": self.key_obligations,
            "semantic_summary": self.semantic_summary,
            # Supporting attributes
            "entities_involved": self.entities_involved,
            "keywords": self.keywords,
            "compliance_indicators": self.compliance_indicators,
            "criticality": self.criticality
        }


# ──────────────────────────────────────────────────────────────────
# Module-level JSON extraction helpers (used by both classes)
# ──────────────────────────────────────────────────────────────────

def _extract_json_from_llm_response(response: str) -> List[Dict[str, Any]]:
    """
    Robust multi-layer JSON extraction from LLM response.
    Handles: markdown code blocks, surrounding prose, malformed JSON,
    unescaped quotes, truncated output, control characters.
    """
    if not response or not response.strip():
        raise json.JSONDecodeError("Empty LLM response", "", 0)

    text = response.strip()

    # ---- Layer 1: Strip markdown code fences anywhere in the text ----
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    elif text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?\s*```\s*$', '', text)

    # ---- Layer 2: Extract the JSON array/object from surrounding prose ----
    first_bracket = text.find('[')
    first_brace = text.find('{')
    last_bracket = text.rfind(']')
    last_brace = text.rfind('}')

    # Prefer array, fall back to object
    if first_bracket != -1 and last_bracket > first_bracket:
        text = text[first_bracket:last_bracket + 1]
    elif first_bracket != -1:
        text = text[first_bracket:]  # truncated array
    elif first_brace != -1 and last_brace > first_brace:
        text = text[first_brace:last_brace + 1]

    # ---- Layer 3: Clean control characters that break JSON parsing ----
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # ---- Layer 4: Try direct parse first (fast path) ----
    try:
        result = json.loads(text)
        if isinstance(result, list):
            logger.info(f"  JSON parsed directly: {len(result)} items")
            return result
        return [result]
    except json.JSONDecodeError:
        pass

    # ---- Layer 5: Use json_repair library (handles unescaped quotes,
    #      missing commas, trailing commas, truncation, etc.) ----
    try:
        repaired = repair_json(text, return_objects=True)
        if isinstance(repaired, list) and len(repaired) > 0:
            logger.info(f"  JSON repaired via json_repair: {len(repaired)} items")
            return repaired
        elif isinstance(repaired, dict):
            logger.info(f"  JSON repaired via json_repair: 1 item (dict)")
            return [repaired]
    except Exception as e:
        logger.warning(f"  json_repair failed: {e}")

    # ---- Layer 6: Manual truncation repair (find last complete object) ----
    try:
        result = _repair_truncated_json(text)
        if result:
            return result
    except Exception:
        pass

    # ---- Layer 7: Last resort — try repair_json on the raw response ----
    try:
        repaired = repair_json(response.strip(), return_objects=True)
        if isinstance(repaired, list) and len(repaired) > 0:
            logger.info(f"  JSON repaired from raw response: {len(repaired)} items")
            return repaired
    except Exception:
        pass

    raise json.JSONDecodeError(
        f"All JSON extraction layers failed on {len(response)} char response",
        response[:200], 0
    )


def _repair_truncated_json(json_str: str) -> Optional[List[Dict[str, Any]]]:
    """
    Attempt to repair truncated JSON array from LLM output.
    Finds the last complete JSON object and closes the array.
    """
    try:
        last_complete = -1
        brace_count = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(json_str):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    last_complete = i

        if last_complete > 0:
            repaired = json_str[:last_complete + 1]
            repaired = repaired.rstrip().rstrip(',')
            if not repaired.endswith(']'):
                repaired += ']'
            if not repaired.lstrip().startswith('['):
                repaired = '[' + repaired

            try:
                result = json.loads(repaired)
            except json.JSONDecodeError:
                result = repair_json(repaired, return_objects=True)

            if isinstance(result, list) and len(result) > 0:
                logger.info(f"  Truncation repair successful: {len(result)} items recovered")
                return result
    except Exception as e:
        logger.warning(f"  Truncation repair failed: {e}")

    return None


class ClauseExtractionService:
    """
    LLM-powered clause extraction service for gap analysis.
    
    OPTIMIZED VERSION:
    - Uses Claude Sonnet 4.5 for high-quality results
    - Single LLM call for extraction + enrichment combined
    - Processes entire document at once (with batching for large docs)
    - Few-shot examples for consistent output format
    
    Uses ComplianceContext for centralized prompt management and domain knowledge.
    """
    
    # Using Sonnet 4 for fast, high-quality extraction
    EXTRACTION_MODEL = "claude-sonnet-4-20250514"
    
    def __init__(self, context: ComplianceContext = None):
        """
        Initialize the clause extraction service.
        
        Args:
            context: ComplianceContext instance. If None, uses default context.
        """
        # Use provided context or get default
        self.context = context or get_default_context()
        
        # Check if using local LLM
        self.use_local_llm = is_using_local_llm()
        if self.use_local_llm:
            logger.info("🚀 ClauseExtractionService: Using LOCAL LLM mode (Ollama)")
            self.local_provider = get_llm_provider()
        else:
            self.local_provider = None
        
        # Initialize API client
        self.api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key and not self.use_local_llm:
            logger.warning("ANTHROPIC_API_KEY not found and USE_LOCAL_LLM=false - LLM features disabled")

        # Temporarily unset proxy env vars to avoid SOCKS issues
        http_proxy_backup = os.environ.get('HTTP_PROXY')
        https_proxy_backup = os.environ.get('HTTPS_PROXY')
        all_proxy_backup = os.environ.get('ALL_PROXY')
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('ALL_PROXY', None)
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)
        os.environ.pop('all_proxy', None)

        try:
            self.client = anthropic.Anthropic(
                api_key=self.api_key
            ) if self.api_key else None
            self.async_client = AsyncAnthropic(
                api_key=self.api_key
            ) if self.api_key else None
        finally:
            if http_proxy_backup:
                os.environ['HTTP_PROXY'] = http_proxy_backup
            if https_proxy_backup:
                os.environ['HTTPS_PROXY'] = https_proxy_backup
            if all_proxy_backup:
                os.environ['ALL_PROXY'] = all_proxy_backup
        
        # Use Sonnet for extraction (quality results)
        self.extraction_model = self.EXTRACTION_MODEL
        self.model = self.context.model  # For gap analysis
        
        # Get categories from context
        self.SUBJECT_CATEGORIES = get_all_subject_categories()
        self.REQUIREMENT_TYPES = get_all_requirement_types()
    
    async def _call_claude(self, system_message: str, user_message: str, max_tokens: int = 4096, use_haiku: bool = True) -> str:
        """
        Async helper to call Claude API or local Ollama with native async.
        Uses AsyncAnthropic.messages.stream() for Claude — no sync wrappers, no thread pools.
        Uses local LLM provider if USE_LOCAL_LLM=true.
        """
        import time
        start_time = time.time()
        
        # Use local LLM if enabled
        if self.use_local_llm and self.local_provider:
            logger.info(f"[CLAUSE LLM - LOCAL] Calling Ollama | system={len(system_message)} chars | user={len(user_message)} chars | max_tokens={max_tokens}")
            try:
                response_text = await self.local_provider.generate(
                    system=system_message,
                    prompt=user_message,
                    max_tokens=max_tokens,
                    temperature=0.3  # Lower temp for structured extraction
                )
                elapsed_time = time.time() - start_time
                logger.info(f"[CLAUSE LLM - LOCAL] Done in {elapsed_time:.1f}s | $0.00 (local) | {len(response_text)} chars")
                return response_text
            except Exception as e:
                logger.error(f"Local LLM call failed: {e}")
                raise
        
        # Fallback to Claude
        if not self.async_client:
            raise ValueError("Anthropic client not initialized and USE_LOCAL_LLM=false")
        
        # Model selection - use Sonnet 4 (fast, cost-effective, high quality)
        SONNET_MODEL = "claude-sonnet-4-20250514"
        model = SONNET_MODEL
        
        logger.info(f"[CLAUSE LLM] Calling {model} | system={len(system_message)} chars | user={len(user_message)} chars | max_tokens={max_tokens}")
        
        response_text = ""
        input_tokens = 0
        output_tokens = 0
        
        async with self.async_client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_message,
            messages=[
                {"role": "user", "content": user_message}
            ]
        ) as stream:
            async for text in stream.text_stream:
                response_text += text
            final_message = await stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens
        
        elapsed_time = time.time() - start_time
        
        # Sonnet pricing
        input_cost = input_tokens * 0.003 / 1000
        output_cost = output_tokens * 0.015 / 1000
        total_cost = input_cost + output_cost
        
        logger.info(f"[CLAUSE LLM] Done in {elapsed_time:.1f}s | {input_tokens} in / {output_tokens} out | ${total_cost:.4f} | {len(response_text)} chars")
        
        return response_text
    
    async def extract_clauses_from_document(
        self,
        text: str,
        document_type: str,  # 'policy' or 'regulation'
        document_id: str,
        document_title: str = ""
    ) -> List[Dict[str, Any]]:
        """
        OPTIMIZED: Extract and enrich all clauses in a SINGLE LLM call.
        
        Uses Claude Haiku for cost efficiency (10x cheaper than Sonnet).
        Combines extraction + enrichment in one prompt to minimize API calls.
        
        Args:
            text: Full document text
            document_type: 'policy' or 'regulation'
            document_id: Unique identifier for the document
            document_title: Title of the document for context
            
        Returns:
            List of enriched clause dictionaries
        """
        import time
        start_time = time.time()
        
        logger.info(f"Starting OPTIMIZED clause extraction for {document_type}: {document_title}")
        logger.info(f"  Document length: {len(text)} chars")
        
        if not self.api_key:
            logger.warning("No API key - using fallback extraction")
            chunks = self._split_into_chunks(text)
            return self._fallback_clause_extraction_with_enrichment(chunks, document_type, document_id)
        
        # Use larger chunks to give the LLM more context per call → fewer, higher-quality clauses
        MAX_CHUNK_FOR_SINGLE_CALL = 25000
        
        if len(text) <= MAX_CHUNK_FOR_SINGLE_CALL:
            # Single LLM call for the entire document
            logger.info("  Using SINGLE LLM call for entire document")
            clauses = await self._extract_and_enrich_single_call(
                text, document_type, document_id, document_title
            )
        else:
            # Split into mega-chunks and process with minimal calls
            logger.info(f"  Document too large, splitting into mega-chunks")
            mega_chunks = self._split_into_mega_chunks(text, MAX_CHUNK_FOR_SINGLE_CALL)
            logger.info(f"  Processing {len(mega_chunks)} mega-chunks")
            
            clauses = []
            for i, chunk in enumerate(mega_chunks):
                logger.info(f"  Processing mega-chunk {i+1}/{len(mega_chunks)} ({len(chunk['text'])} chars)")
                chunk_clauses = await self._extract_and_enrich_single_call(
                    chunk['text'], document_type, document_id, document_title,
                    section_context=chunk.get('section', 'General')
                )
                clauses.extend(chunk_clauses)
        
        # Post-processing: quality filter and deduplication
        before_count = len(clauses)
        clauses = self._post_process_clauses(clauses, document_type)
        
        elapsed = time.time() - start_time
        logger.info(f"OPTIMIZED extraction complete: {len(clauses)} clauses (filtered from {before_count}) in {elapsed:.2f}s")
        
        return clauses
    
    def _post_process_clauses(self, clauses: List[Dict[str, Any]], document_type: str) -> List[Dict[str, Any]]:
        """
        Post-process extracted clauses:
        1. Remove junk/boilerplate clauses (addresses, page numbers, etc.)
        2. Deduplicate near-identical clauses
        3. Enforce minimum quality (tags, keywords, semantic_summary must exist)
        """
        if not clauses:
            return clauses
        
        filtered = []
        seen_texts = set()
        
        for clause in clauses:
            text = (clause.get('original_text') or clause.get('text') or '').strip()
            
            # Skip very short clauses (likely headers or fragments)
            if len(text) < 30:
                continue
            
            # Skip pure boilerplate patterns
            text_lower = text.lower()
            boilerplate_patterns = [
                'registered address', 'corporate office', 'cin:', 'cin :', 
                'page ', 'table of contents', 'index', 'annexure',
                'version history', 'document control', 'confidential',
                'all rights reserved', 'copyright', 'disclaimer',
                'this document is proprietary', 'for internal use only'
            ]
            if any(text_lower.startswith(bp) for bp in boilerplate_patterns):
                continue
            if len(text) < 80 and any(bp in text_lower for bp in boilerplate_patterns):
                continue
            
            # Deduplicate: skip if we've seen very similar text
            # Use first 100 chars as fingerprint
            fingerprint = text[:100].lower().strip()
            if fingerprint in seen_texts:
                continue
            seen_texts.add(fingerprint)
            
            # Enforce quality: if tags/keywords are empty, generate basic ones
            if not clause.get('tags'):
                clause['tags'] = self._generate_basic_tags(text)
            if not clause.get('keywords'):
                clause['keywords'] = clause.get('tags', [])
            if not clause.get('semantic_summary') or clause['semantic_summary'] == text:
                # If semantic_summary is just a copy of text, create a minimal one
                clause['semantic_summary'] = text[:200] + ('...' if len(text) > 200 else '')
            if not clause.get('key_obligations'):
                clause['key_obligations'] = []
            
            filtered.append(clause)
        
        logger.info(f"  Post-processing: {len(clauses)} → {len(filtered)} clauses (removed {len(clauses) - len(filtered)} junk/duplicates)")
        return filtered
    
    # Few-shot examples for POLICY documents
    POLICY_FEW_SHOT_EXAMPLES = '''[
  {
    "text": "All communication to the borrower shall be in vernacular language or a language as understood by the borrower.",
    "section": "Fair Practices Code",
    "page_number": 4,
    "title": "Borrower Communication Language Policy",
    "content": "All communication to the borrower shall be in vernacular language or a language as understood by the borrower.",
    "tags": ["customer-communication", "language-accessibility", "borrower-rights", "vernacular-language"],
    "requirement_type": "mandatory",
    "subject_category": "fair_practices",
    "key_obligations": ["Communicate in borrower's understood language", "Use vernacular or comprehensible language for all borrower communications"],
    "semantic_summary": "The organization's policy mandates that all borrower communications must be in a language the borrower understands, including local vernacular. This policy provision addresses regulatory requirements for language accessibility and customer protection in lending communications.",
    "entities_involved": ["Company", "Borrowers"],
    "keywords": ["vernacular language", "borrower communication", "language accessibility", "customer communication", "fair practices"],
    "compliance_indicators": ["Multi-language communication templates", "Language preference records", "Translation services availability"],
    "criticality": "high",
    "implementation_evidence": ["Multi-language communication templates maintained", "Borrower language preference captured at onboarding", "Dedicated translation support for regional languages"],
    "processes_described": ["Language preference capture during onboarding", "Template selection based on borrower language", "Communication quality review"],
    "regulatory_references": ["RBI Fair Practices Code", "Master Direction on Fair Lending Practices", "Customer protection guidelines"]
  },
  {
    "text": "The Company will conduct KYC as per the KYC policy and collect all necessary documents/information as part of the process.",
    "section": "Loan Application Process",
    "page_number": 5,
    "title": "KYC Verification and Document Collection",
    "content": "The Company will conduct KYC as per the KYC policy and collect all necessary documents/information as part of the process.",
    "tags": ["kyc-compliance", "customer-verification", "document-collection", "know-your-customer", "identity-verification"],
    "requirement_type": "mandatory",
    "subject_category": "kyc_cdd",
    "key_obligations": ["Conduct KYC according to established policy", "Collect all necessary KYC documents and information"],
    "semantic_summary": "The organization's policy requires performing KYC verification following internal KYC procedures. This covers customer identity verification and document collection, addressing regulatory requirements for customer due diligence and anti-money laundering compliance.",
    "entities_involved": ["Company", "Customers", "Borrowers"],
    "keywords": ["KYC", "know your customer", "identity verification", "document collection", "customer due diligence", "CDD"],
    "compliance_indicators": ["KYC policy document", "Customer verification records", "Document collection checklist", "KYC completion certificates"],
    "criticality": "high",
    "implementation_evidence": ["Dedicated KYC team operational", "Digital KYC platform deployed", "Standardized document collection checklist in use", "KYC completion tracked in core banking system"],
    "processes_described": ["Customer identity verification process", "Document collection and scanning", "KYC completion certification", "Periodic KYC refresh"],
    "regulatory_references": ["RBI KYC Master Direction 2016", "PML Act Section 11", "CDD requirements under AML guidelines"]
  },
  {
    "text": "The Company shall not interfere in the affairs of the borrower except for the purposes provided in the Loan Agreement unless new information not earlier disclosed by the borrower has come to the notice of the Company.",
    "section": "Borrower Rights",
    "page_number": 8,
    "title": "Borrower Privacy and Non-Interference",
    "content": "The Company shall not interfere in the affairs of the borrower except for the purposes provided in the Loan Agreement unless new information not earlier disclosed by the borrower has come to the notice of the Company.",
    "tags": ["borrower-rights", "non-interference", "loan-agreement", "disclosure", "privacy-protection", "customer-rights"],
    "requirement_type": "prohibition",
    "subject_category": "fair_practices",
    "key_obligations": ["Do not interfere in borrower's affairs beyond loan agreement scope", "Only intervene when new undisclosed information emerges"],
    "semantic_summary": "The organization's policy prohibits interference in borrower's personal/business affairs except as defined in the loan agreement. This addresses regulatory requirements for borrower privacy protection and fair lending practices.",
    "entities_involved": ["Company", "Borrower"],
    "keywords": ["non-interference", "borrower rights", "borrower affairs", "loan agreement", "privacy", "fair practices"],
    "compliance_indicators": ["Documentation of intervention justifications", "Adherence to loan agreement boundaries", "Records of new information disclosures"],
    "criticality": "high",
    "implementation_evidence": ["Loan agreement scope documented and communicated", "Intervention justification form mandated", "Compliance team reviews all interventions"],
    "processes_described": ["Intervention justification and approval process", "Loan agreement boundary enforcement", "New information disclosure handling"],
    "regulatory_references": ["RBI Fair Practices Code", "Borrower privacy rights under consumer protection"]
  }
]'''

    # Few-shot examples for REGULATION documents
    REGULATION_FEW_SHOT_EXAMPLES = '''[
  {
    "text": "Regulated Entities (REs) shall carry out Customer Due Diligence (CDD) at the time of commencement of an account-based relationship.",
    "section": "Customer Due Diligence",
    "page_number": 3,
    "title": "Mandatory CDD at Account Opening",
    "content": "Regulated Entities (REs) shall carry out Customer Due Diligence (CDD) at the time of commencement of an account-based relationship.",
    "tags": ["customer-due-diligence", "CDD", "account-opening", "kyc-compliance", "identity-verification"],
    "requirement_type": "mandatory",
    "subject_category": "kyc_cdd",
    "key_obligations": ["Perform CDD at account opening", "Verify customer identity before establishing relationship"],
    "semantic_summary": "This regulatory clause mandates that all Regulated Entities must perform Customer Due Diligence when opening new accounts. REs must verify customer identity and assess risk before commencing any account-based relationship. Non-compliance carries regulatory penalties.",
    "entities_involved": ["RBI", "Regulated Entities", "Customers"],
    "keywords": ["customer due diligence", "CDD", "account opening", "KYC", "identity verification", "know your customer"],
    "compliance_indicators": ["CDD process documentation", "Account opening verification records", "Customer risk assessment at onboarding"],
    "criticality": "high",
    "compliance_checklist": [
      {"item": "CDD policy/procedure document exists and is approved", "evidence_type": "document", "mandatory": true, "verification_method": "Review CDD policy document and Board approval records"},
      {"item": "Customer identity verification performed at account opening", "evidence_type": "process", "mandatory": true, "verification_method": "Sample audit of recent account openings for CDD completion"},
      {"item": "Risk assessment conducted for each new customer", "evidence_type": "record", "mandatory": true, "verification_method": "Review customer risk assessment forms in onboarding files"},
      {"item": "CDD completion records maintained", "evidence_type": "record", "mandatory": true, "verification_method": "Check CDD tracking system or register"}
    ]
  },
  {
    "text": "REs shall file Suspicious Transaction Reports (STRs) with the Financial Intelligence Unit - India (FIU-IND) within 7 days of detection of suspicious transactions.",
    "section": "Reporting Requirements",
    "page_number": 12,
    "title": "STR Filing Deadline with FIU-IND",
    "content": "REs shall file Suspicious Transaction Reports (STRs) with the Financial Intelligence Unit - India (FIU-IND) within 7 days of detection of suspicious transactions.",
    "tags": ["suspicious-transaction-reporting", "STR", "FIU-IND", "aml-compliance", "reporting-deadline"],
    "requirement_type": "mandatory",
    "subject_category": "aml_cft",
    "key_obligations": ["File STR with FIU-IND", "Submit within 7 days of detection", "Report all suspicious transactions"],
    "semantic_summary": "This regulatory requirement mandates filing Suspicious Transaction Reports with the Financial Intelligence Unit within 7 days of detecting suspicious activity. This is a critical AML/CFT compliance obligation with strict timelines. Failure to comply attracts regulatory action.",
    "entities_involved": ["RBI", "Regulated Entities", "FIU-IND"],
    "keywords": ["suspicious transaction report", "STR", "FIU-IND", "reporting", "anti-money laundering", "AML", "7 days"],
    "compliance_indicators": ["STR filing records", "Detection-to-filing timeline tracking", "FIU-IND acknowledgment receipts"],
    "criticality": "high",
    "compliance_checklist": [
      {"item": "STR policy and procedure document exists", "evidence_type": "document", "mandatory": true, "verification_method": "Review STR policy document"},
      {"item": "Suspicious transaction detection process operational", "evidence_type": "process", "mandatory": true, "verification_method": "Review transaction monitoring system and alert workflows"},
      {"item": "STR filed with FIU-IND within 7-day deadline", "evidence_type": "record", "mandatory": true, "verification_method": "Check STR filing log and compare detection date vs filing date"},
      {"item": "FIU-IND acknowledgment receipts maintained", "evidence_type": "record", "mandatory": true, "verification_method": "Verify FIU-IND acknowledgment records"},
      {"item": "Staff trained on suspicious transaction identification", "evidence_type": "training", "mandatory": true, "verification_method": "Review training records and attendance"}
    ]
  },
  {
    "text": "The Board of Directors shall be responsible for laying down policies with approval of the Board and to ensure adequate procedures and controls are in place for effective implementation of the requirements.",
    "section": "Governance Framework",
    "page_number": 2,
    "title": "Board Oversight and Policy Responsibility",
    "content": "The Board of Directors shall be responsible for laying down policies with approval of the Board and to ensure adequate procedures and controls are in place for effective implementation of the requirements.",
    "tags": ["board-responsibility", "governance", "policy-approval", "internal-controls", "regulatory-compliance"],
    "requirement_type": "mandatory",
    "subject_category": "governance",
    "key_obligations": ["Board must approve compliance policies", "Ensure adequate procedures and controls exist", "Board oversight of implementation"],
    "semantic_summary": "The regulator requires the Board of Directors to take direct responsibility for approving compliance policies and ensuring effective implementation through adequate procedures and controls. This establishes board-level accountability for regulatory compliance.",
    "entities_involved": ["RBI", "Board of Directors", "Regulated Entities"],
    "keywords": ["board of directors", "board approval", "governance", "policy approval", "internal controls", "oversight"],
    "compliance_indicators": ["Board-approved policy documents", "Board meeting minutes on compliance", "Control framework documentation", "Implementation review records"],
    "criticality": "high",
    "compliance_checklist": [
      {"item": "Board-approved compliance policies exist", "evidence_type": "document", "mandatory": true, "verification_method": "Review Board resolution and policy approval records"},
      {"item": "Board meeting minutes discuss compliance implementation", "evidence_type": "record", "mandatory": true, "verification_method": "Review Board/committee meeting minutes"},
      {"item": "Internal control framework documented", "evidence_type": "document", "mandatory": true, "verification_method": "Review control framework documentation"},
      {"item": "Periodic implementation review conducted", "evidence_type": "report", "mandatory": true, "verification_method": "Check implementation review reports and frequency"}
    ]
  }
]'''

    async def _extract_and_enrich_single_call(
        self,
        text: str,
        document_type: str,
        document_id: str,
        document_title: str,
        section_context: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Extract AND enrich clauses in a single LLM call using Opus 4.
        
        Uses document-type-specific prompts and few-shot examples for consistent,
        high-quality output optimized for gap analysis matching.
        """
        # Select appropriate few-shot examples based on document type
        few_shot_examples = self.REGULATION_FEW_SHOT_EXAMPLES if document_type == "regulation" else self.POLICY_FEW_SHOT_EXAMPLES
        
        # Document-type-specific extraction guidance
        if document_type == "regulation":
            doc_type_guidance = """
DOCUMENT TYPE: REGULATION (Regulatory Circular / RBI Master Direction / Guidelines)
This is an AUTHORITATIVE document from a regulatory body (e.g., RBI, SEBI, IRDAI).

EXTRACTION FOCUS FOR REGULATIONS:
- Extract EVERY distinct regulatory requirement, directive, or obligation
- Each "shall", "must", "required to" statement is typically a separate clause
- Capture the EXACT regulatory language - this is the SOURCE OF TRUTH for compliance
- semantic_summary MUST explain: What the regulator REQUIRES, WHO must comply, and CONSEQUENCES of non-compliance
- key_obligations MUST list specific actions that regulated entities must take
- keywords MUST include both regulatory terminology AND common business terms that a policy would use to address this requirement
  (e.g., for a regulation about "CDD", include keywords: "customer due diligence", "CDD", "KYC", "identity verification", "customer identification")
- criticality should be "high" for any mandatory requirement with penalties

CRITICAL — REGULATION-SPECIFIC EXTRACTION (NEW):
- compliance_checklist: For each clause, create a STRUCTURED CHECKLIST of specific evidence items needed to prove compliance.
  Each item should be an object with:
  - "item": The specific evidence or control needed (e.g., "KYC policy document approved by Board")
  - "evidence_type": One of: "document" (policy/procedure doc), "process" (an ongoing process), "record" (transaction/audit records), "control" (tech/manual control), "training" (staff training), "report" (periodic reports)
  - "mandatory": true/false — is this evidence absolutely required?
  - "verification_method": How would an auditor verify this? (e.g., "Review Board meeting minutes", "Check system logs", "Interview compliance officer")
  This checklist becomes the DEFINITIVE CHECKLIST against which a policy is evaluated for compliance.
  Be SPECIFIC and EXHAUSTIVE — every obligation in the clause should map to at least one checklist item.
- compliance_indicators: STILL include these as a simple string list (backward compatibility), but make them match the compliance_checklist items.

KEYWORD STRATEGY FOR REGULATIONS:
Include 5-8 keywords per clause covering:
1. Official regulatory terms (e.g., "STR", "CDD", "CTR", "FIU-IND")
2. Common business equivalents (e.g., "suspicious transaction", "customer verification")  
3. Related compliance domain terms (e.g., "anti-money laundering", "AML")
4. Process terms a policy might use (e.g., "reporting process", "filing procedure")
This ensures proper matching with policy clauses during gap analysis."""
        else:
            doc_type_guidance = """
DOCUMENT TYPE: POLICY (Internal Organization Policy / Standard Operating Procedure)
This is an INTERNAL document describing the organization's rules, procedures, and controls.

EXTRACTION FOCUS FOR POLICIES:
- Extract SUBSTANTIVE policy provisions — each clause should be a meaningful compliance requirement, control, or procedure
- GROUP related sentences into a SINGLE clause when they describe the same requirement (do NOT create one clause per sentence)
- Aim for 15-60 high-quality clauses per document, NOT hundreds of fragments
- Each clause should be a self-contained compliance provision that can be matched against a regulation
- semantic_summary MUST explain: What the organization DOES or COMMITS TO, and how it relates to regulatory compliance (NEVER just copy the text)
- key_obligations MUST list 1-3 specific actions the organization takes or requires
- tags MUST have 3-5 hyphenated tags (NEVER return empty tags)
- keywords MUST have 5-8 terms including regulatory terminology (NEVER return empty keywords)
- compliance_indicators MUST describe what evidence shows this policy is being followed
- Think about WHICH REGULATION this policy provision might address

CRITICAL — POLICY-SPECIFIC EXTRACTION (NEW):
- implementation_evidence: Extract WHAT THE POLICY ACTUALLY IMPLEMENTS. E.g., "Dedicated KYC team established", "Quarterly Board reviews conducted", "Automated screening system deployed"
  This field captures PROOF that the organization has implemented the stated requirement — not just stated intent.
  Look for: teams/roles established, processes/procedures described, tools/systems mentioned, frequencies/timelines committed, controls/checks in place.
- processes_described: List the specific PROCESSES or PROCEDURES mentioned. E.g., ["Customer identity verification", "Document collection and scanning", "Periodic KYC refresh"]
- regulatory_references: Infer WHICH REGULATION or REGULATORY REQUIREMENT this policy clause is likely trying to address.
  E.g., ["RBI KYC Master Direction", "CDD requirements", "Section 11 of PML Act"]
  This is CRITICAL for matching — even approximate references help gap analysis find correct regulation clauses.

CRITICAL QUALITY RULES:
- EVERY clause MUST have non-empty: tags, keywords, key_obligations, semantic_summary, compliance_indicators, implementation_evidence, processes_described
- semantic_summary must be YOUR ANALYSIS, not a copy of the text
- title must be DESCRIPTIVE ("KYC Process Implementation"), not a section header ("Section 4.1")
- implementation_evidence must describe WHAT IS ACTUALLY DONE (concrete actions/systems), not what SHOULD be done

DO NOT EXTRACT:
- Registered addresses, corporate office addresses, CIN numbers
- Table of contents, page numbers, document version history
- Pure headers/titles without substantive content
- Copyright notices, disclaimers, confidentiality notices
- Signatures, approval blocks, document control metadata
- Definitions that have no compliance obligation

KEYWORD STRATEGY FOR POLICIES:
Include 5-8 keywords per clause covering:
1. Policy-specific terms (e.g., "verification process", "document checklist")
2. Regulatory terms this policy addresses (e.g., "KYC", "CDD", "customer due diligence")  
3. Compliance domain terms (e.g., "anti-money laundering", "AML", "customer protection")
4. Action verbs and processes (e.g., "verify", "collect", "report", "monitor")
This ensures proper matching with regulation clauses during gap analysis."""

        # Optimized prompt with document-type-specific guidance
        # Build schema based on document type
        if document_type == "regulation":
            schema_extra_fields = """  "compliance_checklist": [
    {{"item": "Specific evidence needed", "evidence_type": "document|process|record|control|training|report", "mandatory": true, "verification_method": "How auditor verifies this"}}
  ],"""
        else:
            schema_extra_fields = """  "implementation_evidence": ["What the policy actually implements/proves - concrete actions, systems, teams"],
  "processes_described": ["Specific processes or procedures mentioned in this clause"],
  "regulatory_references": ["Which regulation/requirement this policy clause likely addresses"],"""

        system_prompt = f"""You are an expert Indian financial regulatory compliance analyst. Extract individual compliance clauses from {document_type} documents.

{doc_type_guidance}

OUTPUT FORMAT: JSON array only. No markdown code blocks, no explanations.

CLAUSE SCHEMA (each clause must have ALL these fields):
{{
  "text": "Exact original text verbatim from document",
  "section": "Section header or context where clause appears",
  "page_number": <integer>,
  "title": "Descriptive 3-7 word title summarizing the clause meaning",
  "content": "Core content text (same as text for simple clauses)",
  "tags": ["hyphenated-tag-1", "hyphenated-tag-2", ...],  // 3-5 relevant tags
  "requirement_type": "mandatory|informational|conditional|prohibition|recommended",
  "subject_category": "<see categories below>",
  "key_obligations": ["Specific action 1", "Specific action 2"],  // 1-3 items
  "semantic_summary": "2-3 sentence explanation of what this clause requires/provides, its purpose, and how it relates to compliance",
  "entities_involved": ["Company", "Borrowers", "RBI", ...],
  "keywords": ["keyword1", "keyword2", ...],  // 5-8 keywords INCLUDING cross-reference terms
  "compliance_indicators": ["Evidence item 1", "Evidence item 2", ...],  // What proves compliance
  "criticality": "high|medium|low",
{schema_extra_fields}
}}

SUBJECT CATEGORIES (use EXACTLY one of these - consistency is critical for gap analysis matching):
kyc_cdd, aml_cft, data_protection, digital_lending, outsourcing, information_security, fraud_management, grievance_redressal, governance, reporting, record_keeping, capital_adequacy, payments, licensing, fair_practices, business_continuity, internal_audit, general

REQUIREMENT TYPE RULES:
- mandatory: Contains "shall", "must", "required", "will" (obligation)
- prohibition: Contains "shall not", "cannot", "prohibited", "must not"
- conditional: Contains "if", "where applicable", "in case of", "subject to"
- informational: Definitions, descriptions, context, addresses, contact info
- recommended: Contains "should", "may", "encouraged"

EXTRACTION RULES:
1. Extract each SUBSTANTIVE requirement/provision as a separate clause — group related sentences together
2. For POLICIES: aim for 15-60 high-quality clauses, NOT hundreds of fragments
3. Title must be DESCRIPTIVE (e.g., "KYC Process Implementation"), NOT verbatim headers
4. Tags use hyphenated format: "kyc-compliance", "board-approval" — NEVER return empty tags []
5. Semantic summary must explain PURPOSE and COMPLIANCE RELEVANCE — NEVER just copy the text
6. Compliance indicators = specific evidence that proves compliance — NEVER return empty []
7. Criticality: high (regulatory breach risk), medium (operational impact), low (administrative)
8. KEYWORDS ARE CRITICAL: Include 5-8 domain-specific AND cross-referencing terms — NEVER return empty []
9. key_obligations MUST list 1-3 specific actions — NEVER return empty []

SKIP ENTIRELY: Table of contents, pure headers, page numbers, registered addresses, CIN numbers,
version history, copyright notices, signatures, approval blocks, confidentiality notices, document control metadata.

FEW-SHOT EXAMPLES:
{few_shot_examples}"""

        user_prompt = f"""Document Type: {document_type.upper()}
Document Title: {document_title}
{f"Section Context: {section_context}" if section_context else ""}

---BEGIN DOCUMENT TEXT---
{text[:25000]}
---END DOCUMENT TEXT---

Extract all SUBSTANTIVE compliance clauses following the exact schema and format shown in the examples.
For each clause, ALL fields must be non-empty (especially tags, keywords, key_obligations, semantic_summary, compliance_indicators).
Return JSON array only — no markdown, no explanations."""

        try:
            response = await self._call_claude(
                system_prompt,
                user_prompt,
                max_tokens=16384,  # Large enough for detailed clause extraction from big documents
                use_haiku=False  # Use Sonnet 4.5 for quality
            )
            
            # Parse response with robust multi-layer JSON handling
            clauses_data = _extract_json_from_llm_response(response)
            
            if not isinstance(clauses_data, list):
                clauses_data = [clauses_data]
            
            # Add document metadata to each clause - matching reference format exactly
            enriched = []
            for i, clause in enumerate(clauses_data):
                # Get the original text, preferring 'text' field over 'content'
                original_text = clause.get('text', clause.get('content', ''))
                
                enriched_clause = {
                    "clause_id": str(uuid.uuid4()),
                    "text": original_text,  # Exact verbatim text
                    "original_text": original_text,
                    "document_type": document_type,
                    "document_id": document_id,
                    "section": clause.get('section', section_context or 'General'),
                    "page_number": clause.get('page_number', 1),
                    "reference_circulars": [],
                    "metadata": None,
                    # Structured display attributes
                    "title": clause.get('title', f'Clause {i+1}'),
                    "content": clause.get('content', original_text),
                    "tags": clause.get('tags', [])[:7],
                    # Core attributes for gap analysis
                    "requirement_type": clause.get('requirement_type', 'informational'),
                    "subject_category": clause.get('subject_category', 'general'),
                    "key_obligations": clause.get('key_obligations', [])[:5],
                    "semantic_summary": clause.get('semantic_summary', original_text[:200] if original_text else ''),
                    # Supporting attributes
                    "entities_involved": clause.get('entities_involved', []),
                    "keywords": clause.get('keywords', clause.get('tags', [])),
                    "compliance_indicators": clause.get('compliance_indicators', []),
                    "criticality": clause.get('criticality', 'medium')
                }
                
                # Add document-type-specific fields
                if document_type == "regulation":
                    enriched_clause["compliance_checklist"] = clause.get('compliance_checklist', [])
                else:
                    # Policy-specific fields
                    enriched_clause["implementation_evidence"] = clause.get('implementation_evidence', [])
                    enriched_clause["processes_described"] = clause.get('processes_described', [])
                    enriched_clause["regulatory_references"] = clause.get('regulatory_references', [])
                
                enriched.append(enriched_clause)
            
            return enriched
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Fallback to basic extraction
            chunks = self._split_into_chunks(text)
            return self._fallback_clause_extraction_with_enrichment(chunks, document_type, document_id)
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            chunks = self._split_into_chunks(text)
            return self._fallback_clause_extraction_with_enrichment(chunks, document_type, document_id)
    
    def _split_into_mega_chunks(self, text: str, max_size: int = 15000) -> List[Dict[str, Any]]:
        """Split document into large chunks for minimal LLM calls."""
        chunks = []
        current_section = "General"
        
        # Split by page markers first
        pages = re.split(r'\[PAGE_\d+\]', text)
        
        current_chunk = ""
        for page in pages:
            page = page.strip()
            if not page:
                continue
            
            # Check for section headers
            section_match = self._detect_section_header(page[:200])
            if section_match:
                current_section = section_match
            
            if len(current_chunk) + len(page) > max_size:
                if current_chunk:
                    chunks.append({"text": current_chunk, "section": current_section})
                current_chunk = page
            else:
                current_chunk += "\n\n" + page
        
        if current_chunk:
            chunks.append({"text": current_chunk, "section": current_section})
        
        return chunks if chunks else [{"text": text, "section": "General"}]
    
    def _fallback_clause_extraction_with_enrichment(
        self,
        chunks: List[Dict[str, Any]],
        document_type: str,
        document_id: str
    ) -> List[Dict[str, Any]]:
        """Fallback extraction with basic enrichment when LLM is unavailable."""
        clauses = []
        for chunk in chunks:
            text = chunk.get('text', '')
            section = chunk.get('section', 'General')
            
            # Split into paragraphs
            paragraphs = re.split(r'\n\s*\n', text)
            
            for para in paragraphs:
                para = para.strip()
                if len(para) < 50:
                    continue
                
                title = self._extract_title_from_text(para) or section
                tags = self._generate_basic_tags(para)
                
                clauses.append({
                    "clause_id": str(uuid.uuid4()),
                    "original_text": para,
                    "document_type": document_type,
                    "document_id": document_id,
                    "section": section,
                    "page_number": chunk.get('page', 1),
                    "title": title,
                    "content": para,
                    "tags": tags,
                    "requirement_type": self._infer_requirement_type(para),
                    "subject_category": "general",
                    "key_obligations": [],
                    "semantic_summary": para[:200],
                    "entities_involved": [],
                    "keywords": tags,
                    "compliance_indicators": [],
                    "criticality": "medium"
                })
        
        return clauses
    
    def _split_into_chunks(self, text: str, max_chunk_size: int = 3000) -> List[Dict[str, Any]]:
        """
        Split document into logical chunks for processing.
        Preserves section information and page numbers.
        """
        # Clean text
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        chunks = []
        current_section = "Introduction"
        current_page = 1
        
        # Split by double newlines (paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = []
        current_chunk_size = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check for page markers
            page_match = re.search(r'\[PAGE_(\d+)\]', para)
            if page_match:
                current_page = int(page_match.group(1))
                para = re.sub(r'\[PAGE_\d+\]', '', para).strip()
            
            # Check for section headers
            section_match = self._detect_section_header(para)
            if section_match:
                # Save current chunk before starting new section
                if current_chunk:
                    chunks.append({
                        "text": "\n\n".join(current_chunk),
                        "section": current_section,
                        "page": current_page
                    })
                    current_chunk = []
                    current_chunk_size = 0
                
                current_section = section_match
            
            # Add paragraph to current chunk
            if current_chunk_size + len(para) > max_chunk_size and current_chunk:
                chunks.append({
                    "text": "\n\n".join(current_chunk),
                    "section": current_section,
                    "page": current_page
                })
                current_chunk = [para]
                current_chunk_size = len(para)
            else:
                current_chunk.append(para)
                current_chunk_size += len(para)
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append({
                "text": "\n\n".join(current_chunk),
                "section": current_section,
                "page": current_page
            })
        
        return chunks
    
    def _detect_section_header(self, text: str) -> Optional[str]:
        """Detect if text is a section header and return the section name."""
        text = text.strip()
        if len(text) > 200:
            return None
        
        # Numbered sections
        match = re.match(r'^(\d+(?:\.\d+)*)\s*[.:\-]?\s+(.+)', text)
        if match:
            return f"{match.group(1)} {match.group(2)}"
        
        # Article/Section/Clause headers
        match = re.match(r'^(Article|Section|Clause|Part|Chapter)\s+(\d+(?:\.\d+)*)[:\-]?\s*(.*)', text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} {match.group(2)}: {match.group(3)}".strip()
        
        # All caps headers
        if text.isupper() and 3 < len(text) < 100:
            return text
        
        return None
    
    async def _extract_clauses_with_llm(
        self,
        chunks: List[Dict[str, Any]],
        document_type: str,
        document_title: str
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to extract individual clauses from document chunks.
        """
        if not self.api_key:
            logger.warning("No API key - using fallback extraction")
            return self._fallback_clause_extraction(chunks)
        
        all_clauses = []
        
        # Process chunks in batches to avoid rate limits
        batch_size = 3
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_results = await asyncio.gather(*[
                self._extract_clauses_from_chunk(chunk, document_type, document_title)
                for chunk in batch
            ])
            for result in batch_results:
                all_clauses.extend(result)
        
        return all_clauses
    
    async def _extract_clauses_from_chunk(
        self,
        chunk: Dict[str, Any],
        document_type: str,
        document_title: str
    ) -> List[Dict[str, Any]]:
        """Extract clauses from a single chunk using Claude with context-based prompts."""
        try:
            # Build prompt using compliance context
            user_prompt = self.context.build_extraction_prompt(
                chunk_text=chunk['text'],
                document_type=document_type,
                document_title=document_title,
                section_name=chunk.get('section', 'General'),
                page_number=chunk.get('page', 1)
            )
            
            # Get system prompt from context
            system_prompt = self.context.get_system_prompt("clause_extraction")

            response = await self._call_claude(
                system_message=system_prompt,
                user_message=user_prompt
            )
            
            # Parse response with robust JSON handling
            try:
                clauses = _extract_json_from_llm_response(response)
                
                # Add section and page info
                for clause in clauses:
                    clause['section'] = chunk['section']
                    clause['page'] = chunk['page']
                
                return clauses if isinstance(clauses, list) else []
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response: {e}")
                return self._fallback_chunk_extraction(chunk)
                
        except Exception as e:
            logger.error(f"LLM clause extraction error: {e}")
            return self._fallback_chunk_extraction(chunk)
    
    async def _enrich_clauses_batch(
        self,
        raw_clauses: List[Dict[str, Any]],
        document_type: str,
        document_id: str,
        document_title: str
    ) -> List[Dict[str, Any]]:
        """
        Enrich all clauses with semantic attributes using LLM.
        Processes in batches for efficiency.
        """
        if not self.api_key:
            return [self._create_basic_clause(c, document_type, document_id) for c in raw_clauses]
        
        enriched = []
        batch_size = 5  # Process 5 clauses at a time
        
        for i in range(0, len(raw_clauses), batch_size):
            batch = raw_clauses[i:i + batch_size]
            batch_results = await self._enrich_clause_batch(
                batch, document_type, document_id, document_title
            )
            enriched.extend(batch_results)
        
        return enriched
    
    async def _enrich_clause_batch(
        self,
        clauses: List[Dict[str, Any]],
        document_type: str,
        document_id: str,
        document_title: str
    ) -> List[Dict[str, Any]]:
        """Enrich a batch of clauses with semantic attributes using Anthropic Claude."""
        try:
            clauses_text = "\n\n".join([
                f"CLAUSE {i+1}:\n{c['text']}" 
                for i, c in enumerate(clauses)
            ])
            
            # Build enrichment prompt using compliance context
            user_prompt = self.context.build_enrichment_prompt(
                clauses_text=clauses_text,
                document_type=document_type,
                document_title=document_title,
                issuer="Regulatory Authority" if document_type == "regulation" else "Organization",
                document_context=f"Extracting compliance clauses from {document_type} for gap analysis"
            )
            
            # Get system prompt from context
            system_prompt = self.context.get_system_prompt("semantic_enrichment")
            
            response = await self._call_claude(
                system_prompt,
                user_prompt,
                max_tokens=self.context.max_tokens
            )
            
            # Parse response with robust JSON handling
            try:
                enrichments = _extract_json_from_llm_response(response)
                
                if not isinstance(enrichments, list):
                    raise ValueError("Response is not a list")
                
                # Merge enrichments with original clauses
                enriched_clauses = []
                for i, clause in enumerate(clauses):
                    enrichment = enrichments[i] if i < len(enrichments) else {}
                    enriched_clauses.append(self._merge_clause_data(
                        clause, enrichment, document_type, document_id
                    ))
                
                return enriched_clauses
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse enrichment response: {e}")
                return [self._create_basic_clause(c, document_type, document_id) for c in clauses]
                
        except Exception as e:
            logger.error(f"Clause enrichment error: {e}")
            return [self._create_basic_clause(c, document_type, document_id) for c in clauses]
    
    def _merge_clause_data(
        self,
        clause: Dict[str, Any],
        enrichment: Dict[str, Any],
        document_type: str,
        document_id: str
    ) -> Dict[str, Any]:
        """Merge original clause data with LLM enrichment."""
        original_text = clause.get('text', '')
        
        # Get title from enrichment or extract from section
        title = enrichment.get('title', '')
        if not title:
            title = self._extract_title_from_text(original_text) or clause.get('section', 'General')
        
        # Get content from enrichment or use original text
        content = enrichment.get('content', original_text)
        
        # Get tags from enrichment or generate basic ones
        tags = enrichment.get('tags', [])
        if not tags:
            tags = self._generate_basic_tags(original_text)
        
        return {
            "clause_id": str(uuid.uuid4()),
            "original_text": original_text,
            "document_type": document_type,
            "document_id": document_id,
            "section": clause.get('section', 'General'),
            "page_number": clause.get('page', 1),
            # NEW: Structured display attributes
            "title": title,
            "content": content,
            "tags": tags,
            # Core attributes for gap analysis
            "requirement_type": enrichment.get('requirement_type', 'informational'),
            "subject_category": enrichment.get('subject_category', 'general'),
            "key_obligations": enrichment.get('key_obligations', []),
            "semantic_summary": enrichment.get('semantic_summary', original_text[:200]),
            # Supporting attributes
            "entities_involved": enrichment.get('entities_involved', []),
            "keywords": enrichment.get('keywords', []),
            "compliance_indicators": enrichment.get('compliance_indicators', []),
            "criticality": enrichment.get('criticality', 'medium')
        }
    
    def _extract_title_from_text(self, text: str) -> Optional[str]:
        """Extract title from text if it starts with CAPITAL LETTERS."""
        lines = text.strip().split('\n')
        if not lines:
            return None
        
        first_line = lines[0].strip()
        
        # Check if first line is in CAPITAL LETTERS (block letters)
        if first_line and len(first_line) < 150:
            letters_only = ''.join(c for c in first_line if c.isalpha())
            if letters_only:
                uppercase_count = sum(1 for c in letters_only if c.isupper())
                if uppercase_count / len(letters_only) >= 0.8:
                    return first_line
        
        # Check for numbered section headers
        match = re.match(r'^(\d+(?:\.\d+)*)\s*[.:\-]?\s+(.+)', first_line)
        if match:
            return f"{match.group(1)} {match.group(2)}"
        
        return None
    
    def _generate_basic_tags(self, text: str) -> List[str]:
        """Generate basic tags from text content."""
        tags = []
        text_lower = text.lower()
        
        # Compliance-related tags
        tag_patterns = {
            'mandatory': ['shall', 'must', 'required', 'mandatory'],
            'prohibition': ['prohibited', 'forbidden', 'not allowed', 'shall not'],
            'reporting': ['report', 'notify', 'inform', 'disclose'],
            'verification': ['verify', 'confirm', 'validate', 'check'],
            'documentation': ['document', 'record', 'maintain', 'retain'],
            'risk-management': ['risk', 'assessment', 'evaluate', 'mitigate'],
            'customer-data': ['customer', 'client', 'personal data', 'information'],
            'audit': ['audit', 'review', 'inspect', 'examine'],
            'training': ['train', 'educate', 'awareness', 'competency'],
            'security': ['security', 'protect', 'safeguard', 'confidential'],
            'compliance': ['comply', 'compliance', 'adherence', 'conformity'],
            'governance': ['governance', 'oversight', 'control', 'management']
        }
        
        for tag, keywords in tag_patterns.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)
        
        return tags[:7]  # Limit to 7 tags
    
    def _create_basic_clause(
        self,
        clause: Dict[str, Any],
        document_type: str,
        document_id: str
    ) -> Dict[str, Any]:
        """Create a basic clause when LLM is not available."""
        text = clause.get('text', '')
        
        # Extract title from text
        title = self._extract_title_from_text(text) or clause.get('section', 'General')
        
        # Generate tags
        tags = self._generate_basic_tags(text)
        
        return {
            "clause_id": str(uuid.uuid4()),
            "original_text": text,
            "document_type": document_type,
            "document_id": document_id,
            "section": clause.get('section', 'General'),
            "page_number": clause.get('page', 1),
            # NEW: Structured display attributes
            "title": title,
            "content": text,
            "tags": tags,
            # Analysis attributes
            "requirement_type": self._infer_requirement_type(text),
            "subject_category": "general",
            "key_obligations": [],
            "semantic_summary": text[:200] if len(text) > 200 else text,
            "entities_involved": [],
            "keywords": self._extract_keywords(text),
            "compliance_indicators": [],
            "criticality": "medium"
        }
    
    def _infer_requirement_type(self, text: str) -> str:
        """Infer requirement type from text patterns using compliance context."""
        req_type = self.context.infer_requirement_type(text)
        return req_type.value if hasattr(req_type, 'value') else str(req_type)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction based on common compliance terms
        keywords = []
        text_lower = text.lower()
        
        compliance_terms = [
            'compliance', 'audit', 'report', 'review', 'policy', 'procedure',
            'risk', 'control', 'data', 'customer', 'transaction', 'record',
            'disclosure', 'authorization', 'verification', 'monitoring'
        ]
        
        for term in compliance_terms:
            if term in text_lower:
                keywords.append(term)
        
        return keywords[:5]
    
    def _fallback_clause_extraction(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback extraction when LLM is not available."""
        clauses = []
        for chunk in chunks:
            chunk_clauses = self._fallback_chunk_extraction(chunk)
            clauses.extend(chunk_clauses)
        return clauses
    
    def _fallback_chunk_extraction(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract clauses from chunk without LLM."""
        text = chunk.get('text', '')
        section = chunk.get('section', 'General')
        page = chunk.get('page', 1)
        
        # Split by sentences that look like requirements
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        clauses = []
        current_clause = []
        
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            # Check if this starts a new requirement
            if self._is_requirement_start(sent) and current_clause:
                clauses.append({
                    'text': ' '.join(current_clause),
                    'section': section,
                    'page': page,
                    'clause_number': len(clauses) + 1
                })
                current_clause = [sent]
            else:
                current_clause.append(sent)
        
        if current_clause:
            clauses.append({
                'text': ' '.join(current_clause),
                'section': section,
                'page': page,
                'clause_number': len(clauses) + 1
            })
        
        # Filter out very short clauses
        return [c for c in clauses if len(c['text']) > 50]
    
    def _is_requirement_start(self, text: str) -> bool:
        """Check if text starts a new requirement."""
        text_lower = text.lower()
        starters = [
            'the bank shall', 'the company shall', 'the organization shall',
            'all employees', 'management shall', 'it is required',
            'shall', 'must', 'should'
        ]
        return any(text_lower.startswith(s) or f' {s}' in text_lower[:50] for s in starters)


class GapAnalysisMatcher:
    """
    Service for matching Policy clauses against Regulation clauses
    and identifying gaps using Claude.
    
    Uses ComplianceContext for centralized prompts and domain knowledge.
    """
    
    def __init__(self, context: ComplianceContext = None):
        """
        Initialize the gap analysis matcher.
        
        Args:
            context: ComplianceContext instance. If None, uses default context.
        """
        self.context = context or get_default_context()
        self.api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('EMERGENT_LLM_KEY')

        # Temporarily unset proxy env vars to avoid SOCKS issues
        http_proxy_backup = os.environ.get('HTTP_PROXY')
        https_proxy_backup = os.environ.get('HTTPS_PROXY')
        all_proxy_backup = os.environ.get('ALL_PROXY')
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('ALL_PROXY', None)
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)
        os.environ.pop('all_proxy', None)

        try:
            self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
            self.async_client = AsyncAnthropic(api_key=self.api_key) if self.api_key else None
        finally:
            # Restore proxy settings
            if http_proxy_backup:
                os.environ['HTTP_PROXY'] = http_proxy_backup
            if https_proxy_backup:
                os.environ['HTTPS_PROXY'] = https_proxy_backup
            if all_proxy_backup:
                os.environ['ALL_PROXY'] = all_proxy_backup

        self.model = self.context.model
    
    async def _call_claude(self, system_message: str, user_message: str, max_tokens: int = 4096) -> str:
        """
        Async helper to call Claude API with native async streaming.
        Uses AsyncAnthropic.messages.stream() — no sync wrappers, no thread pools.
        """
        if not self.async_client:
            raise ValueError("Anthropic async client not initialized")
        
        import time
        start_time = time.time()
        
        logger.info(f"[GAP ANALYSIS LLM] Calling {self.model} | system={len(system_message)} chars | user={len(user_message)} chars | max_tokens={max_tokens}")
        
        response_text = ""
        input_tokens = 0
        output_tokens = 0
        
        async with self.async_client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_message,
            messages=[
                {"role": "user", "content": user_message}
            ]
        ) as stream:
            async for text in stream.text_stream:
                response_text += text
            final_message = await stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens
        
        elapsed_time = time.time() - start_time
        logger.info(f"[GAP ANALYSIS LLM] Done in {elapsed_time:.1f}s | {input_tokens} in / {output_tokens} out | {len(response_text)} chars")
        
        return response_text
    
    async def find_matching_clauses(
        self,
        policy_clauses: List[Dict[str, Any]],
        regulation_clauses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Match policy clauses to regulation clauses based on semantic similarity.
        
        Returns a list of matches with gap analysis.
        """
        matches = []
        
        for policy_clause in policy_clauses:
            # Find best matching regulation clauses based on subject category
            candidate_regulations = [
                r for r in regulation_clauses
                if r['subject_category'] == policy_clause['subject_category']
            ]
            
            # If no exact category match, look at related categories
            if not candidate_regulations:
                candidate_regulations = self._find_related_regulations(
                    policy_clause, regulation_clauses
                )
            
            # Use LLM to find the best match and analyze gap
            if candidate_regulations:
                match_result = await self._analyze_match(policy_clause, candidate_regulations)
                matches.append(match_result)
            else:
                # No matching regulation found
                matches.append({
                    "policy_clause": policy_clause,
                    "matched_regulation": None,
                    "gap_type": "no_regulation_match",
                    "gap_analysis": {
                        "severity": "Low",
                        "description": "No corresponding regulation requirement found",
                        "suggested_action": "Review if this policy requirement is based on internal standards"
                    }
                })
        
        return matches
    
    def _find_related_regulations(
        self,
        policy_clause: Dict[str, Any],
        regulation_clauses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find regulations with overlapping keywords."""
        policy_keywords = set(policy_clause.get('keywords', []))
        
        scored_regulations = []
        for reg in regulation_clauses:
            reg_keywords = set(reg.get('keywords', []))
            overlap = len(policy_keywords & reg_keywords)
            if overlap > 0:
                scored_regulations.append((overlap, reg))
        
        scored_regulations.sort(reverse=True, key=lambda x: x[0])
        return [r for _, r in scored_regulations[:5]]
    
    async def _analyze_match(
        self,
        policy_clause: Dict[str, Any],
        candidate_regulations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use Claude with context-based prompts to find best match and analyze gap."""
        if not self.client:
            # Simple fallback
            return {
                "policy_clause": policy_clause,
                "matched_regulation": candidate_regulations[0] if candidate_regulations else None,
                "gap_type": "requires_review",
                "gap_analysis": {
                    "severity": "Medium",
                    "description": "LLM analysis unavailable - manual review required",
                    "suggested_action": "Manually compare policy and regulation requirements"
                }
            }
        
        try:
            # Find the best matching regulation first
            best_match_idx = 0
            best_match_regulation = candidate_regulations[0] if candidate_regulations else None
            
            if len(candidate_regulations) > 1:
                # Use context-aware matching
                regulations_text = "\n\n".join([
                    f"REGULATION {i+1} (Category: {r.get('subject_category', 'general')}):\n"
                    f"Text: {r.get('original_text', r.get('text', ''))[:500]}\n"
                    f"Obligations: {', '.join(r.get('key_obligations', []))}\n"
                    f"Summary: {r.get('semantic_summary', '')}"
                    for i, r in enumerate(candidate_regulations[:5])
                ])
                
                # Build gap analysis prompt using context
                user_prompt = self.context.build_gap_analysis_prompt(
                    regulation_clause=regulations_text,
                    policy_clause=policy_clause.get('original_text', policy_clause.get('text', '')),
                    regulation_title="Candidate Regulations",
                    policy_title="Internal Policy",
                    regulator="Regulatory Authority",
                    regulation_req_type=candidate_regulations[0].get('requirement_type', 'mandatory') if candidate_regulations else 'mandatory',
                    policy_req_type=policy_clause.get('requirement_type', 'mandatory'),
                    regulation_obligations=candidate_regulations[0].get('key_obligations', []) if candidate_regulations else [],
                    policy_obligations=policy_clause.get('key_obligations', [])
                )
                
                # Get system prompt from context
                system_prompt = self.context.get_system_prompt("gap_analysis")
            else:
                # Single regulation - direct comparison
                user_prompt = self.context.build_gap_analysis_prompt(
                    regulation_clause=best_match_regulation.get('original_text', best_match_regulation.get('text', '')) if best_match_regulation else "",
                    policy_clause=policy_clause.get('original_text', policy_clause.get('text', '')),
                    regulation_title=best_match_regulation.get('title', 'Regulation') if best_match_regulation else 'Regulation',
                    policy_title=policy_clause.get('title', 'Policy'),
                    regulator="Regulatory Authority",
                    regulation_req_type=best_match_regulation.get('requirement_type', 'mandatory') if best_match_regulation else 'mandatory',
                    policy_req_type=policy_clause.get('requirement_type', 'mandatory'),
                    regulation_obligations=best_match_regulation.get('key_obligations', []) if best_match_regulation else [],
                    policy_obligations=policy_clause.get('key_obligations', [])
                )
                system_prompt = self.context.get_system_prompt("gap_analysis")
            
            response = await self._call_claude(
                system_prompt,
                user_prompt
            )
            
            # Parse response with robust JSON handling
            parsed = _extract_json_from_llm_response(response)
            result = parsed[0] if isinstance(parsed, list) and len(parsed) > 0 else parsed
            if not isinstance(result, dict):
                result = {}
            
            # Map new schema to expected output
            gap_type = result.get('gap_type', 'requires_review')
            if gap_type == 'fully_compliant':
                gap_type = 'compliant'
            
            return {
                "policy_clause": policy_clause,
                "matched_regulation": best_match_regulation,
                "match_confidence": result.get('confidence_score', 0.5),
                "gap_type": gap_type,
                "gap_analysis": {
                    "severity": result.get('severity', 'Medium'),
                    "description": result.get('gap_description', ''),
                    "missing_elements": result.get('missing_elements', []),
                    "regulatory_risk": result.get('regulatory_risk', ''),
                    "suggested_action": result.get('remediation_actions', ['Manual review required'])[0] if result.get('remediation_actions') else 'Manual review required',
                    "remediation_actions": result.get('remediation_actions', []),
                    "priority": result.get('priority', 'Medium-term'),
                    "evidence_needed": result.get('evidence_needed', [])
                }
            }
            
        except Exception as e:
            logger.error(f"Gap analysis matching error: {e}")
            return {
                "policy_clause": policy_clause,
                "matched_regulation": candidate_regulations[0] if candidate_regulations else None,
                "gap_type": "error",
                "gap_analysis": {
                    "severity": "Medium",
                    "description": f"Analysis error: {str(e)}",
                    "suggested_action": "Manual review required"
                }
            }


# Convenience function for easy import
async def extract_and_enrich_clauses(
    text: str,
    document_type: str,
    document_id: str,
    document_title: str = ""
) -> List[Dict[str, Any]]:
    """
    Convenience function to extract and enrich clauses from a document.
    
    Args:
        text: Document text
        document_type: 'policy' or 'regulation'
        document_id: Unique document identifier
        document_title: Title for context
        
    Returns:
        List of enriched clause dictionaries with semantic attributes
    """
    service = ClauseExtractionService()
    return await service.extract_clauses_from_document(
        text, document_type, document_id, document_title
    )


async def perform_gap_analysis(
    policy_clauses: List[Dict[str, Any]],
    regulation_clauses: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Convenience function to perform gap analysis between policy and regulation clauses.
    
    Args:
        policy_clauses: List of enriched policy clauses
        regulation_clauses: List of enriched regulation clauses
        
    Returns:
        List of match results with gap analysis
    """
    matcher = GapAnalysisMatcher()
    return await matcher.find_matching_clauses(policy_clauses, regulation_clauses)
