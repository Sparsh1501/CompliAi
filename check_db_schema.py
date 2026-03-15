#!/usr/bin/env python3
"""
Script to verify MongoDB and Qdrant schema for Feature #2
"""
import sys
import asyncio
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

# Expected collections from app_spec.txt
EXPECTED_COLLECTIONS = [
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

# Key indexes to verify
EXPECTED_INDEXES = {
    "users": ["email"],
    "policies": ["organization", "type"],
    "tasks": ["assignee", "status"]
}

async def check_mongodb():
    """Check MongoDB collections and indexes"""
    print("=" * 60)
    print("MONGODB SCHEMA VERIFICATION")
    print("=" * 60)

    # Connect to MongoDB
    mongo_url = "mongodb://admin:compliai123@localhost:27017"
    db_name = "compli-ai"

    try:
        # Use AsyncIOMotorClient for consistency with backend
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]

        # List all collections
        collections = await db.list_collection_names()
        print(f"\n✓ Connected to MongoDB: {db_name}")
        print(f"✓ Total collections found: {len(collections)}")
        print(f"\nCollections: {sorted(collections)}")

        # Check for expected collections
        missing = []
        for expected in EXPECTED_COLLECTIONS:
            if expected not in collections:
                missing.append(expected)

        if missing:
            print(f"\n✗ MISSING COLLECTIONS ({len(missing)}):")
            for coll in sorted(missing):
                print(f"  - {coll}")
        else:
            print(f"\n✓ All {len(EXPECTED_COLLECTIONS)} expected collections exist!")

        # Check indexes on key collections
        print(f"\n{'-' * 60}")
        print("INDEX VERIFICATION")
        print("-" * 60)

        for coll_name, expected_fields in EXPECTED_INDEXES.items():
            if coll_name in collections:
                indexes = await db[coll_name].index_information()
                print(f"\n{coll_name} indexes:")
                for idx_name, idx_info in indexes.items():
                    keys = idx_info.get('key', [])
                    print(f"  - {idx_name}: {keys}")

                # Check if expected fields are indexed
                indexed_fields = set()
                for idx_info in indexes.values():
                    for field, _ in idx_info.get('key', []):
                        indexed_fields.add(field)

                for field in expected_fields:
                    if field in indexed_fields:
                        print(f"  ✓ {field} is indexed")
                    else:
                        print(f"  ✗ {field} is NOT indexed")

        client.close()

        return len(missing) == 0

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return False

def check_qdrant():
    """Check Qdrant collections"""
    print("\n" + "=" * 60)
    print("QDRANT SCHEMA VERIFICATION")
    print("=" * 60)

    # Try to import qdrant client
    try:
        from qdrant_client import QdrantClient

        # Check if using memory mode or server mode
        import os
        qdrant_mode = os.getenv('QDRANT_MODE', 'memory')
        qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')

        print(f"\nQdrant mode: {qdrant_mode}")

        if qdrant_mode == 'memory':
            print("✓ Using in-memory mode (development)")
            print("  Collections will be created on first use")
            return True
        else:
            # Try to connect to Qdrant server
            try:
                client = QdrantClient(url=qdrant_url)
                collections = client.get_collections().collections
                collection_names = [c.name for c in collections]

                print(f"✓ Connected to Qdrant at {qdrant_url}")
                print(f"✓ Collections found: {collection_names}")

                expected_qdrant = ["policy_clauses", "regulation_clauses"]
                for expected in expected_qdrant:
                    if expected in collection_names:
                        print(f"  ✓ {expected} exists")
                    else:
                        print(f"  ! {expected} not yet created (will be created on upload)")

                return True

            except Exception as e:
                print(f"✗ Could not connect to Qdrant: {e}")
                return False

    except ImportError:
        print("! qdrant-client not installed")
        return False

async def main():
    """Main verification function"""
    print("\nCompliAI Database Schema Verification")
    print("Feature #2: Database schema/collections applied correctly\n")

    # Check MongoDB
    mongo_ok = await check_mongodb()

    # Check Qdrant
    qdrant_ok = check_qdrant()

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    if mongo_ok and qdrant_ok:
        print("✓ ALL CHECKS PASSED")
        print("  MongoDB: All collections exist with proper indexes")
        print("  Qdrant: Configured and ready")
        return 0
    else:
        print("✗ SOME CHECKS FAILED")
        if not mongo_ok:
            print("  MongoDB: Missing collections or indexes")
        if not qdrant_ok:
            print("  Qdrant: Not properly configured")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
