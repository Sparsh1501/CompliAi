"""Seed test policies for feature verification."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'compli-ai')

# Enum values must match exactly:
# PolicyType: KYC, AML, Digital Lending, InfoSec, Outsourcing, Risk Management, Fraud Management, UPI/Payments, Other
# PolicyStatus: Draft, Review, Approved, Archived

test_policies = [
    {
        "id": str(uuid.uuid4()),
        "title": "KYC Compliance Policy 2025",
        "policy_type": "KYC",
        "status": "Draft",
        "department": "Compliance",
        "version": "2.0",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Anti Money Laundering Framework",
        "policy_type": "AML",
        "status": "Approved",
        "department": "Legal",
        "version": "1.5",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Digital Lending Guidelines",
        "policy_type": "Digital Lending",
        "status": "Draft",
        "department": "Technology",
        "version": "1.0",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=15)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Information Security Standards",
        "policy_type": "InfoSec",
        "status": "Review",
        "department": "IT Security",
        "version": "3.1",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Outsourcing Risk Management Policy",
        "policy_type": "Outsourcing",
        "status": "Approved",
        "department": "Operations",
        "version": "1.2",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Enterprise Risk Management Framework",
        "policy_type": "Risk Management",
        "status": "Approved",
        "department": "Risk",
        "version": "2.3",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=15)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Fraud Detection and Prevention",
        "policy_type": "Fraud Management",
        "status": "Draft",
        "department": "Compliance",
        "version": "1.0",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "UPI Payment Processing Standards",
        "policy_type": "UPI/Payments",
        "status": "Approved",
        "department": "Payments",
        "version": "1.8",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=50)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Customer Due Diligence Procedures",
        "policy_type": "KYC",
        "status": "Review",
        "department": "Compliance",
        "version": "1.3",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=25)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Data Privacy and Protection Policy",
        "policy_type": "InfoSec",
        "status": "Approved",
        "department": "Legal",
        "version": "2.0",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=70)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=12)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Regulatory Reporting Framework",
        "policy_type": "Other",
        "status": "Approved",
        "department": "Finance",
        "version": "1.5",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Suspicious Transaction Reporting",
        "policy_type": "AML",
        "status": "Draft",
        "department": "Compliance",
        "version": "1.0",
        "organization": "CompliAI",
        "user_id": "8a587d44-c374-4051-890f-db7769476b0c",
        "clauses": [],
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat(),
    },
]


async def seed():
    client = AsyncIOMotorClient(mongo_url)
    database = client[db_name]

    # First, delete any bad seeded data (with wrong enum values)
    bad_result = await database.policies.delete_many({
        "organization": "CompliAI",
        "status": {"$in": ["draft", "active", "review", "approved", "rejected", "archived"]}
    })
    if bad_result.deleted_count > 0:
        print(f"Cleaned up {bad_result.deleted_count} bad records with wrong enum values")

    # Check if we already have good CompliAI policies
    good_count = await database.policies.count_documents({
        "organization": "CompliAI",
        "status": {"$in": ["Draft", "Review", "Approved", "Archived"]}
    })

    if good_count >= 10:
        print(f"Already have {good_count} good CompliAI policies, skipping seed.")
        client.close()
        return

    # Delete any existing CompliAI policies to avoid duplicates
    await database.policies.delete_many({"organization": "CompliAI"})

    # Insert test policies
    result = await database.policies.insert_many(test_policies)
    print(f"Inserted {len(result.inserted_ids)} test policies")

    # Verify
    count = await database.policies.count_documents({"organization": "CompliAI"})
    print(f"Total CompliAI policies now: {count}")

    total = await database.policies.count_documents({})
    print(f"Total policies in DB: {total}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
