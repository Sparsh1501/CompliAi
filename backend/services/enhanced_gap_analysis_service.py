"""
Enhanced Gap Analysis Service

This service implements a comprehensive gap analysis framework where:
- REGULATIONS are the SOURCE OF TRUTH (Bible) - immutable benchmark
- Every POLICY clause is evaluated against ALL relevant REGULATION clauses
- Gaps are identified where policy implementation differs from regulatory requirements

Gap Analysis Philosophy:
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REGULATION = SOURCE OF TRUTH                         │
│                                                                             │
│  Regulation Clause (R1)  ──────────────────────────────────────────────►   │
│         ↓                                                                   │
│  "The bank SHALL verify customer identity using valid photo ID"            │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ BENCHMARK REQUIREMENTS:                                          │      │
│  │ • Action: Verify identity                                        │      │
│  │ • Method: Valid photo ID                                         │      │
│  │ • Obligation: Mandatory (SHALL)                                  │      │
│  │ • Entity: Bank                                                   │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  Policy Clause (P1)  ─────────────────────────────────────────────────►    │
│         ↓                                                                   │
│  "Customer verification will be done as per applicable guidelines"         │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ GAP IDENTIFIED:                                                   │      │
│  │ • Missing: Specific method (photo ID not mentioned)              │      │
│  │ • Weak: "will be done" vs "SHALL" (weaker language)              │      │
│  │ • Vague: "as per applicable guidelines" (not specific)          │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘

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
from services.anthropic_utils import create_anthropic_client

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.compliance_context import (
    ComplianceContext,
    get_default_context,
    RequirementType,
    CriticalityLevel,
)

# Import local LLM provider
from services.llm_provider import get_llm_provider, is_using_local_llm

logger = logging.getLogger(__name__)


# =============================================================================
# GAP TYPES - Severity-ordered for compliance prioritization
# =============================================================================

class GapType(str, Enum):
    """Types of gaps between policy and regulation"""
    MISSING = "missing"           # Regulation requires X, policy is completely silent
    CONFLICTING = "conflicting"   # Policy contradicts regulation
    WEAK = "weak"                 # Policy uses weaker language (should vs shall)
    PARTIAL = "partial"           # Policy addresses partially, missing elements
    COMPLIANT = "compliant"       # Policy fully meets regulation
    EXCEEDS = "exceeds"           # Policy goes beyond regulation (positive)
    NOT_APPLICABLE = "not_applicable"  # Regulation doesn't apply to this policy


class GapSeverity(str, Enum):
    """Severity of identified gaps"""
    CRITICAL = "Critical"   # Immediate regulatory action, license risk
    HIGH = "High"          # Significant penalty exposure
    MEDIUM = "Medium"      # Audit finding, needs attention
    LOW = "Low"           # Minor observation, best practice


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class RegulationBenchmark:
    """
    A regulation clause as a benchmark requirement.
    
    This represents the SOURCE OF TRUTH that policies must comply with.
    """
    clause_id: str
    title: str
    original_text: str
    requirement_type: str  # mandatory, prohibition, recommended, etc.
    subject_category: str
    key_obligations: List[str]
    semantic_summary: str
    entities_involved: List[str]
    keywords: List[str]
    compliance_indicators: List[str]
    criticality: str
    # Additional metadata
    regulatory_reference: Optional[str] = None
    timeline: Optional[str] = None
    penalties: Optional[str] = None


@dataclass 
class PolicyImplementation:
    """
    A policy clause representing implementation of regulatory requirements.
    """
    clause_id: str
    title: str
    original_text: str
    requirement_type: str
    subject_category: str
    key_obligations: List[str]
    semantic_summary: str
    entities_involved: List[str]
    keywords: List[str]
    compliance_indicators: List[str]
    criticality: str


@dataclass
class GapDetail:
    """
    Detailed gap analysis result for a policy clause against regulation benchmark.
    """
    gap_id: str
    gap_type: GapType
    severity: GapSeverity
    confidence_score: float  # 0.0 to 1.0
    
    # Source clauses
    policy_clause: PolicyImplementation
    regulation_benchmarks: List[RegulationBenchmark]  # All relevant regulations
    primary_regulation: Optional[RegulationBenchmark]  # Best match
    
    # Gap description
    gap_description: str
    missing_elements: List[str]
    weak_elements: List[str]
    regulatory_risk: str
    
    # Remediation
    remediation_actions: List[str]
    priority: str  # Immediate, Short-term, Medium-term, Long-term
    evidence_needed: List[str]
    
    # Metadata
    analysis_notes: str = ""


@dataclass
class GapAnalysisReport:
    """
    Complete gap analysis report for a policy against a regulation.
    """
    report_id: str
    policy_id: str
    policy_title: str
    regulation_id: str
    regulation_title: str
    
    # Summary metrics
    total_policy_clauses: int
    total_regulation_clauses: int
    compliance_score: float  # 0-100
    
    # Gap breakdown
    gaps: List[GapDetail]
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    compliant_clauses: int
    
    # Unaddressed regulation requirements
    unaddressed_regulations: List[RegulationBenchmark]
    
    # Recommendations
    executive_summary: str
    priority_actions: List[str]
    
    # Metadata
    analysis_timestamp: str
    llm_model: str


# =============================================================================
# ENHANCED GAP ANALYSIS SERVICE
# =============================================================================

class EnhancedGapAnalysisService:
    """
    Comprehensive gap analysis service using Anthropic LLM.
    
    Key Features:
    1. Regulation as Source of Truth - Immutable benchmark
    2. Every policy clause evaluated against ALL relevant regulations
    3. Intelligent clustering by subject category
    4. Detailed gap identification with remediation guidance
    5. Executive summary and prioritized action items
    """
    
    def __init__(self, context: ComplianceContext = None):
        """
        Initialize the gap analysis service.
        
        Args:
            context: ComplianceContext for prompts and domain knowledge
        """
        self.context = context or get_default_context()
        
        # Check if using local LLM
        self.use_local_llm = is_using_local_llm()
        if self.use_local_llm:
            logger.info("🚀 EnhancedGapAnalysisService: Using LOCAL LLM mode (Ollama)")
            self.local_provider = get_llm_provider()
        else:
            self.local_provider = None
        
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key and not self.use_local_llm:
            logger.warning("ANTHROPIC_API_KEY not found and USE_LOCAL_LLM=false - LLM features disabled")
            self.client = None
        elif self.api_key:
            self.client = create_anthropic_client(self.api_key)
        else:
            self.client = None
        self.model = self.context.model
    
    def _call_claude(self, system_message: str, user_message: str, max_tokens: int = 8192) -> str:
        """Synchronous helper to call Claude API or local LLM."""
        import time
        start_time = time.time()
        
        # Use local LLM if enabled
        if self.use_local_llm and self.local_provider:
            import asyncio
            logger.info(f"[GAP LLM - LOCAL] Calling Ollama | system={len(system_message)} chars | user={len(user_message)} chars")
            try:
                # Run async method synchronously
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Use thread-safe approach for running loop
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.local_provider.generate(
                                system=system_message,
                                prompt=user_message,
                                max_tokens=max_tokens,
                                temperature=0.3
                            )
                        )
                        response_text = future.result()
                else:
                    response_text = loop.run_until_complete(
                        self.local_provider.generate(
                            system=system_message,
                            prompt=user_message,
                            max_tokens=max_tokens,
                            temperature=0.3
                        )
                    )
                elapsed_time = time.time() - start_time
                logger.info(f"[GAP LLM - LOCAL] Done in {elapsed_time:.1f}s | $0.00 (local) | {len(response_text)} chars")
                return response_text
            except Exception as e:
                logger.error(f"Local LLM call failed: {e}")
                raise
        
        # Fallback to Claude
        if not self.client:
            raise ValueError("Anthropic client not initialized and USE_LOCAL_LLM=false")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_message,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text
    
    async def analyze_policy_against_regulation(
        self,
        policy_clauses: List[Dict[str, Any]],
        regulation_clauses: List[Dict[str, Any]],
        policy_id: str,
        policy_title: str,
        regulation_id: str,
        regulation_title: str
    ) -> GapAnalysisReport:
        """
        Main entry point: Analyze a policy against a regulation.
        
        Process:
        1. Index regulation clauses by subject category (these are the BENCHMARKS)
        2. For each policy clause, find ALL relevant regulation clauses
        3. Analyze gaps between policy implementation and regulation requirements
        4. Identify unaddressed regulation requirements
        5. Generate executive summary and action items
        
        Args:
            policy_clauses: List of policy clause dictionaries
            regulation_clauses: List of regulation clause dictionaries (SOURCE OF TRUTH)
            policy_id: Policy document ID
            policy_title: Policy document title
            regulation_id: Regulation document ID  
            regulation_title: Regulation document title
            
        Returns:
            GapAnalysisReport with detailed gap analysis
        """
        logger.info(f"Starting comprehensive gap analysis: {policy_title} vs {regulation_title}")
        logger.info(f"Policy clauses: {len(policy_clauses)}, Regulation clauses: {len(regulation_clauses)}")
        
        # Step 1: Index regulation clauses by category (BENCHMARKS)
        regulation_index = self._index_regulations_by_category(regulation_clauses)
        logger.info(f"Indexed regulations into {len(regulation_index)} categories")
        
        # Step 2: Analyze each policy clause against relevant regulations
        gaps = []
        addressed_regulation_ids = set()
        
        # Process policy clauses in batches for efficiency
        batch_size = 3
        for i in range(0, len(policy_clauses), batch_size):
            batch = policy_clauses[i:i + batch_size]
            batch_results = await asyncio.gather(*[
                self._analyze_policy_clause(
                    policy_clause=clause,
                    regulation_index=regulation_index,
                    all_regulations=regulation_clauses
                )
                for clause in batch
            ])
            
            for gap_detail, reg_ids in batch_results:
                gaps.append(gap_detail)
                addressed_regulation_ids.update(reg_ids)
        
        logger.info(f"Analyzed {len(gaps)} policy clauses")
        
        # Step 3: Identify unaddressed regulation requirements
        all_regulation_ids = {r.get('clause_id', r.get('id', '')) for r in regulation_clauses}
        unaddressed_ids = all_regulation_ids - addressed_regulation_ids
        unaddressed_regulations = [
            self._to_regulation_benchmark(r) 
            for r in regulation_clauses 
            if r.get('clause_id', r.get('id', '')) in unaddressed_ids
        ]
        
        logger.info(f"Found {len(unaddressed_regulations)} unaddressed regulation requirements")
        
        # Step 4: Calculate metrics
        critical_gaps = len([g for g in gaps if g.severity == GapSeverity.CRITICAL])
        high_gaps = len([g for g in gaps if g.severity == GapSeverity.HIGH])
        medium_gaps = len([g for g in gaps if g.severity == GapSeverity.MEDIUM])
        low_gaps = len([g for g in gaps if g.severity == GapSeverity.LOW])
        compliant_clauses = len([g for g in gaps if g.gap_type == GapType.COMPLIANT])
        
        # Calculate compliance score
        # Deduct points for gaps, add points for compliance
        total_points = len(gaps)
        if total_points > 0:
            compliance_points = (
                compliant_clauses * 1.0 +
                low_gaps * 0.7 +
                medium_gaps * 0.4 +
                high_gaps * 0.1 +
                critical_gaps * 0.0
            )
            # Also penalize for unaddressed regulations
            unaddressed_penalty = min(len(unaddressed_regulations) * 0.5, total_points * 0.3)
            compliance_score = max(0, ((compliance_points / total_points) * 100) - unaddressed_penalty)
        else:
            compliance_score = 0.0
        
        # Step 5: Generate executive summary
        executive_summary, priority_actions = await self._generate_executive_summary(
            gaps=gaps,
            unaddressed_regulations=unaddressed_regulations,
            policy_title=policy_title,
            regulation_title=regulation_title,
            compliance_score=compliance_score
        )
        
        # Build report
        report = GapAnalysisReport(
            report_id=str(uuid.uuid4()),
            policy_id=policy_id,
            policy_title=policy_title,
            regulation_id=regulation_id,
            regulation_title=regulation_title,
            total_policy_clauses=len(policy_clauses),
            total_regulation_clauses=len(regulation_clauses),
            compliance_score=round(compliance_score, 1),
            gaps=gaps,
            critical_gaps=critical_gaps,
            high_gaps=high_gaps,
            medium_gaps=medium_gaps,
            low_gaps=low_gaps,
            compliant_clauses=compliant_clauses,
            unaddressed_regulations=unaddressed_regulations,
            executive_summary=executive_summary,
            priority_actions=priority_actions,
            analysis_timestamp=__import__('datetime').datetime.now().isoformat(),
            llm_model=self.model
        )
        
        logger.info(f"Gap analysis complete. Score: {compliance_score:.1f}%, Critical: {critical_gaps}, High: {high_gaps}")
        
        return report
    
    def _index_regulations_by_category(
        self,
        regulation_clauses: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Index regulation clauses by subject category for efficient lookup.
        """
        index = {}
        for clause in regulation_clauses:
            category = clause.get('subject_category', 'general')
            if category not in index:
                index[category] = []
            index[category].append(clause)
        return index
    
    async def _analyze_policy_clause(
        self,
        policy_clause: Dict[str, Any],
        regulation_index: Dict[str, List[Dict[str, Any]]],
        all_regulations: List[Dict[str, Any]]
    ) -> Tuple[GapDetail, set]:
        """
        Analyze a single policy clause against all relevant regulations.
        
        Returns:
            Tuple of (GapDetail, set of addressed regulation IDs)
        """
        # Find relevant regulations based on category and keywords
        policy_category = policy_clause.get('subject_category', 'general')
        policy_keywords = set(policy_clause.get('keywords', []))
        
        # Get regulations from same category
        relevant_regulations = list(regulation_index.get(policy_category, []))
        
        # Also find regulations with overlapping keywords from other categories
        for category, regs in regulation_index.items():
            if category != policy_category:
                for reg in regs:
                    reg_keywords = set(reg.get('keywords', []))
                    if len(policy_keywords & reg_keywords) >= 2:  # At least 2 common keywords
                        if reg not in relevant_regulations:
                            relevant_regulations.append(reg)
        
        # Limit to top 10 most relevant
        if len(relevant_regulations) > 10:
            relevant_regulations = self._rank_regulations_by_relevance(
                policy_clause, relevant_regulations
            )[:10]
        
        # If no relevant regulations found, use general matching
        if not relevant_regulations:
            # Try to find any regulation with keyword overlap
            for reg in all_regulations[:20]:  # Check first 20
                reg_keywords = set(reg.get('keywords', []))
                if len(policy_keywords & reg_keywords) >= 1:
                    relevant_regulations.append(reg)
                    if len(relevant_regulations) >= 5:
                        break
        
        # Analyze gap using LLM (Claude API or local Ollama)
        has_llm = self.client or (self.use_local_llm and self.local_provider)
        if relevant_regulations and has_llm:
            gap_detail = await self._analyze_gap_with_llm(
                policy_clause, relevant_regulations
            )
        else:
            # Fallback - no matching regulations
            gap_detail = self._create_no_match_gap(policy_clause)
        
        # Track which regulations were addressed
        addressed_ids = {
            r.get('clause_id', r.get('id', '')) 
            for r in relevant_regulations
        }
        
        return gap_detail, addressed_ids
    
    def _rank_regulations_by_relevance(
        self,
        policy_clause: Dict[str, Any],
        regulations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rank regulations by relevance to policy clause."""
        policy_keywords = set(policy_clause.get('keywords', []))
        policy_obligations = set(policy_clause.get('key_obligations', []))
        policy_text = policy_clause.get('original_text', '').lower()
        
        scored = []
        for reg in regulations:
            score = 0
            
            # Keyword overlap
            reg_keywords = set(reg.get('keywords', []))
            score += len(policy_keywords & reg_keywords) * 2
            
            # Same requirement type
            if reg.get('requirement_type') == policy_clause.get('requirement_type'):
                score += 1
            
            # Obligation similarity (simple text matching)
            reg_obligations = ' '.join(reg.get('key_obligations', [])).lower()
            policy_obligations_text = ' '.join(policy_clause.get('key_obligations', [])).lower()
            common_terms = set(reg_obligations.split()) & set(policy_obligations_text.split())
            score += len(common_terms)
            
            # Text similarity (very basic)
            reg_text = reg.get('original_text', '').lower()
            common_words = set(reg_text.split()) & set(policy_text.split())
            score += len(common_words) / 20  # Normalize
            
            scored.append((score, reg))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [r for _, r in scored]
    
    async def _analyze_gap_with_llm(
        self,
        policy_clause: Dict[str, Any],
        relevant_regulations: List[Dict[str, Any]]
    ) -> GapDetail:
        """
        Use Anthropic Claude to analyze gap between policy and regulations.
        """
        try:
            # Build regulation benchmark text
            regulations_text = "\n\n".join([
                f"""REGULATION BENCHMARK {i+1}:
Title: {r.get('title', 'Untitled')}
Requirement Type: {r.get('requirement_type', 'mandatory')}
Subject: {r.get('subject_category', 'general')}
Original Text: {r.get('original_text', r.get('text', ''))[:600]}
Key Obligations: {', '.join(r.get('key_obligations', []))}
Semantic Summary: {r.get('semantic_summary', '')}
Compliance Indicators: {', '.join(r.get('compliance_indicators', []))}
Criticality: {r.get('criticality', 'high')}"""
                for i, r in enumerate(relevant_regulations[:5])
            ])
            
            # Build policy implementation text
            policy_text = f"""POLICY IMPLEMENTATION:
Title: {policy_clause.get('title', 'Untitled')}
Requirement Type: {policy_clause.get('requirement_type', 'informational')}
Subject: {policy_clause.get('subject_category', 'general')}
Original Text: {policy_clause.get('original_text', policy_clause.get('text', ''))}
Key Obligations: {', '.join(policy_clause.get('key_obligations', []))}
Semantic Summary: {policy_clause.get('semantic_summary', '')}
Compliance Indicators: {', '.join(policy_clause.get('compliance_indicators', []))}"""

            system_prompt = """You are an expert compliance auditor analyzing policy implementations against regulatory requirements.

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

            user_prompt = f"""Analyze this POLICY clause against the REGULATION benchmarks.

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

            response = await asyncio.to_thread(
                self._call_claude,
                system_prompt,
                user_prompt,
                4096
            )
            
            # Parse response
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = re.sub(r'^```(?:json)?\n?', '', clean_response)
                clean_response = re.sub(r'\n?```$', '', clean_response)
            
            result = json.loads(clean_response)
            
            # Find primary regulation
            primary_idx = result.get('primary_regulation_index', 1) - 1
            primary_regulation = None
            if 0 <= primary_idx < len(relevant_regulations):
                primary_regulation = self._to_regulation_benchmark(relevant_regulations[primary_idx])
            
            # Build GapDetail
            return GapDetail(
                gap_id=str(uuid.uuid4()),
                gap_type=GapType(result.get('gap_type', 'partial')),
                severity=GapSeverity(result.get('severity', 'Medium')),
                confidence_score=result.get('confidence_score', 0.7),
                policy_clause=self._to_policy_implementation(policy_clause),
                regulation_benchmarks=[self._to_regulation_benchmark(r) for r in relevant_regulations],
                primary_regulation=primary_regulation,
                gap_description=result.get('gap_description', 'Gap analysis performed'),
                missing_elements=result.get('missing_elements', []),
                weak_elements=result.get('weak_elements', []),
                regulatory_risk=result.get('regulatory_risk', 'Potential compliance finding'),
                remediation_actions=result.get('remediation_actions', ['Review and update policy']),
                priority=result.get('priority', 'Medium-term'),
                evidence_needed=result.get('evidence_needed', []),
                analysis_notes=result.get('analysis_notes', '')
            )
            
        except Exception as e:
            logger.error(f"LLM gap analysis failed: {e}")
            return self._create_fallback_gap(policy_clause, relevant_regulations)
    
    def _create_no_match_gap(self, policy_clause: Dict[str, Any]) -> GapDetail:
        """Create gap detail when no matching regulation is found."""
        return GapDetail(
            gap_id=str(uuid.uuid4()),
            gap_type=GapType.NOT_APPLICABLE,
            severity=GapSeverity.LOW,
            confidence_score=0.5,
            policy_clause=self._to_policy_implementation(policy_clause),
            regulation_benchmarks=[],
            primary_regulation=None,
            gap_description="No corresponding regulation requirement found for this policy clause",
            missing_elements=[],
            weak_elements=[],
            regulatory_risk="This policy clause may be based on internal standards rather than regulatory requirements",
            remediation_actions=["Review if this clause is based on internal standards or best practices"],
            priority="Long-term",
            evidence_needed=[],
            analysis_notes="Consider whether this policy exceeds regulatory requirements or addresses internal governance"
        )
    
    def _create_fallback_gap(
        self,
        policy_clause: Dict[str, Any],
        relevant_regulations: List[Dict[str, Any]]
    ) -> GapDetail:
        """Create fallback gap detail when LLM fails."""
        return GapDetail(
            gap_id=str(uuid.uuid4()),
            gap_type=GapType.PARTIAL,
            severity=GapSeverity.MEDIUM,
            confidence_score=0.3,
            policy_clause=self._to_policy_implementation(policy_clause),
            regulation_benchmarks=[self._to_regulation_benchmark(r) for r in relevant_regulations],
            primary_regulation=self._to_regulation_benchmark(relevant_regulations[0]) if relevant_regulations else None,
            gap_description="Automated analysis incomplete - manual review required",
            missing_elements=["Manual review needed"],
            weak_elements=[],
            regulatory_risk="Unable to automatically assess regulatory risk",
            remediation_actions=["Manual review by compliance officer required"],
            priority="Short-term",
            evidence_needed=["Compliance officer review documentation"],
            analysis_notes="LLM analysis failed, fallback result"
        )
    
    def _to_regulation_benchmark(self, clause: Dict[str, Any]) -> RegulationBenchmark:
        """Convert clause dict to RegulationBenchmark."""
        return RegulationBenchmark(
            clause_id=clause.get('clause_id', str(uuid.uuid4())),
            title=clause.get('title', 'Untitled'),
            original_text=clause.get('original_text', clause.get('text', '')),
            requirement_type=clause.get('requirement_type', 'mandatory'),
            subject_category=clause.get('subject_category', 'general'),
            key_obligations=clause.get('key_obligations', []),
            semantic_summary=clause.get('semantic_summary', ''),
            entities_involved=clause.get('entities_involved', []),
            keywords=clause.get('keywords', []),
            compliance_indicators=clause.get('compliance_indicators', []),
            criticality=clause.get('criticality', 'high'),
            regulatory_reference=clause.get('regulatory_reference'),
            timeline=clause.get('timeline'),
            penalties=clause.get('penalties')
        )
    
    def _to_policy_implementation(self, clause: Dict[str, Any]) -> PolicyImplementation:
        """Convert clause dict to PolicyImplementation."""
        return PolicyImplementation(
            clause_id=clause.get('clause_id', str(uuid.uuid4())),
            title=clause.get('title', 'Untitled'),
            original_text=clause.get('original_text', clause.get('text', '')),
            requirement_type=clause.get('requirement_type', 'informational'),
            subject_category=clause.get('subject_category', 'general'),
            key_obligations=clause.get('key_obligations', []),
            semantic_summary=clause.get('semantic_summary', ''),
            entities_involved=clause.get('entities_involved', []),
            keywords=clause.get('keywords', []),
            compliance_indicators=clause.get('compliance_indicators', []),
            criticality=clause.get('criticality', 'medium')
        )
    
    async def _generate_executive_summary(
        self,
        gaps: List[GapDetail],
        unaddressed_regulations: List[RegulationBenchmark],
        policy_title: str,
        regulation_title: str,
        compliance_score: float
    ) -> Tuple[str, List[str]]:
        """Generate executive summary and priority actions using LLM."""
        has_llm = self.client or (self.use_local_llm and self.local_provider)
        if not has_llm:
            return self._generate_fallback_summary(gaps, compliance_score), []
        
        try:
            # Build summary of gaps
            gap_summary = []
            for gap in gaps[:20]:  # Top 20 gaps
                gap_summary.append(f"- {gap.gap_type.value.upper()}: {gap.gap_description[:100]}")
            
            unaddressed_summary = []
            for reg in unaddressed_regulations[:10]:
                unaddressed_summary.append(f"- {reg.title}: {reg.semantic_summary[:100]}")
            
            system_prompt = """You are a Chief Compliance Officer preparing an executive summary of a gap analysis report for the Board of Directors."""
            
            user_prompt = f"""Generate an executive summary for this gap analysis.

Policy: {policy_title}
Regulation: {regulation_title}
Compliance Score: {compliance_score:.1f}%

Gap Summary (sample):
{chr(10).join(gap_summary[:15])}

Unaddressed Regulation Requirements:
{chr(10).join(unaddressed_summary[:10]) if unaddressed_summary else "None identified"}

Critical Gaps: {len([g for g in gaps if g.severity == GapSeverity.CRITICAL])}
High Gaps: {len([g for g in gaps if g.severity == GapSeverity.HIGH])}
Medium Gaps: {len([g for g in gaps if g.severity == GapSeverity.MEDIUM])}
Low Gaps: {len([g for g in gaps if g.severity == GapSeverity.LOW])}
Compliant Clauses: {len([g for g in gaps if g.gap_type == GapType.COMPLIANT])}

Provide:
1. Executive summary (3-4 paragraphs for Board presentation)
2. Top 5 priority actions (specific, actionable)

Return JSON:
{{
    "executive_summary": "<3-4 paragraphs>",
    "priority_actions": ["<action 1>", "<action 2>", ...]
}}"""

            response = await asyncio.to_thread(
                self._call_claude,
                system_prompt,
                user_prompt,
                2048
            )
            
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = re.sub(r'^```(?:json)?\n?', '', clean_response)
                clean_response = re.sub(r'\n?```$', '', clean_response)
            
            result = json.loads(clean_response)
            
            return result.get('executive_summary', ''), result.get('priority_actions', [])
            
        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            return self._generate_fallback_summary(gaps, compliance_score), []
    
    def _generate_fallback_summary(self, gaps: List[GapDetail], compliance_score: float) -> str:
        """Generate basic executive summary without LLM."""
        critical = len([g for g in gaps if g.severity == GapSeverity.CRITICAL])
        high = len([g for g in gaps if g.severity == GapSeverity.HIGH])
        
        return f"""Gap Analysis Summary

The policy has been analyzed against the regulatory requirements. The overall compliance score is {compliance_score:.1f}%.

{critical} critical gaps and {high} high-priority gaps were identified that require immediate attention. These gaps represent areas where the policy either does not address regulatory requirements or uses weaker language than required.

Recommend immediate review by the compliance team to address critical and high-priority gaps. A detailed remediation plan should be developed within 30 days."""


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def run_enhanced_gap_analysis(
    policy_clauses: List[Dict[str, Any]],
    regulation_clauses: List[Dict[str, Any]],
    policy_id: str,
    policy_title: str,
    regulation_id: str,
    regulation_title: str,
    context: ComplianceContext = None
) -> GapAnalysisReport:
    """
    Convenience function to run enhanced gap analysis.
    
    Args:
        policy_clauses: List of policy clause dictionaries
        regulation_clauses: List of regulation clause dictionaries (SOURCE OF TRUTH)
        policy_id: Policy document ID
        policy_title: Policy document title
        regulation_id: Regulation document ID
        regulation_title: Regulation document title
        context: Optional ComplianceContext
        
    Returns:
        GapAnalysisReport with complete analysis
    """
    service = EnhancedGapAnalysisService(context=context)
    return await service.analyze_policy_against_regulation(
        policy_clauses=policy_clauses,
        regulation_clauses=regulation_clauses,
        policy_id=policy_id,
        policy_title=policy_title,
        regulation_id=regulation_id,
        regulation_title=regulation_title
    )


def gap_report_to_dict(report: GapAnalysisReport) -> Dict[str, Any]:
    """Convert GapAnalysisReport to dictionary for API response."""
    return {
        "report_id": report.report_id,
        "policy_id": report.policy_id,
        "policy_title": report.policy_title,
        "regulation_id": report.regulation_id,
        "regulation_title": report.regulation_title,
        "total_policy_clauses": report.total_policy_clauses,
        "total_regulation_clauses": report.total_regulation_clauses,
        "compliance_score": report.compliance_score,
        "critical_gaps": report.critical_gaps,
        "high_gaps": report.high_gaps,
        "medium_gaps": report.medium_gaps,
        "low_gaps": report.low_gaps,
        "compliant_clauses": report.compliant_clauses,
        "unaddressed_regulations_count": len(report.unaddressed_regulations),
        "executive_summary": report.executive_summary,
        "priority_actions": report.priority_actions,
        "analysis_timestamp": report.analysis_timestamp,
        "llm_model": report.llm_model,
        "gaps": [
            {
                "gap_id": gap.gap_id,
                "gap_type": gap.gap_type.value,
                "severity": gap.severity.value,
                "confidence_score": gap.confidence_score,
                "policy_clause": {
                    "clause_id": gap.policy_clause.clause_id,
                    "title": gap.policy_clause.title,
                    "original_text": gap.policy_clause.original_text,
                    "semantic_summary": gap.policy_clause.semantic_summary
                },
                "primary_regulation": {
                    "clause_id": gap.primary_regulation.clause_id,
                    "title": gap.primary_regulation.title,
                    "original_text": gap.primary_regulation.original_text,
                    "semantic_summary": gap.primary_regulation.semantic_summary,
                    "key_obligations": gap.primary_regulation.key_obligations
                } if gap.primary_regulation else None,
                "gap_description": gap.gap_description,
                "missing_elements": gap.missing_elements,
                "weak_elements": gap.weak_elements,
                "regulatory_risk": gap.regulatory_risk,
                "remediation_actions": gap.remediation_actions,
                "priority": gap.priority,
                "evidence_needed": gap.evidence_needed
            }
            for gap in report.gaps
        ],
        "unaddressed_regulations": [
            {
                "clause_id": reg.clause_id,
                "title": reg.title,
                "original_text": reg.original_text[:500],
                "semantic_summary": reg.semantic_summary,
                "key_obligations": reg.key_obligations,
                "criticality": reg.criticality
            }
            for reg in report.unaddressed_regulations
        ]
    }
