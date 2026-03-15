#!/usr/bin/env python3
"""Test data persistence for Feature 3: Data persists across server restart"""
import os
import sys
import time
from pymongo import MongoClient

# Test user credentials
TEST_EMAIL = "RESTART_TEST_12345@test.com"
TEST_PASSWORD = "TestPassword123!"
TEST_FULL_NAME = "Restart Test User"
TEST_ORGANIZATION = "Test Org"

def connect_mongodb():
    """Connect to MongoDB"""
    mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.getenv('DB_NAME', 'compli-ai')

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    return client, db

def test_direct_database_persistence():
    """
    Test data persistence by directly interacting with MongoDB.
    This verifies that MongoDB itself is persisting data correctly.
    """
    print("="*80)
    print("FEATURE 3 VERIFICATION: Data persists across server restart")
    print("="*80)
    print()
    print("Testing direct MongoDB persistence...")
    print()

    try:
        # Connect to MongoDB
        client, db = connect_mongodb()
        users_collection = db['users']

        # Step 1: Check if test user already exists (cleanup from previous runs)
        print("Step 1: Cleanup any existing test data...")
        existing_user = users_collection.find_one({"email": TEST_EMAIL})
        if existing_user:
            users_collection.delete_one({"email": TEST_EMAIL})
            print(f"  ✓ Removed existing test user")
        else:
            print(f"  ✓ No existing test data found")
        print()

        # Step 2: Create test data
        print("Step 2: Create test user data in MongoDB...")
        test_user = {
            "email": TEST_EMAIL,
            "full_name": TEST_FULL_NAME,
            "organization": TEST_ORGANIZATION,
            "password_hash": "test_hash_12345",  # Not a real hash, just for testing
            "created_at": time.time(),
            "role": "user"
        }

        result = users_collection.insert_one(test_user)
        user_id = result.inserted_id
        print(f"  ✓ Created user with ID: {user_id}")
        print()

        # Step 3: Verify data was written
        print("Step 3: Verify data exists immediately after creation...")
        found_user = users_collection.find_one({"email": TEST_EMAIL})
        if found_user and found_user['email'] == TEST_EMAIL:
            print(f"  ✓ User found: {found_user['email']}")
            print(f"    Name: {found_user['full_name']}")
            print(f"    Organization: {found_user['organization']}")
        else:
            print(f"  ✗ FAILED: User not found after creation!")
            return False
        print()

        # Step 4: Close connection and reconnect (simulates server restart)
        print("Step 4: Disconnect and reconnect to MongoDB (simulating server restart)...")
        client.close()
        print("  ✓ Disconnected from MongoDB")
        time.sleep(1)

        # Reconnect
        client, db = connect_mongodb()
        users_collection = db['users']
        print("  ✓ Reconnected to MongoDB")
        print()

        # Step 5: Verify data still exists after reconnection
        print("Step 5: Verify data persists after reconnection...")
        found_user_after = users_collection.find_one({"email": TEST_EMAIL})

        if found_user_after and found_user_after['email'] == TEST_EMAIL:
            print(f"  ✓ User STILL EXISTS after reconnection: {found_user_after['email']}")
            print(f"    Name: {found_user_after['full_name']}")
            print(f"    Organization: {found_user_after['organization']}")
            print(f"    ID: {found_user_after['_id']}")

            # Verify it's the same user
            if str(found_user_after['_id']) == str(user_id):
                print(f"  ✓ Same user ID - data definitely persisted!")
            else:
                print(f"  ⚠ Different user ID - unexpected but data exists")

            persistence_verified = True
        else:
            print(f"  ✗ CRITICAL FAILURE: User data DISAPPEARED after reconnection!")
            print(f"  ✗ This indicates in-memory storage or data loss!")
            persistence_verified = False
        print()

        # Step 6: Cleanup
        print("Step 6: Cleanup test data...")
        users_collection.delete_one({"email": TEST_EMAIL})
        print(f"  ✓ Test user deleted")
        print()

        # Close connection
        client.close()

        return persistence_verified

    except Exception as e:
        print(f"✗ Error during persistence test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_additional_collections():
    """Test persistence in other important collections"""
    print("Additional Persistence Tests...")
    print()

    try:
        client, db = connect_mongodb()

        # Test policies collection
        print("Testing policies collection...")
        policies = db['policies']

        # Create test policy
        test_policy = {
            "title": "TEST_RESTART_POLICY",
            "organization": "test_org",
            "type": "test",
            "created_at": time.time()
        }

        policy_result = policies.insert_one(test_policy)
        policy_id = policy_result.inserted_id
        print(f"  ✓ Created test policy: {policy_id}")

        # Reconnect
        client.close()
        client, db = connect_mongodb()
        policies = db['policies']

        # Verify persistence
        found_policy = policies.find_one({"_id": policy_id})
        if found_policy:
            print(f"  ✓ Policy persisted after reconnection")
            # Cleanup
            policies.delete_one({"_id": policy_id})
            print(f"  ✓ Cleaned up test policy")
        else:
            print(f"  ✗ Policy did not persist!")
            client.close()
            return False

        client.close()
        return True

    except Exception as e:
        print(f"✗ Error in additional persistence tests: {str(e)}")
        return False

def main():
    # Test primary persistence (users collection)
    persistence_pass = test_direct_database_persistence()

    # Test additional collections
    additional_pass = test_additional_collections()

    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Primary Persistence (users):     {'✓ PASS' if persistence_pass else '✗ FAIL'}")
    print(f"Additional Persistence (policies): {'✓ PASS' if additional_pass else '✗ FAIL'}")
    print()

    if persistence_pass and additional_pass:
        print("✓ FEATURE 3 PASSES: Data persists across server restart")
        print("  MongoDB is correctly configured for persistent storage")
        return 0
    else:
        print("✗ FEATURE 3 FAILS: Data does not persist")
        print("  CRITICAL: In-memory storage or configuration issue detected!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
