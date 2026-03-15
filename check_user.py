#!/usr/bin/env python3
from pymongo import MongoClient
import uuid
from datetime import datetime, timezone

client = MongoClient('mongodb://localhost:27017')
db = client['compli-ai']

# Check if user exists
user = db.users.find_one({"email": "shivichan95@gmail.com"}, {"_id": 0})

if user:
    print("✓ User found!")
    print(f"  Email: {user.get('email')}")
    print(f"  Name: {user.get('full_name')}")
    print(f"  Organization: {user.get('organization')}")
    print(f"  Role: {user.get('role')}")
    print(f"\nUpdating password...")
    
    # Update password hash
    db.users.update_one(
        {"email": "shivichan95@gmail.com"},
        {"$set": {"password_hash": "$2b$12$0CgjhwfYHwa9qazQsc0d9uRipxzR0hVN2hIbn8VPNBy17/L0XSX7C"}}
    )
    print("✓ Password updated successfully!")
    print("\nYou can now login with:")
    print("  Email: shivichan95@gmail.com")
    print("  Password: Shivi@007")
else:
    print("✗ User NOT found in database")
    print("  Creating new user with this email...")
    
    new_user = {
        "id": str(uuid.uuid4()),
        "email": "shivichan95@gmail.com",
        "password_hash": "$2b$12$0CgjhwfYHwa9qazQsc0d9uRipxzR0hVN2hIbn8VPNBy17/L0XSX7C",
        "full_name": "Shivi User",
        "organization": "Default Org",
        "role": "compliance_head",
        "created_at": datetime.now(timezone.utc)
    }
    
    result = db.users.insert_one(new_user)
    print(f"✓ User created with ID: {result.inserted_id}")
    print("\nYou can now login with:")
    print("  Email: shivichan95@gmail.com")
    print("  Password: Shivi@007")
