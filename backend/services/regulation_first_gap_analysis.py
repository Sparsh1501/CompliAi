"""
Regulation-First Gap Analysis Service

This service implements gap analysis where REGULATIONS are the absolute source of truth.
For each regulation clause, we check if policy clauses fulfill its compliance_indicators.

Key Features:
1. Regulation-First: Iterate over each regulation clause
2. Multi-level Matching: tags → keywords → subject_category → LLM semantic
3. Compliance Indicator Check: LLM verifies if policy addresses indicators
4. Weighted Scoring: Based on criticality and gap type
5. Task Assignment: Auto-assign to department members based on subject_category

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

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


# =============================================================================
# CATEGORY TO DEPARTMENT/ROLE MAPPING
# =============================================================================

CATEGORY_TO_DEPARTMENT = {
    # Compliance
    "kyc_aml": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "customer_due_diligence": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "regulatory_reporting": {"department_id": "dept-compliance", "department": "Compliance", "role": "analyst"},
    "compliance_monitoring": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "policy_management": {"department_id": "dept-compliance", "department": "Compliance", "role": "head"},
    "general": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    "customer_protection": {"department_id": "dept-compliance", "department": "Compliance", "role": "manager"},
    
    # Risk
    "risk_management": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    "credit_risk": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    "operational_risk": {"department_id": "dept-risk", "department": "Risk Management", "role": "analyst"},
    "market_risk": {"department_id": "dept-risk", "department": "Risk Management", "role": "analyst"},
    "liquidity_risk": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    "concentration_risk": {"department_id": "dept-risk", "department": "Risk Management", "role": "manager"},
    
    # Legal
    "legal": {"department_id": "dept-legal", "department": "Legal", "role": "manager"},
    "governance": {"department_id": "dept-legal", "department": "Legal", "role": "head"},
    "contracts": {"department_id": "dept-legal", "department": "Legal", "role": "manager"},
    
    # IT
    "data_protection": {"department_id": "dept-it", "department": "Information Technology", "role": "officer"},
    "information_security": {"department_id": "dept-it", "department": "Information Technology", "role": "manager"},
    "cyber_security": {"department_id": "dept-it", "department": "Information Technology", "role": "manager"},
    "technology": {"department_id": "dept-it", "department": "Information Technology", "role": "manager"},
    
    # Operations
    "operational_procedures": {"department_id": "dept-operations", "department": "Operations", "role": "manager"},
    "customer_service": {"department_id": "dept-operations", "department": "Operations", "role": "manager"},
    "outsourcing": {"department_id": "dept-operations", "department": "Operations", "role": "head"},
    
    # Finance
    "reporting": {"department_id": "dept-finance", "department": "Finance & Accounts", "role": "manager"},
    "financial_reporting": {"department_id": "dept-finance", "department": "Finance & Accounts", "role": "manager"},
    "capital_management": {"department_id": "dept-finance", "department": "Finance & Accounts", "role": "head"},
    "asset_liability": {"department_id": "dept-finance", "department": "Finance & Accounts", "role": "manager"},
    
    # Audit
    "audit": {"department_id": "dept-audit", "department": "Internal Audit", "role": "manager"},
    "internal_controls": {"department_id": "dept-audit", "department": "Internal Audit", "role": "manager"},
    
    # HR
    "hr_policies": {"department_id": "dept-hr", "department": "Human Resources", "role": "manager"},
    "training": {"department_id": "dept-hr", "department": "Human Resources", "role": "manager"},
}


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class GapType(str, Enum):
    MISSING = "missing"           # No policy coverage at all
    CONFLICTING = "conflicting"   # Policy contradicts regulation
    WEAK = "weak"                 # Weaker language
    PARTIAL = "partial"           # Partial coverage
    COMPLIANT = "compliant"       # Full compliance
    EXCEEDS = "exceeds"           # Exceeds requirements


class GapSeverity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# Gap type to score mapping (0-100)
GAP_TYPE_SCORES = {
    GapType.COMPLIANT: 100,
    GapType.EXCEEDS: 100,
    GapType.WEAK: 70,
    GapType.PARTIAL: 50,
    GapType.MISSING: 0,
    GapType.CONFLICTING: 0,
}

# Criticality weights
CRITICALITY_WEIGHTS = {
    "high": 3,
    "medium": 2,
    "low": 1,
}


@dataclass
class RegulationGapResult:
    """Result of analyzing a single regulation clause against all policy clauses."""
    regulation_clause_id: str
    regulation_title: str
    regulation_text: str
    regulation_section: str
    subject_category: str
    requirement_type: str
    criticality: str
    compliance_indicators: List[str]
    key_obligations: List[str]
    
    # Matching result
    gap_type: GapType
    severity: GapSeverity
    confidence_score: float
    
    # Matched policy clauses (if any)
    matched_policy_clauses: List[Dict[str, Any]]
    primary_policy_match: Optional[Dict[str, Any]]
    
    # Gap details
    gap_description: str
    unfulfilled_indicators: List[str]  # Compliance indicators not addressed
    weak_elements: List[str]
    
    # Remediation
    suggested_action: str
    remediation_deadline: str  # "Immediate", "1 week", "1 month", "3 months"
    
    # Assignment
    assigned_department: str
    assigned_department_id: str
    assigned_role: str
    assigned_member_id: Optional[str] = None
    assigned_member_name: Optional[str] = None


@dataclass
class PriorityActionItem:
    """Action item generated from gap analysis."""
    action_id: str
    regulation_clause_id: str
    regulation_title: str
    gap_type: str
    severity: str
    action_description: str
    unfulfilled_indicators: List[str]
    
    # Assignment
    assigned_department: str
    assigned_department_id: str
    assigned_role: str
    deadline: str
    priority_rank: int
    assigned_member_id: Optional[str] = None
    assigned_member_name: Optional[str] = None


@dataclass
class RegulationFirstGapReport:
    """Complete gap analysis report with regulation-first approach."""
    report_id: str
    policy_id: str
    policy_title: str
    regulation_id: str
    regulation_title: str
    
    # Counts
    total_regulation_clauses: int
    total_policy_clauses: int
    
    # Coverage metrics
    fully_covered_count: int      # Compliant or exceeds
    partially_covered_count: int  # Partial or weak
    not_covered_count: int        # Missing or conflicting
    
    # Weighted compliance score
    compliance_score: float
    
    # Gap breakdown by severity
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    
    # Results
    gap_results: List[RegulationGapResult]
    
    # Priority actions (sorted by severity and criticality)
    priority_actions: List[PriorityActionItem]
    
    # Executive summary
    executive_summary: str
    
    # Bidirectional: Policy clauses with no regulation match
    policy_only_clauses: List[Dict[str, Any]]
    
    # Metadata
    analysis_timestamp: str
    llm_model: str


# =============================================================================
# REGULATION-FIRST GAP ANALYSIS SERVICE
# =============================================================================

class RegulationFirstGapAnalysisService:
    """
    Gap analysis service that treats regulations as the source of truth.
    
    For each regulation clause:
    1. Find matching policy clauses (tags → keywords → category → LLM)
    2. Use LLM to check if policy addresses compliance_indicators
    3. Identify gaps and severity
    4. Assign to appropriate department/person
    """
    
    def __init__(self, db=None):
        """
        Initialize the service.
        
        Args:
            db: MongoDB database instance for looking up department members
        """
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not found")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.db = db
    
    async def analyze(
        self,
        policy_clauses: List[Dict[str, Any]],
        regulation_clauses: List[Dict[str, Any]],
        policy_id: str,
        policy_title: str,
        regulation_id: str,
        regulation_title: str
    ) -> RegulationFirstGapReport:
        """
        Main entry point: Analyze regulation clauses against policy.
        
        Args:
            policy_clauses: Policy clause list
            regulation_clauses: Regulation clause list (SOURCE OF TRUTH)
            policy_id, policy_title: Policy identifiers
            regulation_id, regulation_title: Regulation identifiers
            
        Returns:
            RegulationFirstGapReport
        """
        logger.info(f"Starting REGULATION-FIRST gap analysis")
        logger.info(f"  Regulation: {regulation_title} ({len(regulation_clauses)} clauses)")
        logger.info(f"  Policy: {policy_title} ({len(policy_clauses)} clauses)")
        
        # Index policy clauses for efficient lookup
        policy_index = self._index_policy_clauses(policy_clauses)
        
        # Analyze each regulation clause
        gap_results: List[RegulationGapResult] = []
        addressed_policy_ids = set()
        
        # Process in batches of 3 for parallel processing
        batch_size = 3
        for i in range(0, len(regulation_clauses), batch_size):
            batch = regulation_clauses[i:i + batch_size]
            batch_results = await asyncio.gather(*[
                self._analyze_regulation_clause(reg_clause, policy_index, policy_clauses)
                for reg_clause in batch
            ])
            
            for result, matched_ids in batch_results:
                gap_results.append(result)
                addressed_policy_ids.update(matched_ids)
        
        # Find policy clauses with no regulation match (bidirectional)
        all_policy_ids = {p.get('clause_id', '') for p in policy_clauses}
        unmatched_policy_ids = all_policy_ids - addressed_policy_ids
        policy_only_clauses = [
            p for p in policy_clauses 
            if p.get('clause_id', '') in unmatched_policy_ids
        ]
        
        # Calculate metrics
        fully_covered = len([r for r in gap_results if r.gap_type in [GapType.COMPLIANT, GapType.EXCEEDS]])
        partially_covered = len([r for r in gap_results if r.gap_type in [GapType.PARTIAL, GapType.WEAK]])
        not_covered = len([r for r in gap_results if r.gap_type in [GapType.MISSING, GapType.CONFLICTING]])
        
        critical = len([r for r in gap_results if r.severity == GapSeverity.CRITICAL])
        high = len([r for r in gap_results if r.severity == GapSeverity.HIGH])
        medium = len([r for r in gap_results if r.severity == GapSeverity.MEDIUM])
        low = len([r for r in gap_results if r.severity == GapSeverity.LOW])
        
        # Calculate weighted compliance score
        compliance_score = self._calculate_weighted_score(gap_results)
        
        # Generate priority actions
        priority_actions = await self._generate_priority_actions(gap_results)
        
        # Generate executive summary
        executive_summary = await self._generate_executive_summary(
            gap_results, policy_title, regulation_title, compliance_score,
            fully_covered, partially_covered, not_covered
        )
        
        report = RegulationFirstGapReport(
            report_id=str(uuid.uuid4()),
            policy_id=policy_id,
            policy_title=policy_title,
            regulation_id=regulation_id,
            regulation_title=regulation_title,
            total_regulation_clauses=len(regulation_clauses),
            total_policy_clauses=len(policy_clauses),
            fully_covered_count=fully_covered,
            partially_covered_count=partially_covered,
            not_covered_count=not_covered,
            compliance_score=round(compliance_score, 1),
            critical_gaps=critical,
            high_gaps=high,
            medium_gaps=medium,
            low_gaps=low,
            gap_results=gap_results,
            priority_actions=priority_actions,
            executive_summary=executive_summary,
            policy_only_clauses=policy_only_clauses[:20],  # Limit for response size
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            llm_model=self.model
        )
        
        logger.info(f"Gap analysis complete. Score: {compliance_score:.1f}%")
        logger.info(f"  Covered: {fully_covered}, Partial: {partially_covered}, Missing: {not_covered}")
        
        return report
    
    def _index_policy_clauses(self, policy_clauses: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Index policy clauses by subject_category and tags for fast lookup."""
        index = {
            "by_category": {},
            "by_tag": {},
            "by_keyword": {},
            "all": policy_clauses
        }
        
        for clause in policy_clauses:
            # By category
            cat = clause.get('subject_category', 'general')
            if cat not in index["by_category"]:
                index["by_category"][cat] = []
            index["by_category"][cat].append(clause)
            
            # By tag
            for tag in clause.get('tags', []):
                tag_lower = tag.lower()
                if tag_lower not in index["by_tag"]:
                    index["by_tag"][tag_lower] = []
                index["by_tag"][tag_lower].append(clause)
            
            # By keyword
            for kw in clause.get('keywords', []):
                kw_lower = kw.lower()
                if kw_lower not in index["by_keyword"]:
                    index["by_keyword"][kw_lower] = []
                index["by_keyword"][kw_lower].append(clause)
        
        return index
    
    async def _analyze_regulation_clause(
        self,
        reg_clause: Dict[str, Any],
        policy_index: Dict[str, List[Dict]],
        all_policy_clauses: List[Dict[str, Any]]
    ) -> Tuple[RegulationGapResult, set]:
        """
        Analyze a single regulation clause against all policy clauses.
        
        Returns:
            Tuple of (RegulationGapResult, set of matched policy clause IDs)
        """
        reg_id = reg_clause.get('clause_id', str(uuid.uuid4()))
        reg_category = reg_clause.get('subject_category', 'general')
        reg_tags = set(t.lower() for t in reg_clause.get('tags', []))
        reg_keywords = set(k.lower() for k in reg_clause.get('keywords', []))
        compliance_indicators = reg_clause.get('compliance_indicators', [])
        
        # Step 1: Find matching policy clauses (multi-level)
        matched_policies = set()
        matched_policy_list = []
        
        # Level 1: Tag matching (most specific)
        for tag in reg_tags:
            for policy in policy_index["by_tag"].get(tag, []):
                p_id = policy.get('clause_id', '')
                if p_id and p_id not in matched_policies:
                    matched_policies.add(p_id)
                    matched_policy_list.append(policy)
        
        # Level 2: Keyword matching
        if len(matched_policy_list) < 3:
            for kw in reg_keywords:
                for policy in policy_index["by_keyword"].get(kw, []):
                    p_id = policy.get('clause_id', '')
                    if p_id and p_id not in matched_policies:
                        matched_policies.add(p_id)
                        matched_policy_list.append(policy)
                        if len(matched_policy_list) >= 5:
                            break
        
        # Level 3: Category matching
        if len(matched_policy_list) < 3:
            for policy in policy_index["by_category"].get(reg_category, []):
                p_id = policy.get('clause_id', '')
                if p_id and p_id not in matched_policies:
                    matched_policies.add(p_id)
                    matched_policy_list.append(policy)
                    if len(matched_policy_list) >= 5:
                        break
        
        # Level 4: LLM semantic matching (if still no matches and we have a client)
        if len(matched_policy_list) == 0 and self.client and len(all_policy_clauses) > 0:
            semantic_matches = await self._llm_semantic_match(reg_clause, all_policy_clauses[:30])
            matched_policy_list = semantic_matches
            matched_policies = {p.get('clause_id', '') for p in semantic_matches}
        
        # Step 2: Use LLM to check if policy addresses compliance indicators
        if matched_policy_list and self.client:
            gap_result = await self._llm_check_compliance_indicators(
                reg_clause, matched_policy_list, compliance_indicators
            )
        else:
            # No match found - this is a MISSING gap (Critical)
            gap_result = self._create_missing_gap(reg_clause)
        
        return gap_result, matched_policies
    
    async def _llm_semantic_match(
        self,
        reg_clause: Dict[str, Any],
        policy_clauses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use LLM to find semantically matching policy clauses."""
        try:
            policy_summaries = "\n".join([
                f"{i+1}. [{p.get('clause_id', '')[:8]}] {p.get('title', 'Untitled')}: {p.get('semantic_summary', p.get('original_text', '')[:200])}"
                for i, p in enumerate(policy_clauses[:15])
            ])
            
            system_prompt = "You are a compliance expert matching regulation requirements to policy clauses."
            user_prompt = f"""Find policy clauses that address this regulation requirement.

REGULATION:
Title: {reg_clause.get('title', 'Untitled')}
Text: {reg_clause.get('original_text', '')[:500]}
Key Obligations: {', '.join(reg_clause.get('key_obligations', []))}

POLICY CLAUSES:
{policy_summaries}

Return JSON with indices of matching policies (1-indexed):
{{"matching_indices": [1, 3, 5]}}

If no match, return: {{"matching_indices": []}}"""

            response = await asyncio.to_thread(
                self._call_claude, system_prompt, user_prompt, 512
            )
            
            clean = response.strip()
            if clean.startswith("```"):
                clean = re.sub(r'^```(?:json)?\n?', '', clean)
                clean = re.sub(r'\n?```$', '', clean)
            
            result = json.loads(clean)
            indices = result.get('matching_indices', [])
            
            return [policy_clauses[i-1] for i in indices if 1 <= i <= len(policy_clauses)]
            
        except Exception as e:
            logger.error(f"LLM semantic match failed: {e}")
            return []
    
    async def _llm_check_compliance_indicators(
        self,
        reg_clause: Dict[str, Any],
        matched_policies: List[Dict[str, Any]],
        compliance_indicators: List[str]
    ) -> RegulationGapResult:
        """Use LLM to check if policy clauses fulfill compliance indicators."""
        try:
            policy_texts = "\n\n".join([
                f"POLICY CLAUSE {i+1}:\nTitle: {p.get('title', 'Untitled')}\nText: {p.get('original_text', '')[:600]}\nObligations: {', '.join(p.get('key_obligations', []))}"
                for i, p in enumerate(matched_policies[:5])
            ])
            
            indicators_text = "\n".join([f"  - {ind}" for ind in compliance_indicators]) if compliance_indicators else "  (No specific indicators defined)"
            
            system_prompt = """You are an expert compliance auditor. The REGULATION is the SOURCE OF TRUTH.
Check if the policy clauses FULLY address all compliance indicators from the regulation."""

            user_prompt = f"""REGULATION REQUIREMENT (Source of Truth):
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

            response = await asyncio.to_thread(
                self._call_claude, system_prompt, user_prompt, 2048
            )
            
            clean = response.strip()
            if clean.startswith("```"):
                clean = re.sub(r'^```(?:json)?\n?', '', clean)
                clean = re.sub(r'\n?```$', '', clean)
            
            result = json.loads(clean)
            
            # Get assignment info
            category = reg_clause.get('subject_category', 'general')
            dept_info = CATEGORY_TO_DEPARTMENT.get(category, CATEGORY_TO_DEPARTMENT['general'])
            
            # Determine deadline based on severity
            severity = GapSeverity(result.get('severity', 'Medium'))
            deadline = {
                GapSeverity.CRITICAL: "Immediate",
                GapSeverity.HIGH: "1 week",
                GapSeverity.MEDIUM: "1 month",
                GapSeverity.LOW: "3 months"
            }.get(severity, "1 month")
            
            # Get primary policy match
            primary_idx = result.get('primary_policy_index', 1) - 1
            primary_policy = matched_policies[primary_idx] if 0 <= primary_idx < len(matched_policies) else matched_policies[0] if matched_policies else None
            
            return RegulationGapResult(
                regulation_clause_id=reg_clause.get('clause_id', ''),
                regulation_title=reg_clause.get('title', 'Untitled'),
                regulation_text=reg_clause.get('original_text', '')[:500],
                regulation_section=reg_clause.get('section', ''),
                subject_category=category,
                requirement_type=reg_clause.get('requirement_type', 'mandatory'),
                criticality=reg_clause.get('criticality', 'high'),
                compliance_indicators=compliance_indicators,
                key_obligations=reg_clause.get('key_obligations', []),
                gap_type=GapType(result.get('gap_type', 'partial')),
                severity=severity,
                confidence_score=result.get('confidence_score', 0.7),
                matched_policy_clauses=[{
                    'clause_id': p.get('clause_id', ''),
                    'title': p.get('title', ''),
                    'text': p.get('original_text', '')[:300]
                } for p in matched_policies],
                primary_policy_match={
                    'clause_id': primary_policy.get('clause_id', ''),
                    'title': primary_policy.get('title', ''),
                    'text': primary_policy.get('original_text', '')[:500]
                } if primary_policy else None,
                gap_description=result.get('gap_description', ''),
                unfulfilled_indicators=result.get('unfulfilled_indicators', []),
                weak_elements=result.get('weak_elements', []),
                suggested_action=result.get('suggested_action', 'Review and update policy'),
                remediation_deadline=deadline,
                assigned_department=dept_info['department'],
                assigned_department_id=dept_info['department_id'],
                assigned_role=dept_info['role']
            )
            
        except Exception as e:
            logger.error(f"LLM compliance check failed: {e}")
            return self._create_fallback_gap(reg_clause, matched_policies)
    
    def _create_missing_gap(self, reg_clause: Dict[str, Any]) -> RegulationGapResult:
        """Create gap result when no policy match is found."""
        category = reg_clause.get('subject_category', 'general')
        dept_info = CATEGORY_TO_DEPARTMENT.get(category, CATEGORY_TO_DEPARTMENT['general'])
        criticality = reg_clause.get('criticality', 'high')
        
        # Missing + high criticality = Critical severity
        severity = GapSeverity.CRITICAL if criticality == 'high' else GapSeverity.HIGH
        
        return RegulationGapResult(
            regulation_clause_id=reg_clause.get('clause_id', ''),
            regulation_title=reg_clause.get('title', 'Untitled'),
            regulation_text=reg_clause.get('original_text', '')[:500],
            regulation_section=reg_clause.get('section', ''),
            subject_category=category,
            requirement_type=reg_clause.get('requirement_type', 'mandatory'),
            criticality=criticality,
            compliance_indicators=reg_clause.get('compliance_indicators', []),
            key_obligations=reg_clause.get('key_obligations', []),
            gap_type=GapType.MISSING,
            severity=severity,
            confidence_score=0.95,  # High confidence for missing
            matched_policy_clauses=[],
            primary_policy_match=None,
            gap_description=f"No policy clause addresses this regulation requirement: {reg_clause.get('title', '')}",
            unfulfilled_indicators=reg_clause.get('compliance_indicators', []),
            weak_elements=[],
            suggested_action=f"Create new policy clause addressing: {', '.join(reg_clause.get('key_obligations', [])[:3])}",
            remediation_deadline="Immediate" if severity == GapSeverity.CRITICAL else "1 week",
            assigned_department=dept_info['department'],
            assigned_department_id=dept_info['department_id'],
            assigned_role=dept_info['role']
        )
    
    def _create_fallback_gap(
        self, 
        reg_clause: Dict[str, Any], 
        matched_policies: List[Dict[str, Any]]
    ) -> RegulationGapResult:
        """Create fallback gap when LLM fails."""
        category = reg_clause.get('subject_category', 'general')
        dept_info = CATEGORY_TO_DEPARTMENT.get(category, CATEGORY_TO_DEPARTMENT['general'])
        
        return RegulationGapResult(
            regulation_clause_id=reg_clause.get('clause_id', ''),
            regulation_title=reg_clause.get('title', 'Untitled'),
            regulation_text=reg_clause.get('original_text', '')[:500],
            regulation_section=reg_clause.get('section', ''),
            subject_category=category,
            requirement_type=reg_clause.get('requirement_type', 'mandatory'),
            criticality=reg_clause.get('criticality', 'high'),
            compliance_indicators=reg_clause.get('compliance_indicators', []),
            key_obligations=reg_clause.get('key_obligations', []),
            gap_type=GapType.PARTIAL,
            severity=GapSeverity.MEDIUM,
            confidence_score=0.3,
            matched_policy_clauses=[{
                'clause_id': p.get('clause_id', ''),
                'title': p.get('title', '')
            } for p in matched_policies],
            primary_policy_match=None,
            gap_description="Automated analysis incomplete - manual review required",
            unfulfilled_indicators=["Manual verification needed"],
            weak_elements=[],
            suggested_action="Manual review by compliance officer required",
            remediation_deadline="1 week",
            assigned_department=dept_info['department'],
            assigned_department_id=dept_info['department_id'],
            assigned_role="manager"
        )
    
    def _calculate_weighted_score(self, gap_results: List[RegulationGapResult]) -> float:
        """
        Calculate weighted compliance score.
        
        Formula:
        - Each regulation gets a score based on gap_type (0-100)
        - Weighted by criticality (high=3, medium=2, low=1)
        - Final score = weighted_sum / max_possible_weighted_sum * 100
        """
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
    
    async def _generate_priority_actions(
        self,
        gap_results: List[RegulationGapResult]
    ) -> List[PriorityActionItem]:
        """Generate priority action items from gaps."""
        # Filter non-compliant gaps
        non_compliant = [
            r for r in gap_results 
            if r.gap_type not in [GapType.COMPLIANT, GapType.EXCEEDS]
        ]
        
        # Sort by severity (Critical > High > Medium > Low) and criticality
        severity_order = {
            GapSeverity.CRITICAL: 0,
            GapSeverity.HIGH: 1,
            GapSeverity.MEDIUM: 2,
            GapSeverity.LOW: 3
        }
        criticality_order = {"high": 0, "medium": 1, "low": 2}
        
        sorted_gaps = sorted(
            non_compliant,
            key=lambda r: (severity_order.get(r.severity, 2), criticality_order.get(r.criticality, 1))
        )
        
        # Lookup members from database if available
        member_cache = {}
        if self.db:
            try:
                members = await self.db.department_members.find({}).to_list(100)
                for m in members:
                    key = (m.get('department_id', ''), m.get('role', ''))
                    if key not in member_cache:
                        member_cache[key] = m
            except Exception as e:
                logger.warning(f"Could not load department members: {e}")
        
        actions = []
        for rank, gap in enumerate(sorted_gaps[:30], 1):  # Top 30 priority actions
            # Find assigned member
            member_key = (gap.assigned_department_id, gap.assigned_role)
            member = member_cache.get(member_key)
            
            action = PriorityActionItem(
                action_id=str(uuid.uuid4()),
                regulation_clause_id=gap.regulation_clause_id,
                regulation_title=gap.regulation_title,
                gap_type=gap.gap_type.value,
                severity=gap.severity.value,
                action_description=gap.suggested_action,
                unfulfilled_indicators=gap.unfulfilled_indicators[:5],
                assigned_department=gap.assigned_department,
                assigned_department_id=gap.assigned_department_id,
                assigned_role=gap.assigned_role,
                assigned_member_id=member.get('id') if member else None,
                assigned_member_name=member.get('name') if member else None,
                deadline=gap.remediation_deadline,
                priority_rank=rank
            )
            actions.append(action)
        
        return actions
    
    async def _generate_executive_summary(
        self,
        gap_results: List[RegulationGapResult],
        policy_title: str,
        regulation_title: str,
        compliance_score: float,
        fully_covered: int,
        partially_covered: int,
        not_covered: int
    ) -> str:
        """Generate executive summary."""
        critical = len([r for r in gap_results if r.severity == GapSeverity.CRITICAL])
        high = len([r for r in gap_results if r.severity == GapSeverity.HIGH])
        
        if self.client:
            try:
                system_prompt = "You are a Chief Compliance Officer preparing a brief executive summary for the Board."
                user_prompt = f"""Generate a 2-paragraph executive summary for this gap analysis.

Policy: {policy_title}
Regulation: {regulation_title}

Compliance Score: {compliance_score:.1f}%
Fully Covered: {fully_covered} clauses
Partially Covered: {partially_covered} clauses
Not Covered: {not_covered} clauses
Critical Gaps: {critical}
High Priority Gaps: {high}

The summary should highlight:
1. Overall compliance posture
2. Key risk areas requiring immediate attention
3. Recommended next steps

Keep it concise (2 paragraphs max). Return plain text, no JSON."""

                response = await asyncio.to_thread(
                    self._call_claude, system_prompt, user_prompt, 1024
                )
                return response.strip()
                
            except Exception as e:
                logger.error(f"Executive summary generation failed: {e}")
        
        # Fallback
        return f"""The gap analysis of "{policy_title}" against "{regulation_title}" shows a compliance score of {compliance_score:.1f}%. Out of {len(gap_results)} regulation requirements analyzed, {fully_covered} are fully addressed, {partially_covered} are partially covered, and {not_covered} have no policy coverage.

There are {critical} critical gaps and {high} high-priority gaps requiring immediate attention. Recommend prioritizing critical gaps within 48 hours and high-priority gaps within 1 week. A detailed remediation plan should be developed with assigned owners from the relevant departments."""
    
    def _call_claude(self, system_message: str, user_message: str, max_tokens: int = 4096) -> str:
        """Synchronous helper to call Claude API."""
        if not self.client:
            raise ValueError("Anthropic client not initialized")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_message,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def run_regulation_first_gap_analysis(
    policy_clauses: List[Dict[str, Any]],
    regulation_clauses: List[Dict[str, Any]],
    policy_id: str,
    policy_title: str,
    regulation_id: str,
    regulation_title: str,
    db=None
) -> RegulationFirstGapReport:
    """Convenience function to run regulation-first gap analysis."""
    service = RegulationFirstGapAnalysisService(db=db)
    return await service.analyze(
        policy_clauses=policy_clauses,
        regulation_clauses=regulation_clauses,
        policy_id=policy_id,
        policy_title=policy_title,
        regulation_id=regulation_id,
        regulation_title=regulation_title
    )


def gap_report_to_dict(report: RegulationFirstGapReport) -> Dict[str, Any]:
    """Convert RegulationFirstGapReport to dictionary."""
    return {
        "report_id": report.report_id,
        "policy_id": report.policy_id,
        "policy_title": report.policy_title,
        "regulation_id": report.regulation_id,
        "regulation_title": report.regulation_title,
        "total_regulation_clauses": report.total_regulation_clauses,
        "total_policy_clauses": report.total_policy_clauses,
        "fully_covered_count": report.fully_covered_count,
        "partially_covered_count": report.partially_covered_count,
        "not_covered_count": report.not_covered_count,
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
                "regulation_section": r.regulation_section,
                "requirement_type": r.requirement_type,
                "criticality": r.criticality,
                "gap_type": r.gap_type.value,
                "severity": r.severity.value,
                "confidence_score": r.confidence_score,
                "gap_description": r.gap_description,
                "unfulfilled_indicators": r.unfulfilled_indicators,
                "matched_policy_count": len(r.matched_policy_clauses),
                "primary_policy": r.primary_policy_match,
                "suggested_action": r.suggested_action,
                "assigned_department": r.assigned_department,
                "assigned_role": r.assigned_role,
                "deadline": r.remediation_deadline
            }
            for r in report.gap_results
        ],
        "priority_actions": [
            {
                "action_id": a.action_id,
                "priority_rank": a.priority_rank,
                "regulation_title": a.regulation_title,
                "gap_type": a.gap_type,
                "severity": a.severity,
                "action_description": a.action_description,
                "unfulfilled_indicators": a.unfulfilled_indicators,
                "assigned_department": a.assigned_department,
                "assigned_member_name": a.assigned_member_name,
                "assigned_role": a.assigned_role,
                "deadline": a.deadline
            }
            for a in report.priority_actions
        ],
        "policy_only_clauses_count": len(report.policy_only_clauses)
    }
