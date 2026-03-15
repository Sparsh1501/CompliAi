"""
Semantic Gap Analysis Service - LLM-First Approach

This service implements gap analysis where:
1. REGULATIONS are the SOURCE OF TRUTH (iterate over regulations)
2. LLM SEMANTIC MATCHING is PRIMARY (not keyword-based)
3. For each regulation clause, use LLM to find semantically matching policy clauses
4. Then assess compliance level using LLM

Key Insight: Compliance is about MEANING, not exact word matching.
A policy saying "verify customer identity with government-issued photo ID"
is COMPLIANT with a regulation requiring "KYC verification using valid ID documents"
even though keywords don't match exactly.

Author: CompliAI
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
# ENUMS AND CONSTANTS
# =============================================================================

class GapType(str, Enum):
    COMPLIANT = "compliant"       # Policy fully addresses regulation
    EXCEEDS = "exceeds"           # Policy goes beyond regulation
    PARTIAL = "partial"           # Partial coverage, some elements missing
    WEAK = "weak"                 # Addressed but weaker language
    MISSING = "missing"           # No policy coverage at all
    CONFLICTING = "conflicting"   # Policy contradicts regulation


class GapSeverity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# Gap type to compliance score mapping (0-100)
GAP_TYPE_SCORES = {
    GapType.COMPLIANT: 100,
    GapType.EXCEEDS: 100,
    GapType.PARTIAL: 60,
    GapType.WEAK: 75,
    GapType.MISSING: 0,
    GapType.CONFLICTING: 0,
}

# Criticality weights for weighted scoring
CRITICALITY_WEIGHTS = {
    "high": 3,
    "medium": 2,
    "low": 1,
}

# Category to department mapping
CATEGORY_TO_DEPARTMENT = {
    "kyc_cdd": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "customer_due_diligence": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "aml_cft": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "regulatory_reporting": {"department_id": "dept-compliance", "department": "Compliance", "role": "analyst"},
    "reporting": {"department_id": "dept-compliance", "department": "Compliance", "role": "analyst"},
    "compliance_monitoring": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "risk_management": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    "capital_adequacy": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    "credit_risk": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    "operational_risk": {"department_id": "dept-risk", "department": "Risk Management", "role": "analyst"},
    "fraud_management": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    "data_protection": {"department_id": "dept-it", "department": "Information Technology", "role": "officer"},
    "information_security": {"department_id": "dept-it", "department": "Information Technology", "role": "manager"},
    "business_continuity": {"department_id": "dept-it", "department": "Information Technology", "role": "manager"},
    "digital_lending": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "fair_practices": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "customer_rights": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "outsourcing": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "third_party_management": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "grievance_redressal": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "governance": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "internal_audit": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "record_keeping": {"department_id": "dept-compliance", "department": "Compliance", "role": "analyst"},
    "payments": {"department_id": "dept-it", "department": "Information Technology", "role": "manager"},
    "licensing": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "licensing_authorization": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "operational_procedures": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "training_awareness": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "disclosure": {"department_id": "dept-compliance", "department": "Compliance", "role": "analyst"},
    "general": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RegulationGapResult:
    """Result of analyzing a single regulation clause against policy."""
    regulation_clause_id: str
    regulation_title: str
    regulation_text: str
    regulation_section: str
    subject_category: str
    requirement_type: str
    criticality: str
    compliance_indicators: List[str]
    key_obligations: List[str]
    
    # Analysis result
    gap_type: GapType
    severity: GapSeverity
    confidence_score: float
    
    # Matched policies
    matched_policy_clauses: List[Dict[str, Any]]
    primary_policy_match: Optional[Dict[str, Any]]
    
    # Gap details
    gap_description: str
    covered_elements: List[str]      # What IS covered by policy
    missing_elements: List[str]      # What's NOT covered
    weak_elements: List[str]         # What's covered but weak
    
    # Remediation
    suggested_action: str
    remediation_deadline: str
    
    # Assignment
    assigned_department: str
    assigned_department_id: str
    assigned_role: str
    
    # NEW: Evidence-level compliance map (checklist-style)
    evidence_map: List[Dict[str, Any]] = field(default_factory=list)
    # Each item: {
    #   "indicator": "KYC policy document approved by Board",
    #   "status": "found" | "missing" | "partial",
    #   "evidence_type": "document|process|record|control|training|report",
    #   "mandatory": true/false,
    #   "source_policy_clause_id": "uuid or null",
    #   "source_policy_title": "...",
    #   "source_text": "excerpt from policy",
    #   "source_page": 5,
    #   "source_section": "KYC Process",
    #   "verification_method": "How auditor checks",
    #   "reasoning": "Why this was marked found/missing"
    # }


@dataclass
class SemanticGapReport:
    """Complete gap analysis report."""
    report_id: str
    policy_id: str
    policy_title: str
    regulation_id: str
    regulation_title: str
    
    # Counts
    total_regulation_clauses: int
    total_policy_clauses: int
    
    # Coverage metrics
    fully_compliant_count: int
    partially_compliant_count: int
    non_compliant_count: int
    
    # Weighted compliance score (0-100)
    compliance_score: float
    
    # Gap breakdown
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    
    # Results
    gap_results: List[RegulationGapResult]
    
    # Executive summary
    executive_summary: str
    
    # Metadata
    analysis_timestamp: str
    llm_model: str


# =============================================================================
# SEMANTIC GAP ANALYSIS SERVICE
# =============================================================================

class SemanticGapAnalysisService:
    """
    LLM-First Semantic Gap Analysis Service.
    
    Philosophy:
    - Regulations are SOURCE OF TRUTH
    - Use LLM to understand MEANING, not just keywords
    - For each regulation, find ALL policy clauses that semantically address it
    - Assess compliance based on coverage of requirements, not word matching
    """
    
    def __init__(self, db=None, vector_service=None, llm_service=None):
        """Initialize the service."""
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not found")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.db = db
        self.vector_service = vector_service
        self.llm_service = llm_service
    
    async def analyze(
        self,
        policy_clauses: List[Dict[str, Any]],
        regulation_clauses: List[Dict[str, Any]],
        policy_id: str,
        policy_title: str,
        regulation_id: str,
        regulation_title: str,
        organization: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> SemanticGapReport:
        """
        Main entry: Analyze ALL regulation clauses against policy.
        
        For EACH regulation clause:
        1. Use LLM to find semantically matching policy clauses
        2. Use LLM to assess compliance level
        3. Identify gaps and severity
        
        Args:
            progress_callback: Optional async callback(step, progress, message, details)
        """
        logger.info(f"Starting SEMANTIC gap analysis (LLM-First)")
        logger.info(f"  Regulation: {regulation_title} ({len(regulation_clauses)} clauses)")
        logger.info(f"  Policy: {policy_title} ({len(policy_clauses)} clauses)")
        
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        if not regulation_clauses:
            logger.warning("No regulation clauses to analyze")
            return SemanticGapReport(
                report_id=str(uuid.uuid4()),
                policy_id=policy_id, policy_title=policy_title,
                regulation_id=regulation_id, regulation_title=regulation_title,
                total_regulation_clauses=0, total_policy_clauses=len(policy_clauses),
                fully_compliant_count=0, partially_compliant_count=0, non_compliant_count=0,
                compliance_score=0.0, critical_gaps=0, high_gaps=0, medium_gaps=0, low_gaps=0,
                gap_results=[], executive_summary="No regulation clauses to analyze.",
                analysis_timestamp=datetime.now(timezone.utc).isoformat(), llm_model=self.model
            )
        
        # Notify: Starting
        if progress_callback:
            try:
                await progress_callback(
                    step="init",
                    progress=0,
                    message="Initializing semantic analysis...",
                    details={"regulation_count": len(regulation_clauses), "policy_count": len(policy_clauses)}
                )
            except Exception:
                pass
        
        # Prepare policy summaries for LLM matching
        policy_summaries = self._prepare_policy_summaries(policy_clauses)
        
        if progress_callback:
            try:
                await progress_callback(
                    step="prepared",
                    progress=5,
                    message="Policy summaries prepared, starting regulation analysis...",
                    details={}
                )
            except Exception:
                pass
        
        # Analyze each regulation clause
        gap_results: List[RegulationGapResult] = []
        
        # Process in batches of 2 (to manage API rate limits)
        batch_size = 2
        total_clauses = len(regulation_clauses)
        for i in range(0, total_clauses, batch_size):
            batch = regulation_clauses[i:i + batch_size]
            logger.info(f"Processing regulations {i+1}-{i+len(batch)} of {total_clauses}")
            
            # Progress update
            if progress_callback:
                try:
                    progress_pct = 10 + int((i / total_clauses) * 70)  # 10-80% for clause processing
                    await progress_callback(
                        step="analyzing",
                        progress=progress_pct,
                        message=f"Analyzing regulation clause {i+1} of {total_clauses}...",
                        details={
                            "current_clause": i + 1,
                            "total_clauses": total_clauses,
                            "clause_title": batch[0].get('title', 'Untitled'),
                            "llm_action": "semantic_matching"
                        }
                    )
                except Exception:
                    pass
            
            batch_results = await asyncio.gather(*[
                self._analyze_single_regulation(
                    reg_clause=reg,
                    policy_clauses=policy_clauses,
                    policy_summaries=policy_summaries,
                    organization=organization
                )
                for reg in batch
            ], return_exceptions=True)
            
            # Handle any failed results gracefully
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Regulation clause {i+j+1} failed: {type(result).__name__}: {result}")
                    gap_results.append(self._create_fallback_result(batch[j]))
                else:
                    gap_results.append(result)
            
            # Small delay between batches to avoid API rate limits
            if i + batch_size < total_clauses:
                await asyncio.sleep(1)
        
        # Safety check: ensure we have results for ALL clauses
        if len(gap_results) < total_clauses:
            logger.warning(f"Only {len(gap_results)} of {total_clauses} clauses analyzed, filling missing with fallbacks")
            analyzed_ids = {r.regulation_clause_id for r in gap_results}
            for reg in regulation_clauses:
                rid = reg.get('clause_id', '')
                if rid not in analyzed_ids:
                    gap_results.append(self._create_fallback_result(reg))
        
        # Progress update: Metrics calculation
        if progress_callback:
            try:
                await progress_callback(
                    step="calculating",
                    progress=82,
                    message="Calculating compliance metrics...",
                    details={"processed_clauses": total_clauses}
                )
            except Exception:
                pass  # Don't let progress callback failures stop the analysis
        
        # Calculate metrics
        compliant = len([r for r in gap_results if r.gap_type in [GapType.COMPLIANT, GapType.EXCEEDS]])
        partial = len([r for r in gap_results if r.gap_type in [GapType.PARTIAL, GapType.WEAK]])
        non_compliant = len([r for r in gap_results if r.gap_type in [GapType.MISSING, GapType.CONFLICTING]])
        
        critical = len([r for r in gap_results if r.severity == GapSeverity.CRITICAL])
        high = len([r for r in gap_results if r.severity == GapSeverity.HIGH])
        medium = len([r for r in gap_results if r.severity == GapSeverity.MEDIUM])
        low = len([r for r in gap_results if r.severity == GapSeverity.LOW])
        
        # Calculate weighted compliance score
        compliance_score = self._calculate_weighted_score(gap_results)
        
        # Progress update: Generating summary
        if progress_callback:
            try:
                await progress_callback(
                    step="summary",
                    progress=88,
                    message="Generating executive summary with AI...",
                    details={
                        "compliance_score": round(compliance_score, 1),
                        "compliant": compliant,
                        "partial": partial,
                        "non_compliant": non_compliant,
                        "llm_action": "summary_generation"
                    }
                )
            except Exception:
                pass
        
        # Generate executive summary (never let this crash the analysis)
        try:
            executive_summary = await self._generate_executive_summary(
                gap_results, policy_title, regulation_title, compliance_score,
                compliant, partial, non_compliant
            )
        except Exception as e:
            logger.error(f"Executive summary generation failed entirely: {e}")
            executive_summary = f"Gap analysis of \"{policy_title}\" against \"{regulation_title}\" shows a compliance score of {compliance_score:.1f}%. {compliant} compliant, {partial} partial, {non_compliant} non-compliant requirements identified."
        
        # Progress update: Finalizing
        if progress_callback:
            try:
                await progress_callback(
                    step="finalizing",
                    progress=95,
                    message="Finalizing report...",
                    details={}
                )
            except Exception:
                pass
        
        report = SemanticGapReport(
            report_id=str(uuid.uuid4()),
            policy_id=policy_id,
            policy_title=policy_title,
            regulation_id=regulation_id,
            regulation_title=regulation_title,
            total_regulation_clauses=len(regulation_clauses),
            total_policy_clauses=len(policy_clauses),
            fully_compliant_count=compliant,
            partially_compliant_count=partial,
            non_compliant_count=non_compliant,
            compliance_score=round(compliance_score, 1),
            critical_gaps=critical,
            high_gaps=high,
            medium_gaps=medium,
            low_gaps=low,
            gap_results=gap_results,
            executive_summary=executive_summary,
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            llm_model=self.model
        )
        
        logger.info(f"Semantic gap analysis complete. Score: {compliance_score:.1f}%")
        logger.info(f"  Compliant: {compliant}, Partial: {partial}, Non-compliant: {non_compliant}")
        
        # Progress update: Complete
        if progress_callback:
            try:
                await progress_callback(
                    step="complete",
                    progress=100,
                    message="Analysis complete!",
                    details={
                        "compliance_score": round(compliance_score, 1),
                        "total_gaps": len(gap_results),
                        "critical_gaps": critical,
                        "high_gaps": high,
                        "medium_gaps": medium,
                        "low_gaps": low
                    }
                )
            except Exception:
                pass
        
        return report
    
    def _prepare_policy_summaries(self, policy_clauses: List[Dict[str, Any]], indices: List[int] = None) -> str:
        """Prepare concise policy summaries for LLM matching.
        
        Args:
            policy_clauses: List of policy clause dictionaries
            indices: Optional list of original indices (1-based) for display
        """
        summaries = []
        for i, p in enumerate(policy_clauses):
            # Use provided index or calculate from position
            display_idx = indices[i] if indices else (i + 1)
            title = p.get('title') or 'Untitled'
            text = (p.get('original_text') or p.get('text') or '')[:300]
            summary = (p.get('semantic_summary') or '')[:150]
            obligations = ', '.join((p.get('key_obligations') or [])[:3])
            keywords = ', '.join((p.get('keywords') or [])[:5])
            category = p.get('subject_category') or 'general'
            
            # Include implementation evidence for policy clauses (critical for gap analysis accuracy)
            impl_evidence = p.get('implementation_evidence') or []
            impl_text = ', '.join(impl_evidence[:3]) if impl_evidence else ''
            processes = p.get('processes_described') or []
            proc_text = ', '.join(processes[:3]) if processes else ''
            reg_refs = p.get('regulatory_references') or []
            reg_text = ', '.join(reg_refs[:2]) if reg_refs else ''
            
            summary_parts = [
                f"[{display_idx}] {title}",
                f"    Category: {category}",
                f"    Keywords: {keywords}",
                f"    Summary: {summary or text[:150]}",
                f"    Obligations: {obligations}",
            ]
            if impl_text:
                summary_parts.append(f"    Implementation Evidence: {impl_text}")
            if proc_text:
                summary_parts.append(f"    Processes: {proc_text}")
            if reg_text:
                summary_parts.append(f"    Addresses Regulations: {reg_text}")
            
            summaries.append("\n".join(summary_parts))
        
        return "\n".join(summaries)

    async def _prefilter_policy_candidates_with_qdrant(
        self,
        reg_clause: Dict[str, Any],
        policy_clauses: List[Dict[str, Any]],
        organization: str,
        max_candidates: int = 25,
        score_threshold: float = 0.25
    ) -> Tuple[List[Dict[str, Any]], List[int], List[float]]:
        """
        Pre-filter policy clauses using Qdrant vector semantic search.

        This method uses embeddings and cosine similarity to find semantically related
        policy clauses, which is more accurate than keyword matching for compliance.

        Args:
            reg_clause: Regulation clause to match against
            policy_clauses: All available policy clauses
            organization: Organization identifier for filtering
            max_candidates: Maximum number of candidates to return
            score_threshold: Minimum similarity score (0-1)

        Returns:
            Tuple of (filtered_clauses, original_1based_indices, similarity_scores)
        """
        # If vector service is not available, fall back to keyword-based filtering
        if not self.vector_service or not self.vector_service.qdrant_client:
            logger.warning("Vector service not available, falling back to keyword-based pre-filtering")
            filtered, indices = self._prefilter_policy_candidates(reg_clause, policy_clauses, max_candidates)
            # Return dummy scores (all 0.0) to maintain API compatibility
            return filtered, indices, [0.0] * len(filtered)

        try:
            # Extract regulation clause text
            reg_text = reg_clause.get('original_text') or reg_clause.get('text', '')
            reg_title = reg_clause.get('title', '')

            # Combine title and text for better semantic matching
            query_text = f"{reg_title}\n\n{reg_text}".strip()

            logger.info(f"[Qdrant] Searching for similar policy clauses for regulation: {reg_title[:60]}...")

            # Use VectorService to search for semantically similar policy clauses
            similar_clauses = await self.vector_service.search_similar_clauses(
                query_text=query_text,
                organization=organization,
                limit=max_candidates,
                score_threshold=score_threshold
            )

            # If organization filter returned 0 results, retry without filter
            # (handles org mismatch between user and stored data)
            if not similar_clauses:
                logger.warning(f"[Qdrant] No results with org filter '{organization}', retrying without filter...")
                similar_clauses = await self.vector_service.search_similar_clauses(
                    query_text=query_text,
                    organization="",  # Will be handled below
                    limit=max_candidates,
                    score_threshold=score_threshold
                )

            logger.info(f"[Qdrant] Found {len(similar_clauses)} similar clauses with scores >= {score_threshold}")
            if similar_clauses:
                scores_preview = [c['score'] for c in similar_clauses[:5]]
                logger.info(f"[Qdrant] Top 5 similarity scores: {scores_preview}")

            # If Qdrant returns no results, fall back to keyword matching
            if len(similar_clauses) < 1:
                logger.warning(f"[Qdrant] Insufficient results ({len(similar_clauses)}), falling back to keyword matching")
                filtered, indices = self._prefilter_policy_candidates(reg_clause, policy_clauses, max_candidates)
                return filtered, indices, [0.0] * len(filtered)

            # Map Qdrant results back to policy_clauses by clause_id
            clause_id_to_policy = {
                policy.get('clause_id'): (idx, policy)
                for idx, policy in enumerate(policy_clauses)
            }

            filtered_policies = []
            original_indices = []
            similarity_scores = []

            for result in similar_clauses:
                clause_id = result.get('clause_id')
                if clause_id in clause_id_to_policy:
                    idx, policy = clause_id_to_policy[clause_id]
                    filtered_policies.append(policy)
                    original_indices.append(idx + 1)  # 1-based for LLM
                    similarity_scores.append(result['score'])

            logger.info(f"[Qdrant] Pre-filtered {len(policy_clauses)} -> {len(filtered_policies)} candidates")

            # If Qdrant returned results but none mapped to current policy clauses
            # (e.g., Qdrant has stale data from different policies), fall back to keyword matching
            if not filtered_policies:
                logger.warning(f"[Qdrant] Found {len(similar_clauses)} Qdrant results but NONE matched current policy clause_ids. Falling back to keyword matching.")
                filtered, indices = self._prefilter_policy_candidates(reg_clause, policy_clauses, max_candidates)
                return filtered, indices, [0.0] * len(filtered)

            return filtered_policies, original_indices, similarity_scores

        except Exception as e:
            logger.error(f"[Qdrant] Error in vector-based pre-filtering: {e}", exc_info=True)
            logger.warning("[Qdrant] Falling back to keyword-based pre-filtering due to error")
            filtered, indices = self._prefilter_policy_candidates(reg_clause, policy_clauses, max_candidates)
            return filtered, indices, [0.0] * len(filtered)

    def _prefilter_policy_candidates(
        self,
        reg_clause: Dict[str, Any],
        policy_clauses: List[Dict[str, Any]],
        max_candidates: int = 25
    ) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Pre-filter policy clauses based on keyword overlap and category matching.
        
        This reduces the number of policies sent to LLM from 100+ to ~25 most relevant,
        improving both accuracy and cost.
        
        Returns:
            Tuple of (filtered_clauses, original_1based_indices)
        """
        reg_keywords = set(k.lower().strip() for k in (reg_clause.get('keywords') or []))
        reg_category = (reg_clause.get('subject_category') or 'general').lower()
        reg_title_words = set((reg_clause.get('title') or '').lower().split())
        reg_text = (reg_clause.get('original_text') or reg_clause.get('text') or '').lower()
        
        # Define category relationships for partial matching
        related_categories = {
            'kyc_cdd': {'aml_cft', 'fair_practices', 'digital_lending', 'governance', 'customer_due_diligence'},
            'customer_due_diligence': {'kyc_cdd', 'aml_cft', 'fair_practices', 'digital_lending'},
            'aml_cft': {'kyc_cdd', 'fraud_management', 'reporting', 'governance', 'record_keeping'},
            'data_protection': {'information_security', 'governance', 'digital_lending', 'record_keeping'},
            'digital_lending': {'fair_practices', 'kyc_cdd', 'data_protection', 'outsourcing', 'grievance_redressal'},
            'outsourcing': {'digital_lending', 'governance', 'information_security', 'third_party_management'},
            'third_party_management': {'outsourcing', 'governance', 'digital_lending'},
            'information_security': {'data_protection', 'business_continuity', 'governance', 'fraud_management'},
            'fraud_management': {'aml_cft', 'information_security', 'governance', 'reporting', 'internal_audit'},
            'grievance_redressal': {'fair_practices', 'digital_lending', 'governance', 'customer_rights'},
            'customer_rights': {'fair_practices', 'grievance_redressal', 'digital_lending', 'governance'},
            'governance': {'internal_audit', 'reporting', 'aml_cft', 'kyc_cdd', 'fraud_management'},
            'reporting': {'aml_cft', 'governance', 'record_keeping', 'internal_audit', 'regulatory_reporting'},
            'regulatory_reporting': {'reporting', 'governance', 'aml_cft'},
            'record_keeping': {'reporting', 'aml_cft', 'kyc_cdd', 'governance', 'data_protection'},
            'capital_adequacy': {'governance', 'reporting', 'risk_management'},
            'risk_management': {'capital_adequacy', 'governance', 'aml_cft', 'fraud_management'},
            'payments': {'digital_lending', 'information_security', 'fair_practices'},
            'licensing': {'governance', 'reporting', 'licensing_authorization'},
            'licensing_authorization': {'licensing', 'governance', 'reporting'},
            'fair_practices': {'digital_lending', 'grievance_redressal', 'customer_rights', 'kyc_cdd'},
            'business_continuity': {'information_security', 'governance', 'operational_procedures'},
            'internal_audit': {'governance', 'fraud_management', 'reporting', 'compliance_monitoring'},
            'operational_procedures': {'governance', 'business_continuity', 'record_keeping'},
            'training_awareness': {'governance', 'aml_cft', 'information_security'},
            'disclosure': {'fair_practices', 'digital_lending', 'reporting'},
            'compliance_monitoring': {'governance', 'internal_audit', 'reporting'},
            'general': {'governance', 'reporting', 'fair_practices'},
        }
        
        scored_policies = []
        
        for idx, policy in enumerate(policy_clauses):
            score = 0.0
            
            # 1. Keyword overlap (highest weight)
            policy_keywords = set(k.lower().strip() for k in (policy.get('keywords') or []))
            keyword_overlap = reg_keywords & policy_keywords
            score += len(keyword_overlap) * 3.0  # 3 points per matching keyword
            
            # 2. Category matching
            policy_category = (policy.get('subject_category') or 'general').lower()
            if policy_category == reg_category:
                score += 5.0  # Exact category match
            elif policy_category in related_categories.get(reg_category, set()):
                score += 2.5  # Related category
            elif reg_category in related_categories.get(policy_category, set()):
                score += 2.5  # Reverse related
            
            # 3. Title word overlap
            policy_title_words = set(policy.get('title', '').lower().split())
            # Remove common words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'for', 'of', 'to', 'in', 'on', 'with', 'by'}
            title_overlap = (reg_title_words - stop_words) & (policy_title_words - stop_words)
            score += len(title_overlap) * 1.5
            
            # 4. Text content keyword search (lightweight)
            policy_text = (policy.get('original_text') or policy.get('text', '')).lower()
            for kw in list(reg_keywords)[:5]:  # Check top 5 regulation keywords in policy text
                if kw in policy_text and len(kw) > 3:  # Skip very short keywords
                    score += 1.0
            
            # 5. Requirement type boost (mandatory policies should match mandatory regulations)
            reg_req = reg_clause.get('requirement_type', 'mandatory')
            policy_req = policy.get('requirement_type', 'mandatory')
            if reg_req == 'mandatory' and policy_req == 'mandatory':
                score += 1.0
            
            scored_policies.append({
                'index': idx,
                'policy': policy,
                'score': score,
                'keyword_overlap': list(keyword_overlap),
                'category_match': policy_category == reg_category
            })
        
        # Sort by score descending
        scored_policies.sort(key=lambda x: -x['score'])
        
        # Take top candidates, but ensure we include at least some if scores are low
        # Also include any policy with score > 0 up to max
        top_candidates = [p for p in scored_policies if p['score'] > 0][:max_candidates]
        
        # If we have very few matches, add some category-matched policies
        if len(top_candidates) < 10:
            category_matched = [p for p in scored_policies 
                               if p['score'] == 0 and p['category_match']
                               and p not in top_candidates][:10 - len(top_candidates)]
            top_candidates.extend(category_matched)
        
        # IMPROVEMENT: If still very few, add policies from RELATED categories
        # This helps when regulation has a category that policy doesn't cover directly
        if len(top_candidates) < 15:
            # Get all policies from related categories
            related_cats = related_categories.get(reg_category, set())
            related_policies = [p for p in scored_policies 
                               if p not in top_candidates 
                               and p['policy'].get('subject_category', 'general').lower() in related_cats][:15 - len(top_candidates)]
            top_candidates.extend(related_policies)
        
        # If still very few, just take top N by any score (including 0) to give LLM a chance
        if len(top_candidates) < 10:
            remaining = [p for p in scored_policies if p not in top_candidates][:10]
            top_candidates.extend(remaining)
        
        # Extract policies and their original indices (1-based for LLM)
        filtered_policies = [c['policy'] for c in top_candidates]
        original_indices = [c['index'] + 1 for c in top_candidates]  # 1-based
        
        logger.debug(f"Pre-filtered {len(policy_clauses)} -> {len(filtered_policies)} candidates for: {(reg_clause.get('title') or '')[:40]}")
        if top_candidates and top_candidates[0]['score'] > 0:
            logger.debug(f"  Top match: score={top_candidates[0]['score']:.1f}, keywords={top_candidates[0]['keyword_overlap'][:3]}")
        
        return filtered_policies, original_indices
    
    async def _analyze_single_regulation(
        self,
        reg_clause: Dict[str, Any],
        policy_clauses: List[Dict[str, Any]],
        policy_summaries: str,  # Not used anymore, kept for compatibility
        organization: Optional[str] = None,
        _retry_attempt: int = 0
    ) -> RegulationGapResult:
        """
        Analyze a single regulation clause using Qdrant + LLM semantic matching.
        Automatically retries up to 3 times on transient failures.

        Three-step process:
        1. Pre-filter policy candidates using Qdrant vector search (or keyword fallback)
        2. LLM finds semantically matching policy clauses from filtered set
        3. LLM assesses compliance level of matches
        """
        MAX_CLAUSE_RETRIES = 3
        reg_id = reg_clause.get('clause_id') or str(uuid.uuid4())
        reg_title = reg_clause.get('title') or 'Untitled'
        reg_text = reg_clause.get('original_text') or reg_clause.get('text') or ''
        reg_category = reg_clause.get('subject_category') or 'general'
        reg_criticality = reg_clause.get('criticality') or 'high'
        compliance_indicators = reg_clause.get('compliance_indicators') or []
        key_obligations = reg_clause.get('key_obligations') or []
        reg_keywords = reg_clause.get('keywords') or []

        try:
            # Step 1: Pre-filter policy candidates using Qdrant vector search
            # Falls back to keyword-based if Qdrant unavailable
            if organization and self.vector_service:
                filtered_policies, original_indices, vector_scores = await self._prefilter_policy_candidates_with_qdrant(
                    reg_clause, policy_clauses, organization, max_candidates=25, score_threshold=0.25
                )
            else:
                filtered_policies, original_indices = self._prefilter_policy_candidates(
                    reg_clause, policy_clauses, max_candidates=25
                )
                vector_scores = [0.0] * len(filtered_policies)  # No vector scores available
            
            # Prepare summaries for ONLY the filtered candidates
            filtered_summaries = self._prepare_policy_summaries(filtered_policies, original_indices)
            
            # Step 2: Find semantically matching policies using LLM (on filtered set)
            matching_indices = await self._llm_find_matching_policies(
                reg_clause, filtered_summaries, len(policy_clauses),
                candidate_indices=original_indices  # Pass the actual indices
            )

            matched_policies = [policy_clauses[i-1] for i in matching_indices if 1 <= i <= len(policy_clauses)]

            # Get vector scores for matched policies (map from filtered to matched)
            matched_vector_scores = []
            for idx in matching_indices:
                # Find this index in original_indices to get the corresponding vector score
                try:
                    filtered_idx = original_indices.index(idx)
                    matched_vector_scores.append(vector_scores[filtered_idx])
                except (ValueError, IndexError):
                    matched_vector_scores.append(0.0)  # Fallback if not found

            # Step 3: Assess compliance level
            if matched_policies:
                result = await self._llm_assess_compliance(
                    reg_clause, matched_policies, compliance_indicators, key_obligations,
                    vector_scores=matched_vector_scores
                )
            else:
                # No matches = MISSING gap — build evidence_map marking all items as missing
                compliance_checklist = reg_clause.get('compliance_checklist', [])
                missing_evidence_map = []
                if compliance_checklist:
                    for item in compliance_checklist:
                        missing_evidence_map.append({
                            "indicator": item.get('item', ''),
                            "status": "missing",
                            "evidence_type": item.get('evidence_type', 'document'),
                            "mandatory": item.get('mandatory', True),
                            "source_policy_clause_id": None,
                            "source_policy_title": None,
                            "source_text": None,
                            "source_page": None,
                            "source_section": None,
                            "verification_method": item.get('verification_method', ''),
                            "reasoning": "No policy clause found that addresses this requirement"
                        })
                elif compliance_indicators:
                    for ind in compliance_indicators:
                        missing_evidence_map.append({
                            "indicator": ind,
                            "status": "missing",
                            "evidence_type": "document",
                            "mandatory": True,
                            "source_policy_clause_id": None,
                            "source_policy_title": None,
                            "source_text": None,
                            "source_page": None,
                            "source_section": None,
                            "verification_method": "",
                            "reasoning": "No policy clause found that addresses this requirement"
                        })
                
                result = {
                    "gap_type": "missing",
                    "severity": "Critical" if reg_criticality == "high" else "High",
                    "confidence_score": 0.9,
                    "primary_policy_index": 0,
                    "gap_description": f"No policy clause addresses this regulatory requirement: {reg_title}",
                    "covered_elements": [],
                    "missing_elements": key_obligations or [reg_title],
                    "weak_elements": [],
                    "suggested_action": f"Create new policy clause to address: {reg_title}",
                    "evidence_map": missing_evidence_map
                }
            
            # Get department assignment
            dept_info = CATEGORY_TO_DEPARTMENT.get(reg_category, CATEGORY_TO_DEPARTMENT['general'])
            
            # Determine severity and deadline
            gap_type = GapType(result.get('gap_type', 'partial'))
            severity = GapSeverity(result.get('severity', 'Medium'))
            
            deadline = {
                GapSeverity.CRITICAL: "Immediate",
                GapSeverity.HIGH: "1 week",
                GapSeverity.MEDIUM: "1 month",
                GapSeverity.LOW: "3 months"
            }.get(severity, "1 month")
            
            # Get primary policy match
            primary_idx_raw = result.get('primary_policy_index')
            primary_idx = (primary_idx_raw - 1) if primary_idx_raw is not None and isinstance(primary_idx_raw, (int, float)) else 0
            primary_policy = None
            if matched_policies and 0 <= primary_idx < len(matched_policies):
                p = matched_policies[primary_idx]
                primary_policy = {
                    'clause_id': p.get('clause_id', ''),
                    'title': p.get('title', ''),
                    'text': p.get('original_text', p.get('text', ''))[:500]
                }
            elif matched_policies:
                p = matched_policies[0]
                primary_policy = {
                    'clause_id': p.get('clause_id', ''),
                    'title': p.get('title', ''),
                    'text': p.get('original_text', p.get('text', ''))[:500]
                }
            
            return RegulationGapResult(
                regulation_clause_id=reg_id,
                regulation_title=reg_title,
                regulation_text=reg_text[:500],
                regulation_section=reg_clause.get('section', ''),
                subject_category=reg_category,
                requirement_type=reg_clause.get('requirement_type', 'mandatory'),
                criticality=reg_criticality,
                compliance_indicators=compliance_indicators,
                key_obligations=key_obligations,
                gap_type=gap_type,
                severity=severity,
                confidence_score=result.get('confidence_score', 0.7),
                matched_policy_clauses=[{
                    'clause_id': p.get('clause_id', ''),
                    'title': p.get('title', ''),
                    'text': p.get('original_text', p.get('text', ''))[:300]
                } for p in matched_policies],
                primary_policy_match=primary_policy,
                gap_description=result.get('gap_description', ''),
                covered_elements=result.get('covered_elements', []),
                missing_elements=result.get('missing_elements', []),
                weak_elements=result.get('weak_elements', []),
                evidence_map=result.get('evidence_map', []),
                suggested_action=result.get('suggested_action', 'Review and update policy'),
                remediation_deadline=deadline,
                assigned_department=dept_info['department'],
                assigned_department_id=dept_info['department_id'],
                assigned_role=dept_info['role']
            )
            
        except Exception as e:
            if _retry_attempt < MAX_CLAUSE_RETRIES - 1:
                delay = 2 * (2 ** _retry_attempt)
                logger.warning(f"Regulation {reg_id} failed (attempt {_retry_attempt+1}/{MAX_CLAUSE_RETRIES}), retrying in {delay}s: {type(e).__name__}: {e}")
                await asyncio.sleep(delay)
                return await self._analyze_single_regulation(
                    reg_clause, policy_clauses, policy_summaries, organization,
                    _retry_attempt=_retry_attempt + 1
                )
            logger.error(f"Failed to analyze regulation {reg_id} after {MAX_CLAUSE_RETRIES} attempts: {e}", exc_info=True)
            return self._create_fallback_result(reg_clause)
    
    async def _llm_find_matching_policies(
        self,
        reg_clause: Dict[str, Any],
        policy_summaries: str,
        total_policies: int,
        candidate_indices: List[int] = None
    ) -> List[int]:
        """Use LLM to find semantically matching policy clauses.
        
        Args:
            candidate_indices: If provided, these are the actual 1-based indices of the
                             pre-filtered candidates. LLM should return from these.
        """
        
        # Build the valid indices hint for LLM
        valid_indices_hint = ""
        if candidate_indices:
            valid_indices_hint = f"\nNOTE: The policy clause indices shown are: {candidate_indices}. Only return indices from this list."
        
        system_prompt = """You are an expert compliance analyst. Your task is to find policy clauses that SEMANTICALLY address a regulatory requirement.

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

        reg_keywords = reg_clause.get('keywords') or []
        keywords_text = f"Keywords: {', '.join(reg_keywords)}" if reg_keywords else ""

        user_prompt = f"""Find ALL policy clauses that could address this regulation requirement.

=== REGULATION REQUIREMENT ===
Title: {reg_clause.get('title') or 'Untitled'}
Category: {reg_clause.get('subject_category') or 'general'}
{keywords_text}
Text: {(reg_clause.get('original_text') or reg_clause.get('text') or '')[:800]}
Key Obligations: {', '.join(reg_clause.get('key_obligations') or [])}

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

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._call_claude, system_prompt, user_prompt, 1024),
                timeout=180  # 3-minute timeout for matching
            )
            
            clean = response.strip()
            # Robust JSON extraction: handle ```json ... ```, ``` ... ```, or raw JSON
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', clean, re.DOTALL)
            if json_match:
                clean = json_match.group(1).strip()
            # Also try to extract raw JSON object if no code fence
            if not clean.startswith('{'):
                brace_match = re.search(r'(\{.*\})', clean, re.DOTALL)
                if brace_match:
                    clean = brace_match.group(1).strip()
            
            if not clean:
                logger.warning("LLM returned empty response for matching")
                return []
            
            result = json.loads(clean)
            indices = result.get('matching_indices', [])
            
            # Validate indices
            valid_indices = [i for i in indices if 1 <= i <= total_policies]
            
            logger.debug(f"Found {len(valid_indices)} matching policies for: {(reg_clause.get('title') or '')[:50]}")
            return valid_indices
            
        except asyncio.TimeoutError:
            logger.error(f"LLM matching timed out for: {(reg_clause.get('title') or '')[:50]}")
            return []
        except Exception as e:
            logger.error(f"LLM matching failed: {type(e).__name__}: {e}", exc_info=True)
            return []
    
    async def _llm_assess_compliance(
        self,
        reg_clause: Dict[str, Any],
        matched_policies: List[Dict[str, Any]],
        compliance_indicators: List[str],
        key_obligations: List[str],
        vector_scores: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to assess how well matched policies comply with the regulation.
        
        IMPROVED: Evidence-level checklist matching.
        For each compliance_indicator/checklist item from the regulation, the LLM must
        explicitly check whether the matched policies provide evidence of coverage,
        and cite the specific policy clause + text as proof.

        Args:
            vector_scores: Optional vector similarity scores for matched policies (0-1)
                          Higher scores indicate better semantic similarity
        """
        
        # Build detailed policy texts with implementation evidence
        policy_texts = "\n\n".join([
            f"POLICY {i+1} (ID: {p.get('clause_id', 'unknown')}):\n"
            f"  Title: {p.get('title', 'Untitled')}\n"
            f"  Section: {p.get('section', 'General')} | Page: {p.get('page_number', 'N/A')}\n"
            f"  Text: {p.get('original_text', p.get('text', ''))[:800]}\n"
            f"  Implementation Evidence: {', '.join(p.get('implementation_evidence', []))}\n"
            f"  Processes Described: {', '.join(p.get('processes_described', []))}\n"
            f"  Regulatory References: {', '.join(p.get('regulatory_references', []))}"
            for i, p in enumerate(matched_policies[:5])
        ])
        
        # Build the compliance checklist from regulation
        compliance_checklist = reg_clause.get('compliance_checklist', [])
        if compliance_checklist:
            checklist_text = "\n".join([
                f"  {j+1}. [{item.get('evidence_type', 'document').upper()}] {item.get('item', '')} "
                f"({'MANDATORY' if item.get('mandatory', True) else 'Optional'}) "
                f"- Verify by: {item.get('verification_method', 'Review documentation')}"
                for j, item in enumerate(compliance_checklist)
            ])
        else:
            # Fall back to compliance_indicators as simple checklist
            checklist_text = "\n".join([
                f"  {j+1}. {ind}"
                for j, ind in enumerate(compliance_indicators)
            ]) if compliance_indicators else "(No specific checklist items)"
        
        obligations_text = "\n".join([f"  • {obl}" for obl in key_obligations]) if key_obligations else "(No specific obligations)"
        
        system_prompt = """You are an expert compliance auditor performing EVIDENCE-BASED assessment of policy compliance against a regulation.

YOUR JOB: For EACH checklist item from the regulation, determine if the matched policy clauses provide EVIDENCE of compliance.

CRITICAL RULES:
1. You MUST evaluate EVERY checklist item individually — do not skip any
2. For each item, cite the SPECIFIC policy clause (by number) and TEXT that proves compliance
3. If no policy addresses a checklist item, mark it as "missing" with clear reasoning
4. If a policy partially addresses it (weak language, general reference), mark as "partial"
5. Overall gap_type should be derived from the RATIO of found/missing/partial items

EVIDENCE-LEVEL ASSESSMENT:
- "found": The policy EXPLICITLY addresses this. Cite the exact policy text as proof.
- "partial": The policy touches on this topic but doesn't fully address it. Explain what's missing.
- "missing": No policy clause addresses this at all. This is a real gap.

GAP TYPE DERIVATION (use these thresholds):
- "compliant": ALL mandatory items are "found" (minor items can be partial)
- "exceeds": All items found AND policy goes beyond requirements
- "partial": 40-80% of mandatory items are found or partial
- "weak": Items are addressed but with permissive language ("should" vs "shall")
- "missing": Less than 40% of mandatory items are found
- "conflicting": Policy contradicts the regulation

SEVERITY DERIVATION:
- "Critical": Mandatory regulatory requirement with <40% evidence coverage
- "High": Mandatory requirement with 40-60% coverage or missing critical items
- "Medium": 60-80% coverage or only optional items missing
- "Low": >80% coverage, minor improvements needed

BE FAIR AND PRECISE: Mark as "found" only when there is CLEAR evidence in the policy text.
Do not assume — if the policy is silent on a point, it's "missing"."""

        user_prompt = f"""Perform EVIDENCE-BASED compliance assessment.

=== REGULATION (Source of Truth) ===
Title: {reg_clause.get('title') or 'Untitled'}
Type: {reg_clause.get('requirement_type') or 'mandatory'}
Criticality: {reg_clause.get('criticality') or 'high'}

Text: {(reg_clause.get('original_text') or '')[:800]}

Key Obligations:
{obligations_text}

COMPLIANCE CHECKLIST (evaluate EACH item):
{checklist_text}

=== MATCHING POLICY CLAUSES ===
{policy_texts}

=== REQUIRED OUTPUT ===
Return JSON with BOTH overall assessment AND per-item evidence mapping:

{{
    "gap_type": "<compliant|exceeds|partial|weak|missing|conflicting>",
    "severity": "<Critical|High|Medium|Low>",
    "confidence_score": <0.0-1.0>,
    "primary_policy_index": <1-5>,
    "gap_description": "<Overall assessment with specific evidence citations>",
    "covered_elements": ["<Requirements that ARE addressed, with policy reference>"],
    "missing_elements": ["<Requirements that are NOT addressed>"],
    "weak_elements": ["<Requirements addressed with weak language>"],
    "suggested_action": "<Specific remediation action>",
    "evidence_map": [
        {{
            "indicator": "<The checklist item text>",
            "status": "<found|missing|partial>",
            "source_policy_index": <1-5 or null if missing>,
            "source_text": "<Exact quote from policy that proves this, or null>",
            "reasoning": "<Why you marked it found/missing/partial>"
        }}
    ]
}}

CRITICAL: The evidence_map MUST have one entry for EVERY checklist item above. Do NOT skip any."""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._call_claude, system_prompt, user_prompt, 4096),
                timeout=180  # 3-minute timeout for compliance assessment
            )

            clean = response.strip()
            # Robust JSON extraction: handle ```json ... ```, ``` ... ```, or raw JSON
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', clean, re.DOTALL)
            if json_match:
                clean = json_match.group(1).strip()
            if not clean.startswith('{'):
                brace_match = re.search(r'(\{.*\})', clean, re.DOTALL)
                if brace_match:
                    clean = brace_match.group(1).strip()

            if not clean:
                logger.warning("LLM returned empty response for compliance assessment")
                raise ValueError("Empty LLM response")

            result = json.loads(clean)

            # Enrich evidence_map with source policy details
            evidence_map = result.get('evidence_map', [])
            enriched_evidence_map = []
            for item in evidence_map:
                policy_idx = item.get('source_policy_index')
                enriched_item = {
                    "indicator": item.get('indicator', ''),
                    "status": item.get('status', 'missing'),
                    "reasoning": item.get('reasoning', ''),
                    "source_text": item.get('source_text'),
                }
                
                # Map to actual policy clause details
                if policy_idx and isinstance(policy_idx, int) and 1 <= policy_idx <= len(matched_policies):
                    source_policy = matched_policies[policy_idx - 1]
                    enriched_item["source_policy_clause_id"] = source_policy.get('clause_id', '')
                    enriched_item["source_policy_title"] = source_policy.get('title', '')
                    enriched_item["source_page"] = source_policy.get('page_number', None)
                    enriched_item["source_section"] = source_policy.get('section', '')
                else:
                    enriched_item["source_policy_clause_id"] = None
                    enriched_item["source_policy_title"] = None
                    enriched_item["source_page"] = None
                    enriched_item["source_section"] = None
                
                # Add evidence_type and mandatory from the original checklist if available
                if compliance_checklist:
                    indicator_text = item.get('indicator', '')
                    for cl_item in compliance_checklist:
                        if cl_item.get('item', '') == indicator_text or indicator_text in cl_item.get('item', ''):
                            enriched_item["evidence_type"] = cl_item.get('evidence_type', 'document')
                            enriched_item["mandatory"] = cl_item.get('mandatory', True)
                            enriched_item["verification_method"] = cl_item.get('verification_method', '')
                            break
                    else:
                        enriched_item["evidence_type"] = "document"
                        enriched_item["mandatory"] = True
                        enriched_item["verification_method"] = ""
                
                enriched_evidence_map.append(enriched_item)
            
            result['evidence_map'] = enriched_evidence_map
            
            # Calculate evidence-based confidence score
            if enriched_evidence_map:
                found_count = sum(1 for e in enriched_evidence_map if e['status'] == 'found')
                partial_count = sum(1 for e in enriched_evidence_map if e['status'] == 'partial')
                total = len(enriched_evidence_map)
                evidence_coverage = (found_count + partial_count * 0.5) / total if total > 0 else 0
                
                # Hybrid confidence: 40% LLM, 30% evidence coverage, 30% vector similarity
                llm_confidence = result.get('confidence_score', 0.5)
                
                if vector_scores and vector_scores:
                    max_vector_score = max(vector_scores[:5])
                    hybrid_confidence = (llm_confidence * 0.4) + (evidence_coverage * 0.3) + (max_vector_score * 0.3)
                    result['vector_similarity_score'] = max_vector_score
                else:
                    hybrid_confidence = (llm_confidence * 0.5) + (evidence_coverage * 0.5)
                
                result['confidence_score'] = min(hybrid_confidence, 1.0)
                result['llm_confidence'] = llm_confidence
                result['evidence_coverage_ratio'] = evidence_coverage
                result['evidence_found'] = found_count
                result['evidence_partial'] = partial_count
                result['evidence_missing'] = total - found_count - partial_count
                result['evidence_total'] = total
                
                logger.info(f"[Evidence] Coverage: {found_count}/{total} found, {partial_count} partial, "
                           f"ratio={evidence_coverage:.2f}, confidence={result['confidence_score']:.3f}")
            elif vector_scores and vector_scores:
                # Fallback to original hybrid scoring if no evidence map
                llm_confidence = result.get('confidence_score', 0.5)
                max_vector_score = max(vector_scores[:5])
                hybrid_confidence = (llm_confidence * 0.6) + (max_vector_score * 0.4)
                result['confidence_score'] = min(hybrid_confidence, 1.0)
                result['vector_similarity_score'] = max_vector_score
                result['llm_confidence'] = llm_confidence

            return result
            
        except asyncio.TimeoutError:
            logger.error(f"LLM compliance assessment timed out for: {(reg_clause.get('title') or '')[:50]}")
            return {
                "gap_type": "partial",
                "severity": "Medium",
                "confidence_score": 0.3,
                "primary_policy_index": 1,
                "gap_description": "Assessment timed out - manual review required",
                "covered_elements": [],
                "missing_elements": ["Assessment incomplete due to timeout"],
                "weak_elements": [],
                "suggested_action": "Manual review by compliance officer required",
                "evidence_map": []
            }
        except Exception as e:
            logger.error(f"LLM compliance assessment failed: {e}")
            # Fallback - assume partial compliance if we found matches
            return {
                "gap_type": "partial",
                "severity": "Medium",
                "confidence_score": 0.4,
                "primary_policy_index": 1,
                "gap_description": "Automated assessment incomplete - manual review required",
                "covered_elements": [],
                "missing_elements": ["Manual verification needed"],
                "weak_elements": [],
                "suggested_action": "Manual review by compliance officer required",
                "evidence_map": []
            }
    
    def _create_fallback_result(self, reg_clause: Dict[str, Any]) -> RegulationGapResult:
        """Create fallback result when analysis fails."""
        category = reg_clause.get('subject_category') or 'general'
        dept_info = CATEGORY_TO_DEPARTMENT.get(category, CATEGORY_TO_DEPARTMENT['general'])

        return RegulationGapResult(
            regulation_clause_id=reg_clause.get('clause_id') or '',
            regulation_title=reg_clause.get('title') or 'Untitled',
            regulation_text=(reg_clause.get('original_text') or '')[:500],
            regulation_section=reg_clause.get('section') or '',
            subject_category=category,
            requirement_type=reg_clause.get('requirement_type') or 'mandatory',
            criticality=reg_clause.get('criticality') or 'high',
            compliance_indicators=reg_clause.get('compliance_indicators') or [],
            key_obligations=reg_clause.get('key_obligations') or [],
            gap_type=GapType.PARTIAL,
            severity=GapSeverity.MEDIUM,
            confidence_score=0.3,
            matched_policy_clauses=[],
            primary_policy_match=None,
            gap_description="Automated analysis failed - manual review required",
            covered_elements=[],
            missing_elements=["Manual verification needed"],
            weak_elements=[],
            suggested_action="Manual review by compliance officer required",
            remediation_deadline="1 week",
            assigned_department=dept_info['department'],
            assigned_department_id=dept_info['department_id'],
            assigned_role=dept_info['role']
        )
    
    def _calculate_weighted_score(self, gap_results: List[RegulationGapResult]) -> float:
        """Calculate weighted compliance score."""
        if not gap_results:
            return 0.0
        
        weighted_sum = 0.0
        max_weighted_sum = 0.0
        
        for result in gap_results:
            weight = CRITICALITY_WEIGHTS.get(result.criticality, 2)
            score = GAP_TYPE_SCORES.get(result.gap_type, 50)
            
            weighted_sum += score * weight
            max_weighted_sum += 100 * weight
        
        if max_weighted_sum == 0:
            return 0.0
        
        return (weighted_sum / max_weighted_sum) * 100
    
    async def _generate_executive_summary(
        self,
        gap_results: List[RegulationGapResult],
        policy_title: str,
        regulation_title: str,
        compliance_score: float,
        compliant: int,
        partial: int,
        non_compliant: int
    ) -> str:
        """Generate executive summary using LLM."""
        critical = len([r for r in gap_results if r.severity == GapSeverity.CRITICAL])
        high = len([r for r in gap_results if r.severity == GapSeverity.HIGH])
        
        if self.client:
            try:
                # Get top gaps for context
                top_gaps = sorted(
                    [r for r in gap_results if r.gap_type not in [GapType.COMPLIANT, GapType.EXCEEDS]],
                    key=lambda x: (0 if x.severity == GapSeverity.CRITICAL else 1 if x.severity == GapSeverity.HIGH else 2)
                )[:5]
                
                gap_context = "\n".join([
                    f"- {g.regulation_title}: {g.gap_description[:100]}"
                    for g in top_gaps
                ])
                
                system_prompt = "You are a Chief Compliance Officer preparing a brief executive summary for the Board."
                user_prompt = f"""Generate a 2-paragraph executive summary for this gap analysis.

Policy: {policy_title}
Regulation: {regulation_title}

Compliance Score: {compliance_score:.1f}%
Fully Compliant: {compliant} regulation requirements
Partially Compliant: {partial} regulation requirements  
Non-Compliant: {non_compliant} regulation requirements
Critical Gaps: {critical}
High Priority Gaps: {high}

Top Gaps to Address:
{gap_context}

The summary should:
1. State overall compliance posture clearly
2. Highlight key risk areas requiring attention
3. Recommend prioritized next steps

Keep it concise (2 short paragraphs). Return plain text only."""

                response = await asyncio.wait_for(
                    asyncio.to_thread(self._call_claude, system_prompt, user_prompt, 1024),
                    timeout=120  # 2-minute timeout for summary
                )
                return response.strip()
                
            except asyncio.TimeoutError:
                logger.error("Executive summary generation timed out")
            except Exception as e:
                logger.error(f"Executive summary generation failed: {e}")
        
        # Fallback summary
        return f"""The gap analysis of "{policy_title}" against "{regulation_title}" shows a compliance score of {compliance_score:.1f}%. Out of {len(gap_results)} regulatory requirements analyzed, {compliant} are fully compliant, {partial} are partially addressed, and {non_compliant} have no policy coverage.

There are {critical} critical gaps and {high} high-priority gaps requiring immediate attention. Recommend prioritizing critical gaps within 48 hours and high-priority gaps within 1 week. A detailed remediation plan should be developed with assigned owners from the relevant departments."""
    
    def _call_claude(self, system_message: str, user_message: str, max_tokens: int = 4096) -> str:
        """Call Claude API with retry logic for transient errors."""
        if not self.client:
            raise ValueError("Anthropic client not initialized")
        
        import time
        max_retries = 3
        base_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_message,
                    messages=[{"role": "user", "content": user_message}],
                    timeout=120  # 2-minute timeout per API call
                )
                text = response.content[0].text
                if not text:
                    logger.error(f"[Claude API] Empty response. Stop reason: {response.stop_reason}, model: {response.model}")
                return text
            except anthropic.RateLimitError as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[Claude API] Rate limited (attempt {attempt+1}/{max_retries}), retrying in {delay}s: {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    logger.error(f"[Claude API] Rate limit exhausted after {max_retries} attempts")
                    raise
            except anthropic.APIStatusError as e:
                if e.status_code in (429, 500, 502, 503, 529):
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[Claude API] Transient error {e.status_code} (attempt {attempt+1}/{max_retries}), retrying in {delay}s")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        logger.error(f"[Claude API] Failed after {max_retries} attempts: {type(e).__name__}: {e}")
                        raise
                else:
                    logger.error(f"[Claude API] Non-retryable error: {type(e).__name__}: {e}")
                    raise
            except anthropic.APIConnectionError as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[Claude API] Connection error (attempt {attempt+1}/{max_retries}), retrying in {delay}s: {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    logger.error(f"[Claude API] Connection failed after {max_retries} attempts")
                    raise
            except Exception as e:
                logger.error(f"[Claude API] Call failed: {type(e).__name__}: {e}")
                raise


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def run_semantic_gap_analysis(
    policy_clauses: List[Dict[str, Any]],
    regulation_clauses: List[Dict[str, Any]],
    policy_id: str,
    policy_title: str,
    regulation_id: str,
    regulation_title: str,
    db=None
) -> SemanticGapReport:
    """Convenience function to run semantic gap analysis."""
    service = SemanticGapAnalysisService(db=db)
    return await service.analyze(
        policy_clauses=policy_clauses,
        regulation_clauses=regulation_clauses,
        policy_id=policy_id,
        policy_title=policy_title,
        regulation_id=regulation_id,
        regulation_title=regulation_title
    )


def semantic_gap_report_to_dict(report: SemanticGapReport) -> Dict[str, Any]:
    """Convert SemanticGapReport to dictionary."""
    return {
        "report_id": report.report_id,
        "policy_id": report.policy_id,
        "policy_title": report.policy_title,
        "regulation_id": report.regulation_id,
        "regulation_title": report.regulation_title,
        "total_regulation_clauses": report.total_regulation_clauses,
        "total_policy_clauses": report.total_policy_clauses,
        "fully_compliant_count": report.fully_compliant_count,
        "partially_compliant_count": report.partially_compliant_count,
        "non_compliant_count": report.non_compliant_count,
        "compliance_score": report.compliance_score,
        "critical_gaps": report.critical_gaps,
        "high_gaps": report.high_gaps,
        "medium_gaps": report.medium_gaps,
        "low_gaps": report.low_gaps,
        "executive_summary": report.executive_summary,
        "analysis_timestamp": report.analysis_timestamp,
        "llm_model": report.llm_model,
        "gap_results": [
            {
                "regulation_clause_id": r.regulation_clause_id,
                "regulation_title": r.regulation_title,
                "regulation_text": r.regulation_text[:300],
                "regulation_section": r.regulation_section,
                "subject_category": r.subject_category,
                "requirement_type": r.requirement_type,
                "criticality": r.criticality,
                "gap_type": r.gap_type.value,
                "severity": r.severity.value,
                "confidence_score": r.confidence_score,
                "gap_description": r.gap_description,
                "covered_elements": r.covered_elements,
                "missing_elements": r.missing_elements,
                "weak_elements": r.weak_elements,
                "evidence_map": r.evidence_map,
                "matched_policy_count": len(r.matched_policy_clauses),
                "primary_policy": r.primary_policy_match,
                "suggested_action": r.suggested_action,
                "assigned_department": r.assigned_department,
                "assigned_role": r.assigned_role,
                "deadline": r.remediation_deadline
            }
            for r in report.gap_results
        ]
    }
