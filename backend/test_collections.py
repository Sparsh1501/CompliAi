#!/usr/bin/env python3
"""Test script to verify MongoDB collections exist."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def check_collections():
    """Check if all required MongoDB collections exist."""
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    db = client["compli-ai"]

    # Expected collections from app_spec.txt
    expected_collections = [
        "users",
        "policies",
        "policy_versions",
        "approval_workflows",
        "regulations",
        "regulation_updates",
        "clauses",
        "gap_analyses",
        "tasks",
        "task_dependencies",
        "escalation_rules",
        "evidence",
        "evidence_audit_log",
        "evidence_templates",
        "departments",
        "department_members",
        "audit_sessions",
        "calendar_events",
        "chat_threads",
        "chat_messages",
        "los_lms_data",
        "los_lms_mappings",
        "los_lms_exceptions",
        "notification_preferences",
        "notifications"
    ]

    # Get actual collections
    actual_collections = await db.list_collection_names()

    print(f"Total collections found: {len(actual_collections)}")
    print(f"\nActual collections: {sorted(actual_collections)}")

    # Check which expected collections exist
    missing = []
    for coll in expected_collections:
        if coll in actual_collections:
            print(f"✓ {coll}")
        else:
            print(f"✗ {coll} (MISSING)")
            missing.append(coll)

    if missing:
        print(f"\n❌ Missing {len(missing)} collections: {missing}")
        return False
    else:
        print(f"\n✅ All {len(expected_collections)} expected collections exist!")
        return True

if __name__ == "__main__":
    result = asyncio.run(check_collections())
    exit(0 if result else 1)
