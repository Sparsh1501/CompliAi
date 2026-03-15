#!/usr/bin/env python3
"""Standalone test script to verify MongoDB and Qdrant collections exist."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import QdrantClient
import os

REQUIRED_COLLECTIONS = [
    "users", "policies", "policy_versions", "approval_workflows",
    "regulations", "regulation_updates", "clauses", "gap_analyses",
    "tasks", "task_dependencies", "escalation_rules",
    "evidence", "evidence_audit_log", "evidence_templates",
    "departments", "department_members", "audit_sessions",
    "calendar_events", "chat_threads", "chat_messages",
    "los_lms_data", "los_lms_mappings", "los_lms_exceptions",
    "notification_preferences", "notifications",
    "checklists"
]

QDRANT_COLLECTIONS = ["policy_clauses", "regulation_clauses"]

async def verify():
    """Verify all collections exist."""
    # MongoDB
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    db = client["compli-ai"]

    print("Checking MongoDB collections...")
    existing_mongo = await db.list_collection_names()
    print(f"Found {len(existing_mongo)} MongoDB collections")

    missing_mongo = []
    for coll in REQUIRED_COLLECTIONS:
        if coll in existing_mongo:
            print(f"✓ {coll}")
        else:
            print(f"✗ {coll} MISSING")
            missing_mongo.append(coll)

    # Qdrant
    print(f"\nChecking Qdrant collections...")
    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant = QdrantClient(url=qdrant_url)
        existing_qdrant = [c.name for c in qdrant.get_collections().collections]
        print(f"Found {len(existing_qdrant)} Qdrant collections")

        missing_qdrant = []
        for coll in QDRANT_COLLECTIONS:
            if coll in existing_qdrant:
                print(f"✓ {coll}")
            else:
                print(f"✗ {coll} MISSING")
                missing_qdrant.append(coll)
    except Exception as e:
        print(f"Error checking Qdrant: {e}")
        missing_qdrant = QDRANT_COLLECTIONS

    # Check indexes on key collections
    print(f"\nChecking key indexes...")
    try:
        # Check users email index
        users_indexes = await db.users.index_information()
        email_index_exists = any('email' in idx for idx in users_indexes.keys())
        print(f"✓ users.email index: {'EXISTS' if email_index_exists else 'MISSING'}")

        # Check policies organization index
        policies_indexes = await db.policies.index_information()
        org_index_exists = any('organization' in idx for idx in policies_indexes.keys())
        print(f"✓ policies.organization index: {'EXISTS' if org_index_exists else 'MISSING'}")

        # Check tasks indexes
        tasks_indexes = await db.tasks.index_information()
        task_index_exists = any('assignee' in idx or 'status' in idx for idx in tasks_indexes.keys())
        print(f"✓ tasks indexes: {'EXISTS' if task_index_exists else 'MISSING'}")
    except Exception as e:
        print(f"Warning: Could not verify indexes: {e}")

    if missing_mongo or missing_qdrant:
        print(f"\n❌ FAILED - Missing collections:")
        print(f"  MongoDB: {missing_mongo}")
        print(f"  Qdrant: {missing_qdrant}")
        return False
    else:
        print(f"\n✅ SUCCESS - All {len(REQUIRED_COLLECTIONS)} MongoDB and {len(QDRANT_COLLECTIONS)} Qdrant collections exist!")
        return True

if __name__ == "__main__":
    result = asyncio.run(verify())
    exit(0 if result else 1)
