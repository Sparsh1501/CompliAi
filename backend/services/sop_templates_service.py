"""
PA SOP Templates Library for CompliAI (Task #12)

Pre-built Standard Operating Procedure templates for common PA/PG compliance areas.
Each template provides structured procedures that can be customized per organization.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Pre-built SOP templates for PA/PG compliance
SOP_TEMPLATES = {
    "merchant_kyc": {
        "id": "sop-tpl-merchant-kyc",
        "title": "Merchant KYC and Due Diligence SOP",
        "category": "merchant_onboarding",
        "entity_types": ["non_bank_pa", "bank_pa", "pa_p"],
        "rbi_references": ["RBI MD Para 7.1", "RBI MD Para 7.2"],
        "sections": [
            {
                "heading": "1. Objective",
                "content": "To establish a standardized procedure for conducting Know Your Customer (KYC) and due diligence checks on all merchants before onboarding onto the payment aggregation platform."
            },
            {
                "heading": "2. Scope",
                "content": "Applicable to all new merchant onboarding requests, existing merchant re-KYC, and periodic merchant reviews."
            },
            {
                "heading": "3. Procedure",
                "sub_sections": [
                    {"heading": "3.1 Document Collection", "content": "Collect: PAN, GST certificate, Certificate of Incorporation/Registration, Board resolution (if company), Address proof of registered office, Identity proof of authorized signatory."},
                    {"heading": "3.2 Verification", "content": "Verify PAN via NSDL/UTIITSL. Cross-check GST details on GST portal. Validate CIN on MCA portal. Perform CIBIL check on proprietor/directors."},
                    {"heading": "3.3 Risk Categorization", "content": "Categorize merchant as Low/Medium/High risk based on: business type, transaction volume, geography, industry vertical, online/offline model."},
                    {"heading": "3.4 Approval", "content": "Low risk: Auto-approved by system. Medium risk: Compliance Officer approval. High risk: CCO + Board committee approval."},
                    {"heading": "3.5 Ongoing Monitoring", "content": "Quarterly review for high-risk. Semi-annual for medium. Annual for low-risk. Trigger re-KYC on material change."},
                ]
            },
            {
                "heading": "4. Responsible Parties",
                "content": "Merchant Onboarding Team (initiation), Compliance Officer (verification), CCO (high-risk approval), IT Team (system configuration)."
            },
            {
                "heading": "5. Verification Checklist",
                "content": "[ ] PAN verified\n[ ] GST verified\n[ ] CIN/Registration verified\n[ ] CIBIL check completed\n[ ] Risk category assigned\n[ ] Approval obtained per category\n[ ] Merchant agreement signed\n[ ] System onboarding completed"
            },
        ],
        "review_frequency": "annual",
    },
    "settlement_process": {
        "id": "sop-tpl-settlement",
        "title": "Settlement and Reconciliation SOP",
        "category": "settlement_operations",
        "entity_types": ["non_bank_pa", "bank_pa"],
        "rbi_references": ["RBI MD Para 9.1", "RBI MD Para 9.2", "RBI MD Para 9.3"],
        "sections": [
            {
                "heading": "1. Objective",
                "content": "To define the end-to-end settlement process ensuring timely merchant payouts within T+1 business day as mandated by RBI."
            },
            {
                "heading": "2. Daily Settlement Cycle",
                "sub_sections": [
                    {"heading": "2.1 Transaction Capture", "content": "All successful transactions captured by EOD (T). Transaction files reconciled against acquiring bank files."},
                    {"heading": "2.2 Reconciliation", "content": "Automated reconciliation at T+0 EOD. Exception handling for mismatches within 4 hours. Escalation to Settlement Manager for unresolved items."},
                    {"heading": "2.3 Settlement Execution", "content": "Net settlement amount calculated per merchant. Commission/MDR deducted. NEFT/RTGS/IMPS payout initiated by T+1 10:00 AM."},
                    {"heading": "2.4 Confirmation", "content": "Settlement confirmation sent to merchants. Dashboard updated. Failed payouts retried within 2 hours."},
                ]
            },
            {
                "heading": "3. Failed Transaction Handling",
                "content": "Auto-reversal within 5 business days. Customer notified via SMS/email. No charges levied on failed transactions. Reversal tracked in dispute management system."
            },
            {
                "heading": "4. Escalation Matrix",
                "content": "Level 1: Settlement Operations Team (0-4 hours). Level 2: Settlement Manager (4-8 hours). Level 3: CFO (>8 hours or >INR 10 Lakh)."
            },
        ],
        "review_frequency": "quarterly",
    },
    "escrow_management": {
        "id": "sop-tpl-escrow",
        "title": "Escrow Account Management SOP",
        "category": "escrow_accounts",
        "entity_types": ["non_bank_pa"],
        "rbi_references": ["RBI MD Para 8", "RBI MD Para 8.1"],
        "sections": [
            {
                "heading": "1. Objective",
                "content": "To ensure compliant management of escrow accounts as per RBI Master Direction, with proper fund segregation and audit trail."
            },
            {
                "heading": "2. Account Structure",
                "content": "Maintain escrow account with a scheduled commercial bank. Separate escrow for each payment instrument type if required. No commingling of PA's own funds with merchant funds."
            },
            {
                "heading": "3. Fund Flow Procedures",
                "sub_sections": [
                    {"heading": "3.1 Inflow", "content": "All customer payments credited to escrow account. Daily reconciliation of inflows against transaction records."},
                    {"heading": "3.2 Outflow", "content": "Settlement to merchants only from escrow. Commission deduction at source. Refunds processed from escrow within prescribed timelines."},
                    {"heading": "3.3 Monitoring", "content": "Daily balance verification. Weekly reconciliation report to CFO. Monthly escrow audit by internal audit team."},
                ]
            },
            {
                "heading": "4. Audit Requirements",
                "content": "Quarterly escrow audit by statutory auditor. Annual certification to RBI. Immediate reporting of any irregularity to CCO and Board."
            },
        ],
        "review_frequency": "quarterly",
    },
    "fraud_monitoring": {
        "id": "sop-tpl-fraud",
        "title": "Fraud Detection and Response SOP",
        "category": "fraud_monitoring",
        "entity_types": ["non_bank_pa", "bank_pa", "pa_p"],
        "rbi_references": ["RBI MD Para 10", "RBI MD Para 10.1"],
        "sections": [
            {
                "heading": "1. Objective",
                "content": "To establish procedures for real-time fraud detection, investigation, and reporting as mandated by RBI for payment aggregators."
            },
            {
                "heading": "2. Detection Mechanisms",
                "sub_sections": [
                    {"heading": "2.1 Rule-Based Detection", "content": "Velocity checks (transactions per minute/hour). Amount thresholds. Geographic anomaly detection. Device fingerprinting."},
                    {"heading": "2.2 ML-Based Detection", "content": "Behavioral pattern analysis. Anomaly detection models. Merchant risk scoring. Network analysis for collusion."},
                ]
            },
            {
                "heading": "3. Alert Handling",
                "content": "P1 (Critical): Immediate block + investigate within 1 hour. P2 (High): Block + investigate within 4 hours. P3 (Medium): Flag + investigate within 24 hours. P4 (Low): Monitor + review in weekly cycle."
            },
            {
                "heading": "4. Incident Response",
                "sub_sections": [
                    {"heading": "4.1 Containment", "content": "Block suspicious merchant/transaction. Preserve transaction logs. Notify acquiring bank if needed."},
                    {"heading": "4.2 Investigation", "content": "Fraud team conducts investigation. Document findings in incident report. Determine loss amount and affected parties."},
                    {"heading": "4.3 Reporting", "content": "Report to RBI within prescribed timelines. File FIR if warranted. Report to FIU-IND for STR if applicable."},
                ]
            },
            {
                "heading": "5. Chargeback Process",
                "content": "Acknowledge within 24 hours. Investigate within 7 days. Resolve within 30 days. Merchant liability framework per agreement terms."
            },
        ],
        "review_frequency": "quarterly",
    },
    "data_security": {
        "id": "sop-tpl-datasec",
        "title": "Data Security and PCI-DSS Compliance SOP",
        "category": "technology_security",
        "entity_types": ["non_bank_pa", "bank_pa", "pa_p", "pg_only"],
        "rbi_references": ["RBI MD Para 11", "RBI MD Para 11.1", "PCI-DSS v4.0"],
        "sections": [
            {
                "heading": "1. Objective",
                "content": "To ensure data security compliance including PCI-DSS, data localization, and encryption requirements as per RBI Master Direction."
            },
            {
                "heading": "2. Card Data Handling",
                "content": "No storage of full card number, CVV, or PIN. Tokenization for recurring transactions. PCI-DSS Level 1 compliance mandatory."
            },
            {
                "heading": "3. Data Localization",
                "content": "All payment data stored within India. Data processing servers located in India. Cross-border data transfer only with RBI approval."
            },
            {
                "heading": "4. Access Controls",
                "sub_sections": [
                    {"heading": "4.1 Authentication", "content": "Multi-factor authentication for all admin access. Role-based access control. Quarterly access reviews."},
                    {"heading": "4.2 Encryption", "content": "AES-256 encryption at rest. TLS 1.2+ in transit. HSM for key management."},
                    {"heading": "4.3 Monitoring", "content": "24/7 SOC monitoring. SIEM integration. Quarterly vulnerability assessments. Annual penetration testing."},
                ]
            },
        ],
        "review_frequency": "annual",
    },
    "grievance_redressal": {
        "id": "sop-tpl-grievance",
        "title": "Customer Grievance Redressal SOP",
        "category": "customer_protection",
        "entity_types": ["non_bank_pa", "bank_pa", "pa_p"],
        "rbi_references": ["RBI MD Para 12", "RBI Integrated Ombudsman Scheme"],
        "sections": [
            {
                "heading": "1. Objective",
                "content": "To establish a structured grievance redressal mechanism for customers and merchants as mandated by RBI."
            },
            {
                "heading": "2. Grievance Channels",
                "content": "Dedicated customer support: email, phone, web portal. Complaint acknowledgement within 24 hours. Unique tracking number for every complaint."
            },
            {
                "heading": "3. Resolution Timelines",
                "sub_sections": [
                    {"heading": "3.1 Level 1", "content": "Customer support team: resolve within 48 hours."},
                    {"heading": "3.2 Level 2", "content": "Nodal Officer: escalation if unresolved in 48 hours, resolve within 7 days."},
                    {"heading": "3.3 Level 3", "content": "Principal Nodal Officer: final escalation, resolve within 30 days."},
                ]
            },
            {
                "heading": "4. RBI Ombudsman",
                "content": "Display Ombudsman details on website. Facilitate customer escalation to RBI Ombudsman if unresolved in 30 days."
            },
        ],
        "review_frequency": "annual",
    },
    "board_governance": {
        "id": "sop-tpl-governance",
        "title": "Board Governance and Compliance Reporting SOP",
        "category": "governance_compliance",
        "entity_types": ["non_bank_pa", "bank_pa"],
        "rbi_references": ["RBI MD Para 6", "RBI MD Para 6.1"],
        "sections": [
            {
                "heading": "1. Objective",
                "content": "To define governance procedures for Board oversight of PA compliance activities as required by RBI Master Direction."
            },
            {
                "heading": "2. Board Committee Structure",
                "content": "IT Strategy Committee (mandatory). Risk Management Committee. Audit Committee. Compliance oversight embedded in Board agenda."
            },
            {
                "heading": "3. Reporting Requirements",
                "sub_sections": [
                    {"heading": "3.1 Quarterly Reports", "content": "Compliance status report to Board. Incident summary. Regulatory update briefing. Gap remediation progress."},
                    {"heading": "3.2 Annual Reports", "content": "Annual compliance certificate. System audit findings. Net worth certificate. RBI returns and filings."},
                ]
            },
            {
                "heading": "4. CCO Responsibilities",
                "content": "Ensure compliance with all RBI directions. Report to Board quarterly. Maintain compliance calendar. Coordinate with external auditors."
            },
        ],
        "review_frequency": "quarterly",
    },
}


class SOPTemplatesService:
    """Manages pre-built and custom SOP templates for PA/PG compliance."""

    def __init__(self, db=None, policy_drafting_service=None):
        self.db = db
        self.policy_drafting_service = policy_drafting_service

    def list_templates(self, entity_type: str = None, category: str = None) -> List[Dict[str, Any]]:
        """List available SOP templates, optionally filtered by entity type or category."""
        templates = []
        for key, tpl in SOP_TEMPLATES.items():
            if entity_type and entity_type not in tpl.get("entity_types", []):
                continue
            if category and tpl.get("category") != category:
                continue
            templates.append({
                "id": tpl["id"],
                "key": key,
                "title": tpl["title"],
                "category": tpl["category"],
                "entity_types": tpl["entity_types"],
                "rbi_references": tpl["rbi_references"],
                "section_count": len(tpl["sections"]),
                "review_frequency": tpl.get("review_frequency", "annual"),
            })
        return templates

    def get_template(self, template_key: str) -> Optional[Dict[str, Any]]:
        """Get a full SOP template by key."""
        return SOP_TEMPLATES.get(template_key)

    async def instantiate_template(
        self,
        template_key: str,
        organization: str,
        user_id: str,
        customizations: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create a policy draft from an SOP template, with optional customizations."""
        template = SOP_TEMPLATES.get(template_key)
        if not template:
            return {"error": f"Template '{template_key}' not found"}

        draft_id = str(uuid.uuid4())
        content = {
            "title": template["title"],
            "sections": template["sections"],
            "summary": f"SOP generated from template: {template['title']}",
            "regulatory_references": template["rbi_references"],
            "review_frequency": template.get("review_frequency", "annual"),
        }

        if customizations:
            if customizations.get("title"):
                content["title"] = customizations["title"]
            if customizations.get("organization_name"):
                for section in content["sections"]:
                    section["content"] = section.get("content", "").replace(
                        "the payment aggregation platform",
                        f"{customizations['organization_name']}'s payment aggregation platform"
                    )

        draft_doc = {
            "id": draft_id,
            "title": content["title"],
            "policy_type": "SOP",
            "entity_type": template["entity_types"][0] if template["entity_types"] else "non_bank_pa",
            "status": "draft",
            "content": content,
            "source_template": template_key,
            "user_id": user_id,
            "organization": organization,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.policy_drafts.insert_one(draft_doc)

        return {
            "draft_id": draft_id,
            "title": content["title"],
            "source_template": template_key,
            "status": "draft",
        }

    async def generate_custom_sop(
        self,
        topic: str,
        entity_type: str,
        organization: str,
        user_id: str,
        instructions: str = "",
    ) -> Dict[str, Any]:
        """Generate a custom SOP using AI (delegates to PolicyDraftingService)."""
        if not self.policy_drafting_service:
            return {"error": "Policy drafting service not available"}

        return await self.policy_drafting_service.generate_policy_draft(
            title=f"SOP: {topic}",
            policy_type="SOP",
            entity_type=entity_type,
            organization=organization,
            user_id=user_id,
            instructions=f"Generate a detailed Standard Operating Procedure for: {topic}. {instructions}",
        )
