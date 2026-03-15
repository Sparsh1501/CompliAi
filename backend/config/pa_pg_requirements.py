"""
RBI PA/PG Master Direction — Requirement Catalog

~50 regulatory requirements organized by 10 compliance categories,
derived from the RBI Master Direction on Regulation of Payment
Aggregators (September 2025 consolidated version).

Each requirement includes:
- Structured ID (RBI-PAPG-{CATEGORY}-{SEQ})
- RBI paragraph reference
- Applicability scope (bank_pa, non_bank_pa, pa_p, etc.)
- Compliance indicators (testable evidence)
- Criticality level
"""

PA_PG_REQUIREMENTS = {
    "authorisation": [
        {
            "id": "RBI-PAPG-AUTH-001",
            "title": "Certificate of Authorisation (CoA)",
            "description": "All payment aggregators must obtain Certificate of Authorisation from RBI under the Payment and Settlement Systems Act, 2007.",
            "rbi_para": "Para 4",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "CoA issued by RBI or application submitted via PRAVAAH",
                "Board resolution acknowledging CoA requirements",
                "CoA displayed on website/premises"
            ],
            "evidence_types": ["document", "record"],
        },
        {
            "id": "RBI-PAPG-AUTH-002",
            "title": "PRAVAAH Application for Existing PAs",
            "description": "Existing payment aggregators operating without authorization must apply via PRAVAAH portal by the stipulated deadline.",
            "rbi_para": "Para 4.2",
            "applicability": ["non_bank_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "PRAVAAH application submitted with acknowledgement",
                "Application reference number documented",
                "Timeline compliance evidence"
            ],
            "evidence_types": ["document", "record"],
        },
        {
            "id": "RBI-PAPG-AUTH-003",
            "title": "Fit and Proper Criteria for Promoters/Directors",
            "description": "Promoters, directors, and key management personnel must satisfy fit and proper criteria as prescribed by RBI.",
            "rbi_para": "Para 4.3",
            "applicability": ["non_bank_pa", "pa_p"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Fit and proper declarations from all directors",
                "Background verification reports",
                "No regulatory adverse findings declaration",
                "Board-approved fit and proper policy"
            ],
            "evidence_types": ["document", "process"],
        },
        {
            "id": "RBI-PAPG-AUTH-004",
            "title": "Cessation of Unauthorised Operations",
            "description": "Entities operating as PAs without authorization must cease operations by the deadline if not applied/authorized.",
            "rbi_para": "Para 4.4",
            "applicability": ["non_bank_pa"],
            "criticality": "high",
            "requirement_type": "prohibition",
            "compliance_indicators": [
                "Authorization status documented",
                "Compliance timeline adherence",
                "Merchant wind-down plan if applicable"
            ],
            "evidence_types": ["document", "process"],
        },
        {
            "id": "RBI-PAPG-AUTH-005",
            "title": "Bank PA Notification Requirement",
            "description": "Banks acting as payment aggregators must notify RBI and comply with applicable directions.",
            "rbi_para": "Para 4.1",
            "applicability": ["bank_pa"],
            "criticality": "medium",
            "compliance_indicators": [
                "RBI notification letter submitted",
                "Acknowledgement from RBI",
                "Compliance confirmation to RBI"
            ],
            "evidence_types": ["document"],
        },
    ],
    "capital_requirements": [
        {
            "id": "RBI-PAPG-CAP-001",
            "title": "Minimum Net Worth Requirement",
            "description": "Non-bank PAs must maintain minimum net worth of ₹15 crore at all times. New applicants must achieve this within specified timeline.",
            "rbi_para": "Para 5.1",
            "applicability": ["non_bank_pa", "pa_p"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Audited net worth certificate >= ₹15 crore",
                "CA certificate confirming net worth calculation",
                "Board resolution on capital maintenance policy",
                "Quarterly net worth monitoring reports"
            ],
            "evidence_types": ["document", "record"],
        },
        {
            "id": "RBI-PAPG-CAP-002",
            "title": "Net Worth Computation Method",
            "description": "Net worth shall be computed as per RBI prescribed method excluding revaluation reserves, intangible assets, and other specified items.",
            "rbi_para": "Para 5.2",
            "applicability": ["non_bank_pa", "pa_p"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Net worth computation worksheet per RBI formula",
                "Auditor attestation on computation method",
                "Exclusion of disallowed items documented"
            ],
            "evidence_types": ["document", "record"],
        },
        {
            "id": "RBI-PAPG-CAP-003",
            "title": "Positive Net Worth Maintenance",
            "description": "PAs must maintain positive net worth at all times and report any breach immediately to RBI.",
            "rbi_para": "Para 5.3",
            "applicability": ["non_bank_pa", "pa_p"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Continuous net worth monitoring process",
                "Breach reporting mechanism to RBI",
                "Corrective action plan for net worth shortfall"
            ],
            "evidence_types": ["process", "document"],
        },
    ],
    "merchant_onboarding": [
        {
            "id": "RBI-PAPG-MER-001",
            "title": "Merchant Due Diligence (KYC)",
            "description": "PAs must conduct thorough due diligence/KYC of merchants before onboarding, including background checks and business verification.",
            "rbi_para": "Para 6.1",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Merchant KYC policy approved by Board",
                "KYC checklist for merchant onboarding",
                "Background verification process documented",
                "Business legitimacy verification process"
            ],
            "evidence_types": ["document", "process"],
        },
        {
            "id": "RBI-PAPG-MER-002",
            "title": "Merchant Agreement Requirements",
            "description": "Written agreements with merchants covering terms, data security, refund policy, and compliance obligations.",
            "rbi_para": "Para 6.2",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Standard merchant agreement template",
                "Data security clauses in agreement",
                "Refund and chargeback policy included",
                "Compliance obligations clearly stated"
            ],
            "evidence_types": ["document"],
        },
        {
            "id": "RBI-PAPG-MER-003",
            "title": "Ongoing Merchant Monitoring",
            "description": "Continuous monitoring of merchant activities for suspicious transactions, policy violations, and compliance adherence.",
            "rbi_para": "Para 6.3",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Transaction monitoring system for merchants",
                "Periodic merchant review process",
                "Merchant risk categorization framework",
                "Adverse findings escalation process"
            ],
            "evidence_types": ["process", "control", "report"],
        },
        {
            "id": "RBI-PAPG-MER-004",
            "title": "Merchant Website/App Compliance",
            "description": "Merchants must display PA details, refund policy, and privacy policy on their website/app.",
            "rbi_para": "Para 6.4",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Merchant website compliance checklist",
                "Periodic website/app audit reports",
                "PA details display verification"
            ],
            "evidence_types": ["process", "record"],
        },
        {
            "id": "RBI-PAPG-MER-005",
            "title": "Pre-2026 Merchant KYC Completion",
            "description": "KYC of all existing merchants onboarded before specific date must be completed within the prescribed timeline.",
            "rbi_para": "Para 6.5",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Existing merchant KYC completion tracker",
                "Timeline compliance dashboard",
                "Board-level KYC completion reporting"
            ],
            "evidence_types": ["record", "report"],
        },
    ],
    "settlement_operations": [
        {
            "id": "RBI-PAPG-SET-001",
            "title": "Settlement Timeline Compliance (T+1)",
            "description": "Settlement to merchants must be completed within T+1 business day from the date of transaction confirmation.",
            "rbi_para": "Para 7.1",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "T+1 settlement SLA documented",
                "Settlement processing system with T+1 capability",
                "Settlement delay monitoring and reporting",
                "Exception handling for delayed settlements"
            ],
            "evidence_types": ["process", "control", "report"],
        },
        {
            "id": "RBI-PAPG-SET-002",
            "title": "Settlement Reconciliation",
            "description": "Daily reconciliation of transactions, settlements, and refunds with proper audit trail.",
            "rbi_para": "Para 7.2",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Daily reconciliation process documented",
                "Automated reconciliation system",
                "Discrepancy resolution process",
                "Reconciliation audit trail maintained"
            ],
            "evidence_types": ["process", "control", "record"],
        },
        {
            "id": "RBI-PAPG-SET-003",
            "title": "Refund Processing Timeline",
            "description": "Customer refunds must be processed within the timeline prescribed by RBI from the date of refund initiation.",
            "rbi_para": "Para 7.3",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Refund processing SLA documented",
                "Refund tracking system",
                "Customer notification on refund status",
                "Refund delay escalation process"
            ],
            "evidence_types": ["process", "control"],
        },
        {
            "id": "RBI-PAPG-SET-004",
            "title": "Failed Transaction Handling",
            "description": "Failed transactions must be reversed/refunded within prescribed timelines with auto-reversal mechanisms.",
            "rbi_para": "Para 7.4",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Auto-reversal mechanism for failed transactions",
                "Failed transaction monitoring dashboard",
                "Customer compensation policy for delays",
                "TAT adherence reporting"
            ],
            "evidence_types": ["process", "control", "report"],
        },
        {
            "id": "RBI-PAPG-SET-005",
            "title": "No Charge on Failed Transactions",
            "description": "PAs shall not levy any charge on customers for failed transactions.",
            "rbi_para": "Para 7.5",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "prohibition",
            "compliance_indicators": [
                "Pricing policy excludes failed transaction charges",
                "System configuration preventing failed transaction charges",
                "Customer complaint monitoring for erroneous charges"
            ],
            "evidence_types": ["document", "control"],
        },
    ],
    "escrow_accounts": [
        {
            "id": "RBI-PAPG-ESC-001",
            "title": "Escrow Account Maintenance",
            "description": "PAs must maintain escrow accounts with scheduled commercial banks for holding funds between collection and settlement.",
            "rbi_para": "Para 8.1",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Escrow account opened with scheduled commercial bank",
                "Escrow account agreement executed",
                "Board resolution for escrow account",
                "Escrow account details filed with RBI"
            ],
            "evidence_types": ["document", "record"],
        },
        {
            "id": "RBI-PAPG-ESC-002",
            "title": "Escrow Account Fund Flow Compliance",
            "description": "All payment collections must flow through the escrow account. No commingling of PA's own funds with merchant funds.",
            "rbi_para": "Para 8.2",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Fund flow diagram showing escrow routing",
                "System configuration preventing commingling",
                "Regular escrow balance reconciliation",
                "Audit report on escrow fund flow compliance"
            ],
            "evidence_types": ["document", "process", "control"],
        },
        {
            "id": "RBI-PAPG-ESC-003",
            "title": "Nodal Account Requirements",
            "description": "PAs must maintain nodal/internal accounts for commissions and fees separately from escrow accounts.",
            "rbi_para": "Para 8.3",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Separate nodal account maintained",
                "Commission/fee transfer process documented",
                "Nodal account reconciliation process"
            ],
            "evidence_types": ["document", "process"],
        },
    ],
    "fraud_monitoring": [
        {
            "id": "RBI-PAPG-FRM-001",
            "title": "Fraud Risk Management Framework",
            "description": "PAs must establish a comprehensive fraud risk management framework approved by the Board.",
            "rbi_para": "Para 9.1",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Board-approved fraud risk management policy",
                "Fraud risk assessment documented",
                "Fraud prevention controls implemented",
                "Fraud response and investigation procedures"
            ],
            "evidence_types": ["document", "process", "control"],
        },
        {
            "id": "RBI-PAPG-FRM-002",
            "title": "Transaction Monitoring System",
            "description": "Real-time and near-real-time transaction monitoring for suspicious patterns, velocity checks, and anomaly detection.",
            "rbi_para": "Para 9.2",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Real-time transaction monitoring system deployed",
                "Rule-based and ML-based detection mechanisms",
                "Alert investigation and disposition process",
                "Periodic tuning of monitoring rules"
            ],
            "evidence_types": ["control", "process", "report"],
        },
        {
            "id": "RBI-PAPG-FRM-003",
            "title": "Fraud Reporting to RBI",
            "description": "PAs must report fraud incidents to RBI and law enforcement as per prescribed timelines and formats.",
            "rbi_para": "Para 9.3",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Fraud reporting process and timelines documented",
                "Reporting templates per RBI format",
                "Escalation matrix for fraud incidents",
                "Fraud incident register maintained"
            ],
            "evidence_types": ["process", "record", "report"],
        },
        {
            "id": "RBI-PAPG-FRM-004",
            "title": "Chargeback Management",
            "description": "PAs must have a structured chargeback management process including customer notification and timely resolution.",
            "rbi_para": "Para 9.4",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Chargeback policy documented",
                "Chargeback processing SLA",
                "Customer notification mechanism",
                "Merchant liability framework"
            ],
            "evidence_types": ["document", "process"],
        },
    ],
    "governance_compliance": [
        {
            "id": "RBI-PAPG-GOV-001",
            "title": "Board-level Compliance Oversight",
            "description": "Board of Directors must exercise oversight on PA compliance including periodic reviews and compliance reporting.",
            "rbi_para": "Para 10.1",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Board compliance agenda items documented",
                "Quarterly compliance reports to Board",
                "Board-approved compliance calendar",
                "Board minutes reflecting compliance discussions"
            ],
            "evidence_types": ["document", "record"],
        },
        {
            "id": "RBI-PAPG-GOV-002",
            "title": "Chief Compliance Officer Appointment",
            "description": "PAs must appoint a designated Chief Compliance Officer (CCO) with adequate authority and resources.",
            "rbi_para": "Para 10.2",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "CCO appointment letter",
                "CCO role and responsibilities documented",
                "CCO reporting line to Board/MD",
                "CCO independence from business functions"
            ],
            "evidence_types": ["document"],
        },
        {
            "id": "RBI-PAPG-GOV-003",
            "title": "Compliance Function and Reporting",
            "description": "Dedicated compliance function with regular reporting to the Board and regulatory bodies.",
            "rbi_para": "Para 10.3",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Compliance function structure and staffing",
                "Periodic compliance reports (quarterly/annual)",
                "Regulatory filing tracker and calendar",
                "Compliance training program for staff"
            ],
            "evidence_types": ["document", "process", "report"],
        },
    ],
    "technology_security": [
        {
            "id": "RBI-PAPG-TEC-001",
            "title": "Information Security Policy",
            "description": "PAs must have Board-approved information security policy covering data protection, access control, encryption, and incident management.",
            "rbi_para": "Para 11.1",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Board-approved information security policy",
                "Data classification and handling procedures",
                "Access control matrix documented",
                "Encryption standards for data at rest and in transit",
                "Incident response plan"
            ],
            "evidence_types": ["document", "control"],
        },
        {
            "id": "RBI-PAPG-TEC-002",
            "title": "PCI-DSS Compliance",
            "description": "PAs handling card data must be PCI-DSS compliant with annual certification.",
            "rbi_para": "Para 11.2",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "PCI-DSS certification (current year)",
                "Quarterly vulnerability scans",
                "Annual penetration testing report",
                "PCI-DSS gap remediation tracker"
            ],
            "evidence_types": ["document", "report"],
        },
        {
            "id": "RBI-PAPG-TEC-003",
            "title": "System Audit",
            "description": "Annual IT/system audit by CERT-In empanelled auditor covering security controls, infrastructure, and compliance.",
            "rbi_para": "Para 11.3",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Annual system audit conducted by CERT-In empanelled auditor",
                "Audit findings and remediation tracker",
                "Audit report submitted to RBI if required",
                "Previous audit findings closure evidence"
            ],
            "evidence_types": ["document", "report"],
        },
        {
            "id": "RBI-PAPG-TEC-004",
            "title": "Business Continuity and Disaster Recovery",
            "description": "PAs must have BCP/DR plans with periodic testing and documented recovery procedures.",
            "rbi_para": "Para 11.4",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Board-approved BCP/DR plan",
                "Annual DR drill conducted and documented",
                "RTO/RPO defined for critical systems",
                "DR site operational readiness evidence"
            ],
            "evidence_types": ["document", "process", "report"],
        },
    ],
    "customer_protection": [
        {
            "id": "RBI-PAPG-CUS-001",
            "title": "Customer Grievance Redressal",
            "description": "PAs must have accessible grievance redressal mechanism with escalation matrix and resolution timelines.",
            "rbi_para": "Para 12.1",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Grievance redressal policy published",
                "Complaint registration mechanism (toll-free/email/portal)",
                "Escalation matrix with timelines",
                "Nodal officer designated per RBI requirements",
                "Complaint resolution TAT monitoring"
            ],
            "evidence_types": ["document", "process", "control"],
        },
        {
            "id": "RBI-PAPG-CUS-002",
            "title": "Data Privacy and Customer Consent",
            "description": "PAs must ensure customer data privacy, obtain explicit consent for data usage, and comply with data localization requirements.",
            "rbi_para": "Para 12.2",
            "applicability": ["all_pa"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Privacy policy published and accessible",
                "Explicit consent mechanism for data collection",
                "Data stored in India per localization requirements",
                "Data sharing only with consent and for specified purposes"
            ],
            "evidence_types": ["document", "control", "process"],
        },
        {
            "id": "RBI-PAPG-CUS-003",
            "title": "Transparency in Charges",
            "description": "PAs must disclose all charges to customers upfront before transaction processing.",
            "rbi_para": "Para 12.3",
            "applicability": ["all_pa"],
            "criticality": "medium",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Charge disclosure at checkout/payment page",
                "No hidden charges policy documented",
                "Charge revision communication process"
            ],
            "evidence_types": ["document", "control"],
        },
    ],
    "pa_p_physical": [
        {
            "id": "RBI-PAPG-PAP-001",
            "title": "PA-P Registration and Compliance",
            "description": "Payment Aggregators in physical/proximity mode (PA-P) must register separately and comply with additional terminal management requirements.",
            "rbi_para": "Para 13.1",
            "applicability": ["pa_p"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Separate PA-P registration with RBI",
                "Terminal management policy",
                "Physical terminal inventory and audit",
                "Terminal security standards compliance"
            ],
            "evidence_types": ["document", "process", "control"],
        },
        {
            "id": "RBI-PAPG-PAP-002",
            "title": "Terminal Security and Tamper-Proofing",
            "description": "PA-P must ensure all payment terminals are secure, tamper-proof, and comply with relevant security standards.",
            "rbi_para": "Para 13.2",
            "applicability": ["pa_p"],
            "criticality": "high",
            "requirement_type": "mandatory",
            "compliance_indicators": [
                "Terminal security certification",
                "Tamper detection mechanisms",
                "Terminal firmware update process",
                "Physical inspection schedule and reports"
            ],
            "evidence_types": ["document", "control", "report"],
        },
    ],
}


def get_all_requirements() -> list:
    """Flatten all requirements into a single list."""
    all_reqs = []
    for category, reqs in PA_PG_REQUIREMENTS.items():
        for req in reqs:
            req_copy = dict(req)
            req_copy["category"] = category
            all_reqs.append(req_copy)
    return all_reqs


def get_requirements_by_applicability(entity_type: str) -> list:
    """Filter requirements applicable to a given entity type."""
    all_reqs = get_all_requirements()
    filtered = []
    for req in all_reqs:
        applicability = req.get("applicability", ["all"])
        if "all_pa" in applicability or "all" in applicability or entity_type in applicability:
            filtered.append(req)
    return filtered


def get_requirement_stats() -> dict:
    """Get summary statistics of the requirement catalog."""
    all_reqs = get_all_requirements()
    stats = {
        "total": len(all_reqs),
        "by_category": {},
        "by_criticality": {"high": 0, "medium": 0, "low": 0},
        "by_type": {},
    }
    for req in all_reqs:
        cat = req.get("category", "general")
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        crit = req.get("criticality", "medium")
        stats["by_criticality"][crit] = stats["by_criticality"].get(crit, 0) + 1
        rtype = req.get("requirement_type", "mandatory")
        stats["by_type"][rtype] = stats["by_type"].get(rtype, 0) + 1
    return stats
