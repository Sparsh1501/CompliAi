#!/usr/bin/env python3
"""Test Pydantic validation for Features #122 and #163."""

import sys
sys.path.insert(0, '/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend')

from models import UserCreate, TaskCreate
from pydantic import ValidationError
import json

print("="*60)
print("TESTING FEATURE #122: Server-side Validation")
print("="*60)

# Test 1: Invalid email format
print("\nTest 1: Invalid email format")
try:
    user = UserCreate(email="not-an-email", password="ValidPass123", full_name="Test User")
    print("FAIL: Should have raised ValidationError")
except ValidationError as e:
    print("PASS: ValidationError raised")
    errors = []
    for err in e.errors():
        errors.append({
            'type': err['type'],
            'loc': list(err['loc']),
            'msg': err['msg']
        })
    print(f"Errors: {json.dumps(errors, indent=2)}")

# Test 2: Weak password (too short)
print("\nTest 2: Weak password (too short)")
try:
    user = UserCreate(email="test@example.com", password="123", full_name="Test User")
    print("FAIL: Should have raised ValidationError")
except ValidationError as e:
    print("PASS: ValidationError raised")
    errors = []
    for err in e.errors():
        errors.append({
            'type': err['type'],
            'loc': list(err['loc']),
            'msg': err['msg']
        })
    print(f"Errors: {json.dumps(errors, indent=2)}")

# Test 3: Password without numbers
print("\nTest 3: Password without numbers")
try:
    user = UserCreate(email="test@example.com", password="OnlyLetters", full_name="Test User")
    print("FAIL: Should have raised ValidationError")
except ValidationError as e:
    print("PASS: ValidationError raised")
    errors = []
    for err in e.errors():
        errors.append({
            'type': err['type'],
            'loc': list(err['loc']),
            'msg': err['msg']
        })
    print(f"Errors: {json.dumps(errors, indent=2)}")

# Test 4: Missing required fields
print("\nTest 4: Missing required fields (password)")
try:
    user = UserCreate(email="test@example.com", full_name="Test User")
    print("FAIL: Should have raised ValidationError")
except ValidationError as e:
    print("PASS: ValidationError raised")
    errors = []
    for err in e.errors():
        errors.append({
            'type': err['type'],
            'loc': list(err['loc']),
            'msg': err['msg']
        })
    print(f"Errors: {json.dumps(errors, indent=2)}")

# Test 5: Empty title in TaskCreate
print("\nTest 5: Empty title in TaskCreate")
try:
    task = TaskCreate(title="", description="Test description")
    print("FAIL: Should have raised ValidationError")
except ValidationError as e:
    print("PASS: ValidationError raised")
    errors = []
    for err in e.errors():
        errors.append({
            'type': err['type'],
            'loc': list(err['loc']),
            'msg': err['msg']
        })
    print(f"Errors: {json.dumps(errors, indent=2)}")

# Test 6: Negative estimated hours
print("\nTest 6: Negative estimated hours")
try:
    task = TaskCreate(title="Test Task", description="Test description", estimated_hours=-5)
    print("FAIL: Should have raised ValidationError")
except ValidationError as e:
    print("PASS: ValidationError raised")
    errors = []
    for err in e.errors():
        errors.append({
            'type': err['type'],
            'loc': list(err['loc']),
            'msg': err['msg']
        })
    print(f"Errors: {json.dumps(errors, indent=2)}")

# Test 7: Valid UserCreate
print("\nTest 7: Valid UserCreate")
try:
    user = UserCreate(email="test@example.com", password="ValidPass123", full_name="Test User")
    print("PASS: Valid user created successfully")
    print(f"User email: {user.email}")
except ValidationError as e:
    print(f"FAIL: Unexpected ValidationError: {e}")

# Test 8: Valid TaskCreate
print("\nTest 8: Valid TaskCreate")
try:
    task = TaskCreate(title="Test Task", description="Test description with details", estimated_hours=5.5)
    print("PASS: Valid task created successfully")
    print(f"Task title: {task.title}")
except ValidationError as e:
    print(f"FAIL: Unexpected ValidationError: {e}")

print("\n" + "="*60)
print("VALIDATION TESTING COMPLETE")
print("="*60)
