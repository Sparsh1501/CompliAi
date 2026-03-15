import pymongo
from datetime import datetime, timezone
import uuid

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["compli-ai"]

# Create a test gap analysis with compliance score
gap_analysis = {
    "id": str(uuid.uuid4()),
    "organization": "Test NBFC Ltd",
    "policy_id": str(uuid.uuid4()),
    "regulation_id": str(uuid.uuid4()),
    "compliance_score": 75.5,  # 75.5% compliance
    "gaps": [
        {
            "gap_id": "gap_1",
            "policy_clause_id": "clause_1",
            "regulation_clause_id": "reg_clause_1",
            "gap_description": "KYC process needs enhancement",
            "severity": "High",
            "recommendation": "Implement video KYC"
        },
        {
            "gap_id": "gap_2",
            "policy_clause_id": "clause_2",
            "regulation_clause_id": "reg_clause_2",
            "gap_description": "Transaction monitoring frequency insufficient",
            "severity": "Critical",
            "recommendation": "Increase monitoring to daily"
        },
        {
            "gap_id": "gap_3",
            "policy_clause_id": "clause_3",
            "regulation_clause_id": "reg_clause_3",
            "gap_description": "Customer data retention period unclear",
            "severity": "Medium",
            "recommendation": "Define 10-year retention policy"
        }
    ],
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
    "status": "completed"
}

result = db.gap_analyses.insert_one(gap_analysis)
print(f"✓ Created gap analysis with compliance score: {gap_analysis['compliance_score']}%")
print(f"✓ Gap analysis ID: {result.inserted_id}")
print(f"✓ Total gaps: {len(gap_analysis['gaps'])}")
print(f"✓ Critical gaps: 1")

# Also create a regulation to show in the regulator overview
regulation = {
    "id": str(uuid.uuid4()),
    "organization": "Test NBFC Ltd",
    "regulatory_body": "RBI",
    "name": "RBI Master Direction on KYC",
    "circular_number": "RBI/2023/KYC/001",
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc)
}

db.regulations.insert_one(regulation)
print(f"✓ Created regulation: {regulation['name']}")

client.close()
