#!/usr/bin/env python3
"""Test MongoDB connection and authentication."""
import sys

try:
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

    # Test 1: Connection without auth (current .env)
    print("Test 1: mongodb://localhost:27017 (no auth)")
    try:
        client1 = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
        client1.admin.command('ping')
        db1 = client1['compli-ai']
        collections1 = db1.list_collection_names()
        print(f"✓ Connected! Found {len(collections1)} collections")
        print(f"  Collections: {collections1}")

        # Try to find the test user
        if 'users' in collections1:
            user = db1.users.find_one({'email': 'RESTART_TEST_12345@test.com'})
            if user:
                print(f"✓ Test user found: {user.get('name')}")
            else:
                print("✗ Test user NOT found")
        client1.close()
    except Exception as e:
        print(f"✗ Failed: {e}")

    # Test 2: Connection with auth (docker-compose credentials)
    print("\nTest 2: mongodb://admin:compliai123@localhost:27017 (with auth)")
    try:
        client2 = MongoClient('mongodb://admin:compliai123@localhost:27017', serverSelectionTimeoutMS=2000)
        client2.admin.command('ping')
        db2 = client2['compli-ai']
        collections2 = db2.list_collection_names()
        print(f"✓ Connected! Found {len(collections2)} collections")
        print(f"  Collections: {collections2}")

        # Try to find the test user
        if 'users' in collections2:
            user = db2.users.find_one({'email': 'RESTART_TEST_12345@test.com'})
            if user:
                print(f"✓ Test user found: {user.get('name')}")
            else:
                print("✗ Test user NOT found")
        client2.close()
    except Exception as e:
        print(f"✗ Failed: {e}")

except ImportError:
    print("pymongo not installed")
    sys.exit(1)
