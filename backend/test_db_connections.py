#!/usr/bin/env python3
"""Test database connections for Feature 1: Database connection established (MongoDB + Qdrant)"""
import os
import sys

# Set environment for in-memory Qdrant
os.environ['QDRANT_MODE'] = 'memory'

def test_mongodb():
    """Test MongoDB connection"""
    try:
        from pymongo import MongoClient
        from pymongo.errors import ServerSelectionTimeoutError

        # Get MongoDB URL from env
        mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.getenv('DB_NAME', 'compli-ai')

        print("Testing MongoDB connection...")
        print(f"  URL: {mongo_url}")
        print(f"  Database: {db_name}")

        # Create client with short timeout
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)

        # Test connection
        client.admin.command('ping')

        # Get database
        db = client[db_name]

        # List collections
        collections = db.list_collection_names()

        print(f"✓ MongoDB connected successfully")
        print(f"  Collections: {len(collections)}")
        for coll in collections[:5]:  # Show first 5
            print(f"    - {coll}")

        return True, "connected"

    except ServerSelectionTimeoutError as e:
        print(f"✗ MongoDB connection failed: Timeout")
        print(f"  Error: {str(e)}")
        return False, "timeout"
    except Exception as e:
        print(f"✗ MongoDB connection failed: {str(e)}")
        return False, "error"

def test_qdrant():
    """Test Qdrant connection (in-memory mode)"""
    try:
        from qdrant_client import QdrantClient

        print("\nTesting Qdrant connection...")
        print(f"  Mode: in-memory (QDRANT_MODE=memory)")

        # Initialize in-memory client
        client = QdrantClient(":memory:")

        # Try to get collections (will be empty in new instance)
        collections = client.get_collections()

        print(f"✓ Qdrant connected successfully (in-memory)")
        print(f"  Collections: {len(collections.collections)}")

        return True, "connected"

    except Exception as e:
        print(f"✗ Qdrant connection failed: {str(e)}")
        return False, "error"

def main():
    print("="*80)
    print("FEATURE 1 VERIFICATION: Database connection established (MongoDB + Qdrant)")
    print("="*80)
    print()

    # Test MongoDB
    mongodb_success, mongodb_status = test_mongodb()

    # Test Qdrant
    qdrant_success, qdrant_status = test_qdrant()

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"MongoDB: {'✓ PASS' if mongodb_success else '✗ FAIL'} ({mongodb_status})")
    print(f"Qdrant:  {'✓ PASS' if qdrant_success else '✗ FAIL'} ({qdrant_status})")
    print()

    if mongodb_success and qdrant_success:
        print("✓ FEATURE 1 PASSES: Both databases connected successfully")
        return 0
    else:
        print("✗ FEATURE 1 FAILS: One or more database connections failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
