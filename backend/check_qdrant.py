#!/usr/bin/env python3
"""Check Qdrant collections via the backend API."""
import os
os.environ['QDRANT_MODE'] = 'memory'  # Use in-memory mode

try:
    from qdrant_client import QdrantClient

    # Initialize in-memory Qdrant client
    client = QdrantClient(":memory:")

    # Get all collections
    collections = client.get_collections()

    print("Qdrant Collections:")
    for coll in collections.collections:
        print(f"  - {coll.name}")

    print(f"\nTotal: {len(collections.collections)} collections")

    # Check for required collections
    required = ["policy_clauses", "regulation_clauses"]
    existing = [c.name for c in collections.collections]

    for req in required:
        if req in existing:
            print(f"✓ {req} exists")
        else:
            print(f"✗ {req} MISSING")

except Exception as e:
    print(f"Error: {e}")
    print("Note: Qdrant is running in-memory mode within the backend server")
    print("Collections only exist in the running server process")
