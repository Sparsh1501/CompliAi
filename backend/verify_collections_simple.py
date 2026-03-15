#!/usr/bin/env python3
"""Simple script to verify collections - prints to stdout for testing agent."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Import from the server module
from server import client, db, qdrant_client, REQUIRED_COLLECTIONS, QDRANT_COLLECTIONS
import asyncio

async def verify():
    """Verify all collections exist."""
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

    print(f"\nChecking Qdrant collections...")
    try:
        existing_qdrant = [c.name for c in qdrant_client.get_collections().collections]
        print(f"Found {len(existing_qdrant)} Qdrant collections")

        missing_qdrant = []
        for coll in QDRANT_COLLECTIONS.keys():
            if coll in existing_qdrant:
                print(f"✓ {coll}")
            else:
                print(f"✗ {coll} MISSING")
                missing_qdrant.append(coll)
    except Exception as e:
        print(f"Error checking Qdrant: {e}")
        missing_qdrant = list(QDRANT_COLLECTIONS.keys())

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
    sys.exit(0 if result else 1)
