#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta

# Login to get token
login_response = requests.post(
    'http://localhost:8000/api/auth/login',
    json={
        'email': 'feature53test@example.com',
        'password': 'testpass123'
    }
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.text)
    exit(1)

token = login_response.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Create 5 test tasks with different priorities and due dates
tasks = [
    {
        "title": "Feature 53 Test Task 1 - Critical Priority",
        "description": "Test export functionality with critical priority task",
        "priority": "Critical",
        "status": "open",
        "due_date": (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    },
    {
        "title": "Feature 53 Test Task 2 - High Priority",
        "description": "Test export with high priority task",
        "priority": "High",
        "status": "in_progress",
        "due_date": (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    },
    {
        "title": "Feature 53 Test Task 3 - Medium Priority",
        "description": "Test export with medium priority task",
        "priority": "Medium",
        "status": "pending_evidence",
        "due_date": (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    },
    {
        "title": "Feature 53 Test Task 4 - Low Priority",
        "description": "Test export with low priority task",
        "priority": "Low",
        "status": "completed",
        "due_date": (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d')
    },
    {
        "title": "Feature 53 Test Task 5 - Overdue Task",
        "description": "Test export with overdue task",
        "priority": "High",
        "status": "open",
        "due_date": (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    }
]

created_count = 0
for task in tasks:
    response = requests.post(
        'http://localhost:8000/api/tasks',
        headers=headers,
        json=task
    )
    if response.status_code == 200:
        created_count += 1
        print(f"✓ Created: {task['title']}")
    else:
        print(f"✗ Failed to create {task['title']}: {response.status_code}")
        print(response.text)

print(f"\n{created_count}/{len(tasks)} tasks created successfully!")
