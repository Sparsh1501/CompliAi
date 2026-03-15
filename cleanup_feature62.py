#!/usr/bin/env python3
"""Cleanup script for Feature #62 test data"""
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['compli-ai']

# Delete test audit sessions
audit_result = db.audit_sessions.delete_many({'user_id': '45294df0-f976-4c26-b75e-dc0028c3db42'})
print(f'Deleted {audit_result.deleted_count} audit sessions')

# Delete test user
user_result = db.users.delete_one({'email': 'audittest@test.com'})
print(f'Deleted {user_result.deleted_count} test user')

print('Cleanup complete!')
