#!/usr/bin/env python3
"""
Script to verify Qdrant collections exist
"""
from qdrant_client import QdrantClient
import sys

# Qdrant connection (from docker-compose and backend config)
QDRANT_URL = "http://localhost:6333"

# Expected collections from app_spec.txt
EXPECTED_COLLECTIONS = [
    "policy_clauses",
    "regulation_clauses"
]

def check_qdrant_collections():
    """Check if Qdrant collections exist"""
    try:
        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL)

        # Get all collections
        collections = client.get_collections()
        existing_collection_names = [col.name for col in collections.collections]

        print(f"Qdrant URL: {QDRANT_URL}")
        print(f"Total collections found: {len(existing_collection_names)}\n")

        if existing_collection_names:
            print("Existing collections:")
            for col in sorted(existing_collection_names):
                print(f"  ✓ {col}")
        else:
            print("No collections found in Qdrant")

        print(f"\n--- Verification against expected collections ---")
        print(f"Expected: {len(EXPECTED_COLLECTIONS)} collections\n")

        # Check each expected collection
        missing = []
        for col in EXPECTED_COLLECTIONS:
            if col in existing_collection_names:
                print(f"  ✓ {col}")
            else:
                print(f"  ✗ {col} - MISSING")
                missing.append(col)

        # Check for extra collections
        extra = [col for col in existing_collection_names if col not in EXPECTED_COLLECTIONS]

        if extra:
            print(f"\nExtra collections (not in expected list):")
            for col in extra:
                print(f"  + {col}")

        # Summary
        print(f"\n--- Summary ---")
        print(f"Expected: {len(EXPECTED_COLLECTIONS)}")
        print(f"Found: {len(existing_collection_names)}")
        print(f"Missing: {len(missing)}")
        print(f"Extra: {len(extra)}")

        if missing:
            print(f"\nMissing collections:")
            for col in missing:
                print(f"  - {col}")
            return False
        else:
            print("\n✅ All expected Qdrant collections exist!")
            return True

    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")
        return False

if __name__ == "__main__":
    success = check_qdrant_collections()
    sys.exit(0 if success else 1)
