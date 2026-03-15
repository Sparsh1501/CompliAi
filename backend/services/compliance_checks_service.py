"""
PA/PG Compliance Checks Service for CompliAI

Provides domain-specific compliance checks for:
- Merchant onboarding (Task #6)
- Settlement operations (Task #7)
- Escrow and nodal accounts (Task #27)
- Fraud monitoring (Task #28)
- PA-P physical terminal compliance (Task #24)

Each check category evaluates organization profile data and gap analysis
results against RBI PA/PG Master Direction requirements.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ComplianceChecksService:
    """Domain-specific compliance checks for PA/PG regulations."""

    def __init__(self, db=None, org_profile_service=None):
        self.db = db
        self.org_profile_service = org_profile_service

    async def _get_org_context(self, user_id: str) -> Dict[str, Any]:
        """Get organization profile and entity context."""
        user_doc = await self.db.users.find_one({"id": user_id}, {"organization": 1, "_id": 0})
        organization = (user_doc or {}).get('organization', 'Default Org')
        profile = await self.org_profile_service.get_profile(organization) if self.org_profile_service else None
        return {
            "organization": organization,
            "profile": profile or {},
            "entity_type": (profile or {}).get('entity_type', 'unknown'),
        }

    async def _get_latest_gap_analysis(self, organization: str, category_filter: str = None) -> List[Dict]:
        """Get gaps from the latest gap analysis for the org."""
        latest = await self.db.gap_analyses.find_one(
            {"organization": organization},
            {"_id": 0, "gaps": 1},
            sort=[("created_at", -1)]
        )
        if not latest:
            return []
        gaps = latest.get("gaps", [])
        if category_filter:
            gaps = [g for g in gaps if g.get("metadata", {}).get("subject_category") == category_filter]
        return gaps

    # =================================================================
    # MERCHANT ONBOARDING COMPLIANCE (Task #6)
    # =================================================================

    async def check_merchant_onboarding(self, user_id: str) -> Dict[str, Any]:
        """Check merchant onboarding compliance against RBI requirements."""
        ctx = await self._get_org_context(user_id)
        profile = ctx["profile"]
        checks = []

        # Merchant KYC Policy
        checks.append({
            "requirement_id": "RBI-PAPG-MER-001",
            "title": "Merchant Due Diligence (KYC)",
            "status": "needs_evidence",
            "details": "Requires Board-approved merchant KYC policy document",
            "criticality": "high",
            "evidence_required": ["Merchant KYC policy", "KYC checklist", "Background verification process"],
        })

        # Merchant Agreement
        checks.append({
            "requirement_id": "RBI-PAPG-MER-002",
            "title": "Merchant Agreement Requirements",
            "status": "needs_evidence",
            "details": "Standard merchant agreement with data security and refund clauses",
            "criticality": "medium",
            "evidence_required": ["Merchant agreement template", "Data security clauses"],
        })

        # Ongoing Monitoring
        checks.append({
            "requirement_id": "RBI-PAPG-MER-003",
            "title": "Ongoing Merchant Monitoring",
            "status": "needs_evidence",
            "details": "Transaction monitoring and periodic merchant review",
            "criticality": "high",
            "evidence_required": ["Transaction monitoring system", "Merchant risk categorization"],
        })

        # Website compliance
        checks.append({
            "requirement_id": "RBI-PAPG-MER-004",
            "title": "Merchant Website/App Compliance",
            "status": "needs_evidence",
            "details": "Merchants display PA details and refund policy",
            "criticality": "medium",
            "evidence_required": ["Website compliance checklist", "Periodic audit reports"],
        })

        # KYC completion for existing merchants
        checks.append({
            "requirement_id": "RBI-PAPG-MER-005",
            "title": "Pre-2026 Merchant KYC Completion",
            "status": "needs_evidence",
            "details": f"KYC completion for {profile.get('merchant_count', 'unknown')} merchants",
            "criticality": "high",
            "evidence_required": ["KYC completion tracker", "Timeline compliance dashboard"],
        })

        # Enrich with gap analysis data if available
        gaps = await self._get_latest_gap_analysis(ctx["organization"], "merchant_onboarding")
        checks = self._enrich_with_gaps(checks, gaps)

        compliant = len([c for c in checks if c['status'] == 'compliant'])
        return self._build_result("merchant_onboarding", checks, compliant)

    # =================================================================
    # SETTLEMENT OPERATIONS COMPLIANCE (Task #7)
    # =================================================================

    async def check_settlement_operations(self, user_id: str) -> Dict[str, Any]:
        """Check settlement and operations compliance."""
        ctx = await self._get_org_context(user_id)
        checks = []

        checks.append({
            "requirement_id": "RBI-PAPG-SET-001",
            "title": "Settlement Timeline (T+1)",
            "status": "needs_evidence",
            "details": "Settlement to merchants within T+1 business day",
            "criticality": "high",
            "evidence_required": ["T+1 settlement SLA", "Settlement processing system", "Delay monitoring"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-SET-002",
            "title": "Daily Settlement Reconciliation",
            "status": "needs_evidence",
            "details": "Daily reconciliation of transactions and settlements",
            "criticality": "high",
            "evidence_required": ["Reconciliation process", "Automated system", "Audit trail"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-SET-003",
            "title": "Refund Processing Timeline",
            "status": "needs_evidence",
            "details": "Customer refunds within prescribed timeline",
            "criticality": "medium",
            "evidence_required": ["Refund SLA", "Tracking system", "Customer notification"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-SET-004",
            "title": "Failed Transaction Auto-Reversal",
            "status": "needs_evidence",
            "details": "Auto-reversal mechanism for failed transactions",
            "criticality": "high",
            "evidence_required": ["Auto-reversal mechanism", "Failed transaction monitoring", "TAT reporting"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-SET-005",
            "title": "No Charge on Failed Transactions",
            "status": "needs_evidence",
            "details": "Zero charges on failed transactions",
            "criticality": "medium",
            "evidence_required": ["Pricing policy", "System configuration", "Complaint monitoring"],
        })

        gaps = await self._get_latest_gap_analysis(ctx["organization"], "settlement_operations")
        checks = self._enrich_with_gaps(checks, gaps)

        compliant = len([c for c in checks if c['status'] == 'compliant'])
        return self._build_result("settlement_operations", checks, compliant)

    # =================================================================
    # ESCROW AND NODAL ACCOUNT COMPLIANCE (Task #27)
    # =================================================================

    async def check_escrow_compliance(self, user_id: str) -> Dict[str, Any]:
        """Check escrow and nodal account compliance."""
        ctx = await self._get_org_context(user_id)
        profile = ctx["profile"]
        checks = []

        checks.append({
            "requirement_id": "RBI-PAPG-ESC-001",
            "title": "Escrow Account with Scheduled Bank",
            "status": "compliant" if profile.get('escrow_bank_name') else "non_compliant",
            "details": f"Escrow bank: {profile.get('escrow_bank_name', 'Not configured')}",
            "criticality": "high",
        })

        checks.append({
            "requirement_id": "RBI-PAPG-ESC-002",
            "title": "Escrow Fund Flow Compliance",
            "status": "needs_evidence",
            "details": "All collections via escrow, no commingling",
            "criticality": "high",
            "evidence_required": ["Fund flow diagram", "System configuration", "Reconciliation reports"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-ESC-003",
            "title": "Nodal Account Separation",
            "status": "compliant" if profile.get('nodal_account_bank') else "non_compliant",
            "details": f"Nodal bank: {profile.get('nodal_account_bank', 'Not configured')}",
            "criticality": "medium",
        })

        compliant = len([c for c in checks if c['status'] == 'compliant'])
        return self._build_result("escrow_accounts", checks, compliant)

    # =================================================================
    # FRAUD MONITORING COMPLIANCE (Task #28)
    # =================================================================

    async def check_fraud_monitoring(self, user_id: str) -> Dict[str, Any]:
        """Check fraud monitoring and transaction surveillance compliance."""
        ctx = await self._get_org_context(user_id)
        checks = []

        checks.append({
            "requirement_id": "RBI-PAPG-FRM-001",
            "title": "Fraud Risk Management Framework",
            "status": "needs_evidence",
            "details": "Board-approved fraud risk management policy",
            "criticality": "high",
            "evidence_required": ["Board-approved fraud policy", "Risk assessment", "Prevention controls"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-FRM-002",
            "title": "Real-time Transaction Monitoring",
            "status": "needs_evidence",
            "details": "Real-time monitoring with rule-based and ML-based detection",
            "criticality": "high",
            "evidence_required": ["Monitoring system", "Detection mechanisms", "Alert disposition process"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-FRM-003",
            "title": "Fraud Reporting to RBI",
            "status": "needs_evidence",
            "details": "Fraud incident reporting per RBI timelines and formats",
            "criticality": "high",
            "evidence_required": ["Reporting process", "RBI format templates", "Incident register"],
        })

        checks.append({
            "requirement_id": "RBI-PAPG-FRM-004",
            "title": "Chargeback Management",
            "status": "needs_evidence",
            "details": "Structured chargeback process with customer notification",
            "criticality": "medium",
            "evidence_required": ["Chargeback policy", "Processing SLA", "Merchant liability framework"],
        })

        gaps = await self._get_latest_gap_analysis(ctx["organization"], "fraud_monitoring")
        checks = self._enrich_with_gaps(checks, gaps)

        compliant = len([c for c in checks if c['status'] == 'compliant'])
        return self._build_result("fraud_monitoring", checks, compliant)

    # =================================================================
    # PA-P PHYSICAL COMPLIANCE (Task #24)
    # =================================================================

    async def check_pa_p_compliance(self, user_id: str) -> Dict[str, Any]:
        """Check PA-P specific physical terminal compliance."""
        ctx = await self._get_org_context(user_id)
        profile = ctx["profile"]
        checks = []

        if ctx["entity_type"] != "pa_p":
            return {
                "category": "pa_p_physical",
                "applicable": False,
                "message": "PA-P checks only apply to PA-P (physical POS) entities",
                "total_checks": 0, "compliant": 0, "score": 100, "checks": [],
            }

        checks.append({
            "requirement_id": "RBI-PAPG-PAP-001",
            "title": "PA-P Registration",
            "status": "compliant" if profile.get('license_status') in ('authorized', 'conditional') else "non_compliant",
            "details": f"PA-P license status: {profile.get('license_status', 'unknown')}",
            "criticality": "high",
        })

        checks.append({
            "requirement_id": "RBI-PAPG-PAP-002",
            "title": "Terminal Security and Tamper-Proofing",
            "status": "needs_evidence",
            "details": "Secure, tamper-proof terminals with regular inspections",
            "criticality": "high",
            "evidence_required": ["Terminal security certification", "Tamper detection", "Inspection reports"],
        })

        compliant = len([c for c in checks if c['status'] == 'compliant'])
        return self._build_result("pa_p_physical", checks, compliant)

    # =================================================================
    # AGGREGATE ALL CHECKS
    # =================================================================

    async def run_all_checks(self, user_id: str) -> Dict[str, Any]:
        """Run all compliance check categories and aggregate results."""
        results = {}
        all_checks = []

        for name, method in [
            ("merchant_onboarding", self.check_merchant_onboarding),
            ("settlement_operations", self.check_settlement_operations),
            ("escrow_accounts", self.check_escrow_compliance),
            ("fraud_monitoring", self.check_fraud_monitoring),
            ("pa_p_physical", self.check_pa_p_compliance),
        ]:
            try:
                result = await method(user_id)
                results[name] = result
                all_checks.extend(result.get("checks", []))
            except Exception as e:
                logger.error(f"Compliance check {name} failed: {e}")
                results[name] = {"category": name, "error": str(e), "checks": []}

        total = len(all_checks)
        compliant = len([c for c in all_checks if c.get('status') == 'compliant'])

        return {
            "overall_score": round((compliant / total) * 100, 1) if total else 0,
            "total_checks": total,
            "compliant": compliant,
            "needs_evidence": len([c for c in all_checks if c.get('status') == 'needs_evidence']),
            "non_compliant": len([c for c in all_checks if c.get('status') == 'non_compliant']),
            "categories": results,
        }

    # =================================================================
    # HELPERS
    # =================================================================

    def _enrich_with_gaps(self, checks: List[Dict], gaps: List[Dict]) -> List[Dict]:
        """Enrich check status from gap analysis results if available."""
        if not gaps:
            return checks

        for check in checks:
            if check.get("status") != "needs_evidence":
                continue
            # Try to find matching gap by requirement title keywords
            req_title = check.get("title", "").lower()
            for gap in gaps:
                gap_desc = (gap.get("description") or "").lower()
                if any(word in gap_desc for word in req_title.split()[:3]):
                    gap_type = gap.get("gap_type", "missing")
                    if gap_type in ("compliant", "exceeds"):
                        check["status"] = "compliant"
                    elif gap_type in ("partial", "weak"):
                        check["status"] = "partial"
                    break
        return checks

    def _build_result(self, category: str, checks: List[Dict], compliant: int) -> Dict:
        total = len(checks)
        return {
            "category": category,
            "total_checks": total,
            "compliant": compliant,
            "needs_evidence": len([c for c in checks if c.get('status') == 'needs_evidence']),
            "non_compliant": len([c for c in checks if c.get('status') == 'non_compliant']),
            "score": round((compliant / total) * 100, 1) if total else 0,
            "checks": checks,
        }
