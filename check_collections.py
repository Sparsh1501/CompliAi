#!/usr/bin/env python3
"""
Script to verify MongoDB collections exist as per app_spec.txt
"""
from pymongo import MongoClient
import sys

# MongoDB connection string (no auth based on backend .env)
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "compli-ai"

# Expected collections from app_spec.txt (Feature 2 verification steps)
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

def check_collections():
    """Check if all expected collections exist in MongoDB"""
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]

        # Get list of existing collections
        existing_collections = db.list_collection_names()

        print(f"Database: {DATABASE_NAME}")
        print(f"Total collections found: {len(existing_collections)}\n")

        print("Existing collections:")
        for col in sorted(existing_collections):
            print(f"  ✓ {col}")

        print(f"\n--- Verification against expected collections ---")
        print(f"Expected: {len(EXPECTED_COLLECTIONS)} collections\n")

        # Check each expected collection
        missing = []
        for col in EXPECTED_COLLECTIONS:
            if col in existing_collections:
                print(f"  ✓ {col}")
            else:
                print(f"  ✗ {col} - MISSING")
                missing.append(col)

        # Check for unexpected collections (not in expected list)
        extra = [col for col in existing_collections if col not in EXPECTED_COLLECTIONS]

        if extra:
            print(f"\nExtra collections (not in expected list):")
            for col in extra:
                print(f"  + {col}")

        # Summary
        print(f"\n--- Summary ---")
        print(f"Expected: {len(EXPECTED_COLLECTIONS)}")
        print(f"Found: {len(existing_collections)}")
        print(f"Missing: {len(missing)}")
        print(f"Extra: {len(extra)}")

        if missing:
            print(f"\nMissing collections:")
            for col in missing:
                print(f"  - {col}")
            return False
        else:
            print("\n✅ All expected collections exist!")
            return True

    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return False
    finally:
        client.close()

if __name__ == "__main__":
    success = check_collections()
    sys.exit(0 if success else 1)
