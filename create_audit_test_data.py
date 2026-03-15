"""Create test audit session with controls that have different RAG statuses for Feature #189 verification."""
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import uuid

async def create_test_audit():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["compli-ai"]

    audit_id = str(uuid.uuid4())[:8] + "-rag-test"
    user_id = "8a587d44-c374-4051-890f-db7769476b0c"  # admin user

    # Create controls with different compliance scores for RAG testing
    controls = [
        {
            "id": f"ctrl-green-1-{audit_id}",
            "control_name": "KYC Customer Identification",
            "control_description": "Verify customer identification procedures comply with RBI KYC Master Direction",
            "category": "KYC/AML",
            "weightage": 1.0,
            "evidence_required": ["CDD Policy", "KYC Form Template"],
            "compliance_score": 92.0,
            "status": "Compliant",
            "findings": "All KYC procedures are properly documented and followed.",
            "recommendations": "Continue current practices. Consider digitalizing remaining manual processes."
        },
        {
            "id": f"ctrl-green-2-{audit_id}",
            "control_name": "Transaction Monitoring System",
            "control_description": "Verify AML transaction monitoring system effectiveness",
            "category": "KYC/AML",
            "weightage": 1.0,
            "evidence_required": ["TMS Config", "Alert Reports"],
            "compliance_score": 85.0,
            "status": "Compliant",
            "findings": "Transaction monitoring system is operational with appropriate thresholds.",
            "recommendations": "Review threshold calibration quarterly."
        },
        {
            "id": f"ctrl-amber-1-{audit_id}",
            "control_name": "Vendor Due Diligence",
            "control_description": "Verify outsourcing vendor assessment and monitoring",
            "category": "Outsourcing",
            "weightage": 1.0,
            "evidence_required": ["Vendor Contracts", "Assessment Reports", "SLA Documents"],
            "compliance_score": 58.0,
            "status": "Partially Compliant",
            "findings": "Vendor assessments conducted but some documentation gaps found.",
            "recommendations": "Complete pending vendor risk assessments. Update SLA monitoring dashboard."
        },
        {
            "id": f"ctrl-amber-2-{audit_id}",
            "control_name": "Data Privacy Controls",
            "control_description": "Verify data privacy and protection measures",
            "category": "IT/InfoSec",
            "weightage": 1.0,
            "evidence_required": ["Privacy Policy", "Data Classification", "Consent Records"],
            "compliance_score": 62.0,
            "status": "Requires Review",
            "findings": "Privacy policy exists but consent management needs improvement.",
            "recommendations": "Implement granular consent tracking. Update privacy notice for digital lending."
        },
        {
            "id": f"ctrl-red-1-{audit_id}",
            "control_name": "Fair Practice Code Disclosure",
            "control_description": "Verify KFS and fair practice code disclosures to borrowers",
            "category": "Digital Lending",
            "weightage": 1.0,
            "evidence_required": ["KFS Templates", "Disclosure Logs", "Borrower Acknowledgments"],
            "compliance_score": 25.0,
            "status": "Non-Compliant",
            "findings": "Key Fact Statements not consistently provided before loan disbursal.",
            "recommendations": "URGENT: Implement mandatory KFS generation and delivery before each disbursal."
        },
        {
            "id": f"ctrl-red-2-{audit_id}",
            "control_name": "Grievance Redressal Mechanism",
            "control_description": "Verify customer grievance handling and escalation procedures",
            "category": "Customer Protection",
            "weightage": 1.0,
            "evidence_required": ["GRM Policy", "Escalation Matrix", "Complaint Log"],
            "compliance_score": 15.0,
            "status": "Non-Compliant",
            "findings": "No formal grievance redressal mechanism in place. Missing escalation matrix.",
            "recommendations": "CRITICAL: Establish GRM immediately. Appoint Nodal Officer as per RBI guidelines."
        },
    ]

    # Calculate overall score
    total_score = sum(c["compliance_score"] for c in controls) / len(controls)

    audit_session = {
        "id": audit_id,
        "audit_type": "regulatory",
        "scope": "RBI KYC Compliance Audit 2025 - RAG Test",
        "controls": controls,
        "overall_score": round(total_score, 1),
        "status": "Completed",
        "user_id": user_id,
        "organization": "CompliAI",
        "created_by": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "signed_off": False,
    }

    # Delete any existing test audit
    await db.audit_sessions.delete_many({"scope": {"$regex": "RAG Test"}})

    # Insert new audit session
    await db.audit_sessions.insert_one(audit_session)

    print(f"Created audit session: {audit_id}")
    print(f"Overall score: {total_score:.1f}%")
    print(f"Controls: {len(controls)} (2 green, 2 amber, 2 red)")
    print("Done!")

    client.close()

asyncio.run(create_test_audit())
